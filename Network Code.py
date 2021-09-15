# -*- coding: utf-8 -*-
"""
Created on Tue Feb  2 17:34:31 2021

@author: user
"""


import salabim as sim
import random
import numpy as np
import pandas as pd


excel_data_df = pd.read_excel('Book1.xlsx')
phc_covid_iat = excel_data_df['phc_iat'].tolist()
chc_covid_iat = excel_data_df['chc_iat'].tolist()
dh_covid_iat = excel_data_df['dh_iat'].tolist()
print(phc_covid_iat)


class PatientGenerator(sim.Component):
    total_OPD_patients = 0

    def process(self):

        global env
        global warmup_time
        global opd_iat_chc1
        global days
        global admin_work_chc1
        global q_len_chc1

        while env.now() <= warmup_time:
            x = (env.now() - days * 1440)  # x is calculated for OPD timing
            if 0 <= x <= 360:
                Registration()
                o = sim.Exponential(opd_iat_chc1).sample()
                yield self.hold(o)
                days = int(env.now() / 1440)
            else:
                # changed here
                yield self.hold(1080)
                days = int(env.now() / 1440)

        while env.now() > warmup_time:
            if 0 <= (env.now() - days * 1440) < 360:
                PatientGenerator.total_OPD_patients += 1
                Registration()
                o = sim.Exponential(opd_iat_chc1).sample()
                yield self.hold(o)
                days = int(env.now() / 1440)
            else:

                admin_work_chc1 += 0#int(sim.Normal(60, 10).bounded_sample(40, 80))
                yield self.hold(1080)
                days = int(env.now() / 1440)


class Registration(sim.Component):
    Patient_log = {}

    def setup(self):

        self.dic = {}  # local dictionary for temporarily   storing generated patients
        # with attributes
        self.time_of_visit = [[0], [0], [0]]  # initializing for assigning time of visits
        self.regis_time = round(env.now())  # registration time is the current simulation time
        self.id = PatientGenerator.total_OPD_patients  # patient count is patient id
        self.age_random = random.randint(0, 1000)  # assigning age to population based on census 2011 gurgaon
        if self.age_random <= 578:
            self.age = random.randint(0, 30)
        else:
            self.age = random.randint(31, 100)
        self.sex = random.choice(["male", "female"])  # Equal probability of male and female patient
        # require lab tests
        self.lab_required = random.randint(0, 100)  # Considering nearly half of all the patients
        self.radiography_required = random.choice(["True", "False"])
        y = random.randint(0, 999)
        self.consultation = random.choice([y])  # for medicine, gynea, pead, denta
        self.visits_assigned = random.randint(1, 10)  # assigning number of visits visits
        self.dic = {"ID": self.id, "Age": self.age, "Sex": self.sex, "Lab": self.lab_required,
                    "Registration_Time": self.regis_time, "No_of_visits": self.visits_assigned,
                    "Time_of_visit": self.time_of_visit, "Radiography": self.radiography_required,
                    "Consultation": self.consultation}
        Registration.Patient_log[PatientGenerator.total_OPD_patients] = self.dic

        self.process()

    def process(self):

        global registration_time
        global registration_q
        global registration_clerk
        global r_time_lb
        global r_time_ub
        global registration_q_waiting_time
        global registration_q_length
        global warmup_time
        global total_opds
        global medicine_count

        if env.now() <= warmup_time:
            self.enter(registration_q)
            yield self.request((registration_clerk, 1))
            self.leave(registration_q)
            r_time = sim.Uniform(r_time_lb, r_time_ub).sample()
            yield self.hold(r_time)
            OPD()
        else:
            total_opds += 1
            entry_time = env.now()
            self.enter(registration_q)
            yield self.request(registration_clerk)
            self.leave(registration_q)
            exit_time = env.now()
            q_time = exit_time - entry_time
            registration_q_waiting_time.append(q_time)
            r_time = sim.Uniform(r_time_lb, r_time_ub).sample()
            yield self.hold(r_time)
            self.release(registration_clerk)
            registration_time += r_time
            x = Registration.Patient_log[PatientGenerator.total_OPD_patients]["Consultation"]
            if x < 1000:  # no dental and childbirth in CHC 2
                if x < 200:  # 20 % are tested for covid
                    opd_covid()
                else:
                    OPD()


class OPD(sim.Component):

    def process(self):

        global c
        global medicine_q
        global doc_OPD
        global opd_ser_time_mean
        global opd_ser_time_sd
        global medicine_count
        global medicine_cons_time
        global opd_q_waiting_time
        global ncd_count
        global ncd_nurse
        global ncd_time
        global warmup_time
        global medicine_count
        global days
        global q_len_chc1

        if env.now() <= warmup_time:
            self.enter(medicine_q)
            yield self.request(doc_OPD)
            self.leave(medicine_q)
            o = sim.Normal(opd_ser_time_mean, opd_ser_time_sd).bounded_sample(0.5)
            yield self.hold(o)
            self.release(doc_OPD)
        if env.now() > warmup_time:
            if 0 <= (env.now() - days * 1440) <= 360:
                medicine_count += 1
                if Registration.Patient_log[PatientGenerator.total_OPD_patients]["Age"] > 30:
                    ncd_count += 1
                    yield self.request(ncd_nurse)
                    ncd_service = sim.Uniform(2, 5).sample()
                    yield self.hold(ncd_service)
                    ncd_time += ncd_service
                # doctor opd starts from here
                entry_time = env.now()
                self.enter(medicine_q)
                yield self.request(doc_OPD)
                self.leave(medicine_q)
                exit_time = env.now()
                opd_q_waiting_time.append(exit_time - entry_time)  # stores waiting time in the queue
                o = sim.Normal(opd_ser_time_mean, opd_ser_time_sd).bounded_sample(0.5)
                yield self.hold(o)
                medicine_cons_time += o
                self.release(doc_OPD)
                # lab starts from here
              
                t = random.randint(0, 1000)
                if t < 206:
                    Lab()

                # pharmacy starts from here
                Pharmacy()
            else:
                q_len_chc1.append(len(medicine_q))


class Pharmacy(sim.Component):

    def process(self):

        global pharmacist
        global pharmacy_time
        global pharmacy_q
        global pharmacy_q_waiting_time
        global warmup_time
        global pharmacy_count

        if env.now() < warmup_time:
            self.enter(pharmacy_q)
            yield self.request(pharmacist)
            self.leave(pharmacy_q)
            service_time = sim.Uniform(1, 2.5).sample()
            yield self.hold(service_time)
            self.release(pharmacist)
        else:
            pharmacy_count += 1
            e1 = env.now()
            self.enter(pharmacy_q)
            yield self.request((pharmacist, 1))
            self.leave(pharmacy_q)
            pharmacy_q_waiting_time.append(env.now() - e1)
            service_time = sim.Uniform(1, 2.5).sample()
            yield self.hold(service_time)
            self.release((pharmacist, 1))
            pharmacy_time += service_time


class Emergency_patient(sim.Component):

    def process(self):
        global emergency_iat

        global warmup_time

        while True:
            if env.now() <= warmup_time:
                Emergency()
                yield self.hold(sim.Exponential(emergency_iat).sample())
            else:
                Emergency()
                yield self.hold(sim.Exponential(emergency_iat).sample())


class Emergency(sim.Component):

    def process(self):

        global emergency_count
        global warmup_time
        global MO
        global emergency_time
        global e_beds
        global ipd_nurse
        global emergency_nurse_time
        global emergency_bed_time
        global in_beds
        global ipd_bed_time
        global ipd_nurse_time
        global emer_inpatients
        global emer_nurse
        global lab_q
        global lab_technician
        global lab_time
        global lab_q_waiting_time
        global xray_tech
        global radio_time
        global xray_q
        global xray_q_waiting_time
        global emergency_refer
        global ipd_q
        global ipd_MO_time_chc1
        global emr_q
        global emr_q_waiting_time
        global ipd_bed_wt_chc1

        if env.now() < warmup_time:
            z = random.randint(0, 100)
            if z < 11:
                pass
            else:
                y = random.randint(0, 1000)
                "Patients go to lab and/or radiography lab before getting admitted to emergency"
                if y < 494:  # 50% emergency patients require lab tests
                    a = env.now()  # for scheduling lab tests during OPD hours
                    c = a / 1440  # divides a by minutes in a day
                    d = c % 1  # takes out the decimal part from c
                    e = d * 1440  # finds out the minutes corrosponding to decimal part
                    if 0 < e <= 480:  # if it is in OPD region calls lab
                        Lab()
                    else:  # Schedules it to the next day
                        j = 1440 - e
                        Lab(at=a + j + 1)
                if 52 < y < 70:  # 17.6% of the total patients require radiography
                    y3 = random.randint(0, 100)
                    if y3 < 50:  # 50 % patients for xray
                        c = env.now() / 1440
                        d = c % 1
                        e = d * 1440
                        if 0 < e <= 480:
                            pass
                        else:  # Schedules it to the next day
                            j = 1440 - e
                            pass
                    else:
                        c = env.now() / 1440
                        d = c % 1
                        e = d * 1440
                        if 0 < e <= 480:
                            pass
                        else:  # Schedules it to the next day
                            j = 1440 - e
                            pass
                yield self.request(MO, emer_nurse, e_beds)
                doc_time = sim.Uniform(10, 20).sample()
                yield self.hold(doc_time)
                self.release(MO)
                nurse_time = sim.Uniform(20, 30).sample()
                yield self.hold((nurse_time - doc_time))  # subtracting just to account nurse time
                self.release(emer_nurse)
                stay = random.uniform(60, 300)
                yield self.hold(stay)
                self.release(e_beds)
                x = random.randint(0, 10)
                if x < 5:  # only 50% patients require inpatient care
                    yield self.request(in_beds)

                    yield self.request(ipd_nurse)
                    t_nurse = sim.Uniform(10, 20).sample()
                    t_bed = sim.Triangular(120, 1440, 240).sample()
                    yield self.hold(t_nurse)
                    self.release(ipd_nurse)
                    yield self.hold(t_bed - t_nurse)
                    self.release(in_beds)
        else:
            # referrals
            self.enter(emr_q)
            c = env.now()
            yield self.request(MO)
            self.leave(emr_q)
            emr_q_waiting_time.append(env.now() - c)
            doc_time = sim.Uniform(10, 20).sample()
            emergency_time += doc_time
            yield self.hold(doc_time)
            self.release(MO)
            z = random.randint(0, 100)
            if z < 11:
                emergency_refer += 1
            else:
                emergency_count += 1
                y = random.randint(0, 100)
                "Patients go to lab and/or radiography lab before getting admitted to emergency"
                if y < 52:  # 52% emergency patients require lab tests
                    a = env.now()  # for scheduling lab tests during OPD hours
                    c = a / 1440  # divides a by minutes in a day
                    d = c % 1  # takes out the decimal part from c
                    e = d * 1440  # finds out the minutes corrsponding to decimal part
                    if 0 < e <= 480:  # if it is in OPD region calls lab
                        Lab()
                    else:  # Schedules it to the next day
                        j = 1440 - e
                        Lab(at=a + j + 1)
                if 52 <= y < 69:  # 17.3% of the total patients require radiography
                    ys = random.randint(0, 100)
                    if ys < 50:  # 50% patients for X-Rays
                        c = env.now() / 1440
                        d = c % 1
                        e = d * 1440
                        if 0 < e <= 480:
                            pass                        
                    else:  # 50% patients for ecg
                        c = env.now() / 1440
                        d = c % 1
                        e = d * 1440
                        if 0 < e <= 480:
                           pass
                        else:  # Schedules it to the next day
                            j = 1440 - e
                            pass
                            #Ecg(at=env.now() + j + 1)
                yield self.request(emer_nurse)
                nurse_time = sim.Uniform(20, 30).sample()
                emergency_nurse_time += nurse_time
                yield self.hold(nurse_time)  # subtracting just to account nurse time
                self.release(emer_nurse)
                yield self.request(e_beds)
                stay = random.uniform(60, 300)
                emergency_bed_time += stay
                yield self.hold(stay)
                self.release(e_beds)
                x = random.randint(0, 10)
                if x < 5:  # only 50% patients require inpatient care
                    emer_inpatients += 1
                    self.enter(ipd_q)
                    h = env.now()
                    yield self.request(in_beds)
                    self.leave(ipd_q)
                    ipd_bed_wt_chc1.append(env.now() - h)
                    yield self.request(ipd_nurse)
                    t_nurse = sim.Uniform(10, 20).sample()
                    t_bed = sim.Triangular(120, 1440, 240).sample()
                    yield self.hold(t_nurse)
                    ipd_nurse_time += t_nurse
                    self.release(ipd_nurse)
                    yield self.hold(t_bed - t_nurse)
                    h = env.now()
                    self.release(in_beds)
                    ipd_bed_time += t_bed
                    ipd_MO_time_chc1 += t_nurse


class Delivery_patient_generator(sim.Component):

    def process(self):
        global delivery_iat
        global warmup_time
        global delivery_count

        while True:
            if env.now() <= warmup_time:
                Delivery_ipd()
                t = sim.Exponential(delivery_iat).sample()
                yield self.hold(t)
            else:
                Delivery_ipd()
                t = sim.Exponential(delivery_iat).sample()
                yield self.hold(t)


class Delivery_ipd(sim.Component):

    def process(self):
        global in_beds
        global ipd_nurse
        global ipd_nurse_time
        global MO
        global warmup_time
        global childbirth_count
        global childbirth_referred
        global ipd_MO_time_chc1
        global ipd_bed_time
        global ipd_q
        global ipd_bed_wt_chc1

        if env.now() <= warmup_time:
            pass
        else:
            childbirth_count += 1
            x = random.randint(0, 100)
            if x <= 4:
                childbirth_referred += 1
                pass
            else:
                self.enter(ipd_q)
                h = env.now()
                yield self.request((in_beds, 1))
                self.leave(ipd_q)
                ipd_bed_wt_chc1.append(env.now() - h)
                yield self.request(ipd_nurse)
                t1 = sim.Uniform(10, 20).sample()
                ipd_nurse_time += t1
                self.hold(t1)
                self.release(ipd_nurse)
                yield self.request(MO)
                t2 = sim.Uniform(5, 10).sample()
                ipd_MO_time_chc1 += t2
                yield self.hold(t2)
                self.release(MO)
                t3 = sim.Uniform(240, 360).sample()
                yield self.hold(t3 - t2 - t1)
                ipd_bed_time += (t3 - t2 - t1)
                self.release(in_beds)
                Delivery()


class Delivery(sim.Component):

    def process(self):
        global delivery_nurse
        global ipd_nurse
        global MO
        global delivery_bed
        global warmpup_time
        global e_beds
        global ipd_nurse_time
        global MO_del_time
        global in_beds
        global delivery_nurse_time
        global inpatient_del_count
        global delivery_count
        global emergency_bed_time
        global ipd_bed_time
        global emergency_nurse_time
        global referred
        global ipd_bed_wt_chc1

        if env.now() <= warmup_time:
            t_doc = sim.Uniform(30, 60).sample()
            t_bed = sim.Uniform(240, 600).sample()
            yield self.request(MO, fail_delay=20)
            if self.failed():  # if doctor is busy staff nurse takes care
                yield self.request(delivery_nurse, delivery_bed)
                yield self.hold(t_bed)
                self.release(delivery_nurse)
                self.release(delivery_bed)
            else:
                yield self.hold(t_doc)
                self.release(MO)
                yield self.request(delivery_nurse, delivery_bed)
                yield self.hold(t_bed)
                self.release(delivery_nurse)
                self.release(delivery_bed)
        else:
            delivery_count += 1
            inpatient_del_count += 1
            yield self.request(MO, fail_delay=20)
            t_doc = sim.Uniform(30, 60).sample()
            t_bed = sim.Uniform(240, 600).sample()  # delivery bed, nurse time
            delivery_nurse_time += t_bed
            if self.failed():  # if doctor is busy staff nurse takes care
                yield self.request(delivery_nurse, delivery_bed)
                yield self.hold(t_bed)
                self.release(delivery_nurse)  # delivery nurse and delivery beds are released simultaneoulsy
                self.release(delivery_bed)
                # after delivery patient shifts to IPD and requests nurse and inpatient bed
                yield self.request(in_beds)
                yield self.request(ipd_nurse)
                t_n = sim.Uniform(20, 30).sample()  # inpatient nurse time in ipd after delivery
                t_bed2 = sim.Uniform(1440, 2880).sample()  # inpatient beds post delivery stay
                yield self.hold(t_n)
                self.release(ipd_nurse)
                ipd_nurse_time += t_n
                yield self.hold(t_bed2 - t_n)
                self.release(in_beds)
                ipd_bed_time += t_bed2

            else:
                MO_del_time += t_doc  # MO
                yield self.hold(t_doc)
                self.release(MO)
                yield self.request(delivery_nurse, delivery_bed)
                yield self.hold(t_bed)
                self.release(delivery_nurse)  # delivery nurse and delivery beds are released simultaneoulsy
                self.release(delivery_bed)
                h = env.now()
                yield self.request(in_beds)
                ipd_bed_wt_chc1.append(env.now() - h)
                yield self.request(ipd_nurse)
                t_n = sim.Uniform(20, 30).sample()  # staff nurser time in ipd after delivery
                t_bed1 = sim.Uniform(1440, 2880).sample()
                yield self.hold(t_n)
                self.release(ipd_nurse)
                ipd_nurse_time += t_n
                yield self.hold(t_bed1 - t_n)
                ipd_bed_time += t_bed1


class Lab(sim.Component):

    def process(self):
        global lab_q
        global lab_technician
        global lab_time
        global lab_q_waiting_time
        global warmup_time
        global lab_count

        if env.now() <= warmup_time:
            self.enter(lab_q)
            yield self.request(lab_technician)
            self.leave(lab_q)
            yp = (np.random.lognormal(5.332, 0.262))
            y0 = yp / 60
            yield self.hold(y0)
            self.release(lab_technician)
        else:
            lab_count += 1
            self.enter(lab_q)
            a0 = env.now()
            yield self.request(lab_technician)
            self.leave(lab_q)
            lab_q_waiting_time.append(env.now() - a0)
            yp = (np.random.lognormal(5.332, 0.262))
            y0 = yp / 60
            yield self.hold(y0)
            self.release(lab_technician)
            lab_time += y0


class IPD(sim.Component):

    def process(self):
        global MO_ipd_chc1
        global ipd_nurse
        global in_beds
        global ipd_MO_time_chc1
        global ipd_nurse_time
        global warmup_time
        global ipd_bed_time
        global ipd_nurse_time
        global emergency_refer
        global ipd_q
        global ipd_bed_wt_chc1
        global ipd_MO_time_chc1

        if env.now() <= warmup_time:
            self.enter(ipd_q)
            yield self.request(in_beds)
            self.leave(ipd_q)
            yield self.request(ipd_nurse)
            yield self.request(MO_ipd_chc1)
            t_doc = sim.Uniform(10, 20).sample()
            t_nurse = sim.Uniform(20, 30).sample()
            t_bed = sim.Uniform(240, 4880).sample()
            yield self.hold(t_doc)
            self.release(MO_ipd_chc1)
            yield self.hold(t_nurse - t_doc)
            self.release(ipd_nurse)
            yield self.hold(t_bed - t_nurse - t_doc)
            self.release(in_beds)
        else:
            self.enter(ipd_q)
            h = env.now()
            yield self.request(in_beds)
            self.leave(ipd_q)
            ipd_bed_wt_chc1.append(env.now() - h)  # manually calculating ipd waiting time
            yield self.request(ipd_nurse)
            yield self.request(MO_ipd_chc1)

            t_doc = sim.Uniform(10, 20).sample()
            t_nurse = sim.Uniform(20, 30).sample()
            t_bed = sim.Uniform(240, 4880).sample()
            ipd_bed_time += t_bed
            ipd_MO_time_chc1 += t_doc
            yield self.hold(t_doc)
            self.release(MO_ipd_chc1)
            yield self.hold(t_nurse - t_doc)
            ipd_nurse_time += t_nurse
            self.release(ipd_nurse)
            # lab starts from here
            x = random.randint(0, 1000)  # for lab
            if x <= 346:  # 34.6% (2) patients for lab. Of them 12.5% go to radiography
                a = env.now()  # for scheduling lab tests during OPD hours
                c = a / 1440  # divides a by minutes in a day
                d = c % 1  # takes out the decimal part from c
                e = d * 1440  # finds out the minutes corr0sponding to decimal part
                if 0 < e <= 480:  # if it is in OPD region calls lab
                    Lab()
                else:  # Schedules it to the next day
                    j = 1440 - e
                    Lab(at=a + j + 1)
            p = random.randint(0, 1000)  # for radiography
            if p < 125:  # 12.5% of the total patients require radiography
                y0 = random.randint(0, 10)
                if y0 < 5:  # 50 % patients for X-Ray
                    a = env.now()  # for scheduling lab tests during OPD hours
                    c = a / 1440  # divides a by minutes in a day
                    d = c % 1  # takes out the decimal part from c
                    e = d * 1440  # finds out the minutes corrsponding to decimal part
                    if 0 < e <= 480:  # if it is in OPD region calls lab
                        pass
                        #Xray()
                    else:  # Schedules it to the next day
                        j = 1440 - e
                        pass
                        #Xray(at=a + j + 1)
                else:
                    a = env.now()  # for scheduling lab tests during OPD hours
                    c = a / 1440  # divides a by minutes in a day
                    d = c % 1  # takes out the decimal part from c
                    e = d * 1440  # finds out the minutes corrsponding to decimal part
                    if 0 < e <= 480:  # if it is in OPD region calls lab

                        pass
                    else:  # Schedules it to the next day
                        j = 1440 - e
                        pass
            yield self.hold(t_bed - t_nurse - t_doc)
            self.release(in_beds)


class ANC(sim.Component):
    global ANC_iat
    global day
    day = 0
    env = sim.Environment()
    No_of_shifts = 0  # tracks number of shifts completed during the simulation time
    No_of_days = 0
    ANC_List = {}
    anc_count = 0
    ANC_p_count = 0

    def process(self):

        global day

        while True:  # condition to run simulation for 8 hour shifts
            x = env.now() - 1440 * days
            if 0 <= x < 480:
                ANC.anc_count += 1    # counts overall patients throghout simulation
                ANC.ANC_p_count += 1  # counts patients in each replication
                id = ANC.anc_count
                age = 223
                day_of_registration = ANC.No_of_days
                visit = 1
                x0 = round(env.now())
                x1 = x0 + 14 * 7 * 24 * 60
                x2 = x0 + 20 * 7 * 24 * 60
                x3 = x0 + 24 * 7 * 24 * 60
                scheduled_visits = [[0], [0], [0], [0]]
                scheduled_visits[0] = x0
                scheduled_visits[1] = x1
                scheduled_visits[2] = x2
                scheduled_visits[3] = x3
                dic = {"ID": id, "Age": age, "Visit Number": visit, "Registration day": day_of_registration,
                       "Scheduled Visit": scheduled_visits}
                ANC.ANC_List[id] = dic
                ANC_Checkup()
                ANC_followup(at=ANC.ANC_List[id]["Scheduled Visit"][1])
                ANC_followup(at=ANC.ANC_List[id]["Scheduled Visit"][2])
                ANC_followup(at=ANC.ANC_List[id]["Scheduled Visit"][3])
                hold_time = sim.Exponential(ANC_iat).sample()
                yield self.hold(hold_time)
            else:
                yield self.hold(960)
                day = int(env.now() / 1440)  # holds simulation for 2 shifts


class ANC_Checkup(sim.Component):
    anc_checkup_count = 0

    def process(self):

        global warmup_time
        global delivery_nurse
        global delivery_nurse_time

        if env.now() <= warmup_time:
            yield self.request(delivery_nurse)
            temp = sim.Triangular(8, 20.6, 12.3).sample()
            yield self.hold(temp)  # time taken from a study on ANC visits in Tanzania
            Lab()
            Pharmacy()

        else:
            ANC_Checkup.anc_checkup_count += 1
            yield self.request(delivery_nurse)
            temp = sim.Triangular(8, 20.6, 12.3).sample()
            delivery_nurse_time += temp
            yield self.hold(temp)  # time taken from a study on ANC visits in Tanzania
            Lab()
            Pharmacy()


class ANC_followup(sim.Component):
    followup_count = 0

    def process(self):

        global warmup_time
        global delivery_nurse
        global q_ANC
        global delivery_nurse_time

        if env.now() <= warmup_time:
            for key in ANC.ANC_List:  # for identifying and updating ANC visit number
                x0 = env.now()
                x1 = ANC.ANC_List[key]["Scheduled Visit"][1]
                x2 = ANC.ANC_List[key]["Scheduled Visit"][2]
                x3 = ANC.ANC_List[key]["Scheduled Visit"][3]
                if 0 <= (x1 - x0) < 481:
                    ANC.ANC_List[key]["Scheduled Visit"][1] = float("inf")
                    ANC.ANC_List[key]["Visit Number"] = 2
                elif 0 <= (x2 - x0) < 481:
                    ANC.ANC_List[key]["Scheduled Visit"][2] = float("inf")
                    ANC.ANC_List[key]["Visit Number"] = 3
                elif 0 <= (x3 - x0) < 481:
                    ANC.ANC_List[key]["Scheduled Visit"][3] = float("inf")
                    ANC.ANC_List[key]["Visit Number"] = 4

            yield self.request(delivery_nurse)
            temp = sim.Triangular(3.33, 13.16, 6.50).sample()
            yield self.hold(temp)
            self.release(delivery_nurse)
            Lab()
            Pharmacy()

        else:
            for key in ANC.ANC_List:  # for identifying and updating ANC visit number
                x0 = env.now()
                x1 = ANC.ANC_List[key]["Scheduled Visit"][1]
                x2 = ANC.ANC_List[key]["Scheduled Visit"][2]
                x3 = ANC.ANC_List[key]["Scheduled Visit"][3]
                if 0 <= (x1 - x0) < 481:
                    ANC.ANC_List[key]["Scheduled Visit"][1] = float("inf")
                    ANC.ANC_List[key]["Visit Number"] = 2
                elif 0 <= (x2 - x0) < 481:
                    ANC.ANC_List[key]["Scheduled Visit"][2] = float("inf")
                    ANC.ANC_List[key]["Visit Number"] = 3
                elif 0 <= (x3 - x0) < 481:
                    ANC.ANC_List[key]["Scheduled Visit"][3] = float("inf")
                    ANC.ANC_List[key]["Visit Number"] = 4

            yield self.request(delivery_nurse)
            temp = sim.Triangular(3.33, 13.16, 6.50).sample()
            yield self.hold(temp)
            self.release(delivery_nurse)
            rand = random.randint(0, 10)
            if rand < 3:  # only 30 % ANC checks require consultation
                # Gynecologist_OPD()
                pass
            Lab()
            Pharmacy()


class Surgery_patient_generator(sim.Component):

    def process(self):

        global warmup_time
        global surgery_count
        global surgery_iat

        while True:
            if env.now() <= warmup_time:
                OT()
                yield self.hold(sim.Exponential(surgery_iat).sample())
            else:
                surgery_count += 1
                OT()
                yield self.hold(sim.Exponential(surgery_iat).sample())


class OT(sim.Component):

    def process(self):

        global warmup_time
        global doc_surgeon
        global doc_ans
        global sur_time
        global ans_time
        global ot_nurse
        global ot_nurse_time
        global ipd_surgery_count

        if env.now() <= warmup_time:
            yield self.request(doc_surgeon, doc_ans, ot_nurse)
            surgery_time = sim.Uniform(20, 60).sample()
            yield self.hold(surgery_time)
            self.release(doc_ans, doc_surgeon, ot_nurse)
            IPD()
        else:
            yield self.request(doc_surgeon, doc_ans, ot_nurse)
            surgery_time = sim.Uniform(20, 60).sample()
            sur_time += surgery_time
            ans_time += surgery_time
            ot_nurse_time += surgery_time
            yield self.hold(surgery_time)
            self.release(doc_ans, doc_surgeon, ot_nurse)
            IPD()
            ipd_surgery_count += 1


"This class is for testing the regular OPD patients "


class opd_covid(sim.Component):

    def process(self):
        global covid_q
        global warmup_time
        global ipd_nurse
        global ipd_nurse_time
        global lab_technician
        global lab_time
        global lab_q_waiting_time
        global ipd_nurse_time

        if env.now() <= warmup_time:
            self.enter(covid_q)
            yield self.request(ipd_nurse)
            self.leave(covid_q)
            h1 = sim.Uniform(5, 10).sample()
            yield self.hold(h1)
            self.release(ipd_nurse)
            yield self.request(lab_technician)
            yield self.hold(sim.Uniform(1, 2).sample())
            self.release(lab_technician)
            yield self.hold(sim.Uniform(15, 30).sample())  # patient waits for the result
        else:
            x = random.randint(0, 100)
            self.enter(covid_q)
            yield self.request(ipd_nurse)
            self.leave(covid_q)
            h1 = sim.Uniform(5, 10).sample()
            yield self.hold(h1)
            self.release(ipd_nurse)
            ipd_nurse_time += h1
            yield self.request(lab_technician)
            t = sim.Uniform(1, 2).sample()
            yield self.hold(t)
            lab_time += t
            self.release(lab_technician)
            yield self.hold(sim.Uniform(15, 30).sample())  # patient waits for the result
            Pharmacy()


class CovidGenerator(sim.Component):

    def process(self):
        global d
        global warmup_time
        global chc1_covid_iat
        global ia_covid_chc
        global d_cc_chc1
        global e_cc_chc1
        global f_cc_chc1
        global d_dh_chc1
        global e_dh_chc1
        global f_dh_chc1
        global t_s_chc1
        global t_m_chc1
        global array_d_cc_chc1
        global array_e_cc_chc1
        global array_f_cc_chc1
        global array_d_dh_chc1
        global array_e_dh_chc1
        global array_f_dh_chc1
        global t_m_chc1
        global t_c_chc1
        global t_b_chc1
        global t_a_chc1
        global a_cc_chc1
        global b_cc_chc1
        global c_cc_chc1
        global a_dh_chc1
        global b_dh_chc1
        global c_dh_chc1
        global t_d_chc1
        global t_e_chc1
        global t_f_chc1
        global array_t_s_chc1
        global array_t_d_chc1
        global array_t_e_chc1
        global array_t_f_chc1
        global array_t_m_chc1
        global array_t_a_chc1
        global array_t_b_chc1
        global array_t_c_chc1
        global array_a_cc_chc1
        global array_b_cc_chc1
        global array_c_cc_chc1
        global array_a_dh_chc1
        global array_b_dh_chc1
        global array_c_dh_chc1
        global array_t_s_chc1
        global j

        while True:
            if env.now() < warmup_time:
                if 0 <= (env.now() - d * 1440) < 480:
                    covid_chc1()
                    yield self.hold(1440 / 3)
                    d = int(env.now() / 1440)
                else:
                    yield self.hold(960)
                    d = int(env.now() / 1440)
            else:
                a = chc_covid_iat[j]
                if 0 <= (env.now() - d * 1440) < 480:
                    covid_chc1()

                    yield self.hold(sim.Exponential(a).sample())
                    d = int(env.now() / 1440)
                else:
                    # the proportion referred are updated each day and then set to zero for the next day
                    array_d_cc_chc1.append(d_cc_chc1)  # daily proportion of patients referred
                    array_e_cc_chc1.append(e_cc_chc1)
                    array_f_cc_chc1.append(f_cc_chc1)
                    array_d_dh_chc1.append(d_dh_chc1)
                    array_e_dh_chc1.append(e_dh_chc1)
                    array_f_dh_chc1.append(f_dh_chc1)
                    array_a_cc_chc1.append(a_cc_chc1)  # daily proportion of patients referred
                    array_b_cc_chc1.append(b_cc_chc1)
                    array_c_cc_chc1.append(c_cc_chc1)
                    array_a_dh_chc1.append(a_dh_chc1)
                    array_b_dh_chc1.append(b_dh_chc1)
                    array_c_dh_chc1.append(c_dh_chc1)
                    array_t_a_chc1.append(t_a_chc1)
                    array_t_b_chc1.append(t_b_chc1)
                    array_t_c_chc1.append(t_c_chc1)
                    array_t_d_chc1.append(t_d_chc1)
                    array_t_e_chc1.append(t_e_chc1)
                    array_t_f_chc1.append(t_f_chc1)
                    array_t_m_chc1.append(t_m_chc1)
                    array_t_s_chc1.append(t_s_chc1)
                    t_a_chc1 = 0
                    t_b_chc1 = 0
                    t_c_chc1 = 0
                    t_d_chc1 = 0
                    t_e_chc1 = 0
                    t_f_chc1 = 0
                    d_cc_chc1 = 0
                    e_cc_chc1 = 0
                    f_cc_chc1 = 0
                    d_dh_chc1 = 0
                    e_dh_chc1 = 0
                    f_dh_chc1 = 0
                    a_cc_chc1 = 0
                    b_cc_chc1 = 0
                    c_cc_chc1 = 0
                    a_dh_chc1 = 0
                    b_dh_chc1 = 0
                    c_dh_chc1 = 0
                    t_s_chc1 = 0
                    t_m_chc1 = 0

                    yield self.hold(960)
                    d = int(env.now() / 1440)


class covid_chc1(sim.Component):

    def process(self):

        global home_refer
        global chc_refer
        global dh_refer_chc1
        global isolation_ward_refer_from_CHC
        global covid_patient_time_chc1
        global covid_count
        global warmup_time
        global ipd_nurse
        global ipd_nurse_time
        global doc_OPD
        global MO_covid_time_chc1
        global MO_ipd_chc1
        global chc1_to_cc_dist
        global chc1_to_dh_dist
        global ICU_oxygen
        global chc1_to_cc_severe_case
        global chc1_2_cc
        global chc1_2_dh
        global chc1_severe_covid
        global chc1_moderate_covid

        global d_cc_chc1
        global e_cc_chc1
        global f_cc_chc1
        global d_dh_chc1
        global e_dh_chc1
        global f_dh_chc1
        global t_s_chc1
        global t_d_chc1
        global t_e_chc1
        global t_f_chc1

        if env.now() < warmup_time:
            covid_nurse()
            covid_lab()
            x = random.randint(0, 1000)
            if x <= 940:
                yield self.request(doc_OPD)
                yield self.hold(sim.Uniform(3, 6).sample())
                self.release(doc_OPD)
                pass
            elif 940 < x <= 980:
                # CovidCare()
                pass
            else:
                yield self.request(doc_OPD)
                yield self.hold(sim.Uniform(3, 6).sample())
                self.release(doc_OPD)
                # SevereCase()
        else:
            covid_count += 1
            covid_nurse()
            covid_lab()
            x = random.randint(0, 1000)
            if x <= 940:  # mild cases
                home_refer += 1
                yield self.request(doc_OPD)
                f = sim.Uniform(3, 6).sample()
                yield self.hold(f)
                self.release(doc_OPD)
                covid_patient_time_chc1 += f
                a1 = random.randint(0, 100)
                if a1 >= 90:  # 10 % patients referred to cc
                    isolation_ward_refer_from_CHC += 1
                    # chc1_to_cc_dist.append(chc1_2_cc)
                    cc_isolation()  # those patients who can not home quarantine themselves
            elif 940 < x <= 980:  # moderate cases
                CovidCare_chc1()
                chc1_moderate_covid += 1
            else:
                t_s_chc1 += 1  # total per day severe patients
                chc1_severe_covid += 1
                yield self.request(doc_OPD)
                f = sim.Uniform(3, 6).sample()
                yield self.hold(f)
                self.release(doc_OPD)
                covid_patient_time_chc1 += f
                """Bed availability is checked at DH, if no available the send to CC"""
                p = random.randint(0, 100)
                if p < 50:  # % 50 patients require ICU oxygen beds first
                    t_f_chc1 += 1
                    if ICU_oxygen.available_quantity() < 1:  # checks if there is a vacant bed in DH
                        # if no, then patient is sent to CC
                        chc1_to_cc_severe_case += 1
                        chc1_to_cc_dist.append(chc1_2_cc)
                        cc_Type_F()
                        f_cc_chc1 += 1
                    else:
                        DH_SevereTypeF()
                        f_dh_chc1 += 1
                elif 50 <= p < 75:
                    t_e_chc1 += 1
                    if ICU_ventilator.available_quantity() < 1:  # checks if there is a vacant bed in DH
                        chc1_severe_covid += 1
                        cc_ICU_ward_TypeE()
                        e_cc_chc1 += 1
                    else:
                        DH_SevereTypeE()
                        e_dh_chc1 += 1
                else:
                    t_d_chc1 += 1
                    if ICU_ventilator.available_quantity() < 1:
                        d_cc_chc1 += 1
                        cc_ventilator_TypeD()
                    else:
                        chc1_to_dh_dist.append(chc1_2_dh)
                        d_dh_chc1 += 1
                        DH_SevereTypeD()


class covid_nurse(sim.Component):

    def process(self):

        global warmup_time
        global ipd_nurse
        global ipd_nurse_time
        global lab_covidcount

        if env.now() <= warmup_time:
            yield self.request(ipd_nurse)
            yield self.hold(sim.Uniform(2, 3).sample())
            self.release(ipd_nurse)
        else:
            lab_covidcount += 1
            yield self.request(ipd_nurse)
            t = sim.Uniform(2, 3).sample()
            yield self.hold(t)
            ipd_nurse_time += t
            self.release(ipd_nurse)


class covid_lab(sim.Component):

    def process(self):

        global lab_technician
        global lab_time
        global lab_q_waiting_time
        global warmup_time
        global lab_covidcount

        if env.now() <= warmup_time:
            yield self.request(lab_technician)
            yield self.hold(sim.Uniform(1, 2).sample())
            self.release(lab_technician)
            yield self.hold(sim.Uniform(15, 30).sample())  # patient waits for reports
            x = random.randint(0, 100)
            if x < 67:  # confirmed positive
                covid_doc_opd()
            else:  # symptomatic negative, retesting
                retesting()

        else:
            lab_covidcount += 1
            yield self.request(lab_technician)
            t = sim.Uniform(1, 2).sample()
            yield self.hold(t)
            lab_time += t
            self.release(lab_technician)
            yield self.hold(sim.Uniform(15, 30).sample())
            x = random.randint(0, 100)
            if x < 67:  # confirmed positive
                pass
            else:  # symptomatic negative, retesting
                retesting()


class retesting(sim.Component):

    def process(self):

        global retesting_count_chc1
        global warmup_time

        if env.now() <= warmup_time:
            yield self.hold(1440)
            covid_doc_opd()
        else:
            retesting_count_chc1 += 1
            yield self.hold(1440)
            covid_doc_opd()


class covid_doc_opd(sim.Component):  # class for triaging covid patients

    def process(self):

        global doc_OPD
        global warmup_time
        global covid_q
        global covid_patient_time_chc1

        if env.now() <= warmup_time:
            self.enter(covid_q)
            yield self.request(doc_OPD)
            self.leave(covid_q)
            yield self.hold(sim.Uniform(5, 10).sample())
            self.release(doc_OPD)
        else:
            in_time = env.now()
            self.enter(covid_q)
            yield self.request(doc_OPD)
            self.leave(covid_q)
            t = sim.Uniform(5, 10).sample()
            yield self.hold(t)
            self.release(doc_OPD)
            covid_patient_time_chc1 += env.now() - in_time


class CovidCare_chc1(sim.Component):  # for moderate covid patients

    def process(self):
        global covid_bed_chc1
        global ipd_nurse
        global ipd_nurse_time
        global MO
        global warmup_time
        global c_bed_wait
        global moderate_refered_chc1
        global chc1_covid_bed_time
        global chc1_to_dh_dist
        global General_bed_DH
        global chc1_to_cc_dist
        global chc1_to_cc_moderate_case
        global chc1_2_dh
        global chc1_2_cc

        global t_c_chc1
        global t_b_chc1
        global t_a_chc1
        global a_cc_chc1
        global b_cc_chc1
        global c_cc_chc1
        global a_dh_chc1
        global b_dh_chc1
        global c_dh_chc1
        global t_m_chc1

        if env.now() <= warmup_time:
            yield self.request(covid_bed_chc1)
            a7 = sim.Uniform(1440 * 4, 1440 * 5).sample()
            a71 = a7 / (24 * 60)
            a711 = round(a71)
            for a8 in range(0, a711):
                covid_doc_opd(at=env.now() + a8 * 24 * 60)
                covid_nurse(at=env.now() + a8 * 24 * 60)
            yield self.hold(a7)
            self.release(covid_bed_chc1)
        else:
            t_m_chc1 += 1  # total moderate patients
            a = random.randint(0, 100)
            if a < 90:  # 90% cases are said to remain moderate through out
                k = env.now()
                yield self.request(covid_bed_chc1, fail_delay=300)  # checks for bed availability at CHC
                t_a_chc1 += 1  # total a type patients chc1
                if self.failed():
                    if General_bed_DH.available_quantity() < 1:
                        chc1_to_cc_moderate_case += 1
                        chc1_to_cc_dist.append(chc1_2_cc)
                        cc_general_ward_TypeA()
                        a_cc_chc1 += 1
                    else:
                        a_dh_chc1 += 1
                        moderate_refered_chc1 += 1
                        chc1_to_dh_dist.append(chc1_2_dh)
                        ModerateTypeA()
                else:
                    k1 = env.now()
                    c_bed_wait.append(k1 - k)
                    a7 = sim.Uniform(1440 * 4, 1440 * 5).sample()
                    chc1_covid_bed_time += a7
                    a71 = a7 / (12 * 60)
                    a711 = round(a71)
                    for a8 in range(0, a711):
                        covid_doc_ipd_chc1(at=env.now() + a8 * 12 * 60)
                        covid_nurse(at=env.now() + a8 * 12 * 60)
                    yield self.hold(a7)
                    self.release(covid_bed_chc1)
            elif 90 <= a < 98:  # B type patients
                t_b_chc1 += 1  # total b type patients per day
                if General_bed_DH.available_quantity() < 1:
                    chc1_to_cc_moderate_case += 1
                    chc1_to_cc_dist.append(chc1_2_cc)
                    cc_general_ward_TypeB()
                    b_cc_chc1 += 1
                else:
                    b_dh_chc1 += 1
                    moderate_refered_chc1 += 1
                    chc1_to_dh_dist.append(chc1_2_dh)
                    ModerateTypeB()

            else:  # c type patients
                t_c_chc1 += 1
                if General_bed_DH.available_quantity() < 1:
                    chc1_to_cc_moderate_case += 1
                    chc1_to_cc_dist.append(chc1_2_cc)
                    cc_general_ward_TypeC()
                    c_cc_chc1 += 1
                else:
                    moderate_refered_chc1 += 1
                    chc1_to_dh_dist.append(chc1_2_dh)
                    ModerateTypeC()
                    c_dh_chc1 += 1


class covid_doc_ipd_chc1(sim.Component):  # class for triaging covid patients

    def process(self):
        global MO_covid_time_chc1
        global MO_ipd_chc1
        global warmup_time
        global covid_q
        global covid_patient_time_chc1

        if env.now() <= warmup_time:
            yield self.request(MO_ipd_chc1)
            yield self.hold(sim.Uniform(3, 6).sample())
            self.release(MO_ipd_chc1)
        else:
            in_time = env.now()
            yield self.request(MO_ipd_chc1)
            t = sim.Uniform(3 / 2, 6 / 2).sample()
            yield self.hold(t)
            MO_covid_time_chc1 += t
            self.release(MO_ipd_chc1)


# CHC 2
class PatientGenerator_chc2(sim.Component):
    total_OPD_patients_chc2 = 0

    def process(self):

        global env
        global warmup_time
        global opd_iat_chc2
        global days
        global admin_work_chc2  # admin time we have assumed is used foronly one doctor in each dept (MO,IPD, Emergency, one staff nurse only)

        while env.now() <= warmup_time:
            x = (env.now() - days * 1440)  # x is calculated for OPD timing
            if 0 <= x <= 360:
                Registration_chc2()
                o = sim.Exponential(opd_iat_chc2).sample()
                yield self.hold(o)
                days = int(env.now() / 1440)
            else:
                yield self.hold(1080)
                days = int(env.now() / 1440)

        while env.now() > warmup_time:
            if 0 <= (env.now() - days * 1440) < 360:
                PatientGenerator_chc2.total_OPD_patients_chc2 += 1
                Registration_chc2()
                o = sim.Exponential(opd_iat_chc2).sample()
                yield self.hold(o)
                days = int(env.now() / 1440)

            else:
                p = int(sim.Normal(60, 10).bounded_sample(40, 80))
                admin_work_chc2 += 0
                yield self.hold(1080)
                days = int(env.now() / 1440)


class Registration_chc2(sim.Component):
    Patient_log_chc2 = {}

    def setup(self):

        self.dic = {}  # local dictionary for temporarily   storing generated patients
        # with attributes
        self.time_of_visit = [[0], [0], [0]]  # initializing for assigning time of visits
        self.regis_time = round(env.now())  # registration time is the current simulation time
        self.id = PatientGenerator_chc2.total_OPD_patients_chc2  # patient count is patient id
        self.age_random = random.randint(0, 1000)  # assigning age to population based on census 2011 gurgaon
        if self.age_random <= 578:
            self.age = random.randint(0, 30)
        else:
            self.age = random.randint(31, 100)
        self.sex = random.choice(["male", "female"])  # Equal probability of male and female patient
        # require lab tests
        self.lab_required = random.randint(0, 100)  # Considering nearly half of all the patients
        self.radiography_required = random.choice(["True", "False"])
        y = random.randint(0, 999)
        self.consultation = random.choice([y])  # for medicine, gynea, pead, denta
        self.visits_assigned = random.randint(1, 10)  # assigning number of visits visits
        self.dic = {"ID": self.id, "Age": self.age, "Sex": self.sex, "Lab": self.lab_required,
                    "Registration_Time": self.regis_time, "No_of_visits": self.visits_assigned,
                    "Time_of_visit": self.time_of_visit, "Radiography": self.radiography_required,
                    "Consultation": self.consultation}
        Registration_chc2.Patient_log_chc2[PatientGenerator_chc2.total_OPD_patients_chc2] = self.dic

        self.process()

    def process(self):

        global registration_time_chc2
        global registration_q_chc2
        global registration_clerk_chc2
        global r_time_lb_chc2
        global r_time_ub_chc2
        global registration_q_waiting_time_chc2
        global registration_q_length_chc2
        global warmup_time
        global total_opds_chc2
        global medicine_count_chc2

        if env.now() <= warmup_time:
            self.enter(registration_q_chc2)
            yield self.request((registration_clerk_chc2, 1))
            self.leave(registration_q_chc2)
            r_time = sim.Uniform(r_time_lb_chc2, r_time_ub_chc2).sample()
            yield self.hold(r_time)
            OPD_chc2()
        else:

            total_opds_chc2 += 1
            entry_time = env.now()
            self.enter(registration_q_chc2)
            yield self.request(registration_clerk_chc2)
            self.leave(registration_q_chc2)
            exit_time = env.now()
            q_time = exit_time - entry_time
            registration_q_waiting_time_chc2.append(q_time)
            r_time = sim.Uniform(r_time_lb_chc2, r_time_ub_chc2).sample()
            yield self.hold(r_time)
            self.release(registration_clerk_chc2)
            registration_time_chc2 += r_time
            x = Registration_chc2.Patient_log_chc2[PatientGenerator_chc2.total_OPD_patients_chc2]["Consultation"]
            if x < 845:  # 80% medicine OPDs
                OPD_chc2()

            elif 845 <= x <= 933:  # 9% Pediatrics OPD OPDs
                Pediatrics_OPD_chc2()
            else:  # remaining dental OPD
                Dental_OPD_chc2()


class OPD_chc2(sim.Component):

    def process(self):

        global c_chc2
        global medicine_q_chc2
        global doc_OPD_chc2
        global opd_ser_time_mean_chc2
        global opd_ser_time_sd_chc2
        global medicine_count_chc2
        global medicine_cons_time_chc2
        global opd_q_waiting_time_chc2
        global ncd_count_chc2
        global ncd_nurse_chc2
        global ncd_time_chc2
        global warmup_time
        global days
        global q_len_chc2
        global medicine_count_chc2

        if env.now() <= warmup_time:
            g = random.randint(0, 100)
            if g < 20:
                opd_covid_chc2()
            else:
                self.enter(medicine_q_chc2)
                yield self.request(doc_OPD_chc2)
                self.leave(medicine_q_chc2)
                o = sim.Normal(opd_ser_time_mean_chc2, opd_ser_time_sd_chc2).bounded_sample(0.5)
                yield self.hold(o)
                self.release(doc_OPD_chc2)
        if env.now() > warmup_time:
            g = random.randint(0, 100)
            if g < 20:
                opd_covid_chc2()
            else:
                if 0 <= (env.now() - days * 1440) <= 360:
                    medicine_count_chc2 += 1
                    if Registration_chc2.Patient_log_chc2[PatientGenerator_chc2.total_OPD_patients_chc2]["Age"] > 30:
                        ncd_count_chc2 += 1
                        yield self.request(ncd_nurse_chc2)
                        ncd_service = sim.Uniform(2, 5).sample()
                        yield self.hold(ncd_service)
                        ncd_time_chc2 += ncd_service
                    # doctor opd starts from here
                    entry_time = env.now()
                    self.enter(medicine_q_chc2)
                    yield self.request(doc_OPD_chc2)
                    self.leave(medicine_q_chc2)
                    exit_time = env.now()
                    opd_q_waiting_time_chc2.append(exit_time - entry_time)  # stores waiting time in the queue
                    o = sim.Normal(opd_ser_time_mean_chc2, opd_ser_time_sd_chc2).bounded_sample(0.5)
                    yield self.hold(o)
                    medicine_cons_time_chc2 += o
                    self.release(doc_OPD_chc2)
                    # lab starts from here
                    x = random.randint(0, 1000)  # for radiography
                    t = random.randint(0, 1000)
                    if t <= 215:  # 21.5% (53) opd patients
                        Lab_chc2()
                        if t <= 56:  # 5.6% (3) of the lab patients require radiographer
                            y0 = random.randint(0, 10)
                            if y0 < 9:  # 90 % PATIENTS FOR XRAY
                                Xray_chc2()
                            else:
                                Ecg_chc2()
                    if x < 12:  # 1.2% (3) of the total patients require radiography
                        y0 = random.randint(0, 10)
                        if y0 <= 8:  # 90 % PATIENTs FOR XRAY
                            Xray_chc2()
                        else:
                            Ecg_chc2()
                    # pharmacy starts from here
                    Pharmacy_chc2()
                else:
                    q_len_chc2.append(len(medicine_q_chc2))


class Pharmacy_chc2(sim.Component):

    def process(self):

        global pharmacist_chc2
        global pharmacy_time_chc2
        global pharmacy_q_chc2
        global pharmacy_q_waiting_time_chc2
        global warmup_time
        global pharmacy_count_chc2

        if env.now() < warmup_time:
            self.enter(pharmacy_q_chc2)
            yield self.request(pharmacist_chc2)
            self.leave(pharmacy_q_chc2)
            service_time = sim.Uniform(1, 2.5).sample()
            yield self.hold(service_time)
            self.release(pharmacist_chc2)
        else:
            pharmacy_count_chc2 += 1
            e1 = env.now()
            self.enter(pharmacy_q_chc2)
            yield self.request((pharmacist_chc2, 1))
            self.leave(pharmacy_q_chc2)
            pharmacy_q_waiting_time_chc2.append(env.now() - e1)
            service_time = sim.Uniform(1, 2.5).sample()
            yield self.hold(service_time)
            self.release((pharmacist_chc2, 1))
            pharmacy_time_chc2 += service_time


class Pediatrics_OPD_chc2(sim.Component):

    def process(self):

        global warmup_time
        global doc_Ped_chc2
        global ped_q_chc2
        global ped_count_chc2
        global ped_q_waiting_time_chc2
        global ped_time_chc2

        if env.now() <= warmup_time:
            self.enter(ped_q_chc2)
            yield self.request(doc_Ped_chc2)
            self.leave(ped_q_chc2)
            yield self.hold(sim.Triangular(2, 15, 6.36).sample())
            self.release(doc_Ped_chc2)
        else:
            ped_count_chc2 += 1
            e = env.now()
            self.enter(ped_q_chc2)
            yield self.request(doc_Ped_chc2)
            self.leave(ped_q_chc2)
            ped_q_waiting_time_chc2.append(env.now() - e)
            s = sim.Triangular(2, 15, 6.36).sample()
            ped_time_chc2 += s
            yield self.hold(s)
            self.release(doc_Ped_chc2)
            x = random.randint(0, 100)
            if x < 12:  # 12 % go to lab
                Lab_chc2()
            if 32 < x < 37:  # 4% of the total pediatrics patients require Xray
                Xray_chc2()
            Pharmacy_chc2()


class Dental_OPD_chc2(sim.Component):

    def process(self):

        global warmup_time
        global doc_Dentist_chc2
        global den_q_chc2
        global den_count_chc2
        global den_consul_chc2
        global den_proced_chc2
        global den_q_waiting_time_chc2
        global den_time_chc2
        global pharmacist_chc2
        global pharmacy_time_chc2
        global pharmacy_q_chc2
        global pharmacy_q_waiting_time_chc2
        global env

        if env.now() <= warmup_time:
            x = random.randint(0, 100)
            if x <= 63:  # 70 % cases are consultations and remaining are procedures
                e = env.now()
                self.enter(den_q_chc2)
                yield self.request(doc_Dentist_chc2)
                self.leave(den_q_chc2)
                p = round((env.now() - e), 2)
                s = sim.Uniform(2, 10).sample()
                yield self.hold(s)
                self.release(doc_Dentist_chc2)
            else:
                self.enter(den_q_chc2)
                e1 = env.now()
                yield self.request(doc_Dentist_chc2)
                self.leave(den_q_chc2)
                p1 = round((env.now() - e1), 2)
                s = sim.Uniform(10, 30).sample()
                yield self.hold(s)
                self.release(doc_Dentist_chc2)
                self.enter(pharmacy_q_chc2)
                Pharmacy_chc2()
        else:
            den_count_chc2 += 1
            x = random.randint(0, 100)
            if x <= 62:  # 63 % cases are consultations and remaining are procedures
                e = env.now()
                den_consul_chc2 += 1
                self.enter(den_q_chc2)
                yield self.request(doc_Dentist_chc2)
                self.leave(den_q_chc2)
                p = round((env.now() - e), 2)
                den_q_waiting_time_chc2.append(p)
                s = sim.Uniform(2, 10).sample()
                den_time_chc2 += s
                yield self.hold(s)
                self.release(doc_Dentist_chc2)
            else:
                den_proced_chc2 += 1
                self.enter(den_q_chc2)
                e1 = env.now()
                yield self.request(doc_Dentist_chc2)
                self.leave(den_q_chc2)
                p1 = round((env.now() - e1), 2)
                den_q_waiting_time_chc2.append(p1)
                s = sim.Uniform(10, 30).sample()
                den_time_chc2 += s
                yield self.hold(s)
                self.release(doc_Dentist_chc2)
                Pharmacy_chc2()


class Emergency_patient_chc2(sim.Component):

    def process(self):
        global emergency_iat_chc2

        global warmup_time

        while True:
            if env.now() <= warmup_time:
                Emergency_chc2()
                yield self.hold(sim.Exponential(emergency_iat_chc2).sample())
            else:
                Emergency_chc2()
                yield self.hold(sim.Exponential(emergency_iat_chc2).sample())


class Emergency_chc2(sim.Component):

    def process(self):

        global emergency_count_chc2
        global warmup_time
        global MO_chc2
        global emergency_time_chc2
        global e_beds_chc2
        global ipd_nurse_chc2
        global emergency_nurse_time_chc2
        global emergency_bed_time_chc2
        global in_beds_chc2
        global ipd_bed_time_chc2
        global ipd_nurse_time_chc2
        global emer_inpatients_chc2
        global emer_nurse_chc2
        global lab_q_chc2
        global lab_technician_chc2
        global lab_time_chc2
        global lab_q_waiting_time_chc2
        global xray_tech_chc2
        global radio_time_chc2
        global xray_q_chc2
        global xray_q_waiting_time_chc2
        global emergency_refer_chc2
        global ipd_q_chc2
        global ipd_MO_time_chc2
        global ipd_bed_wt_chc2
        global emr_q_chc2
        global emr_q_waiting_time_chc2

        if env.now() < warmup_time:
            z = random.randint(0, 100)
            if z < 11:
                pass
            else:
                y = random.randint(0, 1000)
                "Patients go to lab and/or radiography lab before getting admitted to emergency"
                if y < 494:  # 50% emergency patients require lab tests
                    a = env.now()  # for scheduling lab tests during OPD hours
                    c = a / 1440  # divides a by minutes in a day
                    d = c % 1  # takes out the decimal part from c
                    e = d * 1440  # finds out the minutes corrosponding to decimal part
                    if 0 < e <= 480:  # if it is in OPD region calls lab
                        Lab_chc2()
                    else:  # Schedules it to the next day
                        j = 1440 - e
                        Lab_chc2(at=a + j + 1)
                if 52 < y < 70:  # 17.6% of the total patients require radiography
                    y3 = random.randint(0, 100)
                    if y3 < 50:  # 50 % patients for xray
                        c = env.now() / 1440
                        d = c % 1
                        e = d * 1440
                        if 0 < e <= 480:
                            Xray_chc2()
                        else:  # Schedules it to the next day
                            j = 1440 - e
                            Xray_chc2(at=env.now() + j + 1)
                    else:
                        c = env.now() / 1440
                        d = c % 1
                        e = d * 1440
                        if 0 < e <= 480:
                            Ecg_chc2()
                        else:  # Schedules it to the next day
                            j = 1440 - e
                            Ecg_chc2(at=env.now() + j + 1)
                yield self.request(MO_chc2, emer_nurse_chc2, e_beds_chc2)
                doc_time = sim.Uniform(10, 20).sample()
                yield self.hold(doc_time)
                self.release(MO_chc2)
                nurse_time = sim.Uniform(20, 30).sample()
                yield self.hold((nurse_time - doc_time))  # subtracting just to account nurse time
                self.release(emer_nurse_chc2)
                stay = random.uniform(60, 300)
                yield self.hold(stay)
                self.release(e_beds_chc2)
                x = random.randint(0, 10)
                if x < 5:  # only 50% patients require inpatient care
                    yield self.request(in_beds_chc2, ipd_nurse_chc2)
                    t_nurse = sim.Uniform(10, 20).sample()
                    t_bed = sim.Triangular(120, 1440, 240).sample()
                    yield self.hold(t_nurse)
                    self.release(ipd_nurse_chc2)
                    yield self.hold(t_bed - t_nurse)
                    self.release(in_beds_chc2)
        else:
            # referrals
            self.enter(emr_q_chc2)
            c = env.now()
            yield self.request(MO_chc2)
            self.leave(emr_q_chc2)
            emr_q_waiting_time_chc2.append(env.now() - c)
            doc_time = sim.Uniform(10, 20).sample()
            emergency_time_chc2 += doc_time
            yield self.hold(doc_time)
            self.release(MO_chc2)
            z = random.randint(0, 100)
            if z < 11:
                emergency_refer_chc2 += 1
            else:
                emergency_count_chc2 += 1
                y = random.randint(0, 100)
                "Patients go to lab and/or radiography lab before getting admitted to emergency"
                if y < 52:  # 52% emergency patients require lab tests
                    a = env.now()  # for scheduling lab tests during OPD hours
                    c = a / 1440  # divides a by minutes in a day
                    d = c % 1  # takes out the decimal part from c
                    e = d * 1440  # finds out the minutes corrsponding to decimal part
                    if 0 < e <= 480:  # if it is in OPD region calls lab
                        Lab_chc2()
                    else:  # Schedules it to the next day
                        j = 1440 - e
                        Lab_chc2(at=a + j + 1)
                if 52 <= y < 69:  # 17.3% of the total patients require radiography
                    ys = random.randint(0, 100)
                    if ys < 50:  # 50% patients for X-Rays
                        c = env.now() / 1440
                        d = c % 1
                        e = d * 1440
                        if 0 < e <= 480:
                            Xray_chc2()
                        else:  # Schedules it to the next day
                            j = 1440 - e
                            Xray_chc2(at=env.now() + j + 1)
                    else:  # 50% patients for ecg
                        c = env.now() / 1440
                        d = c % 1
                        e = d * 1440
                        if 0 < e <= 480:
                            Ecg_chc2()
                        else:  # Schedules it to the next day
                            j = 1440 - e
                            Ecg_chc2(at=env.now() + j + 1)

                yield self.request(emer_nurse_chc2)
                nurse_time = sim.Uniform(20, 30).sample()
                emergency_nurse_time_chc2 += nurse_time
                yield self.hold(nurse_time)  # subtracting just to account nurse time
                self.release(emer_nurse_chc2)
                yield self.request(e_beds_chc2)
                stay = random.uniform(60, 300)
                emergency_bed_time_chc2 += stay
                yield self.hold(stay)
                self.release(e_beds_chc2)
                x = random.randint(0, 10)
                if x < 5:  # only 50% patients require inpatient care
                    emer_inpatients_chc2 += 1
                    self.enter(ipd_q_chc2)
                    h = env.now()
                    yield self.request(in_beds_chc2)
                    self.leave(ipd_q_chc2)
                    ipd_bed_wt_chc2.append(env.now() - h)
                    yield self.request(ipd_nurse_chc2)
                    t_nurse = sim.Uniform(10, 20).sample()
                    t_bed = sim.Triangular(120, 1440, 240).sample()
                    yield self.hold(t_nurse)
                    ipd_nurse_time_chc2 += t_nurse
                    self.release(ipd_nurse_chc2)
                    yield self.hold(t_bed - t_nurse)
                    self.release(in_beds_chc2)
                    ipd_bed_time_chc2 += t_bed
                    ipd_MO_time_chc2 += t_nurse


class Delivery_patient_generator_chc2(sim.Component):

    def process(self):
        global delivery_iat_chc2
        global warmup_time
        global delivery_count_chc2

        while True:
            if env.now() <= warmup_time:
                Delivery_ipd_chc2()
                t = sim.Exponential(delivery_iat_chc2).sample()
                yield self.hold(t)
            else:
                Delivery_ipd_chc2()
                t = sim.Exponential(delivery_iat_chc2).sample()
                yield self.hold(t)


class Delivery_ipd_chc2(sim.Component):

    def process(self):
        global in_beds_chc2
        global ipd_nurse_chc2
        global ipd_nurse_time_chc2
        global MO_chc2
        global warmup_time
        global childbirth_count_chc2
        global childbirth_referred_chc2
        global ipd_MO_time_chc2
        global ipd_bed_time_chc2
        global ipd_q_chc2
        global ipd_bed_wt_chc2

        if env.now() <= warmup_time:
            pass
        else:
            childbirth_count_chc2 += 1
            x = random.randint(0, 100)
            if x <= 4:
                childbirth_referred_chc2 += 1
                pass
            else:
                self.enter(ipd_q_chc2)
                h = env.now()
                yield self.request(in_beds_chc2)
                ipd_bed_wt_chc2.append(env.now() - h)
                self.leave(ipd_q_chc2)
                yield self.request(ipd_nurse_chc2)
                t1 = sim.Uniform(10, 20).sample()
                ipd_nurse_time_chc2 += t1
                self.hold(t1)
                self.release(ipd_nurse_chc2)
                yield self.request(MO_chc2)
                t2 = sim.Uniform(5, 10).sample()
                ipd_MO_time_chc2 += t2
                yield self.hold(t2)
                self.release(MO_chc2)
                t3 = sim.Uniform(240, 360).sample()
                yield self.hold(t3 - t2 - t1)
                ipd_bed_time_chc2 += (t3 - t2 - t1)
                self.release(in_beds_chc2)
                Delivery_chc2()


class Delivery_chc2(sim.Component):

    def process(self):
        global delivery_nurse_chc2
        global ipd_nurse_chc2
        global MO_chc2
        global delivery_bed_chc2
        global warmpup_time
        global e_beds_chc2
        global ipd_nurse_time_chc2
        global MO_del_time_chc2
        global in_beds_chc2
        global delivery_nurse_time_chc2
        global inpatient_del_count_chc2
        global delivery_count_chc2
        global emergency_bed_time_chc2
        global ipd_bed_time_chc2
        global emergency_nurse_time_chc2
        global referred_chc2
        global ipd_bed_wt_chc2

        if env.now() <= warmup_time:
            t_doc = sim.Uniform(30, 60).sample()
            t_bed = sim.Uniform(240, 360).sample()
            yield self.request(MO_chc2, fail_delay=20)
            if self.failed():  # if doctor is busy staff nurse takes care
                yield self.request(delivery_nurse_chc2, delivery_bed_chc2)
                yield self.hold(t_bed)
                self.release(delivery_nurse_chc2)
                self.release(delivery_bed_chc2)
            else:
                yield self.hold(t_doc)
                self.release(MO_chc2)
                yield self.request(delivery_nurse_chc2, delivery_bed_chc2)
                yield self.hold(t_bed)
                self.release(delivery_nurse_chc2)
                self.release(delivery_bed_chc2)
        else:
            delivery_count_chc2 += 1
            inpatient_del_count_chc2 += 1
            yield self.request(MO_chc2, fail_delay=20)
            t_doc = sim.Uniform(30, 60).sample()
            t_bed = sim.Uniform(240, 360).sample()  # delivery bed, nurse time
            delivery_nurse_time_chc2 += t_bed
            if self.failed():  # if doctor is busy staff nurse takes care
                yield self.request(delivery_nurse_chc2, delivery_bed_chc2)
                yield self.hold(t_bed)
                self.release(delivery_nurse_chc2)  # delivery nurse and delivery beds are released simultaneoulsy
                self.release(delivery_bed_chc2)
                # after delivery patient shifts to IPD and requests nurse and inpatient bed
                a1 = env.now()
                yield self.request(in_beds_chc2)
                ipd_bed_wt_chc2.append((env.now() - a1))
                yield self.request(ipd_nurse_chc2)
                t_n = sim.Uniform(20, 30).sample()  # inpatient nurse time in ipd after delivery
                t_bed2 = sim.Uniform(1440, 2880).sample()  # inpatient beds post delivery stay
                yield self.hold(t_n)
                self.release(ipd_nurse_chc2)
                ipd_nurse_time_chc2 += t_n
                yield self.hold(t_bed2 - t_n)
                self.release(in_beds_chc2)
                ipd_bed_time_chc2 += t_bed2

            else:
                MO_del_time_chc2 += t_doc  # MO
                yield self.hold(t_doc)
                self.release(MO_chc2)
                yield self.request(delivery_nurse_chc2, delivery_bed_chc2)
                yield self.hold(t_bed)
                self.release(delivery_nurse_chc2)  # delivery nurse and delivery beds are released simultaneoulsy
                self.release(delivery_bed_chc2)
                a1 = env.now()
                yield self.request(in_beds_chc2)
                ipd_bed_wt_chc2.append((env.now() - a1))
                yield self.request(ipd_nurse_chc2)
                t_n = sim.Uniform(20, 30).sample()  # staff nurser time in ipd after delivery
                t_bed1 = sim.Uniform(1440, 2880).sample()
                yield self.hold(t_n)
                self.release(ipd_nurse_chc2)
                ipd_nurse_time_chc2 += t_n
                yield self.hold(t_bed1 - t_n)
                self.release(in_beds_chc2)
                ipd_bed_time_chc2 += t_bed1


class Lab_chc2(sim.Component):

    def process(self):
        global lab_q_chc2
        global lab_technician_chc2
        global lab_time_chc2
        global lab_q_waiting_time_chc2
        global warmup_time
        global lab_count_chc2

        if env.now() <= warmup_time:
            self.enter(lab_q_chc2)
            yield self.request(lab_technician_chc2)
            self.leave(lab_q_chc2)
            yp = (np.random.lognormal(5.332, 0.262))
            y0 = yp / 60
            yield self.hold(y0)
            self.release(lab_technician_chc2)
        else:
            lab_count_chc2 += 1
            self.enter(lab_q_chc2)
            a0 = env.now()
            yield self.request(lab_technician_chc2)
            self.leave(lab_q_chc2)
            lab_q_waiting_time_chc2.append(env.now() - a0)
            yp = (np.random.lognormal(5.332, 0.262))
            y0 = yp / 60
            yield self.hold(y0)
            self.release(lab_technician_chc2)
            lab_time_chc2 += y0


class IPD_chc2(sim.Component):

    def process(self):
        global MO_ipd_chc2
        global ipd_nurse_chc2
        global in_beds_chc2
        global ipd_MO_time_chc2
        global ipd_nurse_time_chc2
        global warmup_time
        global ipd_bed_time_chc2
        global ipd_nurse_time_chc2
        global emergency_refer_chc2
        global ipd_q_chc2
        global ipd_MO_time_chc2
        global ipd_bed_wt_chc2

        if env.now() <= warmup_time:
            self.enter(ipd_q_chc2)
            yield self.request(in_beds_chc2)
            self.leave(ipd_q_chc2)
            yield self.request(ipd_nurse_chc2)
            yield self.request(MO_ipd_chc2)
            t_doc = sim.Uniform(10, 20).sample()
            t_nurse = sim.Uniform(20, 30).sample()
            t_bed = sim.Uniform(240, 4880).sample()
            yield self.hold(t_doc)
            self.release(MO_ipd_chc2)
            yield self.hold(t_nurse - t_doc)
            self.release(ipd_nurse_chc2)
            yield self.hold(t_bed - t_nurse - t_doc)
            self.release(in_beds_chc2)
        else:
            self.enter(ipd_q_chc2)
            h = env.now()
            yield self.request(in_beds_chc2)
            self.leave(ipd_q_chc2)
            ipd_bed_wt_chc2.append((env.now() - h))
            yield self.request(ipd_nurse_chc2)
            yield self.request(MO_ipd_chc2)

            t_doc = sim.Uniform(10, 20).sample()
            t_nurse = sim.Uniform(20, 30).sample()
            t_bed = sim.Uniform(240, 4880).sample()
            ipd_bed_time_chc2 += t_bed
            ipd_MO_time_chc2 += t_doc
            yield self.hold(t_doc)
            self.release(MO_ipd_chc2)
            yield self.hold(t_nurse - t_doc)
            ipd_nurse_time_chc2 += t_nurse
            self.release(ipd_nurse_chc2)
            # lab starts from here
            x = random.randint(0, 1000)  # for lab
            if x <= 346:  # 34.6% (2) patients for lab. Of them 12.5% go to radiography
                a = env.now()  # for scheduling lab tests during OPD hours
                c = a / 1440  # divides a by minutes in a day
                d = c % 1  # takes out the decimal part from c
                e = d * 1440  # finds out the minutes corrsponding to decimal part
                if 0 < e <= 480:  # if it is in OPD region calls lab
                    Lab_chc2()
                else:  # Schedules it to the next day
                    j = 1440 - e
                    Lab_chc2(at=a + j + 1)
            p = random.randint(0, 1000)  # for radiography
            if p < 125:  # 12.5% of the total patients require radiography
                y0 = random.randint(0, 10)
                if y0 < 5:  # 50 % patients for X-Ray
                    a = env.now()  # for scheduling lab tests during OPD hours
                    c = a / 1440  # divides a by minutes in a day
                    d = c % 1  # takes out the decimal part from c
                    e = d * 1440  # finds out the minutes corrsponding to decimal part
                    if 0 < e <= 480:  # if it is in OPD region calls lab
                        Xray_chc2()
                    else:  # Schedules it to the next day
                        j = 1440 - e
                        Xray_chc2(at=a + j + 1)
                else:
                    a = env.now()  # for scheduling lab tests during OPD hours
                    c = a / 1440  # divides a by minutes in a day
                    d = c % 1  # takes out the decimal part from c
                    e = d * 1440  # finds out the minutes corrsponding to decimal part
                    if 0 < e <= 480:  # if it is in OPD region calls lab
                        Ecg_chc2()
                    else:  # Schedules it to the next day
                        j = 1440 - e
                        Ecg_chc2(at=a + j + 1)
            yield self.hold(t_bed - t_nurse - t_doc)
            self.release(in_beds_chc2)


class ANC_chc2(sim.Component):
    global ANC_iat_chc2
    global day
    day = 0
    env = sim.Environment()
    No_of_shifts = 0  # tracks number of shifts completed during the simulation time
    No_of_days = 0
    ANC_List = {}
    anc_count = 0
    ANC_p_count = 0

    def process(self):

        global day

        while True:  # condition to run simulation for 8 hour shifts
            x = env.now() - 1440 * days
            if 0 <= x < 480:
                ANC_chc2.anc_count += 1  # counts overall patients throghout simulation
                ANC_chc2.ANC_p_count += 1  # counts patients in each replication
                id = ANC_chc2.anc_count
                age = 223
                day_of_registration = ANC_chc2.No_of_days
                visit = 1
                x0 = round(env.now())
                x1 = x0 + 14 * 7 * 24 * 60
                x2 = x0 + 20 * 7 * 24 * 60
                x3 = x0 + 24 * 7 * 24 * 60
                scheduled_visits = [[0], [0], [0], [0]]
                scheduled_visits[0] = x0
                scheduled_visits[1] = x1
                scheduled_visits[2] = x2
                scheduled_visits[3] = x3
                dic = {"ID": id, "Age": age, "Visit Number": visit, "Registration day": day_of_registration,
                       "Scheduled Visit": scheduled_visits}
                ANC_chc2.ANC_List[id] = dic
                ANC_Checkup_chc2()
                ANC_followup_chc2(at=ANC_chc2.ANC_List[id]["Scheduled Visit"][1])
                ANC_followup_chc2(at=ANC_chc2.ANC_List[id]["Scheduled Visit"][2])
                ANC_followup_chc2(at=ANC_chc2.ANC_List[id]["Scheduled Visit"][3])
                hold_time = sim.Exponential(ANC_iat_chc2).sample()
                yield self.hold(hold_time)
            else:
                yield self.hold(960)
                day = int(env.now() / 1440)  # holds simulation for 2 shifts


class ANC_Checkup_chc2(sim.Component):
    anc_checkup_count = 0

    def process(self):

        global warmup_time
        global delivery_nurse_chc2
        global delivery_nurse_time_chc2

        if env.now() <= warmup_time:
            yield self.request(delivery_nurse_chc2)
            temp = sim.Triangular(8, 20.6, 12.3).sample()
            yield self.hold(temp)  # time taken from a study on ANC visits in Tanzania
            Lab_chc2()
            Pharmacy_chc2()

        else:
            ANC_Checkup_chc2.anc_checkup_count += 1
            yield self.request(delivery_nurse_chc2)
            temp = sim.Triangular(8, 20.6, 12.3).sample()
            delivery_nurse_time_chc2 += temp
            yield self.hold(temp)  # time taken from a study on ANC visits in Tanzania
            # Gynecologist_OPD()
            Lab_chc2()
            Pharmacy_chc2()


class ANC_followup_chc2(sim.Component):
    followup_count = 0

    def process(self):

        global warmup_time
        global delivery_nurse_chc2
        global q_ANC_chc2
        global delivery_nurse_time_chc2

        if env.now() <= warmup_time:
            for key in ANC_chc2.ANC_List:  # for identifying and updating ANC visit number
                x0 = env.now()
                x1 = ANC_chc2.ANC_List[key]["Scheduled Visit"][1]
                x2 = ANC_chc2.ANC_List[key]["Scheduled Visit"][2]
                x3 = ANC_chc2.ANC_List[key]["Scheduled Visit"][3]
                if 0 <= (x1 - x0) < 481:
                    ANC_chc2.ANC_List[key]["Scheduled Visit"][1] = float("inf")
                    ANC_chc2.ANC_List[key]["Visit Number"] = 2
                elif 0 <= (x2 - x0) < 481:
                    ANC_chc2.ANC_List[key]["Scheduled Visit"][2] = float("inf")
                    ANC_chc2.ANC_List[key]["Visit Number"] = 3
                elif 0 <= (x3 - x0) < 481:
                    ANC_chc2.ANC_List[key]["Scheduled Visit"][3] = float("inf")
                    ANC_chc2.ANC_List[key]["Visit Number"] = 4

            yield self.request(delivery_nurse_chc2)
            temp = sim.Triangular(3.33, 13.16, 6.50).sample()
            yield self.hold(temp)
            self.release(delivery_nurse_chc2)
            Lab_chc2()
            Pharmacy_chc2()

        else:
            for key in ANC_chc2.ANC_List:  # for identifying and updating ANC visit number
                x0 = env.now()
                x1 = ANC_chc2.ANC_List[key]["Scheduled Visit"][1]
                x2 = ANC_chc2.ANC_List[key]["Scheduled Visit"][2]
                x3 = ANC_chc2.ANC_List[key]["Scheduled Visit"][3]
                if 0 <= (x1 - x0) < 481:
                    ANC_chc2.ANC_List[key]["Scheduled Visit"][1] = float("inf")
                    ANC_chc2.ANC_List[key]["Visit Number"] = 2
                elif 0 <= (x2 - x0) < 481:
                    ANC_chc2.ANC_List[key]["Scheduled Visit"][2] = float("inf")
                    ANC_chc2.ANC_List[key]["Visit Number"] = 3
                elif 0 <= (x3 - x0) < 481:
                    ANC_chc2.ANC_List[key]["Scheduled Visit"][3] = float("inf")
                    ANC_chc2.ANC_List[key]["Visit Number"] = 4

            yield self.request(delivery_nurse_chc2)
            temp = sim.Triangular(3.33, 13.16, 6.50).sample()
            yield self.hold(temp)
            self.release(delivery_nurse_chc2)
            rand = random.randint(0, 10)
            if rand < 3:  # only 30 % ANC checks require consultation
                # Gynecologist_OPD()
                pass
            Lab_chc2()
            Pharmacy_chc2()


class Surgery_patient_generator_chc2(sim.Component):

    def process(self):

        global warmup_time
        global surgery_count_chc2
        global surgery_iat_chc2

        while True:
            if env.now() <= warmup_time:
                OT_chc2()
                yield self.hold(sim.Exponential(surgery_iat_chc2).sample())
            else:
                surgery_count_chc2 += 1
                OT_chc2()
                yield self.hold(sim.Exponential(surgery_iat_chc2).sample())


class OT_chc2(sim.Component):

    def process(self):

        global warmup_time
        global doc_surgeon_chc2
        global doc_ans_chc2
        global sur_time_chc2
        global ans_time_chc2
        global ot_nurse_chc2
        global ot_nurse_time_chc2
        global ipd_surgery_count_chc2

        if env.now() <= warmup_time:
            yield self.request(doc_surgeon_chc2, doc_ans_chc2, ot_nurse_chc2)
            surgery_time = sim.Uniform(20, 60).sample()
            yield self.hold(surgery_time)
            self.release(doc_ans_chc2, doc_surgeon_chc2, ot_nurse_chc2)
            IPD_chc2()
        else:
            yield self.request(doc_surgeon_chc2, doc_ans_chc2, ot_nurse_chc2)
            surgery_time = sim.Uniform(20, 60).sample()
            sur_time_chc2 += surgery_time
            ans_time_chc2 += surgery_time
            ot_nurse_time_chc2 += surgery_time
            yield self.hold(surgery_time)
            self.release(doc_ans_chc2, doc_surgeon_chc2, ot_nurse_chc2)
            IPD_chc2()
            ipd_surgery_count_chc2 += 1


class Xray_chc2(sim.Component):

    def process(self):
        global xray_count_chc2
        global xray_tech_chc2
        global radio_time_chc2
        global xray_q_chc2
        global xray_q_waiting_time_chc2
        global xray_q_length_chc2
        global xray_time_chc2
        global warmup_time

        if env.now() <= warmup_time:
            self.enter(xray_q_chc2)
            yield self.request(xray_tech_chc2)
            self.leave(xray_q_chc2)
            y1 = sim.Triangular(2, 20, 9).sample()
            yield self.hold(y1)
            self.release(xray_tech_chc2)
        else:
            xray_count_chc2 += 1
            self.enter(xray_q_chc2)
            g0 = env.now()
            yield self.request(xray_tech_chc2)
            self.leave(xray_q_chc2)
            xray_q_waiting_time_chc2.append(env.now() - g0)
            y1 = sim.Triangular(2, 20, 9).sample()
            xray_time_chc2 += y1
            yield self.hold(y1)
            self.release(xray_tech_chc2)


class Ecg_chc2(sim.Component):

    def process(self):
        global xray_tech_chc2
        global radio_time_chc2
        global ecg_q_chc2
        global ecg_q_waiting_time_chc2
        global ecg_q_length_chc2
        global xray_time_chc2
        global ecg_count_chc2
        global warmuo_time

        if env.now() <= warmup_time:
            self.enter(ecg_q_chc2)
            yield self.request(xray_tech_chc2)
            self.leave(ecg_q_chc2)
            yp = sim.Uniform(7, 13).sample()
            yield self.hold(yp)
            self.release(xray_tech_chc2)
        else:
            ecg_count_chc2 += 1
            self.enter(ecg_q_chc2)
            b0 = env.now()
            yield self.request(xray_tech_chc2)
            self.leave(ecg_q_chc2)
            ecg_q_waiting_time_chc2.append(env.now() - b0)
            yp = sim.Uniform(7, 13).sample()
            xray_time_chc2 += yp
            yield self.hold(yp)
            self.release(xray_tech_chc2)


"This class is for testing the regular OPD patients "


class opd_covid_chc2(sim.Component):

    def process(self):
        global covid_q_chc2
        global warmup_time
        global ipd_nurse_chc2
        global ipd_nurse_time_chc2
        global lab_technician_chc2
        global lab_time_chc2
        global ipd_nurse_time_chc2
        if env.now() <= warmup_time:
            self.enter(covid_q_chc2)
            yield self.request(ipd_nurse_chc2)
            self.leave(covid_q_chc2)
            h1 = sim.Uniform(5, 10).sample()
            yield self.hold(h1)
            self.release(ipd_nurse_chc2)
            yield self.request(lab_technician_chc2)
            t = sim.Uniform(1, 2).sample()
            yield self.hold(t)
            self.release(lab_technician_chc2)
            yield self.hold(sim.Uniform(15, 30).sample())  # patient waits for the result
        else:
            x = random.randint(0, 100)
            self.enter(covid_q_chc2)
            yield self.request(ipd_nurse_chc2)
            self.leave(covid_q_chc2)
            h1 = sim.Uniform(5, 10).sample()
            yield self.hold(h1)
            self.release(ipd_nurse_chc2)
            ipd_nurse_time_chc2 += h1
            yield self.request(lab_technician_chc2)
            t = sim.Uniform(1, 2).sample()
            yield self.hold(t)

            self.release(lab_technician_chc2)
            lab_time_chc2 += t
            yield self.hold(sim.Uniform(15, 30).sample())  # patient waits for the result
            Pharmacy_chc2()


class CovidGenerator_chc2(sim.Component):

    def process(self):
        global d_chc2
        global warmup_time
        global ia_covid_chc
        global chc2_covid_iat

        global d_cc_chc2
        global e_cc_chc2
        global f_cc_chc2
        global d_dh_chc2
        global e_dh_chc2
        global f_dh_chc2
        global array_d_cc_chc2
        global array_e_cc_chc2
        global array_f_cc_chc2
        global array_d_dh_chc2
        global array_e_dh_chc2
        global array_f_dh_chc2
        global t_m_chc2
        global t_c_chc2
        global t_b_chc2
        global t_a_chc2
        global t_s_chc2
        global t_d_chc2
        global t_e_chc2
        global t_f_chc2
        global a_cc_chc2
        global b_cc_chc2
        global c_cc_chc2
        global a_dh_chc2
        global b_dh_chc2
        global c_dh_chc2
        global array_a_cc_chc2
        global array_b_cc_chc2
        global array_c_cc_chc2
        global array_a_dh_chc2
        global array_b_dh_chc2
        global array_c_dh_chc2
        global array_t_s_chc2
        global array_t_m_chc2
        global array_t_d_chc2
        global array_t_e_chc2
        global array_t_f_chc2
        global array_t_a_chc2
        global array_t_b_chc2
        global array_t_c_chc2
        global array_a_cc_chc2
        global array_b_cc_chc2
        global array_c_cc_chc2
        global array_a_dh_chc2
        global array_b_dh_chc2
        global array_c_dh_chc2
        global array_t_s_chc2
        global j

        while True:
            if env.now() < warmup_time:
                if 0 <= (env.now() - d_chc2 * 1440) < 480:
                    covid_chc2()
                    yield self.hold(1440 / 3)
                    d_chc2 = int(env.now() / 1440)
                else:
                    yield self.hold(960)
                    d_chc2 = int(env.now() / 1440)
            else:
                a = chc_covid_iat[j]
                if 0 <= (env.now() - d_chc2 * 1440) < 480:
                    covid_chc2()

                    yield self.hold(sim.Exponential(a).sample())
                    d_chc2 = int(env.now() / 1440)
                else:
                    # the proportion referred are updated each day and then set to zero for the next day
                    array_d_cc_chc2.append(d_cc_chc2)  # daily proportion of patients referred
                    array_e_cc_chc2.append(e_cc_chc2)
                    array_f_cc_chc2.append(f_cc_chc2)
                    array_d_dh_chc2.append(d_dh_chc2)
                    array_e_dh_chc2.append(e_dh_chc2)
                    array_f_dh_chc2.append(f_dh_chc2)
                    array_a_cc_chc2.append(a_cc_chc2)  # daily proportion of patients referred
                    array_b_cc_chc2.append(b_cc_chc2)
                    array_c_cc_chc2.append(c_cc_chc2)
                    array_a_dh_chc2.append(a_dh_chc2)
                    array_b_dh_chc2.append(b_dh_chc2)
                    array_c_dh_chc2.append(c_dh_chc2)
                    array_t_a_chc2.append(t_a_chc2)

                    array_t_b_chc2.append(t_b_chc2)
                    array_t_c_chc2.append(t_c_chc2)
                    array_t_d_chc2.append(t_d_chc2)
                    array_t_e_chc2.append(t_e_chc2)
                    array_t_f_chc2.append(t_f_chc2)
                    array_t_m_chc2.append(t_m_chc2)
                    array_t_s_chc2.append(t_s_chc2)

                    t_a_chc2 = 0
                    t_b_chc2 = 0
                    t_c_chc2 = 0
                    t_d_chc2 = 0
                    t_e_chc2 = 0
                    t_f_chc2 = 0
                    d_cc_chc2 = 0
                    e_cc_chc2 = 0
                    f_cc_chc2 = 0
                    d_dh_chc2 = 0
                    e_dh_chc2 = 0
                    f_dh_chc2 = 0
                    a_cc_chc2 = 0
                    b_cc_chc2 = 0
                    c_cc_chc2 = 0
                    a_dh_chc2 = 0
                    b_dh_chc2 = 0
                    c_dh_chc2 = 0
                    t_s_chc2 = 0
                    t_m_chc2 = 0
                    yield self.hold(960)
                    d_chc2 = int(env.now() / 1440)


class covid_chc2(sim.Component):

    def process(self):

        global home_refer_chc2
        global chc_refer_chc2
        global dh_refer_chc2
        global isolation_ward_refer_from_CHC_chc2
        global covid_patient_time_chc2
        global covid_count_chc2
        global warmup_time
        global ipd_nurse_chc2
        global ipd_nurse_time_chc2
        global doc_OPD_chc2
        global chc2_to_cc_dist
        global chc2_to_dh_dist
        global chc2_to_cc_severe_case
        global chc2_2_cc
        global chc2_2_dh
        global chc2_severe_covid
        global chc2_moderate_covid

        global d_cc_chc2
        global e_cc_chc2
        global f_cc_chc2
        global d_dh_chc2
        global e_dh_chc2
        global f_dh_chc2
        global t_s_chc2
        global t_d_chc2
        global t_e_chc2
        global t_f_chc2

        if env.now() < warmup_time:
            covid_nurse()
            covid_lab()
            x = random.randint(0, 1000)
            if x <= 940:
                yield self.request(doc_OPD_chc2)
                yield self.hold(sim.Uniform(3, 6).sample())
                self.release(doc_OPD_chc2)
                pass
            elif 940 < x <= 980:
                # CovidCare()
                pass
            else:
                yield self.request(doc_OPD_chc2)
                yield self.hold(sim.Uniform(3, 6).sample())
                self.release(doc_OPD_chc2)
                # SevereCase()
        else:
            covid_count_chc2 += 1
            covid_nurse_chc2()
            covid_lab_chc2()
            x = random.randint(0, 1000)
            if x <= 940:  # mild cases
                home_refer_chc2 += 1
                yield self.request(doc_OPD_chc2)
                f = sim.Uniform(3, 6).sample()
                yield self.hold(f)
                self.release(doc_OPD_chc2)
                covid_patient_time_chc2 += f
                a1 = random.randint(0, 10)
                if a1 >= 9:  # 10 % patients referred to cc
                    isolation_ward_refer_from_CHC_chc2 += 1
                    # chc2_to_cc_dist.append(chc2_2_cc)
                    cc_isolation()  # those patients who can not home quarantine themselves
            elif 940 < x <= 980:  # moderate cases
                CovidCare_chc2()
                chc2_moderate_covid += 1
            else:
                t_s_chc2 += 1  # total per day severe patients
                chc2_severe_covid += 1
                yield self.request(doc_OPD_chc2)
                f = sim.Uniform(3, 6).sample()
                yield self.hold(f)
                self.release(doc_OPD_chc2)
                covid_patient_time_chc2 += f
                """Bed availability is checked at DH, if no available the send to CC"""
                p = random.randint(0, 100)
                if p <= 50:  # Type F. 64% patients require ICU oxygen beds first
                    t_f_chc2 += 1
                    if ICU_oxygen.available_quantity() < 1:  # checks if there is a vacant bed in DH
                        # if no, then patient is sent to CC
                        chc2_to_cc_severe_case += 1
                        chc2_to_cc_dist.append(chc1_2_cc)
                        cc_Type_F()
                        f_cc_chc2 += 1
                    else:
                        DH_SevereTypeF()
                        f_dh_chc2 += 1
                elif 50 <= p < 75:
                    t_e_chc2 += 1
                    if ICU_ventilator.available_quantity() < 1:  # checks if there is a vacant bed in DH
                        chc2_severe_covid += 1
                        cc_ICU_ward_TypeE()
                        e_cc_chc2 += 1
                    else:
                        DH_SevereTypeE()
                        e_dh_chc2 += 1
                else:
                    t_d_chc2 += 1
                    if ICU_ventilator.available_quantity() < 1:
                        d_cc_chc2 += 1
                        cc_ventilator_TypeD()
                    else:
                        chc2_to_dh_dist.append(chc2_2_dh)
                        d_dh_chc2 += 1
                        DH_SevereTypeD()


class covid_nurse_chc2(sim.Component):

    def process(self):

        global warmup_time
        global ipd_nurse_chc2
        global ipd_nurse_time_chc2
        global lab_covidcount_chc2

        if env.now() <= warmup_time:
            yield self.request(ipd_nurse_chc2)
            yield self.hold(sim.Uniform(2, 3).sample())
            self.release(ipd_nurse_chc2)
        else:
            lab_covidcount_chc2 += 1
            yield self.request(ipd_nurse_chc2)
            t = sim.Uniform(2, 3).sample()
            yield self.hold(t)
            ipd_nurse_time_chc2 += t
            self.release(ipd_nurse_chc2)


class covid_lab_chc2(sim.Component):

    def process(self):

        global lab_technician_chc2
        global lab_time_chc2
        global lab_q_waiting_time_chc2
        global warmup_time
        global lab_covidcount_chc2

        if env.now() <= warmup_time:
            yield self.request(lab_technician_chc2)
            yield self.hold(sim.Uniform(1, 2).sample())
            self.release(lab_technician_chc2)
            yield self.hold(sim.Uniform(15, 30).sample())  # patient waits for reports
            x = random.randint(0, 100)
            if x < 67:  # confirmed positive
                # covid_doc_chc2()
                pass
            else:  # symptomatic negative, retesting
                retesting_chc2()

        else:
            lab_covidcount_chc2 += 1
            yield self.request(lab_technician_chc2)
            t = sim.Uniform(1, 2).sample()  # sample collection
            yield self.hold(t)
            lab_time_chc2 += t
            self.release(lab_technician_chc2)
            yield self.hold(sim.Uniform(15, 30).sample())
            x = random.randint(0, 100)
            if x < 67:  # confirmed positive
                pass
            else:  # symptomatic negative, retesting
                retesting_chc2()


class retesting_chc2(sim.Component):

    def process(self):

        global retesting_count_chc2
        global warmup_time

        if env.now() <= warmup_time:
            yield self.hold(1440)
            covid_doc_chc3()
        else:
            retesting_count_chc2 += 1
            yield self.hold(1440)
            covid_doc_chc3()


class covid_doc_chc2(sim.Component):  # class for triaging covid patients

    def process(self):

        global doc_OPD_chc2
        global warmup_time
        global covid_q_chc2
        global covid_patient_time_chc2

        if env.now() <= warmup_time:
            self.enter(covid_q_chc2)
            yield self.request(doc_OPD_chc2)
            self.leave(covid_q_chc2)
            yield self.hold(sim.Uniform(5, 10).sample())
            self.release(doc_OPD_chc2)
        else:
            in_time = env.now()
            self.enter(covid_q_chc2)
            yield self.request(doc_OPD_chc2)
            self.leave(covid_q_chc2)
            t = sim.Uniform(5, 10).sample()
            yield self.hold(t)
            self.release(doc_OPD_chc2)
            covid_patient_time_chc2 += env.now() - in_time


class covid_doc_ipd_chc2(sim.Component):  # class for triaging covid patients

    def process(self):
        global MO_covid_time_chc2
        global MO_ipd_chc2
        global warmup_time

        if env.now() <= warmup_time:
            yield self.request(MO_ipd_chc2)
            yield self.hold(sim.Uniform(3, 6).sample())
            self.release(MO_ipd_chc2)
        else:
            in_time = env.now()
            yield self.request(MO_ipd_chc2)
            t = sim.Uniform(3 / 2, 6 / 2).sample()
            yield self.hold(t)
            MO_covid_time_chc2 += t
            self.release(MO_ipd_chc2)


class CovidCare_chc2(sim.Component):

    def process(self):
        global covid_bed_chc2
        global ipd_nurse_chc2
        global ipd_nurse_time_chc2
        global MO_chc2
        global MO_covid_time_chc2
        global warmup_time
        global moderate_refered_chc2
        global chc2_covid_bed_time
        global chc2_to_cc_dist
        global chc2_to_dh_dist
        global General_bed_DH
        global chc2_to_cc_moderate_case
        global chc2_2_dh
        global c_bed_wait_chc2
        global chc2_2_cc
        global covid_doc_chc2

        global t_c_chc2
        global t_b_chc2
        global t_a_chc2
        global a_cc_chc2
        global b_cc_chc2
        global c_cc_chc2
        global a_dh_chc2
        global b_dh_chc2
        global c_dh_chc2
        global t_m_chc2

        if env.now() <= warmup_time:
            yield self.request(covid_bed_chc2)
            a7 = sim.Uniform(1440 * 4, 1440 * 5).sample()
            a71 = a7 / (24 * 60)
            a711 = round(a71)
            for a8 in range(0, a711):
                covid_doc_chc2(at=env.now() + a8 * 24 * 60)
                covid_nurse_chc2(at=env.now() + a8 * 24 * 60)
            yield self.hold(a7)
            self.release(covid_bed_chc2)
        else:
            t_m_chc2 += 1  # total moderate patients
            a = random.randint(0, 100)
            if a < 90:  # 90% cases are said to remain moderate through out
                k = env.now()

                yield self.request(covid_bed_chc2, fail_delay=300)  # checks for bed availability at CHC
                t_a_chc2 += 1  # total a type patients chc1
                if self.failed():
                    if General_bed_DH.available_quantity() < 1:
                        chc2_to_cc_moderate_case += 1
                        chc2_to_cc_dist.append(chc2_2_cc)
                        cc_general_ward_TypeA()
                        a_cc_chc2 += 1
                    else:
                        a_dh_chc2 += 1
                        moderate_refered_chc2 += 1
                        chc2_to_dh_dist.append(chc2_2_dh)
                        ModerateTypeA()
                else:
                    k1 = env.now()
                    c_bed_wait_chc2.append(k1 - k)
                    a7 = sim.Uniform(1440 * 4, 1440 * 5).sample()
                    chc2_covid_bed_time += a7
                    a71 = a7 / (12 * 60)
                    a711 = round(a71)
                    for a8 in range(0, a711):
                        covid_doc_ipd_chc2(at=env.now() + a8 * 12 * 60)
                        covid_nurse(at=env.now() + a8 * 12 * 60)
                    yield self.hold(a7)
                    self.release(covid_bed_chc2)
            elif 90 <= a < 98:  # B type patients
                t_b_chc2 += 1  # total b type patients per day
                if General_bed_DH.available_quantity() < 1:
                    chc2_to_cc_moderate_case += 1
                    chc2_to_cc_dist.append(chc2_2_cc)
                    cc_general_ward_TypeB()
                    b_cc_chc2 += 1
                else:
                    b_dh_chc2 += 1
                    moderate_refered_chc2 += 1
                    chc2_to_dh_dist.append(chc2_2_dh)
                    ModerateTypeB()

            else:  # c type patients
                t_c_chc2 += 1
                if General_bed_DH.available_quantity() < 1:
                    chc2_to_cc_moderate_case += 1
                    chc2_to_cc_dist.append(chc2_2_cc)
                    cc_general_ward_TypeC()
                    c_cc_chc2 += 1
                else:
                    moderate_refered_chc2 += 1
                    chc2_to_dh_dist.append(chc2_2_dh)
                    ModerateTypeC()
                    c_dh_chc2 += 1


# CHC3


class PatientGenerator_chc3(sim.Component):
    total_OPD_patients_chc2 = 0

    def process(self):

        global env
        global warmup_time
        global opd_iat_chc3
        global days
        global admin_work_chc3

        while env.now() <= warmup_time:
            x = (env.now() - days * 1440)  # x is calculated for OPD timing
            if 0 <= x <= 360:
                Registration_chc3()
                o = sim.Exponential(opd_iat_chc3).sample()
                yield self.hold(o)
                days = int(env.now() / 1440)
            else:
                yield self.hold(1080)
                days = int(env.now() / 1440)

        while env.now() > warmup_time:
            if 0 <= (env.now() - days * 1440) < 360:
                PatientGenerator_chc3.total_OPD_patients_chc2 += 1
                Registration_chc3()
                o = sim.Exponential(opd_iat_chc3).sample()
                yield self.hold(o)
                days = int(env.now() / 1440)
            else:
                p = int(sim.Normal(60, 10).bounded_sample(40, 80))
                admin_work_chc3 += 0
                yield self.hold(1080)
                days = int(env.now() / 1440)


class Registration_chc3(sim.Component):
    Patient_log_chc3 = {}

    def setup(self):

        self.dic = {}  # local dictionary for temporarily   storing generated patients
        # with attributes
        self.time_of_visit = [[0], [0], [0]]  # initializing for assigning time of visits
        self.regis_time = round(env.now())  # registration time is the current simulation time
        self.id = PatientGenerator_chc3.total_OPD_patients_chc2  # patient count is patient id
        self.age_random = random.randint(0, 1000)  # assigning age to population based on census 2011 gurgaon
        if self.age_random <= 578:
            self.age = random.randint(0, 30)
        else:
            self.age = random.randint(31, 100)
        self.sex = random.choice(["male", "female"])  # Equal probability of male and female patient
        # require lab tests
        self.lab_required = random.randint(0, 100)  # Considering nearly half of all the patients
        self.radiography_required = random.choice(["True", "False"])
        y = random.randint(0, 999)
        self.consultation = random.choice([y])  # for medicine, gynea, pead, denta
        self.visits_assigned = random.randint(1, 10)  # assigning number of visits visits
        self.dic = {"ID": self.id, "Age": self.age, "Sex": self.sex, "Lab": self.lab_required,
                    "Registration_Time": self.regis_time, "No_of_visits": self.visits_assigned,
                    "Time_of_visit": self.time_of_visit, "Radiography": self.radiography_required,
                    "Consultation": self.consultation}
        Registration_chc3.Patient_log_chc3[PatientGenerator_chc3.total_OPD_patients_chc2] = self.dic
        self.process()

    def process(self):

        global registration_time_chc3
        global registration_q_chc3
        global registration_clerk_chc3
        global r_time_lb_chc3
        global r_time_ub_chc3
        global registration_q_waiting_time_chc3
        global registration_q_length_chc3
        global warmup_time
        global total_opds_chc3
        global medicine_count_chc3

        if env.now() <= warmup_time:
            self.enter(registration_q_chc3)
            yield self.request((registration_clerk_chc3, 1))
            self.leave(registration_q_chc3)
            r_time = sim.Uniform(r_time_lb_chc3, r_time_ub_chc3).sample()
            yield self.hold(r_time)
            OPD_chc3()
        else:
            total_opds_chc3 += 1
            entry_time = env.now()
            self.enter(registration_q_chc3)
            yield self.request(registration_clerk_chc3)
            self.leave(registration_q_chc3)
            exit_time = env.now()
            q_time = exit_time - entry_time
            registration_q_waiting_time_chc3.append(q_time)
            r_time = sim.Uniform(r_time_lb_chc3, r_time_ub_chc3).sample()
            yield self.hold(r_time)
            self.release(registration_clerk_chc3)
            registration_time_chc3 += r_time
            x = Registration_chc3.Patient_log_chc3[PatientGenerator_chc3.total_OPD_patients_chc2]["Consultation"]
            if x < 921:  # 92.1% medicine OPDs
                OPD_chc3()

            else:  # remaining dental OPD
                Dental_OPD_chc3()


class OPD_chc3(sim.Component):

    def process(self):

        global c_chc3
        global medicine_q_chc3
        global doc_OPD_chc3
        global opd_ser_time_mean_chc3
        global opd_ser_time_sd_chc3
        global medicine_count_chc3
        global medicine_cons_time_chc3
        global opd_q_waiting_time_chc3
        global ncd_count_chc3
        global ncd_nurse_chc3
        global ncd_time_chc3
        global warmup_time
        global q_len_chc3
        global days

        if env.now() <= warmup_time:
            g = random.randint(0, 100)
            if g < 20:
                opd_covid_chc3()
            else:
                self.enter(medicine_q_chc3)
                yield self.request(doc_OPD_chc3)
                self.leave(medicine_q_chc3)
                o = sim.Normal(opd_ser_time_mean_chc3, opd_ser_time_sd_chc3).bounded_sample(0.5)
                yield self.hold(o)
                self.release(doc_OPD_chc3)
        if env.now() > warmup_time:
            g = random.randint(0, 100)
            if g < 20:
                opd_covid_chc3()
            else:
                if 0 <= (env.now() - days * 1440) < 360:
                    medicine_count_chc3 += 1
                    if Registration_chc3.Patient_log_chc3[PatientGenerator_chc3.total_OPD_patients_chc2]["Age"] > 30:
                        ncd_count_chc3 += 1
                        yield self.request(ncd_nurse_chc3)
                        ncd_service = sim.Uniform(2, 5).sample()
                        yield self.hold(ncd_service)
                        ncd_time_chc3 += ncd_service
                    # doctor opd starts from here
                    entry_time = env.now()
                    self.enter(medicine_q_chc3)
                    yield self.request(doc_OPD_chc3)
                    self.leave(medicine_q_chc3)
                    exit_time = env.now()
                    opd_q_waiting_time_chc3.append(exit_time - entry_time)  # stores waiting time in the queue
                    o = sim.Normal(opd_ser_time_mean_chc3, opd_ser_time_sd_chc3).bounded_sample(0.5)
                    yield self.hold(o)
                    medicine_cons_time_chc3 += o
                    self.release(doc_OPD_chc3)
                    # lab starts from here
                    x = random.randint(0, 1000)  # for radiography
                    t = random.randint(0, 1000)
                    if t <= 133:  # 21.5% (53) opd patients
                        Lab_chc3()

                    if x < 30:  # 3% (6.24) of the total patients require radiography
                        Xray_chc3()
                    Pharmacy_chc3()
                else:
                    q_len_chc3.append(len(medicine_q_chc3))


class Pharmacy_chc3(sim.Component):

    def process(self):

        global pharmacist_chc3
        global pharmacy_time_chc3
        global pharmacy_q_chc3
        global pharmacy_q_waiting_time_chc3
        global warmup_time
        global pharmacy_count_chc3

        if env.now() < warmup_time:
            self.enter(pharmacy_q_chc3)
            yield self.request(pharmacist_chc3)
            self.leave(pharmacy_q_chc3)
            service_time = sim.Uniform(1, 2.5).sample()
            yield self.hold(service_time)
            self.release(pharmacist_chc3)
        else:
            pharmacy_count_chc3 += 1
            e1 = env.now()
            self.enter(pharmacy_q_chc3)
            yield self.request((pharmacist_chc3, 1))
            self.leave(pharmacy_q_chc3)
            pharmacy_q_waiting_time_chc3.append(env.now() - e1)
            service_time = sim.Uniform(1, 2.5).sample()
            yield self.hold(service_time)
            self.release((pharmacist_chc3, 1))
            pharmacy_time_chc3 += service_time


class Gynecologist_OPD_chc3(sim.Component):

    def process(self):

        global warmup_time
        global doc_Gyn_chc3
        global gyn_q_chc3
        global gyn_count_chc3
        global gyn_q_waiting_time_chc3
        global gyn_time_chc3
        global xray_tech_chc3
        global radio_time_chc3
        global xray_q_chc3
        global xray_q_waiting_time_chc3
        global radio_count_chc3

        if env.now() <= warmup_time:
            self.enter(gyn_q_chc3)
            yield self.request(doc_Gyn_chc3)
            self.leave(gyn_q_chc3)
            yield self.hold(sim.Uniform(5, 10).sample())
        else:
            gyn_count_chc3 += 1
            e = env.now()
            self.enter(gyn_q_chc3)
            yield self.request(doc_Gyn_chc3)
            self.leave(gyn_q_chc3)
            gyn_q_waiting_time_chc3.append(env.now() - e)
            s = sim.Uniform(5, 10).sample()
            gyn_time_chc3 += s
            yield self.hold(s)
            self.release(doc_Gyn_chc3)
            x = random.randint(0, 10)
            if x < 5:  # 50 % go to lab
                Lab_chc3()
                if x < 2:  # 20% of lab patients require radiographer
                    Lab_chc3()
            if 5 < x < 9:  # 30 % of the total patients require radiography
                Xray_chc3()
            Pharmacy_chc3()


class Pediatrics_OPD_chc3(sim.Component):

    def process(self):

        global warmup_time
        global doc_Ped_chc3
        global ped_q_chc3
        global ped_count_chc3
        global ped_q_waiting_time_chc3
        global ped_time_chc3

        if env.now() <= warmup_time:
            self.enter(ped_q_chc3)
            yield self.request(doc_Ped_chc3)
            self.leave(ped_q_chc3)
            yield self.hold(sim.Triangular(2, 15, 6.36).sample())
            self.release(doc_Ped_chc3)
        else:
            ped_count_chc3 += 1
            e = env.now()
            self.enter(ped_q_chc3)
            yield self.request(doc_Ped_chc3)
            self.leave(ped_q_chc3)
            ped_q_waiting_time_chc3.append(env.now() - e)
            s = sim.Triangular(2, 15, 6.36).sample()
            ped_time_chc3 += s
            yield self.hold(s)
            self.release(doc_Ped_chc3)
            x = random.randint(0, 100)
            if x < 12:  # 12 % go to lab
                Lab_chc3()
            if 32 < x < 37:  # 4% of the total pediatrics patients require Xray
                Xray_chc3()
            Pharmacy_chc3()


class Dental_OPD_chc3(sim.Component):

    def process(self):

        global warmup_time
        global doc_Dentist_chc3
        global den_q_chc3
        global den_count_chc3
        global den_consul_chc3
        global den_proced_chc3
        global den_q_waiting_time_chc3
        global den_time_chc3
        global pharmacist_chc3
        global pharmacy_time_chc3
        global pharmacy_q_chc3
        global pharmacy_q_waiting_time_chc3
        global env

        if env.now() <= warmup_time:
            x = random.randint(0, 100)
            if x <= 63:  # 70 % cases are consultations and remaining are procedures
                e = env.now()
                self.enter(den_q_chc3)
                yield self.request(doc_Dentist_chc3)
                self.leave(den_q_chc3)
                p = round((env.now() - e), 2)
                s = sim.Uniform(2, 10).sample()
                yield self.hold(s)
                self.release(doc_Dentist_chc3)
            else:
                self.enter(den_q_chc3)
                e1 = env.now()
                yield self.request(doc_Dentist_chc3)
                self.leave(den_q_chc3)
                p1 = round((env.now() - e1), 2)
                s = sim.Uniform(10, 30).sample()
                yield self.hold(s)
                self.release(doc_Dentist_chc3)
                self.enter(pharmacy_q_chc3)
                Pharmacy_chc3()
        else:
            den_count_chc3 += 1
            x = random.randint(0, 100)
            if x <= 62:  # 63 % cases are consultations and remaining are procedures
                e = env.now()
                den_consul_chc3 += 1
                self.enter(den_q_chc3)
                yield self.request(doc_Dentist_chc3)
                self.leave(den_q_chc3)
                p = round((env.now() - e), 2)
                den_q_waiting_time_chc3.append(p)
                s = sim.Uniform(2, 10).sample()
                den_time_chc3 += s
                yield self.hold(s)
                self.release(doc_Dentist_chc3)
            else:
                den_proced_chc3 += 1
                self.enter(den_q_chc3)
                e1 = env.now()
                yield self.request(doc_Dentist_chc3)
                self.leave(den_q_chc3)
                p1 = round((env.now() - e1), 2)
                den_q_waiting_time_chc3.append(p1)
                s = sim.Uniform(10, 30).sample()
                den_time_chc3 += s
                yield self.hold(s)
                self.release(doc_Dentist_chc3)
                Pharmacy_chc3()


class Emergency_patient_chc3(sim.Component):

    def process(self):
        global emergency_iat_chc3

        global warmup_time

        while True:
            if env.now() <= warmup_time:
                Emergency_chc3()
                yield self.hold(sim.Exponential(emergency_iat_chc3).sample())
            else:
                Emergency_chc3()
                yield self.hold(sim.Exponential(emergency_iat_chc3).sample())


class Emergency_chc3(sim.Component):

    def process(self):

        global emergency_count_chc3
        global warmup_time
        global MO_chc3
        global emergency_time_chc3
        global e_beds_chc3
        global ipd_nurse_chc3
        global emergency_nurse_time_chc3
        global emergency_bed_time_chc3
        global in_beds_chc3
        global ipd_bed_time_chc3
        global ipd_nurse_time_chc3
        global emer_inpatients_chc3
        global emer_nurse_chc3
        global lab_q_chc3
        global lab_technician_chc3
        global lab_time_chc3
        global lab_q_waiting_time_chc3
        global xray_tech_chc3
        global radio_time_chc3
        global xray_q_chc3
        global xray_q_waiting_time_chc3
        global emergency_refer_chc3
        global ipd_q_chc3
        global ipd_MO_time_chc3
        global ipd_bed_wt_chc3

        global emr_q_chc3
        global emr_q_waiting_time_chc3

        if env.now() < warmup_time:
            z = random.randint(0, 100)
            if z < 11:
                pass
            else:
                y = random.randint(0, 1000)
                "Patients go to lab and/or radiography lab before getting admitted to emergency"
                if y < 494:  # 50% emergency patients require lab tests
                    a = env.now()  # for scheduling lab tests during OPD hours
                    c = a / 1440  # divides a by minutes in a day
                    d = c % 1  # takes out the decimal part from c
                    e = d * 1440  # finds out the minutes corrsponding to decimal part
                    if 0 < e <= 480:  # if it is in OPD region calls lab
                        Lab_chc3()
                    else:  # Schedules it to the next day
                        j = 1440 - e
                        Lab_chc3(at=a + j + 1)
                if 52 < y < 70:  # 17.6% of the total patients require radiography
                    y3 = random.randint(0, 100)
                    if y3 < 50:  # 50 % patients for xray
                        c = env.now() / 1440
                        d = c % 1
                        e = d * 1440
                        if 0 < e <= 480:
                            Xray_chc3()
                        else:  # Schedules it to the next day
                            j = 1440 - e
                            Xray_chc3(at=env.now() + j + 1)
                    else:
                        c = env.now() / 1440
                        d = c % 1
                        e = d * 1440
                        if 0 < e <= 480:
                            Ecg_chc3()

                        else:  # Schedules it to the next day
                            j = 1440 - e
                            Ecg_chc3(at=env.now() + j + 1)
                yield self.request(MO_chc3, emer_nurse_chc3, e_beds_chc3)
                doc_time = sim.Uniform(10, 20).sample()
                yield self.hold(doc_time)
                self.release(MO_chc3)
                nurse_time = sim.Uniform(20, 30).sample()
                yield self.hold((nurse_time - doc_time))  # subtracting just to account nurse time
                self.release(emer_nurse_chc3)
                stay = random.uniform(60, 300)
                yield self.hold(stay)
                self.release(e_beds_chc3)
                x = random.randint(0, 10)
                if x < 5:  # only 50% patients require inpatient care
                    yield self.request(in_beds_chc3, ipd_nurse_chc3)
                    t_nurse = sim.Uniform(10, 20).sample()
                    t_bed = sim.Triangular(120, 1440, 240).sample()
                    yield self.hold(t_nurse)
                    self.release(ipd_nurse_chc3)
                    yield self.hold(t_bed - t_nurse)
                    self.release(in_beds_chc3)
        else:
            # referrals
            self.enter(emr_q_chc3)
            c = env.now()
            yield self.request(MO_chc3)
            self.leave(emr_q_chc3)
            emr_q_waiting_time_chc3.append(env.now() - c)
            doc_time = sim.Uniform(10, 20).sample()
            emergency_time_chc3 += doc_time
            yield self.hold(doc_time)
            self.release(MO_chc3)
            z = random.randint(0, 100)
            if z < 11:
                emergency_refer_chc3 += 1
            else:
                emergency_count_chc3 += 1
                y = random.randint(0, 1000)
                "Patients go to lab and/or radiography lab before getting admitted to emergency"
                if y < 496:  # 50% emergency patients require lab tests
                    a = env.now()  # for scheduling lab tests during OPD hours
                    c = a / 1440  # divides a by minutes in a day
                    d = c % 1  # takes out the decimal part from c
                    e = d * 1440  # finds out the minutes corrsponding to decimal part
                    if 0 < e <= 480:  # if it is in OPD region calls lab
                        Lab_chc3()
                    else:  # Schedules it to the next day
                        j = 1440 - e
                        Lab_chc3(at=a + j + 1)
                if 0 <= y < 666:  # 66% of the total patients require radiography
                    ys = random.randint(0, 100)
                    if ys < 73:  # 73% patients for X-Rays
                        c = env.now() / 1440
                        d = c % 1
                        e = d * 1440
                        if 0 < e <= 480:
                            Xray_chc3()
                        else:  # Schedules it to the next day
                            j = 1440 - e
                            Xray_chc3(at=env.now() + j + 1)
                    else:  # 50% patients for ecg
                        c = env.now() / 1440
                        d = c % 1
                        e = d * 1440
                        if 0 < e <= 480:
                            Ecg_chc3()
                        else:  # Schedules it to the next day
                            j = 1440 - e
                            Ecg_chc3(at=env.now() + j + 1)

                yield self.request(emer_nurse_chc3)
                nurse_time = sim.Uniform(20, 30).sample()
                emergency_nurse_time_chc3 += nurse_time
                yield self.hold(nurse_time)  # subtracting just to account nurse time
                self.release(emer_nurse_chc3)
                yield self.request(e_beds_chc3)
                stay = random.uniform(60, 300)
                emergency_bed_time_chc3 += stay
                yield self.hold(stay)
                self.release(e_beds_chc3)
                x = random.randint(0, 10)
                if x < 5:  # only 50% patients require inpatient care
                    emer_inpatients_chc3 += 1
                    self.enter(ipd_q_chc3)
                    h = env.now()
                    yield self.request(in_beds_chc3)
                    ipd_bed_wt_chc3.append((env.now() - h))
                    yield self.request(ipd_nurse_chc3)
                    self.leave(ipd_q_chc3)
                    t_nurse = sim.Uniform(10, 20).sample()
                    t_bed = sim.Triangular(120, 1440, 240).sample()
                    yield self.hold(t_nurse)
                    ipd_nurse_time_chc3 += t_nurse
                    self.release(ipd_nurse_chc3)
                    yield self.hold(t_bed - t_nurse)
                    self.release(in_beds_chc3)
                    ipd_bed_time_chc3 += t_bed
                    ipd_MO_time_chc3 += t_nurse


class Delivery_patient_generator_chc3(sim.Component):

    def process(self):
        global delivery_iat_chc3
        global warmup_time
        global delivery_count_chc3

        while True:
            if env.now() <= warmup_time:
                Delivery_ipd_chc3()
                t = sim.Exponential(delivery_iat_chc3).sample()
                yield self.hold(t)
            else:
                Delivery_ipd_chc3()
                t = sim.Exponential(delivery_iat_chc3).sample()
                yield self.hold(t)


class Delivery_ipd_chc3(sim.Component):

    def process(self):
        global in_beds_chc3
        global ipd_nurse_chc3
        global ipd_nurse_time_chc3
        global MO_chc3
        global warmup_time
        global childbirth_count_chc3
        global childbirth_referred_chc3
        global ipd_MO_time_chc3
        global ipd_bed_time_chc3
        global ipd_q_chc3
        global ipd_bed_wt_chc3

        if env.now() <= warmup_time:
            pass
        else:
            childbirth_count_chc3 += 1
            x = random.randint(0, 100)
            if x <= 4:
                childbirth_referred_chc3 += 1
                pass
            else:
                self.enter(ipd_q_chc3)
                h = env.now()
                yield self.request(in_beds_chc3)
                self.leave(ipd_q_chc3)
                ipd_bed_wt_chc3.append((env.now() - h))
                yield self.request(ipd_nurse_chc3)
                t1 = sim.Uniform(10, 20).sample()
                ipd_nurse_time_chc3 += t1
                self.hold(t1)
                self.release(ipd_nurse_chc3)
                yield self.request(MO_chc3)
                t2 = sim.Uniform(5, 10).sample()
                ipd_MO_time_chc3 += t2
                yield self.hold(t2)
                self.release(MO_chc3)
                t3 = sim.Uniform(240, 360).sample()
                yield self.hold(t3 - t2 - t1)
                ipd_bed_time_chc3 += (t3 - t2 - t1)
                self.release(in_beds_chc3)
                Delivery_chc3()


class Delivery_chc3(sim.Component):

    def process(self):
        global delivery_nurse_chc3
        global ipd_nurse_chc3
        global MO_chc3
        global delivery_bed_chc3
        global warmpup_time
        global e_beds_chc3
        global ipd_nurse_time_chc3
        global MO_del_time_chc3
        global in_beds_chc3
        global delivery_nurse_time_chc3
        global inpatient_del_count_chc3
        global delivery_count_chc3
        global emergency_bed_time_chc3
        global ipd_bed_time_chc3
        global emergency_nurse_time_chc3
        global referred_chc3
        global ipd_bed_wt_chc3

        if env.now() <= warmup_time:
            t_doc = sim.Uniform(30, 60).sample()
            t_bed = sim.Uniform(240, 600).sample()
            yield self.request(MO_chc3, fail_delay=20)
            if self.failed():  # if doctor is busy staff nurse takes care
                yield self.request(delivery_nurse_chc3, delivery_bed_chc3)
                yield self.hold(t_bed)
                self.release(delivery_nurse_chc3)
                self.release(delivery_bed_chc3)
            else:
                yield self.hold(t_doc)
                self.release(MO_chc3)
                yield self.request(delivery_nurse_chc3, delivery_bed_chc3)
                yield self.hold(t_bed)
                self.release(delivery_nurse_chc3)
                self.release(delivery_bed_chc3)
        else:
            delivery_count_chc3 += 1
            inpatient_del_count_chc3 += 1
            yield self.request(MO_chc3, fail_delay=20)
            t_doc = sim.Uniform(30, 60).sample()
            t_bed = sim.Uniform(240, 600).sample()  # delivery bed, nurse time
            delivery_nurse_time_chc3 += t_bed
            if self.failed():  # if doctor is busy staff nurse takes care
                yield self.request(delivery_nurse_chc3, delivery_bed_chc3)
                yield self.hold(t_bed)
                self.release(delivery_nurse_chc3)  # delivery nurse and delivery beds are released simultaneoulsy
                self.release(delivery_bed_chc3)
                # after delivery patient shifts to IPD and requests nurse and inpatient bed
                yield self.request(in_beds_chc3, ipd_nurse_chc3)
                t_n = sim.Uniform(20, 30).sample()  # inpatient nurse time in ipd after delivery
                t_bed2 = sim.Uniform(1440, 2880).sample()  # inpatient beds post delivery stay
                yield self.hold(t_n)
                self.release(ipd_nurse_chc3)
                ipd_nurse_time_chc3 += t_n
                yield self.hold(t_bed2 - t_n)
                ipd_bed_time_chc3 += t_bed2

            else:
                MO_del_time_chc3 += t_doc  # MO
                yield self.hold(t_doc)
                self.release(MO_chc3)
                yield self.request(delivery_nurse_chc3, delivery_bed_chc3)
                yield self.hold(t_bed)
                self.release(delivery_nurse_chc3)  # delivery nurse and delivery beds are released simultaneoulsy
                self.release(delivery_bed_chc3)
                h = env.now()
                yield self.request(in_beds_chc3)
                ipd_bed_wt_chc3.append((env.now() - h))
                yield self.request(ipd_nurse_chc3)
                t_n = sim.Uniform(20, 30).sample()  # staff nurser time in ipd after delivery
                t_bed1 = sim.Uniform(1440, 2880).sample()
                yield self.hold(t_n)
                self.release(ipd_nurse_chc3)
                ipd_nurse_time_chc3 += t_n
                yield self.hold(t_bed1 - t_n)
                ipd_bed_time_chc3 += t_bed1


class Lab_chc3(sim.Component):

    def process(self):
        global lab_q_chc3
        global lab_technician_chc3
        global lab_time_chc3
        global lab_q_waiting_time_chc3
        global warmup_time
        global lab_count_chc3

        if env.now() <= warmup_time:
            self.enter(lab_q_chc3)
            yield self.request(lab_technician_chc3)
            self.leave(lab_q_chc3)
            yp = (np.random.lognormal(5.332, 0.262))
            y0 = yp / 60
            yield self.hold(y0)
            self.release(lab_technician_chc3)
        else:
            lab_count_chc3 += 1
            self.enter(lab_q_chc3)
            a0 = env.now()
            yield self.request(lab_technician_chc3)
            self.leave(lab_q_chc3)
            lab_q_waiting_time_chc3.append(env.now() - a0)
            yp = (np.random.lognormal(5.332, 0.262))
            y0 = yp / 60
            yield self.hold(y0)
            self.release(lab_technician_chc3)
            lab_time_chc3 += y0


class IPD_chc3(sim.Component):

    def process(self):
        global MO_ipd_chc3
        global ipd_nurse_chc3
        global in_beds_chc3
        global ipd_MO_time_chc3
        global ipd_nurse_time_chc3
        global warmup_time
        global ipd_bed_time_chc3
        global ipd_nurse_time_chc3
        global emergency_refer_chc3
        global ipd_q_chc3
        global ipd_MO_time_chc3
        global ipd_bed_wt_chc3

        if env.now() <= warmup_time:
            self.enter(ipd_q_chc3)
            yield self.request(in_beds_chc3)
            self.leave(ipd_q_chc3)
            yield self.request(ipd_nurse_chc3)
            yield self.request(MO_ipd_chc3)
            t_doc = sim.Uniform(10, 20).sample()
            t_nurse = sim.Uniform(20, 30).sample()
            t_bed = sim.Uniform(240, 4880).sample()
            yield self.hold(t_doc)
            self.release(MO_ipd_chc3)
            yield self.hold(t_nurse - t_doc)
            self.release(ipd_nurse_chc3)
            yield self.hold(t_bed - t_nurse - t_doc)
            self.release(in_beds_chc3)
        else:
            self.enter(ipd_q_chc3)
            h = env.now()
            yield self.request(in_beds_chc3)
            self.leave(ipd_q_chc3)
            ipd_bed_wt_chc3.append((env.now() - h))
            yield self.request(ipd_nurse_chc3)
            yield self.request(MO_ipd_chc3)

            t_doc = sim.Uniform(10, 20).sample()
            t_nurse = sim.Uniform(20, 30).sample()
            t_bed = sim.Uniform(240, 4880).sample()
            ipd_bed_time_chc3 += t_bed
            ipd_MO_time_chc3 += t_doc
            yield self.hold(t_doc)
            self.release(MO_ipd_chc3)
            yield self.hold(t_nurse - t_doc)
            ipd_nurse_time_chc3 += t_nurse
            self.release(ipd_nurse_chc3)
            # lab starts from here
            x = random.randint(0, 1000)  # for lab
            if x <= 408:  # 41% (5) patients for lab. Of them 12.5% go to radiography
                a = env.now()  # for scheduling lab tests during OPD hours
                c = a / 1440  # divides a by minutes in a day
                d = c % 1  # takes out the decimal part from c
                e = d * 1440  # finds out the minutes corrsponding to decimal part
                if 0 < e <= 480:  # if it is in OPD region calls lab
                    Lab_chc3()
                else:  # Schedules it to the next day
                    j = 1440 - e
                    Lab_chc3(at=a + j + 1)
            p = random.randint(0, 1000)  # for radiography
            if p < 245:  # 24.5% of the total patients require radiography
                y0 = random.randint(0, 10)
                if y0 < 10:  # 100 % patients for X-Ray
                    a = env.now()  # for scheduling lab tests during OPD hours
                    c = a / 1440  # divides a by minutes in a day
                    d = c % 1  # takes out the decimal part from c
                    e = d * 1440  # finds out the minutes corrsponding to decimal part
                    if 0 < e <= 480:  # if it is in OPD region calls lab
                        Xray_chc3()
                    else:  # Schedules it to the next day
                        j = 1440 - e
                        Xray_chc3(at=a + j + 1)
                else:
                    pass        # no ecg
            yield self.hold(t_bed - t_nurse - t_doc)
            self.release(in_beds_chc3)


class ANC_chc3(sim.Component):
    global ANC_iat_chc3
    global day
    day = 0
    env = sim.Environment()
    No_of_shifts = 0  # tracks number of shifts completed during the simulation time
    No_of_days = 0
    ANC_List = {}
    anc_count = 0
    ANC_p_count = 0

    def process(self):

        global day

        while True:  # condition to run simulation for 8 hour shifts
            x = env.now() - 1440 * days
            if 0 <= x < 480:
                ANC_chc3.anc_count += 1  # counts overall patients throghout simulation
                ANC_chc3.ANC_p_count += 1  # counts patients in each replication
                id = ANC_chc3.anc_count
                age = 223
                day_of_registration = ANC_chc3.No_of_days
                visit = 1
                x0 = round(env.now())
                x1 = x0 + 14 * 7 * 24 * 60
                x2 = x0 + 20 * 7 * 24 * 60
                x3 = x0 + 24 * 7 * 24 * 60
                scheduled_visits = [[0], [0], [0], [0]]
                scheduled_visits[0] = x0
                scheduled_visits[1] = x1
                scheduled_visits[2] = x2
                scheduled_visits[3] = x3
                dic = {"ID": id, "Age": age, "Visit Number": visit, "Registration day": day_of_registration,
                       "Scheduled Visit": scheduled_visits}
                ANC_chc3.ANC_List[id] = dic
                ANC_Checkup_chc2()
                ANC_followup_chc2(at=ANC_chc3.ANC_List[id]["Scheduled Visit"][1])
                ANC_followup_chc2(at=ANC_chc3.ANC_List[id]["Scheduled Visit"][2])
                ANC_followup_chc2(at=ANC_chc3.ANC_List[id]["Scheduled Visit"][3])
                hold_time = sim.Exponential(ANC_iat_chc3).sample()
                yield self.hold(hold_time)
            else:
                yield self.hold(960)
                day = int(env.now() / 1440)  # holds simulation for 2 shifts


class ANC_Checkup_chc3(sim.Component):
    anc_checkup_count = 0

    def process(self):

        global warmup_time
        global delivery_nurse_chc3
        global delivery_nurse_time_chc3

        if env.now() <= warmup_time:
            yield self.request(delivery_nurse_chc3)
            temp = sim.Triangular(8, 20.6, 12.3).sample()
            yield self.hold(temp)  # time taken from a study on ANC visits in Tanzania
            Lab_chc3()
            Pharmacy_chc3()

        else:
            ANC_Checkup_chc2.anc_checkup_count += 1
            yield self.request(delivery_nurse_chc3)
            temp = sim.Triangular(8, 20.6, 12.3).sample()
            delivery_nurse_time_chc3 += temp
            yield self.hold(temp)  # time taken from a study on ANC visits in Tanzania
            # Gynecologist_OPD()
            Lab_chc3()
            Pharmacy_chc3()


class ANC_followup_chc3(sim.Component):
    followup_count = 0

    def process(self):

        global warmup_time
        global delivery_nurse_chc3
        global q_ANC_chc3
        global delivery_nurse_time_chc3

        if env.now() <= warmup_time:
            for key in ANC_chc3.ANC_List:  # for identifying and updating ANC visit number
                x0 = env.now()
                x1 = ANC_chc3.ANC_List[key]["Scheduled Visit"][1]
                x2 = ANC_chc3.ANC_List[key]["Scheduled Visit"][2]
                x3 = ANC_chc3.ANC_List[key]["Scheduled Visit"][3]
                if 0 <= (x1 - x0) < 481:
                    ANC_chc3.ANC_List[key]["Scheduled Visit"][1] = float("inf")
                    ANC_chc3.ANC_List[key]["Visit Number"] = 2
                elif 0 <= (x2 - x0) < 481:
                    ANC_chc3.ANC_List[key]["Scheduled Visit"][2] = float("inf")
                    ANC_chc3.ANC_List[key]["Visit Number"] = 3
                elif 0 <= (x3 - x0) < 481:
                    ANC_chc3.ANC_List[key]["Scheduled Visit"][3] = float("inf")
                    ANC_chc3.ANC_List[key]["Visit Number"] = 4

            yield self.request(delivery_nurse_chc3)
            temp = sim.Triangular(3.33, 13.16, 6.50).sample()
            yield self.hold(temp)
            self.release(delivery_nurse_chc3)
            Lab_chc3()
            Pharmacy_chc3()

        else:
            for key in ANC_chc3.ANC_List:  # for identifying and updating ANC visit number
                x0 = env.now()
                x1 = ANC_chc3.ANC_List[key]["Scheduled Visit"][1]
                x2 = ANC_chc3.ANC_List[key]["Scheduled Visit"][2]
                x3 = ANC_chc3.ANC_List[key]["Scheduled Visit"][3]
                if 0 <= (x1 - x0) < 481:
                    ANC_chc3.ANC_List[key]["Scheduled Visit"][1] = float("inf")
                    ANC_chc3.ANC_List[key]["Visit Number"] = 2
                elif 0 <= (x2 - x0) < 481:
                    ANC_chc3.ANC_List[key]["Scheduled Visit"][2] = float("inf")
                    ANC_chc3.ANC_List[key]["Visit Number"] = 3
                elif 0 <= (x3 - x0) < 481:
                    ANC_chc3.ANC_List[key]["Scheduled Visit"][3] = float("inf")
                    ANC_chc3.ANC_List[key]["Visit Number"] = 4

            yield self.request(delivery_nurse_chc3)
            temp = sim.Triangular(3.33, 13.16, 6.50).sample()
            yield self.hold(temp)
            self.release(delivery_nurse_chc3)
            rand = random.randint(0, 10)
            if rand < 3:  # only 30 % ANC checks require consultation
                # Gynecologist_OPD()
                pass
            Lab_chc3()
            Pharmacy_chc3()


class Surgery_patient_generator_chc3(sim.Component):

    def process(self):

        global warmup_time
        global surgery_count_chc3
        global surgery_iat_chc3

        while True:
            if env.now() <= warmup_time:
                OT_chc3()
                yield self.hold(sim.Exponential(surgery_iat_chc3).sample())
            else:
                surgery_count_chc3 += 1
                OT_chc3()
                yield self.hold(sim.Exponential(surgery_iat_chc3).sample())


class OT_chc3(sim.Component):

    def process(self):

        global warmup_time
        global doc_surgeon_chc3
        global doc_ans_chc3
        global sur_time_chc3
        global ans_time_chc3
        global ot_nurse_chc3
        global ot_nurse_time_chc3
        global ipd_surgery_count_chc3

        if env.now() <= warmup_time:
            yield self.request(doc_surgeon_chc3, doc_ans_chc3, ot_nurse_chc3)
            surgery_time = sim.Uniform(20, 60).sample()
            yield self.hold(surgery_time)
            self.release(doc_ans_chc3, doc_surgeon_chc3, ot_nurse_chc3)
            IPD_chc3()
        else:
            yield self.request(doc_surgeon_chc3, doc_ans_chc3, ot_nurse_chc3)
            surgery_time = sim.Uniform(20, 60).sample()
            sur_time_chc3 += surgery_time
            ans_time_chc3 += surgery_time
            ot_nurse_time_chc3 += surgery_time
            yield self.hold(surgery_time)
            self.release(doc_ans_chc3, doc_surgeon_chc3, ot_nurse_chc3)
            IPD_chc3()
            ipd_surgery_count_chc3 += 1


class Xray_chc3(sim.Component):

    def process(self):
        global xray_count_chc3
        global xray_tech_chc3
        global radio_time_chc3
        global xray_q_chc3
        global xray_q_waiting_time_chc3
        global xray_q_length_chc3
        global xray_time_chc3
        global warmup_time

        if env.now() <= warmup_time:
            self.enter(xray_q_chc3)
            yield self.request(xray_tech_chc3)
            self.leave(xray_q_chc3)
            y1 = sim.Triangular(2, 20, 9).sample()
            yield self.hold(y1)
            self.release(xray_tech_chc3)
        else:
            xray_count_chc3 += 1
            self.enter(xray_q_chc3)
            g0 = env.now()
            yield self.request(xray_tech_chc3)
            self.leave(xray_q_chc3)
            xray_q_waiting_time_chc3.append(env.now() - g0)
            y1 = sim.Triangular(2, 20, 9).sample()
            xray_time_chc3 += y1
            yield self.hold(y1)
            self.release(xray_tech_chc3)


class Ecg_chc3(sim.Component):

    def process(self):
        global xray_tech_chc3
        global radio_time_chc3
        global ecg_q_chc3
        global ecg_q_waiting_time_chc3
        global ecg_q_length_chc3
        global xray_time_chc3
        global ecg_count_chc3
        global warmuo_time

        if env.now() <= warmup_time:
            self.enter(ecg_q_chc3)
            yield self.request(xray_tech_chc3)
            self.leave(ecg_q_chc3)
            yp = sim.Uniform(7, 13).sample()
            yield self.hold(yp)
            self.release(xray_tech_chc3)
        else:
            ecg_count_chc3 += 1
            self.enter(ecg_q_chc3)
            b0 = env.now()
            yield self.request(xray_tech_chc3)
            self.leave(ecg_q_chc3)
            ecg_q_waiting_time_chc3.append(env.now() - b0)
            yp = sim.Uniform(7, 13).sample()
            xray_time_chc3 += yp
            yield self.hold(yp)
            self.release(xray_tech_chc3)


"This class is for testing the regular OPD patients "


class opd_covid_chc3(sim.Component):

    def process(self):
        global covid_q_chc3
        global warmup_time
        global ipd_nurse_chc3
        global ipd_nurse_time_chc3
        global lab_time_chc3
        global lab_technician_chc3
        global ipd_nurse_time_chc3

        if env.now() <= warmup_time:
            self.enter(covid_q_chc3)
            yield self.request(ipd_nurse_chc3)
            self.leave(covid_q_chc3)
            h1 = sim.Uniform(5, 10).sample()
            yield self.hold(h1)
            self.release(ipd_nurse_chc3)
            yield self.request(lab_technician_chc3)
            t = sim.Uniform(1, 2).sample()
            yield self.hold(t)

            self.release(lab_technician_chc3)
            yield self.hold(sim.Uniform(15, 30).sample())  # patient waits for the result
        else:
            x = random.randint(0, 100)
            self.enter(covid_q_chc3)
            yield self.request(ipd_nurse_chc3)
            self.leave(covid_q_chc3)
            h1 = sim.Uniform(5, 10).sample()
            yield self.hold(h1)
            self.release(ipd_nurse_chc3)
            ipd_nurse_time_chc3 += h1
            yield self.request(lab_technician_chc3)
            t = sim.Uniform(1, 2).sample()
            yield self.hold(t)
            lab_time_chc3 += t
            self.release(lab_technician_chc3)
            yield self.hold(sim.Uniform(15, 30).sample())  # patient waits for the result
            Pharmacy_chc3()


class CovidGenerator_chc3(sim.Component):

    def process(self):
        global d_chc3
        global warmup_time
        global ia_covid_chc
        global chc3_covid_iat
        global chc_covid_iat

        global ia_covid_chc
        global d_cc_chc3
        global e_cc_chc3
        global f_cc_chc3
        global d_dh_chc3
        global e_dh_chc3
        global f_dh_chc3
        global array_d_cc_chc3
        global array_e_cc_chc3
        global array_f_cc_chc3
        global array_d_dh_chc3
        global array_e_dh_chc3
        global array_f_dh_chc3
        global t_m_chc3
        global t_s_chc3
        global t_c_chc3
        global t_b_chc3
        global t_a_chc3
        global a_cc_chc3
        global b_cc_chc3
        global c_cc_chc3
        global a_dh_chc3
        global b_dh_chc3
        global c_dh_chc3
        global t_d_chc3
        global t_e_chc3
        global t_f_chc3
        global array_t_s_chc3
        global array_t_d_chc3
        global array_t_e_chc3
        global array_t_f_chc3
        global array_t_m_chc3
        global array_t_a_chc3
        global array_t_b_chc3
        global array_t_c_chc3
        global array_a_cc_chc3
        global array_b_cc_chc3
        global array_c_cc_chc3
        global array_a_dh_chc3
        global array_b_dh_chc3
        global array_c_dh_chc3
        global j

        # for daily values for the DH patients
        global dh_2_cc_a
        global dh_2_cc_b
        global dh_2_cc_c
        global dh_2_cc_d
        global dh_2_cc_e
        global dh_2_cc_f

        global dh_total_a
        global dh_total_b
        global dh_total_c
        global dh_total_d
        global dh_total_e
        global dh_total_f

        global dh_2_cc_b_ox
        global dh_2_cc_c_ven
        global array_dh_2_cc_b_ox
        global array_dh_2_cc_c_ven


        global array_dh_2_cc_a
        global array_dh_2_cc_b
        global array_dh_2_cc_c
        global array_dh_2_cc_d
        global array_dh_2_cc_e
        global array_dh_2_cc_f
        global array_dh_total_a
        global array_dh_total_b
        global array_dh_total_c
        global array_dh_total_d
        global array_dh_total_e
        global array_dh_total_f

        while True:
            if env.now() < warmup_time:
                if 0 <= (env.now() - d_chc3 * 1440) < 480:
                    covid_chc3()
                    yield self.hold(1440 / 3)
                    d_chc3 = int(env.now() / 1440)
                else:
                    yield self.hold(960)
                    d_chc3 = int(env.now() / 1440)
            else:
                a = chc_covid_iat[j]
                if 0 <= (env.now() - d_chc3 * 1440) < 480:
                    covid_chc3()
                    yield self.hold(sim.Exponential(a).sample())
                    d_chc3 = int(env.now() / 1440)
                else:
                    array_a_cc_chc3.append(a_cc_chc3)  # daily proportion of patients referred
                    array_b_cc_chc3.append(b_cc_chc3)
                    array_c_cc_chc3.append(c_cc_chc3)
                    array_d_cc_chc3.append(d_cc_chc3)  # daily proportion of patients referred
                    array_e_cc_chc3.append(e_cc_chc3)
                    array_f_cc_chc3.append(f_cc_chc3)

                    array_a_dh_chc3.append(a_dh_chc3)
                    array_b_dh_chc3.append(b_dh_chc3)
                    array_c_dh_chc3.append(c_dh_chc3)
                    array_d_dh_chc3.append(d_dh_chc3)
                    array_e_dh_chc3.append(e_dh_chc3)
                    array_f_dh_chc3.append(f_dh_chc3)

                    array_t_a_chc3.append(t_a_chc3)
                    array_t_b_chc3.append(t_b_chc3)
                    array_t_c_chc3.append(t_c_chc3)
                    array_t_d_chc3.append(t_d_chc3)
                    array_t_e_chc3.append(t_e_chc3)
                    array_t_f_chc3.append(t_f_chc3)

                    array_t_m_chc3.append(t_m_chc3)
                    array_t_s_chc3.append(t_s_chc3)
                    t_a_chc3 = 0
                    t_b_chc3 = 0
                    t_c_chc3 = 0
                    t_d_chc3 = 0
                    t_e_chc3 = 0
                    t_f_chc3 = 0
                    d_cc_chc3 = 0
                    e_cc_chc3 = 0
                    f_cc_chc3 = 0
                    d_dh_chc3 = 0
                    e_dh_chc3 = 0
                    f_dh_chc3 = 0
                    a_cc_chc3 = 0
                    b_cc_chc3 = 0
                    c_cc_chc3 = 0
                    a_dh_chc3 = 0
                    b_dh_chc3 = 0
                    c_dh_chc3 = 0
                    t_s_chc3 = 0
                    t_m_chc3 = 0
                    yield self.hold(960)
                    array_dh_2_cc_a.append(dh_2_cc_a)
                    array_dh_2_cc_b.append(dh_2_cc_b)
                    array_dh_2_cc_c.append(dh_2_cc_c)
                    array_dh_2_cc_d.append(dh_2_cc_d)
                    array_dh_2_cc_e.append(dh_2_cc_e)
                    array_dh_2_cc_f.append(dh_2_cc_f)

                    array_dh_total_a.append(dh_total_a)
                    array_dh_total_b.append(dh_total_b)
                    array_dh_total_c.append(dh_total_c)
                    array_dh_total_d.append(dh_total_d)
                    array_dh_total_e.append(dh_total_e)
                    array_dh_total_f.append(dh_total_f)
                    array_dh_2_cc_b_ox.append(dh_2_cc_b_ox)
                    array_dh_2_cc_c_ven.append(dh_2_cc_c_ven)
                    d_chc3 = int(env.now() / 1440)
                    dh_2_cc_a = 0
                    dh_2_cc_b= 0
                    dh_2_cc_c=0
                    dh_2_cc_d=0
                    dh_2_cc_e=0
                    dh_2_cc_f=0
                    dh_2_cc_b_ox = 0
                    dh_2_cc_c_ven = 0

                    dh_total_a=0
                    dh_total_b=0
                    dh_total_c=0
                    dh_total_d=0
                    dh_total_e=0
                    dh_total_f=0


class covid_chc3(sim.Component):

    def process(self):

        global home_refer_chc3
        global chc_refer_chc3
        global dh_refer_chc3
        global isolation_ward_refer_from_CHC_chc3
        global covid_patient_time_chc3
        global covid_count_chc3
        global warmup_time
        global ipd_nurse_chc3
        global ipd_nurse_time_chc3
        global doc_OPD_chc3
        global MO_covid_time_chc3
        global MO_ipd_chc3
        global chc3_to_dh_dist
        global chc3_to_cc_dist
        global ICU_oxygen
        global chc3_to_cc_severe_case
        global ICU_oxygen
        global chc3_2_cc
        global chc3_2_dh
        global chc3_severe_covid
        global chc3_moderate_covid
        global d_cc_chc3
        global e_cc_chc3
        global f_cc_chc3
        global d_dh_chc3
        global e_dh_chc3
        global f_dh_chc3
        global t_s_chc3
        global t_d_chc3
        global t_e_chc3
        global t_f_chc3

        if env.now() < warmup_time:
            covid_nurse_chc3()
            covid_lab_chc3()
            x = random.randint(0, 1000)
            if x < 940:
                yield self.request(doc_OPD_chc3)
                f = sim.Uniform(3, 6).sample()
                yield self.hold(f)
                self.release(doc_OPD_chc3)
                # cc_isolation()
            elif 940 < x <= 980:
                pass
                # CovidCare_chc3()
            else:
                yield self.request(doc_OPD_chc3)
                f = sim.Uniform(3, 6).sample()
                yield self.hold(f)
                self.release(doc_OPD_chc3)
                # SevereCase()
                pass
        else:
            covid_count_chc3 += 1
            covid_nurse_chc3()
            covid_lab_chc3()
            x = random.randint(0, 1000)
            if x <= 940:  # mild cases
                home_refer_chc3 += 1
                a1 = random.randint(0, 100)
                if a1 >= 90:
                    isolation_ward_refer_from_CHC_chc3 += 1
                    yield self.request(doc_OPD_chc3)
                    f = sim.Uniform(3, 6).sample()
                    yield self.hold(f)
                    self.release(doc_OPD_chc3)
                    covid_patient_time_chc3 += f
                    # chc3_to_cc_dist.append(100)
                    cc_isolation()  # those patients who can not home quarantine themselves
            elif 940 < x <= 980:  # moderate cases
                CovidCare_chc3()
                chc3_moderate_covid += 1
            else:
                t_s_chc3 += 1  # total per day severe patients
                chc3_severe_covid += 1
                yield self.request(doc_OPD_chc3)
                f = sim.Uniform(3, 6).sample()
                yield self.hold(f)
                self.release(doc_OPD_chc3)
                covid_patient_time_chc3 += f
                """Bed availability is checked at DH, if no available the send to CC"""
                p = random.randint(0, 100)
                if p < 50:  # % 64 patients require ICU oxygen beds first
                    t_f_chc3 += 1
                    if ICU_oxygen.available_quantity() < 1:  # checks if there is a vacant bed in DH
                        # if no, then patient is sent to CC
                        chc3_to_cc_severe_case += 1
                        chc3_to_cc_dist.append(chc3_2_cc)
                        cc_Type_F()
                        f_cc_chc3 += 1
                    else:
                        DH_SevereTypeF()
                        f_dh_chc3 += 1
                elif 50 <= p < 75:  # Type F patients
                    t_e_chc3 += 1
                    if ICU_ventilator.available_quantity() < 1:  # checks if there is a vacant bed in DH
                        chc3_severe_covid += 1
                        cc_ICU_ward_TypeE()
                        e_cc_chc3 += 1
                    else:
                        DH_SevereTypeF()
                        e_dh_chc3 += 1
                else:  # Type E patients
                    t_d_chc3 += 1
                    if ICU_ventilator.available_quantity() < 1:
                        d_cc_chc3 += 1
                        cc_ventilator_TypeD()
                    else:
                        chc3_to_dh_dist.append(chc3_2_dh)
                        d_dh_chc3 += 1
                        DH_SevereTypeE()


class covid_nurse_chc3(sim.Component):

    def process(self):

        global warmup_time
        global ipd_nurse_chc3
        global ipd_nurse_time_chc3
        global lab_covidcount_chc3

        if env.now() <= warmup_time:
            yield self.request(ipd_nurse_chc3)
            yield self.hold(sim.Uniform(2, 3).sample())
            self.release(ipd_nurse_chc3)
        else:
            lab_covidcount_chc3 += 1
            yield self.request(ipd_nurse_chc3)
            t = sim.Uniform(2, 3).sample()
            yield self.hold(t)
            ipd_nurse_time_chc3 += t
            self.release(ipd_nurse_chc3)


class covid_lab_chc3(sim.Component):

    def process(self):

        global lab_technician_chc3
        global lab_time_chc3
        global lab_q_waiting_time_chc3
        global warmup_time
        global lab_covidcount_chc3

        if env.now() <= warmup_time:
            yield self.request(lab_technician_chc3)
            yield self.hold(sim.Uniform(1, 2).sample())
            self.release(lab_technician_chc3)
            yield self.hold(sim.Uniform(15, 30).sample())  # patient waits for reports
            x = random.randint(0, 100)
            if x < 67:  # confirmed positive
                pass
            else:
                retesting_chc3()
        else:
            lab_covidcount_chc3 += 1
            yield self.request(lab_technician_chc3)
            t = sim.Uniform(1, 2).sample()
            yield self.hold(t)
            lab_time_chc3 += t
            self.release(lab_technician_chc3)
            yield self.hold(sim.Uniform(15, 30).sample())
            x = random.randint(0, 100)
            if x < 67:  # confirmed positive
                pass
            else:  # symptomatic negative, retesting
                retesting_chc3()


class retesting_chc3(sim.Component):

    def process(self):

        global retesting_count_chc3
        global warmup_time

        if env.now() <= warmup_time:
            yield self.hold(1440)
            covid_doc_chc3()
        else:
            retesting_count_chc3 += 1
            yield self.hold(1440)
            covid_doc_chc3()


class covid_doc_chc3(sim.Component):  # class for triaging covid patients

    def process(self):

        global doc_OPD_chc3
        global warmup_time
        global covid_q_chc3
        global covid_patient_time_chc3

        if env.now() <= warmup_time:
            self.enter(covid_q_chc3)
            yield self.request(doc_OPD_chc3)
            self.leave(covid_q_chc3)
            yield self.hold(sim.Uniform(5, 10).sample())
            self.release(doc_OPD_chc3)
        else:
            in_time = env.now()
            self.enter(covid_q_chc3)
            yield self.request(doc_OPD_chc3)
            self.leave(covid_q_chc3)
            t = sim.Uniform(5, 10).sample()
            yield self.hold(t)
            self.release(doc_OPD_chc3)
            covid_patient_time_chc3 += env.now() - in_time


class covid_doc_ipd_chc3(sim.Component):  # class for triaging covid patients

    def process(self):
        global MO_covid_time_chc3
        global MO_ipd_chc3
        global warmup_time

        if env.now() <= warmup_time:
            yield self.request(MO_ipd_chc3)
            yield self.hold(sim.Uniform(3, 6).sample())
            self.release(MO_ipd_chc3)
        else:
            in_time = env.now()
            yield self.request(MO_ipd_chc3)
            t = sim.Uniform(3 / 2, 6 / 2).sample()
            yield self.hold(t)
            MO_covid_time_chc3 += t
            self.release(MO_ipd_chc3)


class CovidCare_chc3(sim.Component):

    def process(self):
        global covid_bed_chc3
        global ipd_nurse_chc3
        global ipd_nurse_time_chc3
        global MO_chc3
        global MO_covid_time_chc3
        global warmup_time
        global moderate_refered_chc3
        global chc3_covid_bed_time
        global chc3_to_cc_dist
        global chc3_to_dh_dist
        global chc3_to_cc_moderate_case
        global chc3_2_dh
        global chc3_2_cc
        global c_bed_wait_chc3

        global t_c_chc3
        global t_b_chc3
        global t_a_chc3
        global a_cc_chc3
        global b_cc_chc3
        global c_cc_chc3
        global a_dh_chc3
        global b_dh_chc3
        global c_dh_chc3
        global t_m_chc3

        if env.now() <= warmup_time:
            yield self.request(covid_bed_chc3)
            a7 = sim.Uniform(1440 * 4, 1440 * 5).sample()
            a71 = a7 / (12 * 60)
            a711 = round(a71)
            for a8 in range(0, a711):
                covid_doc_ipd_chc3(at=env.now() + a8 * 12 * 60)
                covid_nurse_chc3(at=env.now() + a8 * 12 * 60)
            yield self.hold(a7)
            self.release(covid_bed_chc3)
        else:
            t_m_chc3 += 1
            a = random.randint(0, 100)
            if a < 90:  # 90% cases are said to remain moderate through out
                k = env.now()
                yield self.request(covid_bed_chc3, fail_delay=300)
                t_a_chc3 += 1  # total a type patients chc3
                if self.failed():
                    if General_bed_DH.available_quantity() < 1:
                        chc3_to_cc_moderate_case += 1
                        chc3_to_cc_dist.append(chc3_2_cc)
                        cc_general_ward_TypeA()
                        a_cc_chc3 += 1
                    else:
                        a_dh_chc3 += 1
                        moderate_refered_chc3 += 1
                        chc3_to_dh_dist.append(chc3_2_dh)
                        ModerateTypeA()
                else:
                    k1 = env.now()
                    c_bed_wait_chc3.append(k1 - k)
                    a7 = sim.Uniform(1440 * 4, 1440 * 5).sample()
                    chc3_covid_bed_time += a7
                    a71 = a7 / (12 * 60)
                    a711 = round(a71)
                    for a8 in range(0, a711):
                        covid_doc_ipd_chc3(at=env.now() + a8 * 12 * 60)
                        covid_nurse_chc3(at=env.now() + a8 * 12 * 60)
                    yield self.hold(a7)
                    self.release(covid_bed_chc3)
            elif 90 <= a < 98:
                if General_bed_DH.available_quantity() < 1:
                    chc3_to_cc_moderate_case += 1
                    chc3_to_cc_dist.append(chc3_2_cc)
                    cc_general_ward_TypeB()
                    b_cc_chc3 += 1
                else:
                    b_dh_chc3 += 1
                    moderate_refered_chc3 += 1
                    chc3_to_dh_dist.append(chc3_2_dh)
                    ModerateTypeB()

            else:
                t_c_chc3 += 1
                if General_bed_DH.available_quantity() < 1:
                    chc3_to_cc_moderate_case += 1
                    chc3_to_cc_dist.append(chc3_2_cc)
                    cc_general_ward_TypeC()
                    c_cc_chc3 += 1
                else:
                    moderate_refered_chc3 += 1
                    chc3_to_dh_dist.append(chc3_2_dh)
                    ModerateTypeC()
                    c_dh_chc3 += 1


# PHC1

class PatientGenerator1(sim.Component):
    global shift
    shift = 0
    No_of_days = 0

    total_OPD_patients = 0

    def process(self):

        global env
        global warmup_time
        global opd_iat1
        global days1
        global medicine_cons_time1
        global shift
        global phc1_doc_time

        self.sim_time = 0  # local variable defined for dividing each day into shits
        self.z = 0
        self.admin_count = 0
        k = 0
        while self.z % 3 == 0:  # condition to run simulation for 8 hour shifts
            PatientGenerator1.No_of_days += 1  # class variable to track number of days passed
            while self.sim_time < 360:  # from morning 8 am to afternoon 2 pm (in minutes)
                if env.now() <= warmup_time:
                    pass
                else:
                    OPD1()
                o = sim.Exponential(opd_iat1).sample()
                yield self.hold(o)
                self.sim_time += o

            while 360 <= self.sim_time < 480:  # condition for admin work after opd hours are over
                k = int(sim.Normal(100, 20).bounded_sample(60, 140))
                """For sensitivity analysis. Admin work added to staff nurse rather than doctor"""
                if env.now() <= warmup_time:
                    pass
                else:
                    medicine_cons_time1 += k  # contains all doctor service times
                    phc1_doc_time += k
                yield self.hold(120)
                self.sim_time = 481
            self.z += 3
            self.sim_time = 0
            # PatientGenerator1.No_of_shifts += 3
            yield self.hold(959)  # holds simulation for 2 shifts


class OPD1(sim.Component):
    Patient_log = {}

    def setup(self):

        self.dic = {}  # local dictionary for temporarily   storing generated patients
        # with attributes
        self.time_of_visit = [[0], [0], [0]]  # initializing for assigning time of visits
        self.regis_time = round(env.now())  # registration time is the current simulation time
        self.id = PatientGenerator1.total_OPD_patients  # patient count is patient id
        self.age_random = random.randint(0, 1000)  # assigning age to population based on census 2011 gurgaon
        if self.age_random <= 578:
            self.age = random.randint(0, 30)
        else:
            self.age = random.randint(31, 100)
        self.sex = random.choice(["male", "female"])  # Equal probability of male and female patient
        # require lab tests
        self.lab_required = random.choice(["True", "False"])  # Considering nearly half of all the patients
        self.radiography_required = random.choice(["True", "False"])
        y = random.randint(0, 999)
        self.consultation = random.choice([y])  # for medicine, gynea, pead, denta
        self.visits_assigned = random.randint(1, 10)  # assigning number of visits visits
        self.dic = {"ID": self.id, "Age": self.age, "Sex": self.sex, "Lab": self.lab_required,
                    "Registration_Time": self.regis_time, "No_of_visits": self.visits_assigned,
                    "Time_of_visit": self.time_of_visit, "Radiography": self.radiography_required,
                    "Consultation": self.consultation}
        OPD1.Patient_log[PatientGenerator1.total_OPD_patients] = self.dic

        self.process()

    def process(self):

        global c
        global medicine_q1
        global doc_OPD1
        global opd_ser_time_mean1
        global opd_ser_time_sd1
        global medicine_count1
        global medicine_cons_time1
        global opd_q_waiting_time1
        global ncd_count1
        global ncd_nurse1
        global ncd_time1
        global warmup_time
        global l3
        global phc1_doc_time

        if env.now() <= warmup_time:
            if OPD1.Patient_log[PatientGenerator1.total_OPD_patients]["Age"] > 30:
                yield self.request(ncd_nurse1)
                ncd_service = sim.Uniform(2, 5).sample()
                yield self.hold(ncd_service)
            self.enter(medicine_q1)
            yield self.request(doc_OPD1)
            self.leave(medicine_q1)
            o = sim.Normal(opd_ser_time_mean1, opd_ser_time_sd1).bounded_sample(0.3)
            yield self.hold(o)
            self.release(doc_OPD1)
            if OPD1.Patient_log[PatientGenerator1.total_OPD_patients]["Lab"] == "True":
                Lab1()
            Pharmacy1()
        else:
            medicine_count1 += 1
            p = random.randint(0, 10)
            if p < 2:  # extra 20% patients are tested for covid
                COVID_OPD_PHC1()
            if OPD1.Patient_log[PatientGenerator1.total_OPD_patients]["Age"] > 30:
                ncd_count1 += 1
                yield self.request(ncd_nurse1)
                ncd_service = sim.Uniform(2, 5).sample()
                yield self.hold(ncd_service)
                ncd_time1 += ncd_service
            # doctor opd starts from here
            entry_time = env.now()
            self.enter(medicine_q1)
            yield self.request(doc_OPD1)
            self.leave(medicine_q1)
            exit_time = env.now()
            opd_q_waiting_time1.append(exit_time - entry_time)  # stores waiting time in the queue
            o = sim.Normal(opd_ser_time_mean1, opd_ser_time_sd1).bounded_sample(0.3)
            yield self.hold(o)
            phc1_doc_time += o
            medicine_cons_time1 += o
            self.release(doc_OPD1)
            # lab starts from here
            t = random.randint(0, 1000)
            # changed here
            if OPD1.Patient_log[PatientGenerator1.total_OPD_patients]["Lab"] == "True":
                Lab1()
            Pharmacy1()


"This class is for testing the regular OPD patients. These are default negative patients" \
"but are tested "


class COVID_OPD_PHC1(sim.Component):

    def process(self):

        global ipd_nurse1
        global in_beds1
        global ipd_nurse_time1

        if env.now() <= warmup_time:
            yield self.request(ipd_nurse1)
            h1 = sim.Uniform(5, 10).sample()
            yield self.hold(h1)
            self.release(ipd_nurse1)
            OPD_covidtest_PHC1()
            yield self.hold(sim.Uniform(15, 30).sample())  # patient waits for the result
        else:
            yield self.request(ipd_nurse1)
            h1 = sim.Uniform(5, 10).sample()
            yield self.hold(h1)
            self.release(ipd_nurse1)
            OPD_covidtest_PHC1()
            ipd_nurse_time1 += h1
            yield self.hold(sim.Uniform(15, 30).sample())  # patient waits for the result


class OPD_covidtest_PHC1(sim.Component):

    def process(self):
        global lab_covidcount1
        global lab_technician1
        global lab_time1
        global warmup_time

        if env.now() <= warmup_time:
            yield self.request(lab_technician1)
            t = sim.Uniform(1, 2).sample()
            yield self.hold(t)
            self.release(lab_technician1)
        else:
            lab_covidcount1 += 1
            yield self.request(lab_technician1)
            t = sim.Uniform(1, 2).sample()
            yield self.hold(t)
            lab_time1 += t
            self.release(lab_technician1)


class Pharmacy1(sim.Component):

    def process(self):

        global pharmacist1
        global pharmacy_time1
        global pharmacy_q1
        global pharmacy_q_waiting_time1
        global warmup_time
        global pharmacy_count1

        if env.now() < warmup_time:
            self.enter(pharmacy_q1)
            yield self.request(pharmacist1)
            self.leave(pharmacy_q1)
            # service_time = sim.Uniform(1, 2.5).sample()
            service_time = sim.Normal(2.083, 0.72).bounded_sample(.67)
            yield self.hold(service_time)
            self.release(pharmacist1)
        else:
            pharmacy_count1 += 1
            e1 = env.now()
            self.enter(pharmacy_q1)
            yield self.request((pharmacist1, 1))
            self.leave(pharmacy_q1)
            pharmacy_q_waiting_time1.append(env.now() - e1)
            service_time = sim.Normal(2.083, 0.72).bounded_sample(.67)
            yield self.hold(service_time)
            self.release((pharmacist1, 1))
            pharmacy_time1 += service_time


class Delivery_patient_generator1(sim.Component):
    Delivery_list = {}

    def process(self):
        global delivery_iat1
        global warmup_time
        global delivery_count1
        global days1
        global childbirth_count1
        global N

        while True:
            if env.now() <= warmup_time:
                pass
            else:
                childbirth_count1 += 1
                self.registration_time = round(env.now())
                if 0 < (self.registration_time - N * 1440) < 480:
                    Delivery_with_doctor1(urgent=True)  # sets priority
                else:
                    Delivery_no_doc1(urgent=True)
            self.hold_time = sim.Exponential(delivery_iat1).sample()
            yield self.hold(self.hold_time)
            N = int(env.now() / 1440)


class Delivery_no_doc1(sim.Component):

    def process(self):
        global ipd_nurse1
        global ipd_nurse1
        global doc_OPD1
        global delivery_bed1
        global warmup_time
        global e_beds1
        global ipd_nurse_time1
        global MO_del_time1
        global in_beds1
        global delivery_nurse_time1
        global inpatient_del_count1
        global delivery_count1
        global emergency_bed_time
        global ipd_bed_time1
        global emergency_nurse_time
        global referred
        global fail_count1

        if env.now() <= warmup_time:
            t_nurse = sim.Uniform(120, 240, 'minutes').sample()
            t_bed = sim.Uniform(360, 600).sample()
            yield self.request(ipd_nurse1)
            yield self.hold(t_nurse)
            self.release(ipd_nurse1)
            yield self.request(delivery_bed1, fail_delay=120)
            if self.failed():
                pass
            else:
                yield self.hold(t_bed)
                self.release(delivery_bed1)
                yield self.request(in_beds1)
                yield self.hold(sim.Uniform(240, 1440, 'minutes').bounded_sample(0))
                self.release(in_beds1)
        else:
            delivery_count1 += 1
            t_bed = sim.Uniform(360, 600).sample()  # delivery bed, nurse time
            t_nur = sim.Uniform(120, 240).sample()
            delivery_nurse_time1 += t_nur
            yield self.request(ipd_nurse1)
            yield self.hold(t_nur)
            self.release(ipd_nurse1)  # delivery nurse and delivery beds are released simultaneoulsy
            yield self.request(delivery_bed1, fail_delay=120)
            if self.failed():
                fail_count1 += 1
                delivery_count1 -= 1
                pass
            else:
                yield self.hold(t_bed)
                self.release(delivery_bed1)
                yield self.request(in_beds1)
                t_bed1 = sim.Uniform(240, 1440).sample()
                yield self.hold(t_bed1)
                ipd_bed_time1 += t_bed1


class Delivery_with_doctor1(sim.Component):

    def process(self):
        global ipd_nurse1
        global ipd_nurse1
        global doc_OPD1
        global delivery_bed1
        global warmup_time
        global e_beds1
        global ipd_nurse_time1
        global MO_del_time1
        global in_beds1
        global delivery_nurse_time1
        global inpatient_del_count1
        global delivery_count1
        global emergency_bed_time
        global ipd_bed_time1
        global emergency_nurse_time
        global referred
        global fail_count1
        global opd_q_waiting_time1
        global phc1_doc_time
        global medicine_cons_time1

        if env.now() <= warmup_time:
            t_doc = sim.Uniform(30, 60).sample()
            t_bed = sim.Uniform(240, 360).sample()
            t_nurse = sim.Uniform(120, 240, 'minutes').sample()
            self.enter_at_head(medicine_q1)
            yield self.request(doc_OPD1, fail_delay=20)
            if self.failed():  # if doctor is busy staff nurse takes care
                self.leave(medicine_q1)
                yield self.request(ipd_nurse1)
                yield self.hold(t_nurse)
                self.release(ipd_nurse1)
                yield self.request(doc_OPD1)
                yield self.hold(t_doc)
                self.release(doc_OPD1)
                self.release(delivery_bed1)
                yield self.request(delivery_bed, fail_delay=120)
                if self.failed():
                    pass
                else:
                    yield self.hold(sim.Uniform(6 * 60, 10 * 60, 'minutes').sample())
                    self.release(delivery_bed)
                    yield self.request(in_beds1)
                    yield self.hold(sim.Uniform(240, 1440, 'minutes').sample())
                    self.release()
            else:
                self.leave(medicine_q1)
                yield self.hold(t_doc)
                self.release(doc_OPD1)
                yield self.request(ipd_nurse1)
                yield self.hold(t_nurse)
                self.release(ipd_nurse1)
                yield self.request(delivery_bed1)
                yield self.hold(sim.Uniform(6 * 60, 10 * 60, 'minutes').sample())
                self.release(delivery_bed)
                yield self.request(in_beds1)
                yield self.hold(sim.Uniform(240, 1440, 'minutes').bounded_sample(0))  # holding patient for min 4 hours
                # to 48 hours
                self.release(in_beds1)
        else:
            delivery_count1 += 1
            entry_time1 = env.now()
            self.enter_at_head(medicine_q1)
            yield self.request(doc_OPD1, fail_delay=20)
            t_doc = sim.Uniform(30, 60).sample()
            t_bed = sim.Uniform(360, 600).sample()  # delivery bed, nurse time
            t_nur = sim.Uniform(120, 240).sample()
            delivery_nurse_time1 += t_nur
            phc1_doc_time += t_doc
            MO_del_time1 += t_doc  # changed here
            medicine_cons_time1 += t_doc
            if self.failed():  # if doctor is busy staff nurse takes care
                self.leave(medicine_q1)
                exit_time1 = env.now()
                opd_q_waiting_time1.append(exit_time1 - entry_time1)  # stores waiting time in the queue
                yield self.request(ipd_nurse1)
                yield self.hold(t_nur)
                self.release(ipd_nurse1)
                # changed here
                yield self.request(doc_OPD1)
                yield self.hold(t_doc)
                self.release(doc_OPD1)
                yield self.request(delivery_bed1, fail_delay=120)
                if self.failed():
                    fail_count1 += 1
                    delivery_count1 -= 1
                else:
                    yield self.hold(t_bed)
                    self.release(delivery_bed1)
                    # after delivery patient shifts to IPD and requests nurse and inpatient bed
                    # changed here, removed ipd nurse
                    yield self.request(in_beds1)
                    # t_n = sim.Uniform(20, 30).sample()          # inpatient nurse time in ipd after delivery
                    t_bed2 = sim.Uniform(240, 1440).sample()  # inpatient beds post delivery stay
                    # yield self.hold(t_n)
                    # self.release(ipd_nurse1)
                    # ipd_nurse_time1 += t_n
                    yield self.hold(t_bed2)
                    ipd_bed_time1 += t_bed2
            else:
                self.leave(medicine_q1)
                exit_time1 = env.now()
                opd_q_waiting_time1.append(exit_time1 - entry_time1)  # stores waiting time in the queue
                yield self.hold(t_doc)
                self.release(doc_OPD1)
                yield self.request(ipd_nurse1)
                yield self.hold(t_nur)
                self.release(ipd_nurse1)  # delivery nurse and delivery beds are released simultaneoulsy
                yield self.request(delivery_bed1)
                yield self.hold(t_bed)
                self.release(delivery_bed1)
                yield self.request(in_beds1)
                t_bed1 = sim.Uniform(240, 1440).sample()
                yield self.hold(t_bed1)
                ipd_bed_time1 += t_bed1


class Lab1(sim.Component):

    def process(self):
        global lab_q1
        global lab_technician1
        global lab_time1
        global lab_q_waiting_time1
        global warmup_time
        global lab_count1
        global o

        if env.now() <= warmup_time:
            self.enter(lab_q1)
            yield self.request(lab_technician1)
            self.leave(lab_q1)
            yp = (sim.Normal(3.456, .823).bounded_sample(2))
            y0 = yp
            yield self.hold(y0)
            self.release(lab_technician1)
        else:
            lab_count1 += 1
            self.enter(lab_q1)
            a0 = env.now()
            yield self.request(lab_technician1)
            self.leave(lab_q1)
            lab_q_waiting_time1.append(env.now() - a0)
            f1 = env.now()
            yp = (sim.Normal(3.456, .823).bounded_sample(2))
            y0 = yp
            yield self.hold(y0)
            self.release(lab_technician1)
            f2 = env.now()
            lab_time1 += f2 - f1
            o += 1


class IPD_PatientGenerator1(sim.Component):
    global IPD1_iat
    global warmup_time
    IPD_List = {}  # log of all the IPD patients stored here
    patient_count = 0
    p_count = 0  # log of patients in each replication

    def process(self):
        global days1
        M = 0
        while True:
            if env.now() <= warmup_time:
                pass
            else:
                IPD_PatientGenerator1.patient_count += 1
                IPD_PatientGenerator1.p_count += 1
            self.registration_time = env.now()
            self.id = IPD_PatientGenerator1.patient_count
            self.age = round(random.normalvariate(35, 8))
            self.sex = random.choice(["Male", "Female"])
            IPD_PatientGenerator1.IPD_List[self.id] = [self.registration_time, self.id, self.age, self.sex]
            if 0 < (self.registration_time - M * 1440) < 480:
                IPD_with_doc1(urgent=True)
            else:
                IPD_no_doc1(urgent=True)
            self.hold_time_1 = sim.Exponential(IPD1_iat).sample()
            yield self.hold(self.hold_time_1)
            M = int(env.now() / 1440)


class IPD_no_doc1(sim.Component):

    def process(self):
        global MO_ipd_chc1
        global ipd_nurse1
        global in_beds1
        global ipd_nurse_time1
        global warmup_time
        global ipd_bed_time1
        global medicine_q1
        global ipd_MO_time1

        if env.now() <= warmup_time:

            yield self.request(in_beds1, ipd_nurse1)
            temp = sim.Uniform(30, 60, 'minutes').sample()
            yield self.hold(temp)
            self.release(ipd_nurse1)
            yield self.hold(sim.Triangular(60, 360, 180, 'minutes').bounded_sample(0))
            self.release(in_beds1)
        else:
            t_bed = sim.Triangular(60, 360, 180, 'minutes').sample()
            t_nurse = sim.Uniform(30, 60, 'minutes').sample()
            yield self.request(in_beds1, ipd_nurse1)
            yield self.hold(t_nurse)
            self.release(ipd_nurse1)
            yield self.hold(t_bed)
            self.release(in_beds1)
            ipd_bed_time1 += t_bed
            ipd_nurse_time1 += t_nurse


class IPD_with_doc1(sim.Component):

    def process(self):
        global MO_ipd_chc1
        global ipd_nurse1
        global in_beds1
        global MO_ipd_time1
        global ipd_nurse_time1
        global warmup_time
        global ipd_bed_time1
        global emergency_refer
        global medicine_q1
        global ipd_MO_time1
        global opd_q_waiting_time1
        global phc1_doc_time
        global medicine_cons_time1

        if env.now() <= warmup_time:
            self.enter_at_head(medicine_q1)
            yield self.request(doc_OPD1, fail_delay=20)
            doc_time = round(sim.Uniform(10, 30, 'minutes').sample())
            if self.failed():
                self.leave(medicine_q1)
                yield self.request(ipd_nurse1)
                temp = sim.Uniform(30, 60, 'minutes').sample()
                yield self.hold(temp)
                self.release(ipd_nurse1)
                yield self.request(doc_OPD1)
                yield self.hold(doc_time)
                self.release(doc_OPD1)
                yield self.request(in_beds1)
                yield self.hold(sim.Triangular(60, 360, 180, 'minutes').bounded_sample(0))
                self.release(in_beds1)
            else:
                self.leave(medicine_q1)
                yield self.hold(doc_time)
                self.release(doc_OPD1)
                yield self.request(in_beds1, ipd_nurse1)
                temp = sim.Uniform(30, 60, 'minutes').sample()
                yield self.hold(temp)
                self.release(ipd_nurse1)
                yield self.hold(sim.Triangular(60, 360, 180, 'minutes').bounded_sample(0))
                self.release(in_beds1)
        else:
            self.enter_at_head(medicine_q1)
            entry_time2 = env.now()
            yield self.request(doc_OPD1, fail_delay=20)
            doc_time = sim.Uniform(10, 30, 'minutes').sample()
            t_bed = sim.Triangular(60, 360, 180, 'minutes').sample()
            t_nurse = sim.Uniform(30, 60, 'minutes').sample()
            phc1_doc_time += doc_time
            medicine_cons_time1 += doc_time
            if self.failed():
                self.leave(medicine_q1)
                exit_time2 = env.now()
                opd_q_waiting_time1.append(exit_time2 - entry_time2)  # stores waiting time in the queue
                yield self.request(ipd_nurse1)
                yield self.hold(t_nurse)
                self.release(ipd_nurse1)
                yield self.request(doc_OPD1)
                yield self.hold(doc_time)
                self.release(doc_OPD1)
                yield self.request(in_beds1)
                yield self.hold(t_bed)
                self.release(in_beds1)
                ipd_bed_time1 += t_bed
                ipd_MO_time1 += doc_time
                ipd_nurse_time1 += t_nurse
            else:
                self.leave(medicine_q1)
                exit_time3 = env.now()
                opd_q_waiting_time1.append(exit_time3 - entry_time2)  # stores waiting time in the queue
                yield self.hold(doc_time)
                self.release(doc_OPD1)
                yield self.request(in_beds1, ipd_nurse1)
                yield self.hold(t_nurse)
                self.release(ipd_nurse1)
                yield self.hold(t_bed)
                self.release(in_beds1)
                ipd_bed_time1 += t_bed
                ipd_MO_time1 += doc_time
                ipd_nurse_time1 += t_nurse


class ANC1(sim.Component):
    global ANC_iat1
    global days1
    days1 = 0
    env = sim.Environment()
    No_of_shifts = 0  # tracks number of shifts completed during the simulation time
    No_of_days = 0
    ANC_List = {}
    anc_count = 0
    ANC_p_count = 0

    def process(self):

        global days1

        while True:  # condition to run simulation for 8 hour shifts
            x = env.now() - 1440 * days1
            if 0 <= x < 480:
                ANC1.anc_count += 1  # counts overall patients throghout simulation
                ANC1.ANC_p_count += 1  # counts patients in each replication
                id = ANC1.anc_count
                age = 223
                day_of_registration = ANC1.No_of_days
                visit = 1
                x0 = round(env.now())
                x1 = x0 + 14 * 7 * 24 * 60
                x2 = x0 + 20 * 7 * 24 * 60
                x3 = x0 + 24 * 7 * 24 * 60
                scheduled_visits = [[0], [0], [0], [0]]
                scheduled_visits[0] = x0
                scheduled_visits[1] = x1
                scheduled_visits[2] = x2
                scheduled_visits[3] = x3
                dic = {"ID": id, "Age": age, "Visit Number": visit, "Registration day": day_of_registration,
                       "Scheduled Visit": scheduled_visits}
                ANC1.ANC_List[id] = dic
                ANC_Checkup1()
                ANC_followup1(at=ANC1.ANC_List[id]["Scheduled Visit"][1])
                ANC_followup1(at=ANC1.ANC_List[id]["Scheduled Visit"][2])
                ANC_followup1(at=ANC1.ANC_List[id]["Scheduled Visit"][3])
                hold_time = sim.Exponential(ANC_iat1).sample()
                yield self.hold(hold_time)
            else:
                yield self.hold(960)
                days1 = int(env.now() / 1440)  # holds simulation for 2 shifts


class ANC_Checkup1(sim.Component):
    anc_checkup_count = 0

    def process(self):

        global warmup_time
        global ipd_nurse1
        global delivery_nurse_time1
        global lab_q1
        global lab_technician1
        global lab_time1
        global lab_q_waiting_time1
        global warmup_time
        global lab_count1

        if env.now() <= warmup_time:
            yield self.request(ipd_nurse1)
            temp = sim.Triangular(8, 20.6, 12.3).sample()
            yield self.hold(temp)  # time taken from a study on ANC visits in Tanzania
            self.release(ipd_nurse1)
            self.enter(lab_q1)
            yield self.request(lab_technician1)
            self.leave(lab_q1)
            yp = (sim.Normal(5, 1).bounded_sample())
            y0 = yp
            yield self.hold(y0)
            self.release(lab_technician1)
        else:
            ANC_Checkup1.anc_checkup_count += 1
            yield self.request(ipd_nurse1)
            temp = sim.Triangular(8, 20.6, 12.3).sample()
            delivery_nurse_time1 += temp
            yield self.hold(temp)  # time taken from a study on ANC visits in Tanzania
            self.release(ipd_nurse1)
            lab_count1 += 1
            # changed here
            a0 = env.now()
            self.enter(lab_q1)
            yield self.request(lab_technician1)
            self.leave(lab_q1)
            lab_q_waiting_time1.append(env.now() - a0)
            yp = (sim.Normal(3.456, .823).bounded_sample(2))
            y0 = yp
            yield self.hold(y0)
            self.release(lab_technician1)
            lab_time1 += y0


class ANC_followup1(sim.Component):
    followup_count = 0

    def process(self):

        global warmup_time
        global ipd_nurse1
        global q_ANC
        global delivery_nurse_time1
        global lab_time1

        if env.now() <= warmup_time:
            for key in ANC1.ANC_List:  # for identifying and updating ANC visit number
                x0 = env.now()
                x1 = ANC1.ANC_List[key]["Scheduled Visit"][1]
                x2 = ANC1.ANC_List[key]["Scheduled Visit"][2]
                x3 = ANC1.ANC_List[key]["Scheduled Visit"][3]
                if 0 <= (x1 - x0) < 481:
                    ANC1.ANC_List[key]["Scheduled Visit"][1] = float("inf")
                    ANC1.ANC_List[key]["Visit Number"] = 2
                elif 0 <= (x2 - x0) < 481:
                    ANC1.ANC_List[key]["Scheduled Visit"][2] = float("inf")
                    ANC1.ANC_List[key]["Visit Number"] = 3
                elif 0 <= (x3 - x0) < 481:
                    ANC1.ANC_List[key]["Scheduled Visit"][3] = float("inf")
                    ANC1.ANC_List[key]["Visit Number"] = 4

            yield self.request(ipd_nurse1)
            temp = sim.Triangular(3.33, 13.16, 6.50).sample()
            yield self.hold(temp)
            self.release(ipd_nurse1)
            self.enter(lab_q1)
            yield self.request(lab_technician1)
            self.leave(lab_q1)
            yp = (sim.Normal(3.456, .823).bounded_sample(2))
            y0 = yp
            yield self.hold(y0)
            self.release(lab_technician1)

        else:
            for key in ANC1.ANC_List:  # for identifying and updating ANC visit number
                x0 = env.now()
                x1 = ANC1.ANC_List[key]["Scheduled Visit"][1]
                x2 = ANC1.ANC_List[key]["Scheduled Visit"][2]
                x3 = ANC1.ANC_List[key]["Scheduled Visit"][3]
                if 0 <= (x1 - x0) < 481:
                    ANC1.ANC_List[key]["Scheduled Visit"][1] = float("inf")
                    ANC1.ANC_List[key]["Visit Number"] = 2
                elif 0 <= (x2 - x0) < 481:
                    ANC1.ANC_List[key]["Scheduled Visit"][2] = float("inf")
                    ANC1.ANC_List[key]["Visit Number"] = 3
                elif 0 <= (x3 - x0) < 481:
                    ANC1.ANC_List[key]["Scheduled Visit"][3] = float("inf")
                    ANC1.ANC_List[key]["Visit Number"] = 4

            yield self.request(ipd_nurse1)
            temp = sim.Triangular(3.33, 13.16, 6.50).sample()
            delivery_nurse_time1 += temp
            yield self.hold(temp)
            self.release(ipd_nurse1)
            a0 = env.now()
            self.enter(lab_q1)
            yield self.request(lab_technician1)
            self.leave(lab_q1)
            yp = (sim.Normal(3.456, .823).bounded_sample(2))
            y0 = yp
            yield self.hold(y0)
            self.release(lab_technician1)
            lab_time1 += y0


class CovidGenerator1(sim.Component):

    def process(self):
        global d1
        global warmup_time
        global phc_covid_iat
        global covid_iat_PHC1
        global j

        while True:
            if env.now() < warmup_time:
                if 0 <= (env.now() - d1 * 1440) < 480:
                    covid1()
                    yield self.hold(covid_iat_PHC1)
                    d1 = int(env.now() / 1440)
                else:
                    yield self.hold(960)
                    d1 = int(env.now() / 1440)

            else:
                a = phc_covid_iat[j]
                if 0 <= (env.now() - d1 * 1440) < 480:
                    covid1()
                    yield self.hold(sim.Exponential(a).sample())
                    d1 = int(env.now() / 1440)
                else:

                    yield self.hold(960)
                    d1 = int(env.now() / 1440)


class covid1(sim.Component):

    def process(self):

        global home_refer1
        global chc_refer1
        global dh_refer1
        global isolation_ward_refer1
        global covid_patient_time1
        global covid_count1
        global warmup_time
        global ipd_nurse1
        global ipd_nurse_time1
        global doc_OPD1
        global MO_covid_time1
        global phc2chc_count
        global home_isolation_PHC1
        global covid_nurse1

        global ICU_oxygen
        global phc1_to_cc_severe_case
        global phc1_to_cc_dist
        global phc1_2_cc

        if env.now() < warmup_time:
            covid_nurse1()
            covid_lab1()
            x = random.randint(0, 1000)
            if x <= 940:
                a = random.randint(0, 100)
                if a >= 90:
                    cc_isolation()
            elif 940 < x <= 980:
                pass
            # CovidCare_chc1()
            else:
                pass
                # SevereCase()
        else:
            covid_count1 += 1
            covid_nurse1()
            covid_lab1()
            x = random.randint(0, 1000)
            if x <= 940:  # mild cases
                home_refer1 += 1
                a = random.randint(0, 100)
                if a >= 90:  # 10 % for institutional quarantine
                    isolation_ward_refer1 += 1
                    cc_isolation()
                else:
                    home_isolation_PHC1 += 1
            elif 940 < x <= 980:  # moderate cases
                chc_refer1 += 1
                phc2chc_count += 1
                CovidCare_chc1()
            else:  # severe case
                s = random.randint(0, 100)
                if s < 50:  # Type f patients
                    if ICU_oxygen.available_quantity() < 1:  # checks if there is a vacant bed in DH
                        phc1_to_cc_severe_case += 1
                        phc1_to_cc_dist.append(phc1_2_cc)
                        c = random.randint(1, 100)
                        cc_Type_F()  # patient refered tpo CC
                    else:
                        DH_SevereTypeF()
                        dh_refer1 += 1  # Severe cases
                elif 50 <= s < 74:  # E type patients
                    if ICU_ventilator.available_quantity() < 1:  # checks if there is a vacant bed in DH
                        cc_ICU_ward_TypeE()
                        phc1_to_cc_severe_case += 1
                    else:
                        DH_SevereTypeE()
                        dh_refer1 += 1  # Severe cases
                else:  # Type d patients
                    if ICU_ventilator.available_quantity() < 1:  # checks if there is a vacant bed in DH
                        cc_ventilator_TypeD()
                        phc1_to_cc_severe_case += 1
                    else:
                        dh_refer1 += 1  # Severe cases
                        DH_SevereTypeD()


class covid_nurse1(sim.Component):
    global lab_covidcount1

    def process(self):

        global warmup_time
        global ipd_nurse1
        global ipd_nurse_time1
        global lab_covidcount1

        if env.now() <= warmup_time:
            yield self.request(ipd_nurse1)
            yield self.hold(sim.Uniform(2, 3).sample())
            self.release(ipd_nurse1)
        else:
            lab_covidcount1 += 1
            yield self.request(ipd_nurse1)
            t = sim.Uniform(2, 3).sample()
            yield self.hold(t)
            ipd_nurse_time1 += t
            self.release(ipd_nurse1)


class covid_lab1(sim.Component):

    def process(self):

        global lab_technician1
        global lab_time1
        global lab_q_waiting_time1
        global warmup_time
        global lab_covidcount1

        if env.now() <= warmup_time:
            yield self.request(lab_technician1)
            yield self.hold(sim.Uniform(1, 2).sample())
            self.release(lab_technician1)
        else:
            lab_covidcount1 += 1
            yield self.request(lab_technician1)
            t = sim.Uniform(1, 2).sample()
            yield self.hold(t)
            lab_time1 += t
            self.release(lab_technician1)
            x = random.randint(0, 100)
            if x < 33:  # confirmed positive
                covid_doc1()
            elif 33 < x < 67:  # symptomatic negative, retesting
                retesting1()
            else:
                Pharmacy1()


class retesting1(sim.Component):

    def process(self):

        global retesting_count1
        global warmup_time

        if env.now() <= warmup_time:
            yield self.hold(1440)
            covid_doc1()
        else:
            retesting_count1 += 1
            yield self.hold(1440)
            covid_doc1()


class covid_doc1(sim.Component):

    def process(self):
        global MO_covid_time1
        global doc_OPD1
        global warmup_time
        global covid_q1
        global covid_patient_time1
        global medicine_cons_time1

        if env.now() <= warmup_time:
            self.enter(covid_q1)
            yield self.request(doc_OPD1)
            self.leave(covid_q1)
            yield self.hold(sim.Uniform(3, 6).sample())
            self.release(doc_OPD1)
        else:
            in_time = env.now()
            self.enter(covid_q1)
            yield self.request(doc_OPD1)
            self.leave(covid_q1)
            t = sim.Uniform(3, 6).sample()
            yield self.hold(t)
            MO_covid_time1 += t
            medicine_cons_time1 += t
            self.release(doc_OPD1)
            covid_patient_time1 += env.now() - in_time


# PHC 2
class PatientGenerator_PHC2(sim.Component):
    global shift_PHC2
    shift_PHC2 = 0
    No_of_days_PHC2 = 0

    total_OPD_patients_PHC2 = 0

    def process(self):

        global env
        global warmup_time
        global warmup_time
        global opd_iat_PHC2
        global days_PHC2
        global medicine_cons_time_PHC2
        global shift_PHC2
        global phc1_doc_time_PHC2

        self.sim_time_PHC2 = 0  # local variable defined for dividing each day into shits
        self.z_PHC2 = 0
        self.admin_count_PHC2 = 0
        k_PHC2 = 0

        while self.z_PHC2 % 3 == 0:  # condition to run simulation for 8 hour shifts
            PatientGenerator_PHC2.No_of_days_PHC2 += 1  # class variable to track number of days passed
            while self.sim_time_PHC2 < 360:  # from morning 8 am to afternoon 2 pm (in minutes)
                if env.now() <= warmup_time:
                    pass
                else:
                    OPD_PHC2()
                o = sim.Exponential(opd_iat_PHC2).sample()
                yield self.hold(o)
                self.sim_time_PHC2 += o

            while 360 <= self.sim_time_PHC2 < 480:  # condition for admin work after opd hours are over
                k_PHC2 = int(sim.Normal(100, 20).bounded_sample(60, 140))
                """For sensitivity analysis. Admin work added to staff nurse rather than doctor"""
                if env.now() <= warmup_time:
                    pass
                else:
                    medicine_cons_time_PHC2 += k_PHC2  # conatns all doctor service times
                    phc1_doc_time_PHC2 += k_PHC2
                yield self.hold(120)
                self.sim_time_PHC2 = 481
            self.z_PHC2 += 3
            self.sim_time_PHC2 = 0
            # PatientGenerator1.No_of_shifts += 3
            yield self.hold(959)  # holds simulation for 2 shifts


l = 0
global o_PHC2  # temp opd count
o_PHC2 = 0


class OPD_PHC2(sim.Component):
    Patient_log_PHC2 = {}

    def setup(self):

        self.dic = {}  # local dictionary for temporarily   storing generated patients
        # with attributes
        self.time_of_visit = [[0], [0], [0]]  # initializing for assigning time of visits
        self.regis_time = round(env.now())  # registration time is the current simulation time
        self.id = PatientGenerator_PHC2.total_OPD_patients_PHC2  # patient count is patient id
        self.age_random = random.randint(0, 1000)  # assigning age to population based on census 2011 gurgaon
        if self.age_random <= 578:
            self.age = random.randint(0, 30)
        else:
            self.age = random.randint(31, 100)
        self.sex = random.choice(["male", "female"])  # Equal probability of male and female patient
        # require lab tests
        self.lab_required = random.choice(["True", "False"])  # Considering nearly half of all the patients
        self.radiography_required = random.choice(["True", "False"])
        y = random.randint(0, 999)
        self.consultation = random.choice([y])  # for medicine, gynea, pead, denta
        self.visits_assigned = random.randint(1, 10)  # assigning number of visits visits
        self.dic = {"ID": self.id, "Age": self.age, "Sex": self.sex, "Lab": self.lab_required,
                    "Registration_Time": self.regis_time, "No_of_visits": self.visits_assigned,
                    "Time_of_visit": self.time_of_visit, "Radiography": self.radiography_required,
                    "Consultation": self.consultation}
        OPD_PHC2.Patient_log_PHC2[PatientGenerator_PHC2.total_OPD_patients_PHC2] = self.dic

        self.process()

    def process(self):

        global c
        global medicine_q_PHC2
        global doc_OPD_PHC2
        global opd_ser_time_mean_PHC2
        global opd_ser_time_sd_PHC2
        global medicine_count_PHC2
        global medicine_cons_time_PHC2
        global opd_q_waiting_time_PHC2
        global ncd_count_PHC2
        global ncd_nurse_PHC2
        global ncd_time_PHC2
        global warmup_time
        global warmup_time
        global l
        global phc1_doc_time_PHC2

        if env.now() <= warmup_time:
            p = random.randint(0, 10)
            if p < 2:
                COVID_OPD_PHC2()
            if OPD_PHC2.Patient_log_PHC2[PatientGenerator_PHC2.total_OPD_patients_PHC2]["Age"] > 30:
                yield self.request(ncd_nurse_PHC2)
                ncd_service = sim.Uniform(2, 5).sample()
                yield self.hold(ncd_service)
            self.enter(medicine_q_PHC2)
            yield self.request(doc_OPD_PHC2)
            self.leave(medicine_q_PHC2)
            o = sim.Normal(opd_ser_time_mean_PHC2, opd_ser_time_sd_PHC2).bounded_sample(0.3)
            yield self.hold(o)
            self.release(doc_OPD_PHC2)
            if OPD_PHC2.Patient_log_PHC2[PatientGenerator_PHC2.total_OPD_patients_PHC2]["Lab"] == "True":
                Lab_PHC2()
            Pharmacy_PHC2()
        else:
            l += 1
            medicine_count_PHC2 += 1
            p = random.randint(0, 10)
            if p < 2:
                COVID_OPD_PHC2()
            if OPD_PHC2.Patient_log_PHC2[PatientGenerator_PHC2.total_OPD_patients_PHC2]["Age"] > 30:
                ncd_count_PHC2 += 1
                yield self.request(ncd_nurse_PHC2)
                ncd_service = sim.Uniform(2, 5).sample()
                yield self.hold(ncd_service)
                ncd_time_PHC2 += ncd_service
            # doctor opd starts from here
            entry_time = env.now()
            self.enter(medicine_q_PHC2)
            yield self.request(doc_OPD_PHC2)
            self.leave(medicine_q_PHC2)
            exit_time = env.now()
            opd_q_waiting_time_PHC2.append(exit_time - entry_time)  # stores waiting time in the queue
            o = sim.Normal(opd_ser_time_mean_PHC2, opd_ser_time_sd_PHC2).bounded_sample(0.3)
            yield self.hold(o)
            phc1_doc_time_PHC2 += o
            medicine_cons_time_PHC2 += o
            self.release(doc_OPD_PHC2)
            # lab starts from here
            t = random.randint(0, 1000)
            # changed here
            if OPD_PHC2.Patient_log_PHC2[PatientGenerator_PHC2.total_OPD_patients_PHC2]["Lab"] == "True":
                Lab_PHC2()
            Pharmacy_PHC2()


class COVID_OPD_PHC2(sim.Component):

    def process(self):

        global ipd_nurse_PHC2
        global delivery_nurse_time_PHC2

        if env.now() <= warmup_time:
            yield self.request(ipd_nurse_PHC2)
            h1 = sim.Uniform(5, 10).sample()
            yield self.hold(h1)
            self.release(ipd_nurse_PHC2)
            OPD_covidtest_PHC2()
            yield self.hold(sim.Uniform(15, 30).sample())  # patient waits for the result
        else:
            yield self.request(ipd_nurse_PHC2)
            h1 = sim.Uniform(5, 10).sample()
            yield self.hold(h1)
            self.release(ipd_nurse_PHC2)
            OPD_covidtest_PHC2()
            delivery_nurse_time_PHC2 += h1
            yield self.hold(sim.Uniform(15, 30).sample())


class OPD_covidtest_PHC2(sim.Component):

    def process(self):
        global lab_covidcount_PHC2
        global lab_technician_PHC2
        global lab_time_PHC2
        global warmup_time

        if env.now() <= warmup_time:
            yield self.request(lab_technician_PHC2)
            t = sim.Uniform(1, 2).sample()
            yield self.hold(t)
            self.release(lab_technician_PHC2)
        else:
            lab_covidcount_PHC2 += 1
            yield self.request(lab_technician_PHC2)
            t = sim.Uniform(1, 2).sample()
            yield self.hold(t)
            lab_time_PHC2 += t
            self.release(lab_technician_PHC2)


class Pharmacy_PHC2(sim.Component):

    def process(self):

        global pharmacist_PHC2
        global pharmacy_time_PHC2
        global pharmacy_q_PHC2
        global pharmacy_q_waiting_time_PHC2
        global warmup_time
        global pharmacy_count_PHC2
        global warmup_time

        if env.now() < warmup_time:
            self.enter(pharmacy_q_PHC2)
            yield self.request(pharmacist_PHC2)
            self.leave(pharmacy_q_PHC2)
            # service_time = sim.Uniform(1, 2.5).sample()
            service_time = sim.Normal(2.083, 0.72).bounded_sample(.67)
            yield self.hold(service_time)
            self.release(pharmacist_PHC2)
        else:
            pharmacy_count_PHC2 += 1
            e1 = env.now()
            self.enter(pharmacy_q_PHC2)
            yield self.request((pharmacist_PHC2, 1))
            self.leave(pharmacy_q_PHC2)
            pharmacy_q_waiting_time_PHC2.append(env.now() - e1)
            service_time = sim.Normal(2.083, 0.72).bounded_sample(.67)
            yield self.hold(service_time)
            self.release((pharmacist_PHC2, 1))
            pharmacy_time_PHC2 += service_time


class Delivery_patient_generator_PHC2(sim.Component):
    Delivery_list = {}

    def process(self):
        global delivery_iat_PHC2
        global warmup_time
        global delivery_count_PHC2
        global days_PHC2
        global childbirth_count_PHC2
        global N_PHC2
        global warmup_time

        while True:
            if env.now() <= warmup_time:
                pass
            else:
                childbirth_count_PHC2 += 1
                self.registration_time = round(env.now())
                if 0 < (self.registration_time - N_PHC2 * 1440) < 480:
                    Delivery_with_doctor_PHC2(urgent=True)  # sets priority
                else:
                    Delivery_no_doc_PHC2(urgent=True)
            self.hold_time = sim.Exponential(delivery_iat_PHC2).sample()
            yield self.hold(self.hold_time)
            N_PHC2 = int(env.now() / 1440)


class Delivery_no_doc_PHC2(sim.Component):

    def process(self):
        global ipd_nurse_PHC2
        global ipd_nurse_PHC2
        global doc_OPD_PHC2
        global delivery_bed_PHC2
        global warmup_time
        global e_beds_PHC2
        global ipd_nurse_time_PHC2
        global MO_del_time_PHC2
        global in_beds_PHC2
        global delivery_nurse_time_PHC2
        global inpatient_del_count_PHC2
        global delivery_count_PHC2
        global emergency_bed_time_PHC2
        global ipd_bed_time_PHC2
        global emergency_nurse_time_PHC2
        global referred_PHC2
        global fail_count_PHC2
        global warmup_time

        if env.now() <= warmup_time:
            t_nurse = sim.Uniform(120, 240, 'minutes').sample()
            t_bed = sim.Uniform(360, 600).sample()
            yield self.request(ipd_nurse_PHC2)
            yield self.hold(t_nurse)
            self.release(ipd_nurse_PHC2)
            yield self.request(delivery_bed_PHC2, fail_delay=120)
            if self.failed():
                pass
            else:
                yield self.hold(t_bed)
                self.release(delivery_bed_PHC2)
                yield self.request(in_beds_PHC2)
                yield self.hold(sim.Uniform(240, 1440, 'minutes').bounded_sample(0))
                self.release(in_beds_PHC2)
        else:
            delivery_count_PHC2 += 1
            t_bed = sim.Uniform(360, 600).sample()  # delivery bed, nurse time
            t_nur = sim.Uniform(120, 240).sample()
            delivery_nurse_time_PHC2 += t_nur
            yield self.request(ipd_nurse_PHC2)
            yield self.hold(t_nur)
            self.release(ipd_nurse_PHC2)  # delivery nurse and delivery beds are released simultaneoulsy
            yield self.request(delivery_bed_PHC2, fail_delay=120)
            if self.failed():
                fail_count_PHC2 += 1
                delivery_count_PHC2 -= 1
                pass
            else:
                yield self.hold(t_bed)
                self.release(delivery_bed_PHC2)
                yield self.request(in_beds_PHC2)
                t_bed1 = sim.Uniform(240, 1440).sample()
                yield self.hold(t_bed1)
                ipd_bed_time_PHC2 += t_bed1


class Delivery_with_doctor_PHC2(sim.Component):

    def process(self):
        global ipd_nurse_PHC2
        global ipd_nurse_PHC2
        global doc_OPD_PHC2
        global delivery_bed_PHC2
        global warmup_time
        global e_beds_PHC2
        global ipd_nurse_time_PHC2
        global MO_del_time_PHC2
        global in_beds_PHC2
        global delivery_nurse_time_PHC2
        global inpatient_del_count_PHC2
        global delivery_count_PHC2
        global emergency_bed_time_PHC2
        global ipd_bed_time_PHC2
        global emergency_nurse_time_PHC2
        global referred_PHC2
        global fail_count_PHC2
        global opd_q_waiting_time_PHC2
        global phc1_doc_time_PHC2
        global medicine_cons_time_PHC2
        global medicine_q_PHC2
        global warmup_time

        if env.now() <= warmup_time:
            t_doc = sim.Uniform(30, 60).sample()
            t_bed = sim.Uniform(240, 360).sample()
            t_nurse = sim.Uniform(120, 240, 'minutes').sample()
            self.enter_at_head(medicine_q_PHC2)
            yield self.request(doc_OPD_PHC2, fail_delay=20)
            if self.failed():  # if doctor is busy staff nurse takes care
                self.leave(medicine_q_PHC2)
                yield self.request(ipd_nurse_PHC2)
                yield self.hold(t_nurse)
                self.release(ipd_nurse_PHC2)
                yield self.request(doc_OPD_PHC2)
                yield self.hold(t_doc)
                self.release(doc_OPD_PHC2)
                self.release(delivery_bed_PHC2)
                yield self.request(delivery_bed_PHC2, fail_delay=120)
                if self.failed():
                    pass
                else:
                    yield self.hold(sim.Uniform(6 * 60, 10 * 60, 'minutes').sample())
                    self.release(delivery_bed_PHC2)
                    yield self.request(in_beds_PHC2)
                    yield self.hold(sim.Uniform(240, 1440, 'minutes').sample())
                    self.release()
            else:
                self.leave(medicine_q_PHC2)
                yield self.hold(t_doc)
                self.release(doc_OPD_PHC2)
                yield self.request(ipd_nurse_PHC2)
                yield self.hold(t_nurse)
                self.release(ipd_nurse_PHC2)
                yield self.request(delivery_bed_PHC2)
                yield self.hold(sim.Uniform(6 * 60, 10 * 60, 'minutes').sample())
                self.release(delivery_bed_PHC2)
                yield self.request(in_beds_PHC2)
                yield self.hold(sim.Uniform(240, 1440, 'minutes').bounded_sample(0))  # holding patient for min 4 hours
                # to 48 hours
                self.release(in_beds_PHC2)
        else:
            delivery_count_PHC2 += 1
            entry_time1 = env.now()
            self.enter_at_head(medicine_q_PHC2)
            yield self.request(doc_OPD_PHC2, fail_delay=20)
            t_doc = sim.Uniform(30, 60).sample()
            t_bed = sim.Uniform(360, 600).sample()  # delivery bed, nurse time
            t_nur = sim.Uniform(120, 240).sample()
            delivery_nurse_time_PHC2 += t_nur
            phc1_doc_time_PHC2 += t_doc
            MO_del_time_PHC2 += t_doc  # changed here
            medicine_cons_time_PHC2 += t_doc
            if self.failed():  # if doctor is busy staff nurse takes care
                self.leave(medicine_q_PHC2)
                exit_time1 = env.now()
                opd_q_waiting_time_PHC2.append(exit_time1 - entry_time1)  # stores waiting time in the queue
                yield self.request(ipd_nurse_PHC2)
                yield self.hold(t_nur)
                self.release(ipd_nurse_PHC2)
                # changed here
                yield self.request(doc_OPD_PHC2)
                yield self.hold(t_doc)
                self.release(doc_OPD_PHC2)
                yield self.request(delivery_bed_PHC2, fail_delay=120)
                if self.failed():
                    fail_count_PHC2 += 1
                    delivery_count_PHC2 -= 1
                else:
                    yield self.hold(t_bed)
                    self.release(delivery_bed_PHC2)
                    # after delivery patient shifts to IPD and requests nurse and inpatient bed
                    # changed here, removed ipd nurse
                    yield self.request(in_beds_PHC2)
                    # t_n = sim.Uniform(20, 30).sample()          # inpatient nurse time in ipd after delivery
                    t_bed2 = sim.Uniform(240, 1440).sample()  # inpatient beds post delivery stay
                    yield self.hold(t_bed2)
                    ipd_bed_time_PHC2 += t_bed2
            else:
                self.leave(medicine_q_PHC2)
                exit_time1 = env.now()
                opd_q_waiting_time_PHC2.append(exit_time1 - entry_time1)  # stores waiting time in the queue
                yield self.hold(t_doc)
                self.release(doc_OPD_PHC2)
                yield self.request(ipd_nurse_PHC2)
                yield self.hold(t_nur)
                self.release(ipd_nurse_PHC2)  # delivery nurse and delivery beds are released simultaneoulsy
                yield self.request(delivery_bed_PHC2)
                yield self.hold(t_bed)
                self.release(delivery_bed_PHC2)
                yield self.request(in_beds_PHC2)
                t_bed1 = sim.Uniform(240, 1440).sample()
                yield self.hold(t_bed1)
                ipd_bed_time_PHC2 += t_bed1


class Lab_PHC2(sim.Component):

    def process(self):
        global lab_q_PHC2
        global lab_technician_PHC2
        global lab_time_PHC2
        global lab_q_waiting_time_PHC2
        global warmup_time
        global lab_count_PHC2
        global o_PHC2
        global warmup_time

        if env.now() <= warmup_time:
            self.enter(lab_q_PHC2)
            yield self.request(lab_technician_PHC2)
            self.leave(lab_q_PHC2)
            yp = (sim.Normal(3.456, .823).bounded_sample(2))
            y0 = yp
            yield self.hold(y0)
            self.release(lab_technician_PHC2)
        else:
            lab_count_PHC2 += 1
            self.enter(lab_q_PHC2)
            a0 = env.now()
            yield self.request(lab_technician_PHC2)
            self.leave(lab_q_PHC2)
            lab_q_waiting_time_PHC2.append(env.now() - a0)
            f1 = env.now()
            yp = (sim.Normal(3.456, .823).bounded_sample(2))
            y0 = yp
            yield self.hold(y0)
            self.release(lab_technician_PHC2)
            f2 = env.now()
            lab_time_PHC2 += f2 - f1
            o_PHC2 += 1


class IPD_PatientGenerator_PHC2(sim.Component):
    global IPD1_iat_PHC2
    global warmup_time
    global warmup_time
    IPD_List_PHC2 = {}  # log of all the IPD patients stored here
    patient_count_PHC2 = 0
    p_count_PHC2 = 0  # log of patients in each replication

    def process(self):
        global days_PHC2
        M = 0
        while True:
            if env.now() <= warmup_time:
                pass
            else:
                IPD_PatientGenerator_PHC2.patient_count_PHC2 += 1
                IPD_PatientGenerator_PHC2.p_count_PHC2 += 1
            self.registration_time = env.now()
            self.id = IPD_PatientGenerator_PHC2.patient_count_PHC2
            self.age = round(random.normalvariate(35, 8))
            self.sex = random.choice(["Male", "Female"])
            IPD_PatientGenerator_PHC2.IPD_List_PHC2[self.id] = [self.registration_time, self.id, self.age, self.sex]
            if 0 < (self.registration_time - M * 1440) < 480:
                IPD_with_doc_PHC2(urgent=True)
            else:
                IPD_no_doc_PHC2(urgent=True)
            self.hold_time_1 = sim.Exponential(IPD1_iat_PHC2).sample()
            yield self.hold(self.hold_time_1)
            M = int(env.now() / 1440)


class IPD_no_doc_PHC2(sim.Component):

    def process(self):
        global MO_ipd_PHC2
        global ipd_nurse_PHC2
        global in_beds_PHC2
        global ipd_nurse_time_PHC2
        global warmup_time
        global ipd_bed_time_PHC2
        global ipd_nurse_time_PHC2
        global medicine_q_PHC2
        global ipd_MO_time_PHC2
        global warmup_time

        if env.now() <= warmup_time:

            yield self.request(in_beds_PHC2, ipd_nurse_PHC2)
            temp = sim.Uniform(30, 60, 'minutes').sample()
            yield self.hold(temp)
            self.release(ipd_nurse_PHC2)
            yield self.hold(sim.Triangular(60, 360, 180, 'minutes').bounded_sample(0))
            self.release(in_beds_PHC2)
        else:
            t_bed = sim.Triangular(60, 360, 180, 'minutes').sample()
            t_nurse = sim.Uniform(30, 60, 'minutes').sample()
            yield self.request(in_beds_PHC2, ipd_nurse_PHC2)
            yield self.hold(t_nurse)
            self.release(ipd_nurse_PHC2)
            yield self.hold(t_bed)
            self.release(in_beds_PHC2)
            ipd_bed_time_PHC2 += t_bed
            ipd_nurse_time_PHC2 += t_nurse


class IPD_with_doc_PHC2(sim.Component):

    def process(self):
        global MO_ipd_PHC2
        global ipd_nurse_PHC2
        global in_beds_PHC2
        global MO_ipd_time_PHC2
        global ipd_nurse_time_PHC2
        global warmup_time
        global ipd_bed_time_PHC2
        global ipd_nurse_time_PHC2
        global emergency_refer_PHC2
        global medicine_q_PHC2
        global ipd_MO_time_PHC2
        global opd_q_waiting_time_PHC2
        global phc1_doc_time_PHC2
        global medicine_cons_time_PHC2
        global warmup_time

        if env.now() <= warmup_time:
            self.enter_at_head(medicine_q_PHC2)
            yield self.request(doc_OPD_PHC2, fail_delay=20)
            doc_time = round(sim.Uniform(10, 30, 'minutes').sample())
            if self.failed():
                self.leave(medicine_q_PHC2)
                yield self.request(ipd_nurse_PHC2)
                temp = sim.Uniform(30, 60, 'minutes').sample()
                yield self.hold(temp)
                self.release(ipd_nurse_PHC2)
                yield self.request(doc_OPD_PHC2)
                yield self.hold(doc_time)
                self.release(doc_OPD_PHC2)
                yield self.request(in_beds_PHC2)
                yield self.hold(sim.Triangular(60, 360, 180, 'minutes').bounded_sample(0))
                self.release(in_beds_PHC2)
            else:
                self.leave(medicine_q_PHC2)
                yield self.hold(doc_time)
                self.release(doc_OPD_PHC2)
                yield self.request(in_beds_PHC2, ipd_nurse_PHC2)
                temp = sim.Uniform(30, 60, 'minutes').sample()
                yield self.hold(temp)
                self.release(ipd_nurse_PHC2)
                yield self.hold(sim.Triangular(60, 360, 180, 'minutes').bounded_sample(0))
                self.release(in_beds_PHC2)
        else:
            self.enter_at_head(medicine_q_PHC2)
            entry_time2 = env.now()
            yield self.request(doc_OPD_PHC2, fail_delay=20)
            doc_time = sim.Uniform(10, 30, 'minutes').sample()
            t_bed = sim.Triangular(60, 360, 180, 'minutes').sample()
            t_nurse = sim.Uniform(30, 60, 'minutes').sample()
            phc1_doc_time_PHC2 += doc_time
            medicine_cons_time_PHC2 += doc_time
            if self.failed():
                self.leave(medicine_q_PHC2)
                exit_time2 = env.now()
                opd_q_waiting_time_PHC2.append(exit_time2 - entry_time2)  # stores waiting time in the queue
                yield self.request(ipd_nurse_PHC2)
                yield self.hold(t_nurse)
                self.release(ipd_nurse_PHC2)
                yield self.request(doc_OPD_PHC2)
                yield self.hold(doc_time)
                self.release(doc_OPD_PHC2)
                yield self.request(in_beds_PHC2)
                yield self.hold(t_bed)
                self.release(in_beds_PHC2)
                ipd_bed_time_PHC2 += t_bed
                ipd_MO_time_PHC2 += doc_time
                ipd_nurse_time_PHC2 += t_nurse
            else:
                self.leave(medicine_q_PHC2)
                exit_time3 = env.now()
                opd_q_waiting_time_PHC2.append(exit_time3 - entry_time2)  # stores waiting time in the queue
                yield self.hold(doc_time)
                self.release(doc_OPD_PHC2)
                yield self.request(in_beds_PHC2, ipd_nurse_PHC2)
                yield self.hold(t_nurse)
                self.release(ipd_nurse_PHC2)
                yield self.hold(t_bed)
                self.release(in_beds_PHC2)
                ipd_bed_time_PHC2 += t_bed
                ipd_MO_time_PHC2 += doc_time
                ipd_nurse_time_PHC2 += t_nurse


class ANC_PHC2(sim.Component):
    global ANC_iat_PHC2
    global days_PHC2
    days_PHC2 = 0
    env = sim.Environment()
    No_of_shifts_PHC2 = 0  # tracks number of shifts completed during the simulation time
    No_of_days_PHC2 = 0
    ANC_List_PHC2 = {}
    anc_count_PHC2 = 0
    ANC_p_count_PHC2 = 0

    def process(self):

        global days_PHC2
        global warmup_time

        while True:  # condition to run simulation for 8 hour shifts
            x = env.now() - 1440 * days_PHC2
            if 0 <= x < 480:
                ANC_PHC2.anc_count_PHC2 += 1  # counts overall patients throghout simulation
                ANC_PHC2.ANC_p_count_PHC2 += 1  # counts patients in each replication
                id = ANC_PHC2.anc_count_PHC2
                age = 223
                day_of_registration = ANC_PHC2.No_of_days_PHC2
                visit = 1
                x0 = round(env.now())
                x1 = x0 + 14 * 7 * 24 * 60
                x2 = x0 + 20 * 7 * 24 * 60
                x3 = x0 + 24 * 7 * 24 * 60
                scheduled_visits = [[0], [0], [0], [0]]
                scheduled_visits[0] = x0
                scheduled_visits[1] = x1
                scheduled_visits[2] = x2
                scheduled_visits[3] = x3
                dic = {"ID": id, "Age": age, "Visit Number": visit, "Registration day": day_of_registration,
                       "Scheduled Visit": scheduled_visits}
                ANC_PHC2.ANC_List_PHC2[id] = dic
                ANC_Checkup_PHC2()
                ANC_followup_PHC2(at=ANC_PHC2.ANC_List_PHC2[id]["Scheduled Visit"][1])
                ANC_followup_PHC2(at=ANC_PHC2.ANC_List_PHC2[id]["Scheduled Visit"][2])
                ANC_followup_PHC2(at=ANC_PHC2.ANC_List_PHC2[id]["Scheduled Visit"][3])
                hold_time = sim.Exponential(ANC_iat_PHC2).sample()
                yield self.hold(hold_time)
            else:
                yield self.hold(960)
                days_PHC2 = int(env.now() / 1440)  # holds simulation for 2 shifts


class ANC_Checkup_PHC2(sim.Component):
    anc_checkup_count_PHC2 = 0

    def process(self):

        global warmup_time
        global ipd_nurse_PHC2
        global delivery_nurse_time_PHC2
        global lab_q_PHC2
        global lab_technician_PHC2
        global lab_time_PHC2
        global lab_q_waiting_time_PHC2
        global warmup_time
        global lab_count_PHC2
        global warmup_time

        if env.now() <= warmup_time:
            yield self.request(ipd_nurse_PHC2)
            temp = sim.Triangular(8, 20.6, 12.3).sample()
            yield self.hold(temp)  # time taken from a study on ANC visits in Tanzania
            self.release(ipd_nurse_PHC2)
            self.enter(lab_q_PHC2)
            yield self.request(lab_technician_PHC2)
            self.leave(lab_q_PHC2)
            yp = (sim.Normal(5, 1).bounded_sample())
            y0 = yp
            yield self.hold(y0)
            self.release(lab_technician_PHC2)
        else:
            ANC_Checkup_PHC2.anc_checkup_count_PHC2 += 1
            yield self.request(ipd_nurse_PHC2)
            temp = sim.Triangular(8, 20.6, 12.3).sample()
            delivery_nurse_time_PHC2 += temp
            yield self.hold(temp)  # time taken from a study on ANC visits in Tanzania
            self.release(ipd_nurse_PHC2)
            lab_count_PHC2 += 1
            # changed here
            a0 = env.now()
            self.enter(lab_q_PHC2)
            yield self.request(lab_technician_PHC2)
            self.leave(lab_q_PHC2)
            lab_q_waiting_time_PHC2.append(env.now() - a0)
            yp = (sim.Normal(5, 1).bounded_sample())
            y0 = yp
            yield self.hold(y0)
            self.release(lab_technician_PHC2)
            lab_time_PHC2 += y0


class ANC_followup_PHC2(sim.Component):
    followup_count = 0

    def process(self):

        global warmup_time
        global ipd_nurse_PHC2
        global q_ANC_PHC2
        global delivery_nurse_time_PHC2
        global lab_time_PHC2
        global warmup_time
        global lab_q_waiting_time_PHC2

        if env.now() <= warmup_time:
            for key in ANC_PHC2.ANC_List_PHC2:  # for identifying and updating ANC visit number
                x0 = env.now()
                x1 = ANC_PHC2.ANC_List_PHC2[key]["Scheduled Visit"][1]
                x2 = ANC_PHC2.ANC_List_PHC2[key]["Scheduled Visit"][2]
                x3 = ANC_PHC2.ANC_List_PHC2[key]["Scheduled Visit"][3]
                if 0 <= (x1 - x0) < 481:
                    ANC_PHC2.ANC_List_PHC2[key]["Scheduled Visit"][1] = float("inf")
                    ANC_PHC2.ANC_List_PHC2[key]["Visit Number"] = 2
                elif 0 <= (x2 - x0) < 481:
                    ANC_PHC2.ANC_List_PHC2[key]["Scheduled Visit"][2] = float("inf")
                    ANC_PHC2.ANC_List_PHC2[key]["Visit Number"] = 3
                elif 0 <= (x3 - x0) < 481:
                    ANC_PHC2.ANC_List_PHC2[key]["Scheduled Visit"][3] = float("inf")
                    ANC_PHC2.ANC_List_PHC2[key]["Visit Number"] = 4

            yield self.request(ipd_nurse_PHC2)
            temp = sim.Triangular(3.33, 13.16, 6.50).sample()
            yield self.hold(temp)
            self.release(ipd_nurse_PHC2)
            self.enter(lab_q_PHC2)
            yield self.request(lab_technician_PHC2)
            self.leave(lab_q_PHC2)
            yp = (sim.Normal(3.456, .823).bounded_sample(2))
            y0 = yp
            yield self.hold(y0)
            self.release(lab_technician_PHC2)

        else:
            for key in ANC_PHC2.ANC_List_PHC2:  # for identifying and updating ANC visit number
                x0 = env.now()
                x1 = ANC_PHC2.ANC_List_PHC2[key]["Scheduled Visit"][1]
                x2 = ANC_PHC2.ANC_List_PHC2[key]["Scheduled Visit"][2]
                x3 = ANC_PHC2.ANC_List_PHC2[key]["Scheduled Visit"][3]
                if 0 <= (x1 - x0) < 481:
                    ANC_PHC2.ANC_List_PHC2[key]["Scheduled Visit"][1] = float("inf")
                    ANC_PHC2.ANC_List_PHC2[key]["Visit Number"] = 2
                elif 0 <= (x2 - x0) < 481:
                    ANC_PHC2.ANC_List_PHC2[key]["Scheduled Visit"][2] = float("inf")
                    ANC_PHC2.ANC_List_PHC2[key]["Visit Number"] = 3
                elif 0 <= (x3 - x0) < 481:
                    ANC_PHC2.ANC_List_PHC2[key]["Scheduled Visit"][3] = float("inf")
                    ANC_PHC2.ANC_List_PHC2[key]["Visit Number"] = 4

            yield self.request(ipd_nurse_PHC2)
            temp = sim.Triangular(3.33, 13.16, 6.50).sample()
            yield self.hold(temp)
            delivery_nurse_time_PHC2 += temp
            self.release(ipd_nurse_PHC2)
            a0 = env.now()
            self.enter(lab_q_PHC2)
            yield self.request(lab_technician_PHC2)
            self.leave(lab_q_PHC2)
            lab_q_waiting_time_PHC2.append(env.now() - a0)
            yp = (sim.Normal(3.456, .823).bounded_sample(2))
            y0 = yp
            yield self.hold(y0)
            self.release(lab_technician_PHC2)
            lab_time_PHC2 += y0


class CovidGenerator_PHC2(sim.Component):

    def process(self):
        global d1_PHC2
        global warmup_time
        global warmup_time
        global covid_iat_PHC2
        global j

        while True:
            if env.now() < warmup_time:
                if 0 <= (env.now() - d1_PHC2 * 1440) < 480:
                    covid_PHC2()
                    yield self.hold(1440 / 3)
                    d1_PHC2 = int(env.now() / 1440)
                else:
                    yield self.hold(960)
                    d1_PHC2 = int(env.now() / 1440)
            else:
                a = phc_covid_iat[j]

                if 0 <= (env.now() - d1_PHC2 * 1440) < 480:
                    covid_PHC2()
                    yield self.hold(sim.Exponential(a).sample())
                    d1_PHC2 = int(env.now() / 1440)
                else:
                    yield self.hold(960)
                    d1_PHC2 = int(env.now() / 1440)


class covid_PHC2(sim.Component):

    def process(self):

        global home_refer_PHC2
        global chc_refer_PHC2
        global dh_refer_PHC2
        global isolation_ward_refer_PHC2
        global covid_patient_time_PHC2
        global covid_count_PHC2
        global warmup_time
        global ipd_nurse_PHC2
        global ipd_nurse_time_PHC2
        global doc_OPD_PHC2
        global MO_covid_time_PHC2
        global phc2chc_count_PHC2
        global warmup_time
        global home_isolation_PHC2

        global ICU_oxygen
        global phc2_to_cc_severe_case
        global phc2_to_cc_dist
        global phc2_2_cc

        if env.now() < warmup_time:
            covid_nurse_PHC2()
            covid_lab_PHC2()
            x = random.randint(0, 1000)
            if x <= 940:
                a = random.randint(0, 100)
                if a > 90:
                    cc_isolation()
            elif 940 < x <= 980:
                pass
            # CovidCare_chc2()
            else:
                pass
                # SevereCase()
        else:
            covid_count_PHC2 += 1
            covid_nurse_PHC2()
            covid_lab_PHC2()
            x = random.randint(0, 1000)
            if x <= 940:  # mild cases
                home_refer_PHC2 += 1
                a = random.randint(0, 100)
                if a >= 90:  # 10 % for institutional quarantine
                    isolation_ward_refer_PHC2 += 1
                    cc_isolation()
                else:
                    home_isolation_PHC2 += 1
            elif 940 < x <= 980:  # moderate cases
                chc_refer_PHC2 += 1
                phc2chc_count_PHC2 += 1
                CovidCare_chc2()
            else:  # severe case
                s = random.randint(0, 100)
                if s < 50:  # Type f patients
                    if ICU_oxygen.available_quantity() < 1:  # checks if there is a vacant bed in DH
                        phc2_to_cc_severe_case += 1
                        phc2_to_cc_dist.append(phc2_2_cc)
                        cc_Type_F()  # patient refered tpo CC
                    else:
                        DH_SevereTypeF()
                        dh_refer_PHC2 += 1  # Severe cases
                elif 50 <= s <= 75:  # E type patients
                    if ICU_ventilator.available_quantity() < 1:  # checks if there is a vacant bed in DH
                        cc_ICU_ward_TypeE()
                        phc2_to_cc_severe_case += 1
                    else:
                        DH_SevereTypeE()
                        dh_refer_PHC2 += 1  # Severe cases
                else:  # Type d patients
                    if ICU_ventilator.available_quantity() < 1:  # checks if there is a vacant bed in DH
                        cc_ventilator_TypeD()
                        phc2_to_cc_severe_case += 1
                    else:
                        dh_refer_PHC2 += 1  # Severe cases
                        DH_SevereTypeD()


class covid_nurse_PHC2(sim.Component):
    global lab_covidcount_PHC2

    def process(self):

        global warmup_time
        global ipd_nurse_PHC2
        global ipd_nurse_time_PHC2
        global lab_covidcount_PHC2
        global warmup_time

        if env.now() <= warmup_time:
            yield self.request(ipd_nurse_PHC2)
            yield self.hold(sim.Uniform(2, 3).sample())
            self.release(ipd_nurse_PHC2)
        else:
            lab_covidcount_PHC2 += 1
            yield self.request(ipd_nurse_PHC2)
            t = sim.Uniform(2, 3).sample()
            yield self.hold(t)
            ipd_nurse_time_PHC2 += t
            self.release(ipd_nurse_PHC2)


class covid_lab_PHC2(sim.Component):

    def process(self):

        global lab_technician_PHC2
        global lab_time_PHC2
        global lab_q_waiting_time_PHC2
        global warmup_time
        global lab_covidcount_PHC2
        global warmup_time

        if env.now() <= warmup_time:
            yield self.request(lab_technician_PHC2)
            yield self.hold(sim.Uniform(1, 2).sample())
            self.release(lab_technician_PHC2)
        else:
            lab_covidcount_PHC2 += 1
            yield self.request(lab_technician_PHC2)
            t = sim.Uniform(1, 2).sample()
            yield self.hold(t)
            lab_time_PHC2 += t
            self.release(lab_technician_PHC2)
            x = random.randint(0, 100)
            if x < 33:  # confirmed posiive
                covid_doc_PHC2()
            elif 33 < x < 67:  # symptomatic negative, retesting
                retesting_PHC2()
            else:
                Pharmacy_PHC2()


class retesting_PHC2(sim.Component):

    def process(self):

        global retesting_count_PHC2
        global warmup_time
        global warmup_time

        if env.now() <= warmup_time:
            yield self.hold(1440)
            covid_doc_PHC2()
        else:
            retesting_count_PHC2 += 1
            yield self.hold(1440)
            covid_doc_PHC2()


class covid_doc_PHC2(sim.Component):

    def process(self):
        global MO_covid_time_PHC2
        global doc_OPD_PHC2
        global warmup_time
        global covid_q_PHC2
        global covid_patient_time_PHC2
        global warmup_time
        global medicine_cons_time_PHC2

        if env.now() <= warmup_time:
            self.enter(covid_q_PHC2)
            yield self.request(doc_OPD_PHC2)
            self.leave(covid_q_PHC2)
            yield self.hold(sim.Uniform(3, 6).sample())
            self.release(doc_OPD_PHC2)
        else:
            in_time = env.now()
            self.enter(covid_q_PHC2)
            yield self.request(doc_OPD_PHC2)
            self.leave(covid_q_PHC2)
            t = sim.Uniform(3, 6).sample()
            yield self.hold(t)
            MO_covid_time_PHC2 += t
            medicine_cons_time_PHC2 += t
            self.release(doc_OPD_PHC2)
            covid_patient_time_PHC2 += env.now() - in_time


global l3  # temp lab count
l3 = 0
global o_PHC3  # temp opd count
o_PHC3 = 0


# PHC 3
class PatientGenerator_PHC3(sim.Component):
    global shift_PHC3
    shift_PHC3 = 0
    No_of_days_PHC3 = 0

    total_OPD_patients_PHC3 = 0

    def process(self):

        global env
        global warmup_time
        global opd_iat_PHC3
        global days_PHC3
        global medicine_cons_time_PHC3
        global shift_PHC3
        global phc1_doc_time_PHC3

        self.sim_time_PHC3 = 0  # local variable defined for dividing each day into shits
        self.z_PHC3 = 0
        self.admin_count_PHC3 = 0
        k_PHC3 = 0

        while self.z_PHC3 % 3 == 0:  # condition to run simulation for 8 hour shifts
            PatientGenerator_PHC3.No_of_days_PHC3 += 1  # class variable to track number of days passed
            while self.sim_time_PHC3 < 360:  # from morning 8 am to afternoon 2 pm (in minutes)
                if env.now() <= warmup_time:
                    pass
                else:
                    OPD_PHC3()
                o = sim.Exponential(opd_iat_PHC3).sample()
                yield self.hold(o)
                self.sim_time_PHC3 += o

            while 360 <= self.sim_time_PHC3 < 480:  # condition for admin work after opd hours are over
                k_PHC3 = int(sim.Normal(100, 20).bounded_sample(60, 140))
                """For sensitivity analysis. Admin work added to staff nurse rather than doctor"""
                if env.now() <= warmup_time:
                    pass
                else:
                    medicine_cons_time_PHC3 += k_PHC3  # conatns all doctor service times
                    phc1_doc_time_PHC3 += k_PHC3
                yield self.hold(120)
                self.sim_time_PHC3 = 481
            self.z_PHC3 += 3
            self.sim_time_PHC3 = 0
            # PatientGenerator1.No_of_shifts += 3
            yield self.hold(959)  # holds simulation for 2 shifts


class OPD_PHC3(sim.Component):
    Patient_log_PHC3 = {}

    def setup(self):

        self.dic = {}  # local dictionary for temporarily   storing generated patients
        # with attributes
        self.time_of_visit = [[0], [0], [0]]  # initializing for assigning time of visits
        self.regis_time = round(env.now())  # registration time is the current simulation time
        self.id = PatientGenerator_PHC3.total_OPD_patients_PHC3  # patient count is patient id
        self.age_random = random.randint(0, 1000)  # assigning age to population based on census 2011 gurgaon
        if self.age_random <= 578:
            self.age = random.randint(0, 30)
        else:
            self.age = random.randint(31, 100)
        self.sex = random.choice(["male", "female"])  # Equal probability of male and female patient
        # require lab tests
        self.lab_required = random.choice(["True", "False"])  # Considering nearly half of all the patients
        self.radiography_required = random.choice(["True", "False"])
        y = random.randint(0, 999)
        self.consultation = random.choice([y])  # for medicine, gynea, pead, denta
        self.visits_assigned = random.randint(1, 10)  # assigning number of visits visits
        self.dic = {"ID": self.id, "Age": self.age, "Sex": self.sex, "Lab": self.lab_required,
                    "Registration_Time": self.regis_time, "No_of_visits": self.visits_assigned,
                    "Time_of_visit": self.time_of_visit, "Radiography": self.radiography_required,
                    "Consultation": self.consultation}
        OPD_PHC3.Patient_log_PHC3[PatientGenerator_PHC3.total_OPD_patients_PHC3] = self.dic

        self.process()

    def process(self):

        global c3
        global medicine_q_PHC3
        global doc_OPD_PHC3
        global opd_ser_time_mean_PHC3
        global opd_ser_time_sd_PHC3
        global medicine_count_PHC3
        global medicine_cons_time_PHC3
        global opd_q_waiting_time_PHC3
        global ncd_count_PHC3
        global ncd_nurse_PHC3
        global ncd_time_PHC3
        global warmup_time
        global l3
        global phc1_doc_time_PHC3

        if env.now() <= warmup_time:
            p = random.randint(0, 10)
            if p < 2:
                COVID_OPD_PHC3()
            if OPD_PHC3.Patient_log_PHC3[PatientGenerator_PHC3.total_OPD_patients_PHC3]["Age"] > 30:
                yield self.request(ncd_nurse_PHC3)
                ncd_service = sim.Uniform(2, 5).sample()
                yield self.hold(ncd_service)
            self.enter(medicine_q_PHC3)
            yield self.request(doc_OPD_PHC3)
            self.leave(medicine_q_PHC3)
            o = sim.Normal(opd_ser_time_mean_PHC3, opd_ser_time_sd_PHC3).bounded_sample(0.3)
            yield self.hold(o)
            self.release(doc_OPD_PHC3)
            if OPD_PHC3.Patient_log_PHC3[PatientGenerator_PHC3.total_OPD_patients_PHC3]["Lab"] == "True":
                Lab_PHC3()
            Pharmacy_PHC3()
        else:
            l3 += 1
            medicine_count_PHC3 += 1
            p = random.randint(0, 10)
            if p < 2:
                COVID_OPD_PHC3()
            if OPD_PHC3.Patient_log_PHC3[PatientGenerator_PHC3.total_OPD_patients_PHC3]["Age"] > 30:
                ncd_count_PHC3 += 1
                yield self.request(ncd_nurse_PHC3)
                ncd_service = sim.Uniform(2, 5).sample()
                yield self.hold(ncd_service)
                ncd_time_PHC3 += ncd_service
            # doctor opd starts from here
            entry_time = env.now()
            self.enter(medicine_q_PHC3)
            yield self.request(doc_OPD_PHC3)
            self.leave(medicine_q_PHC3)
            exit_time = env.now()
            opd_q_waiting_time_PHC3.append(exit_time - entry_time)  # stores waiting time in the queue
            o = sim.Normal(opd_ser_time_mean_PHC3, opd_ser_time_sd_PHC3).bounded_sample(0.3)
            yield self.hold(o)
            phc1_doc_time_PHC3 += o
            medicine_cons_time_PHC3 += o
            self.release(doc_OPD_PHC3)
            # lab starts from here
            t = random.randint(0, 1000)
            # changed here
            if OPD_PHC3.Patient_log_PHC3[PatientGenerator_PHC3.total_OPD_patients_PHC3]["Lab"] == "True":
                Lab_PHC3()
            Pharmacy_PHC3()


class COVID_OPD_PHC3(sim.Component):

    def process(self):

        global ipd_nurse_PHC3
        global delivery_nurse_time_PHC3

        if env.now() <= warmup_time:
            yield self.request(ipd_nurse_PHC3)
            h1 = sim.Uniform(5, 10).sample()
            yield self.hold(h1)
            self.release(ipd_nurse_PHC3)
            OPD_covidtest_PHC3()
            yield self.hold(sim.Uniform(15, 30).sample())  # patient waits for the result
        else:
            yield self.request(ipd_nurse_PHC3)
            h1 = sim.Uniform(5, 10).sample()
            yield self.hold(h1)
            self.release(ipd_nurse_PHC3)
            OPD_covidtest_PHC3()
            delivery_nurse_time_PHC3 += h1
            yield self.hold(sim.Uniform(15, 30).sample())


class OPD_covidtest_PHC3(sim.Component):

    def process(self):
        global lab_covidcount_PHC3
        global lab_technician_PHC3
        global lab_time_PHC3
        global warmup_time

        if env.now() <= warmup_time:
            yield self.request(lab_technician_PHC3)
            t = sim.Uniform(1, 2).sample()
            yield self.hold(t)
            self.release(lab_technician_PHC3)
        else:
            lab_covidcount_PHC3 += 1
            yield self.request(lab_technician_PHC3)
            t = sim.Uniform(1, 2).sample()
            yield self.hold(t)
            lab_time_PHC3 += t
            self.release(lab_technician_PHC3)


class Pharmacy_PHC3(sim.Component):

    def process(self):

        global pharmacist_PHC3
        global pharmacy_time_PHC3
        global pharmacy_q_PHC3
        global pharmacy_q_waiting_time_PHC3
        global warmup_time
        global pharmacy_count_PHC3

        if env.now() < warmup_time:
            self.enter(pharmacy_q_PHC3)
            yield self.request(pharmacist_PHC3)
            self.leave(pharmacy_q_PHC3)
            # service_time = sim.Uniform(1, 2.5).sample()
            service_time = sim.Normal(2.083, 0.72).bounded_sample(.67)
            yield self.hold(service_time)
            self.release(pharmacist_PHC3)
        else:
            pharmacy_count_PHC3 += 1
            e1 = env.now()
            self.enter(pharmacy_q_PHC3)
            yield self.request((pharmacist_PHC3, 1))
            self.leave(pharmacy_q_PHC3)
            pharmacy_q_waiting_time_PHC3.append(env.now() - e1)
            service_time = sim.Normal(2.083, 0.72).bounded_sample(.67)
            yield self.hold(service_time)
            self.release((pharmacist_PHC3, 1))
            pharmacy_time_PHC3 += service_time


class Delivery_patient_generator_PHC3(sim.Component):
    Delivery_list = {}

    def process(self):
        global delivery_iat_PHC3
        global warmup_time
        global delivery_count_PHC3
        global days_PHC3
        global childbirth_count_PHC3
        global N_PHC3

        while True:
            if env.now() <= warmup_time:
                pass
            else:
                childbirth_count_PHC3 += 1
                self.registration_time = round(env.now())
                if 0 < (self.registration_time - N_PHC3 * 1440) < 480:
                    Delivery_with_doctor_PHC3(urgent=True)  # sets priority
                else:
                    Delivery_no_doc_PHC3(urgent=True)
            self.hold_time = sim.Exponential(delivery_iat_PHC3).sample()
            yield self.hold(self.hold_time)
            N_PHC3 = int(env.now() / 1440)


class Delivery_no_doc_PHC3(sim.Component):

    def process(self):
        global ipd_nurse_PHC3
        global ipd_nurse_PHC3
        global doc_OPD_PHC3
        global delivery_bed_PHC3
        global warmup_time
        global e_beds_PHC3
        global ipd_nurse_time_PHC3
        global MO_del_time_PHC3
        global in_beds_PHC3
        global delivery_nurse_time_PHC3
        global inpatient_del_count_PHC3
        global delivery_count_PHC3
        global emergency_bed_time_PHC3
        global ipd_bed_time_PHC3
        global emergency_nurse_time_PHC3
        global referred_PHC3
        global fail_count_PHC3

        if env.now() <= warmup_time:
            t_nurse = sim.Uniform(120, 240, 'minutes').sample()
            t_bed = sim.Uniform(360, 600).sample()
            yield self.request(ipd_nurse_PHC3)
            yield self.hold(t_nurse)
            self.release(ipd_nurse_PHC3)
            yield self.request(delivery_bed_PHC3, fail_delay=120)
            if self.failed():
                pass
            else:
                yield self.hold(t_bed)
                self.release(delivery_bed_PHC3)
                yield self.request(in_beds_PHC3)
                yield self.hold(sim.Uniform(240, 1440, 'minutes').bounded_sample(0))
                self.release(in_beds_PHC3)
        else:
            delivery_count_PHC3 += 1
            t_bed = sim.Uniform(360, 600).sample()  # delivery bed, nurse time
            t_nur = sim.Uniform(120, 240).sample()
            delivery_nurse_time_PHC3 += t_nur
            yield self.request(ipd_nurse_PHC3)
            yield self.hold(t_nur)
            self.release(ipd_nurse_PHC3)  # delivery nurse and delivery beds are released simultaneoulsy
            yield self.request(delivery_bed_PHC3, fail_delay=120)
            if self.failed():
                fail_count_PHC3 += 1
                delivery_count_PHC3 -= 1
                pass
            else:
                yield self.hold(t_bed)
                self.release(delivery_bed_PHC3)
                yield self.request(in_beds_PHC3)
                t_bed1 = sim.Uniform(240, 1440).sample()
                yield self.hold(t_bed1)
                ipd_bed_time_PHC3 += t_bed1


class Delivery_with_doctor_PHC3(sim.Component):

    def process(self):
        global ipd_nurse_PHC3
        global ipd_nurse_PHC3
        global doc_OPD_PHC3
        global delivery_bed_PHC3
        global warmup_time
        global e_beds_PHC3
        global ipd_nurse_time_PHC3
        global MO_del_time_PHC3
        global in_beds_PHC3
        global delivery_nurse_time_PHC3
        global inpatient_del_count_PHC3
        global delivery_count_PHC3
        global emergency_bed_time_PHC3
        global ipd_bed_time_PHC3
        global emergency_nurse_time_PHC3
        global referred_PHC3
        global fail_count_PHC3
        global opd_q_waiting_time_PHC3
        global phc1_doc_time_PHC3
        global medicine_cons_time_PHC3
        global medicine_q_PHC3

        if env.now() <= warmup_time:
            t_doc = sim.Uniform(30, 60).sample()
            t_bed = sim.Uniform(240, 360).sample()
            t_nurse = sim.Uniform(120, 240, 'minutes').sample()
            self.enter_at_head(medicine_q_PHC3)
            yield self.request(doc_OPD_PHC3, fail_delay=20)
            if self.failed():  # if doctor is busy staff nurse takes care
                self.leave(medicine_q_PHC3)
                yield self.request(ipd_nurse_PHC3)
                yield self.hold(t_nurse)
                self.release(ipd_nurse_PHC3)
                yield self.request(doc_OPD_PHC3)
                yield self.hold(t_doc)
                self.release(doc_OPD_PHC3)
                self.release(delivery_bed_PHC3)
                yield self.request(delivery_bed_PHC3, fail_delay=120)
                if self.failed():
                    pass
                else:
                    yield self.hold(sim.Uniform(6 * 60, 10 * 60, 'minutes').sample())
                    self.release(delivery_bed_PHC3)
                    yield self.request(in_beds_PHC3)
                    yield self.hold(sim.Uniform(240, 1440, 'minutes').sample())
                    self.release()
            else:
                self.leave(medicine_q_PHC3)
                yield self.hold(t_doc)
                self.release(doc_OPD_PHC3)
                yield self.request(ipd_nurse_PHC3)
                yield self.hold(t_nurse)
                self.release(ipd_nurse_PHC3)
                yield self.request(delivery_bed_PHC3)
                yield self.hold(sim.Uniform(6 * 60, 10 * 60, 'minutes').sample())
                self.release(delivery_bed_PHC3)
                yield self.request(in_beds_PHC3)
                yield self.hold(sim.Uniform(240, 1440, 'minutes').bounded_sample(0))  # holding patient for min 4 hours
                # to 48 hours
                self.release(in_beds_PHC3)
        else:
            delivery_count_PHC3 += 1
            entry_time1 = env.now()
            self.enter_at_head(medicine_q_PHC3)
            yield self.request(doc_OPD_PHC3, fail_delay=20)
            t_doc = sim.Uniform(30, 60).sample()
            t_bed = sim.Uniform(360, 600).sample()  # delivery bed, nurse time
            t_nur = sim.Uniform(120, 240).sample()
            delivery_nurse_time_PHC3 += t_nur
            phc1_doc_time_PHC3 += t_doc
            MO_del_time_PHC3 += t_doc  # changed here
            medicine_cons_time_PHC3 += t_doc
            if self.failed():  # if doctor is busy staff nurse takes care
                self.leave(medicine_q_PHC3)
                exit_time1 = env.now()
                opd_q_waiting_time_PHC3.append(exit_time1 - entry_time1)  # stores waiting time in the queue
                yield self.request(ipd_nurse_PHC3)
                yield self.hold(t_nur)
                self.release(ipd_nurse_PHC3)
                # changed here
                yield self.request(doc_OPD_PHC3)
                yield self.hold(t_doc)
                self.release(doc_OPD_PHC3)
                yield self.request(delivery_bed_PHC3, fail_delay=120)
                if self.failed():
                    fail_count_PHC3 += 1
                    delivery_count_PHC3 -= 1
                else:
                    yield self.hold(t_bed)
                    self.release(delivery_bed_PHC3)
                    # after delivery patient shifts to IPD and requests nurse and inpatient bed
                    # changed here, removed ipd nurse
                    yield self.request(in_beds_PHC3)
                    # t_n = sim.Uniform(20, 30).sample()          # inpatient nurse time in ipd after delivery
                    t_bed2 = sim.Uniform(240, 1440).sample()  # inpatient beds post delivery stay
                    # yield self.hold(t_n)
                    # self.release(ipd_nurse1)
                    # ipd_nurse_time1 += t_n
                    yield self.hold(t_bed2)
                    ipd_bed_time_PHC3 += t_bed2
            else:
                self.leave(medicine_q_PHC3)
                exit_time1 = env.now()
                opd_q_waiting_time_PHC3.append(exit_time1 - entry_time1)  # stores waiting time in the queue
                yield self.hold(t_doc)
                self.release(doc_OPD_PHC3)
                yield self.request(ipd_nurse_PHC3)
                yield self.hold(t_nur)
                self.release(ipd_nurse_PHC3)  # delivery nurse and delivery beds are released simultaneoulsy
                yield self.request(delivery_bed_PHC3)
                yield self.hold(t_bed)
                self.release(delivery_bed_PHC3)
                yield self.request(in_beds_PHC3)
                t_bed1 = sim.Uniform(240, 1440).sample()
                yield self.hold(t_bed1)
                ipd_bed_time_PHC3 += t_bed1


class Lab_PHC3(sim.Component):

    def process(self):
        global lab_q_PHC3
        global lab_technician_PHC3
        global lab_time_PHC3
        global lab_q_waiting_time_PHC3
        global warmup_time
        global lab_count_PHC3
        global o_PHC3

        if env.now() <= warmup_time:
            self.enter(lab_q_PHC3)
            yield self.request(lab_technician_PHC3)
            self.leave(lab_q_PHC3)
            yp = (sim.Normal(3.456, .823).bounded_sample(2))
            y0 = yp
            yield self.hold(y0)
            self.release(lab_technician_PHC3)
        else:
            lab_count_PHC3 += 1
            self.enter(lab_q_PHC3)
            a0 = env.now()
            yield self.request(lab_technician_PHC3)
            self.leave(lab_q_PHC3)
            lab_q_waiting_time_PHC3.append(env.now() - a0)
            f1 = env.now()
            yp = (sim.Normal(3.456, .823).bounded_sample(2))
            y0 = yp
            yield self.hold(y0)
            self.release(lab_technician_PHC3)
            f2 = env.now()
            lab_time_PHC3 += f2 - f1
            o_PHC3 += 1


class IPD_PatientGenerator_PHC3(sim.Component):
    global IPD1_iat_PHC3
    global warmup_time
    IPD_List_PHC3 = {}  # log of all the IPD patients stored here
    patient_count_PHC3 = 0
    p_count_PHC3 = 0  # log of patients in each replication

    def process(self):
        global days_PHC3
        M = 0
        while True:
            if env.now() <= warmup_time:
                pass
            else:
                IPD_PatientGenerator_PHC3.patient_count_PHC3 += 1
                IPD_PatientGenerator_PHC3.p_count_PHC3 += 1
            self.registration_time = env.now()
            self.id = IPD_PatientGenerator_PHC3.patient_count_PHC3
            self.age = round(random.normalvariate(35, 8))
            self.sex = random.choice(["Male", "Female"])
            IPD_PatientGenerator_PHC3.IPD_List_PHC3[self.id] = [self.registration_time, self.id, self.age, self.sex]
            if 0 < (self.registration_time - M * 1440) < 480:
                IPD_with_doc_PHC3(urgent=True)
            else:
                IPD_no_doc_PHC3(urgent=True)
            self.hold_time_1 = sim.Exponential(IPD1_iat_PHC3).sample()
            yield self.hold(self.hold_time_1)
            M = int(env.now() / 1440)


class IPD_no_doc_PHC3(sim.Component):

    def process(self):
        global MO_ipd_PHC3
        global ipd_nurse_PHC3
        global in_beds_PHC3
        global ipd_nurse_time_PHC3
        global warmup_time
        global ipd_bed_time_PHC3
        global ipd_nurse_time_PHC3
        global medicine_q_PHC3
        global ipd_MO_time_PHC3

        if env.now() <= warmup_time:

            yield self.request(in_beds_PHC3, ipd_nurse_PHC3)
            temp = sim.Uniform(30, 60, 'minutes').sample()
            yield self.hold(temp)
            self.release(ipd_nurse_PHC3)
            yield self.hold(sim.Triangular(60, 360, 180, 'minutes').bounded_sample(0))
            self.release(in_beds_PHC3)
        else:
            t_bed = sim.Triangular(60, 360, 180, 'minutes').sample()
            t_nurse = sim.Uniform(30, 60, 'minutes').sample()
            yield self.request(in_beds_PHC3, ipd_nurse_PHC3)
            yield self.hold(t_nurse)
            self.release(ipd_nurse_PHC3)
            yield self.hold(t_bed)
            self.release(in_beds_PHC3)
            ipd_bed_time_PHC3 += t_bed
            ipd_nurse_time_PHC3 += t_nurse


class IPD_with_doc_PHC3(sim.Component):

    def process(self):
        global MO_ipd_PHC3
        global ipd_nurse_PHC3
        global in_beds_PHC3
        global MO_ipd_time_PHC3
        global ipd_nurse_time_PHC3
        global warmup_time
        global ipd_bed_time_PHC3
        global ipd_nurse_time_PHC3
        global emergency_refer_PHC2
        global medicine_q_PHC3
        global ipd_MO_time_PHC3
        global opd_q_waiting_time_PHC3
        global phc1_doc_time_PHC3
        global medicine_cons_time_PHC3

        if env.now() <= warmup_time:
            self.enter_at_head(medicine_q_PHC3)
            yield self.request(doc_OPD_PHC3, fail_delay=20)
            doc_time = round(sim.Uniform(10, 30, 'minutes').sample())
            if self.failed():
                self.leave(medicine_q_PHC3)
                yield self.request(ipd_nurse_PHC3)
                temp = sim.Uniform(30, 60, 'minutes').sample()
                yield self.hold(temp)
                self.release(ipd_nurse_PHC3)
                yield self.request(doc_OPD_PHC3)
                yield self.hold(doc_time)
                self.release(doc_OPD_PHC3)
                yield self.request(in_beds_PHC3)
                yield self.hold(sim.Triangular(60, 360, 180, 'minutes').bounded_sample(0))
                self.release(in_beds_PHC3)
            else:
                self.leave(medicine_q_PHC3)
                yield self.hold(doc_time)
                self.release(doc_OPD_PHC3)
                yield self.request(in_beds_PHC3, ipd_nurse_PHC3)
                temp = sim.Uniform(30, 60, 'minutes').sample()
                yield self.hold(temp)
                self.release(ipd_nurse_PHC3)
                yield self.hold(sim.Triangular(60, 360, 180, 'minutes').bounded_sample(0))
                self.release(in_beds_PHC3)
        else:
            self.enter_at_head(medicine_q_PHC3)
            entry_time2 = env.now()
            yield self.request(doc_OPD_PHC3, fail_delay=20)
            doc_time = sim.Uniform(10, 30, 'minutes').sample()
            t_bed = sim.Triangular(60, 360, 180, 'minutes').sample()
            t_nurse = sim.Uniform(30, 60, 'minutes').sample()
            phc1_doc_time_PHC3 += doc_time
            medicine_cons_time_PHC3 += doc_time
            if self.failed():
                self.leave(medicine_q_PHC3)
                exit_time2 = env.now()
                opd_q_waiting_time_PHC3.append(exit_time2 - entry_time2)  # stores waiting time in the queue
                yield self.request(ipd_nurse_PHC3)
                yield self.hold(t_nurse)
                self.release(ipd_nurse_PHC3)
                yield self.request(doc_OPD_PHC3)
                yield self.hold(doc_time)
                self.release(doc_OPD_PHC3)
                yield self.request(in_beds_PHC3)
                yield self.hold(t_bed)
                self.release(in_beds_PHC3)
                ipd_bed_time_PHC3 += t_bed
                ipd_MO_time_PHC3 += doc_time
                ipd_nurse_time_PHC3 += t_nurse
            else:
                self.leave(medicine_q_PHC3)
                exit_time3 = env.now()
                opd_q_waiting_time_PHC3.append(exit_time3 - entry_time2)  # stores waiting time in the queue
                yield self.hold(doc_time)
                self.release(doc_OPD_PHC3)
                yield self.request(in_beds_PHC3, ipd_nurse_PHC3)
                yield self.hold(t_nurse)
                self.release(ipd_nurse_PHC3)
                yield self.hold(t_bed)
                self.release(in_beds_PHC3)
                ipd_bed_time_PHC3 += t_bed
                ipd_MO_time_PHC3 += doc_time
                ipd_nurse_time_PHC3 += t_nurse


class ANC_PHC3(sim.Component):
    global ANC_iat_PHC3
    global days_PHC3
    days_PHC3 = 0
    env = sim.Environment()
    No_of_shifts_PHC3 = 0  # tracks number of shifts completed during the simulation time
    No_of_days_PHC3 = 0
    ANC_List_PHC3 = {}
    anc_count_PHC3 = 0
    ANC_p_count_PHC3 = 0

    def process(self):

        global days_PHC3

        while True:  # condition to run simulation for 8 hour shifts
            x = env.now() - 1440 * days_PHC3
            if 0 <= x < 480:
                ANC_PHC3.anc_count_PHC3 += 1  # counts overall patients throghout simulation
                ANC_PHC3.ANC_p_count_PHC3 += 1  # counts patients in each replication
                id = ANC_PHC3.anc_count_PHC3
                age = 223
                day_of_registration = ANC_PHC3.No_of_days_PHC3
                visit = 1
                x0 = round(env.now())
                x1 = x0 + 14 * 7 * 24 * 60
                x2 = x0 + 20 * 7 * 24 * 60
                x3 = x0 + 24 * 7 * 24 * 60
                scheduled_visits = [[0], [0], [0], [0]]
                scheduled_visits[0] = x0
                scheduled_visits[1] = x1
                scheduled_visits[2] = x2
                scheduled_visits[3] = x3
                dic = {"ID": id, "Age": age, "Visit Number": visit, "Registration day": day_of_registration,
                       "Scheduled Visit": scheduled_visits}
                ANC_PHC3.ANC_List_PHC3[id] = dic
                ANC_Checkup_PHC3()
                ANC_followup_PHC3(at=ANC_PHC3.ANC_List_PHC3[id]["Scheduled Visit"][1])
                ANC_followup_PHC3(at=ANC_PHC3.ANC_List_PHC3[id]["Scheduled Visit"][2])
                ANC_followup_PHC3(at=ANC_PHC3.ANC_List_PHC3[id]["Scheduled Visit"][3])
                hold_time = sim.Exponential(ANC_iat_PHC3).sample()
                yield self.hold(hold_time)
            else:
                yield self.hold(960)
                days_PHC3 = int(env.now() / 1440)  # holds simulation for 2 shifts


class ANC_Checkup_PHC3(sim.Component):
    anc_checkup_count_PHC3 = 0

    def process(self):

        global warmup_time
        global ipd_nurse_PHC3
        global delivery_nurse_time_PHC3
        global lab_q_PHC3
        global lab_technician_PHC3
        global lab_time_PHC3
        global lab_q_waiting_time_PHC3
        global warmup_time
        global lab_count_PHC3

        if env.now() <= warmup_time:
            yield self.request(ipd_nurse_PHC3)
            temp = sim.Triangular(8, 20.6, 12.3).sample()
            yield self.hold(temp)  # time taken from a study on ANC visits in Tanzania
            self.release(ipd_nurse_PHC3)
            self.enter(lab_q_PHC3)
            yield self.request(lab_technician_PHC3)
            self.leave(lab_q_PHC3)
            yp = (sim.Normal(5, 1).bounded_sample())
            y0 = yp
            yield self.hold(y0)
            self.release(lab_technician_PHC3)
        else:
            ANC_Checkup_PHC3.anc_checkup_count_PHC3 += 1
            yield self.request(ipd_nurse_PHC3)
            temp = sim.Triangular(8, 20.6, 12.3).sample()
            delivery_nurse_time_PHC3 += temp
            yield self.hold(temp)  # time taken from a study on ANC visits in Tanzania
            self.release(ipd_nurse_PHC3)
            lab_count_PHC3 += 1
            # changed here
            a0 = env.now()
            self.enter(lab_q_PHC3)
            yield self.request(lab_technician_PHC3)
            self.leave(lab_q_PHC3)
            lab_q_waiting_time_PHC3.append(env.now() - a0)
            yp = (sim.Normal(5, 1).bounded_sample())
            y0 = yp
            yield self.hold(y0)
            self.release(lab_technician_PHC3)
            lab_time_PHC3 += y0


class ANC_followup_PHC3(sim.Component):
    followup_count = 0

    def process(self):

        global warmup_time
        global ipd_nurse_PHC3
        global q_ANC_PHC2  # need change here and corrosponding arrays
        global delivery_nurse_time_PHC3
        global lab_time_PHC3
        global lab_q_waiting_time_PHC3

        if env.now() <= warmup_time:
            for key in ANC_PHC3.ANC_List_PHC3:  # for identifying and updating ANC visit number
                x0 = env.now()
                x1 = ANC_PHC3.ANC_List_PHC3[key]["Scheduled Visit"][1]
                x2 = ANC_PHC3.ANC_List_PHC3[key]["Scheduled Visit"][2]
                x3 = ANC_PHC3.ANC_List_PHC3[key]["Scheduled Visit"][3]
                if 0 <= (x1 - x0) < 481:
                    ANC_PHC3.ANC_List_PHC3[key]["Scheduled Visit"][1] = float("inf")
                    ANC_PHC3.ANC_List_PHC3[key]["Visit Number"] = 2
                elif 0 <= (x2 - x0) < 481:
                    ANC_PHC3.ANC_List_PHC3[key]["Scheduled Visit"][2] = float("inf")
                    ANC_PHC3.ANC_List_PHC3[key]["Visit Number"] = 3
                elif 0 <= (x3 - x0) < 481:
                    ANC_PHC3.ANC_List_PHC3[key]["Scheduled Visit"][3] = float("inf")
                    ANC_PHC3.ANC_List_PHC3[key]["Visit Number"] = 4

            yield self.request(ipd_nurse_PHC3)
            temp = sim.Triangular(3.33, 13.16, 6.50).sample()
            yield self.hold(temp)
            self.release(ipd_nurse_PHC3)
            self.enter(lab_q_PHC3)
            yield self.request(lab_technician_PHC3)
            self.leave(lab_q_PHC3)
            yp = (sim.Normal(3.456, .823).bounded_sample(2))
            y0 = yp
            yield self.hold(y0)
            self.release(lab_technician_PHC3)

        else:
            for key in ANC_PHC3.ANC_List_PHC3:  # for identifying and updating ANC visit number
                x0 = env.now()
                x1 = ANC_PHC3.ANC_List_PHC3[key]["Scheduled Visit"][1]
                x2 = ANC_PHC3.ANC_List_PHC3[key]["Scheduled Visit"][2]
                x3 = ANC_PHC3.ANC_List_PHC3[key]["Scheduled Visit"][3]
                if 0 <= (x1 - x0) < 481:
                    ANC_PHC3.ANC_List_PHC3[key]["Scheduled Visit"][1] = float("inf")
                    ANC_PHC3.ANC_List_PHC3[key]["Visit Number"] = 2
                elif 0 <= (x2 - x0) < 481:
                    ANC_PHC3.ANC_List_PHC3[key]["Scheduled Visit"][2] = float("inf")
                    ANC_PHC3.ANC_List_PHC3[key]["Visit Number"] = 3
                elif 0 <= (x3 - x0) < 481:
                    ANC_PHC3.ANC_List_PHC3[key]["Scheduled Visit"][3] = float("inf")
                    ANC_PHC3.ANC_List_PHC3[key]["Visit Number"] = 4

            yield self.request(ipd_nurse_PHC3)
            temp = sim.Triangular(3.33, 13.16, 6.50).sample()
            delivery_nurse_time_PHC3 += temp
            yield self.hold(temp)
            self.release(ipd_nurse_PHC3)
            a0 = env.now()
            self.enter(lab_q_PHC3)
            yield self.request(lab_technician_PHC3)
            self.leave(lab_q_PHC3)
            lab_q_waiting_time_PHC3.append(env.now() - a0)
            yp = (sim.Normal(3.456, .823).bounded_sample(2))
            y0 = yp
            yield self.hold(y0)
            self.release(lab_technician_PHC3)
            lab_time_PHC3 += y0


class CovidGenerator_PHC3(sim.Component):

    def process(self):
        global d1_PHC3
        global warmup_time
        global covid_iat_PHC3
        global phc_covid_iat
        global j

        while True:

            if env.now() < warmup_time:
                if 0 <= (env.now() - d1_PHC3 * 1440) < 480:
                    covid_PHC3()
                    yield self.hold(covid_iat_PHC3)
                    d1_PHC3 = int(env.now() / 1440)
                else:
                    yield self.hold(960)
                    d1_PHC3 = int(env.now() / 1440)
            else:
                a = phc_covid_iat[j]
                if 0 <= (env.now() - d1_PHC3 * 1440) < 480:
                    covid_PHC3()
                    yield self.hold(sim.Exponential(a).sample())
                    d1_PHC3 = int(env.now() / 1440)
                else:
                    yield self.hold(960)
                    d1_PHC3 = int(env.now() / 1440)


class covid_PHC3(sim.Component):

    def process(self):

        global home_refer_PHC3
        global chc_refer_PHC3
        global dh_refer_PHC3
        global isolation_ward_refer_PHC3
        global covid_patient_time_PHC3
        global covid_count_PHC3
        global warmup_time
        global ipd_nurse_PHC3
        global ipd_nurse_time_PHC3
        global doc_OPD_PHC3
        global MO_covid_time_PHC3
        global phc2chc_count_PHC3
        global warmup_time
        global home_isolation_PHC3

        global ICU_oxygen
        global phc3_to_cc_severe_case
        global phc3_to_cc_dist
        global phc3_2_cc

        if env.now() < warmup_time:
            covid_nurse_PHC3()
            covid_lab_PHC3()
            x = random.randint(0, 1000)
            if x <= 940:
                a = random.randint(0, 100)
                if a >=90 :
                    cc_isolation()
            elif 940 < x <= 980:
                pass
            # CovidCare_chc2()
            else:
                pass
                # SevereCase()
        else:
            covid_count_PHC3 += 1
            covid_nurse_PHC3()
            covid_lab_PHC3()
            x = random.randint(0, 1000)
            if x <= 940:  # mild cases
                home_refer_PHC3 += 1
                a = random.randint(0, 100)
                if a >= 90:  # 10 % for institutional quarantine
                    isolation_ward_refer_PHC3 += 1
                    cc_isolation()
                else:
                    home_isolation_PHC3 += 1
            elif 940 < x <= 980:  # moderate cases
                chc_refer_PHC3 += 1
                phc2chc_count_PHC3 += 1
                CovidCare_chc3()
            else:  # severe case
                s = random.randint(0, 100)
                if s < 50:  # Type f patients
                    if ICU_oxygen.available_quantity() < 1:  # checks if there is a vacant bed in DH
                        phc3_to_cc_severe_case += 1
                        phc3_to_cc_dist.append(phc3_2_cc)
                        c = random.randint(1, 100)
                        cc_Type_F()  # patient refered tpo CC
                    else:
                        DH_SevereTypeF()
                        dh_refer_PHC3 += 1  # Severe cases
                elif 50 <= s < 75:  # E type patients
                    if ICU_ventilator.available_quantity() < 1:  # checks if there is a vacant bed in DH
                        cc_ICU_ward_TypeE()
                        phc3_to_cc_severe_case += 1
                    else:
                        DH_SevereTypeE()
                        dh_refer_PHC3 += 1  # Severe cases
                else:  # Type d patients
                    if ICU_ventilator.available_quantity() < 1:  # checks if there is a vacant bed in DH
                        cc_ventilator_TypeD()
                        phc3_to_cc_severe_case += 1
                    else:
                        dh_refer_PHC3 += 1  # Severe cases
                        DH_SevereTypeD()


class covid_nurse_PHC3(sim.Component):
    global lab_covidcount_PHC3

    def process(self):

        global warmup_time
        global ipd_nurse_PHC3
        global ipd_nurse_time_PHC3
        global lab_covidcount_PHC3

        if env.now() <= warmup_time:
            yield self.request(ipd_nurse_PHC3)
            yield self.hold(sim.Uniform(2, 3).sample())
            self.release(ipd_nurse_PHC3)
        else:
            lab_covidcount_PHC3 += 1
            yield self.request(ipd_nurse_PHC3)
            t = sim.Uniform(2, 3).sample()
            yield self.hold(t)
            ipd_nurse_time_PHC3 += t
            self.release(ipd_nurse_PHC3)


class covid_lab_PHC3(sim.Component):

    def process(self):

        global lab_technician_PHC3
        global lab_time_PHC3
        global lab_q_waiting_time_PHC3
        global warmup_time
        global lab_covidcount_PHC3

        if env.now() <= warmup_time:
            yield self.request(lab_technician_PHC3)
            yield self.hold(sim.Uniform(1, 2).sample())
            self.release(lab_technician_PHC3)
        else:
            lab_covidcount_PHC3 += 1
            yield self.request(lab_technician_PHC3)
            t = sim.Uniform(1, 2).sample()
            yield self.hold(t)
            lab_time_PHC3 += t
            self.release(lab_technician_PHC3)
            x = random.randint(0, 100)
            if x < 33:  # confirmed posiive
                covid_doc_PHC3()
            elif 33 < x < 67:  # symptomatic negative, retesting
                retesting_PHC3()
            else:
                Pharmacy_PHC3()


class retesting_PHC3(sim.Component):

    def process(self):

        global retesting_count_PHC3
        global warmup_time

        if env.now() <= warmup_time:
            yield self.hold(1440)
            covid_doc_PHC3()
        else:
            retesting_count_PHC3 += 1
            yield self.hold(1440)
            covid_doc_PHC3()


class covid_doc_PHC3(sim.Component):

    def process(self):
        global MO_covid_time_PHC3
        global doc_OPD_PHC3
        global warmup_time
        global covid_q_PHC3
        global covid_patient_time_PHC3
        global medicine_cons_time_PHC3

        if env.now() <= warmup_time:
            self.enter(covid_q_PHC3)
            yield self.request(doc_OPD_PHC3)
            self.leave(covid_q_PHC3)
            yield self.hold(sim.Uniform(3, 6).sample())
            self.release(doc_OPD_PHC3)
        else:
            in_time = env.now()
            self.enter(covid_q_PHC3)
            yield self.request(doc_OPD_PHC3)
            self.leave(covid_q_PHC3)
            t = sim.Uniform(3, 6).sample()
            yield self.hold(t)
            MO_covid_time_PHC3 += t
            self.release(doc_OPD_PHC3)
            medicine_cons_time_PHC3 += t
            covid_patient_time_PHC3 += env.now() - in_time


global l4  # temp lab count
l4 = 0
global o_PHC4  # temp opd count
o_PHC4 = 0


# PHC 3
class PatientGenerator_PHC4(sim.Component):
    global shift_PHC4
    shift_PHC4 = 0
    No_of_days_PHC4 = 0

    total_OPD_patients_PHC4 = 0

    def process(self):

        global env
        global warmup_time
        global opd_iat_PHC4
        global days_PHC4
        global medicine_cons_time_PHC4
        global shift_PHC4
        global phc1_doc_time_PHC4

        self.sim_time_PHC4 = 0  # local variable defined for dividing each day into shits
        self.z_PHC4 = 0
        self.admin_count_PHC4 = 0
        k_PHC4 = 0

        while self.z_PHC4 % 3 == 0:  # condition to run simulation for 8 hour shifts
            PatientGenerator_PHC4.No_of_days_PHC4 += 1  # class variable to track number of days passed
            while self.sim_time_PHC4 < 360:  # from morning 8 am to afternoon 2 pm (in minutes)
                if env.now() <= warmup_time:
                    pass
                else:
                    OPD_PHC4()
                o = sim.Exponential(opd_iat_PHC4).sample()
                yield self.hold(o)
                self.sim_time_PHC4 += o

            while 360 <= self.sim_time_PHC4 < 480:  # condition for admin work after opd hours are over
                k_PHC4 = int(sim.Normal(100, 20).bounded_sample(60, 140))
                """For sensitivity analysis. Admin work added to staff nurse rather than doctor"""
                if env.now() <= warmup_time:
                    pass
                else:
                    medicine_cons_time_PHC4 += k_PHC4  # conatns all doctor service times
                    phc1_doc_time_PHC4 += k_PHC4
                yield self.hold(120)
                self.sim_time_PHC4 = 481
            self.z_PHC4 += 3
            self.sim_time_PHC4 = 0
            # PatientGenerator1.No_of_shifts += 3
            yield self.hold(959)  # holds simulation for 2 shifts


class OPD_PHC4(sim.Component):
    Patient_log_PHC4 = {}

    def setup(self):

        self.dic = {}  # local dictionary for temporarily   storing generated patients
        # with attributes
        self.time_of_visit = [[0], [0], [0]]  # initializing for assigning time of visits
        self.regis_time = round(env.now())  # registration time is the current simulation time
        self.id = PatientGenerator_PHC4.total_OPD_patients_PHC4  # patient count is patient id
        self.age_random = random.randint(0, 1000)  # assigning age to population based on census 2011 gurgaon
        if self.age_random <= 578:
            self.age = random.randint(0, 30)
        else:
            self.age = random.randint(31, 100)
        self.sex = random.choice(["male", "female"])  # Equal probability of male and female patient
        # require lab tests
        self.lab_required = random.choice(["True", "False"])  # Considering nearly half of all the patients
        self.radiography_required = random.choice(["True", "False"])
        y = random.randint(0, 999)
        self.consultation = random.choice([y])  # for medicine, gynea, pead, denta
        self.visits_assigned = random.randint(1, 10)  # assigning number of visits visits
        self.dic = {"ID": self.id, "Age": self.age, "Sex": self.sex, "Lab": self.lab_required,
                    "Registration_Time": self.regis_time, "No_of_visits": self.visits_assigned,
                    "Time_of_visit": self.time_of_visit, "Radiography": self.radiography_required,
                    "Consultation": self.consultation}
        OPD_PHC4.Patient_log_PHC4[PatientGenerator_PHC4.total_OPD_patients_PHC4] = self.dic

        self.process()

    def process(self):

        global c4
        global medicine_q_PHC4
        global doc_OPD_PHC4
        global opd_ser_time_mean_PHC4
        global opd_ser_time_sd_PHC4
        global medicine_count_PHC4
        global medicine_cons_time_PHC4
        global opd_q_waiting_time_PHC4
        global ncd_count_PHC4
        global ncd_nurse_PHC4
        global ncd_time_PHC4
        global warmup_time
        global l4
        global phc1_doc_time_PHC4

        if env.now() <= warmup_time:
            p = random.randint(0, 10)
            if p < 2:
                COVID_OPD_PHC4()
            if OPD_PHC4.Patient_log_PHC4[PatientGenerator_PHC4.total_OPD_patients_PHC4]["Age"] > 30:
                yield self.request(ncd_nurse_PHC4)
                ncd_service = sim.Uniform(2, 5).sample()
                yield self.hold(ncd_service)
            self.enter(medicine_q_PHC4)
            yield self.request(doc_OPD_PHC4)
            self.leave(medicine_q_PHC4)
            o = sim.Normal(opd_ser_time_mean_PHC4, opd_ser_time_sd_PHC4).bounded_sample(0.3)
            yield self.hold(o)
            self.release(doc_OPD_PHC4)
            if OPD_PHC4.Patient_log_PHC4[PatientGenerator_PHC4.total_OPD_patients_PHC4]["Lab"] == "True":
                Lab_PHC4()
            Pharmacy_PHC4()
        else:
            l4 += 1
            medicine_count_PHC4 += 1
            p = random.randint(0, 10)
            if p < 2:
                COVID_OPD_PHC4()
            if OPD_PHC4.Patient_log_PHC4[PatientGenerator_PHC4.total_OPD_patients_PHC4]["Age"] > 30:
                ncd_count_PHC4 += 1
                yield self.request(ncd_nurse_PHC4)
                ncd_service = sim.Uniform(2, 5).sample()
                yield self.hold(ncd_service)
                ncd_time_PHC4 += ncd_service
            # doctor opd starts from here
            entry_time = env.now()
            self.enter(medicine_q_PHC4)
            yield self.request(doc_OPD_PHC4)
            self.leave(medicine_q_PHC4)
            exit_time = env.now()
            opd_q_waiting_time_PHC4.append(exit_time - entry_time)  # stores waiting time in the queue
            o = sim.Normal(opd_ser_time_mean_PHC4, opd_ser_time_sd_PHC4).bounded_sample(0.3)
            yield self.hold(o)
            phc1_doc_time_PHC4 += o
            medicine_cons_time_PHC4 += o
            self.release(doc_OPD_PHC4)
            # lab starts from here
            t = random.randint(0, 1000)
            # changed here
            if OPD_PHC4.Patient_log_PHC4[PatientGenerator_PHC4.total_OPD_patients_PHC4]["Lab"] == "True":
                Lab_PHC4()
            Pharmacy_PHC4()


class COVID_OPD_PHC4(sim.Component):

    def process(self):

        global ipd_nurse_PHC4
        global ipd_nurse_time_PHC4

        if env.now() <= warmup_time:
            yield self.request(ipd_nurse_PHC4)
            h1 = sim.Uniform(5, 10).sample()
            yield self.hold(h1)
            self.release(ipd_nurse_PHC4)
            OPD_covidtest_PHC4()
            yield self.hold(sim.Uniform(15, 30).sample())  # patient waits for the result
        else:
            yield self.request(ipd_nurse_PHC4)
            h1 = sim.Uniform(5, 10).sample()
            yield self.hold(h1)
            self.release(ipd_nurse_PHC4)
            ipd_nurse_time_PHC4 += h1
            OPD_covidtest_PHC4()
            yield self.hold(sim.Uniform(15, 30).sample())


class OPD_covidtest_PHC4(sim.Component):

    def process(self):
        global lab_covidcount_PHC4
        global lab_technician_PHC4
        global lab_time_PHC4
        global warmup_time

        if env.now() <= warmup_time:
            yield self.request(lab_technician_PHC4)
            t = sim.Uniform(1, 2).sample()
            yield self.hold(t)
            self.release(lab_technician_PHC4)
        else:
            lab_covidcount_PHC4 += 1
            yield self.request(lab_technician_PHC4)
            t = sim.Uniform(1, 2).sample()
            yield self.hold(t)
            lab_time_PHC4 += t
            self.release(lab_technician_PHC4)


class Pharmacy_PHC4(sim.Component):

    def process(self):

        global pharmacist_PHC4
        global pharmacy_time_PHC4
        global pharmacy_q_PHC4
        global pharmacy_q_waiting_time_PHC4
        global warmup_time
        global pharmacy_count_PHC4

        if env.now() < warmup_time:
            self.enter(pharmacy_q_PHC4)
            yield self.request(pharmacist_PHC4)
            self.leave(pharmacy_q_PHC4)
            # service_time = sim.Uniform(1, 2.5).sample()
            service_time = sim.Normal(2.083, 0.72).bounded_sample(.67)
            yield self.hold(service_time)
            self.release(pharmacist_PHC4)
        else:
            pharmacy_count_PHC4 += 1
            e1 = env.now()
            self.enter(pharmacy_q_PHC4)
            yield self.request((pharmacist_PHC4, 1))
            self.leave(pharmacy_q_PHC4)
            pharmacy_q_waiting_time_PHC4.append(env.now() - e1)
            service_time = sim.Normal(2.083, 0.72).bounded_sample(.67)
            yield self.hold(service_time)
            self.release((pharmacist_PHC4, 1))
            pharmacy_time_PHC4 += service_time


class Lab_PHC4(sim.Component):

    def process(self):
        global lab_q_PHC4
        global lab_technician_PHC4
        global lab_time_PHC4
        global lab_q_waiting_time_PHC4
        global warmup_time
        global lab_count_PHC4
        global o_PHC4

        if env.now() <= warmup_time:
            self.enter(lab_q_PHC4)
            yield self.request(lab_technician_PHC4)
            self.leave(lab_q_PHC4)
            yp = (sim.Normal(3.456, .823).bounded_sample(2))
            y0 = yp
            yield self.hold(y0)
            self.release(lab_technician_PHC4)
        else:
            lab_count_PHC4 += 1
            self.enter(lab_q_PHC4)
            a0 = env.now()
            yield self.request(lab_technician_PHC4)
            self.leave(lab_q_PHC4)
            lab_q_waiting_time_PHC4.append(env.now() - a0)
            f1 = env.now()
            yp = (sim.Normal(3.456, .823).bounded_sample(2))
            y0 = yp
            yield self.hold(y0)
            self.release(lab_technician_PHC4)
            f2 = env.now()
            lab_time_PHC4 += f2 - f1
            o_PHC4 += 1


class IPD_PatientGenerator_PHC4(sim.Component):
    global IPD1_iat_PHC4
    global warmup_time
    IPD_List_PHC4 = {}  # log of all the IPD patients stored here
    patient_count_PHC4 = 0
    p_count_PHC4 = 0  # log of patients in each replication

    def process(self):
        global days_PHC3
        M = 0
        while True:
            if env.now() <= warmup_time:
                pass
            else:
                IPD_PatientGenerator_PHC4.patient_count_PHC4 += 1
                IPD_PatientGenerator_PHC4.p_count_PHC4 += 1
            self.registration_time = env.now()
            self.id = IPD_PatientGenerator_PHC4.patient_count_PHC4
            self.age = round(random.normalvariate(35, 8))
            self.sex = random.choice(["Male", "Female"])
            IPD_PatientGenerator_PHC4.IPD_List_PHC4[self.id] = [self.registration_time, self.id, self.age, self.sex]
            if 0 < (self.registration_time - M * 1440) < 480:
                IPD_with_doc_PHC4(urgent=True)
            else:
                pass
            self.hold_time_1 = sim.Exponential(IPD1_iat_PHC4).sample()
            yield self.hold(self.hold_time_1)
            M = int(env.now() / 1440)


class IPD_with_doc_PHC4(sim.Component):

    def process(self):
        global MO_ipd_PHC4
        global ipd_nurse_PHC4
        global in_beds_PHC4
        global MO_ipd_time_PHC4
        global ipd_nurse_time_PHC4
        global warmup_time
        global ipd_bed_time_PHC4
        global ipd_nurse_time_PHC4
        global emergency_refer_PHC4  # Changed here
        global medicine_q_PHC4
        global ipd_MO_time_PHC4
        global opd_q_waiting_time_PHC4
        global phc1_doc_time_PHC4
        global medicine_cons_time_PHC4

        if env.now() <= warmup_time:
            self.enter_at_head(medicine_q_PHC4)
            yield self.request(doc_OPD_PHC4, fail_delay=20)
            doc_time = round(sim.Uniform(10, 30, 'minutes').sample())
            if self.failed():
                self.leave(medicine_q_PHC4)
                yield self.request(ipd_nurse_PHC4)
                temp = sim.Uniform(30, 60, 'minutes').sample()
                yield self.hold(temp)
                self.release(ipd_nurse_PHC4)
                yield self.request(doc_OPD_PHC4)
                yield self.hold(doc_time)
                self.release(doc_OPD_PHC4)
                yield self.request(in_beds_PHC4)
                yield self.hold(sim.Triangular(60, 360, 180, 'minutes').bounded_sample(0))
                self.release(in_beds_PHC4)
            else:
                self.leave(medicine_q_PHC4)
                yield self.hold(doc_time)
                self.release(doc_OPD_PHC4)
                yield self.request(in_beds_PHC4, ipd_nurse_PHC4)
                temp = sim.Uniform(30, 60, 'minutes').sample()
                yield self.hold(temp)
                self.release(ipd_nurse_PHC4)
                yield self.hold(sim.Triangular(60, 360, 180, 'minutes').bounded_sample(0))
                self.release(in_beds_PHC4)
        else:
            self.enter_at_head(medicine_q_PHC4)
            entry_time2 = env.now()
            yield self.request(doc_OPD_PHC4, fail_delay=20)
            doc_time = sim.Uniform(10, 30, 'minutes').sample()
            t_bed = sim.Triangular(60, 360, 180, 'minutes').sample()
            t_nurse = sim.Uniform(30, 60, 'minutes').sample()
            phc1_doc_time_PHC4 += doc_time
            medicine_cons_time_PHC4 += doc_time
            if self.failed():
                self.leave(medicine_q_PHC4)
                exit_time2 = env.now()
                opd_q_waiting_time_PHC4.append(exit_time2 - entry_time2)  # stores waiting time in the queue
                yield self.request(ipd_nurse_PHC4)
                yield self.hold(t_nurse)
                self.release(ipd_nurse_PHC4)
                yield self.request(doc_OPD_PHC4)
                yield self.hold(doc_time)
                self.release(doc_OPD_PHC4)
                yield self.request(in_beds_PHC4)
                yield self.hold(t_bed)
                self.release(in_beds_PHC4)
                ipd_bed_time_PHC4 += t_bed
                ipd_MO_time_PHC4 += doc_time
                ipd_nurse_time_PHC4 += t_nurse
            else:
                self.leave(medicine_q_PHC4)
                exit_time3 = env.now()
                opd_q_waiting_time_PHC4.append(exit_time3 - entry_time2)  # stores waiting time in the queue
                yield self.hold(doc_time)
                self.release(doc_OPD_PHC4)
                yield self.request(in_beds_PHC4, ipd_nurse_PHC4)
                yield self.hold(t_nurse)
                self.release(ipd_nurse_PHC4)
                yield self.hold(t_bed)
                self.release(in_beds_PHC4)
                ipd_bed_time_PHC4 += t_bed
                ipd_MO_time_PHC4 += doc_time
                ipd_nurse_time_PHC4 += t_nurse


class CovidGenerator_PHC4(sim.Component):

    def process(self):

        global d1_PHC4
        global warmup_time
        global covid_iat_PHC4
        global phc_covid_iat
        global j

        while True:

            if env.now() < warmup_time:
                if 0 <= (env.now() - d1_PHC4 * 1440) < 480:
                    covid_PHC4()
                    yield self.hold(1440 / 3)
                    d1_PHC4 = int(env.now() / 1440)
                else:
                    yield self.hold(960)
                    d1_PHC4 = int(env.now() / 1440)

            else:
                a = phc_covid_iat[j]
                if 0 <= (env.now() - d1_PHC4 * 1440) < 480:
                    covid_PHC4()
                    yield self.hold(sim.Exponential(a).sample())
                    d1_PHC4 = int(env.now() / 1440)
                else:
                    yield self.hold(960)
                    d1_PHC4 = int(env.now() / 1440)


class covid_PHC4(sim.Component):

    def process(self):

        global home_refer_PHC4
        global chc_refer_PHC4
        global dh_refer_PHC4
        global isolation_ward_refer_PHC4
        global covid_patient_time_PHC4
        global covid_count_PHC4
        global warmup_time
        global ipd_nurse_PHC4
        global ipd_nurse_time_PHC4
        global doc_OPD_PHC4
        global MO_covid_time_PHC4
        global phc2chc_count_PHC4
        global warmup_time
        global home_isolation_PHC4

        global ICU_oxygen
        global phc4_to_cc_severe_case
        global phc4_to_cc_dist
        global phc4_2_cc

        if env.now() < warmup_time:
            covid_nurse_PHC4()
            covid_lab_PHC4()
            x = random.randint(0, 1000)
            if x <= 940:
                a = random.randint(0, 10)
                if a >= 9:
                    cc_isolation()
            elif 940 < x <= 980:
                pass
            # CovidCare_chc2()
            else:
                pass
                 #SevereCase()
        else:
            covid_count_PHC4 += 1
            covid_nurse_PHC4()
            covid_lab_PHC4()
            x = random.randint(0, 1000)
            if x <= 940:  # mild cases
                home_refer_PHC4 += 1
                a = random.randint(0, 100)
                if a >= 90:  # 10 % for institutional quarantine
                    isolation_ward_refer_PHC4 += 1
                    cc_isolation()
                else:
                    home_isolation_PHC4 += 1
            elif 940 < x <= 980:  # moderate cases
                chc_refer_PHC4 += 1
                phc2chc_count_PHC4 += 1
                CovidCare_chc1()
            else:  # severe case
                s = random.randint(0, 100)
                if s < 50:  # Type f patients
                    if ICU_oxygen.available_quantity() < 1:  # checks if there is a vacant bed in DH
                        phc4_to_cc_severe_case += 1
                        phc4_to_cc_dist.append(phc4_2_cc)
                        cc_Type_F()  # patient refered tpo CC
                    else:
                        DH_SevereTypeF()
                        dh_refer_PHC4 += 1  # Severe cases
                elif 50 <= s <= 74:  # E type patients
                    if ICU_ventilator.available_quantity() < 1:  # checks if there is a vacant bed in DH
                        cc_ICU_ward_TypeE()
                        phc4_to_cc_severe_case += 1
                    else:
                        DH_SevereTypeE()
                        dh_refer_PHC4 += 1  # Severe cases
                else:  # Type d patients
                    if ICU_ventilator.available_quantity() < 1:  # checks if there is a vacant bed in DH
                        cc_ventilator_TypeD()
                        phc4_to_cc_severe_case += 1
                    else:
                        dh_refer_PHC4 += 1  # Severe cases
                        DH_SevereTypeD()


class covid_nurse_PHC4(sim.Component):
    global lab_covidcount_PHC4

    def process(self):

        global warmup_time
        global ipd_nurse_PHC4
        global ipd_nurse_time_PHC4
        global lab_covidcount_PHC4

        if env.now() <= warmup_time:
            yield self.request(ipd_nurse_PHC4)
            yield self.hold(sim.Uniform(2, 3).sample())
            self.release(ipd_nurse_PHC4)
        else:
            lab_covidcount_PHC4 += 1
            yield self.request(ipd_nurse_PHC4)
            t = sim.Uniform(2, 3).sample()
            yield self.hold(t)
            ipd_nurse_time_PHC4 += t
            self.release(ipd_nurse_PHC4)


class covid_lab_PHC4(sim.Component):

    def process(self):

        global lab_technician_PHC4
        global lab_time_PHC4
        global lab_q_waiting_time_PHC4
        global warmup_time
        global lab_covidcount_PHC4

        if env.now() <= warmup_time:
            yield self.request(lab_technician_PHC4)
            yield self.hold(sim.Uniform(1, 2).sample())
            self.release(lab_technician_PHC4)
        else:
            lab_covidcount_PHC4 += 1
            yield self.request(lab_technician_PHC4)
            t = sim.Uniform(1, 2).sample()
            yield self.hold(t)
            lab_time_PHC4 += t
            self.release(lab_technician_PHC4)
            x = random.randint(0, 100)
            if x < 33:  # confirmed posiive
                covid_doc_PHC4()
            elif 33 < x < 67:  # symptomatic negative, retesting
                retesting_PHC4()
            else:
                Pharmacy_PHC4()


class retesting_PHC4(sim.Component):

    def process(self):

        global retesting_count_PHC4
        global warmup_time

        if env.now() <= warmup_time:
            yield self.hold(1440)
            covid_doc_PHC4()
        else:
            retesting_count_PHC4 += 1
            yield self.hold(1440)
            covid_doc_PHC4()


class covid_doc_PHC4(sim.Component):

    def process(self):
        global MO_covid_time_PHC4
        global doc_OPD_PHC4
        global warmup_time
        global covid_q_PHC4
        global covid_patient_time_PHC4
        global medicine_cons_time_PHC4

        if env.now() <= warmup_time:
            self.enter(covid_q_PHC4)
            yield self.request(doc_OPD_PHC4)
            self.leave(covid_q_PHC4)
            yield self.hold(sim.Uniform(3, 6).sample())
            self.release(doc_OPD_PHC4)
        else:
            in_time = env.now()
            self.enter(covid_q_PHC4)
            yield self.request(doc_OPD_PHC4)
            self.leave(covid_q_PHC4)
            t = sim.Uniform(3, 6).sample()
            yield self.hold(t)
            MO_covid_time_PHC4 += t
            medicine_cons_time_PHC4 += t
            self.release(doc_OPD_PHC4)
            covid_patient_time_PHC4 += env.now() - in_time


global l5  # temp lab count
l5 = 0
global o_PHC5  # temp opd count
o_PHC5 = 0


# PHC 5
class PatientGenerator_PHC5(sim.Component):
    global shift_PHC5
    shift_PHC5 = 0
    No_of_days_PHC5 = 0

    total_OPD_patients_PHC5 = 0

    def process(self):

        global env
        global warmup_time
        global opd_iat_PHC5
        global days_PHC5
        global medicine_cons_time_PHC5
        global shift_PHC5
        global phc1_doc_time_PHC5

        self.sim_time_PHC5 = 0  # local variable defined for dividing each day into shits
        self.z_PHC5 = 0
        self.admin_count_PHC5 = 0
        k_PHC5 = 0

        while self.z_PHC5 % 3 == 0:  # condition to run simulation for 8 hour shifts
            PatientGenerator_PHC5.No_of_days_PHC5 += 1  # class variable to track number of days passed
            while self.sim_time_PHC5 < 360:  # from morning 8 am to afternoon 2 pm (in minutes)
                if env.now() <= warmup_time:
                    pass
                else:
                    OPD_PHC5()
                o = sim.Exponential(opd_iat_PHC5).sample()
                yield self.hold(o)
                self.sim_time_PHC5 += o

            while 360 <= self.sim_time_PHC5 < 480:  # condition for admin work after opd hours are over
                k_PHC5 = int(sim.Normal(100, 20).bounded_sample(60, 140))
                """For sensitivity analysis. Admin work added to staff nurse rather than doctor"""
                if env.now() <= warmup_time:
                    pass
                else:
                    medicine_cons_time_PHC5 += k_PHC5  # conatns all doctor service times
                    phc1_doc_time_PHC5 += k_PHC5
                yield self.hold(120)
                self.sim_time_PHC5 = 481
            self.z_PHC5 += 3
            self.sim_time_PHC5 = 0
            # PatientGenerator1.No_of_shifts += 3
            yield self.hold(959)  # holds simulation for 2 shifts


class OPD_PHC5(sim.Component):
    Patient_log_PHC5 = {}

    def setup(self):

        self.dic = {}  # local dictionary for temporarily   storing generated patients
        # with attributes
        self.time_of_visit = [[0], [0], [0]]  # initializing for assigning time of visits
        self.regis_time = round(env.now())  # registration time is the current simulation time
        self.id = PatientGenerator_PHC5.total_OPD_patients_PHC5  # patient count is patient id
        self.age_random = random.randint(0, 1000)  # assigning age to population based on census 2011 gurgaon
        if self.age_random <= 578:
            self.age = random.randint(0, 30)
        else:
            self.age = random.randint(31, 100)
        self.sex = random.choice(["male", "female"])  # Equal probability of male and female patient
        # require lab tests
        self.lab_required = random.choice(["True", "False"])  # Considering nearly half of all the patients
        self.radiography_required = random.choice(["True", "False"])
        y = random.randint(0, 999)
        self.consultation = random.choice([y])  # for medicine, gynea, pead, denta
        self.visits_assigned = random.randint(1, 10)  # assigning number of visits visits
        self.dic = {"ID": self.id, "Age": self.age, "Sex": self.sex, "Lab": self.lab_required,
                    "Registration_Time": self.regis_time, "No_of_visits": self.visits_assigned,
                    "Time_of_visit": self.time_of_visit, "Radiography": self.radiography_required,
                    "Consultation": self.consultation}
        OPD_PHC5.Patient_log_PHC5[PatientGenerator_PHC5.total_OPD_patients_PHC5] = self.dic

        self.process()

    def process(self):

        global c5
        global medicine_q_PHC5
        global doc_OPD_PHC5
        global opd_ser_time_mean_PHC5
        global opd_ser_time_sd_PHC5
        global medicine_count_PHC5
        global medicine_cons_time_PHC5
        global opd_q_waiting_time_PHC5
        global ncd_count_PHC5
        global ncd_nurse_PHC5
        global ncd_time_PHC5
        global warmup_time
        global l5
        global phc1_doc_time_PHC5

        if env.now() <= warmup_time:
            p = random.randint(0, 10)
            if p < 2:
                COVID_OPD_PHC5()
            if OPD_PHC5.Patient_log_PHC5[PatientGenerator_PHC5.total_OPD_patients_PHC5]["Age"] > 30:
                yield self.request(ncd_nurse_PHC5)
                ncd_service = sim.Uniform(2, 5).sample()
                yield self.hold(ncd_service)
            self.enter(medicine_q_PHC5)
            yield self.request(doc_OPD_PHC5)
            self.leave(medicine_q_PHC5)
            o = sim.Normal(opd_ser_time_mean_PHC5, opd_ser_time_sd_PHC5).bounded_sample(0.3)
            yield self.hold(o)
            self.release(doc_OPD_PHC5)
            if OPD_PHC5.Patient_log_PHC5[PatientGenerator_PHC5.total_OPD_patients_PHC5]["Lab"] == "True":
                Lab_PHC5()
            Pharmacy_PHC5()
        else:
            l5 += 1
            medicine_count_PHC5 += 1
            p = random.randint(0, 10)
            if p < 2:
                COVID_OPD_PHC5()
            if OPD_PHC5.Patient_log_PHC5[PatientGenerator_PHC5.total_OPD_patients_PHC5]["Age"] > 30:
                ncd_count_PHC5 += 1
                yield self.request(ncd_nurse_PHC5)
                ncd_service = sim.Uniform(2, 5).sample()
                yield self.hold(ncd_service)
                ncd_time_PHC5 += ncd_service
            # doctor opd starts from here
            entry_time = env.now()
            self.enter(medicine_q_PHC5)
            yield self.request(doc_OPD_PHC5)
            self.leave(medicine_q_PHC5)
            exit_time = env.now()
            opd_q_waiting_time_PHC5.append(exit_time - entry_time)  # stores waiting time in the queue
            o = sim.Normal(opd_ser_time_mean_PHC5, opd_ser_time_sd_PHC5).bounded_sample(0.3)
            yield self.hold(o)
            phc1_doc_time_PHC5 += o
            medicine_cons_time_PHC5 += o
            self.release(doc_OPD_PHC5)
            # lab starts from here
            t = random.randint(0, 1000)
            # changed here
            if OPD_PHC5.Patient_log_PHC5[PatientGenerator_PHC5.total_OPD_patients_PHC5]["Lab"] == "True":
                Lab_PHC5()
            Pharmacy_PHC5()


class COVID_OPD_PHC5(sim.Component):

    def process(self):

        global ipd_nurse_PHC5
        global ipd_nurse_time_PHC5

        if env.now() <= warmup_time:
            yield self.request(ipd_nurse_PHC5)
            h1 = sim.Uniform(5, 10).sample()
            yield self.hold(h1)
            self.release(ipd_nurse_PHC5)
            OPD_covidtest_PHC5()
            yield self.hold(sim.Uniform(15, 30).sample())  # patient waits for the result
        else:
            yield self.request(ipd_nurse_PHC5)
            h1 = sim.Uniform(5, 10).sample()
            yield self.hold(h1)
            self.release(ipd_nurse_PHC5)
            ipd_nurse_time_PHC5 += h1
            OPD_covidtest_PHC5()
            yield self.hold(sim.Uniform(15, 30).sample())


class OPD_covidtest_PHC5(sim.Component):

    def process(self):
        global lab_covidcount_PHC5
        global lab_technician_PHC5
        global lab_time_PHC5
        global warmup_time

        if env.now() <= warmup_time:
            yield self.request(lab_technician_PHC5)
            t = sim.Uniform(1, 2).sample()
            yield self.hold(t)
            self.release(lab_technician_PHC5)
        else:
            lab_covidcount_PHC5 += 1
            yield self.request(lab_technician_PHC5)
            t = sim.Uniform(1, 2).sample()
            yield self.hold(t)
            lab_time_PHC5 += t
            self.release(lab_technician_PHC5)


class Pharmacy_PHC5(sim.Component):

    def process(self):

        global pharmacist_PHC5
        global pharmacy_time_PHC5
        global pharmacy_q_PHC5
        global pharmacy_q_waiting_time_PHC5
        global warmup_time
        global pharmacy_count_PHC5

        if env.now() < warmup_time:
            self.enter(pharmacy_q_PHC5)
            yield self.request(pharmacist_PHC5)
            self.leave(pharmacy_q_PHC5)
            # service_time = sim.Uniform(1, 2.5).sample()
            service_time = sim.Normal(2.083, 0.72).bounded_sample(.67)
            yield self.hold(service_time)
            self.release(pharmacist_PHC5)
        else:
            pharmacy_count_PHC5 += 1
            e1 = env.now()
            self.enter(pharmacy_q_PHC5)
            yield self.request((pharmacist_PHC5, 1))
            self.leave(pharmacy_q_PHC5)
            pharmacy_q_waiting_time_PHC5.append(env.now() - e1)
            service_time = sim.Normal(2.083, 0.72).bounded_sample(.67)
            yield self.hold(service_time)
            self.release((pharmacist_PHC5, 1))
            pharmacy_time_PHC5 += service_time


class Lab_PHC5(sim.Component):

    def process(self):
        global lab_q_PHC5
        global lab_technician_PHC5
        global lab_time_PHC5
        global lab_q_waiting_time_PHC5
        global warmup_time
        global lab_count_PHC5
        global o_PHC5

        if env.now() <= warmup_time:
            self.enter(lab_q_PHC5)
            yield self.request(lab_technician_PHC5)
            self.leave(lab_q_PHC5)
            yp = (sim.Normal(3.456, .823).bounded_sample(2))
            y0 = yp
            yield self.hold(y0)
            self.release(lab_technician_PHC5)
        else:
            lab_count_PHC5 += 1
            self.enter(lab_q_PHC5)
            a0 = env.now()
            yield self.request(lab_technician_PHC5)
            self.leave(lab_q_PHC5)
            lab_q_waiting_time_PHC5.append(env.now() - a0)
            f1 = env.now()
            yp = (sim.Normal(3.456, .823).bounded_sample(2))
            y0 = yp
            yield self.hold(y0)
            self.release(lab_technician_PHC5)
            f2 = env.now()
            lab_time_PHC5 += f2 - f1
            o_PHC5 += 1


class IPD_PatientGenerator_PHC5(sim.Component):
    global IPD1_iat_PHC5
    global warmup_time
    IPD_List_PHC5 = {}  # log of all the IPD patients stored here
    patient_count_PHC5 = 0
    p_count_PHC5 = 0  # log of patients in each replication

    def process(self):
        global days_PHC5
        M = 0
        while True:
            if env.now() <= warmup_time:
                pass
            else:
                IPD_PatientGenerator_PHC5.patient_count_PHC5 += 1
                IPD_PatientGenerator_PHC5.p_count_PHC5 += 1
            self.registration_time = env.now()
            self.id = IPD_PatientGenerator_PHC5.patient_count_PHC5
            self.age = round(random.normalvariate(35, 8))
            self.sex = random.choice(["Male", "Female"])
            IPD_PatientGenerator_PHC5.IPD_List_PHC5[self.id] = [self.registration_time, self.id, self.age, self.sex]
            if 0 < (self.registration_time - M * 1440) < 480:
                IPD_with_doc_PHC5(urgent=True)
            else:
                IPD_no_doc_PHC5(urgent=True)
            self.hold_time_1 = sim.Exponential(IPD1_iat_PHC5).sample()
            yield self.hold(self.hold_time_1)
            M = int(env.now() / 1440)


class IPD_no_doc_PHC5(sim.Component):

    def process(self):
        global MO_ipd_PHC5
        global ipd_nurse_PHC5
        global in_beds_PHC5
        global ipd_nurse_time_PHC5
        global warmup_time
        global ipd_bed_time_PHC5
        global ipd_nurse_time_PHC5
        global medicine_q_PHC5
        global ipd_MO_time_PHC5

        if env.now() <= warmup_time:

            yield self.request(in_beds_PHC5, ipd_nurse_PHC5)
            temp = sim.Uniform(30, 60, 'minutes').sample()
            yield self.hold(temp)
            self.release(ipd_nurse_PHC5)
            yield self.hold(sim.Triangular(60, 360, 180, 'minutes').bounded_sample(0))
            self.release(in_beds_PHC5)
        else:
            t_bed = sim.Triangular(60, 360, 180, 'minutes').sample()
            t_nurse = sim.Uniform(30, 60, 'minutes').sample()
            yield self.request(in_beds_PHC5, ipd_nurse_PHC5)
            yield self.hold(t_nurse)
            self.release(ipd_nurse_PHC5)
            yield self.hold(t_bed)
            self.release(in_beds_PHC5)
            ipd_bed_time_PHC5 += t_bed
            ipd_nurse_time_PHC5 += t_nurse


class IPD_with_doc_PHC5(sim.Component):

    def process(self):
        global MO_ipd_PHC5
        global ipd_nurse_PHC5
        global in_beds_PHC5
        global MO_ipd_time_PHC5
        global ipd_nurse_time_PHC5
        global warmup_time
        global ipd_bed_time_PHC5
        global ipd_nurse_time_PHC5
        global emergency_refer_PHC5
        global medicine_q_PHC5
        global ipd_MO_time_PHC5
        global opd_q_waiting_time_PHC5
        global phc1_doc_time_PHC5
        global medicine_cons_time_PHC5

        if env.now() <= warmup_time:
            self.enter_at_head(medicine_q_PHC5)
            yield self.request(doc_OPD_PHC5, fail_delay=20)
            doc_time = round(sim.Uniform(10, 30, 'minutes').sample())
            if self.failed():
                self.leave(medicine_q_PHC5)
                yield self.request(ipd_nurse_PHC5)
                temp = sim.Uniform(30, 60, 'minutes').sample()
                yield self.hold(temp)
                self.release(ipd_nurse_PHC5)
                yield self.request(doc_OPD_PHC5)
                yield self.hold(doc_time)
                self.release(doc_OPD_PHC5)
                yield self.request(in_beds_PHC5)
                yield self.hold(sim.Triangular(60, 360, 180, 'minutes').bounded_sample(0))
                self.release(in_beds_PHC5)
            else:
                self.leave(medicine_q_PHC5)
                yield self.hold(doc_time)
                self.release(doc_OPD_PHC5)
                yield self.request(in_beds_PHC5, ipd_nurse_PHC5)
                temp = sim.Uniform(30, 60, 'minutes').sample()
                yield self.hold(temp)
                self.release(ipd_nurse_PHC5)
                yield self.hold(sim.Triangular(60, 360, 180, 'minutes').bounded_sample(0))
                self.release(in_beds_PHC5)
        else:
            self.enter_at_head(medicine_q_PHC5)
            entry_time2 = env.now()
            yield self.request(doc_OPD_PHC5, fail_delay=20)
            doc_time = sim.Uniform(10, 30, 'minutes').sample()
            t_bed = sim.Triangular(60, 360, 180, 'minutes').sample()
            t_nurse = sim.Uniform(30, 60, 'minutes').sample()
            phc1_doc_time_PHC5 += doc_time
            medicine_cons_time_PHC5 += doc_time
            if self.failed():
                self.leave(medicine_q_PHC5)
                exit_time2 = env.now()
                opd_q_waiting_time_PHC5.append(exit_time2 - entry_time2)  # stores waiting time in the queue
                yield self.request(ipd_nurse_PHC5)
                yield self.hold(t_nurse)
                self.release(ipd_nurse_PHC5)
                yield self.request(doc_OPD_PHC5)
                yield self.hold(doc_time)
                self.release(doc_OPD_PHC5)
                yield self.request(in_beds_PHC5)
                yield self.hold(t_bed)
                self.release(in_beds_PHC5)
                ipd_bed_time_PHC5 += t_bed
                ipd_MO_time_PHC5 += doc_time
                ipd_nurse_time_PHC5 += t_nurse
            else:
                self.leave(medicine_q_PHC5)
                exit_time3 = env.now()
                opd_q_waiting_time_PHC5.append(exit_time3 - entry_time2)  # stores waiting time in the queue
                yield self.hold(doc_time)
                self.release(doc_OPD_PHC5)
                yield self.request(in_beds_PHC5, ipd_nurse_PHC5)
                yield self.hold(t_nurse)
                self.release(ipd_nurse_PHC5)
                yield self.hold(t_bed)
                self.release(in_beds_PHC5)
                ipd_bed_time_PHC5 += t_bed
                ipd_MO_time_PHC5 += doc_time
                ipd_nurse_time_PHC5 += t_nurse


class CovidGenerator_PHC5(sim.Component):

    def process(self):
        global d1_PHC5
        global warmup_time
        global covid_iat_PHC5
        global phc_covid_iat
        global j

        while True:

            if env.now() < warmup_time:
                if 0 <= (env.now() - d1_PHC5 * 1440) < 480:
                    covid_PHC5()
                    yield self.hold(1440 / 3)
                    d1_PHC5 = int(env.now() / 1440)
                else:
                    yield self.hold(960)
                    d1_PHC5 = int(env.now() / 1440)

            else:
                a = phc_covid_iat[j]
                if 0 <= (env.now() - d1_PHC5 * 1440) < 480:
                    covid_PHC5()
                    yield self.hold(sim.Exponential(a).sample())
                    d1_PHC5 = int(env.now() / 1440)
                else:
                    yield self.hold(960)
                    d1_PHC5 = int(env.now() / 1440)


class covid_PHC5(sim.Component):

    def process(self):

        global home_refer_PHC5
        global chc_refer_PHC5
        global dh_refer_PHC5
        global isolation_ward_refer_PHC5
        global covid_patient_time_PHC5
        global covid_count_PHC5
        global warmup_time
        global ipd_nurse_PHC5
        global ipd_nurse_time_PHC5
        global doc_OPD_PHC5
        global MO_covid_time_PHC5
        global phc2chc_count_PHC5
        global warmup_time
        global home_isolation_PHC5

        global ICU_oxygen
        global phc5_to_cc_severe_case
        global phc5_to_cc_dist
        global phc5_2_cc

        if env.now() < warmup_time:
            covid_nurse_PHC5()
            covid_lab_PHC5()
            x = random.randint(0, 1000)
            if x <= 940:
                a = random.randint(0, 10)
                if a >= 9:
                    cc_isolation()
            elif 940 < x <= 980:
                pass
            else:
                pass
                #SevereCase()
        else:
            covid_count_PHC5 += 1
            covid_nurse_PHC5()
            covid_lab_PHC5()
            x = random.randint(0, 1000)
            if x <= 940:  # mild cases
                home_refer_PHC5 += 1
                a = random.randint(0, 100)
                if a >= 90:  # 10 % for institutional quarantine
                    isolation_ward_refer_PHC5 += 1
                    cc_isolation()
                else:
                    home_isolation_PHC5 += 1
            elif 940 < x <= 980:  # moderate cases
                chc_refer_PHC5 += 1
                phc2chc_count_PHC5 += 1
                CovidCare_chc2()
            else:  # severe case
                s = random.randint(0, 100)
                if s < 50:  # Type f patients
                    if ICU_oxygen.available_quantity() < 1:  # checks if there is a vacant bed in DH
                        phc5_to_cc_severe_case += 1
                        phc5_to_cc_dist.append(phc5_2_cc)
                        cc_Type_F()  # patient refered tpo CC
                    else:
                        DH_SevereTypeF()
                        dh_refer_PHC5 += 1  # Severe cases
                elif 50 <= s <= 74:  # E type patients
                    if ICU_ventilator.available_quantity() < 1:  # checks if there is a vacant bed in DH
                        cc_ICU_ward_TypeE()
                        phc5_to_cc_severe_case += 1
                    else:
                        DH_SevereTypeE()
                        dh_refer_PHC5 += 1  # Severe cases
                else:  # Type d patients
                    if ICU_ventilator.available_quantity() < 1:  # checks if there is a vacant bed in DH
                        cc_ventilator_TypeD()
                        phc5_to_cc_severe_case += 1
                    else:
                        dh_refer_PHC5 += 1  # Severe cases
                        DH_SevereTypeD()


class covid_nurse_PHC5(sim.Component):
    global lab_covidcount_PHC5

    def process(self):

        global warmup_time
        global ipd_nurse_PHC5
        global ipd_nurse_time_PHC5
        global lab_covidcount_PHC5

        if env.now() <= warmup_time:
            yield self.request(ipd_nurse_PHC5)
            yield self.hold(sim.Uniform(2, 3).sample())
            self.release(ipd_nurse_PHC5)
        else:
            lab_covidcount_PHC5 += 1
            yield self.request(ipd_nurse_PHC5)
            t = sim.Uniform(2, 3).sample()
            yield self.hold(t)
            ipd_nurse_time_PHC5 += t
            self.release(ipd_nurse_PHC5)


class covid_lab_PHC5(sim.Component):

    def process(self):

        global lab_technician_PHC5
        global lab_time_PHC5
        global lab_q_waiting_time_PHC5
        global warmup_time
        global lab_covidcount_PHC5

        if env.now() <= warmup_time:
            yield self.request(lab_technician_PHC5)
            yield self.hold(sim.Uniform(1, 2).sample())
            self.release(lab_technician_PHC5)
        else:
            lab_covidcount_PHC5 += 1
            yield self.request(lab_technician_PHC5)
            t = sim.Uniform(1, 2).sample()
            yield self.hold(t)
            lab_time_PHC5 += t
            self.release(lab_technician_PHC5)
            x = random.randint(0, 100)
            if x < 33:  # confirmed posiive
                covid_doc_PHC5()
            elif 33 < x < 67:  # symptomatic negative, retesting
                retesting_PHC5()
            else:
                Pharmacy_PHC5()


class retesting_PHC5(sim.Component):

    def process(self):

        global retesting_count_PHC5
        global warmup_time

        if env.now() <= warmup_time:
            yield self.hold(1440)
            covid_doc_PHC5()
        else:
            retesting_count_PHC5 += 1
            yield self.hold(1440)
            covid_doc_PHC5()


class covid_doc_PHC5(sim.Component):

    def process(self):
        global MO_covid_time_PHC5
        global doc_OPD_PHC5
        global warmup_time
        global covid_q_PHC5
        global covid_patient_time_PHC5
        global medicine_cons_time_PHC5

        if env.now() <= warmup_time:
            self.enter(covid_q_PHC5)
            yield self.request(doc_OPD_PHC5)
            self.leave(covid_q_PHC5)
            yield self.hold(sim.Uniform(3, 6).sample())
            self.release(doc_OPD_PHC5)
        else:
            in_time = env.now()
            self.enter(covid_q_PHC5)
            yield self.request(doc_OPD_PHC5)
            self.leave(covid_q_PHC5)
            t = sim.Uniform(3, 6).sample()
            yield self.hold(t)
            MO_covid_time_PHC5 += t
            medicine_cons_time_PHC5 += t
            self.release(doc_OPD_PHC5)
            covid_patient_time_PHC5 += env.now() - in_time


global l6  # temp lab count
l6 = 0
global o_PHC6  # temp opd count
o_PHC6 = 0


# PHC 6
class PatientGenerator_PHC6(sim.Component):
    global shift_PHC6
    shift_PHC6 = 0
    No_of_days_PHC6 = 0

    total_OPD_patients_PHC6 = 0

    def process(self):

        global env
        global warmup_time
        global opd_iat_PHC6
        global days_PHC6
        global medicine_cons_time_PHC6
        global shift_PHC6
        global phc1_doc_time_PHC6

        self.sim_time_PHC6 = 0  # local variable defined for dividing each day into shits
        self.z_PHC6 = 0
        self.admin_count_PHC6 = 0
        k_PHC6 = 0

        while self.z_PHC6 % 3 == 0:  # condition to run simulation for 8 hour shifts
            PatientGenerator_PHC6.No_of_days_PHC6 += 1  # class variable to track number of days passed
            while self.sim_time_PHC6 < 360:  # from morning 8 am to afternoon 2 pm (in minutes)
                if env.now() <= warmup_time:
                    pass
                else:
                    OPD_PHC6()
                o = sim.Exponential(opd_iat_PHC6).sample()
                yield self.hold(o)
                self.sim_time_PHC6 += o

            while 360 <= self.sim_time_PHC6 < 480:  # condition for admin work after opd hours are over
                k_PHC6 = int(sim.Normal(100, 20).bounded_sample(60, 140))
                """For sensitivity analysis. Admin work added to staff nurse rather than doctor"""
                if env.now() <= warmup_time:
                    pass
                else:
                    medicine_cons_time_PHC6 += k_PHC6  # conatns all doctor service times
                    phc1_doc_time_PHC6 += k_PHC6
                yield self.hold(120)
                self.sim_time_PHC6 = 481
            self.z_PHC6 += 3
            self.sim_time_PHC6 = 0
            # PatientGenerator1.No_of_shifts += 3
            yield self.hold(959)  # holds simulation for 2 shifts


class OPD_PHC6(sim.Component):
    Patient_log_PHC6 = {}

    def setup(self):

        self.dic = {}  # local dictionary for temporarily   storing generated patients
        # with attributes
        self.time_of_visit = [[0], [0], [0]]  # initializing for assigning time of visits
        self.regis_time = round(env.now())  # registration time is the current simulation time
        self.id = PatientGenerator_PHC6.total_OPD_patients_PHC6  # patient count is patient id
        self.age_random = random.randint(0, 1000)  # assigning age to population based on census 2011 gurgaon
        if self.age_random <= 578:
            self.age = random.randint(0, 30)
        else:
            self.age = random.randint(31, 100)
        self.sex = random.choice(["male", "female"])  # Equal probability of male and female patient
        # require lab tests
        self.lab_required = random.choice(["True", "False"])  # Considering nearly half of all the patients
        self.radiography_required = random.choice(["True", "False"])
        y = random.randint(0, 999)
        self.consultation = random.choice([y])  # for medicine, gynea, pead, denta
        self.visits_assigned = random.randint(1, 10)  # assigning number of visits visits
        self.dic = {"ID": self.id, "Age": self.age, "Sex": self.sex, "Lab": self.lab_required,
                    "Registration_Time": self.regis_time, "No_of_visits": self.visits_assigned,
                    "Time_of_visit": self.time_of_visit, "Radiography": self.radiography_required,
                    "Consultation": self.consultation}
        OPD_PHC6.Patient_log_PHC6[PatientGenerator_PHC6.total_OPD_patients_PHC6] = self.dic

        self.process()

    def process(self):

        global c6
        global medicine_q_PHC6
        global doc_OPD_PHC6
        global opd_ser_time_mean_PHC6
        global opd_ser_time_sd_PHC6
        global medicine_count_PHC6
        global medicine_cons_time_PHC6
        global opd_q_waiting_time_PHC6
        global ncd_count_PHC6
        global ncd_nurse_PHC6
        global ncd_time_PHC6
        global warmup_time
        global l6
        global phc1_doc_time_PHC6

        if env.now() <= warmup_time:
            p = random.randint(0, 10)
            if p < 2:
                COVID_OPD_PHC6()
            if OPD_PHC6.Patient_log_PHC6[PatientGenerator_PHC6.total_OPD_patients_PHC6]["Age"] > 30:
                yield self.request(ncd_nurse_PHC6)
                ncd_service = sim.Uniform(2, 5).sample()
                yield self.hold(ncd_service)
            self.enter(medicine_q_PHC6)
            yield self.request(doc_OPD_PHC6)
            self.leave(medicine_q_PHC6)
            o = sim.Normal(opd_ser_time_mean_PHC6, opd_ser_time_sd_PHC6).bounded_sample(0.3)
            yield self.hold(o)
            self.release(doc_OPD_PHC6)
            if OPD_PHC6.Patient_log_PHC6[PatientGenerator_PHC6.total_OPD_patients_PHC6]["Lab"] == "True":
                Lab_PHC6()
            Pharmacy_PHC6()
        else:
            l6 += 1
            medicine_count_PHC6 += 1
            p = random.randint(0, 10)
            if p < 2:
                COVID_OPD_PHC6()
            if OPD_PHC6.Patient_log_PHC6[PatientGenerator_PHC6.total_OPD_patients_PHC6]["Age"] > 30:
                ncd_count_PHC6 += 1
                yield self.request(ncd_nurse_PHC6)
                ncd_service = sim.Uniform(2, 5).sample()
                yield self.hold(ncd_service)
                ncd_time_PHC6 += ncd_service
            # doctor opd starts from here
            entry_time = env.now()
            self.enter(medicine_q_PHC6)
            yield self.request(doc_OPD_PHC6)
            self.leave(medicine_q_PHC6)
            exit_time = env.now()
            opd_q_waiting_time_PHC6.append(exit_time - entry_time)  # stores waiting time in the queue
            o = sim.Normal(opd_ser_time_mean_PHC6, opd_ser_time_sd_PHC6).bounded_sample(0.3)
            yield self.hold(o)
            phc1_doc_time_PHC6 += o
            medicine_cons_time_PHC6 += o
            self.release(doc_OPD_PHC6)
            # lab starts from here
            t = random.randint(0, 1000)
            # changed here
            if OPD_PHC6.Patient_log_PHC6[PatientGenerator_PHC6.total_OPD_patients_PHC6]["Lab"] == "True":
                Lab_PHC6()
            Pharmacy_PHC6()


class COVID_OPD_PHC6(sim.Component):

    def process(self):

        global ipd_nurse_PHC6
        global delivery_nurse_time_PHC6

        if env.now() <= warmup_time:
            yield self.request(ipd_nurse_PHC6)
            h1 = sim.Uniform(5, 10).sample()
            yield self.hold(h1)
            self.release(ipd_nurse_PHC6)
            OPD_covidtest_PHC6()
            yield self.hold(sim.Uniform(15, 30).sample())  # patient waits for the result
        else:
            yield self.request(ipd_nurse_PHC6)
            h1 = sim.Uniform(5, 10).sample()
            yield self.hold(h1)
            self.release(ipd_nurse_PHC6)
            delivery_nurse_time_PHC6 += h1
            OPD_covidtest_PHC6()
            yield self.hold(sim.Uniform(15, 30).sample())


class OPD_covidtest_PHC6(sim.Component):

    def process(self):
        global lab_covidcount_PHC6
        global lab_technician_PHC6
        global lab_time_PHC6
        global warmup_time

        if env.now() <= warmup_time:
            yield self.request(lab_technician_PHC6)
            t = sim.Uniform(1, 2).sample()
            yield self.hold(t)
            self.release(lab_technician_PHC6)
        else:
            lab_covidcount_PHC6 += 1
            yield self.request(lab_technician_PHC6)
            t = sim.Uniform(1, 2).sample()
            yield self.hold(t)
            lab_time_PHC6 += t
            self.release(lab_technician_PHC6)


class Pharmacy_PHC6(sim.Component):

    def process(self):

        global pharmacist_PHC6
        global pharmacy_time_PHC6
        global pharmacy_q_PHC6
        global pharmacy_q_waiting_time_PHC6
        global warmup_time
        global pharmacy_count_PHC6

        if env.now() < warmup_time:
            self.enter(pharmacy_q_PHC6)
            yield self.request(pharmacist_PHC6)
            self.leave(pharmacy_q_PHC6)
            # service_time = sim.Uniform(1, 2.5).sample()
            service_time = sim.Normal(2.083, 0.72).bounded_sample(.67)
            yield self.hold(service_time)
            self.release(pharmacist_PHC6)
        else:
            pharmacy_count_PHC6 += 1
            e1 = env.now()
            self.enter(pharmacy_q_PHC6)
            yield self.request((pharmacist_PHC6, 1))
            self.leave(pharmacy_q_PHC6)
            pharmacy_q_waiting_time_PHC6.append(env.now() - e1)
            service_time = sim.Normal(2.083, 0.72).bounded_sample(.67)
            yield self.hold(service_time)
            self.release((pharmacist_PHC6, 1))
            pharmacy_time_PHC6 += service_time


class Delivery_patient_generator_PHC6(sim.Component):
    Delivery_list = {}

    def process(self):
        global delivery_iat_PHC6
        global warmup_time
        global delivery_count_PHC6
        global days_PHC6
        global childbirth_count_PHC6
        global N_PHC6

        while True:
            if env.now() <= warmup_time:
                pass
            else:
                childbirth_count_PHC6 += 1
                self.registration_time = round(env.now())
                if 0 < (self.registration_time - N_PHC6 * 1440) < 480:
                    Delivery_with_doctor_PHC6(urgent=True)  # sets priority
                else:
                    Delivery_no_doc_PHC6(urgent=True)
            self.hold_time = sim.Exponential(delivery_iat_PHC6).sample()
            yield self.hold(self.hold_time)
            N_PHC6 = int(env.now() / 1440)


class Delivery_no_doc_PHC6(sim.Component):

    def process(self):
        global ipd_nurse_PHC6
        global ipd_nurse_PHC6
        global doc_OPD_PHC6
        global delivery_bed_PHC6
        global warmup_time
        global e_beds_PHC6
        global ipd_nurse_time_PHC6
        global MO_del_time_PHC6
        global in_beds_PHC6
        global delivery_nurse_time_PHC6
        global inpatient_del_count_PHC6
        global delivery_count_PHC6
        global emergency_bed_time_PHC6
        global ipd_bed_time_PHC6
        global emergency_nurse_time_PHC6
        global referred_PHC6
        global fail_count_PHC6

        if env.now() <= warmup_time:
            t_nurse = sim.Uniform(120, 240, 'minutes').sample()
            t_bed = sim.Uniform(360, 600).sample()
            yield self.request(ipd_nurse_PHC6)
            yield self.hold(t_nurse)
            self.release(ipd_nurse_PHC6)
            yield self.request(delivery_bed_PHC6, fail_delay=120)
            if self.failed():
                pass
            else:
                yield self.hold(t_bed)
                self.release(delivery_bed_PHC6)
                yield self.request(in_beds_PHC6)
                yield self.hold(sim.Uniform(240, 1440, 'minutes').bounded_sample(0))
                self.release(in_beds_PHC6)
        else:
            delivery_count_PHC6 += 1
            t_bed = sim.Uniform(360, 600).sample()  # delivery bed, nurse time
            t_nur = sim.Uniform(120, 240).sample()
            delivery_nurse_time_PHC6 += t_nur
            yield self.request(ipd_nurse_PHC6)
            yield self.hold(t_nur)
            self.release(ipd_nurse_PHC6)  # delivery nurse and delivery beds are released simultaneoulsy
            yield self.request(delivery_bed_PHC6, fail_delay=120)
            if self.failed():
                fail_count_PHC6 += 1
                delivery_count_PHC6 -= 1
                pass
            else:
                yield self.hold(t_bed)
                self.release(delivery_bed_PHC6)
                yield self.request(in_beds_PHC6)
                t_bed1 = sim.Uniform(240, 1440).sample()
                yield self.hold(t_bed1)
                ipd_bed_time_PHC6 += t_bed1


class Delivery_with_doctor_PHC6(sim.Component):

    def process(self):
        global ipd_nurse_PHC6
        global ipd_nurse_PHC6
        global doc_OPD_PHC6
        global delivery_bed_PHC6
        global warmup_time
        global e_beds_PHC6
        global ipd_nurse_time_PHC6
        global MO_del_time_PHC6
        global in_beds_PHC6
        global delivery_nurse_time_PHC6
        global inpatient_del_count_PHC6
        global delivery_count_PHC6
        global emergency_bed_time_PHC6
        global ipd_bed_time_PHC6
        global emergency_nurse_time_PHC6
        global referred_PHC6
        global fail_count_PHC6
        global opd_q_waiting_time_PHC6
        global phc1_doc_time_PHC6
        global medicine_cons_time_PHC6
        global medicine_q_PHC6

        if env.now() <= warmup_time:
            t_doc = sim.Uniform(30, 60).sample()
            t_bed = sim.Uniform(240, 360).sample()
            t_nurse = sim.Uniform(120, 240, 'minutes').sample()
            self.enter_at_head(medicine_q_PHC6)
            yield self.request(doc_OPD_PHC6, fail_delay=20)
            if self.failed():  # if doctor is busy staff nurse takes care
                self.leave(medicine_q_PHC6)
                yield self.request(ipd_nurse_PHC6)
                yield self.hold(t_nurse)
                self.release(ipd_nurse_PHC6)
                yield self.request(doc_OPD_PHC6)
                yield self.hold(t_doc)
                self.release(doc_OPD_PHC6)
                self.release(delivery_bed_PHC6)
                yield self.request(delivery_bed_PHC6, fail_delay=120)
                if self.failed():
                    pass
                else:
                    yield self.hold(sim.Uniform(6 * 60, 10 * 60, 'minutes').sample())
                    self.release(delivery_bed_PHC6)
                    yield self.request(in_beds_PHC6)
                    yield self.hold(sim.Uniform(240, 1440, 'minutes').sample())
                    self.release()
            else:
                self.leave(medicine_q_PHC6)
                yield self.hold(t_doc)
                self.release(doc_OPD_PHC6)
                yield self.request(ipd_nurse_PHC6)
                yield self.hold(t_nurse)
                self.release(ipd_nurse_PHC6)
                yield self.request(delivery_bed_PHC6)
                yield self.hold(sim.Uniform(6 * 60, 10 * 60, 'minutes').sample())
                self.release(delivery_bed_PHC6)
                yield self.request(in_beds_PHC6)
                yield self.hold(sim.Uniform(240, 1440, 'minutes').bounded_sample(0))  # holding patient for min 4 hours
                # to 48 hours
                self.release(in_beds_PHC6)
        else:
            delivery_count_PHC6 += 1
            entry_time1 = env.now()
            self.enter_at_head(medicine_q_PHC6)
            yield self.request(doc_OPD_PHC6, fail_delay=20)
            t_doc = sim.Uniform(30, 60).sample()
            t_bed = sim.Uniform(360, 600).sample()  # delivery bed, nurse time
            t_nur = sim.Uniform(120, 240).sample()
            delivery_nurse_time_PHC6 += t_nur
            phc1_doc_time_PHC6 += t_doc
            MO_del_time_PHC6 += t_doc  # changed here
            medicine_cons_time_PHC6 += t_doc
            if self.failed():  # if doctor is busy staff nurse takes care
                self.leave(medicine_q_PHC6)
                exit_time1 = env.now()
                opd_q_waiting_time_PHC6.append(exit_time1 - entry_time1)  # stores waiting time in the queue
                yield self.request(ipd_nurse_PHC6)
                yield self.hold(t_nur)
                self.release(ipd_nurse_PHC6)
                # changed here
                yield self.request(doc_OPD_PHC6)
                yield self.hold(t_doc)
                self.release(doc_OPD_PHC6)
                yield self.request(delivery_bed_PHC6, fail_delay=120)
                if self.failed():
                    fail_count_PHC6 += 1
                    delivery_count_PHC6 -= 1
                else:
                    yield self.hold(t_bed)
                    self.release(delivery_bed_PHC6)
                    # after delivery patient shifts to IPD and requests nurse and inpatient bed
                    # changed here, removed ipd nurse
                    yield self.request(in_beds_PHC6)
                    t_bed2 = sim.Uniform(240, 1440).sample()  # inpatient beds post delivery stay
                    yield self.hold(t_bed2)
                    ipd_bed_time_PHC6 += t_bed2
            else:
                self.leave(medicine_q_PHC6)
                exit_time1 = env.now()
                opd_q_waiting_time_PHC6.append(exit_time1 - entry_time1)  # stores waiting time in the queue
                yield self.hold(t_doc)
                self.release(doc_OPD_PHC6)
                yield self.request(ipd_nurse_PHC6)
                yield self.hold(t_nur)
                self.release(ipd_nurse_PHC6)  # delivery nurse and delivery beds are released simultaneoulsy
                yield self.request(delivery_bed_PHC6)
                yield self.hold(t_bed)
                self.release(delivery_bed_PHC6)
                yield self.request(in_beds_PHC6)
                t_bed1 = sim.Uniform(240, 1440).sample()
                yield self.hold(t_bed1)
                ipd_bed_time_PHC6 += t_bed1


class Lab_PHC6(sim.Component):

    def process(self):
        global lab_q_PHC6
        global lab_technician_PHC6
        global lab_time_PHC6
        global lab_q_waiting_time_PHC6
        global warmup_time
        global lab_count_PHC6
        global o_PHC6

        if env.now() <= warmup_time:
            self.enter(lab_q_PHC6)
            yield self.request(lab_technician_PHC6)
            self.leave(lab_q_PHC6)
            yp = (sim.Normal(3.456, .823).bounded_sample(2))
            y0 = yp
            yield self.hold(y0)
            self.release(lab_technician_PHC6)
        else:
            lab_count_PHC6 += 1
            self.enter(lab_q_PHC6)
            a0 = env.now()
            yield self.request(lab_technician_PHC6)
            self.leave(lab_q_PHC6)
            lab_q_waiting_time_PHC6.append(env.now() - a0)
            f1 = env.now()
            yp = (sim.Normal(3.456, .823).bounded_sample(2))
            y0 = yp
            yield self.hold(y0)
            self.release(lab_technician_PHC6)
            f2 = env.now()
            lab_time_PHC6 += f2 - f1
            o_PHC6 += 1


class IPD_PatientGenerator_PHC6(sim.Component):
    global IPD1_iat_PHC6
    global warmup_time
    IPD_List_PHC6 = {}  # log of all the IPD patients stored here
    patient_count_PHC6 = 0
    p_count_PHC6 = 0  # log of patients in each replication

    def process(self):
        global days_PHC6
        M = 0
        while True:
            if env.now() <= warmup_time:
                pass
            else:
                IPD_PatientGenerator_PHC6.patient_count_PHC6 += 1
                IPD_PatientGenerator_PHC6.p_count_PHC6 += 1
            self.registration_time = env.now()
            self.id = IPD_PatientGenerator_PHC6.patient_count_PHC6
            self.age = round(random.normalvariate(35, 8))
            self.sex = random.choice(["Male", "Female"])
            IPD_PatientGenerator_PHC6.IPD_List_PHC6[self.id] = [self.registration_time, self.id, self.age, self.sex]
            if 0 < (self.registration_time - M * 1440) < 480:
                IPD_with_doc_PHC6(urgent=True)
            else:
                IPD_no_doc_PHC6(urgent=True)
            self.hold_time_1 = sim.Exponential(IPD1_iat_PHC6).sample()
            yield self.hold(self.hold_time_1)
            M = int(env.now() / 1440)


class IPD_no_doc_PHC6(sim.Component):

    def process(self):
        global MO_ipd_PHC6
        global ipd_nurse_PHC6
        global in_beds_PHC6
        global ipd_nurse_time_PHC6
        global warmup_time
        global ipd_bed_time_PHC6
        global ipd_nurse_time_PHC6
        global medicine_q_PHC6
        global ipd_MO_time_PHC6

        if env.now() <= warmup_time:

            yield self.request(in_beds_PHC6, ipd_nurse_PHC6)
            temp = sim.Uniform(30, 60, 'minutes').sample()
            yield self.hold(temp)
            self.release(ipd_nurse_PHC6)
            yield self.hold(sim.Triangular(60, 360, 180, 'minutes').bounded_sample(0))
            self.release(in_beds_PHC6)
        else:
            t_bed = sim.Triangular(60, 360, 180, 'minutes').sample()
            t_nurse = sim.Uniform(30, 60, 'minutes').sample()
            yield self.request(in_beds_PHC6, ipd_nurse_PHC6)
            yield self.hold(t_nurse)
            self.release(ipd_nurse_PHC6)
            yield self.hold(t_bed)
            self.release(in_beds_PHC6)
            ipd_bed_time_PHC6 += t_bed
            ipd_nurse_time_PHC6 += t_nurse


class IPD_with_doc_PHC6(sim.Component):

    def process(self):
        global MO_ipd_PHC6
        global ipd_nurse_PHC6
        global in_beds_PHC6
        global MO_ipd_time_PHC6
        global ipd_nurse_time_PHC6
        global warmup_time
        global ipd_bed_time_PHC6
        global ipd_nurse_time_PHC6
        global emergency_refer_PHC6
        global medicine_q_PHC6
        global ipd_MO_time_PHC6
        global opd_q_waiting_time_PHC6
        global phc1_doc_time_PHC6
        global medicine_cons_time_PHC6

        if env.now() <= warmup_time:
            self.enter_at_head(medicine_q_PHC6)
            yield self.request(doc_OPD_PHC6, fail_delay=20)
            doc_time = round(sim.Uniform(10, 30, 'minutes').sample())
            if self.failed():
                self.leave(medicine_q_PHC6)
                yield self.request(ipd_nurse_PHC6)
                temp = sim.Uniform(30, 60, 'minutes').sample()
                yield self.hold(temp)
                self.release(ipd_nurse_PHC6)
                yield self.request(doc_OPD_PHC6)
                yield self.hold(doc_time)
                self.release(doc_OPD_PHC6)
                yield self.request(in_beds_PHC6)
                yield self.hold(sim.Triangular(60, 360, 180, 'minutes').bounded_sample(0))
                self.release(in_beds_PHC6)
            else:
                self.leave(medicine_q_PHC6)
                yield self.hold(doc_time)
                self.release(doc_OPD_PHC6)
                yield self.request(in_beds_PHC6, ipd_nurse_PHC6)
                temp = sim.Uniform(30, 60, 'minutes').sample()
                yield self.hold(temp)
                self.release(ipd_nurse_PHC6)
                yield self.hold(sim.Triangular(60, 360, 180, 'minutes').bounded_sample(0))
                self.release(in_beds_PHC6)
        else:
            self.enter_at_head(medicine_q_PHC6)
            entry_time2 = env.now()
            yield self.request(doc_OPD_PHC6, fail_delay=20)
            doc_time = sim.Uniform(10, 30, 'minutes').sample()
            t_bed = sim.Triangular(60, 360, 180, 'minutes').sample()
            t_nurse = sim.Uniform(30, 60, 'minutes').sample()
            phc1_doc_time_PHC6 += doc_time
            medicine_cons_time_PHC6 += doc_time
            if self.failed():
                self.leave(medicine_q_PHC6)
                exit_time2 = env.now()
                opd_q_waiting_time_PHC6.append(exit_time2 - entry_time2)  # stores waiting time in the queue
                yield self.request(ipd_nurse_PHC6)
                yield self.hold(t_nurse)
                self.release(ipd_nurse_PHC6)
                yield self.request(doc_OPD_PHC6)
                yield self.hold(doc_time)
                self.release(doc_OPD_PHC6)
                yield self.request(in_beds_PHC6)
                yield self.hold(t_bed)
                self.release(in_beds_PHC6)
                ipd_bed_time_PHC6 += t_bed
                ipd_MO_time_PHC6 += doc_time
                ipd_nurse_time_PHC6 += t_nurse
            else:
                self.leave(medicine_q_PHC6)
                exit_time3 = env.now()
                opd_q_waiting_time_PHC6.append(exit_time3 - entry_time2)  # stores waiting time in the queue
                yield self.hold(doc_time)
                self.release(doc_OPD_PHC6)
                yield self.request(in_beds_PHC6, ipd_nurse_PHC6)
                yield self.hold(t_nurse)
                self.release(ipd_nurse_PHC6)
                yield self.hold(t_bed)
                self.release(in_beds_PHC6)
                ipd_bed_time_PHC6 += t_bed
                ipd_MO_time_PHC6 += doc_time
                ipd_nurse_time_PHC6 += t_nurse


class ANC_PHC6(sim.Component):
    global ANC_iat_PHC6
    global days_PHC6
    days_PHC6 = 0
    env = sim.Environment()
    No_of_shifts_PHC6 = 0  # tracks number of shifts completed during the simulation time
    No_of_days_PHC6 = 0
    ANC_List_PHC6 = {}
    anc_count_PHC6 = 0
    ANC_p_count_PHC6 = 0

    def process(self):

        global days_PHC6

        while True:  # condition to run simulation for 8 hour shifts
            x = env.now() - 1440 * days_PHC6
            if 0 <= x < 480:
                ANC_PHC6.anc_count_PHC6 += 1  # counts overall patients throghout simulation
                ANC_PHC6.ANC_p_count_PHC6 += 1  # counts patients in each replication
                id = ANC_PHC6.anc_count_PHC6
                age = 223
                day_of_registration = ANC_PHC6.No_of_days_PHC6
                visit = 1
                x0 = round(env.now())
                x1 = x0 + 14 * 7 * 24 * 60
                x2 = x0 + 20 * 7 * 24 * 60
                x3 = x0 + 24 * 7 * 24 * 60
                scheduled_visits = [[0], [0], [0], [0]]
                scheduled_visits[0] = x0
                scheduled_visits[1] = x1
                scheduled_visits[2] = x2
                scheduled_visits[3] = x3
                dic = {"ID": id, "Age": age, "Visit Number": visit, "Registration day": day_of_registration,
                       "Scheduled Visit": scheduled_visits}
                ANC_PHC6.ANC_List_PHC6[id] = dic
                ANC_Checkup_PHC6()
                ANC_followup_PHC6(at=ANC_PHC6.ANC_List_PHC6[id]["Scheduled Visit"][1])
                ANC_followup_PHC6(at=ANC_PHC6.ANC_List_PHC6[id]["Scheduled Visit"][2])
                ANC_followup_PHC6(at=ANC_PHC6.ANC_List_PHC6[id]["Scheduled Visit"][3])
                hold_time = sim.Exponential(ANC_iat_PHC6).sample()
                yield self.hold(hold_time)
            else:
                yield self.hold(960)
                days_PHC6 = int(env.now() / 1440)  # holds simulation for 2 shifts



class ANC_Checkup_PHC6(sim.Component):
    anc_checkup_count_PHC6 = 0

    def process(self):

        global warmup_time
        global ipd_nurse_PHC6
        global delivery_nurse_time_PHC6
        global lab_q_PHC6
        global lab_technician_PHC6
        global lab_time_PHC6
        global lab_q_waiting_time_PHC6
        global warmup_time
        global lab_count_PHC6

        if env.now() <= warmup_time:
            yield self.request(ipd_nurse_PHC6)
            temp = sim.Triangular(8, 20.6, 12.3).sample()
            yield self.hold(temp)  # time taken from a study on ANC visits in Tanzania
            self.release(ipd_nurse_PHC6)
            self.enter(lab_q_PHC6)
            yield self.request(lab_technician_PHC6)
            self.leave(lab_q_PHC6)
            yp = (sim.Normal(5, 1).bounded_sample())
            y0 = yp
            yield self.hold(y0)
            self.release(lab_technician_PHC6)
        else:
            ANC_Checkup_PHC6.anc_checkup_count_PHC6 += 1
            yield self.request(ipd_nurse_PHC6)
            temp = sim.Triangular(8, 20.6, 12.3).sample()
            delivery_nurse_time_PHC6 += temp
            yield self.hold(temp)  # time taken from a study on ANC visits in Tanzania
            self.release(ipd_nurse_PHC6)
            lab_count_PHC6 += 1
            # changed here
            a0 = env.now()
            self.enter(lab_q_PHC6)
            yield self.request(lab_technician_PHC6)
            self.leave(lab_q_PHC6)
            lab_q_waiting_time_PHC6.append(env.now() - a0)
            yp = (sim.Normal(5, 1).bounded_sample())
            y0 = yp
            yield self.hold(y0)
            self.release(lab_technician_PHC6)
            lab_time_PHC6 += y0


class ANC_followup_PHC6(sim.Component):
    followup_count = 0

    def process(self):

        global warmup_time
        global ipd_nurse_PHC6
        global q_ANC_PHC6  # need change here and corrosponding arrays
        global delivery_nurse_time_PHC6
        global lab_time_PHC6
        global lab_q_waiting_time_PHC6

        if env.now() <= warmup_time:
            for key in ANC_PHC6.ANC_List_PHC6:  # for identifying and updating ANC visit number
                x0 = env.now()
                x1 = ANC_PHC6.ANC_List_PHC6[key]["Scheduled Visit"][1]
                x2 = ANC_PHC6.ANC_List_PHC6[key]["Scheduled Visit"][2]
                x3 = ANC_PHC6.ANC_List_PHC6[key]["Scheduled Visit"][3]
                if 0 <= (x1 - x0) < 481:
                    ANC_PHC6.ANC_List_PHC6[key]["Scheduled Visit"][1] = float("inf")
                    ANC_PHC6.ANC_List_PHC6[key]["Visit Number"] = 2
                elif 0 <= (x2 - x0) < 481:
                    ANC_PHC6.ANC_List_PHC6[key]["Scheduled Visit"][2] = float("inf")
                    ANC_PHC6.ANC_List_PHC6[key]["Visit Number"] = 3
                elif 0 <= (x3 - x0) < 481:
                    ANC_PHC6.ANC_List_PHC6[key]["Scheduled Visit"][3] = float("inf")
                    ANC_PHC6.ANC_List_PHC6[key]["Visit Number"] = 4

            yield self.request(ipd_nurse_PHC6)
            temp = sim.Triangular(3.33, 13.16, 6.50).sample()
            yield self.hold(temp)
            self.release(ipd_nurse_PHC6)
            self.enter(lab_q_PHC6)
            yield self.request(lab_technician_PHC6)
            self.leave(lab_q_PHC6)
            yp = (sim.Normal(3.456, .823).bounded_sample(2))
            y0 = yp
            yield self.hold(y0)
            self.release(lab_technician_PHC6)

        else:
            for key in ANC_PHC6.ANC_List_PHC6:  # for identifying and updating ANC visit number
                x0 = env.now()
                x1 = ANC_PHC6.ANC_List_PHC6[key]["Scheduled Visit"][1]
                x2 = ANC_PHC6.ANC_List_PHC6[key]["Scheduled Visit"][2]
                x3 = ANC_PHC6.ANC_List_PHC6[key]["Scheduled Visit"][3]
                if 0 <= (x1 - x0) < 481:
                    ANC_PHC6.ANC_List_PHC6[key]["Scheduled Visit"][1] = float("inf")
                    ANC_PHC6.ANC_List_PHC6[key]["Visit Number"] = 2
                elif 0 <= (x2 - x0) < 481:
                    ANC_PHC6.ANC_List_PHC6[key]["Scheduled Visit"][2] = float("inf")
                    ANC_PHC6.ANC_List_PHC6[key]["Visit Number"] = 3
                elif 0 <= (x3 - x0) < 481:
                    ANC_PHC6.ANC_List_PHC6[key]["Scheduled Visit"][3] = float("inf")
                    ANC_PHC6.ANC_List_PHC6[key]["Visit Number"] = 4

            yield self.request(ipd_nurse_PHC6)
            temp = sim.Triangular(3.33, 13.16, 6.50).sample()
            delivery_nurse_time_PHC6 += temp
            yield self.hold(temp)
            self.release(ipd_nurse_PHC6)
            a0 = env.now()
            self.enter(lab_q_PHC6)
            yield self.request(lab_technician_PHC6)
            self.leave(lab_q_PHC6)
            lab_q_waiting_time_PHC6.append(env.now() - a0)
            yp = (sim.Normal(3.456, .823).bounded_sample(2))
            y0 = yp
            yield self.hold(y0)
            self.release(lab_technician_PHC6)
            lab_time_PHC6 += y0


class CovidGenerator_PHC6(sim.Component):

    def process(self):
        global d1_PHC6
        global warmup_time
        global covid_iat_PHC6
        global phc_covid_iat
        global j

        while True:

            if env.now() < warmup_time:
                if 0 <= (env.now() - d1_PHC6 * 1440) < 480:
                    covid_PHC6()
                    yield self.hold(1440 / 3)
                    d1_PHC6 = int(env.now() / 1440)
                else:
                    yield self.hold(960)
                    d1_PHC6 = int(env.now() / 1440)

            else:
                a = phc_covid_iat[j]
                if 0 <= (env.now() - d1_PHC6 * 1440) < 480:
                    covid_PHC6()
                    yield self.hold(sim.Exponential(a).sample())
                    d1_PHC6 = int(env.now() / 1440)
                else:
                    yield self.hold(960)
                    d1_PHC6 = int(env.now() / 1440)


class covid_PHC6(sim.Component):

    def process(self):

        global home_refer_PHC6
        global chc_refer_PHC6
        global dh_refer_PHC6
        global isolation_ward_refer_PHC6
        global covid_patient_time_PHC6
        global covid_count_PHC6
        global warmup_time
        global ipd_nurse_PHC6
        global ipd_nurse_time_PHC6
        global doc_OPD_PHC6
        global MO_covid_time_PHC6
        global phc2chc_count_PHC6
        global warmup_time
        global home_isolation_PHC6

        global ICU_oxygen
        global phc6_to_cc_severe_case
        global phc6_to_cc_dist
        global phc6_2_cc

        if env.now() < warmup_time:
            covid_nurse_PHC6()
            covid_lab_PHC6()
            x = random.randint(0, 1000)
            if x <= 940:
                a = random.randint(0, 10)
                if a >= 9:
                    cc_isolation()
            elif 940 < x <= 980:
                pass
            # CovidCare_chc2()
            else:
                pass
                #SevereCase()
        else:
            covid_count_PHC6 += 1
            covid_nurse_PHC6()
            covid_lab_PHC6()
            x = random.randint(0, 1000)
            if x <= 940:  # mild cases
                home_refer_PHC6 += 1
                a = random.randint(0, 100)
                if a >= 90:  # 10 % for institutional quarantine
                    isolation_ward_refer_PHC6 += 1
                    cc_isolation()
                else:
                    home_isolation_PHC6 += 1
            elif 940 < x <= 980:  # moderate cases
                chc_refer_PHC6 += 1
                phc2chc_count_PHC6 += 1
                CovidCare_chc2()
            else:  # severe case
                s = random.randint(0, 100)
                if s < 50:  # Type f patients
                    if ICU_oxygen.available_quantity() < 1:  # checks if there is a vacant bed in DH
                        phc6_to_cc_severe_case += 1
                        phc6_to_cc_dist.append(phc6_2_cc)
                        cc_Type_F()  # patient refered tpo CC
                    else:
                        DH_SevereTypeF()
                        dh_refer_PHC6 += 1  # Severe cases
                elif 50 <= s <= 74:  # E type patients
                    if ICU_ventilator.available_quantity() < 1:  # checks if there is a vacant bed in DH
                        cc_ICU_ward_TypeE()
                        phc6_to_cc_severe_case += 1
                    else:
                        DH_SevereTypeE()
                        dh_refer_PHC6 += 1  # Severe cases
                else:  # Type d patients
                    if ICU_ventilator.available_quantity() < 1:  # checks if there is a vacant bed in DH
                        cc_ventilator_TypeD()
                        phc6_to_cc_severe_case += 1
                    else:
                        dh_refer_PHC6 += 1  # Severe cases
                        DH_SevereTypeD()


class covid_nurse_PHC6(sim.Component):
    global lab_covidcount_PHC6

    def process(self):

        global warmup_time
        global ipd_nurse_PHC6
        global ipd_nurse_time_PHC6
        global lab_covidcount_PHC6

        if env.now() <= warmup_time:
            yield self.request(ipd_nurse_PHC6)
            yield self.hold(sim.Uniform(2, 3).sample())
            self.release(ipd_nurse_PHC6)
        else:
            lab_covidcount_PHC6 += 1
            yield self.request(ipd_nurse_PHC6)
            t = sim.Uniform(2, 3).sample()
            yield self.hold(t)
            ipd_nurse_time_PHC6 += t
            self.release(ipd_nurse_PHC6)


class covid_lab_PHC6(sim.Component):

    def process(self):

        global lab_technician_PHC6
        global lab_time_PHC6
        global lab_q_waiting_time_PHC6
        global warmup_time
        global lab_covidcount_PHC6

        if env.now() <= warmup_time:
            yield self.request(lab_technician_PHC6)
            yield self.hold(sim.Uniform(1, 2).sample())
            self.release(lab_technician_PHC6)
        else:
            lab_covidcount_PHC6 += 1
            yield self.request(lab_technician_PHC6)
            t = sim.Uniform(1, 2).sample()
            yield self.hold(t)
            lab_time_PHC6 += t
            self.release(lab_technician_PHC6)
            x = random.randint(0, 100)
            if x < 33:  # confirmed posiive
                covid_doc_PHC6()
            elif 33 < x < 67:  # symptomatic negative, retesting
                retesting_PHC6()
            else:
                Pharmacy_PHC6()


class retesting_PHC6(sim.Component):

    def process(self):

        global retesting_count_PHC6
        global warmup_time

        if env.now() <= warmup_time:
            yield self.hold(1440)
            covid_doc_PHC6()
        else:
            retesting_count_PHC6 += 1
            yield self.hold(1440)
            covid_doc_PHC6()


class covid_doc_PHC6(sim.Component):

    def process(self):
        global MO_covid_time_PHC6
        global doc_OPD_PHC6
        global warmup_time
        global covid_q_PHC6
        global covid_patient_time_PHC6
        global medicine_cons_time_PHC6

        if env.now() <= warmup_time:
            self.enter(covid_q_PHC6)
            yield self.request(doc_OPD_PHC6)
            self.leave(covid_q_PHC6)
            yield self.hold(sim.Uniform(3, 6).sample())
            self.release(doc_OPD_PHC6)
        else:
            in_time = env.now()
            self.enter(covid_q_PHC6)
            yield self.request(doc_OPD_PHC6)
            self.leave(covid_q_PHC6)
            t = sim.Uniform(3, 6).sample()
            yield self.hold(t)
            MO_covid_time_PHC6 += t
            medicine_cons_time_PHC6 += t
            self.release(doc_OPD_PHC6)
            covid_patient_time_PHC6 += env.now() - in_time


global l7  # temp lab count
l7 = 0
global o_PHC7  # temp opd count
o_PHC7 = 0


# PHC 7
class PatientGenerator_PHC7(sim.Component):
    global shift_PHC7
    shift_PHC7 = 0
    No_of_days_PHC7 = 0

    total_OPD_patients_PHC7 = 0

    def process(self):

        global env
        global warmup_time
        global opd_iat_PHC7
        global days_PHC7
        global medicine_cons_time_PHC7
        global shift_PHC7
        global phc1_doc_time_PHC7

        self.sim_time_PHC7 = 0  # local variable defined for dividing each day into shits
        self.z_PHC7 = 0
        self.admin_count_PHC7 = 0
        k_PHC7 = 0

        while self.z_PHC7 % 3 == 0:  # condition to run simulation for 8 hour shifts
            PatientGenerator_PHC7.No_of_days_PHC7 += 1  # class variable to track number of days passed
            while self.sim_time_PHC7 < 360:  # from morning 8 am to afternoon 2 pm (in minutes)
                if env.now() <= warmup_time:
                    pass
                else:
                    OPD_PHC7()
                o = sim.Exponential(opd_iat_PHC7).sample()
                yield self.hold(o)
                self.sim_time_PHC7 += o

            while 360 <= self.sim_time_PHC7 < 480:  # condition for admin work after opd hours are over
                k_PHC7 = int(sim.Normal(100, 20).bounded_sample(60, 140))
                """For sensitivity analysis. Admin work added to staff nurse rather than doctor"""
                if env.now() <= warmup_time:
                    pass
                else:
                    medicine_cons_time_PHC7 += k_PHC7  # conatns all doctor service times
                    phc1_doc_time_PHC7 += k_PHC7
                yield self.hold(120)
                self.sim_time_PHC7 = 481
            self.z_PHC7 += 3
            self.sim_time_PHC7 = 0
            # PatientGenerator1.No_of_shifts += 3
            yield self.hold(959)  # holds simulation for 2 shifts


class OPD_PHC7(sim.Component):
    Patient_log_PHC7 = {}

    def setup(self):

        self.dic = {}  # local dictionary for temporarily   storing generated patients
        # with attributes
        self.time_of_visit = [[0], [0], [0]]  # initializing for assigning time of visits
        self.regis_time = round(env.now())  # registration time is the current simulation time
        self.id = PatientGenerator_PHC7.total_OPD_patients_PHC7  # patient count is patient id
        self.age_random = random.randint(0, 1000)  # assigning age to population based on census 2011 gurgaon
        if self.age_random <= 578:
            self.age = random.randint(0, 30)
        else:
            self.age = random.randint(31, 100)
        self.sex = random.choice(["male", "female"])  # Equal probability of male and female patient
        # require lab tests
        self.lab_required = random.choice(["True", "False"])  # Considering nearly half of all the patients
        self.radiography_required = random.choice(["True", "False"])
        y = random.randint(0, 999)
        self.consultation = random.choice([y])  # for medicine, gynea, pead, denta
        self.visits_assigned = random.randint(1, 10)  # assigning number of visits visits
        self.dic = {"ID": self.id, "Age": self.age, "Sex": self.sex, "Lab": self.lab_required,
                    "Registration_Time": self.regis_time, "No_of_visits": self.visits_assigned,
                    "Time_of_visit": self.time_of_visit, "Radiography": self.radiography_required,
                    "Consultation": self.consultation}
        OPD_PHC7.Patient_log_PHC7[PatientGenerator_PHC7.total_OPD_patients_PHC7] = self.dic

        self.process()

    def process(self):

        global c7
        global medicine_q_PHC7
        global doc_OPD_PHC7
        global opd_ser_time_mean_PHC7
        global opd_ser_time_sd_PHC7
        global medicine_count_PHC7
        global medicine_cons_time_PHC7
        global opd_q_waiting_time_PHC7
        global ncd_count_PHC7
        global ncd_nurse_PHC7
        global ncd_time_PHC7
        global warmup_time
        global l7
        global phc1_doc_time_PHC7

        if env.now() <= warmup_time:
            p = random.randint(0, 10)
            if p < 2:
                COVID_OPD_PHC7()
            if OPD_PHC7.Patient_log_PHC7[PatientGenerator_PHC7.total_OPD_patients_PHC7]["Age"] > 30:
                yield self.request(ncd_nurse_PHC7)
                ncd_service = sim.Uniform(2, 5).sample()
                yield self.hold(ncd_service)
            self.enter(medicine_q_PHC7)
            yield self.request(doc_OPD_PHC7)
            self.leave(medicine_q_PHC7)
            o = sim.Normal(opd_ser_time_mean_PHC7, opd_ser_time_sd_PHC7).bounded_sample(0.3)
            yield self.hold(o)
            self.release(doc_OPD_PHC7)
            if OPD_PHC7.Patient_log_PHC7[PatientGenerator_PHC7.total_OPD_patients_PHC7]["Lab"] == "True":
                Lab_PHC7()
            Pharmacy_PHC7()
        else:
            l7 += 1
            medicine_count_PHC7 += 1
            p = random.randint(0, 10)
            if p < 2:
                COVID_OPD_PHC7()
            if OPD_PHC7.Patient_log_PHC7[PatientGenerator_PHC7.total_OPD_patients_PHC7]["Age"] > 30:
                ncd_count_PHC7 += 1
                yield self.request(ncd_nurse_PHC7)
                ncd_service = sim.Uniform(2, 5).sample()
                yield self.hold(ncd_service)
                ncd_time_PHC7 += ncd_service
            # doctor opd starts from here
            entry_time = env.now()
            self.enter(medicine_q_PHC7)
            yield self.request(doc_OPD_PHC7)
            self.leave(medicine_q_PHC7)
            exit_time = env.now()
            opd_q_waiting_time_PHC7.append(exit_time - entry_time)  # stores waiting time in the queue
            o = sim.Normal(opd_ser_time_mean_PHC7, opd_ser_time_sd_PHC7).bounded_sample(0.3)
            yield self.hold(o)
            phc1_doc_time_PHC7 += o
            medicine_cons_time_PHC7 += o
            self.release(doc_OPD_PHC7)
            # lab starts from here
            t = random.randint(0, 1000)
            # changed here
            if OPD_PHC7.Patient_log_PHC7[PatientGenerator_PHC7.total_OPD_patients_PHC7]["Lab"] == "True":
                Lab_PHC7()
            Pharmacy_PHC7()


class COVID_OPD_PHC7(sim.Component):

    def process(self):

        global ipd_nurse_PHC7
        global ipd_nurse_time_PHC7

        if env.now() <= warmup_time:
            yield self.request(ipd_nurse_PHC7)
            h1 = sim.Uniform(5, 10).sample()
            yield self.hold(h1)
            self.release(ipd_nurse_PHC7)
            OPD_covidtest_PHC7()
            yield self.hold(sim.Uniform(15, 30).sample())  # patient waits for the result
        else:
            yield self.request(ipd_nurse_PHC7)
            h1 = sim.Uniform(5, 10).sample()
            yield self.hold(h1)
            self.release(ipd_nurse_PHC7)
            ipd_nurse_time_PHC7 += h1
            OPD_covidtest_PHC7()
            yield self.hold(sim.Uniform(15, 30).sample())


class OPD_covidtest_PHC7(sim.Component):

    def process(self):
        global lab_covidcount_PHC7
        global lab_technician_PHC7
        global lab_time_PHC7
        global warmup_time

        if env.now() <= warmup_time:
            yield self.request(lab_technician_PHC7)
            t = sim.Uniform(1, 2).sample()
            yield self.hold(t)
            self.release(lab_technician_PHC7)
        else:
            lab_covidcount_PHC7 += 1
            yield self.request(lab_technician_PHC7)
            t = sim.Uniform(1, 2).sample()
            yield self.hold(t)
            lab_time_PHC7 += t
            self.release(lab_technician_PHC7)


class Pharmacy_PHC7(sim.Component):

    def process(self):

        global pharmacist_PHC7
        global pharmacy_time_PHC7
        global pharmacy_q_PHC7
        global pharmacy_q_waiting_time_PHC7
        global warmup_time
        global pharmacy_count_PHC7

        if env.now() < warmup_time:
            self.enter(pharmacy_q_PHC7)
            yield self.request(pharmacist_PHC7)
            self.leave(pharmacy_q_PHC7)
            # service_time = sim.Uniform(1, 2.5).sample()
            service_time = sim.Normal(2.083, 0.72).bounded_sample(.67)
            yield self.hold(service_time)
            self.release(pharmacist_PHC7)
        else:
            pharmacy_count_PHC7 += 1
            e1 = env.now()
            self.enter(pharmacy_q_PHC7)
            yield self.request((pharmacist_PHC7, 1))
            self.leave(pharmacy_q_PHC7)
            pharmacy_q_waiting_time_PHC7.append(env.now() - e1)
            service_time = sim.Normal(2.083, 0.72).bounded_sample(.67)
            yield self.hold(service_time)
            self.release((pharmacist_PHC7, 1))
            pharmacy_time_PHC7 += service_time


class Lab_PHC7(sim.Component):

    def process(self):
        global lab_q_PHC7
        global lab_technician_PHC7
        global lab_time_PHC7
        global lab_q_waiting_time_PHC7
        global warmup_time
        global lab_count_PHC7
        global o_PHC7

        if env.now() <= warmup_time:
            self.enter(lab_q_PHC7)
            yield self.request(lab_technician_PHC7)
            self.leave(lab_q_PHC7)
            yp = (sim.Normal(3.456, .823).bounded_sample(2))
            y0 = yp
            yield self.hold(y0)
            self.release(lab_technician_PHC7)
        else:
            lab_count_PHC7 += 1
            self.enter(lab_q_PHC7)
            a0 = env.now()
            yield self.request(lab_technician_PHC7)
            self.leave(lab_q_PHC7)
            lab_q_waiting_time_PHC7.append(env.now() - a0)
            f1 = env.now()
            yp = (sim.Normal(3.456, .823).bounded_sample(2))
            y0 = yp
            yield self.hold(y0)
            self.release(lab_technician_PHC7)
            f2 = env.now()
            lab_time_PHC7 += f2 - f1
            o_PHC7 += 1


class IPD_PatientGenerator_PHC7(sim.Component):
    global IPD1_iat_PHC7
    global warmup_time
    IPD_List_PHC7 = {}  # log of all the IPD patients stored here
    patient_count_PHC7 = 0
    p_count_PHC7 = 0  # log of patients in each replication

    def process(self):
        global days_PHC7
        M = 0
        while True:
            if env.now() <= warmup_time:
                pass
            else:
                IPD_PatientGenerator_PHC7.patient_count_PHC7 += 1
                IPD_PatientGenerator_PHC7.p_count_PHC7 += 1
            self.registration_time = env.now()
            self.id = IPD_PatientGenerator_PHC7.patient_count_PHC7
            self.age = round(random.normalvariate(35, 8))
            self.sex = random.choice(["Male", "Female"])
            IPD_PatientGenerator_PHC7.IPD_List_PHC7[self.id] = [self.registration_time, self.id, self.age, self.sex]
            if 0 < (self.registration_time - M * 1440) < 480:
                IPD_with_doc_PHC7(urgent=True)
            else:
                pass
            self.hold_time_1 = sim.Exponential(IPD1_iat_PHC7).sample()
            yield self.hold(self.hold_time_1)
            M = int(env.now() / 1440)


class IPD_with_doc_PHC7(sim.Component):

    def process(self):
        global MO_ipd_PHC7
        global ipd_nurse_PHC7
        global in_beds_PHC7
        global MO_ipd_time_PHC7
        global ipd_nurse_time_PHC7
        global warmup_time
        global ipd_bed_time_PHC7
        global ipd_nurse_time_PHC7
        global emergency_refer_PHC7  # Changed here
        global medicine_q_PHC7
        global ipd_MO_time_PHC7
        global opd_q_waiting_time_PHC7
        global phc1_doc_time_PHC7
        global medicine_cons_time_PHC7

        if env.now() <= warmup_time:
            self.enter_at_head(medicine_q_PHC7)
            yield self.request(doc_OPD_PHC7, fail_delay=20)
            doc_time = round(sim.Uniform(10, 30, 'minutes').sample())
            if self.failed():
                self.leave(medicine_q_PHC7)
                yield self.request(ipd_nurse_PHC7)
                temp = sim.Uniform(30, 60, 'minutes').sample()
                yield self.hold(temp)
                self.release(ipd_nurse_PHC7)
                yield self.request(doc_OPD_PHC7)
                yield self.hold(doc_time)
                self.release(doc_OPD_PHC7)
                yield self.request(in_beds_PHC7)
                yield self.hold(sim.Triangular(60, 360, 180, 'minutes').bounded_sample(0))
                self.release(in_beds_PHC7)
            else:
                self.leave(medicine_q_PHC7)
                yield self.hold(doc_time)
                self.release(doc_OPD_PHC7)
                yield self.request(in_beds_PHC7, ipd_nurse_PHC7)
                temp = sim.Uniform(30, 60, 'minutes').sample()
                yield self.hold(temp)
                self.release(ipd_nurse_PHC7)
                yield self.hold(sim.Triangular(60, 360, 180, 'minutes').bounded_sample(0))
                self.release(in_beds_PHC7)
        else:
            self.enter_at_head(medicine_q_PHC7)
            entry_time2 = env.now()
            yield self.request(doc_OPD_PHC7, fail_delay=20)
            doc_time = sim.Uniform(10, 30, 'minutes').sample()
            t_bed = sim.Triangular(60, 360, 180, 'minutes').sample()
            t_nurse = sim.Uniform(30, 60, 'minutes').sample()
            phc1_doc_time_PHC7 += doc_time
            medicine_cons_time_PHC7 += doc_time
            if self.failed():
                self.leave(medicine_q_PHC7)
                exit_time2 = env.now()
                opd_q_waiting_time_PHC7.append(exit_time2 - entry_time2)  # stores waiting time in the queue
                yield self.request(ipd_nurse_PHC7)
                yield self.hold(t_nurse)
                self.release(ipd_nurse_PHC7)
                yield self.request(doc_OPD_PHC7)
                yield self.hold(doc_time)
                self.release(doc_OPD_PHC7)
                yield self.request(in_beds_PHC7)
                yield self.hold(t_bed)
                self.release(in_beds_PHC7)
                ipd_bed_time_PHC7 += t_bed
                ipd_MO_time_PHC7 += doc_time
                ipd_nurse_time_PHC7 += t_nurse
            else:
                self.leave(medicine_q_PHC7)
                exit_time3 = env.now()
                opd_q_waiting_time_PHC7.append(exit_time3 - entry_time2)  # stores waiting time in the queue
                yield self.hold(doc_time)
                self.release(doc_OPD_PHC7)
                yield self.request(in_beds_PHC7, ipd_nurse_PHC7)
                yield self.hold(t_nurse)
                self.release(ipd_nurse_PHC7)
                yield self.hold(t_bed)
                self.release(in_beds_PHC7)
                ipd_bed_time_PHC7 += t_bed
                ipd_MO_time_PHC7 += doc_time
                ipd_nurse_time_PHC7 += t_nurse


class CovidGenerator_PHC7(sim.Component):

    def process(self):
        global d1_PHC7
        global warmup_time
        global covid_iat_PHC7
        global phc_covid_iat
        global j

        while True:

            if env.now() < warmup_time:
                if 0 <= (env.now() - d1_PHC7 * 1440) < 480:
                    covid_PHC7()
                    yield self.hold(1440 / 3)
                    d1_PHC7 = int(env.now() / 1440)
                else:
                    yield self.hold(960)
                    d1_PHC7 = int(env.now() / 1440)

            else:
                a = phc_covid_iat[j]
                if 0 <= (env.now() - d1_PHC7 * 1440) < 480:
                    covid_PHC7()
                    yield self.hold(sim.Exponential(a).sample())
                    d1_PHC7 = int(env.now() / 1440)
                else:

                    yield self.hold(960)
                    d1_PHC7 = int(env.now() / 1440)


class covid_PHC7(sim.Component):

    def process(self):

        global home_refer_PHC7
        global chc_refer_PHC7
        global dh_refer_PHC7
        global isolation_ward_refer_PHC7
        global covid_patient_time_PHC7
        global covid_count_PHC7
        global warmup_time
        global ipd_nurse_PHC7
        global ipd_nurse_time_PHC7
        global doc_OPD_PHC7
        global MO_covid_time_PHC7
        global phc2chc_count_PHC7
        global warmup_time
        global home_isolation_PHC7

        global ICU_oxygen
        global phc7_to_cc_severe_case
        global phc7_to_cc_dist
        global phc7_2_cc

        if env.now() < warmup_time:
            covid_nurse_PHC7()
            covid_lab_PHC7()
            x = random.randint(0, 1000)
            if x <= 940:
                a = random.randint(0, 10)
                if a >= 9:
                    cc_isolation()
            elif 940 < x <= 980:
                pass
            # CovidCare_chc1()
            else:
                pass
                # SevereCase()
        else:
            covid_count_PHC7 += 1
            covid_nurse_PHC7()
            covid_lab_PHC7()
            x = random.randint(0, 1000)
            if x <= 940:  # mild cases
                home_refer_PHC7 += 1
                a = random.randint(0, 100)
                if a >= 90:  # 10 % for institutional quarantine
                    isolation_ward_refer_PHC7 += 1
                    cc_isolation()
                else:
                    home_isolation_PHC7 += 1
            elif 940 < x <= 980:  # moderate cases
                chc_refer_PHC7 += 1
                phc2chc_count_PHC7 += 1
                CovidCare_chc1()
            else:  # severe case
                s = random.randint(0, 100)
                if s < 50:  # Type f patients
                    if ICU_oxygen.available_quantity() < 1:  # checks if there is a vacant bed in DH
                        phc7_to_cc_severe_case += 1
                        phc7_to_cc_dist.append(phc7_2_cc)
                        cc_Type_F()  # patient refered tpo CC
                    else:
                        DH_SevereTypeF()
                        dh_refer_PHC7 += 1  # Severe cases
                elif 50 <= s <= 74:  # E type patients
                    if ICU_ventilator.available_quantity() < 1:  # checks if there is a vacant bed in DH
                        cc_ICU_ward_TypeE()
                        phc7_to_cc_severe_case += 1
                    else:
                        DH_SevereTypeE()
                        dh_refer_PHC7 += 1  # Severe cases
                else:  # Type d patients
                    if ICU_ventilator.available_quantity() < 1:  # checks if there is a vacant bed in DH
                        cc_ventilator_TypeD()
                        phc7_to_cc_severe_case += 1
                    else:
                        dh_refer_PHC7 += 1  # Severe cases
                        DH_SevereTypeD()


class covid_nurse_PHC7(sim.Component):

    def process(self):

        global warmup_time
        global ipd_nurse_PHC7
        global ipd_nurse_time_PHC7
        global lab_covidcount_PHC7

        if env.now() <= warmup_time:
            yield self.request(ipd_nurse_PHC7)
            yield self.hold(sim.Uniform(2, 3).sample())
            self.release(ipd_nurse_PHC7)
        else:
            lab_covidcount_PHC7 += 1
            yield self.request(ipd_nurse_PHC7)
            t = sim.Uniform(2, 3).sample()
            yield self.hold(t)
            ipd_nurse_time_PHC7 += t
            self.release(ipd_nurse_PHC7)


class covid_lab_PHC7(sim.Component):

    def process(self):

        global lab_technician_PHC7
        global lab_time_PHC7
        global lab_q_waiting_time_PHC7
        global warmup_time
        global lab_covidcount_PHC7

        if env.now() <= warmup_time:
            yield self.request(lab_technician_PHC7)
            yield self.hold(sim.Uniform(1, 2).sample())
            self.release(lab_technician_PHC7)
        else:
            lab_covidcount_PHC7 += 1
            yield self.request(lab_technician_PHC7)
            t = sim.Uniform(1, 2).sample()
            yield self.hold(t)
            lab_time_PHC7 += t
            self.release(lab_technician_PHC7)
            x = random.randint(0, 100)
            if x < 33:  # confirmed posiive
                covid_doc_PHC7()
            elif 33 < x < 67:  # symptomatic negative, retesting
                retesting_PHC7()
            else:
                Pharmacy_PHC7()


class retesting_PHC7(sim.Component):

    def process(self):

        global retesting_count_PHC7
        global warmup_time

        if env.now() <= warmup_time:
            yield self.hold(1440)
            covid_doc_PHC7()
        else:
            retesting_count_PHC7 += 1
            yield self.hold(1440)
            covid_doc_PHC7()


class covid_doc_PHC7(sim.Component):

    def process(self):
        global MO_covid_time_PHC7
        global doc_OPD_PHC7
        global warmup_time
        global covid_q_PHC7
        global covid_patient_time_PHC7
        global medicine_cons_time_PHC7

        if env.now() <= warmup_time:
            self.enter(covid_q_PHC7)
            yield self.request(doc_OPD_PHC7)
            self.leave(covid_q_PHC7)
            yield self.hold(sim.Uniform(3, 6).sample())
            self.release(doc_OPD_PHC7)
        else:
            in_time = env.now()
            self.enter(covid_q_PHC7)
            yield self.request(doc_OPD_PHC7)
            self.leave(covid_q_PHC7)
            t = sim.Uniform(3, 6).sample()
            yield self.hold(t)
            MO_covid_time_PHC7 += t
            medicine_cons_time_PHC7 += t
            self.release(doc_OPD_PHC7)
            covid_patient_time_PHC7 += env.now() - in_time


global l8  # temp lab count
l8 = 0
global o_PHC8  # temp opd count
o_PHC8 = 0


# PHC 8
class PatientGenerator_PHC8(sim.Component):
    global shift_PHC8
    shift_PHC8 = 0
    No_of_days_PHC8 = 0

    total_OPD_patients_PHC8 = 0

    def process(self):

        global env
        global warmup_time
        global opd_iat_PHC8
        global days_PHC8
        global medicine_cons_time_PHC8
        global shift_PHC8
        global phc1_doc_time_PHC8

        self.sim_time_PHC8 = 0  # local variable defined for dividing each day into shits
        self.z_PHC8 = 0
        self.admin_count_PHC8 = 0
        k_PHC8 = 0

        while self.z_PHC8 % 3 == 0:  # condition to run simulation for 8 hour shifts
            PatientGenerator_PHC8.No_of_days_PHC8 += 1  # class variable to track number of days passed
            while self.sim_time_PHC8 < 360:  # from morning 8 am to afternoon 2 pm (in minutes)
                if env.now() <= warmup_time:
                    pass
                else:
                    OPD_PHC8()
                o = sim.Exponential(opd_iat_PHC8).sample()
                yield self.hold(o)
                self.sim_time_PHC8 += o

            while 360 <= self.sim_time_PHC8 < 480:  # condition for admin work after opd hours are over
                k_PHC8 = int(sim.Normal(100, 20).bounded_sample(60, 140))
                """For sensitivity analysis. Admin work added to staff nurse rather than doctor"""
                if env.now() <= warmup_time:
                    pass
                else:
                    medicine_cons_time_PHC8 += k_PHC8  # conatns all doctor service times
                    phc1_doc_time_PHC8 += k_PHC8
                yield self.hold(120)
                self.sim_time_PHC8 = 481
            self.z_PHC8 += 3
            self.sim_time_PHC8 = 0
            # PatientGenerator1.No_of_shifts += 3
            yield self.hold(959)  # holds simulation for 2 shifts


class OPD_PHC8(sim.Component):
    Patient_log_PHC8 = {}

    def setup(self):

        self.dic = {}  # local dictionary for temporarily   storing generated patients
        # with attributes
        self.time_of_visit = [[0], [0], [0]]  # initializing for assigning time of visits
        self.regis_time = round(env.now())  # registration time is the current simulation time
        self.id = PatientGenerator_PHC8.total_OPD_patients_PHC8  # patient count is patient id
        self.age_random = random.randint(0, 1000)  # assigning age to population based on census 2011 gurgaon
        if self.age_random <= 578:
            self.age = random.randint(0, 30)
        else:
            self.age = random.randint(31, 100)
        self.sex = random.choice(["male", "female"])  # Equal probability of male and female patient
        # require lab tests
        self.lab_required = random.choice(["True", "False"])  # Considering nearly half of all the patients
        self.radiography_required = random.choice(["True", "False"])
        y = random.randint(0, 999)
        self.consultation = random.choice([y])  # for medicine, gynea, pead, denta
        self.visits_assigned = random.randint(1, 10)  # assigning number of visits visits
        self.dic = {"ID": self.id, "Age": self.age, "Sex": self.sex, "Lab": self.lab_required,
                    "Registration_Time": self.regis_time, "No_of_visits": self.visits_assigned,
                    "Time_of_visit": self.time_of_visit, "Radiography": self.radiography_required,
                    "Consultation": self.consultation}
        OPD_PHC8.Patient_log_PHC8[PatientGenerator_PHC8.total_OPD_patients_PHC8] = self.dic

        self.process()

    def process(self):

        global c8
        global medicine_q_PHC8
        global doc_OPD_PHC8
        global opd_ser_time_mean_PHC8
        global opd_ser_time_sd_PHC8
        global medicine_count_PHC8
        global medicine_cons_time_PHC8
        global opd_q_waiting_time_PHC8
        global ncd_count_PHC8
        global ncd_nurse_PHC8
        global ncd_time_PHC8
        global warmup_time
        global l8
        global phc1_doc_time_PHC8

        if env.now() <= warmup_time:
            p = random.randint(0, 10)
            if p < 2:
                COVID_OPD_PHC8()
            if OPD_PHC8.Patient_log_PHC8[PatientGenerator_PHC8.total_OPD_patients_PHC8]["Age"] > 30:
                yield self.request(ncd_nurse_PHC8)
                ncd_service = sim.Uniform(2, 5).sample()
                yield self.hold(ncd_service)
            self.enter(medicine_q_PHC8)
            yield self.request(doc_OPD_PHC8)
            self.leave(medicine_q_PHC8)
            o = sim.Normal(opd_ser_time_mean_PHC8, opd_ser_time_sd_PHC8).bounded_sample(0.3)
            yield self.hold(o)
            self.release(doc_OPD_PHC8)
            if OPD_PHC8.Patient_log_PHC8[PatientGenerator_PHC8.total_OPD_patients_PHC8]["Lab"] == "True":
                Lab_PHC8()
            Pharmacy_PHC8()
        else:
            l8 += 1
            medicine_count_PHC8 += 1
            p = random.randint(0, 10)
            if p < 2:
                COVID_OPD_PHC8()
            if OPD_PHC8.Patient_log_PHC8[PatientGenerator_PHC8.total_OPD_patients_PHC8]["Age"] > 30:
                ncd_count_PHC8 += 1
                yield self.request(ncd_nurse_PHC8)
                ncd_service = sim.Uniform(2, 5).sample()
                yield self.hold(ncd_service)
                ncd_time_PHC8 += ncd_service
            # doctor opd starts from here
            entry_time = env.now()
            self.enter(medicine_q_PHC8)
            yield self.request(doc_OPD_PHC8)
            self.leave(medicine_q_PHC8)
            exit_time = env.now()
            opd_q_waiting_time_PHC8.append(exit_time - entry_time)  # stores waiting time in the queue
            o = sim.Normal(opd_ser_time_mean_PHC8, opd_ser_time_sd_PHC8).bounded_sample(0.3)
            yield self.hold(o)
            phc1_doc_time_PHC8 += o
            medicine_cons_time_PHC8 += o
            self.release(doc_OPD_PHC8)
            # lab starts from here
            t = random.randint(0, 1000)
            # changed here
            if OPD_PHC8.Patient_log_PHC8[PatientGenerator_PHC8.total_OPD_patients_PHC8]["Lab"] == "True":
                Lab_PHC8()
            Pharmacy_PHC8()


class COVID_OPD_PHC8(sim.Component):

    def process(self):

        global ipd_nurse_PHC8
        global delivery_nurse_time_PHC8

        if env.now() <= warmup_time:
            yield self.request(ipd_nurse_PHC8)
            h1 = sim.Uniform(5, 10).sample()
            yield self.hold(h1)
            self.release(ipd_nurse_PHC8)
            OPD_covidtest_PHC8()
            yield self.hold(sim.Uniform(15, 30).sample())  # patient waits for the result
        else:
            yield self.request(ipd_nurse_PHC8)
            h1 = sim.Uniform(5, 10).sample()
            yield self.hold(h1)
            self.release(ipd_nurse_PHC8)
            OPD_covidtest_PHC8()
            delivery_nurse_time_PHC8 += h1
            yield self.hold(sim.Uniform(15, 30).sample())


class OPD_covidtest_PHC8(sim.Component):

    def process(self):
        global lab_covidcount_PHC8
        global lab_technician_PHC8
        global lab_time_PHC8
        global warmup_time

        if env.now() <= warmup_time:
            yield self.request(lab_technician_PHC8)
            t = sim.Uniform(1, 2).sample()
            yield self.hold(t)
            self.release(lab_technician_PHC8)
        else:
            lab_covidcount_PHC8 += 1
            yield self.request(lab_technician_PHC8)
            t = sim.Uniform(1, 2).sample()
            yield self.hold(t)
            lab_time_PHC8 += t
            self.release(lab_technician_PHC8)


class Pharmacy_PHC8(sim.Component):

    def process(self):

        global pharmacist_PHC8
        global pharmacy_time_PHC8
        global pharmacy_q_PHC8
        global pharmacy_q_waiting_time_PHC8
        global warmup_time
        global pharmacy_count_PHC8

        if env.now() < warmup_time:
            self.enter(pharmacy_q_PHC8)
            yield self.request(pharmacist_PHC8)
            self.leave(pharmacy_q_PHC8)
            # service_time = sim.Uniform(1, 2.5).sample()
            service_time = sim.Normal(2.083, 0.72).bounded_sample(.67)
            yield self.hold(service_time)
            self.release(pharmacist_PHC8)
        else:
            pharmacy_count_PHC8 += 1
            e1 = env.now()
            self.enter(pharmacy_q_PHC8)
            yield self.request((pharmacist_PHC8, 1))
            self.leave(pharmacy_q_PHC8)
            pharmacy_q_waiting_time_PHC8.append(env.now() - e1)
            service_time = sim.Normal(2.083, 0.72).bounded_sample(.67)
            yield self.hold(service_time)
            self.release((pharmacist_PHC8, 1))
            pharmacy_time_PHC8 += service_time


class Delivery_patient_generator_PHC8(sim.Component):
    Delivery_list = {}

    def process(self):
        global delivery_iat_PHC8
        global warmup_time
        global delivery_count_PHC8
        global days_PHC8
        global childbirth_count_PHC8
        global N_PHC8

        while True:
            if env.now() <= warmup_time:
                pass
            else:
                childbirth_count_PHC8 += 1
                self.registration_time = round(env.now())
                if 0 < (self.registration_time - N_PHC8 * 1440) < 480:
                    Delivery_with_doctor_PHC8(urgent=True)  # sets priority
                else:
                    Delivery_no_doc_PHC8(urgent=True)
            self.hold_time = sim.Exponential(delivery_iat_PHC8).sample()
            yield self.hold(self.hold_time)
            N_PHC8 = int(env.now() / 1440)


class Delivery_no_doc_PHC8(sim.Component):

    def process(self):
        global ipd_nurse_PHC8
        global ipd_nurse_PHC8
        global doc_OPD_PHC8
        global delivery_bed_PHC8
        global warmup_time
        global e_beds_PHC8
        global ipd_nurse_time_PHC8
        global MO_del_time_PHC8
        global in_beds_PHC8
        global delivery_nurse_time_PHC8
        global inpatient_del_count_PHC8
        global delivery_count_PHC8
        global emergency_bed_time_PHC8
        global ipd_bed_time_PHC8
        global emergency_nurse_time_PHC8
        global referred_PHC8
        global fail_count_PHC8

        if env.now() <= warmup_time:
            t_nurse = sim.Uniform(120, 240, 'minutes').sample()
            t_bed = sim.Uniform(360, 600).sample()
            yield self.request(ipd_nurse_PHC8)
            yield self.hold(t_nurse)
            self.release(ipd_nurse_PHC8)
            yield self.request(delivery_bed_PHC8, fail_delay=120)
            if self.failed():
                pass
            else:
                yield self.hold(t_bed)
                self.release(delivery_bed_PHC8)
                yield self.request(in_beds_PHC8)
                yield self.hold(sim.Uniform(240, 1440, 'minutes').bounded_sample(0))
                self.release(in_beds_PHC8)
        else:
            delivery_count_PHC8 += 1
            t_bed = sim.Uniform(360, 600).sample()  # delivery bed, nurse time
            t_nur = sim.Uniform(120, 240).sample()
            delivery_nurse_time_PHC8 += t_nur
            yield self.request(ipd_nurse_PHC8)
            yield self.hold(t_nur)
            self.release(ipd_nurse_PHC8)  # delivery nurse and delivery beds are released simultaneoulsy
            yield self.request(delivery_bed_PHC8, fail_delay=120)
            if self.failed():
                fail_count_PHC8 += 1
                delivery_count_PHC8 -= 1
                pass
            else:
                yield self.hold(t_bed)
                self.release(delivery_bed_PHC8)
                yield self.request(in_beds_PHC8)
                t_bed1 = sim.Uniform(240, 1440).sample()
                yield self.hold(t_bed1)
                ipd_bed_time_PHC8 += t_bed1


class Delivery_with_doctor_PHC8(sim.Component):

    def process(self):
        global ipd_nurse_PHC8
        global ipd_nurse_PHC8
        global doc_OPD_PHC8
        global delivery_bed_PHC8
        global warmup_time
        global e_beds_PHC8
        global ipd_nurse_time_PHC8
        global MO_del_time_PHC8
        global in_beds_PHC8
        global delivery_nurse_time_PHC8
        global inpatient_del_count_PHC8
        global delivery_count_PHC8
        global emergency_bed_time_PHC8
        global ipd_bed_time_PHC8
        global emergency_nurse_time_PHC8
        global referred_PHC8
        global fail_count_PHC8
        global opd_q_waiting_time_PHC8
        global phc1_doc_time_PHC8
        global medicine_cons_time_PHC8
        global medicine_q_PHC8

        if env.now() <= warmup_time:
            t_doc = sim.Uniform(30, 60).sample()
            t_bed = sim.Uniform(240, 360).sample()
            t_nurse = sim.Uniform(120, 240, 'minutes').sample()
            self.enter_at_head(medicine_q_PHC8)
            yield self.request(doc_OPD_PHC8, fail_delay=20)
            if self.failed():  # if doctor is busy staff nurse takes care
                self.leave(medicine_q_PHC8)
                yield self.request(ipd_nurse_PHC8)
                yield self.hold(t_nurse)
                self.release(ipd_nurse_PHC8)
                yield self.request(doc_OPD_PHC8)
                yield self.hold(t_doc)
                self.release(doc_OPD_PHC8)
                self.release(delivery_bed_PHC8)
                yield self.request(delivery_bed_PHC8, fail_delay=120)
                if self.failed():
                    pass
                else:
                    yield self.hold(sim.Uniform(6 * 60, 10 * 60, 'minutes').sample())
                    self.release(delivery_bed_PHC8)
                    yield self.request(in_beds_PHC8)
                    yield self.hold(sim.Uniform(240, 1440, 'minutes').sample())
                    self.release()
            else:
                self.leave(medicine_q_PHC8)
                yield self.hold(t_doc)
                self.release(doc_OPD_PHC8)
                yield self.request(ipd_nurse_PHC8)
                yield self.hold(t_nurse)
                self.release(ipd_nurse_PHC8)
                yield self.request(delivery_bed_PHC8)
                yield self.hold(sim.Uniform(6 * 60, 10 * 60, 'minutes').sample())
                self.release(delivery_bed_PHC8)
                yield self.request(in_beds_PHC8)
                yield self.hold(sim.Uniform(240, 1440, 'minutes').bounded_sample(0))  # holding patient for min 4 hours
                # to 48 hours
                self.release(in_beds_PHC8)
        else:
            delivery_count_PHC8 += 1
            entry_time1 = env.now()
            self.enter_at_head(medicine_q_PHC8)
            yield self.request(doc_OPD_PHC8, fail_delay=20)
            t_doc = sim.Uniform(30, 60).sample()
            t_bed = sim.Uniform(360, 600).sample()  # delivery bed, nurse time
            t_nur = sim.Uniform(120, 240).sample()
            delivery_nurse_time_PHC8 += t_nur
            phc1_doc_time_PHC8 += t_doc
            MO_del_time_PHC8 += t_doc  # changed here
            medicine_cons_time_PHC8 += t_doc
            if self.failed():  # if doctor is busy staff nurse takes care
                self.leave(medicine_q_PHC8)
                exit_time1 = env.now()
                opd_q_waiting_time_PHC8.append(exit_time1 - entry_time1)  # stores waiting time in the queue
                yield self.request(ipd_nurse_PHC8)
                yield self.hold(t_nur)
                self.release(ipd_nurse_PHC8)
                # changed here
                yield self.request(doc_OPD_PHC8)
                yield self.hold(t_doc)
                self.release(doc_OPD_PHC8)
                yield self.request(delivery_bed_PHC8, fail_delay=120)
                if self.failed():
                    fail_count_PHC8 += 1
                    delivery_count_PHC8 -= 1
                else:
                    yield self.hold(t_bed)
                    self.release(delivery_bed_PHC8)
                    # after delivery patient shifts to IPD and requests nurse and inpatient bed
                    # changed here, removed ipd nurse
                    yield self.request(in_beds_PHC8)
                    # t_n = sim.Uniform(20, 30).sample()          # inpatient nurse time in ipd after delivery
                    t_bed2 = sim.Uniform(240, 1440).sample()  # inpatient beds post delivery stay
                    # yield self.hold(t_n)
                    # self.release(ipd_nurse1)
                    # ipd_nurse_time1 += t_n
                    yield self.hold(t_bed2)
                    ipd_bed_time_PHC8 += t_bed2
            else:
                self.leave(medicine_q_PHC8)
                exit_time1 = env.now()
                opd_q_waiting_time_PHC8.append(exit_time1 - entry_time1)  # stores waiting time in the queue
                yield self.hold(t_doc)
                self.release(doc_OPD_PHC8)
                yield self.request(ipd_nurse_PHC8)
                yield self.hold(t_nur)
                self.release(ipd_nurse_PHC8)  # delivery nurse and delivery beds are released simultaneoulsy
                yield self.request(delivery_bed_PHC8)
                yield self.hold(t_bed)
                self.release(delivery_bed_PHC8)
                yield self.request(in_beds_PHC8)
                t_bed1 = sim.Uniform(240, 1440).sample()
                yield self.hold(t_bed1)
                ipd_bed_time_PHC8 += t_bed1


class Lab_PHC8(sim.Component):

    def process(self):
        global lab_q_PHC8
        global lab_technician_PHC8
        global lab_time_PHC8
        global lab_q_waiting_time_PHC8
        global warmup_time
        global lab_count_PHC8
        global o_PHC8

        if env.now() <= warmup_time:
            self.enter(lab_q_PHC8)
            yield self.request(lab_technician_PHC8)
            self.leave(lab_q_PHC8)
            yp = (sim.Normal(3.456, .823).bounded_sample(2))
            y0 = yp
            yield self.hold(y0)
            self.release(lab_technician_PHC8)
        else:
            lab_count_PHC8 += 1
            self.enter(lab_q_PHC8)
            a0 = env.now()
            yield self.request(lab_technician_PHC8)
            self.leave(lab_q_PHC8)
            lab_q_waiting_time_PHC8.append(env.now() - a0)
            f1 = env.now()
            yp = (sim.Normal(3.456, .823).bounded_sample(2))
            y0 = yp
            yield self.hold(y0)
            self.release(lab_technician_PHC8)
            f2 = env.now()
            lab_time_PHC8 += f2 - f1
            o_PHC8 += 1


class IPD_PatientGenerator_PHC8(sim.Component):
    global IPD1_iat_PHC8
    global warmup_time
    IPD_List_PHC8 = {}  # log of all the IPD patients stored here
    patient_count_PHC8 = 0
    p_count_PHC8 = 0  # log of patients in each replication

    def process(self):
        global days_PHC8
        M = 0
        while True:
            if env.now() <= warmup_time:
                pass
            else:
                IPD_PatientGenerator_PHC8.patient_count_PHC8 += 1
                IPD_PatientGenerator_PHC8.p_count_PHC8 += 1
            self.registration_time = env.now()
            self.id = IPD_PatientGenerator_PHC8.patient_count_PHC8
            self.age = round(random.normalvariate(35, 8))
            self.sex = random.choice(["Male", "Female"])
            IPD_PatientGenerator_PHC8.IPD_List_PHC8[self.id] = [self.registration_time, self.id, self.age, self.sex]
            if 0 < (self.registration_time - M * 1440) < 480:
                IPD_with_doc_PHC8(urgent=True)
            else:
                IPD_no_doc_PHC8(urgent=True)
            self.hold_time_1 = sim.Exponential(IPD1_iat_PHC8).sample()
            yield self.hold(self.hold_time_1)
            M = int(env.now() / 1440)


class IPD_no_doc_PHC8(sim.Component):

    def process(self):
        global MO_ipd_PHC8
        global ipd_nurse_PHC8
        global in_beds_PHC8
        global ipd_nurse_time_PHC8
        global warmup_time
        global ipd_bed_time_PHC8
        global ipd_nurse_time_PHC8
        global medicine_q_PHC8
        global ipd_MO_time_PHC8

        if env.now() <= warmup_time:

            yield self.request(in_beds_PHC8, ipd_nurse_PHC8)
            temp = sim.Uniform(30, 60, 'minutes').sample()
            yield self.hold(temp)
            self.release(ipd_nurse_PHC8)
            yield self.hold(sim.Triangular(60, 360, 180, 'minutes').bounded_sample(0))
            self.release(in_beds_PHC8)
        else:
            t_bed = sim.Triangular(60, 360, 180, 'minutes').sample()
            t_nurse = sim.Uniform(30, 60, 'minutes').sample()
            yield self.request(in_beds_PHC8, ipd_nurse_PHC8)
            yield self.hold(t_nurse)
            self.release(ipd_nurse_PHC8)
            yield self.hold(t_bed)
            self.release(in_beds_PHC8)
            ipd_bed_time_PHC8 += t_bed
            ipd_nurse_time_PHC8 += t_nurse


class IPD_with_doc_PHC8(sim.Component):

    def process(self):
        global MO_ipd_PHC8
        global ipd_nurse_PHC8
        global in_beds_PHC8
        global MO_ipd_time_PHC8
        global ipd_nurse_time_PHC8
        global warmup_time
        global ipd_bed_time_PHC8
        global ipd_nurse_time_PHC8
        global emergency_refer_PHC8
        global medicine_q_PHC8
        global ipd_MO_time_PHC8
        global opd_q_waiting_time_PHC8
        global phc1_doc_time_PHC8
        global medicine_cons_time_PHC8

        if env.now() <= warmup_time:
            self.enter_at_head(medicine_q_PHC8)
            yield self.request(doc_OPD_PHC8, fail_delay=20)
            doc_time = round(sim.Uniform(10, 30, 'minutes').sample())
            if self.failed():
                self.leave(medicine_q_PHC8)
                yield self.request(ipd_nurse_PHC8)
                temp = sim.Uniform(30, 60, 'minutes').sample()
                yield self.hold(temp)
                self.release(ipd_nurse_PHC8)
                yield self.request(doc_OPD_PHC8)
                yield self.hold(doc_time)
                self.release(doc_OPD_PHC8)
                yield self.request(in_beds_PHC8)
                yield self.hold(sim.Triangular(60, 360, 180, 'minutes').bounded_sample(0))
                self.release(in_beds_PHC8)
            else:
                self.leave(medicine_q_PHC8)
                yield self.hold(doc_time)
                self.release(doc_OPD_PHC8)
                yield self.request(in_beds_PHC8, ipd_nurse_PHC8)
                temp = sim.Uniform(30, 60, 'minutes').sample()
                yield self.hold(temp)
                self.release(ipd_nurse_PHC8)
                yield self.hold(sim.Triangular(60, 360, 180, 'minutes').bounded_sample(0))
                self.release(in_beds_PHC8)
        else:
            self.enter_at_head(medicine_q_PHC8)
            entry_time2 = env.now()
            yield self.request(doc_OPD_PHC8, fail_delay=20)
            doc_time = sim.Uniform(10, 30, 'minutes').sample()
            t_bed = sim.Triangular(60, 360, 180, 'minutes').sample()
            t_nurse = sim.Uniform(30, 60, 'minutes').sample()
            phc1_doc_time_PHC8 += doc_time
            medicine_cons_time_PHC8 += doc_time
            if self.failed():
                self.leave(medicine_q_PHC8)
                exit_time2 = env.now()
                opd_q_waiting_time_PHC8.append(exit_time2 - entry_time2)  # stores waiting time in the queue
                yield self.request(ipd_nurse_PHC8)
                yield self.hold(t_nurse)
                self.release(ipd_nurse_PHC8)
                yield self.request(doc_OPD_PHC8)
                yield self.hold(doc_time)
                self.release(doc_OPD_PHC8)
                yield self.request(in_beds_PHC8)
                yield self.hold(t_bed)
                self.release(in_beds_PHC8)
                ipd_bed_time_PHC8 += t_bed
                ipd_MO_time_PHC8 += doc_time
                ipd_nurse_time_PHC8 += t_nurse
            else:
                self.leave(medicine_q_PHC8)
                exit_time3 = env.now()
                opd_q_waiting_time_PHC8.append(exit_time3 - entry_time2)  # stores waiting time in the queue
                yield self.hold(doc_time)
                self.release(doc_OPD_PHC8)
                yield self.request(in_beds_PHC8, ipd_nurse_PHC8)
                yield self.hold(t_nurse)
                self.release(ipd_nurse_PHC8)
                yield self.hold(t_bed)
                self.release(in_beds_PHC8)
                ipd_bed_time_PHC8 += t_bed
                ipd_MO_time_PHC8 += doc_time
                ipd_nurse_time_PHC8 += t_nurse


class ANC_PHC8(sim.Component):
    global ANC_iat_PHC8
    global days_PHC8
    days_PHC8 = 0
    env = sim.Environment()
    No_of_shifts_PHC8 = 0  # tracks number of shifts completed during the simulation time
    No_of_days_PHC8 = 0
    ANC_List_PHC8 = {}
    anc_count_PHC8 = 0
    ANC_p_count_PHC8 = 0

    def process(self):

        global days_PHC8

        while True:  # condition to run simulation for 8 hour shifts
            x = env.now() - 1440 * days_PHC8
            if 0 <= x < 480:
                ANC_PHC8.anc_count_PHC8 += 1  # counts overall patients throghout simulation
                ANC_PHC8.ANC_p_count_PHC8 += 1  # counts patients in each replication
                id = ANC_PHC8.anc_count_PHC8
                age = 223
                day_of_registration = ANC_PHC8.No_of_days_PHC8
                visit = 1
                x0 = round(env.now())
                x1 = x0 + 14 * 7 * 24 * 60
                x2 = x0 + 20 * 7 * 24 * 60
                x3 = x0 + 24 * 7 * 24 * 60
                scheduled_visits = [[0], [0], [0], [0]]
                scheduled_visits[0] = x0
                scheduled_visits[1] = x1
                scheduled_visits[2] = x2
                scheduled_visits[3] = x3
                dic = {"ID": id, "Age": age, "Visit Number": visit, "Registration day": day_of_registration,
                       "Scheduled Visit": scheduled_visits}
                ANC_PHC8.ANC_List_PHC8[id] = dic
                ANC_Checkup_PHC8()
                ANC_followup_PHC8(at=ANC_PHC8.ANC_List_PHC8[id]["Scheduled Visit"][1])
                ANC_followup_PHC8(at=ANC_PHC8.ANC_List_PHC8[id]["Scheduled Visit"][2])
                ANC_followup_PHC8(at=ANC_PHC8.ANC_List_PHC8[id]["Scheduled Visit"][3])
                hold_time = sim.Exponential(ANC_iat_PHC8).sample()
                yield self.hold(hold_time)
            else:
                yield self.hold(960)
                days_PHC8 = int(env.now() / 1440)  # holds simulation for 2 shifts


class ANC_Checkup_PHC8(sim.Component):
    anc_checkup_count_PHC8 = 0

    def process(self):

        global warmup_time
        global ipd_nurse_PHC8
        global delivery_nurse_time_PHC8
        global lab_q_PHC8
        global lab_technician_PHC8
        global lab_time_PHC8
        global lab_q_waiting_time_PHC8
        global warmup_time
        global lab_count_PHC8

        if env.now() <= warmup_time:
            yield self.request(ipd_nurse_PHC8)
            temp = sim.Triangular(8, 20.6, 12.3).sample()
            yield self.hold(temp)  # time taken from a study on ANC visits in Tanzania
            self.release(ipd_nurse_PHC8)
            self.enter(lab_q_PHC8)
            yield self.request(lab_technician_PHC8)
            self.leave(lab_q_PHC8)
            yp = (sim.Normal(5, 1).bounded_sample())
            y0 = yp
            yield self.hold(y0)
            self.release(lab_technician_PHC8)
        else:
            ANC_Checkup_PHC8.anc_checkup_count_PHC8 += 1
            yield self.request(ipd_nurse_PHC8)
            temp = sim.Triangular(8, 20.6, 12.3).sample()
            delivery_nurse_time_PHC8 += temp
            yield self.hold(temp)  # time taken from a study on ANC visits in Tanzania
            self.release(ipd_nurse_PHC8)
            lab_count_PHC8 += 1
            # changed here
            a0 = env.now()
            self.enter(lab_q_PHC8)
            yield self.request(lab_technician_PHC8)
            self.leave(lab_q_PHC8)
            lab_q_waiting_time_PHC8.append(env.now() - a0)
            yp = (sim.Normal(5, 1).bounded_sample())
            y0 = yp
            yield self.hold(y0)
            self.release(lab_technician_PHC8)
            lab_time_PHC8 += y0


class ANC_followup_PHC8(sim.Component):
    followup_count = 0

    def process(self):

        global warmup_time
        global ipd_nurse_PHC8
        global q_ANC_PHC8  # need change here and corrosponding arrays
        global delivery_nurse_time_PHC8
        global lab_time_PHC8
        global lab_q_waiting_time_PHC8

        if env.now() <= warmup_time:
            for key in ANC_PHC8.ANC_List_PHC8:  # for identifying and updating ANC visit number
                x0 = env.now()
                x1 = ANC_PHC8.ANC_List_PHC8[key]["Scheduled Visit"][1]
                x2 = ANC_PHC8.ANC_List_PHC8[key]["Scheduled Visit"][2]
                x3 = ANC_PHC8.ANC_List_PHC8[key]["Scheduled Visit"][3]
                if 0 <= (x1 - x0) < 481:
                    ANC_PHC8.ANC_List_PHC8[key]["Scheduled Visit"][1] = float("inf")
                    ANC_PHC8.ANC_List_PHC8[key]["Visit Number"] = 2
                elif 0 <= (x2 - x0) < 481:
                    ANC_PHC8.ANC_List_PHC8[key]["Scheduled Visit"][2] = float("inf")
                    ANC_PHC8.ANC_List_PHC8[key]["Visit Number"] = 3
                elif 0 <= (x3 - x0) < 481:
                    ANC_PHC8.ANC_List_PHC8[key]["Scheduled Visit"][3] = float("inf")
                    ANC_PHC8.ANC_List_PHC8[key]["Visit Number"] = 4

            yield self.request(ipd_nurse_PHC8)
            temp = sim.Triangular(3.33, 13.16, 6.50).sample()
            yield self.hold(temp)
            self.release(ipd_nurse_PHC8)
            a0 = env.now()
            self.enter(lab_q_PHC8)
            yield self.request(lab_technician_PHC8)
            self.leave(lab_q_PHC8)

            yp = (sim.Normal(3.456, .823).bounded_sample(2))
            y0 = yp
            yield self.hold(y0)
            self.release(lab_technician_PHC8)

        else:
            for key in ANC_PHC8.ANC_List_PHC8:  # for identifying and updating ANC visit number
                x0 = env.now()
                x1 = ANC_PHC8.ANC_List_PHC8[key]["Scheduled Visit"][1]
                x2 = ANC_PHC8.ANC_List_PHC8[key]["Scheduled Visit"][2]
                x3 = ANC_PHC8.ANC_List_PHC8[key]["Scheduled Visit"][3]
                if 0 <= (x1 - x0) < 481:
                    ANC_PHC8.ANC_List_PHC8[key]["Scheduled Visit"][1] = float("inf")
                    ANC_PHC8.ANC_List_PHC8[key]["Visit Number"] = 2
                elif 0 <= (x2 - x0) < 481:
                    ANC_PHC8.ANC_List_PHC8[key]["Scheduled Visit"][2] = float("inf")
                    ANC_PHC8.ANC_List_PHC8[key]["Visit Number"] = 3
                elif 0 <= (x3 - x0) < 481:
                    ANC_PHC8.ANC_List_PHC8[key]["Scheduled Visit"][3] = float("inf")
                    ANC_PHC8.ANC_List_PHC8[key]["Visit Number"] = 4

            yield self.request(ipd_nurse_PHC8)
            temp = sim.Triangular(3.33, 13.16, 6.50).sample()
            delivery_nurse_time_PHC8 += temp
            yield self.hold(temp)
            self.release(ipd_nurse_PHC8)
            a0 = env.now()
            self.enter(lab_q_PHC8)
            yield self.request(lab_technician_PHC8)
            self.leave(lab_q_PHC8)
            lab_q_waiting_time_PHC8.append(env.now() - a0)
            yp = (sim.Normal(3.456, .823).bounded_sample(2))
            y0 = yp
            yield self.hold(y0)
            self.release(lab_technician_PHC8)
            lab_time_PHC8 += y0


class CovidGenerator_PHC8(sim.Component):

    def process(self):
        global d1_PHC8
        global warmup_time
        global covid_iat_PHC8
        global phc_covid_iat
        global j

        while True:

            if env.now() < warmup_time:
                if 0 <= (env.now() - d1_PHC8 * 1440) < 480:
                    covid_PHC8()
                    yield self.hold(1440 / 3)
                    d1_PHC8 = int(env.now() / 1440)
                else:
                    yield self.hold(960)
                    d1_PHC8 = int(env.now() / 1440)

            else:
                a = phc_covid_iat[j]
                if 0 <= (env.now() - d1_PHC8 * 1440) < 480:
                    covid_PHC8()
                    yield self.hold(sim.Exponential(a).sample())
                    d1_PHC8 = int(env.now() / 1440)
                else:
                    yield self.hold(960)

                    d1_PHC8 = int(env.now() / 1440)


class covid_PHC8(sim.Component):

    def process(self):

        global home_refer_PHC8
        global chc_refer_PHC8
        global dh_refer_PHC8
        global isolation_ward_refer_PHC8
        global covid_patient_time_PHC8
        global covid_count_PHC8
        global warmup_time
        global ipd_nurse_PHC8
        global ipd_nurse_time_PHC8
        global doc_OPD_PHC8
        global MO_covid_time_PHC8
        global phc2chc_count_PHC8
        global warmup_time
        global home_isolation_PHC8

        global ICU_oxygen
        global phc8_to_cc_severe_case
        global phc8_to_cc_dist
        global phc8_2_cc

        if env.now() < warmup_time:
            covid_nurse_PHC8()
            covid_lab_PHC8()
            x = random.randint(0, 1000)
            if x <= 940:
                a = random.randint(0, 10)
                if a >= 9:
                    cc_isolation()
            elif 940 < x <= 980:
                pass
            # CovidCare_chc2()
            else:
                pass
                # SevereCase()
        else:
            covid_count_PHC8 += 1
            covid_nurse_PHC8()
            covid_lab_PHC8()
            x = random.randint(0, 1000)
            if x <= 940:  # mild cases
                home_refer_PHC8 += 1
                a = random.randint(0, 100)
                if a >= 90:  # 10 % for institutional quarantine
                    isolation_ward_refer_PHC8 += 1
                    cc_isolation()
                else:
                    home_isolation_PHC8 += 1
            elif 940 < x <= 980:  # moderate cases
                chc_refer_PHC8 += 1
                phc2chc_count_PHC8 += 1
                CovidCare_chc3()
            else:  # severe case
                s = random.randint(0, 100)
                if s < 50:  # Type f patients
                    if ICU_oxygen.available_quantity() < 1:  # checks if there is a vacant bed in DH
                        phc8_to_cc_severe_case += 1
                        phc8_to_cc_dist.append(phc8_2_cc)
                        cc_Type_F()  # patient refered tpo CC
                    else:
                        DH_SevereTypeF()
                        dh_refer_PHC8 += 1  # Severe cases
                elif 50 <= s <= 74:  # E type patients
                    if ICU_ventilator.available_quantity() < 1:  # checks if there is a vacant bed in DH
                        cc_ICU_ward_TypeE()
                        phc8_to_cc_severe_case += 1
                    else:
                        DH_SevereTypeE()
                        dh_refer_PHC8 += 1  # Severe cases
                else:  # Type d patients
                    if ICU_ventilator.available_quantity() < 1:  # checks if there is a vacant bed in DH
                        cc_ventilator_TypeD()
                        phc8_to_cc_severe_case += 1
                    else:
                        dh_refer_PHC8 += 1  # Severe cases
                        DH_SevereTypeD()


class covid_nurse_PHC8(sim.Component):

    def process(self):

        global warmup_time
        global ipd_nurse_PHC8
        global ipd_nurse_time_PHC8
        global lab_covidcount_PHC8

        if env.now() <= warmup_time:
            yield self.request(ipd_nurse_PHC8)
            yield self.hold(sim.Uniform(2, 3).sample())
            self.release(ipd_nurse_PHC8)
        else:
            lab_covidcount_PHC8 += 1
            yield self.request(ipd_nurse_PHC8)
            t = sim.Uniform(2, 3).sample()
            yield self.hold(t)
            ipd_nurse_time_PHC8 += t
            self.release(ipd_nurse_PHC8)


class covid_lab_PHC8(sim.Component):

    def process(self):

        global lab_technician_PHC8
        global lab_time_PHC8
        global lab_q_waiting_time_PHC8
        global warmup_time
        global lab_covidcount_PHC8

        if env.now() <= warmup_time:
            yield self.request(lab_technician_PHC8)
            yield self.hold(sim.Uniform(1, 2).sample())
            self.release(lab_technician_PHC8)
        else:
            lab_covidcount_PHC8 += 1
            yield self.request(lab_technician_PHC8)
            t = sim.Uniform(1, 2).sample()
            yield self.hold(t)
            lab_time_PHC8 += t
            self.release(lab_technician_PHC8)
            x = random.randint(0, 100)
            if x < 33:  # confirmed posiive
                covid_doc_PHC8()
            elif 33 < x < 67:  # symptomatic negative, retesting
                retesting_PHC8()
            else:
                Pharmacy_PHC8()


class retesting_PHC8(sim.Component):

    def process(self):

        global retesting_count_PHC8
        global warmup_time

        if env.now() <= warmup_time:
            yield self.hold(1440)
            covid_doc_PHC8()
        else:
            retesting_count_PHC8 += 1
            yield self.hold(1440)
            covid_doc_PHC8()


class covid_doc_PHC8(sim.Component):

    def process(self):
        global MO_covid_time_PHC8
        global doc_OPD_PHC8
        global warmup_time
        global covid_q_PHC8
        global covid_patient_time_PHC8
        global medicine_cons_time_PHC8

        if env.now() <= warmup_time:
            self.enter(covid_q_PHC8)
            yield self.request(doc_OPD_PHC8)
            self.leave(covid_q_PHC8)
            yield self.hold(sim.Uniform(3, 6).sample())
            self.release(doc_OPD_PHC8)
        else:
            in_time = env.now()
            self.enter(covid_q_PHC8)
            yield self.request(doc_OPD_PHC8)
            self.leave(covid_q_PHC8)
            t = sim.Uniform(3, 6).sample()
            yield self.hold(t)
            medicine_cons_time_PHC8 += t
            MO_covid_time_PHC8 += t
            self.release(doc_OPD_PHC8)
            covid_patient_time_PHC8 += env.now() - in_time


global l9  # temp lab count
l9 = 0
global o_PHC9  # temp opd count
o_PHC9 = 0


# PHC 9
class PatientGenerator_PHC9(sim.Component):
    global shift_PHC9
    shift_PHC9 = 0
    No_of_days_PHC9 = 0

    total_OPD_patients_PHC9 = 0

    def process(self):

        global env
        global warmup_time
        global opd_iat_PHC9
        global days_PHC9
        global medicine_cons_time_PHC9
        global shift_PHC9
        global phc1_doc_time_PHC9

        self.sim_time_PHC9 = 0  # local variable defined for dividing each day into shits
        self.z_PHC9 = 0
        self.admin_count_PHC9 = 0
        k_PHC9 = 0

        while self.z_PHC9 % 3 == 0:  # condition to run simulation for 8 hour shifts
            PatientGenerator_PHC9.No_of_days_PHC9 += 1  # class variable to track number of days passed
            while self.sim_time_PHC9 < 360:  # from morning 8 am to afternoon 2 pm (in minutes)
                if env.now() <= warmup_time:
                    pass
                else:
                    OPD_PHC9()
                o = sim.Exponential(opd_iat_PHC9).sample()
                yield self.hold(o)
                self.sim_time_PHC9 += o

            while 360 <= self.sim_time_PHC9 < 480:  # condition for admin work after opd hours are over
                k_PHC9 = int(sim.Normal(100, 20).bounded_sample(60, 140))
                """For sensitivity analysis. Admin work added to staff nurse rather than doctor"""
                if env.now() <= warmup_time:
                    pass
                else:
                    medicine_cons_time_PHC9 += k_PHC9  # conatns all doctor service times
                    phc1_doc_time_PHC9 += k_PHC9
                yield self.hold(120)
                self.sim_time_PHC9 = 481
            self.z_PHC9 += 3
            self.sim_time_PHC9 = 0
            # PatientGenerator1.No_of_shifts += 3
            yield self.hold(959)  # holds simulation for 2 shifts


class OPD_PHC9(sim.Component):
    Patient_log_PHC9 = {}

    def setup(self):

        self.dic = {}  # local dictionary for temporarily   storing generated patients
        # with attributes
        self.time_of_visit = [[0], [0], [0]]  # initializing for assigning time of visits
        self.regis_time = round(env.now())  # registration time is the current simulation time
        self.id = PatientGenerator_PHC9.total_OPD_patients_PHC9  # patient count is patient id
        self.age_random = random.randint(0, 1000)  # assigning age to population based on census 2011 gurgaon
        if self.age_random <= 578:
            self.age = random.randint(0, 30)
        else:
            self.age = random.randint(31, 100)
        self.sex = random.choice(["male", "female"])  # Equal probability of male and female patient
        # require lab tests
        self.lab_required = random.choice(["True", "False"])  # Considering nearly half of all the patients
        self.radiography_required = random.choice(["True", "False"])
        y = random.randint(0, 999)
        self.consultation = random.choice([y])  # for medicine, gynea, pead, denta
        self.visits_assigned = random.randint(1, 10)  # assigning number of visits visits
        self.dic = {"ID": self.id, "Age": self.age, "Sex": self.sex, "Lab": self.lab_required,
                    "Registration_Time": self.regis_time, "No_of_visits": self.visits_assigned,
                    "Time_of_visit": self.time_of_visit, "Radiography": self.radiography_required,
                    "Consultation": self.consultation}
        OPD_PHC9.Patient_log_PHC9[PatientGenerator_PHC9.total_OPD_patients_PHC9] = self.dic

        self.process()

    def process(self):

        global c9
        global medicine_q_PHC9
        global doc_OPD_PHC9
        global opd_ser_time_mean_PHC9
        global opd_ser_time_sd_PHC9
        global medicine_count_PHC9
        global medicine_cons_time_PHC9
        global opd_q_waiting_time_PHC9
        global ncd_count_PHC9
        global ncd_nurse_PHC9
        global ncd_time_PHC9
        global warmup_time
        global l9
        global phc1_doc_time_PHC9

        if env.now() <= warmup_time:
            p = random.randint(0, 10)
            if p < 2:
                COVID_OPD_PHC9()
            if OPD_PHC9.Patient_log_PHC9[PatientGenerator_PHC9.total_OPD_patients_PHC9]["Age"] > 30:
                yield self.request(ncd_nurse_PHC9)
                ncd_service = sim.Uniform(2, 5).sample()
                yield self.hold(ncd_service)
            self.enter(medicine_q_PHC9)
            yield self.request(doc_OPD_PHC9)
            self.leave(medicine_q_PHC9)
            o = sim.Normal(opd_ser_time_mean_PHC9, opd_ser_time_sd_PHC9).bounded_sample(0.3)
            yield self.hold(o)
            self.release(doc_OPD_PHC9)
            if OPD_PHC9.Patient_log_PHC9[PatientGenerator_PHC9.total_OPD_patients_PHC9]["Lab"] == "True":
                Lab_PHC9()
            Pharmacy_PHC9()
        else:
            l9 += 1
            medicine_count_PHC9 += 1
            p = random.randint(0, 10)
            if p < 2:
                COVID_OPD_PHC9()
            if OPD_PHC9.Patient_log_PHC9[PatientGenerator_PHC9.total_OPD_patients_PHC9]["Age"] > 30:
                ncd_count_PHC9 += 1
                yield self.request(ncd_nurse_PHC9)
                ncd_service = sim.Uniform(2, 5).sample()
                yield self.hold(ncd_service)
                ncd_time_PHC9 += ncd_service
            # doctor opd starts from here
            entry_time = env.now()
            self.enter(medicine_q_PHC9)
            yield self.request(doc_OPD_PHC9)
            self.leave(medicine_q_PHC9)
            exit_time = env.now()
            opd_q_waiting_time_PHC9.append(exit_time - entry_time)  # stores waiting time in the queue
            o = sim.Normal(opd_ser_time_mean_PHC9, opd_ser_time_sd_PHC9).bounded_sample(0.3)
            yield self.hold(o)
            phc1_doc_time_PHC9 += o
            medicine_cons_time_PHC9 += o
            self.release(doc_OPD_PHC9)
            # lab starts from here
            t = random.randint(0, 1000)
            # changed here
            if OPD_PHC9.Patient_log_PHC9[PatientGenerator_PHC9.total_OPD_patients_PHC9]["Lab"] == "True":
                Lab_PHC9()
            Pharmacy_PHC9()


class COVID_OPD_PHC9(sim.Component):

    def process(self):

        global ipd_nurse_PHC9
        global delivery_nurse_time_PHC9

        if env.now() <= warmup_time:
            yield self.request(ipd_nurse_PHC9)
            h1 = sim.Uniform(5, 10).sample()
            yield self.hold(h1)
            self.release(ipd_nurse_PHC9)
            OPD_covidtest_PHC9()
            yield self.hold(sim.Uniform(15, 30).sample())  # patient waits for the result
        else:
            yield self.request(ipd_nurse_PHC9)
            h1 = sim.Uniform(5, 10).sample()
            yield self.hold(h1)
            self.release(ipd_nurse_PHC9)
            OPD_covidtest_PHC9()
            delivery_nurse_time_PHC9 += h1
            yield self.hold(sim.Uniform(15, 30).sample())


class OPD_covidtest_PHC9(sim.Component):

    def process(self):
        global lab_covidcount_PHC9
        global lab_technician_PHC9
        global lab_time_PHC9
        global warmup_time

        if env.now() <= warmup_time:
            yield self.request(lab_technician_PHC9)
            t = sim.Uniform(1, 2).sample()
            yield self.hold(t)
            self.release(lab_technician_PHC9)
        else:
            lab_covidcount_PHC9 += 1
            yield self.request(lab_technician_PHC9)
            t = sim.Uniform(1, 2).sample()
            yield self.hold(t)
            lab_time_PHC9 += t
            self.release(lab_technician_PHC9)


class Pharmacy_PHC9(sim.Component):

    def process(self):

        global pharmacist_PHC9
        global pharmacy_time_PHC9
        global pharmacy_q_PHC9
        global pharmacy_q_waiting_time_PHC9
        global warmup_time
        global pharmacy_count_PHC9

        if env.now() < warmup_time:
            self.enter(pharmacy_q_PHC9)
            yield self.request(pharmacist_PHC9)
            self.leave(pharmacy_q_PHC9)
            # service_time = sim.Uniform(1, 2.5).sample()
            service_time = sim.Normal(2.083, 0.72).bounded_sample(.67)
            yield self.hold(service_time)
            self.release(pharmacist_PHC9)
        else:
            pharmacy_count_PHC9 += 1
            e1 = env.now()
            self.enter(pharmacy_q_PHC9)
            yield self.request((pharmacist_PHC9, 1))
            self.leave(pharmacy_q_PHC9)
            pharmacy_q_waiting_time_PHC9.append(env.now() - e1)
            service_time = sim.Normal(2.083, 0.72).bounded_sample(.67)
            yield self.hold(service_time)
            self.release((pharmacist_PHC9, 1))
            pharmacy_time_PHC9 += service_time


class Delivery_patient_generator_PHC9(sim.Component):
    Delivery_list = {}

    def process(self):
        global delivery_iat_PHC9
        global warmup_time
        global delivery_count_PHC9
        global days_PHC9
        global childbirth_count_PHC9
        global N_PHC9

        while True:
            if env.now() <= warmup_time:
                pass
            else:
                childbirth_count_PHC9 += 1
                self.registration_time = round(env.now())
                if 0 < (self.registration_time - N_PHC9 * 1440) < 480:
                    Delivery_with_doctor_PHC9(urgent=True)  # sets priority
                else:
                    Delivery_no_doc_PHC9(urgent=True)
            self.hold_time = sim.Exponential(delivery_iat_PHC9).sample()
            yield self.hold(self.hold_time)
            N_PHC9 = int(env.now() / 1440)


class Delivery_no_doc_PHC9(sim.Component):

    def process(self):
        global ipd_nurse_PHC9
        global ipd_nurse_PHC9
        global doc_OPD_PHC9
        global delivery_bed_PHC9
        global warmup_time
        global e_beds_PHC9
        global ipd_nurse_time_PHC9
        global MO_del_time_PHC9
        global in_beds_PHC9
        global delivery_nurse_time_PHC9
        global inpatient_del_count_PHC9
        global delivery_count_PHC9
        global emergency_bed_time_PHC9
        global ipd_bed_time_PHC9
        global emergency_nurse_time_PHC9
        global referred_PHC9
        global fail_count_PHC9

        if env.now() <= warmup_time:
            t_nurse = sim.Uniform(120, 240, 'minutes').sample()
            t_bed = sim.Uniform(360, 600).sample()
            yield self.request(ipd_nurse_PHC9)
            yield self.hold(t_nurse)
            self.release(ipd_nurse_PHC9)
            yield self.request(delivery_bed_PHC9, fail_delay=120)
            if self.failed():
                pass
            else:
                yield self.hold(t_bed)
                self.release(delivery_bed_PHC9)
                yield self.request(in_beds_PHC9)
                yield self.hold(sim.Uniform(240, 1440, 'minutes').bounded_sample(0))
                self.release(in_beds_PHC9)
        else:
            delivery_count_PHC9 += 1
            t_bed = sim.Uniform(360, 600).sample()  # delivery bed, nurse time
            t_nur = sim.Uniform(120, 240).sample()
            delivery_nurse_time_PHC9 += t_nur
            yield self.request(ipd_nurse_PHC9)
            yield self.hold(t_nur)
            self.release(ipd_nurse_PHC9)  # delivery nurse and delivery beds are released simultaneoulsy
            yield self.request(delivery_bed_PHC9, fail_delay=120)
            if self.failed():
                fail_count_PHC9 += 1
                delivery_count_PHC9 -= 1
                pass
            else:
                yield self.hold(t_bed)
                self.release(delivery_bed_PHC9)
                yield self.request(in_beds_PHC9)
                t_bed1 = sim.Uniform(240, 1440).sample()
                yield self.hold(t_bed1)
                ipd_bed_time_PHC9 += t_bed1


class Delivery_with_doctor_PHC9(sim.Component):

    def process(self):
        global ipd_nurse_PHC9
        global ipd_nurse_PHC9
        global doc_OPD_PHC9
        global delivery_bed_PHC9
        global warmup_time
        global e_beds_PHC9
        global ipd_nurse_time_PHC9
        global MO_del_time_PHC9
        global in_beds_PHC9
        global delivery_nurse_time_PHC9
        global inpatient_del_count_PHC9
        global delivery_count_PHC9
        global emergency_bed_time_PHC9
        global ipd_bed_time_PHC9
        global emergency_nurse_time_PHC9
        global referred_PHC9
        global fail_count_PHC9
        global opd_q_waiting_time_PHC9
        global phc1_doc_time_PHC9
        global medicine_cons_time_PHC9
        global medicine_q_PHC9

        if env.now() <= warmup_time:
            t_doc = sim.Uniform(30, 60).sample()
            t_bed = sim.Uniform(240, 360).sample()
            t_nurse = sim.Uniform(120, 240, 'minutes').sample()
            self.enter_at_head(medicine_q_PHC9)
            yield self.request(doc_OPD_PHC9, fail_delay=20)
            if self.failed():  # if doctor is busy staff nurse takes care
                self.leave(medicine_q_PHC9)
                yield self.request(ipd_nurse_PHC9)
                yield self.hold(t_nurse)
                self.release(ipd_nurse_PHC9)
                yield self.request(doc_OPD_PHC9)
                yield self.hold(t_doc)
                self.release(doc_OPD_PHC9)
                self.release(delivery_bed_PHC9)
                yield self.request(delivery_bed_PHC9, fail_delay=120)
                if self.failed():
                    pass
                else:
                    yield self.hold(sim.Uniform(6 * 60, 10 * 60, 'minutes').sample())
                    self.release(delivery_bed_PHC9)
                    yield self.request(in_beds_PHC9)
                    yield self.hold(sim.Uniform(240, 1440, 'minutes').sample())
                    self.release()
            else:
                self.leave(medicine_q_PHC9)
                yield self.hold(t_doc)
                self.release(doc_OPD_PHC9)
                yield self.request(ipd_nurse_PHC9)
                yield self.hold(t_nurse)
                self.release(ipd_nurse_PHC9)
                yield self.request(delivery_bed_PHC9)
                yield self.hold(sim.Uniform(6 * 60, 10 * 60, 'minutes').sample())
                self.release(delivery_bed_PHC9)
                yield self.request(in_beds_PHC9)
                yield self.hold(sim.Uniform(240, 1440, 'minutes').bounded_sample(0))  # holding patient for min 4 hours
                # to 48 hours
                self.release(in_beds_PHC9)
        else:
            delivery_count_PHC9 += 1
            entry_time1 = env.now()
            self.enter_at_head(medicine_q_PHC9)
            yield self.request(doc_OPD_PHC9, fail_delay=20)
            t_doc = sim.Uniform(30, 60).sample()
            t_bed = sim.Uniform(360, 600).sample()  # delivery bed, nurse time
            t_nur = sim.Uniform(120, 240).sample()
            delivery_nurse_time_PHC9 += t_nur
            phc1_doc_time_PHC9 += t_doc
            MO_del_time_PHC9 += t_doc  # changed here
            medicine_cons_time_PHC9 += t_doc
            if self.failed():  # if doctor is busy staff nurse takes care
                self.leave(medicine_q_PHC9)
                exit_time1 = env.now()
                opd_q_waiting_time_PHC9.append(exit_time1 - entry_time1)  # stores waiting time in the queue
                yield self.request(ipd_nurse_PHC9)
                yield self.hold(t_nur)
                self.release(ipd_nurse_PHC9)
                # changed here
                yield self.request(doc_OPD_PHC9)
                yield self.hold(t_doc)
                self.release(doc_OPD_PHC9)
                yield self.request(delivery_bed_PHC9, fail_delay=120)
                if self.failed():
                    fail_count_PHC9 += 1
                    delivery_count_PHC9 -= 1
                else:
                    yield self.hold(t_bed)
                    self.release(delivery_bed_PHC9)
                    # after delivery patient shifts to IPD and requests nurse and inpatient bed
                    # changed here, removed ipd nurse
                    yield self.request(in_beds_PHC9)
                    # t_n = sim.Uniform(20, 30).sample()          # inpatient nurse time in ipd after delivery
                    t_bed2 = sim.Uniform(240, 1440).sample()  # inpatient beds post delivery stay
                    # yield self.hold(t_n)
                    # self.release(ipd_nurse1)
                    # ipd_nurse_time1 += t_n
                    yield self.hold(t_bed2)
                    ipd_bed_time_PHC9 += t_bed2
            else:
                self.leave(medicine_q_PHC9)
                exit_time1 = env.now()
                opd_q_waiting_time_PHC9.append(exit_time1 - entry_time1)  # stores waiting time in the queue
                yield self.hold(t_doc)
                self.release(doc_OPD_PHC9)
                yield self.request(ipd_nurse_PHC9)
                yield self.hold(t_nur)
                self.release(ipd_nurse_PHC9)  # delivery nurse and delivery beds are released simultaneoulsy
                yield self.request(delivery_bed_PHC9)
                yield self.hold(t_bed)
                self.release(delivery_bed_PHC9)
                yield self.request(in_beds_PHC9)
                t_bed1 = sim.Uniform(240, 1440).sample()
                yield self.hold(t_bed1)
                ipd_bed_time_PHC9 += t_bed1


class Lab_PHC9(sim.Component):

    def process(self):
        global lab_q_PHC9
        global lab_technician_PHC9
        global lab_time_PHC9
        global lab_q_waiting_time_PHC9
        global warmup_time
        global lab_count_PHC9
        global o_PHC9

        if env.now() <= warmup_time:
            self.enter(lab_q_PHC9)
            yield self.request(lab_technician_PHC9)
            self.leave(lab_q_PHC9)
            yp = (sim.Normal(3.456, .823).bounded_sample(2))
            y0 = yp
            yield self.hold(y0)
            self.release(lab_technician_PHC9)
        else:
            lab_count_PHC9 += 1
            self.enter(lab_q_PHC9)
            a0 = env.now()
            yield self.request(lab_technician_PHC9)
            self.leave(lab_q_PHC9)
            lab_q_waiting_time_PHC9.append(env.now() - a0)
            f1 = env.now()
            yp = (sim.Normal(3.456, .823).bounded_sample(2))
            y0 = yp
            yield self.hold(y0)
            self.release(lab_technician_PHC9)
            f2 = env.now()
            lab_time_PHC9 += f2 - f1
            o_PHC9 += 1


class IPD_PatientGenerator_PHC9(sim.Component):
    global IPD1_iat_PHC9
    global warmup_time
    IPD_List_PHC9 = {}  # log of all the IPD patients stored here
    patient_count_PHC9 = 0
    p_count_PHC9 = 0  # log of patients in each replication

    def process(self):
        global days_PHC9
        M = 0
        while True:
            if env.now() <= warmup_time:
                pass
            else:
                IPD_PatientGenerator_PHC9.patient_count_PHC9 += 1
                IPD_PatientGenerator_PHC9.p_count_PHC9 += 1
            self.registration_time = env.now()
            self.id = IPD_PatientGenerator_PHC9.patient_count_PHC9
            self.age = round(random.normalvariate(35, 8))
            self.sex = random.choice(["Male", "Female"])
            IPD_PatientGenerator_PHC9.IPD_List_PHC9[self.id] = [self.registration_time, self.id, self.age, self.sex]
            if 0 < (self.registration_time - M * 1440) < 480:
                IPD_with_doc_PHC9(urgent=True)
            else:
                IPD_no_doc_PHC9(urgent=True)
            self.hold_time_1 = sim.Exponential(IPD1_iat_PHC9).sample()
            yield self.hold(self.hold_time_1)
            M = int(env.now() / 1440)


class IPD_no_doc_PHC9(sim.Component):

    def process(self):
        global MO_ipd_PHC9
        global ipd_nurse_PHC9
        global in_beds_PHC9
        global ipd_nurse_time_PHC9
        global warmup_time
        global ipd_bed_time_PHC9
        global ipd_nurse_time_PHC9
        global medicine_q_PHC9
        global ipd_MO_time_PHC9

        if env.now() <= warmup_time:

            yield self.request(in_beds_PHC9, ipd_nurse_PHC9)
            temp = sim.Uniform(30, 60, 'minutes').sample()
            yield self.hold(temp)
            self.release(ipd_nurse_PHC9)
            yield self.hold(sim.Triangular(60, 360, 180, 'minutes').bounded_sample(0))
            self.release(in_beds_PHC9)
        else:
            t_bed = sim.Triangular(60, 360, 180, 'minutes').sample()
            t_nurse = sim.Uniform(30, 60, 'minutes').sample()
            yield self.request(in_beds_PHC9, ipd_nurse_PHC9)
            yield self.hold(t_nurse)
            self.release(ipd_nurse_PHC9)
            yield self.hold(t_bed)
            self.release(in_beds_PHC9)
            ipd_bed_time_PHC9 += t_bed
            ipd_nurse_time_PHC9 += t_nurse


class IPD_with_doc_PHC9(sim.Component):

    def process(self):
        global MO_ipd_PHC9
        global ipd_nurse_PHC9
        global in_beds_PHC9
        global MO_ipd_time_PHC9
        global ipd_nurse_time_PHC9
        global warmup_time
        global ipd_bed_time_PHC9
        global ipd_nurse_time_PHC9
        global emergency_refer_PHC9
        global medicine_q_PHC9
        global ipd_MO_time_PHC9
        global opd_q_waiting_time_PHC9
        global phc1_doc_time_PHC9
        global medicine_cons_time_PHC9

        if env.now() <= warmup_time:
            self.enter_at_head(medicine_q_PHC9)
            yield self.request(doc_OPD_PHC9, fail_delay=20)
            doc_time = round(sim.Uniform(10, 30, 'minutes').sample())
            if self.failed():
                self.leave(medicine_q_PHC9)
                yield self.request(ipd_nurse_PHC9)
                temp = sim.Uniform(30, 60, 'minutes').sample()
                yield self.hold(temp)
                self.release(ipd_nurse_PHC9)
                yield self.request(doc_OPD_PHC9)
                yield self.hold(doc_time)
                self.release(doc_OPD_PHC9)
                yield self.request(in_beds_PHC9)
                yield self.hold(sim.Triangular(60, 360, 180, 'minutes').bounded_sample(0))
                self.release(in_beds_PHC9)
            else:
                self.leave(medicine_q_PHC9)
                yield self.hold(doc_time)
                self.release(doc_OPD_PHC9)
                yield self.request(in_beds_PHC9, ipd_nurse_PHC9)
                temp = sim.Uniform(30, 60, 'minutes').sample()
                yield self.hold(temp)
                self.release(ipd_nurse_PHC9)
                yield self.hold(sim.Triangular(60, 360, 180, 'minutes').bounded_sample(0))
                self.release(in_beds_PHC9)
        else:
            self.enter_at_head(medicine_q_PHC9)
            entry_time2 = env.now()
            yield self.request(doc_OPD_PHC9, fail_delay=20)
            doc_time = sim.Uniform(10, 30, 'minutes').sample()
            t_bed = sim.Triangular(60, 360, 180, 'minutes').sample()
            t_nurse = sim.Uniform(30, 60, 'minutes').sample()
            phc1_doc_time_PHC9 += doc_time
            medicine_cons_time_PHC9 += doc_time
            if self.failed():
                self.leave(medicine_q_PHC9)
                exit_time2 = env.now()
                opd_q_waiting_time_PHC9.append(exit_time2 - entry_time2)  # stores waiting time in the queue
                yield self.request(ipd_nurse_PHC9)
                yield self.hold(t_nurse)
                self.release(ipd_nurse_PHC9)
                yield self.request(doc_OPD_PHC9)
                yield self.hold(doc_time)
                self.release(doc_OPD_PHC9)
                yield self.request(in_beds_PHC9)
                yield self.hold(t_bed)
                self.release(in_beds_PHC9)
                ipd_bed_time_PHC9 += t_bed
                ipd_MO_time_PHC9 += doc_time
                ipd_nurse_time_PHC9 += t_nurse
            else:
                self.leave(medicine_q_PHC9)
                exit_time3 = env.now()
                opd_q_waiting_time_PHC9.append(exit_time3 - entry_time2)  # stores waiting time in the queue
                yield self.hold(doc_time)
                self.release(doc_OPD_PHC9)
                yield self.request(in_beds_PHC9, ipd_nurse_PHC9)
                yield self.hold(t_nurse)
                self.release(ipd_nurse_PHC9)
                yield self.hold(t_bed)
                self.release(in_beds_PHC9)
                ipd_bed_time_PHC9 += t_bed
                ipd_MO_time_PHC9 += doc_time
                ipd_nurse_time_PHC9 += t_nurse


class ANC_PHC9(sim.Component):
    global ANC_iat_PHC9
    global days_PHC9
    days_PHC9 = 0
    env = sim.Environment()
    No_of_shifts_PHC9 = 0  # tracks number of shifts completed during the simulation time
    No_of_days_PHC9 = 0
    ANC_List_PHC9 = {}
    anc_count_PHC9 = 0
    ANC_p_count_PHC9 = 0

    def process(self):

        global days_PHC9

        while True:  # condition to run simulation for 8 hour shifts
            x = env.now() - 1440 * days_PHC9
            if 0 <= x < 480:
                ANC_PHC9.anc_count_PHC9 += 1  # counts overall patients throghout simulation
                ANC_PHC9.ANC_p_count_PHC9 += 1  # counts patients in each replication
                id = ANC_PHC9.anc_count_PHC9
                age = 223
                day_of_registration = ANC_PHC9.No_of_days_PHC9
                visit = 1
                x0 = round(env.now())
                x1 = x0 + 14 * 7 * 24 * 60
                x2 = x0 + 20 * 7 * 24 * 60
                x3 = x0 + 24 * 7 * 24 * 60
                scheduled_visits = [[0], [0], [0], [0]]
                scheduled_visits[0] = x0
                scheduled_visits[1] = x1
                scheduled_visits[2] = x2
                scheduled_visits[3] = x3
                dic = {"ID": id, "Age": age, "Visit Number": visit, "Registration day": day_of_registration,
                       "Scheduled Visit": scheduled_visits}
                ANC_PHC9.ANC_List_PHC9[id] = dic
                ANC_Checkup_PHC9()
                ANC_followup_PHC9(at=ANC_PHC9.ANC_List_PHC9[id]["Scheduled Visit"][1])
                ANC_followup_PHC9(at=ANC_PHC9.ANC_List_PHC9[id]["Scheduled Visit"][2])
                ANC_followup_PHC9(at=ANC_PHC9.ANC_List_PHC9[id]["Scheduled Visit"][3])
                hold_time = sim.Exponential(ANC_iat_PHC9).sample()
                yield self.hold(hold_time)
            else:
                yield self.hold(960)
                days_PHC9 = int(env.now() / 1440)  # holds simulation for 2 shifts


class ANC_Checkup_PHC9(sim.Component):
    anc_checkup_count_PHC9 = 0

    def process(self):

        global warmup_time
        global ipd_nurse_PHC9
        global delivery_nurse_time_PHC9
        global lab_q_PHC9
        global lab_technician_PHC9
        global lab_time_PHC9
        global lab_q_waiting_time_PHC9
        global warmup_time
        global lab_count_PHC9

        if env.now() <= warmup_time:
            yield self.request(ipd_nurse_PHC9)
            temp = sim.Triangular(8, 20.6, 12.3).sample()
            yield self.hold(temp)  # time taken from a study on ANC visits in Tanzania
            self.release(ipd_nurse_PHC9)
            self.enter(lab_q_PHC9)
            yield self.request(lab_technician_PHC9)
            self.leave(lab_q_PHC9)
            yp = (sim.Normal(5, 1).bounded_sample())
            y0 = yp
            yield self.hold(y0)
            self.release(lab_technician_PHC9)
        else:
            ANC_Checkup_PHC9.anc_checkup_count_PHC9 += 1
            yield self.request(ipd_nurse_PHC9)
            temp = sim.Triangular(8, 20.6, 12.3).sample()
            delivery_nurse_time_PHC9 += temp
            yield self.hold(temp)  # time taken from a study on ANC visits in Tanzania
            self.release(ipd_nurse_PHC9)
            lab_count_PHC9 += 1
            # changed here
            a0 = env.now()
            self.enter(lab_q_PHC9)
            yield self.request(lab_technician_PHC9)
            self.leave(lab_q_PHC9)
            lab_q_waiting_time_PHC9.append(env.now() - a0)
            yp = (sim.Normal(5, 1).bounded_sample())
            y0 = yp
            yield self.hold(y0)
            self.release(lab_technician_PHC9)
            lab_time_PHC9 += y0


class ANC_followup_PHC9(sim.Component):
    followup_count = 0

    def process(self):

        global warmup_time
        global ipd_nurse_PHC9
        global q_ANC_PHC9  # need change here and corrosponding arrays
        global delivery_nurse_time_PHC9
        global lab_time_PHC9
        global lab_q_waiting_time_PHC9

        if env.now() <= warmup_time:
            for key in ANC_PHC9.ANC_List_PHC9:  # for identifying and updating ANC visit number
                x0 = env.now()
                x1 = ANC_PHC9.ANC_List_PHC9[key]["Scheduled Visit"][1]
                x2 = ANC_PHC9.ANC_List_PHC9[key]["Scheduled Visit"][2]
                x3 = ANC_PHC9.ANC_List_PHC9[key]["Scheduled Visit"][3]
                if 0 <= (x1 - x0) < 481:
                    ANC_PHC9.ANC_List_PHC9[key]["Scheduled Visit"][1] = float("inf")
                    ANC_PHC9.ANC_List_PHC9[key]["Visit Number"] = 2
                elif 0 <= (x2 - x0) < 481:
                    ANC_PHC9.ANC_List_PHC9[key]["Scheduled Visit"][2] = float("inf")
                    ANC_PHC9.ANC_List_PHC9[key]["Visit Number"] = 3
                elif 0 <= (x3 - x0) < 481:
                    ANC_PHC9.ANC_List_PHC9[key]["Scheduled Visit"][3] = float("inf")
                    ANC_PHC9.ANC_List_PHC9[key]["Visit Number"] = 4

            yield self.request(ipd_nurse_PHC9)
            temp = sim.Triangular(3.33, 13.16, 6.50).sample()
            yield self.hold(temp)
            self.release(ipd_nurse_PHC9)
            self.enter(lab_q_PHC9)
            yield self.request(lab_technician_PHC9)
            self.leave(lab_q_PHC9)
            yp = (sim.Normal(3.456, .823).bounded_sample(2))
            y0 = yp
            yield self.hold(y0)
            self.release(lab_technician_PHC9)

        else:
            for key in ANC_PHC9.ANC_List_PHC9:  # for identifying and updating ANC visit number
                x0 = env.now()
                x1 = ANC_PHC9.ANC_List_PHC9[key]["Scheduled Visit"][1]
                x2 = ANC_PHC9.ANC_List_PHC9[key]["Scheduled Visit"][2]
                x3 = ANC_PHC9.ANC_List_PHC9[key]["Scheduled Visit"][3]
                if 0 <= (x1 - x0) < 481:
                    ANC_PHC9.ANC_List_PHC9[key]["Scheduled Visit"][1] = float("inf")
                    ANC_PHC9.ANC_List_PHC9[key]["Visit Number"] = 2
                elif 0 <= (x2 - x0) < 481:
                    ANC_PHC9.ANC_List_PHC9[key]["Scheduled Visit"][2] = float("inf")
                    ANC_PHC9.ANC_List_PHC9[key]["Visit Number"] = 3
                elif 0 <= (x3 - x0) < 481:
                    ANC_PHC9.ANC_List_PHC9[key]["Scheduled Visit"][3] = float("inf")
                    ANC_PHC9.ANC_List_PHC9[key]["Visit Number"] = 4

            yield self.request(ipd_nurse_PHC9)
            temp = sim.Triangular(3.33, 13.16, 6.50).sample()
            delivery_nurse_time_PHC9 += temp
            yield self.hold(temp)
            self.release(ipd_nurse_PHC9)
            a0 = env.now()
            self.enter(lab_q_PHC9)
            yield self.request(lab_technician_PHC9)
            self.leave(lab_q_PHC9)
            lab_q_waiting_time_PHC9.append(env.now() - a0)
            yp = (sim.Normal(3.456, .823).bounded_sample(2))
            y0 = yp
            yield self.hold(y0)
            self.release(lab_technician_PHC9)
            lab_time_PHC9 += y0


class CovidGenerator_PHC9(sim.Component):

    def process(self):
        global d1_PHC9
        global warmup_time
        global covid_iat_PHC9
        global phc_covid_iat
        global j
        while True:

            if env.now() < warmup_time:
                if 0 <= (env.now() - d1_PHC9 * 1440) < 480:
                    covid_PHC9()
                    yield self.hold(1440 / 3)
                    d1_PHC9 = int(env.now() / 1440)
                else:
                    yield self.hold(960)
                    d1_PHC9 = int(env.now() / 1440)
            else:
                a = phc_covid_iat[j]
                if 0 <= (env.now() - d1_PHC9 * 1440) < 480:
                    covid_PHC9()
                    yield self.hold(sim.Exponential(a).sample())
                    d1_PHC9 = int(env.now() / 1440)
                else:

                    yield self.hold(960)
                    d1_PHC9 = int(env.now() / 1440)


class covid_PHC9(sim.Component):

    def process(self):

        global home_refer_PHC9
        global chc_refer_PHC9
        global dh_refer_PHC9
        global isolation_ward_refer_PHC9
        global covid_patient_time_PHC9
        global covid_count_PHC9
        global warmup_time
        global ipd_nurse_PHC9
        global ipd_nurse_time_PHC9
        global doc_OPD_PHC9
        global MO_covid_time_PHC9
        global phc2chc_count_PHC9
        global warmup_time
        global home_isolation_PHC9

        global ICU_oxygen
        global phc9_to_cc_severe_case
        global phc9_to_cc_dist
        global phc9_2_cc

        if env.now() < warmup_time:
            covid_nurse_PHC9()
            covid_lab_PHC9()
            x = random.randint(0, 1000)
            if x <= 940:
                a = random.randint(0, 100)
                if a >= 90:
                    cc_isolation()
            elif 940 < x <= 980:
                pass
            # CovidCare_chc2()
            else:
                pass
                #SevereCase()
        else:
            covid_count_PHC9 += 1
            covid_nurse_PHC9()
            covid_lab_PHC9()
            x = random.randint(0, 1000)
            if x <= 940:  # mild cases
                home_refer_PHC9 += 1
                a = random.randint(0, 100)
                if a >= 90:  # 10 % for institutional quarantine
                    isolation_ward_refer_PHC9 += 1
                    cc_isolation()
                else:
                    home_isolation_PHC9 += 1
            elif 940 < x <= 980:  # moderate cases
                chc_refer_PHC9 += 1
                phc2chc_count_PHC9 += 1
                CovidCare_chc3()
            else:  # severe case
                s = random.randint(0, 100)
                if s < 50:  # Type f patients
                    if ICU_oxygen.available_quantity() < 1:  # checks if there is a vacant bed in DH
                        phc9_to_cc_severe_case += 1
                        phc9_to_cc_dist.append(phc9_2_cc)
                        cc_Type_F()  # patient refered tpo CC
                    else:
                        DH_SevereTypeF()
                        dh_refer_PHC9 += 1  # Severe cases
                elif 50 <= s <= 74:  # E type patients
                    if ICU_ventilator.available_quantity() < 1:  # checks if there is a vacant bed in DH
                        cc_ICU_ward_TypeE()
                        phc9_to_cc_severe_case += 1
                    else:
                        DH_SevereTypeE()
                        dh_refer_PHC9 += 1  # Severe cases
                else:  # Type d patients
                    if ICU_ventilator.available_quantity() < 1:  # checks if there is a vacant bed in DH
                        cc_ventilator_TypeD()
                        phc9_to_cc_severe_case += 1
                    else:
                        dh_refer_PHC9 += 1  # Severe cases
                        DH_SevereTypeD()


class covid_nurse_PHC9(sim.Component):
    global lab_covidcount_PHC9

    def process(self):

        global warmup_time
        global ipd_nurse_PHC9
        global ipd_nurse_time_PHC9
        global lab_covidcount_PHC9

        if env.now() <= warmup_time:
            yield self.request(ipd_nurse_PHC9)
            yield self.hold(sim.Uniform(2, 3).sample())
            self.release(ipd_nurse_PHC9)
        else:
            lab_covidcount_PHC9 += 1
            yield self.request(ipd_nurse_PHC9)
            t = sim.Uniform(2, 3).sample()
            yield self.hold(t)
            ipd_nurse_time_PHC9 += t
            self.release(ipd_nurse_PHC9)


class covid_lab_PHC9(sim.Component):

    def process(self):

        global lab_technician_PHC9
        global lab_time_PHC9
        global lab_q_waiting_time_PHC9
        global warmup_time
        global lab_covidcount_PHC9

        if env.now() <= warmup_time:
            yield self.request(lab_technician_PHC9)
            yield self.hold(sim.Uniform(1, 2).sample())
            self.release(lab_technician_PHC9)
        else:
            lab_covidcount_PHC9 += 1
            yield self.request(lab_technician_PHC9)
            t = sim.Uniform(1, 2).sample()
            yield self.hold(t)
            lab_time_PHC9 += t
            self.release(lab_technician_PHC9)
            x = random.randint(0, 100)
            if x < 33:  # confirmed posiive
                covid_doc_PHC9()
            elif 33 < x < 67:  # symptomatic negative, retesting
                retesting_PHC9()
            else:
                Pharmacy_PHC9()


class retesting_PHC9(sim.Component):

    def process(self):

        global retesting_count_PHC9
        global warmup_time

        if env.now() <= warmup_time:
            yield self.hold(1440)
            covid_doc_PHC9()
        else:
            retesting_count_PHC9 += 1
            yield self.hold(1440)
            covid_doc_PHC9()


class covid_doc_PHC9(sim.Component):

    def process(self):
        global MO_covid_time_PHC9
        global doc_OPD_PHC9
        global warmup_time
        global covid_q_PHC9
        global covid_patient_time_PHC9
        global medicine_cons_time_PHC9

        if env.now() <= warmup_time:
            self.enter(covid_q_PHC9)
            yield self.request(doc_OPD_PHC9)
            self.leave(covid_q_PHC9)
            yield self.hold(sim.Uniform(3, 6).sample())
            self.release(doc_OPD_PHC9)
        else:
            in_time = env.now()
            self.enter(covid_q_PHC9)
            yield self.request(doc_OPD_PHC9)
            self.leave(covid_q_PHC9)
            t = sim.Uniform(3, 6).sample()
            yield self.hold(t)
            MO_covid_time_PHC9 += t
            medicine_cons_time_PHC9 += t
            self.release(doc_OPD_PHC9)
            covid_patient_time_PHC9 += env.now() - in_time


global l10  # temp lab count
l10 = 0
global o_PHC10  # temp opd count
o_PHC10 = 0


# PHC 10
class PatientGenerator_PHC10(sim.Component):
    global shift_PHC10
    shift_PHC10 = 0
    No_of_days_PHC10 = 0

    total_OPD_patients_PHC10 = 0

    def process(self):

        global env
        global warmup_time
        global opd_iat_PHC10
        global days_PHC10
        global medicine_cons_time_PHC10
        global shift_PHC10
        global phc1_doc_time_PHC10

        self.sim_time_PHC10 = 0  # local variable defined for dividing each day into shits
        self.z_PHC10 = 0
        self.admin_count_PHC10 = 0
        k_PHC10 = 0

        while self.z_PHC10 % 3 == 0:  # condition to run simulation for 8 hour shifts
            PatientGenerator_PHC10.No_of_days_PHC10 += 1  # class variable to track number of days passed
            while self.sim_time_PHC10 < 360:  # from morning 8 am to afternoon 2 pm (in minutes)
                if env.now() <= warmup_time:
                    pass
                else:
                    OPD_PHC10()
                o = sim.Exponential(opd_iat_PHC10).sample()
                yield self.hold(o)
                self.sim_time_PHC10 += o

            while 360 <= self.sim_time_PHC10 < 480:  # condition for admin work after opd hours are over
                k_PHC10 = int(sim.Normal(100, 20).bounded_sample(60, 140))
                """For sensitivity analysis. Admin work added to staff nurse rather than doctor"""
                if env.now() <= warmup_time:
                    pass
                else:
                    medicine_cons_time_PHC10 += k_PHC10  # conatns all doctor service times
                    phc1_doc_time_PHC10 += k_PHC10
                yield self.hold(120)
                self.sim_time_PHC10 = 481
            self.z_PHC10 += 3
            self.sim_time_PHC10 = 0
            # PatientGenerator1.No_of_shifts += 3
            yield self.hold(959)  # holds simulation for 2 shifts


class OPD_PHC10(sim.Component):
    Patient_log_PHC10 = {}

    def setup(self):

        self.dic = {}  # local dictionary for temporarily   storing generated patients
        # with attributes
        self.time_of_visit = [[0], [0], [0]]  # initializing for assigning time of visits
        self.regis_time = round(env.now())  # registration time is the current simulation time
        self.id = PatientGenerator_PHC10.total_OPD_patients_PHC10  # patient count is patient id
        self.age_random = random.randint(0, 1000)  # assigning age to population based on census 2011 gurgaon
        if self.age_random <= 578:
            self.age = random.randint(0, 30)
        else:
            self.age = random.randint(31, 100)
        self.sex = random.choice(["male", "female"])  # Equal probability of male and female patient
        # require lab tests
        self.lab_required = random.choice(["True", "False"])  # Considering nearly half of all the patients
        self.radiography_required = random.choice(["True", "False"])
        y = random.randint(0, 999)
        self.consultation = random.choice([y])  # for medicine, gynea, pead, denta
        self.visits_assigned = random.randint(1, 10)  # assigning number of visits visits
        self.dic = {"ID": self.id, "Age": self.age, "Sex": self.sex, "Lab": self.lab_required,
                    "Registration_Time": self.regis_time, "No_of_visits": self.visits_assigned,
                    "Time_of_visit": self.time_of_visit, "Radiography": self.radiography_required,
                    "Consultation": self.consultation}
        OPD_PHC10.Patient_log_PHC10[PatientGenerator_PHC10.total_OPD_patients_PHC10] = self.dic

        self.process()

    def process(self):

        global c10
        global medicine_q_PHC10
        global doc_OPD_PHC10
        global opd_ser_time_mean_PHC10
        global opd_ser_time_sd_PHC10
        global medicine_count_PHC10
        global medicine_cons_time_PHC10
        global opd_q_waiting_time_PHC10
        global ncd_count_PHC10
        global ncd_nurse_PHC10
        global ncd_time_PHC10
        global warmup_time
        global l10
        global phc1_doc_time_PHC10

        if env.now() <= warmup_time:
            p = random.randint(0, 10)
            if p < 2:
                COVID_OPD_PHC10()
            if OPD_PHC10.Patient_log_PHC10[PatientGenerator_PHC10.total_OPD_patients_PHC10]["Age"] > 30:
                yield self.request(ncd_nurse_PHC10)
                ncd_service = sim.Uniform(2, 5).sample()
                yield self.hold(ncd_service)
            self.enter(medicine_q_PHC10)
            yield self.request(doc_OPD_PHC10)
            self.leave(medicine_q_PHC10)
            o = sim.Normal(opd_ser_time_mean_PHC10, opd_ser_time_sd_PHC10).bounded_sample(0.3)
            yield self.hold(o)
            self.release(doc_OPD_PHC10)
            if OPD_PHC10.Patient_log_PHC10[PatientGenerator_PHC10.total_OPD_patients_PHC10]["Lab"] == "True":
                Lab_PHC10()
            Pharmacy_PHC10()
        else:
            l10 += 1
            medicine_count_PHC10 += 1
            p = random.randint(0, 10)
            if p < 2:
                COVID_OPD_PHC10()
            if OPD_PHC10.Patient_log_PHC10[PatientGenerator_PHC10.total_OPD_patients_PHC10]["Age"] > 30:
                ncd_count_PHC10 += 1
                yield self.request(ncd_nurse_PHC10)
                ncd_service = sim.Uniform(2, 5).sample()
                yield self.hold(ncd_service)
                ncd_time_PHC10 += ncd_service
            # doctor opd starts from here
            entry_time = env.now()
            self.enter(medicine_q_PHC10)
            yield self.request(doc_OPD_PHC10)
            self.leave(medicine_q_PHC10)
            exit_time = env.now()
            opd_q_waiting_time_PHC10.append(exit_time - entry_time)  # stores waiting time in the queue
            o = sim.Normal(opd_ser_time_mean_PHC10, opd_ser_time_sd_PHC10).bounded_sample(0.3)
            yield self.hold(o)
            phc1_doc_time_PHC10 += o
            medicine_cons_time_PHC10 += o
            self.release(doc_OPD_PHC10)
            # lab starts from here
            t = random.randint(0, 1000)
            # changed here
            if OPD_PHC10.Patient_log_PHC10[PatientGenerator_PHC10.total_OPD_patients_PHC10]["Lab"] == "True":
                Lab_PHC10()
            Pharmacy_PHC10()


class COVID_OPD_PHC10(sim.Component):

    def process(self):

        global ipd_nurse_PHC10
        global delivery_nurse_time_PHC10

        if env.now() <= warmup_time:
            yield self.request(ipd_nurse_PHC10)
            h1 = sim.Uniform(5, 10).sample()
            yield self.hold(h1)
            self.release(ipd_nurse_PHC10)
            OPD_covidtest_PHC10()
            yield self.hold(sim.Uniform(15, 30).sample())  # patient waits for the result
        else:
            yield self.request(ipd_nurse_PHC10)
            h1 = sim.Uniform(5, 10).sample()
            yield self.hold(h1)
            self.release(ipd_nurse_PHC10)
            delivery_nurse_time_PHC10 += h1
            OPD_covidtest_PHC10()
            yield self.hold(sim.Uniform(15, 30).sample())


class OPD_covidtest_PHC10(sim.Component):

    def process(self):
        global lab_covidcount_PHC10
        global lab_technician_PHC10
        global lab_time_PHC10
        global warmup_time

        if env.now() <= warmup_time:
            yield self.request(lab_technician_PHC10)
            t = sim.Uniform(1, 2).sample()
            yield self.hold(t)
            self.release(lab_technician_PHC10)
        else:
            lab_covidcount_PHC10 += 1
            yield self.request(lab_technician_PHC10)
            t = sim.Uniform(1, 2).sample()
            yield self.hold(t)
            lab_time_PHC10 += t
            self.release(lab_technician_PHC10)


class Pharmacy_PHC10(sim.Component):

    def process(self):

        global pharmacist_PHC10
        global pharmacy_time_PHC10
        global pharmacy_q_PHC10
        global pharmacy_q_waiting_time_PHC10
        global warmup_time
        global pharmacy_count_PHC10

        if env.now() < warmup_time:
            self.enter(pharmacy_q_PHC10)
            yield self.request(pharmacist_PHC10)
            self.leave(pharmacy_q_PHC10)
            # service_time = sim.Uniform(1, 2.5).sample()
            service_time = sim.Normal(2.083, 0.72).bounded_sample(.67)
            yield self.hold(service_time)
            self.release(pharmacist_PHC10)
        else:
            pharmacy_count_PHC10 += 1
            e1 = env.now()
            self.enter(pharmacy_q_PHC10)
            yield self.request((pharmacist_PHC10, 1))
            self.leave(pharmacy_q_PHC10)
            pharmacy_q_waiting_time_PHC10.append(env.now() - e1)
            service_time = sim.Normal(2.083, 0.72).bounded_sample(.67)
            yield self.hold(service_time)
            self.release((pharmacist_PHC10, 1))
            pharmacy_time_PHC10 += service_time


class Delivery_patient_generator_PHC10(sim.Component):
    Delivery_list = {}

    def process(self):
        global delivery_iat_PHC10
        global warmup_time
        global delivery_count_PHC10
        global days_PHC10
        global childbirth_count_PHC10
        global N_PHC10

        while True:
            if env.now() <= warmup_time:
                pass
            else:
                childbirth_count_PHC10 += 1
                self.registration_time = round(env.now())
                if 0 < (self.registration_time - N_PHC10 * 1440) < 480:
                    Delivery_with_doctor_PHC10(urgent=True)  # sets priority
                else:
                    Delivery_no_doc_PHC10(urgent=True)
            self.hold_time = sim.Exponential(delivery_iat_PHC10).sample()
            yield self.hold(self.hold_time)
            N_PHC10 = int(env.now() / 1440)


class Delivery_no_doc_PHC10(sim.Component):

    def process(self):
        global ipd_nurse_PHC10
        global ipd_nurse_PHC10
        global doc_OPD_PHC10
        global delivery_bed_PHC10
        global warmup_time
        global e_beds_PHC10
        global ipd_nurse_time_PHC10
        global MO_del_time_PHC10
        global in_beds_PHC10
        global delivery_nurse_time_PHC10
        global inpatient_del_count_PHC10
        global delivery_count_PHC10
        global emergency_bed_time_PHC10
        global ipd_bed_time_PHC10
        global emergency_nurse_time_PHC10
        global referred_PHC10
        global fail_count_PHC10

        if env.now() <= warmup_time:
            t_nurse = sim.Uniform(120, 240, 'minutes').sample()
            t_bed = sim.Uniform(360, 600).sample()
            yield self.request(ipd_nurse_PHC10)
            yield self.hold(t_nurse)
            self.release(ipd_nurse_PHC10)
            yield self.request(delivery_bed_PHC10, fail_delay=120)
            if self.failed():
                pass
            else:
                yield self.hold(t_bed)
                self.release(delivery_bed_PHC10)
                yield self.request(in_beds_PHC10)
                yield self.hold(sim.Uniform(240, 1440, 'minutes').bounded_sample(0))
                self.release(in_beds_PHC10)
        else:
            delivery_count_PHC10 += 1
            t_bed = sim.Uniform(360, 600).sample()  # delivery bed, nurse time
            t_nur = sim.Uniform(120, 240).sample()
            delivery_nurse_time_PHC10 += t_nur
            yield self.request(ipd_nurse_PHC10)
            yield self.hold(t_nur)
            self.release(ipd_nurse_PHC10)  # delivery nurse and delivery beds are released simultaneoulsy
            yield self.request(delivery_bed_PHC10, fail_delay=120)
            if self.failed():
                fail_count_PHC10 += 1
                delivery_count_PHC10 -= 1
                pass
            else:
                yield self.hold(t_bed)
                self.release(delivery_bed_PHC10)
                yield self.request(in_beds_PHC10)
                t_bed1 = sim.Uniform(240, 1440).sample()
                yield self.hold(t_bed1)
                ipd_bed_time_PHC10 += t_bed1


class Delivery_with_doctor_PHC10(sim.Component):

    def process(self):
        global ipd_nurse_PHC10
        global ipd_nurse_PHC10
        global doc_OPD_PHC10
        global delivery_bed_PHC10
        global warmup_time
        global e_beds_PHC10
        global ipd_nurse_time_PHC10
        global MO_del_time_PHC10
        global in_beds_PHC10
        global delivery_nurse_time_PHC10
        global inpatient_del_count_PHC10
        global delivery_count_PHC10
        global emergency_bed_time_PHC10
        global ipd_bed_time_PHC10
        global emergency_nurse_time_PHC10
        global referred_PHC10
        global fail_count_PHC10
        global opd_q_waiting_time_PHC10
        global phc1_doc_time_PHC10
        global medicine_cons_time_PHC10
        global medicine_q_PHC10

        if env.now() <= warmup_time:
            t_doc = sim.Uniform(30, 60).sample()
            t_bed = sim.Uniform(240, 360).sample()
            t_nurse = sim.Uniform(120, 240, 'minutes').sample()
            self.enter_at_head(medicine_q_PHC10)
            yield self.request(doc_OPD_PHC10, fail_delay=20)
            if self.failed():  # if doctor is busy staff nurse takes care
                self.leave(medicine_q_PHC10)
                yield self.request(ipd_nurse_PHC10)
                yield self.hold(t_nurse)
                self.release(ipd_nurse_PHC10)
                yield self.request(doc_OPD_PHC10)
                yield self.hold(t_doc)
                self.release(doc_OPD_PHC10)
                self.release(delivery_bed_PHC10)
                yield self.request(delivery_bed_PHC10, fail_delay=120)
                if self.failed():
                    pass
                else:
                    yield self.hold(sim.Uniform(6 * 60, 10 * 60, 'minutes').sample())
                    self.release(delivery_bed_PHC10)
                    yield self.request(in_beds_PHC10)
                    yield self.hold(sim.Uniform(240, 1440, 'minutes').sample())
                    self.release()
            else:
                self.leave(medicine_q_PHC10)
                yield self.hold(t_doc)
                self.release(doc_OPD_PHC10)
                yield self.request(ipd_nurse_PHC10)
                yield self.hold(t_nurse)
                self.release(ipd_nurse_PHC10)
                yield self.request(delivery_bed_PHC10)
                yield self.hold(sim.Uniform(6 * 60, 10 * 60, 'minutes').sample())
                self.release(delivery_bed_PHC10)
                yield self.request(in_beds_PHC10)
                yield self.hold(sim.Uniform(240, 1440, 'minutes').bounded_sample(0))  # holding patient for min 4 hours
                # to 48 hours
                self.release(in_beds_PHC10)
        else:
            delivery_count_PHC10 += 1
            entry_time1 = env.now()
            self.enter_at_head(medicine_q_PHC10)
            yield self.request(doc_OPD_PHC10, fail_delay=20)
            t_doc = sim.Uniform(30, 60).sample()
            t_bed = sim.Uniform(360, 600).sample()  # delivery bed, nurse time
            t_nur = sim.Uniform(120, 240).sample()
            delivery_nurse_time_PHC10 += t_nur
            phc1_doc_time_PHC10 += t_doc
            MO_del_time_PHC10 += t_doc  # changed here
            medicine_cons_time_PHC10 += t_doc
            if self.failed():  # if doctor is busy staff nurse takes care
                self.leave(medicine_q_PHC10)
                exit_time1 = env.now()
                opd_q_waiting_time_PHC10.append(exit_time1 - entry_time1)  # stores waiting time in the queue
                yield self.request(ipd_nurse_PHC10)
                yield self.hold(t_nur)
                self.release(ipd_nurse_PHC10)
                # changed here
                yield self.request(doc_OPD_PHC10)
                yield self.hold(t_doc)
                self.release(doc_OPD_PHC10)
                yield self.request(delivery_bed_PHC10, fail_delay=120)
                if self.failed():
                    fail_count_PHC10 += 1
                    delivery_count_PHC10 -= 1
                else:
                    yield self.hold(t_bed)
                    self.release(delivery_bed_PHC10)
                    # after delivery patient shifts to IPD and requests nurse and inpatient bed
                    # changed here, removed ipd nurse
                    yield self.request(in_beds_PHC10)
                    # t_n = sim.Uniform(20, 30).sample()          # inpatient nurse time in ipd after delivery
                    t_bed2 = sim.Uniform(240, 1440).sample()  # inpatient beds post delivery stay
                    # yield self.hold(t_n)
                    # self.release(ipd_nurse1)
                    # ipd_nurse_time1 += t_n
                    yield self.hold(t_bed2)
                    ipd_bed_time_PHC10 += t_bed2
            else:
                self.leave(medicine_q_PHC10)
                exit_time1 = env.now()
                opd_q_waiting_time_PHC10.append(exit_time1 - entry_time1)  # stores waiting time in the queue
                yield self.hold(t_doc)
                self.release(doc_OPD_PHC10)
                yield self.request(ipd_nurse_PHC10)
                yield self.hold(t_nur)
                self.release(ipd_nurse_PHC10)  # delivery nurse and delivery beds are released simultaneoulsy
                yield self.request(delivery_bed_PHC10)
                yield self.hold(t_bed)
                self.release(delivery_bed_PHC10)
                yield self.request(in_beds_PHC10)
                t_bed1 = sim.Uniform(240, 1440).sample()
                yield self.hold(t_bed1)
                ipd_bed_time_PHC10 += t_bed1


class Lab_PHC10(sim.Component):

    def process(self):
        global lab_q_PHC10
        global lab_technician_PHC10
        global lab_time_PHC10
        global lab_q_waiting_time_PHC10
        global warmup_time
        global lab_count_PHC10
        global o_PHC10

        if env.now() <= warmup_time:
            self.enter(lab_q_PHC10)
            yield self.request(lab_technician_PHC10)
            self.leave(lab_q_PHC10)
            yp = (sim.Normal(3.456, .823).bounded_sample(2))
            y0 = yp
            yield self.hold(y0)
            self.release(lab_technician_PHC10)
        else:
            lab_count_PHC10 += 1
            self.enter(lab_q_PHC10)
            a0 = env.now()
            yield self.request(lab_technician_PHC10)
            self.leave(lab_q_PHC10)
            lab_q_waiting_time_PHC10.append(env.now() - a0)
            f1 = env.now()
            yp = (sim.Normal(3.456, .823).bounded_sample(2))
            y0 = yp
            yield self.hold(y0)
            self.release(lab_technician_PHC10)
            f2 = env.now()
            lab_time_PHC10 += f2 - f1
            o_PHC10 += 1


class IPD_PatientGenerator_PHC10(sim.Component):
    global IPD1_iat_PHC10
    global warmup_time
    IPD_List_PHC10 = {}  # log of all the IPD patients stored here
    patient_count_PHC10 = 0
    p_count_PHC10 = 0  # log of patients in each replication

    def process(self):
        global days_PHC10
        M = 0
        while True:
            if env.now() <= warmup_time:
                pass
            else:
                IPD_PatientGenerator_PHC10.patient_count_PHC10 += 1
                IPD_PatientGenerator_PHC10.p_count_PHC10 += 1
            self.registration_time = env.now()
            self.id = IPD_PatientGenerator_PHC10.patient_count_PHC10
            self.age = round(random.normalvariate(35, 8))
            self.sex = random.choice(["Male", "Female"])
            IPD_PatientGenerator_PHC10.IPD_List_PHC10[self.id] = [self.registration_time, self.id, self.age, self.sex]
            if 0 < (self.registration_time - M * 1440) < 480:
                IPD_with_doc_PHC10(urgent=True)
            else:
                IPD_no_doc_PHC10(urgent=True)
            self.hold_time_1 = sim.Exponential(IPD1_iat_PHC10).sample()
            yield self.hold(self.hold_time_1)
            M = int(env.now() / 1440)


class IPD_no_doc_PHC10(sim.Component):

    def process(self):
        global MO_ipd_PHC10
        global ipd_nurse_PHC10
        global in_beds_PHC10
        global ipd_nurse_time_PHC10
        global warmup_time
        global ipd_bed_time_PHC10
        global ipd_nurse_time_PHC10
        global medicine_q_PHC10
        global ipd_MO_time_PHC10

        if env.now() <= warmup_time:

            yield self.request(in_beds_PHC10, ipd_nurse_PHC10)
            temp = sim.Uniform(30, 60, 'minutes').sample()
            yield self.hold(temp)
            self.release(ipd_nurse_PHC10)
            yield self.hold(sim.Triangular(60, 360, 180, 'minutes').bounded_sample(0))
            self.release(in_beds_PHC10)
        else:
            t_bed = sim.Triangular(60, 360, 180, 'minutes').sample()
            t_nurse = sim.Uniform(30, 60, 'minutes').sample()
            yield self.request(in_beds_PHC10, ipd_nurse_PHC10)
            yield self.hold(t_nurse)
            self.release(ipd_nurse_PHC10)
            yield self.hold(t_bed)
            self.release(in_beds_PHC10)
            ipd_bed_time_PHC10 += t_bed
            ipd_nurse_time_PHC10 += t_nurse


class IPD_with_doc_PHC10(sim.Component):

    def process(self):
        global MO_ipd_PHC10
        global ipd_nurse_PHC10
        global in_beds_PHC10
        global MO_ipd_time_PHC10
        global ipd_nurse_time_PHC10
        global warmup_time
        global ipd_bed_time_PHC10
        global ipd_nurse_time_PHC10
        global emergency_refer_PHC10
        global medicine_q_PHC10
        global ipd_MO_time_PHC10
        global opd_q_waiting_time_PHC10
        global phc1_doc_time_PHC10
        global medicine_cons_time_PHC10

        if env.now() <= warmup_time:
            self.enter_at_head(medicine_q_PHC10)
            yield self.request(doc_OPD_PHC10, fail_delay=20)
            doc_time = round(sim.Uniform(10, 30, 'minutes').sample())
            if self.failed():
                self.leave(medicine_q_PHC10)
                yield self.request(ipd_nurse_PHC10)
                temp = sim.Uniform(30, 60, 'minutes').sample()
                yield self.hold(temp)
                self.release(ipd_nurse_PHC10)
                yield self.request(doc_OPD_PHC10)
                yield self.hold(doc_time)
                self.release(doc_OPD_PHC10)
                yield self.request(in_beds_PHC10)
                yield self.hold(sim.Triangular(60, 360, 180, 'minutes').bounded_sample(0))
                self.release(in_beds_PHC10)
            else:
                self.leave(medicine_q_PHC10)
                yield self.hold(doc_time)
                self.release(doc_OPD_PHC10)
                yield self.request(in_beds_PHC10, ipd_nurse_PHC10)
                temp = sim.Uniform(30, 60, 'minutes').sample()
                yield self.hold(temp)
                self.release(ipd_nurse_PHC10)
                yield self.hold(sim.Triangular(60, 360, 180, 'minutes').bounded_sample(0))
                self.release(in_beds_PHC10)
        else:
            self.enter_at_head(medicine_q_PHC10)
            entry_time2 = env.now()
            yield self.request(doc_OPD_PHC10, fail_delay=20)
            doc_time = sim.Uniform(10, 30, 'minutes').sample()
            t_bed = sim.Triangular(60, 360, 180, 'minutes').sample()
            t_nurse = sim.Uniform(30, 60, 'minutes').sample()
            phc1_doc_time_PHC10 += doc_time
            medicine_cons_time_PHC10 += doc_time
            if self.failed():
                self.leave(medicine_q_PHC10)
                exit_time2 = env.now()
                opd_q_waiting_time_PHC10.append(exit_time2 - entry_time2)  # stores waiting time in the queue
                yield self.request(ipd_nurse_PHC10)
                yield self.hold(t_nurse)
                self.release(ipd_nurse_PHC10)
                yield self.request(doc_OPD_PHC10)
                yield self.hold(doc_time)
                self.release(doc_OPD_PHC10)
                yield self.request(in_beds_PHC10)
                yield self.hold(t_bed)
                self.release(in_beds_PHC10)
                ipd_bed_time_PHC10 += t_bed
                ipd_MO_time_PHC10 += doc_time
                ipd_nurse_time_PHC10 += t_nurse
            else:
                self.leave(medicine_q_PHC10)
                exit_time3 = env.now()
                opd_q_waiting_time_PHC10.append(exit_time3 - entry_time2)  # stores waiting time in the queue
                yield self.hold(doc_time)
                self.release(doc_OPD_PHC10)
                yield self.request(in_beds_PHC10, ipd_nurse_PHC10)
                yield self.hold(t_nurse)
                self.release(ipd_nurse_PHC10)
                yield self.hold(t_bed)
                self.release(in_beds_PHC10)
                ipd_bed_time_PHC10 += t_bed
                ipd_MO_time_PHC10 += doc_time
                ipd_nurse_time_PHC10 += t_nurse


class ANC_PHC10(sim.Component):
    global ANC_iat_PHC10
    global days_PHC10
    days_PHC10 = 0
    env = sim.Environment()
    No_of_shifts_PHC10 = 0  # tracks number of shifts completed during the simulation time
    No_of_days_PHC10 = 0
    ANC_List_PHC10 = {}
    anc_count_PHC10 = 0
    ANC_p_count_PHC10 = 0

    def process(self):

        global days_PHC10

        while True:  # condition to run simulation for 8 hour shifts
            x = env.now() - 1440 * days_PHC10
            if 0 <= x < 480:
                ANC_PHC10.anc_count_PHC10 += 1  # counts overall patients throghout simulation
                ANC_PHC10.ANC_p_count_PHC10 += 1  # counts patients in each replication
                id = ANC_PHC10.anc_count_PHC10
                age = 223
                day_of_registration = ANC_PHC10.No_of_days_PHC10
                visit = 1
                x0 = round(env.now())
                x1 = x0 + 14 * 7 * 24 * 60
                x2 = x0 + 20 * 7 * 24 * 60
                x3 = x0 + 24 * 7 * 24 * 60
                scheduled_visits = [[0], [0], [0], [0]]
                scheduled_visits[0] = x0
                scheduled_visits[1] = x1
                scheduled_visits[2] = x2
                scheduled_visits[3] = x3
                dic = {"ID": id, "Age": age, "Visit Number": visit, "Registration day": day_of_registration,
                       "Scheduled Visit": scheduled_visits}
                ANC_PHC10.ANC_List_PHC10[id] = dic
                ANC_Checkup_PHC10()
                ANC_followup_PHC10(at=ANC_PHC10.ANC_List_PHC10[id]["Scheduled Visit"][1])
                ANC_followup_PHC10(at=ANC_PHC10.ANC_List_PHC10[id]["Scheduled Visit"][2])
                ANC_followup_PHC10(at=ANC_PHC10.ANC_List_PHC10[id]["Scheduled Visit"][3])
                hold_time = sim.Exponential(ANC_iat_PHC10).sample()
                yield self.hold(hold_time)
            else:
                yield self.hold(960)
                days_PHC10 = int(env.now() / 1440)  # holds simulation for 2 shifts


class ANC_Checkup_PHC10(sim.Component):
    anc_checkup_count_PHC10 = 0

    def process(self):

        global warmup_time
        global ipd_nurse_PHC10
        global delivery_nurse_time_PHC10
        global lab_q_PHC10
        global lab_technician_PHC10
        global lab_time_PHC10
        global lab_q_waiting_time_PHC10
        global warmup_time
        global lab_count_PHC10

        if env.now() <= warmup_time:
            yield self.request(ipd_nurse_PHC10)
            temp = sim.Triangular(8, 20.6, 12.3).sample()
            yield self.hold(temp)  # time taken from a study on ANC visits in Tanzania
            self.release(ipd_nurse_PHC10)
            self.enter(lab_q_PHC10)
            yield self.request(lab_technician_PHC10)
            self.leave(lab_q_PHC10)
            yp = (sim.Normal(5, 1).bounded_sample())
            y0 = yp
            yield self.hold(y0)
            self.release(lab_technician_PHC10)
        else:
            ANC_Checkup_PHC10.anc_checkup_count_PHC10 += 1
            yield self.request(ipd_nurse_PHC10)
            temp = sim.Triangular(8, 20.6, 12.3).sample()
            delivery_nurse_time_PHC10 += temp
            yield self.hold(temp)  # time taken from a study on ANC visits in Tanzania
            self.release(ipd_nurse_PHC10)
            lab_count_PHC10 += 1
            # changed here
            a0 = env.now()
            self.enter(lab_q_PHC10)
            yield self.request(lab_technician_PHC10)
            self.leave(lab_q_PHC10)
            lab_q_waiting_time_PHC10.append(env.now() - a0)
            yp = (sim.Normal(5, 1).bounded_sample())
            y0 = yp
            yield self.hold(y0)
            self.release(lab_technician_PHC10)
            lab_time_PHC10 += y0


class ANC_followup_PHC10(sim.Component):
    followup_count = 0

    def process(self):

        global warmup_time
        global ipd_nurse_PHC10
        global q_ANC_PHC10  # need change here and corrosponding arrays
        global delivery_nurse_time_PHC10
        global lab_time_PHC10
        global lab_q_waiting_time_PHC1

        if env.now() <= warmup_time:
            for key in ANC_PHC10.ANC_List_PHC10:  # for identifying and updating ANC visit number
                x0 = env.now()
                x1 = ANC_PHC10.ANC_List_PHC10[key]["Scheduled Visit"][1]
                x2 = ANC_PHC10.ANC_List_PHC10[key]["Scheduled Visit"][2]
                x3 = ANC_PHC10.ANC_List_PHC10[key]["Scheduled Visit"][3]
                if 0 <= (x1 - x0) < 481:
                    ANC_PHC10.ANC_List_PHC10[key]["Scheduled Visit"][1] = float("inf")
                    ANC_PHC10.ANC_List_PHC10[key]["Visit Number"] = 2
                elif 0 <= (x2 - x0) < 481:
                    ANC_PHC10.ANC_List_PHC10[key]["Scheduled Visit"][2] = float("inf")
                    ANC_PHC10.ANC_List_PHC10[key]["Visit Number"] = 3
                elif 0 <= (x3 - x0) < 481:
                    ANC_PHC10.ANC_List_PHC10[key]["Scheduled Visit"][3] = float("inf")
                    ANC_PHC10.ANC_List_PHC10[key]["Visit Number"] = 4

            yield self.request(ipd_nurse_PHC10)
            temp = sim.Triangular(3.33, 13.16, 6.50).sample()
            yield self.hold(temp)
            self.release(ipd_nurse_PHC10)
            self.enter(lab_q_PHC10)
            yield self.request(lab_technician_PHC10)
            self.leave(lab_q_PHC10)
            yp = (sim.Normal(3.456, .823).bounded_sample(2))
            y0 = yp
            yield self.hold(y0)
            self.release(lab_technician_PHC10)

        else:
            for key in ANC_PHC10.ANC_List_PHC10:  # for identifying and updating ANC visit number
                x0 = env.now()
                x1 = ANC_PHC10.ANC_List_PHC10[key]["Scheduled Visit"][1]
                x2 = ANC_PHC10.ANC_List_PHC10[key]["Scheduled Visit"][2]
                x3 = ANC_PHC10.ANC_List_PHC10[key]["Scheduled Visit"][3]
                if 0 <= (x1 - x0) < 481:
                    ANC_PHC10.ANC_List_PHC10[key]["Scheduled Visit"][1] = float("inf")
                    ANC_PHC10.ANC_List_PHC10[key]["Visit Number"] = 2
                elif 0 <= (x2 - x0) < 481:
                    ANC_PHC10.ANC_List_PHC10[key]["Scheduled Visit"][2] = float("inf")
                    ANC_PHC10.ANC_List_PHC10[key]["Visit Number"] = 3
                elif 0 <= (x3 - x0) < 481:
                    ANC_PHC10.ANC_List_PHC10[key]["Scheduled Visit"][3] = float("inf")
                    ANC_PHC10.ANC_List_PHC10[key]["Visit Number"] = 4

            yield self.request(ipd_nurse_PHC10)
            temp = sim.Triangular(3.33, 13.16, 6.50).sample()
            delivery_nurse_time_PHC10 += temp
            yield self.hold(temp)
            self.release(ipd_nurse_PHC10)
            a0 = env.now()
            self.enter(lab_q_PHC10)
            yield self.request(lab_technician_PHC10)
            self.leave(lab_q_PHC10)
            lab_q_waiting_time_PHC10.append(env.now() - a0)
            yp = (sim.Normal(3.456, .823).bounded_sample(2))
            y0 = yp
            yield self.hold(y0)
            self.release(lab_technician_PHC10)
            lab_time_PHC10 += y0


class CovidGenerator_PHC10(sim.Component):

    def process(self):
        global d1_PHC10
        global warmup_time
        global covid_iat_PHC10
        global phc_covid_iat
        global j

        while True:

            if env.now() < warmup_time:
                if 0 <= (env.now() - d1_PHC10 * 1440) < 480:
                    covid_PHC10()
                    yield self.hold(1440 / 3)
                    d1_PHC10 = int(env.now() / 1440)
                else:
                    yield self.hold(960)
                    d1_PHC10 = int(env.now() / 1440)

            else:
                a = phc_covid_iat[j]
                if 0 <= (env.now() - d1_PHC10 * 1440) < 480:
                    covid_PHC10()
                    yield self.hold(sim.Exponential(a).sample())
                    d1_PHC10 = int(env.now() / 1440)
                else:

                    yield self.hold(960)
                    d1_PHC10 = int(env.now() / 1440)


class covid_PHC10(sim.Component):

    def process(self):

        global home_refer_PHC10
        global chc_refer_PHC10
        global dh_refer_PHC10
        global isolation_ward_refer_PHC10
        global covid_patient_time_PHC10
        global covid_count_PHC10
        global warmup_time
        global ipd_nurse_PHC10
        global ipd_nurse_time_PHC10
        global doc_OPD_PHC10
        global MO_covid_time_PHC10
        global phc2chc_count_PHC10
        global warmup_time
        global home_isolation_PHC10

        global ICU_oxygen
        global phc10_to_cc_severe_case
        global phc10_to_cc_dist
        global phc10_2_cc

        if env.now() < warmup_time:
            covid_nurse_PHC10()
            covid_lab_PHC10()
            x = random.randint(0, 1000)
            if x <= 940:
                a = random.randint(0, 100)
                if a >= 90:
                    cc_isolation()
            elif 940 < x <= 980:
                pass
            # CovidCare_chc2()
            else:
                pass
                #SevereCase()
        else:
            covid_count_PHC10 += 1
            covid_nurse_PHC10()
            covid_lab_PHC10()
            x = random.randint(0, 1000)
            if x <= 940:  # mild cases
                home_refer_PHC10 += 1
                a = random.randint(0, 100)
                if a >= 90:  # 10 % for institutional quarantine
                    isolation_ward_refer_PHC10 += 1
                    cc_isolation()
                else:
                    home_isolation_PHC10 += 1
            elif 940 < x <= 980:  # moderate cases
                chc_refer_PHC10 += 1
                phc2chc_count_PHC10 += 1
                CovidCare_chc3()
            else:  # severe case
                s = random.randint(0, 100)
                if s < 50:  # Type f patients
                    if ICU_oxygen.available_quantity() < 1:  # checks if there is a vacant bed in DH
                        phc10_to_cc_severe_case += 1
                        phc10_to_cc_dist.append(phc10_2_cc)
                        cc_Type_F()  # patient refered tpo CC
                    else:
                        DH_SevereTypeF()
                        dh_refer_PHC10 += 1  # Severe cases
                elif 50 <= s <= 74:  # E type patients
                    if ICU_ventilator.available_quantity() < 1:  # checks if there is a vacant bed in DH
                        cc_ICU_ward_TypeE()
                        phc10_to_cc_severe_case += 1
                    else:
                        DH_SevereTypeE()
                        dh_refer_PHC10 += 1  # Severe cases
                else:  # Type d patients
                    if ICU_ventilator.available_quantity() < 1:  # checks if there is a vacant bed in DH
                        cc_ventilator_TypeD()
                        phc10_to_cc_severe_case += 1
                    else:
                        dh_refer_PHC10 += 1  # Severe cases
                        DH_SevereTypeD()


class covid_nurse_PHC10(sim.Component):
    global lab_covidcount_PHC10

    def process(self):

        global warmup_time
        global ipd_nurse_PHC10
        global ipd_nurse_time_PHC10
        global lab_covidcount_PHC10

        if env.now() <= warmup_time:
            yield self.request(ipd_nurse_PHC10)
            yield self.hold(sim.Uniform(2, 3).sample())
            self.release(ipd_nurse_PHC10)
        else:
            lab_covidcount_PHC10 += 1
            yield self.request(ipd_nurse_PHC10)
            t = sim.Uniform(2, 3).sample()
            yield self.hold(t)
            ipd_nurse_time_PHC10 += t
            self.release(ipd_nurse_PHC10)


class covid_lab_PHC10(sim.Component):

    def process(self):

        global lab_technician_PHC10
        global lab_time_PHC10
        global lab_q_waiting_time_PHC10
        global warmup_time
        global lab_covidcount_PHC10

        if env.now() <= warmup_time:
            yield self.request(lab_technician_PHC10)
            yield self.hold(sim.Uniform(1, 2).sample())
            self.release(lab_technician_PHC10)
        else:
            lab_covidcount_PHC10 += 1
            yield self.request(lab_technician_PHC10)
            t = sim.Uniform(1, 2).sample()
            yield self.hold(t)
            lab_time_PHC10 += t
            self.release(lab_technician_PHC10)
            x = random.randint(0, 100)
            if x < 33:  # confirmed posiive
                covid_doc_PHC10()
            elif 33 < x < 67:  # symptomatic negative, retesting
                retesting_PHC10()
            else:
                Pharmacy_PHC10()


class retesting_PHC10(sim.Component):

    def process(self):

        global retesting_count_PHC10
        global warmup_time

        if env.now() <= warmup_time:
            yield self.hold(1440)
            covid_doc_PHC10()
        else:
            retesting_count_PHC10 += 1
            yield self.hold(1440)
            covid_doc_PHC10()


class covid_doc_PHC10(sim.Component):

    def process(self):
        global MO_covid_time_PHC10
        global doc_OPD_PHC10
        global warmup_time
        global covid_q_PHC10
        global covid_patient_time_PHC10
        global medicine_cons_time_PHC10

        if env.now() <= warmup_time:
            self.enter(covid_q_PHC10)
            yield self.request(doc_OPD_PHC10)
            self.leave(covid_q_PHC10)
            yield self.hold(sim.Uniform(3, 6).sample())
            self.release(doc_OPD_PHC10)
        else:
            in_time = env.now()
            self.enter(covid_q_PHC10)
            yield self.request(doc_OPD_PHC10)
            self.leave(covid_q_PHC10)
            t = sim.Uniform(3, 6).sample()
            yield self.hold(t)
            MO_covid_time_PHC10 += t
            medicine_cons_time_PHC10 += t
            self.release(doc_OPD_PHC10)
            covid_patient_time_PHC10 += env.now() - in_time


"District hospital code"


class DHPatient(sim.Component):
    env = sim.Environment()

    warm_up = 3 * 30 * 24 * 60
    Covid_count = 0

    def process(self):
        global Covid_iat
        global days
        global Covid_count
        global warmup_time
        global dh_covid_iat
        global j
        global dh_time

        while True:

            if env.now() <= warmup_time:
                DHPatientTest()
                t = sim.Exponential(Covid_iat).sample()
                yield self.hold(t)
            else:
                if 0 <= (env.now() - dh_time * 1440) < 480:
                    a = dh_covid_iat[j]
                    DHPatient.Covid_count += 1
                    DHPatientTest()
                    self.hold_time = sim.Exponential(a).sample()
                    yield self.hold(self.hold_time)
                else:

                    yield self.hold(961)
                    dh_time = int(env.now() / 1440)
                    j += 1




class DHPatientTest(sim.Component):
    CovidPatients_DH = 0
    DH_to_Home_refer = 0
    DH_Nurse_sample_collection_time = []
    DH_Nurse_sample_collection_wait_time = []
    DH_Doctor_initial_doctor_test_time = []
    DH_lab_time = []
    DH_lab_waiting_time = []

    def process(self):

        global warmup_time

        if env.now() < warmup_time:
            self.enter(CovidPatients_waitingline_DH)  # nurse takes sample
            yield self.request(nurse_DH_sample_collection)
            self.leave(CovidPatients_waitingline_DH)
            yield self.hold(sim.Uniform(2, 3, 'minutes').sample())
            self.release(nurse_DH_sample_collection)
            self.enter(waitingline_DH_lab)
            yield self.request(lab_technician_DH)
            yield self.hold(sim.Uniform(1, 2).sample())
            self.release(lab_technician_DH)
            yield self.hold(sim.Uniform(15, 30, 'minutes').sample())  # patient waits till test report is generated
            a1 = random.randint(0, 100)
            if a1 < 67:  # Covid Positive Patients
                yield self.request((doctor_DH_Gen, 1))
                yield self.hold(sim.Uniform(3, 6, 'minutes').sample())  # patient consults will doctors
                self.release(doctor_DH_Gen)
                DHPatients()
            elif 67 <= a1 < 87:
                RetestingDH()  # Asymptomatic patients
            else:
                pass  # Patients who tested negative, sent back to home
        else:
            DHPatientTest.CovidPatients_DH += 1
            a2 = env.now()
            self.enter(CovidPatients_waitingline_DH)  # nurse takes sample
            yield self.request(nurse_DH_sample_collection)
            self.leave(CovidPatients_waitingline_DH)
            a3 = env.now()
            a4 = a3 - a2
            DHPatientTest.DH_Nurse_sample_collection_wait_time.append(a4)  # lab test wait time
            a5 = sim.Uniform(2, 3, 'minutes').sample()
            yield self.hold(a5)
            self.release(nurse_DH_sample_collection)
            DHPatientTest.DH_Nurse_sample_collection_time.append(a5)
            a6 = env.now()
            self.enter(waitingline_DH_lab)
            yield self.request(lab_technician_DH)
            self.release(lab_technician_DH)
            a7 = env.now()
            a8 = a7 - a6
            DHPatientTest.DH_lab_waiting_time.append(a8)
            a9 = sim.Uniform(1, 2).sample()
            yield self.hold(a9)
            DHPatientTest.DH_lab_time.append(a9)
            self.release()
            yield self.hold(sim.Uniform(15, 30, 'minutes').sample())  # patient waits till test report is generated
            a10 = random.randint(0, 100)
            if a10 <= 67:
                yield self.request((doctor_DH_Gen, 1))
                a11 = sim.Uniform(3, 6, 'minutes').sample()
                yield self.hold(a11)  # patient consults with doctor
                self.release(doctor_DH_Gen)
                DHPatientTest.DH_Doctor_initial_doctor_test_time.append(a11)
                DHPatients()
            elif 67 <= a10 < 87:
                RetestingDH()
            else:
                DHPatientTest.DH_to_Home_refer += 1  # referred to home


class RetestingDH(sim.Component):
    retesting_count_DH = 0

    def process(self):
        global warmup_time

        if env.now() <= warmup_time:
            yield self.hold(1440)
            yield self.request((doctor_DH_Gen, 1))
            a12 = sim.Uniform(3, 6, 'minutes').sample()
            yield self.hold(a12)  # patient consults will doctors
            self.release(doctor_DH_Gen)
            DHPatientTest.DH_Doctor_initial_doctor_test_time.append(a12)
            DHPatients()
        else:
            RetestingDH.retesting_count_DH += 1
            yield self.hold(1440)
            yield self.request((doctor_DH_Gen, 1))
            a13 = sim.Uniform(3, 6, 'minutes').sample()
            yield self.hold(a13)  # patient consults will doctors
            self.release(doctor_DH_Gen)
            DHPatientTest.DH_Doctor_initial_doctor_test_time.append(a13)
            DHPatients()


class SevereCase(sim.Component):  # severe patients from PHC and CHCs

    def process(self):
        global warmup_time
        global dh_ven_wait
        global severe_total
        global severe_refer
        global severe_D
        global severe_E
        global severe_F
        global severe_E2F
        global severe_F2E
        global ICU_oxygen_waitingline
        global ICU_oxygen

        if env.now() < warmup_time:
            a46 = random.randint(0, 100)
            if a46 < 50:  # Approximately 50 % of them need ICU bed with oxygen supply
                # patient type F
                self.enter(ICU_oxygen_waitingline)
                yield self.request(ICU_oxygen, fail_delay=30)  # first will check for the availability of ICU bed
                if self.failed():
                    cc_Type_F()
                else:
                    self.leave(ICU_oxygen_waitingline)
                    a47 = sim.Uniform(5 * 1440, 7 * 1440).sample()
                    a48 = a47 / (12 * 60)
                    a49 = round(a48)
                    for a50 in range(0, a49):
                        DoctorDH_Oxygen(at=env.now() + a50 * 12 * 60)
                        NurseDH_Oxygen(at=env.now() + a50 * 12 * 60)
                    yield self.hold(a47)
                    self.release()
                    a51 = random.randint(0, 100)
                    if a51 < 50:  # sent to general ward as condition improves
                        self.enter(Generalward_waitingline)
                        yield self.request(General_bed_DH)
                        self.leave(Generalward_waitingline)
                        a52 = sim.Uniform(2 * 1440, 3 * 1440).sample()
                        a53 = a52 / (12 * 60)
                        a54 = round(a53)
                        for a55 in range(0, a54):
                            DoctorDH_Gen(at=env.now() + a55 * 12 * 60)
                            NurseDH_Gen(at=env.now() + a55 * 12 * 60)
                        yield self.hold(sim.Uniform(2 * 1440, 3 * 1440).sample())
                        self.release()
                    else:  # sent to icu with ventialtor as condition worsens
                        self.enter(ICU_ventilator_waitingline)
                        yield self.request(ICU_ventilator)
                        self.leave(ICU_ventilator_waitingline)
                        a56 = sim.Uniform(5, 10, "days").sample()
                        a57 = a56 / (24 * 60)
                        a58 = round(a57)
                        for a59 in range(0, a58):
                            DoctorDH_Ventilator(at=env.now() + a59 * 24 * 60)
                            NurseDH_Ventilator(at=env.now() + a59 * 24 * 60)
                        yield self.hold(a56)
                        self.release(ICU_ventilator)
                        self.enter(Generalward_waitingline)  # shifted to general ward
                        yield self.request(General_bed_DH)
                        self.leave(Generalward_waitingline)
                        a60 = sim.Uniform(4, 7, "days").sample()
                        a61 = a60 / (24 * 60)
                        a62 = round(a61)
                        for a63 in range(0, a62):
                            DoctorDH_Gen(at=env.now() + a63 * 24 * 60)
                            NurseDH_Gen(at=env.now() + a63 * 24 * 60)
                        yield self.hold(sim.Uniform(4 * 1440, 7 * 1440).sample())
                        self.release()
            elif 50 <= a46 <= 67:  # approximately 17% of the severe patients require ventilators
                self.enter(ICU_ventilator_waitingline)
                yield self.request(ICU_ventilator, fail_delay=120)
                if self.failed():
                    cc_ICU_ward_TypeE()
                else:
                    self.leave(ICU_ventilator_waitingline)
                    a67 = sim.Uniform(5 * 1440, 10 * 1440).sample()
                    a68 = a67 / (24 * 60)
                    a69 = round(a68)
                    for a70 in range(0, a69):
                        DoctorDH_Ventilator(at=env.now() + a70 * 24 * 60)
                        NurseDH_Ventilator(at=env.now() + a70 * 24 * 60)
                    yield self.hold(a67)
                    self.release(ICU_ventilator)
                    a71 = random.randint(0, 100)
                    if a71 < 50:  # shifted to general ward
                        self.enter(Generalward_waitingline)
                        yield self.request(General_bed_DH)
                        self.leave(Generalward_waitingline)
                        a72 = sim.Uniform(4 * 1440, 7 * 1440).sample()
                        a73 = a72 / (12 * 60)
                        a74 = round(a73)
                        for a75 in range(0, a74):
                            DoctorDH_Gen(at=env.now() + a75 * 12 * 60)
                            NurseDH_Gen(at=env.now() + a75 * 12 * 60)
                        yield self.hold(sim.Uniform(4 * 1440, 7 * 1440).sample())
                        self.release()
                    else:
                        self.enter(ICU_oxygen_waitingline)  # shifted to ICU with oxygen ward
                        yield self.request(ICU_oxygen)
                        self.leave(ICU_oxygen_waitingline)
                        a76 = sim.Uniform(5 * 1440, 7 * 1440).sample()
                        a77 = a76 / (12 * 60)
                        a78 = round(a77)
                        for a79 in range(0, a78):
                            DoctorDH_Oxygen(at=env.now() + a79 * 12 * 60)
                            NurseDH_Oxygen(at=env.now() + a79 * 12 * 60)
                        yield self.hold(a76)
                        self.release()
                        self.enter(Generalward_waitingline)  # sent to general ward as condition improves
                        yield self.request(General_bed_DH)
                        self.leave(Generalward_waitingline)
                        a80 = sim.Uniform(2 * 1440, 3 * 1440).sample()
                        a81 = a80 / (12 * 60)
                        a82 = round(a81)
                        for a82 in range(0, a82):
                            DoctorDH_Gen(at=env.now() + a82 * 12 * 60)
                            NurseDH_Gen(at=env.now() + a82 * 12 * 60)
                        yield self.hold(sim.Uniform(2 * 1440, 3 * 1440).sample())
                        self.release()
            else:
                self.enter(ICU_ventilator_waitingline)  # about 33 % of the patients die after 2 to 3 days on
                # ventilator
                yield self.request(ICU_ventilator, fail_delay=120)
                if self.failed():
                    cc_ventilator_TypeF()  # class for severe patients in CC
                else:
                    self.leave(ICU_ventilator_waitingline)
                    a83 = sim.Uniform(2 * 1440, 3 * 1440).sample()
                    a84 = a83 / (12 * 60)
                    a85 = round(a84)
                    for a86 in range(0, a85):
                        DoctorDH_Ventilator(at=env.now() + a86 * 12 * 60)
                        NurseDH_Ventilator(at=env.now() + a86 * 12 * 60)
                    yield self.hold(a83)
                    self.release()
        else:
            DHPatients.severepatients += 1
            a140 = random.randint(0, 100)
            severe_total += 1
            if a140 < 50:  # Type F patients. 64% of total severe cases
                a141 = env.now()
                self.enter(ICU_oxygen_waitingline)
                yield self.request(ICU_oxygen, fail_delay=30)
                if self.failed():
                    severe_refer += 1
                    self.leave(ICU_oxygen_waitingline)
                    DHPatients.severe_icu_to_gen_refer_CCC += 1
                    cc_Type_F()
                else:
                    severe_F += 1
                    self.leave(ICU_oxygen_waitingline)
                    a142 = env.now()
                    a143 = a142 - a141
                    DHPatients.icuoxygenwaitingtime.append(a143)
                    a144 = sim.Uniform(5 * 1440, 7 * 1440).sample()
                    a145 = a144 / (12 * 60)
                    a146 = round(a145)
                    for a147 in range(0, a146):
                        DoctorDH_Oxygen(at=env.now() + a147 * 12 * 60)
                        NurseDH_Oxygen(at=env.now() + a147 * 12 * 60)
                    yield self.hold(a144)
                    self.release()
                    DHPatients.icuoxygentime.append(a144)
                    a148 = random.randint(0, 100)
                    if a148 < 10:  # 50% of type F will become type E
                        severe_F2E += 1
                        DHPatients.R2 += 1
                        a149 = env.now()
                        self.enter(Generalward_waitingline)
                        yield self.request(General_bed_DH)
                        self.leave(Generalward_waitingline)
                        a150 = env.now()
                        a151 = a150 - a149
                        DHPatients.generalbedwaitingtime.append(a151)
                        a152 = sim.Uniform(2 * 1440, 3 * 1440).sample()
                        a153 = a152 / (12 * 60)
                        a154 = round(a153)
                        for a155 in range(0, a154):
                            DoctorDH_Gen(at=env.now() + a155 * 12 * 60)
                            NurseDH_Gen(at=env.now() + a155 * 12 * 60)
                        yield self.hold(a152)
                        self.release()
                        DHPatients.generalbedtime.append(a152)
                    else:  # remaining 50% type F patients
                        DHPatients.R1 += 1
                        a156 = env.now()
                        self.enter(ICU_ventilator_waitingline)
                        yield self.request(ICU_ventilator, fail_delay=30)
                        if self.failed():
                            severe_refer += 1
                            self.leave(ICU_ventilator_waitingline)
                            DHPatients.severe_ventilator_dead_refer_CCC += 1
                            cc_ventilator_TypeF()
                            DHPatients.R1 -= 1
                            severe_F -= 1
                        else:
                            self.leave(ICU_ventilator_waitingline)
                            a157 = env.now()
                            a158 = a157 - a156
                            DHPatients.icuventilatorwaitingtime.append(a158)
                            dh_ven_wait.append(a158)
                            a159 = sim.Uniform(5 * 1440, 10 * 1440).sample()  # changed minutes
                            a160 = a159 / (12 * 60)
                            a161 = round(a160)
                            for a162 in range(0, a161):
                                DoctorDH_Ventilator(at=env.now() + a162 * 12 * 60)
                                NurseDH_Ventilator(at=env.now() + a162 * 12 * 60)
                            yield self.hold(a159)
                            self.release(ICU_ventilator)
                            DHPatients.icuventilatortime.append(a159)
                        a163 = env.now()
                        self.enter(Generalward_waitingline)
                        yield self.request(General_bed_DH)
                        self.leave(Generalward_waitingline)
                        a164 = env.now()
                        a165 = a164 - a163
                        DHPatients.generalbedwaitingtime.append(a165)
                        a166 = sim.Uniform(4 * 1440, 7 * 1440).sample()  # changed minutes
                        a167 = a166 / (12 * 60)
                        a168 = round(a167)
                        for a169 in range(0, a168):
                            DoctorDH_Gen(at=env.now() + a169 * 12 * 60)
                            NurseDH_Gen(at=env.now() + a169 * 12 * 60)
                        yield self.hold(a166)
                        self.release()
                        DHPatients.generalbedtime.append(a166)
            elif 50 <= a140 < 74:  # Type E patients. Total 30%.
                a170 = env.now()
                self.enter(ICU_ventilator_waitingline)
                yield self.request(ICU_ventilator, fail_delay=30)
                if self.failed():
                    severe_refer += 1
                    self.leave(ICU_ventilator_waitingline)
                    DHPatients.severe_ventilator_to_gen_refer_CCC += 1
                    cc_ICU_ward_TypeE()
                else:
                    severe_E += 1
                    self.leave(ICU_ventilator_waitingline)
                    a172 = env.now()
                    a173 = a172 - a170
                    DHPatients.icuventilatorwaitingtime.append(a173)
                    dh_ven_wait.append(a173)
                    a174 = sim.Uniform(5 * 1440, 10 * 1440).sample()
                    a175 = a174 / (12 * 60)
                    a176 = round(a175)
                    for a177 in range(0, a176):
                        DoctorDH_Ventilator(at=env.now() + a177 * 12 * 60)
                        NurseDH_Ventilator(at=env.now() + a177 * 12 * 60)
                    yield self.hold(a174)
                    self.release(ICU_ventilator)
                    DHPatients.icuventilatortime.append(a174)
                    a178 = random.randint(0, 100)
                    if a178 < 50:  # 50% type E will become type F
                        severe_E2F += 1
                        DHPatients.R4 += 1
                        a179 = env.now()
                        self.enter(Generalward_waitingline)
                        yield self.request(General_bed_DH)
                        self.leave(Generalward_waitingline)
                        a180 = env.now()
                        a181 = a180 - a179
                        DHPatients.generalbedwaitingtime.append(a181)
                        a182 = sim.Uniform(4 * 1440, 7 * 1440).sample()
                        a183 = a182 / (12 * 60)
                        a184 = round(a183)
                        for r53 in range(0, a184):
                            DoctorDH_Gen(at=env.now() + r53 * 12 * 60)
                            NurseDH_Gen(at=env.now() + r53 * 12 * 60)
                        yield self.hold(a182)
                        self.release()
                        DHPatients.generalbedtime.append(a182)
                    else:  # remaining type e patients
                        DHPatients.R3 += 1
                        a185 = env.now()
                        self.enter(ICU_oxygen_waitingline)
                        yield self.request(ICU_oxygen)
                        self.leave(ICU_oxygen_waitingline)
                        a186 = env.now()
                        a187 = a186 - a185
                        DHPatients.icuoxygenwaitingtime.append(a187)
                        a188 = sim.Uniform(5 * 1440, 7 * 1440).sample()
                        a189 = a188 / (12 * 60)
                        a190 = round(a189)
                        for a191 in range(0, a190):
                            DoctorDH_Oxygen(at=env.now() + a191 * 12 * 60)
                            NurseDH_Oxygen(at=env.now() + a191 * 12 * 60)
                        yield self.hold(a188)
                        self.release()
                        DHPatients.icuoxygentime.append(a188)
                        a192 = env.now()
                        self.enter(Generalward_waitingline)
                        yield self.request(General_bed_DH)
                        self.leave(Generalward_waitingline)
                        a193 = env.now()
                        a194 = a193 - a192
                        DHPatients.generalbedwaitingtime.append(a194)
                        a195 = sim.Uniform(2 * 1440, 3 * 1440).sample()
                        a196 = a195 / (12 * 60)
                        a197 = round(a196)
                        for a198 in range(0, a197):
                            DoctorDH_Gen(at=env.now() + a198 * 12 * 60)
                            NurseDH_Gen(at=env.now() + a198 * 12 * 60)
                        yield self.hold(a195)
                        self.release()
                        DHPatients.generalbedtime.append(a195)
            else:  # 25% type D patients
                a199 = env.now()
                self.enter(ICU_ventilator_waitingline)
                yield self.request(ICU_ventilator, fail_delay=30)
                if self.failed():
                    severe_refer += 1
                    self.leave(ICU_ventilator_waitingline)
                    DHPatients.severe_ventilator_dead_refer_CCC += 1
                    cc_ventilator_TypeD()
                else:
                    self.leave(ICU_ventilator_waitingline)
                    DHPatients.severe_ventilator_dead += 1
                    severe_D += 1
                    a200 = env.now()
                    a201 = a200 - a199
                    DHPatients.icuventilatorwaitingtime.append(a201)
                    dh_ven_wait.append(a201)
                    a202 = sim.Uniform(2 * 1440, 3 * 1440).sample()
                    a203 = a202 / (12 * 60)
                    a204 = round(a203)
                    for a205 in range(0, a204):
                        DoctorDH_Ventilator(at=env.now() + a205 * 12 * 60)
                        NurseDH_Ventilator(at=env.now() + a205 * 12 * 60)
                    yield self.hold(a202)
                    self.release()
                    DHPatients.icuventilatortime.append(a202)


class DH_SevereTypeE(sim.Component):

    def process(self):
        global warmup_time
        global dh_ven_wait
        global severe_total
        global severe_refer
        global severe_D
        global severe_E
        global severe_F
        global severe_E2F
        global severe_F2E
        global ICU_oxygen_waitingline
        global ICU_oxygen
        global dh_2_cc_e
        global dh_total_e

        if env.now() < warmup_time:
            pass

        else:
            a170 = env.now()
            self.enter(ICU_ventilator_waitingline)
            yield self.request(ICU_ventilator, fail_delay=30)
            dh_total_e += 1
            if self.failed():
                dh_2_cc_e += 1
                severe_refer += 1
                self.leave(ICU_ventilator_waitingline)
                DHPatients.severe_ventilator_to_gen_refer_CCC += 1
                cc_ICU_ward_TypeE()
            else:
                severe_E += 1
                self.leave(ICU_ventilator_waitingline)
                a172 = env.now()
                a173 = a172 - a170
                DHPatients.icuventilatorwaitingtime.append(a173)
                dh_ven_wait.append(a173)
                a174 = sim.Uniform(5 * 1440, 10 * 1440).sample()
                a175 = a174 / (12 * 60)
                a176 = round(a175)
                for a177 in range(0, a176):
                    DoctorDH_Ventilator(at=env.now() + a177 * 12 * 60)
                    NurseDH_Ventilator(at=env.now() + a177 * 12 * 60)
                yield self.hold(a174)
                self.release(ICU_ventilator)
                DHPatients.icuventilatortime.append(a174)
                a178 = random.randint(0, 100)
                if a178 < 50:  # 50% type E will become type F
                    severe_E2F += 1
                    DHPatients.R4 += 1
                    a179 = env.now()
                    self.enter(Generalward_waitingline)
                    yield self.request(General_bed_DH)
                    self.leave(Generalward_waitingline)
                    a180 = env.now()
                    a181 = a180 - a179
                    DHPatients.generalbedwaitingtime.append(a181)
                    a182 = sim.Uniform(4 * 1440, 7 * 1440).sample()
                    a183 = a182 / (12 * 60)
                    a184 = round(a183)
                    for r53 in range(0, a184):
                        DoctorDH_Gen(at=env.now() + r53 * 12 * 60)
                        NurseDH_Gen(at=env.now() + r53 * 12 * 60)
                    yield self.hold(a182)
                    self.release()
                    DHPatients.generalbedtime.append(a182)
                else:  # remaining type e patients
                    DHPatients.R3 += 1
                    a185 = env.now()
                    self.enter(ICU_oxygen_waitingline)
                    yield self.request(ICU_oxygen)
                    self.leave(ICU_oxygen_waitingline)
                    a186 = env.now()
                    a187 = a186 - a185
                    DHPatients.icuoxygenwaitingtime.append(a187)
                    a188 = sim.Uniform(5 * 1440, 7 * 1440).sample()
                    a189 = a188 / (12 * 60)
                    a190 = round(a189)
                    for a191 in range(0, a190):
                        DoctorDH_Oxygen(at=env.now() + a191 * 12 * 60)
                        NurseDH_Oxygen(at=env.now() + a191 * 12 * 60)
                    yield self.hold(a188)
                    self.release()
                    DHPatients.icuoxygentime.append(a188)
                    a192 = env.now()
                    self.enter(Generalward_waitingline)
                    yield self.request(General_bed_DH)
                    self.leave(Generalward_waitingline)
                    a193 = env.now()
                    a194 = a193 - a192
                    DHPatients.generalbedwaitingtime.append(a194)
                    a195 = sim.Uniform(2 * 1440, 3 * 1440).sample()
                    a196 = a195 / (12 * 60)
                    a197 = round(a196)
                    for a198 in range(0, a197):
                        DoctorDH_Gen(at=env.now() + a198 * 12 * 60)
                        NurseDH_Gen(at=env.now() + a198 * 12 * 60)
                    yield self.hold(a195)
                    self.release()
                    DHPatients.generalbedtime.append(a195)


class DH_SevereTypeF(sim.Component):

    def process(self):

        global warmup_time
        global dh_ven_wait
        global severe_total
        global severe_refer
        global severe_D
        global severe_E
        global severe_F
        global severe_E2F
        global severe_F2E
        global ICU_oxygen_waitingline
        global ICU_oxygen
        global dh_2_cc_f
        global dh_total_f

        if env.now() < warmup_time:
            pass
        else:
            DHPatients.severepatients += 1
            a140 = random.randint(0, 100)
            severe_total += 1
            a141 = env.now()
            self.enter(ICU_oxygen_waitingline)
            yield self.request(ICU_oxygen, fail_delay=30)
            dh_total_f += 1
            if self.failed():
                dh_2_cc_f += 1
                severe_refer += 1
                self.leave(ICU_oxygen_waitingline)
                DHPatients.severe_icu_to_gen_refer_CCC += 1
                cc_Type_F()
            else:
                severe_F += 1
                self.leave(ICU_oxygen_waitingline)
                a142 = env.now()
                a143 = a142 - a141
                DHPatients.icuoxygenwaitingtime.append(a143)
                a144 = sim.Uniform(5 * 1440, 7 * 1440).sample()
                a145 = a144 / (12 * 60)
                a146 = round(a145)
                for a147 in range(0, a146):
                    DoctorDH_Oxygen(at=env.now() + a147 * 12 * 60)
                    NurseDH_Oxygen(at=env.now() + a147 * 12 * 60)
                yield self.hold(a144)
                self.release()
                DHPatients.icuoxygentime.append(a144)
                a148 = random.randint(0, 100)
                if a148 < 10:  # 10% of type F will become type E
                    severe_F2E += 1
                    DHPatients.R2 += 1
                    a149 = env.now()
                    self.enter(Generalward_waitingline)
                    yield self.request(General_bed_DH)
                    self.leave(Generalward_waitingline)
                    a150 = env.now()
                    a151 = a150 - a149
                    DHPatients.generalbedwaitingtime.append(a151)
                    a152 = sim.Uniform(2 * 1440, 3 * 1440).sample()
                    a153 = a152 / (12 * 60)
                    a154 = round(a153)
                    for a155 in range(0, a154):
                        DoctorDH_Gen(at=env.now() + a155 * 12 * 60)
                        NurseDH_Gen(at=env.now() + a155 * 12 * 60)
                    yield self.hold(a152)
                    self.release()
                    DHPatients.generalbedtime.append(a152)
                else:  # remaining 90% type F patients
                    DHPatients.R1 += 1
                    a156 = env.now()
                    self.enter(ICU_ventilator_waitingline)
                    yield self.request(ICU_ventilator, fail_delay=30)
                    if self.failed():
                        severe_refer += 1
                        self.leave(ICU_ventilator_waitingline)
                        DHPatients.severe_ventilator_dead_refer_CCC += 1
                        cc_ventilator_TypeF()
                        DHPatients.R1 -= 1
                        severe_F -= 1
                    else:
                        self.leave(ICU_ventilator_waitingline)
                        a157 = env.now()
                        a158 = a157 - a156
                        DHPatients.icuventilatorwaitingtime.append(a158)
                        dh_ven_wait.append(a158)
                        a159 = sim.Uniform(5 * 1440, 10 * 1440).sample()  # changed minutes
                        a160 = a159 / (24 * 60)
                        a161 = round(a160)
                        for a162 in range(0, a161):
                            DoctorDH_Ventilator(at=env.now() + a162 * 12 * 60)
                            NurseDH_Ventilator(at=env.now() + a162 * 12 * 60)
                        yield self.hold(a159)
                        self.release(ICU_ventilator)
                        DHPatients.icuventilatortime.append(a159)
                    a163 = env.now()
                    self.enter(Generalward_waitingline)
                    yield self.request(General_bed_DH)
                    self.leave(Generalward_waitingline)
                    a164 = env.now()
                    a165 = a164 - a163
                    DHPatients.generalbedwaitingtime.append(a165)
                    a166 = sim.Uniform(4 * 1440, 7 * 1440).sample()  # changed minutes
                    a167 = a166 / (12 * 60)
                    a168 = round(a167)
                    for a169 in range(0, a168):
                        DoctorDH_Gen(at=env.now() + a169 * 12 * 60)
                        NurseDH_Gen(at=env.now() + a169 * 12 * 60)
                    yield self.hold(a166)
                    self.release()
                    DHPatients.generalbedtime.append(a166)


class DH_SevereTypeD(sim.Component):

    def process(self):
        global warmup_time
        global severe_refer
        global dh_ven_wait
        global DoctorDH_Ventilator
        global NurseDH_Ventilator
        global severe_D
        global ICU_ventilator_waitingline
        global dh_2_cc_d
        global dh_total_d

        if env.now() <= warmup_time:
            t = sim.Uniform(2 * 1440, 3 * 1440).sample()
            yield self.request(ICU_ventilator)
            yield self.hold(t)
            t1 = t / (12 * 60)
            t11 = round(t1)
            for t111 in range(0, t11):
                DoctorDH_Ventilator(at=env.now() + t111 * 12 * 60)
                NurseDH_Ventilator(at=env.now() + t111 * 12 * 60)
            self.release(ICU_ventilator)
        else:
            a199 = env.now()
            self.enter(ICU_ventilator_waitingline)
            yield self.request(ICU_ventilator, fail_delay=30)
            dh_total_d += 1
            if self.failed():
                severe_refer += 1
                dh_2_cc_d += 1
                self.leave(ICU_ventilator_waitingline)
                DHPatients.severe_ventilator_dead_refer_CCC += 1
                cc_ventilator_TypeD()
            else:
                self.leave(ICU_ventilator_waitingline)
                DHPatients.severe_ventilator_dead += 1
                severe_D += 1
                a200 = env.now()
                a201 = a200 - a199
                DHPatients.icuventilatorwaitingtime.append(a201)
                dh_ven_wait.append(a201)
                a202 = sim.Uniform(2 * 1440, 3 * 1440).sample()
                a203 = a202 / (12 * 60)
                a204 = round(a203)
                for a205 in range(0, a204):
                    DoctorDH_Ventilator(at=env.now() + a205 * 12 * 60)
                    NurseDH_Ventilator(at=env.now() + a205 * 12 * 60)
                yield self.hold(a202)
                self.release()
                DHPatients.icuventilatortime.append(a202)


class ModerateTypeA(sim.Component):

    def process(self):
        global warmup_time
        global moderate_A
        global moderate_total
        global moderate_refer
        global dh_total_a
        global dh_2_cc_a

        if env.now() < warmup_time:
            self.enter(Generalward_waitingline)
            yield self.request(General_bed_DH, fail_delay=300)
            if self.failed():
                self.leave(Generalward_waitingline)
                cc_general_ward_TypeA()
            else:
                DHPatients.moderatepatients += 1
                self.leave(Generalward_waitingline)
                a97 = env.now()
                a100 = sim.Uniform(4 * 1440, 5 * 1440).sample()
                a101 = a100 / (12 * 60)
                a102 = round(a101)
                for a103 in range(0, a102):
                    DoctorDH_Gen(at=env.now() + a103 * 12 * 60)
                    NurseDH_Gen(at=env.now() + a103 * 12 * 60)
                yield self.hold(a100)
                self.release()
                DHPatients.generalbedtime.append(a100)
        else:
            self.enter(Generalward_waitingline)
            a96 = env.now()
            yield self.request(General_bed_DH, fail_delay=300)
            dh_total_a += 1
            if self.failed():
                dh_2_cc_a += 1
                moderate_refer += 1
                self.leave(Generalward_waitingline)
                DHPatients.moderate_gen_refer_CCC += 1
                cc_general_ward_TypeA()
            else:
                moderate_total += 1
                moderate_A += 1  # count of type A moderate patients
                DHPatients.moderatepatients += 1
                self.leave(Generalward_waitingline)
                a97 = env.now()
                a98 = a97 - a96
                DHPatients.generalbedwaitingtime.append(a98)
                a99 = random.randint(0, 100)
                DHPatients.moderate_gen_to_exit += 1
                a100 = sim.Uniform(4 * 1440, 5 * 1440).sample()
                a101 = a100 / (12 * 60)
                a102 = round(a101)
                for a103 in range(0, a102):
                    DoctorDH_Gen(at=env.now() + a103 * 12 * 60)
                    NurseDH_Gen(at=env.now() + a103 * 12 * 60)
                yield self.hold(a100)
                self.release()
                DHPatients.generalbedtime.append(a100)


class ModerateTypeB(sim.Component):

    def process(self):

        global warmup_time
        global moderate_total
        global moderate_B
        global moderate_refer
        global dh_2_cc_b
        global dh_total_b
        global dh_2_cc_b_ox

        if env.now() < warmup_time:
            self.enter(Generalward_waitingline)
            yield self.request(General_bed_DH, fail_delay=180)
            if self.failed():
                self.leave(Generalward_waitingline)
                cc_general_ward_TypeB()
            else:
                self.leave(Generalward_waitingline)

                a104 = sim.Uniform(3 * 1440, 4 * 1440).sample()  # stay 4,5 days
                a105 = a104 / (12 * 60)
                a106 = round(a105)
                for a107 in range(0, a106):
                    DoctorDH_Gen(at=env.now() + a107 * 12 * 60)
                    NurseDH_Gen(at=env.now() + a107 * 12 * 60)
                yield self.hold(a104)
                self.release(General_bed_DH)
                a108 = env.now()
                self.enter(ICU_oxygen_waitingline)
                yield self.request(ICU_oxygen)
                self.leave(ICU_oxygen_waitingline)
                a109 = env.now()
                a110 = a109 - a108
                a111 = sim.Uniform(5 * 1440, 7 * 1440).sample()
                a112 = a111 / (12 * 60)
                a113 = round(a112)
                for a114 in range(0, a113):
                    DoctorDH_Oxygen(at=env.now() + a114 * 12 * 60)
                    NurseDH_Oxygen(at=env.now() + a114 * 12 * 60)
                yield self.hold(a111)
                self.release(ICU_oxygen)
                DHPatients.icuoxygentime.append(a111)
                a115 = env.now()
                self.enter(Generalward_waitingline)
                yield self.request(General_bed_DH)
                self.leave(Generalward_waitingline)
                a116 = env.now()
                a117 = a116 - a115
                a118 = sim.Uniform(2 * 1440, 3 * 1440).sample()
                a119 = a118 / (12 * 60)
                a120 = round(a119)
                for a121 in range(0, a120):
                    DoctorDH_Gen(at=env.now() + a121 * 12 * 60)
                    NurseDH_Gen(at=env.now() + a121 * 12 * 60)
                yield self.hold(a118)
                self.release(General_bed_DH)
        else:
            self.enter(Generalward_waitingline)
            yield self.request(General_bed_DH, fail_delay=180)
            dh_total_b += 1
            if self.failed():
                moderate_refer += 1
                dh_2_cc_b += 1
                self.leave(Generalward_waitingline)
                DHPatients.moderate_gen_refer_CCC += 1
                cc_general_ward_TypeB()
            else:
                moderate_total += 1
                moderate_B += 1
                self.leave(Generalward_waitingline)
                DHPatients.moderate_gen_to_icu_to_gen_exit += 1
                a104 = sim.Uniform(3 * 1440, 4 * 1440).sample()  # stay 4,5 days
                a105 = a104 / (12 * 60)
                a106 = round(a105)
                for a107 in range(0, a106):
                    DoctorDH_Gen(at=env.now() + a107 * 12 * 60)
                    NurseDH_Gen(at=env.now() + a107 * 12 * 60)
                yield self.hold(a104)
                self.release(General_bed_DH)
                DHPatients.generalbedtime.append(a104)
                a108 = env.now()
                self.enter(ICU_oxygen_waitingline)
                yield self.request(ICU_oxygen, fail_delay=30)
                if self.failed():
                    self.leave(ICU_oxygen_waitingline)
                    G2O_ward()
                    dh_2_cc_b_ox += 1
                else:
                    self.leave(ICU_oxygen_waitingline)
                    a109 = env.now()
                    a110 = a109 - a108
                    DHPatients.icuoxygenwaitingtime.append(a110)
                    a111 = sim.Uniform(5 * 1440, 7 * 1440).sample()
                    a112 = a111 / (12 * 60)
                    a113 = round(a112)
                    for a114 in range(0, a113):
                        DoctorDH_Oxygen(at=env.now() + a114 * 12 * 60)
                        NurseDH_Oxygen(at=env.now() + a114 * 12 * 60)
                    yield self.hold(a111)
                    self.release(ICU_oxygen)
                    DHPatients.icuoxygentime.append(a111)
                    a115 = env.now()
                    self.enter(Generalward_waitingline)
                    yield self.request(General_bed_DH)
                    self.leave(Generalward_waitingline)
                    a116 = env.now()
                    a117 = a116 - a115
                    DHPatients.generalbedwaitingtime.append(a117)
                    a118 = sim.Uniform(2 * 1440, 3 * 1440).sample()
                    a119 = a118 / (12 * 60)
                    a120 = round(a119)
                    for a121 in range(0, a120):
                        DoctorDH_Gen(at=env.now() + a121 * 12 * 60)
                        NurseDH_Gen(at=env.now() + a121 * 12 * 60)
                    yield self.hold(a118)
                    self.release(General_bed_DH)
                    DHPatients.generalbedtime.append(a118)


class ModerateTypeC(sim.Component):

    def process(self):
        global warmup_time
        global moderate_total
        global moderate_C
        global moderate_refer
        global dh_2_cc_c
        global dh_total_c
        global dh_2_cc_c_ven

        if env.now() <= warmup_time:
            self.enter(Generalward_waitingline)
            yield self.request(General_bed_DH, fail_delay=180)
            if self.failed():
                self.leave(Generalward_waitingline)
                cc_general_ward_TypeC()
            else:
                self.leave(Generalward_waitingline)
                a122 = sim.Uniform(3 * 1440, 4 * 1440).sample()
                a123 = a122 / (12 * 60)
                a124 = round(a123)
                for a125 in range(0, a124):
                    DoctorDH_Gen(at=env.now() + a125 * 12 * 60)
                    NurseDH_Gen(at=env.now() + a125 * 12 * 60)
                yield self.hold(a122)
                self.release(General_bed_DH)
                a126 = env.now()
                self.enter(ICU_ventilator_waitingline)
                yield self.request(ICU_ventilator)
                self.leave(ICU_ventilator_waitingline)
                a127 = env.now()
                a128 = a127 - a126
                a129 = sim.Uniform(5 * 1440, 10 * 1440).sample()  # changed minutes
                a130 = a129 / (12 * 60)
                a131 = round(a130)
                for a132 in range(0, a131):
                    DoctorDH_Ventilator(at=env.now() + a132 * 12 * 60)
                    NurseDH_Ventilator(at=env.now() + a132 * 12 * 60)
                yield self.hold(a129)
                self.release(ICU_ventilator)
                a133 = env.now()
                self.enter(Generalward_waitingline)
                yield self.request(General_bed_DH)
                self.leave(Generalward_waitingline)
                a134 = env.now()
                a135 = a134 - a133
                a136 = sim.Uniform(4 * 1440, 7 * 1440).sample()  # changed to minutes
                a137 = a136 / (12 * 60)
                a138 = round(a137)
                for a139 in range(0, a138):
                    DoctorDH_Gen(at=env.now() + a139 * 12 * 60)
                    NurseDH_Gen(at=env.now() + a139 * 12 * 60)
                yield self.hold(a136)
                self.release(General_bed_DH)
        else:
            self.enter(Generalward_waitingline)
            yield self.request(General_bed_DH, fail_delay=180)
            dh_total_c += 1
            if self.failed():
                dh_2_cc_c += 1
                moderate_refer += 1
                self.leave(Generalward_waitingline)
                DHPatients.moderate_gen_refer_CCC += 1
                cc_general_ward_TypeC()
            else:
                moderate_total += 1
                self.leave(Generalward_waitingline)
                DHPatients.moderate_gen_to_ventilator_to_gen_exit += 1
                moderate_C += 1
                a122 = sim.Uniform(3 * 1440, 4 * 1440).sample()
                a123 = a122 / (12 * 60)
                a124 = round(a123)
                for a125 in range(0, a124):
                    DoctorDH_Gen(at=env.now() + a125 * 12 * 60)
                    NurseDH_Gen(at=env.now() + a125 * 12 * 60)
                yield self.hold(a122)
                self.release(General_bed_DH)
                DHPatients.generalbedtime.append(a122)
                a126 = env.now()
                self.enter(ICU_ventilator_waitingline)
                yield self.request(ICU_ventilator, fail_delay = 30)
                if self.failed():
                    self.leave(ICU_ventilator_waitingline)
                    G2V_ward()
                    dh_2_cc_c_ven += 1
                else:
                    self.leave(ICU_ventilator_waitingline)
                    a127 = env.now()
                    a128 = a127 - a126
                    DHPatients.icuventilatorwaitingtime.append(a128)
                    dh_ven_wait.append(a128)
                    a129 = sim.Uniform(5 * 1440, 10 * 1440).sample()  # changed minutes
                    a130 = a129 / (12 * 60)
                    a131 = round(a130)
                    for a132 in range(0, a131):
                        DoctorDH_Ventilator(at=env.now() + a132 * 12 * 60)
                        NurseDH_Ventilator(at=env.now() + a132 * 12 * 60)
                    yield self.hold(a129)
                    self.release(ICU_ventilator)
                    DHPatients.icuventilatortime.append(a129)
                    a133 = env.now()
                    self.enter(Generalward_waitingline)
                    yield self.request(General_bed_DH)
                    self.leave(Generalward_waitingline)
                    a134 = env.now()
                    a135 = a134 - a133
                    DHPatients.generalbedwaitingtime.append(a135)
                    a136 = sim.Uniform(4 * 1440, 7 * 1440).sample()  # changed to minutes
                    a137 = a136 / (12 * 60)
                    a138 = round(a137)
                    for a139 in range(0, a138):
                        DoctorDH_Gen(at=env.now() + a139 * 12 * 60)
                        NurseDH_Gen(at=env.now() + a139 * 12 * 60)
                    yield self.hold(a136)
                    self.release(General_bed_DH)
                    DHPatients.generalbedtime.append(a136)


class Moderate_case(sim.Component):

    def process(self):
        global warmup_time
        global dh_ven_wait
        global m_dh_count
        global moderate_total
        global moderate_A
        global moderate_B
        global moderate_C
        global moderate_refer
        global General_bed_DH
        global dh_total_a
        global dh_total_b
        global dh_total_c
        global dh_2_cc_a
        global dh_2_cc_b
        global dh_2_cc_c
        global dh_2_cc_c_ven
        global dh_2_cc_b_ox

        if env.now() < warmup_time:
            self.enter(Generalward_waitingline)  # First patient will check for availability of bed
            yield self.request(General_bed_DH, fail_delay=300)  # if bed is not available within 6 hours,
            # patient will be referred to Covid Care Centres
            if self.failed():
                cc_general_ward_TypeA()  # referred to CC general ward
            else:
                self.leave(Generalward_waitingline)
                a17 = random.randint(0, 100)
                if a17 < 90:  # 90% of them will be treated in General ward
                    a18 = sim.Uniform(4 * 1440, 5 * 1440).sample()  # patient will occupy bed for 4 to 5 days
                    a19 = a18 / (12 * 60)
                    a20 = round(a19)
                    for a21 in range(0, a20):  # the doctor and nurse will be called twice each day
                        # for monitoring the condition of patient
                        DoctorDH_Gen(at=env.now() + a21 * 12 * 60)
                        NurseDH_Gen(at=env.now() + a21 * 12 * 60)
                    yield self.hold(sim.Uniform(4 * 1440, 5 * 1440).sample())
                    self.release()  # patients leave general ward and exit
                elif 90 <= a17 <= 96:  # approximately 6% of the patients are referred from general ward
                    # to ICU ward with oxygen as their condition deteriorates
                    a22 = sim.Uniform(3 * 1440, 4 * 1440).sample()  # patient will stay in General ward for 3 to 4 days
                    a23 = a22 / (12 * 60)
                    a24 = round(a23)
                    for a25 in range(0, a24):  # doctor and nurse will be called twice every day
                        DoctorDH_Gen(at=env.now() + a25 * 12 * 60)
                        NurseDH_Gen(at=env.now() + a25 * 12 * 60)
                    yield self.hold(sim.Uniform(3 * 1440, 4 * 1440).sample())
                    self.release()  # patient leaves general ward and requests ICU bed with oxygen
                    self.enter(ICU_oxygen_waitingline)
                    yield self.request(ICU_oxygen)
                    self.leave(ICU_oxygen_waitingline)
                    a26 = sim.Uniform(5 * 1440, 7 * 1440).sample()
                    a27 = a26 / (12 * 60)
                    a28 = round(a27)
                    for a29 in range(0, a28):
                        DoctorDH_Oxygen(at=env.now() + a29 * 12 * 60)
                        NurseDH_Oxygen(at=env.now() + a29 * 12 * 60)
                    yield self.hold(a26)
                    self.release()
                    self.enter(Generalward_waitingline)  # as the condition improves,
                    # patient is again sent back to general ward for 2 to 3 days
                    yield self.request(General_bed_DH)
                    self.leave(Generalward_waitingline)
                    a30 = sim.Uniform(2 * 1440, 3 * 1440).sample()
                    a31 = a30 / (12 * 60)
                    a32 = round(a31)
                    for a33 in range(0, a32):
                        DoctorDH_Gen(at=env.now() + a33 * 12 * 60)
                        NurseDH_Gen(at=env.now() + a33 * 12 * 60)
                    yield self.hold(sim.Uniform(2 * 1440, 3 * 1440).sample())
                    self.release()
                else:  # 4 % of the patients will be referred to ICU ward with ventilator from the general
                    # ward and as their condition becomes normal are again sent to general ward
                    a34 = sim.Uniform(3 * 1440, 4 * 1440).sample()  # stay for 3 to 4 days
                    a35 = a34 / (12 * 60)
                    a36 = round(a35)
                    for a37 in range(0, a36):
                        DoctorDH_Gen(at=env.now() + a37 * 12 * 60)
                        NurseDH_Gen(at=env.now() + a37 * 12 * 60)
                    yield self.hold(sim.Uniform(3 * 1440, 4 * 1440).sample())
                    self.release()
                    self.enter(ICU_ventilator_waitingline)  # request for ventilator as condition worsens
                    yield self.request(ICU_ventilator)
                    self.leave(ICU_ventilator_waitingline)
                    a38 = sim.Uniform(5 * 1440, 10 * 1440).sample()
                    a39 = a38 / (12 * 60)
                    a40 = round(a39)
                    for a41 in range(0, a40):
                        DoctorDH_Ventilator(at=env.now() + a41 * 12 * 60)
                        NurseDH_Ventilator(at=env.now() + a41 * 12 * 60)
                    yield self.hold(a38)
                    self.release(ICU_ventilator)
                    self.enter(Generalward_waitingline)  # again are shifted back to general ward (condition
                    # normal)
                    yield self.request(General_bed_DH)
                    self.leave(Generalward_waitingline)
                    a42 = sim.Uniform(4 * 1440, 7 * 1440).sample()
                    a43 = a42 / (12 * 60)
                    a44 = round(a43)
                    for a45 in range(0, a44):
                        DoctorDH_Gen(at=env.now() + a45 * 12 * 60)
                        NurseDH_Gen(at=env.now() + a45 * 12 * 60)
                    yield self.hold(sim.Uniform(4 * 1440, 7 * 1440).sample())
                    self.release()
        else:
            a95 = random.randint(0, 100)
            moderate_total += 1
            if a95 < 90:  # 90% of them will be treated in General ward. Type A patients
                a96 = env.now()
                self.enter(Generalward_waitingline)
                yield self.request(General_bed_DH, fail_delay=300)
                dh_total_a += 1
                if self.failed():
                    dh_2_cc_a += 1
                    moderate_refer += 1
                    self.leave(Generalward_waitingline)
                    DHPatients.moderate_gen_refer_CCC += 1
                    cc_general_ward_TypeA()
                else:
                    moderate_A += 1  # count of type A moderate patients
                    DHPatients.moderatepatients += 1
                    self.leave(Generalward_waitingline)
                    a97 = env.now()
                    a98 = a97 - a96
                    DHPatients.generalbedwaitingtime.append(a98)
                    a99 = random.randint(0, 100)
                    DHPatients.moderate_gen_to_exit += 1
                    a100 = sim.Uniform(4 * 1440, 5 * 1440).sample()
                    a101 = a100 / (12 * 60)
                    a102 = round(a101)
                    for a103 in range(0, a102):
                        DoctorDH_Gen(at=env.now() + a103 * 12 * 60)
                        NurseDH_Gen(at=env.now() + a103 * 12 * 60)
                    yield self.hold(a100)
                    self.release()
                    DHPatients.generalbedtime.append(a100)

            elif 90 <= a95 < 98:  # type B patients. 8% of the total moderate patients
                self.enter(Generalward_waitingline)
                yield self.request(General_bed_DH, fail_delay=180)
                dh_total_b += 1
                if self.failed():
                    dh_2_cc_b += 1
                    moderate_refer += 1
                    self.leave(Generalward_waitingline)
                    DHPatients.moderate_gen_refer_CCC += 1
                    cc_general_ward_TypeB()
                else:
                    moderate_B += 1
                    self.leave(Generalward_waitingline)
                    DHPatients.moderate_gen_to_icu_to_gen_exit += 1
                    a104 = sim.Uniform(3 * 1440, 4 * 1440).sample()  # stay 4,5 days
                    a105 = a104 / (12 * 60)
                    a106 = round(a105)
                    for a107 in range(0, a106):
                        DoctorDH_Gen(at=env.now() + a107 * 12 * 60)
                        NurseDH_Gen(at=env.now() + a107 * 12 * 60)
                    yield self.hold(a104)
                    self.release(General_bed_DH)
                    DHPatients.generalbedtime.append(a104)
                    a108 = env.now()
                    self.enter(ICU_oxygen_waitingline)
                    yield self.request(ICU_oxygen, fail_delay = 30)
                    if self.failed():
                        self.leave(ICU_oxygen_waitingline)
                        G2O_ward()
                        dh_2_cc_b_ox += 1
                    else:

                        self.leave(ICU_oxygen_waitingline)
                        a109 = env.now()
                        a110 = a109 - a108
                        DHPatients.icuoxygenwaitingtime.append(a110)
                        a111 = sim.Uniform(5 * 1440, 7 * 1440).sample()
                        a112 = a111 / (12 * 60)
                        a113 = round(a112)
                        for a114 in range(0, a113):
                            DoctorDH_Oxygen(at=env.now() + a114 * 12 * 60)
                            NurseDH_Oxygen(at=env.now() + a114 * 12 * 60)
                        yield self.hold(a111)
                        self.release(ICU_oxygen)
                        DHPatients.icuoxygentime.append(a111)
                        a115 = env.now()
                        self.enter(Generalward_waitingline)
                        yield self.request(General_bed_DH)
                        self.leave(Generalward_waitingline)
                        a116 = env.now()
                        a117 = a116 - a115
                        DHPatients.generalbedwaitingtime.append(a117)
                        a118 = sim.Uniform(2 * 1440, 3 * 1440).sample()
                        a119 = a118 / (12 * 60)
                        a120 = round(a119)
                        for a121 in range(0, a120):
                            DoctorDH_Gen(at=env.now() + a121 * 12 * 60)
                            NurseDH_Gen(at=env.now() + a121 * 12 * 60)
                        yield self.hold(a118)
                        self.release(General_bed_DH)
                        DHPatients.generalbedtime.append(a118)
            else:  # Type C moderate patients. 2% of the total moderate patients
                self.enter(Generalward_waitingline)
                yield self.request(General_bed_DH, fail_delay=180)
                dh_total_c += 1
                if self.failed():
                    dh_2_cc_c += 1
                    moderate_refer += 1
                    self.leave(Generalward_waitingline)
                    DHPatients.moderate_gen_refer_CCC += 1
                    cc_general_ward_TypeC()
                else:
                    self.leave(Generalward_waitingline)
                    DHPatients.moderate_gen_to_ventilator_to_gen_exit += 1
                    moderate_C += 1
                    a122 = sim.Uniform(3 * 1440, 4 * 1440).sample()
                    a123 = a122 / (12 * 60)
                    a124 = round(a123)
                    for a125 in range(0, a124):
                        DoctorDH_Gen(at=env.now() + a125 * 12 * 60)
                        NurseDH_Gen(at=env.now() + a125 * 12 * 60)
                    yield self.hold(a122)
                    self.release(General_bed_DH)
                    DHPatients.generalbedtime.append(a122)
                    a126 = env.now()
                    self.enter(ICU_ventilator_waitingline)
                    yield self.request(ICU_ventilator, fail_delay = 30)
                    if self.failed():
                        self.leave(ICU_ventilator_waitingline)
                        G2V_ward()
                        dh_2_cc_c_ven += 1
                    else:
                        self.leave(ICU_ventilator_waitingline)
                        a127 = env.now()
                        a128 = a127 - a126
                        DHPatients.icuventilatorwaitingtime.append(a128)
                        dh_ven_wait.append(a128)
                        a129 = sim.Uniform(5 * 1440, 10 * 1440).sample()  # changed minutes
                        a130 = a129 / (12 * 60)
                        a131 = round(a130)
                        for a132 in range(0, a131):
                            DoctorDH_Ventilator(at=env.now() + a132 * 12 * 60)
                            NurseDH_Ventilator(at=env.now() + a132 * 12 * 60)
                        yield self.hold(a129)
                        self.release(ICU_ventilator)
                        DHPatients.icuventilatortime.append(a129)
                        a133 = env.now()
                        self.enter(Generalward_waitingline)
                        yield self.request(General_bed_DH)
                        self.leave(Generalward_waitingline)
                        a134 = env.now()
                        a135 = a134 - a133
                        DHPatients.generalbedwaitingtime.append(a135)
                        a136 = sim.Uniform(4 * 1440, 7 * 1440).sample()  # changed to minutes
                        a137 = a136 / (12 * 60)
                        a138 = round(a137)
                        for a139 in range(0, a138):
                            DoctorDH_Gen(at=env.now() + a139 * 12 * 60)
                            NurseDH_Gen(at=env.now() + a139 * 12 * 60)
                        yield self.hold(a136)
                        self.release(General_bed_DH)
                        DHPatients.generalbedtime.append(a136)


class DHPatients(sim.Component):
    triagewaitingtime = []
    generalbedwaitingtime = []
    icuoxygenwaitingtime = []
    icuventilatorwaitingtime = []
    receptionwaitingtime = []
    receptionistservicetime = []
    triageservicetime = []
    severepatients = 0
    moderatepatients = 0
    moderate_gen_to_exit = 0
    moderate_gen_to_icu_to_gen_exit = 0
    moderate_gen_to_ventilator_to_gen_exit = 0
    moderate_gen_refer_CCC = 0
    severe_icu_to_gen_refer_CCC = 0
    severe_ventilator_to_gen_refer_CCC = 0
    severe_ventilator_dead = 0
    severe_ventilator_dead_refer_CCC = 0
    No_of_covid_patients = 0
    generalbedtime = []
    icuoxygentime = []
    icuventilatortime = []
    R1 = 0  # icubed_with_oxygen_to_icu_with_ventilator
    R2 = 0  # icubed_with_oxygen_to_gen_ward
    R3 = 0  # icu ventilator_to_icu_oxygen
    R4 = 0  # icu ventilator_to_gen_ward

    def process(self):

        global DH_mild_count
        global warmup_time
        global dh_ven_wait

        if env.now() <= warmup_time:
            self.enter(waitingline_registration)  # patients enter registration line
            yield self.request(Receptionist)
            self.leave(waitingline_registration)
            a14 = sim.Triangular(125, 190, 145, 'seconds').sample()
            yield self.hold(a14)
            self.release()
            self.enter(waitingline_triage)  # patient is triaged and sent to either General ward or ICU ward
            # depending upon severity
            yield self.request((doctor_DH_Gen, 1))
            self.leave(waitingline_triage)
            a15 = sim.Uniform(1, 2, 'minutes').sample()
            yield self.hold(a15)
            self.release()
            a95 = random.randint(0, 100)
            if a95 < 94:  # mild patients
                if a95 < 10:  # patients require instituitional quarantine
                    cc_isolation()
            elif 94 <= a95 < 98:  # moderate patients
                Moderate_case()
            else:   # severe patients
                s = random.randint(0, 100)
                if s < 50:  # Type f patients
                    DH_SevereTypeF()
                elif 50 <= s < 74:  # E type patients
                    DH_SevereTypeE()
                else:
                    DH_SevereTypeD()
        else:
            DHPatients.No_of_covid_patients += 1
            a87 = env.now()
            self.enter(waitingline_registration)
            yield self.request(Receptionist)
            self.leave(waitingline_registration)
            a88 = env.now()
            a89 = a88 - a87
            DHPatients.receptionwaitingtime.append(a89)
            a90 = sim.Triangular(125, 190, 145, 'seconds').sample()
            yield self.hold(a90)
            self.release(Receptionist)
            DHPatients.receptionistservicetime.append(a90)
            a91 = env.now()
            self.enter(waitingline_triage)
            yield self.request((doctor_DH_Gen, 1))
            self.leave(waitingline_triage)
            a92 = env.now()
            a93 = a92 - a91
            DHPatients.triagewaitingtime.append(a93)
            a94 = sim.Uniform(1, 1.5, 'minutes').sample()
            yield self.hold(a94)
            self.release()
            DHPatients.triageservicetime.append(a94)
            a95 = random.randint(0, 100)
            if a95 < 94:  # mild patients
                DH_mild_count += 1
                if a95 < 10:  # patients require instituitional quarantine
                    cc_isolation()
            elif 94 <= a95 < 98:  # moderate patients
                Moderate_case()
            else:
                # severe patients
                s = random.randint(0, 100)
                if s < 50:  # Type f patients
                    DH_SevereTypeF()
                elif 50 <= s < 74:  # E type patients
                    DH_SevereTypeE()
                else:  # Type d patients
                    DH_SevereTypeD()


class DoctorDH_Gen(sim.Component):
    doc_DH_time_Gen = []

    def process(self):

        global warmup_time

        doc_time_DH_Gen = sim.Uniform(3/2, 6/2, "minutes").sample()
        if env.now() < warmup_time:
            yield self.request(doctor_DH_Gen)
            yield self.hold(doc_time_DH_Gen)
            self.release(doctor_DH_Gen)
        else:
            yield self.request(doctor_DH_Gen)
            yield self.hold(doc_time_DH_Gen)
            self.release(doctor_DH_Gen)
            DoctorDH_Gen.doc_DH_time_Gen.append(doc_time_DH_Gen)


class NurseDH_Gen(sim.Component):
    nurse_DH_time_Gen = []

    def process(self):

        global warmup_time

        nurse_time_DH_Gen = sim.Uniform(5 / 2, 10 / 2, "minutes").sample()

        if env.now() < warmup_time:
            yield self.request(nurse_DH_Gen)
            yield self.hold(nurse_time_DH_Gen)
            self.release(nurse_DH_Gen)
        else:
            yield self.request(nurse_DH_Gen)
            yield self.hold(nurse_time_DH_Gen)
            self.release(nurse_DH_Gen)
            NurseDH_Gen.nurse_DH_time_Gen.append(nurse_time_DH_Gen)


class DoctorDH_Oxygen(sim.Component):
    doc_DH_time_Oxygen = []

    def process(self):

        global warmup_time

        doc_time_DH_Oxygen = sim.Uniform(30 / 2, 60 / 2, "minutes").sample()

        if env.now() < warmup_time:
            yield self.request(doctor_DH_Oxygen)
            yield self.hold(doc_time_DH_Oxygen)
            self.release(doctor_DH_Oxygen)
        else:
            yield self.request(doctor_DH_Oxygen)
            yield self.hold(doc_time_DH_Oxygen)
            self.release(doctor_DH_Oxygen)
            DoctorDH_Oxygen.doc_DH_time_Oxygen.append(doc_time_DH_Oxygen)


class NurseDH_Oxygen(sim.Component):
    nurse_DH_time_Oxygen = []

    def process(self):
        global warmup_time
        nurse_time_DH_Oxygen = sim.Uniform(40 / 2, 80 / 2, "minutes").sample()
        if env.now() < warmup_time:
            yield self.request(nurse_DH_Oxygen)
            yield self.hold(nurse_time_DH_Oxygen)
            self.release(nurse_DH_Oxygen)
        else:
            yield self.request(nurse_DH_Oxygen)
            yield self.hold(nurse_time_DH_Oxygen)
            self.release(nurse_DH_Oxygen)
            NurseDH_Oxygen.nurse_DH_time_Oxygen.append(nurse_time_DH_Oxygen)


class DoctorDH_Ventilator(sim.Component):
    doc_DH_time_Ventilator = []

    def process(self):

        global warmup_time

        doc_time_DH_Ventilator = sim.Uniform(30 / 2, 60 / 2, "minutes").sample()

        if env.now() < warmup_time:
            yield self.request(doctor_DH_Ventilator)
            yield self.hold(doc_time_DH_Ventilator)
            self.release(doctor_DH_Ventilator)
        else:
            yield self.request(doctor_DH_Ventilator)
            yield self.hold(doc_time_DH_Ventilator)
            self.release(doctor_DH_Ventilator)
            DoctorDH_Ventilator.doc_DH_time_Ventilator.append(doc_time_DH_Ventilator)


class NurseDH_Ventilator(sim.Component):
    nurse_DH_time_Ventilator = []

    def process(self):
        global warmup_time

        nurse_time_DH_Ventilator = sim.Uniform(80 / 2, 160 / 2, "minutes").sample()

        if env.now() < warmup_time:
            yield self.request(nurse_DH_Ventilator)
            yield self.hold(nurse_time_DH_Ventilator)
            self.release(nurse_DH_Ventilator)
        else:
            yield self.request(nurse_DH_Ventilator)
            yield self.hold(nurse_time_DH_Ventilator)
            self.release(nurse_DH_Ventilator)
            NurseDH_Ventilator.nurse_DH_time_Ventilator.append(nurse_time_DH_Ventilator)


"COVID center code"


class cc_isolation(sim.Component):

    def process(self):
        global isolation_count
        global warmup_time
        global isolation_bed
        global m_iso_bed_wt
        global cc_iso_q

        if env.now() <= warmup_time:
            self.enter(cc_iso_q)
            yield self.request(isolation_bed)
            self.leave(cc_iso_q)
            yield self.hold(sim.Uniform(7 * 1440, 14 * 1440).sample())
            self.release(isolation_bed)
        else:
            isolation_count += 1
            self.enter(cc_iso_q)
            k1 = env.now()
            yield self.request(isolation_bed)
            k2 = env.now()
            self.leave(cc_iso_q)
            m_iso_bed_wt.append(k2-k1)

            yield self.hold(sim.Uniform(7 * 1440, 14 * 1440).sample())
            self.release(isolation_bed)


# class for typeA patients.


class cc_general_ward_TypeA(sim.Component):

    def process(self):
        global A_count
        global warmup_time
        global G_bed
        global general_count

        if env.now() < warmup_time:
            yield self.request(G_bed)
            t = sim.Uniform(4 * 1440, 5 * 1440).sample()
            yield self.hold(t)
            t1 = t / (12 * 60)
            t11 = round(t1)
            for t111 in range(0, t11):
                cc_gen_Doctor(at=env.now() + t111 * 12 * 60)
                cc_gen_Nurse(at=env.now() + t111 * 12 * 60)
            self.release(G_bed)
        else:

            A_count += 1
            general_count += 1
            yield self.request(G_bed)
            t = sim.Uniform(4 * 1440, 5 * 1440).sample()
            yield self.hold(t)
            t1 = t / (12 * 60)
            t11 = round(t1)
            for t111 in range(0, t11):
                cc_gen_Doctor(at=env.now() + t111 * 12 * 60)
                cc_gen_Nurse(at=env.now() + t111 * 12 * 60)
            self.release(G_bed)


# class for type B patients.
class cc_general_ward_TypeB(sim.Component):

    def process(self):
        global B_count
        global warmup_time
        global G_bed
        global general_count

        if env.now() < warmup_time:
            yield self.request(G_bed)
            t = sim.Uniform(3 * 1440, 4 * 1440).sample()
            yield self.hold(t)
            t1 = t / (12 * 60)
            t11 = round(t1)
            for t111 in range(0, t11):
                cc_gen_Doctor(at=env.now() + t111 * 12 * 60)
                cc_gen_Nurse(at=env.now() + t111 * 12 * 60)
            self.release(G_bed)
            G2O_ward()
        else:
            B_count += 1
            general_count += 1
            yield self.request(G_bed)
            t = sim.Uniform(4 * 1440, 5 * 1440).sample()
            yield self.hold(t)
            t1 = t / (12 * 60)
            t11 = round(t1)
            for t111 in range(0, t11):
                cc_gen_Doctor(at=env.now() + t111 * 12 * 60)
                cc_gen_Nurse(at=env.now() + t111 * 12 * 60)
            self.release(G_bed)
            G2O_ward()


# class for type C patients.

class cc_general_ward_TypeC(sim.Component):

    def process(self):
        global C_count
        global warmup_time
        global G_bed
        global general_count

        if env.now() < warmup_time:
            yield self.request(G_bed)
            t = sim.Uniform(3 * 1440, 4 * 1440).sample()
            yield self.hold(t)
            t1 = t / (12 * 60)
            t11 = round(t1)
            for t111 in range(0, t11):
                cc_gen_Doctor(at=env.now() + t111 * 12 * 60)
                cc_gen_Nurse(at=env.now() + t111 * 12 * 60)
            self.release(G_bed)
            G2V_ward()
        else:
            C_count += 1
            general_count += 1
            yield self.request(G_bed)
            t = sim.Uniform(3 * 1440, 4 * 1440).sample()
            yield self.hold(t)
            t1 = t / (12 * 60)
            t11 = round(t1)
            for t111 in range(0, t11):
                cc_gen_Doctor(at=env.now() + t111 * 12 * 60)
                cc_gen_Nurse(at=env.now() + t111 * 12 * 60)
            self.release(G_bed)
            G2V_ward()


# class for general ward doctor
class cc_gen_Doctor(sim.Component):

    def process(self):
        global G_doctor
        global G_doctor_time

        if env.now() < warmup_time:
            yield self.request(G_doctor)
            yield self.hold(sim.Uniform(3 / 2, 6 / 2, "minutes").sample())
            self.release(G_doctor)
        else:
            yield self.request(G_doctor)
            t = env.now()
            yield self.hold(sim.Uniform(3 / 2, 6 / 2, "minutes").sample())
            self.release(G_doctor)
            G_doctor_time += (env.now() - t)


class cc_gen_Nurse(sim.Component):

    def process(self):
        global G_nurse
        global G_nurse_time

        if env.now() < warmup_time:
            yield self.request(G_nurse)
            yield self.hold(sim.Uniform(5 / 2, 10 / 2).sample())
            self.release(G_nurse)
        else:
            yield self.request(G_nurse)
            t = env.now()
            yield self.hold(sim.Uniform(5/2, 10/2).sample())
            self.release(G_nurse)
            G_nurse_time += (env.now() - t)


class G2O_ward(sim.Component):  # general to oxygen ward

    def process(self):
        global warmup_time
        global O_bed
        global V_bed
        global G_bed

        if env.now() <= warmup_time:
            yield self.request(O_bed)
            t = sim.Uniform(5 * 1440, 10 * 1440).sample()
            yield self.hold(t)
            t1 = t / (12 * 60)
            t11 = round(t1)
            for t111 in range(0, t11):
                cc_O_Doctor(at=env.now() + t111 * 12 * 60)
                cc_O_Nurse(at=env.now() + t111 * 12 * 60)
            yield self.release(O_bed)
            # again shifted back to general ward
            yield self.request(G_bed)
            p = sim.Uniform(7 * 1440, 14 * 1440).sample()
            yield self.hold(p)
            p1 = p / (12 * 60)
            p11 = round(p1)
            for p111 in range(0, p11):
                cc_gen_Doctor(at=env.now() + p111 * 12 * 60)
                cc_gen_Nurse(at=env.now() + p111 * 12 * 60)
            yield self.release(G_bed)
        else:

            yield self.request(O_bed)
            t = sim.Uniform(5 * 1440, 7 * 1440).sample()
            yield self.hold(t)
            t1 = t / (12 * 60)
            t11 = round(t1)
            for t111 in range(0, t11):
                cc_O_Doctor(at=env.now() + t111 * 12 * 60)
                cc_O_Nurse(at=env.now() + t111 * 12 * 60)
            yield self.release(O_bed)
            # again shifted back to general ward
            yield self.request(G_bed)
            p = sim.Uniform(2 * 1440, 3 * 1440).sample()
            yield self.hold(p)
            p1 = p / (12 * 60)
            p11 = round(p1)
            for p111 in range(0, p11):
                cc_gen_Doctor(at=env.now() + p111 * 12 * 60)
                cc_gen_Nurse(at=env.now() + p111 * 12 * 60)
            yield self.release(G_bed)


class cc_O_Doctor(sim.Component):  # class for ICU oxygen doctor

    def process(self):
        global O_doctor
        global O_doctor_time

        if env.now() < warmup_time:
            yield self.request(O_doctor)
            yield self.hold(sim.Uniform(30 / 2, 60 / 2, "minutes").sample())
            self.release(O_doctor)
        else:
            yield self.request(O_doctor)
            t = env.now()
            yield self.hold(sim.Uniform(30 / 2, 60 / 2, "minutes").sample())
            self.release(O_doctor)
            O_doctor_time += (env.now() - t)


class cc_O_Nurse(sim.Component):  # class for ICU oxygen doctor

    def process(self):
        global O_nurse_time
        global warmup_time

        if env.now() < warmup_time:
            yield self.request(O_nurse)
            yield self.hold(sim.Uniform(40 / 2, 80 / 2, "minutes").sample())
            self.release(O_nurse)
        else:
            yield self.request(O_nurse)
            t = env.now()
            yield self.hold(sim.Uniform(40 / 2, 80 / 2, "minutes").sample())
            self.release(O_nurse)
            O_nurse_time += (env.now() - t)


class G2V_ward(sim.Component):  # general to ventilator ward

    def process(self):
        global warmup_time
        global V_bed

        if env.now() <= warmup_time:
            yield self.request(V_bed)
            t = sim.Uniform(5 * 1440, 7 * 1440).sample()
            yield self.hold(t)
            t1 = t / (12 * 60)
            t11 = round(t1)
            for t111 in range(0, t11):
                cc_V_Doctor(at=env.now() + t111 * 12 * 60)
                cc_V_Nurse(at=env.now() + t111 * 12 * 60)
            self.release(V_bed)
            # again shifted back to general ward
            yield self.request(G_bed)
            p = sim.Uniform(4 * 1440, 7 * 1440).sample()
            yield self.hold(p)
            p1 = p / (12 * 60)
            p11 = round(p1)
            for p111 in range(0, p11):
                cc_gen_Doctor(at=env.now() + p111 * 12 * 60)
                cc_gen_Nurse(at=env.now() + p111 * 12 * 60)
            self.release(G_bed)
        else:
            yield self.request(V_bed)
            t = sim.Uniform(5 * 1440, 10 * 1440).sample()
            yield self.hold(t)
            t1 = t / (12 * 60)
            t11 = round(t1)
            for t111 in range(0, t11):
                cc_V_Doctor(at=env.now() + t111 * 12 * 60)
                cc_V_Nurse(at=env.now() + t111 * 12 * 60)
            self.release(V_bed)
            # again shifted back to general ward
            yield self.request(G_bed)
            p = sim.Uniform(4 * 1440, 7 * 1440).sample()
            yield self.hold(p)
            p1 = p / (12 * 60)
            p11 = round(p1)
            for p111 in range(0, p11):
                cc_gen_Doctor(at=env.now() + p111 * 12 * 60)
                cc_gen_Nurse(at=env.now() + p111 * 12 * 60)
            self.release(G_bed)


class cc_V_Doctor(sim.Component):  # class for ICU ventilator doctor
    global V_doctor_time

    def process(self):
        global V_doctor
        global V_doctor_time

        if env.now() < warmup_time:
            yield self.request(V_doctor)
            yield self.hold(sim.Uniform(30 / 2, 60 / 2, "minutes").sample())
            self.release(V_doctor)
        else:
            yield self.request(V_doctor)
            t = env.now()
            yield self.hold(sim.Uniform(30 / 2, 60 / 2, "minutes").sample())
            self.release(V_doctor)
            V_doctor_time += (env.now() - t)


class cc_V_Nurse(sim.Component):  # class for ICU ventilator nurse
    global V_nurse_time

    def process(self):

        global V_nurse
        global V_nurse_time

        if env.now() < warmup_time:
            yield self.request(V_nurse)
            yield self.hold(sim.Uniform(80 / 2, 160 / 2, "minutes").sample())
            self.release(V_nurse)
        else:
            yield self.request(V_nurse)
            t = env.now()
            yield self.hold(sim.Uniform(80 / 2, 160 / 2, "minutes").sample())
            self.release(V_nurse)
            V_nurse_time += env.now() - t


class cc_ICU_ward_TypeE(sim.Component):  # class for the patients referred from severe E type patients.
    # these did not get bed on time

    def process(self):

        global D_count
        global E_count
        global F_count
        global warmup_time
        global O_bed
        global V_bed
        global G_bed
        global ICU_count
        global D_count
        global E_count
        global F_count
        global dead
        global severe_count
        global O_nurse_time

        if env.now() <= warmup_time:

            yield self.request(V_bed)
            t = sim.Uniform(4 * 1440, 7 * 1440).sample()
            yield self.hold(t)
            t1 = t / (12 * 60)
            t11 = round(t1)
            for t111 in range(0, t11):
                cc_V_Doctor(at=env.now() + t111 * 12 * 60)
                cc_V_Nurse(at=env.now() + t111 * 12 * 60)
            self.release(V_bed)
            # again back to general wards
            yield self.request(G_bed)
            p = sim.Uniform(4 * 1440, 7 * 1440).sample()
            yield self.hold(t)
            p1 = p / (12 * 60)
            p11 = round(p1)
            for p111 in range(0, p11):
                cc_gen_Doctor(at=env.now() + p111 * 12 * 60)
                cc_gen_Nurse(at=env.now() + p111 * 12 * 60)
            self.release(G_bed)

        else:  # after warm up time
            E_count += 1
            severe_count += 1
            yield self.request(V_bed)
            t = sim.Uniform(5 * 1440, 10 * 1440).sample()
            t1 = t / (12 * 60)
            t11 = round(t1)
            for t111 in range(0, t11):
                cc_V_Doctor(at=env.now() + t111 * 12 * 60)
                cc_V_Nurse(at=env.now() + t111 * 12 * 60)
            yield self.hold(t)
            self.release(V_bed)
            # again back to general wards
            yield self.request(G_bed)
            p = sim.Uniform(4 * 1440, 7 * 1440).sample()
            p1 = p / (12 * 60)
            p11 = round(p1)
            for p111 in range(0, p11):
                cc_gen_Doctor(at=env.now() + p111 * 12 * 60)
                cc_gen_Nurse(at=env.now() + p111 * 12 * 60)
            yield self.hold(p)
            self.release(G_bed)


class cc_ventilator_TypeF(sim.Component):  # this class is for the patients who are referred from DH of type F.
    # These did not get bed on time

    def process(self):
        global warmup_time
        global F_DH  # F type patients referred from DH
        global severe_count
        global G_bed
        global F_count

        if env.now() <= warmup_time:

            prob = random.randint(0, 50)
            if prob < 33:
                t = sim.Uniform(2 * 1440, 3 * 1440).sample()
                yield self.request(V_bed)
                yield self.hold(t)
                t1 = t / (12 * 60)
                t11 = round(t1)
                for t111 in range(0, t11):
                    cc_V_Doctor(at=env.now() + t111 * 12 * 60)
                    cc_V_Nurse(at=env.now() + t111 * 12 * 60)
                self.release(V_bed)
        else:
            F_DH += 1
            severe_count += 1
            F_count += 1
            t = sim.Uniform(5 * 1440, 10 * 1440).sample()
            yield self.request(V_bed)
            yield self.hold(t)
            t1 = t / (12 * 60)
            t11 = round(t1)
            for t111 in range(0, t11):
                cc_V_Doctor(at=env.now() + t111 * 12 * 60)
                cc_V_Nurse(at=env.now() + t111 * 12 * 60)
            self.release(V_bed)
            yield self.request(G_bed)
            p = sim.Uniform(2 * 1440, 3 * 1440).sample()
            yield self.hold(t)
            p1 = p / (12 * 60)
            p11 = round(p1)
            for p111 in range(0, p11):
                cc_gen_Doctor(at=env.now() + p111 * 12 * 60)
                cc_gen_Nurse(at=env.now() + p111 * 12 * 60)
            self.release(G_bed)


class cc_ventilator_TypeD(sim.Component):  # this class is for the patients who are refered from DH of type D.
    # These did not get bed on time

    def process(self):
        global warmup_time
        global D_count  # D type patients referred from DH
        global severe_count
        global dead
        global V_bed

        if env.now() <= warmup_time:

            t = sim.Uniform(2 * 1440, 3 * 1440).sample()
            yield self.request(V_bed)
            yield self.hold(t)
            t1 = t / (12 * 60)
            t11 = round(t1)
            for t111 in range(0, t11):
                cc_V_Doctor(at=env.now() + t111 * 12 * 60)
                cc_V_Nurse(at=env.now() + t111 * 12 * 60)
            self.release(V_bed)
        else:
            severe_count += 1
            D_count += 1
            dead += 1
            t = sim.Uniform(2 * 1440, 3 * 1440).sample()
            yield self.request(V_bed)
            yield self.hold(t)
            t1 = t / (12 * 60)
            t11 = round(t1)
            for t111 in range(0, t11):
                cc_V_Doctor(at=env.now() + t111 * 12 * 60)
                cc_V_Nurse(at=env.now() + t111 * 12 * 60)
            self.release(V_bed)


# add after warm up code


class cc_Type_F(sim.Component):  # class for the severe patients referred from the DH. Type F patients.

    def process(self):
        global warmup_time
        global F_count
        global O_bed
        global G_bed
        global V_bed
        global severe_count

        if env.now() <= warmup_time:
            pass
        else:
            severe_count += 1
            F_count += 1
            yield self.request(O_bed)
            t = sim.Uniform(5 * 1440, 7 * 1440).sample()
            yield self.hold(t)
            t1 = t / (12 * 60)
            t11 = round(t1)
            for t111 in range(0, t11):
                cc_O_Doctor(at=env.now() + t111 * 12 * 60)
                cc_O_Nurse(at=env.now() + t111 * 12 * 60)
            yield self.release(O_bed)
            # After spending 5-7 days
            # 10% will be shifted to general ward and remaining will require ventilator
            y = random.randint(0, 10)
            if y < 5:
                yield self.request(G_bed)
                p = sim.Uniform(2 * 1440, 3 * 1440).sample()
                yield self.hold(p)
                p1 = p / (12 * 60)
                p11 = round(p1)
                for p111 in range(0, p11):
                    cc_gen_Doctor(at=env.now() + p111 * 12 * 60)
                    cc_gen_Nurse(at=env.now() + p111 * 12 * 60)
                yield self.release(G_bed)
            else:  # 50% patients sent to ventilator, they will improve after staing for 5-10 days
                # and move to general ward
                yield self.request(V_bed)
                t = sim.Uniform(5 * 1440, 10 * 1440).sample()
                yield self.hold(t)
                t1 = t / (12 * 60)
                t11 = round(t1)
                for t111 in range(0, t11):
                    cc_V_Doctor(at=env.now() + t111 * 12 * 60)
                    cc_V_Nurse(at=env.now() + t111 * 12 * 60)
                yield self.release(V_bed)
                # again back to general wards
                yield self.request(G_bed)
                p = sim.Uniform(2 * 1440, 3 * 1440).sample()
                yield self.hold(t)
                p1 = p / (12 * 60)
                p11 = round(p1)
                for p111 in range(0, p11):
                    cc_gen_Doctor(at=env.now() + p111 * 12 * 60)
                    cc_gen_Nurse(at=env.now() + p111 * 12 * 60)
                yield self.release(G_bed)


# add after warm up code

def main(p):
    # defining system parameters

    # defining system parameters
    global days
    global days1
    global warmup_time
    global sim_time

    # defining Salabim variables/resources
    global env
    global doc_OPD
    global doc_Gyn
    global doc_Ped
    global doc_Dentist
    global xray_tech
    global pharmacist
    global lab_technician
    global delivery_nurse
    global ncd_nurse
    global registration_clerk
    global MO
    global emer_nurse
    global doc_surgeon
    global doc_ans
    # defining salabim queues
    global registration_q
    global medicine_q
    global gyn_q
    global ped_q
    global den_q
    global lab_q
    global xray_q
    global pharmacy_q
    global pharmacy_count

    # registration parameters
    global r_time_lb  # registration time lower bound
    global r_time_ub  # registration time upper bound
    global registration_q_waiting_time
    global registration_q_length
    global registration_time
    global total_opds

    global array_registration_time
    global array_registration_q_waiting_time
    global array_registration_q_length
    global array_registration_occupancy
    global array_total_patients

    array_total_patients = []
    array_registration_time = []
    array_registration_q_waiting_time = []
    array_registration_q_length = []
    array_registration_occupancy = []

    # opd medicine parameters
    global opd_iat_chc1
    global opd_ser_time_mean
    global opd_ser_time_sd
    global medicine_count
    global medicine_cons_time
    global opd_q_waiting_time

    global array_opd_patients
    global array_medicine_doctor_occupancy
    global array_opd_q_waiting_time
    global array_opd_q_length
    global array_medicine_count
    array_opd_patients = []
    array_medicine_doctor_occupancy = []
    array_opd_q_waiting_time = []
    array_opd_q_length = []
    array_medicine_count = []

    # NCD nurse variables
    global ncd_count
    global ncd_time

    global array_ncd_count
    global array_ncd_occupancy
    array_ncd_count = []
    array_ncd_occupancy = []

    # pharmacist variables
    global pharmacy_time
    global pharmacy_q_waiting_time
    global pharmacy_q_length
    global array_pharmacy_time
    global array_pharmacy_count

    global array_pharmacy_q_waiting_time
    global array_pharmacy_q_length
    global array_pharmacy_occupancy
    array_pharmacy_occupancy = []
    array_pharmacy_q_length = []
    array_pharmacy_q_waiting_time = []
    array_pharmacy_time = []
    array_pharmacy_count = []

    # lab variables
    global lab_time
    global lab_q_waiting_time
    global lab_q_length
    global lab_count
    global retesting_count_chc1

    global array_lab_q_waiting_time
    global array_lab_q_length
    global array_lab_occupancy
    global array_lab_count
    array_lab_count = []
    array_lab_occupancy = []
    array_lab_q_length = []
    array_lab_q_waiting_time = []

    # Gynecology variables
    global gyn_count
    global gyn_q_waiting_time
    global gyn_time

    global array_gyn_q_waiting_time
    global array_gyn_q_length
    global array_gyn_occupancy
    global array_gyn_count
    array_gyn_count = []
    array_gyn_occupancy = []
    array_gyn_q_length = []
    array_gyn_q_waiting_time = []

    # Pediatrics variables
    global ped_count
    global ped_q_waiting_time
    global ped_time

    global array_ped_q_waiting_time
    global array_ped_q_length
    global array_ped_occupancy
    global array_ped_count
    array_ped_count = []
    array_ped_occupancy = []
    array_ped_q_length = []
    array_ped_q_waiting_time = []

    # Dentist variables
    global den_count
    global den_consul
    global den_proced
    global den_q_waiting_time
    global den_time

    global array_den_q_waiting_time
    global array_den_q_length
    global array_den_occupancy
    global array_den_count
    global array_den_cons
    global array_den_proced
    array_den_count = []
    array_den_cons = []
    array_den_proced = []
    array_den_occupancy = []
    array_den_q_length = []
    array_den_q_waiting_time = []

    # Emergency variables
    global emergency_count
    global emergency_time
    global e_beds
    global delivery_nurse
    global emergency_nurse_time
    global emergency_bed_time
    global emergency_refer
    global array_emr_count
    global array_emr_doc_occupancy
    global array_emr_staffnurse_occupancy
    global array_emr_bed_occupancy
    global array_emr_bed_occupancy1
    global array_emergency_refer
    global emr_q
    global emr_q_waiting_time
    global array_emr_q_waiting_time
    global array_emr_q_length
    global array_emr_q_length_of_stay
    global emr_q_los

    array_emr_count = []
    array_emr_doc_occupancy = []
    array_emr_staffnurse_occupancy = []
    array_emr_bed_occupancy = []
    array_emr_bed_occupancy1 = []
    array_emergency_refer = []
    array_emr_q_waiting_time = []
    array_emr_q_length = []
    array_emr_q_length_of_stay = []
    emr_q_los = []

    # Delivery variables
    global delivery_iat
    global delivery_count
    global delivery_bed
    global delivery_nurse
    global ipd_nurse
    global MO
    global e_beds
    global delivery_nurse_time
    global MO_del_time
    global ipd_nurse_time
    global childbirth_count
    global childbirth_referred
    global array_childbirth_count
    global array_del_count
    global array_del_nurse_occupancy
    global array_del_bed_occupancy
    global array_childbirth_referred

    array_del_nurse_occupancy = []
    array_del_bed_occupancy = []
    array_del_count = []
    global referred
    global array_referred
    array_referred = []
    array_childbirth_referred = []
    array_childbirth_count = []

    # inpatient department
    global in_beds
    global ipd_q
    global ipd_MO_time_chc1
    global surgery_iat
    global inpatient_del_count
    global inpatient_count
    global array_ipd_count
    global array_ipd_staffnurse_occupancy
    global array_ipd_bed_occupancy
    global array_ipd_del_count
    global array_staffnurse_occupancy
    global emer_inpatients
    global array_emer_inpatients
    global ipd_bed_time
    global array_ipd_bed_time
    global ipd_nurse_time
    global ipd_surgery_count
    global array_ipd_surgery_count
    global array_ipd_bed_time_m
    global array_ip_waiting_time_chc1
    global array_ip_q_length
    global MO_ipd_chc1
    global ipd_MO_time_chc1
    global array_ipd_MO_occupancy
    global covid_bed_chc1

    array_ipd_surgery_count = []
    array_ipd_staffnurse_occupancy = []
    array_ipd_bed_occupancy = []
    array_ipd_count = []
    array_ipd_del_count = []
    array_staffnurse_occupancy = []
    array_emer_inpatients = []
    array_ipd_bed_time = []
    array_ipd_bed_time_m = []
    array_ip_waiting_time_chc1 = []
    array_ip_q_length = []
    array_ipd_MO_occupancy = []

    # ANC
    global ANC_iat

    # surgery
    global surgery_iat
    global surgery_count
    global doc_surgeon
    global doc_ans
    global sur_time
    global ans_time
    global ot_nurse
    global ot_nurse_time
    global array_ot_doc_occupancy
    global array_ot_anasthetic_occupancy
    global array_ot_nurse_occupancy
    global array_ot_count
    array_ot_doc_occupancy = []
    array_ot_anasthetic_occupancy = []
    array_ot_nurse_occupancy = []
    array_ot_count = []

    # Xray & ecg variables
    global xray_tech
    global xray_q
    global xray_q_waiting_time
    global xray_q_length
    global array_xray_occupancy
    global array_xray_q_length
    global array_xray_q_waiting_time
    global radio_count
    global array_radio_count
    global xray_count
    global ecg_count
    global array_xray_count
    global array_ecg_count
    global array_radio_q_waiting_time_sys
    global array_radio_time
    global xray_time
    global xray_time
    global array_xray_time
    global array_ecg_time
    global xray_tech
    global ecg_q
    global ecg_q_waiting_time
    global ecg_q_length
    global array_ecg_occupancy
    global array_ecg_q_length
    global array_ecg_q_waiting_time

    array_radio_q_waiting_time_sys = []

    array_xray_occupancy = []
    array_xray_q_length = []
    array_xray_q_waiting_time = []
    array_radio_count = []
    array_xray_count = []
    array_ecg_count = []
    array_radio_time = []
    array_xray_time = []
    array_ecg_time = []

    array_ecg_occupancy = []
    array_ecg_q_length = []
    array_ecg_q_waiting_time = []

    # covid
    global covid_q
    global home_refer
    global chc_refer
    global dh_refer_chc1

    global isolation_ward_refer_from_CHC
    global array_home_refer
    global array_chc_refer
    global array_dh_refer
    global array_isolation_ward_refer_from_CHC
    global d  # number of days for OPD
    global covid_count
    global covid_patient_time_chc1
    global array_covid_patient_time
    global MO_covid_time_chc1
    global array_covid_bed_waiting_time
    global array_covid_q_length
    global array_covid_bed_occupancy
    global covid_generator
    global phc2chc_count
    global array_phc2chc_count
    global array_covid_count
    global chc1_covid_bed_time
    global array_chc1_covid_bed_occ

    array_phc2chc_count = []
    array_chc1_covid_bed_occ = []
    array_covid_count = []
    array_covid_bed_occupancy = []
    array_covid_bed_waiting_time = []
    array_covid_q_length = []

    array_chc_refer = []
    array_home_refer = []
    array_dh_refer = []
    array_covid_patient_time = []
    array_isolation_ward_refer_from_CHC = []  # Added October 8

    # admin work
    global admin_work_chc1
    global ip_bed_cap
    global emergency_iat

    global array_dh_refer_chc1
    global array_dh_refer_chc2
    global array_dh_refer_chc3
    array_dh_refer_chc1 = []
    array_dh_refer_chc2 = []
    array_dh_refer_chc3 = []
    # queue parameters
    global q_len_chc1
    global array_q_len_chc1
    q_len_chc1 = []
    array_q_len_chc1 = []

    # New added on jan 6 for calculating proprtions
    # variables and arrays for severe patients
    global d_cc_chc1
    global e_cc_chc1
    global f_cc_chc1
    global d_dh_chc1
    global e_dh_chc1
    global f_dh_chc1
    global array_d_cc_chc1
    global array_e_cc_chc1
    global array_f_cc_chc1
    global array_d_dh_chc1
    global array_e_dh_chc1
    global array_f_dh_chc1
    global t_s_chc1
    global t_d_chc1
    global t_e_chc1
    global t_f_chc1

    # variables and arrays for moderate patients

    global t_c_chc1
    global t_b_chc1
    global t_a_chc1
    global a_cc_chc1
    global b_cc_chc1
    global c_cc_chc1
    global a_dh_chc1
    global b_dh_chc1
    global c_dh_chc1
    global t_m_chc1

    global array_a_cc_chc1
    global array_b_cc_chc1
    global array_c_cc_chc1
    global array_a_dh_chc1
    global array_b_dh_chc1
    global array_c_dh_chc1

    global array_prop_a2cc_chc1_max
    global array_prop_a2dh_chc1_max
    global array_prop_a2cc_chc1_avg
    global array_prop_a2dh_chc1_avg

    global array_prop_b2cc_chc1_max
    global array_prop_b2dh_chc1_max
    global array_prop_b2cc_chc1_avg
    global array_prop_b2dh_chc1_avg

    global array_prop_c2cc_chc1_max
    global array_prop_c2dh_chc1_max
    global array_prop_c2cc_chc1_avg
    global array_prop_c2dh_chc1_avg

    global array_prop_d2cc_chc1_max
    global array_prop_d2dh_chc1_max
    global array_prop_d2cc_chc1_avg
    global array_prop_d2dh_chc1_avg

    global array_prop_e2cc_chc1_max
    global array_prop_e2dh_chc1_max
    global array_prop_e2cc_chc1_avg
    global array_prop_e2dh_chc1_avg

    global array_prop_f2cc_chc1_max
    global array_prop_f2dh_chc1_max
    global array_prop_f2cc_chc1_avg
    global array_prop_f2dh_chc1_avg

    array_d_cc_chc1 = []
    array_e_cc_chc1 = []
    array_f_cc_chc1 = []
    array_d_dh_chc1 = []
    array_e_dh_chc1 = []
    array_f_dh_chc1 = []

    array_a_cc_chc1 = []
    array_b_cc_chc1 = []
    array_c_cc_chc1 = []
    array_a_dh_chc1 = []
    array_b_dh_chc1 = []
    array_c_dh_chc1 = []

    array_prop_a2cc_chc1_max = []
    array_prop_a2dh_chc1_max = []
    array_prop_a2cc_chc1_avg = []
    array_prop_a2dh_chc1_avg = []

    array_prop_b2cc_chc1_max = []
    array_prop_b2dh_chc1_max = []
    array_prop_b2cc_chc1_avg = []
    array_prop_b2dh_chc1_avg = []

    array_prop_c2cc_chc1_max = []
    array_prop_c2dh_chc1_max = []
    array_prop_c2cc_chc1_avg = []
    array_prop_c2dh_chc1_avg = []

    array_prop_d2cc_chc1_max = []
    array_prop_d2dh_chc1_max = []
    array_prop_d2cc_chc1_avg = []
    array_prop_d2dh_chc1_avg = []

    array_prop_e2cc_chc1_max = []
    array_prop_e2dh_chc1_max = []
    array_prop_e2cc_chc1_avg = []
    array_prop_e2dh_chc1_avg = []

    array_prop_f2cc_chc1_max = []
    array_prop_f2dh_chc1_max = []
    array_prop_f2cc_chc1_avg = []
    array_prop_f2dh_chc1_avg = []

    global array_t_s_chc1
    global array_t_d_chc1
    global array_t_e_chc1
    global array_t_f_chc1
    global array_t_m_chc1
    global array_t_a_chc1
    global array_t_b_chc1
    global array_t_c_chc1

    array_t_s_chc1 = []
    array_t_d_chc1 = []
    array_t_e_chc1 = []
    array_t_f_chc1 = []
    array_t_m_chc1 = []
    array_t_a_chc1 = []
    array_t_b_chc1 = []
    array_t_c_chc1 = []

    global array_moderate_chc1
    global array_severe_chc1
    array_moderate_chc1 = []
    array_severe_chc1 = []
    # New CHC1
    global a_dh_chc1
    global a_cc_chc1
    global b_dh_chc1
    global b_cc_chc1
    global c_dh_chc1
    global c_cc_chc1
    global d_dh_chc1
    global d_cc_chc1
    global e_dh_chc1
    global e_cc_chc1
    global f_dh_chc1
    global f_cc_chc1

    a_dh_chc1 = []
    a_cc_chc1 = []
    b_dh_chc1 = []
    b_cc_chc1 = []
    c_dh_chc1 = []
    c_cc_chc1 = []
    d_dh_chc1 = []
    d_cc_chc1 = []
    e_dh_chc1 = []
    e_cc_chc1 = []
    f_dh_chc1 = []
    f_cc_chc1 = []

    global array_moderate_chc2
    global array_severe_chc2
    array_moderate_chc2 = []
    array_severe_chc2 = []

    # CHC 2
    # queue parameters
    global q_len_chc2
    global array_q_len_chc2
    q_len_chc2 = []
    array_q_len_chc2 = []

    # defining system parameters
    global days1
    global warmup_time
    global sim_time

    # defining Salabim variables/resources
    global env
    global doc_OPD_chc2
    global doc_Gyn_chc2
    global doc_Ped_chc2
    global doc_Dentist_chc2
    global xray_tech_chc2
    global pharmacist_chc2
    global lab_technician_chc2
    global delivery_nurse_chc2
    global ncd_nurse_chc2
    global registration_clerk_chc2
    global MO_chc2
    global emer_nurse_chc2
    global doc_surgeon_chc2
    global doc_ans_chc2
    # defining salabim queues
    global registration_q_chc2
    global medicine_q_chc2
    global gyn_q_chc2
    global ped_q_chc2
    global den_q_chc2
    global lab_q_chc2
    global xray_q_chc2
    global pharmacy_q_chc2
    global pharmacy_count_chc2

    # registration parameters
    global r_time_lb_chc2  # registration time lower bound
    global r_time_ub_chc2  # registration time upper bound
    global registration_q_waiting_time_chc2
    global registration_q_length_chc2
    global registration_time_chc2
    global total_opds_chc2

    global array_registration_time_chc2
    global array_registration_q_waiting_time_chc2
    global array_registration_q_length_chc2
    global array_registration_occupancy_chc2
    global array_total_patients_chc2

    array_total_patients_chc2 = []
    array_registration_time_chc2 = []
    array_registration_q_waiting_time_chc2 = []
    array_registration_q_length_chc2 = []
    array_registration_occupancy_chc2 = []

    # opd medicine parameters
    global opd_iat_chc2
    global opd_ser_time_mean_chc2
    global opd_ser_time_sd_chc2
    global medicine_count_chc2
    global medicine_cons_time_chc2
    global opd_q_waiting_time_chc2

    global array_opd_patients_chc2
    global array_medicine_doctor_occupancy_chc2
    global array_opd_q_waiting_time_chc2
    global array_opd_q_length_chc2
    global array_medicine_count_chc2
    array_opd_patients_chc2 = []
    array_medicine_doctor_occupancy_chc2 = []
    array_opd_q_waiting_time_chc2 = []
    array_opd_q_length_chc2 = []
    array_medicine_count_chc2 = []

    # NCD nurse variables
    global ncd_count_chc2
    global ncd_time_chc2

    global array_ncd_count_chc2
    global array_ncd_occupancy_chc2
    array_ncd_count_chc2 = []
    array_ncd_occupancy_chc2 = []

    # pharmacist variables
    global pharmacy_time_chc2
    global pharmacy_q_waiting_time_chc2
    global pharmacy_q_length_chc2
    global array_pharmacy_time_chc2
    global array_pharmacy_count_chc2

    global array_pharmacy_q_waiting_time_chc2
    global array_pharmacy_q_length_chc2
    global array_pharmacy_occupancy_chc2
    array_pharmacy_occupancy_chc2 = []
    array_pharmacy_q_length_chc2 = []
    array_pharmacy_q_waiting_time_chc2 = []
    array_pharmacy_time_chc2 = []
    array_pharmacy_count_chc2 = []

    # lab variables
    global lab_time_chc2
    global lab_q_waiting_time_chc2
    global lab_q_length_chc2
    global lab_count_chc2
    global retesting_count_chc2

    global array_lab_q_waiting_time_chc2
    global array_lab_q_length_chc2
    global array_lab_occupancy_chc2
    global array_lab_count_chc2
    global lab_covidcount_chc2
    array_lab_count_chc2 = []
    array_lab_occupancy_chc2 = []
    array_lab_q_length_chc2 = []
    array_lab_q_waiting_time_chc2 = []

    # Gynecology variables
    global gyn_count_chc2
    global gyn_q_waiting_time_chc2
    global gyn_time_chc2

    global array_gyn_q_waiting_time_chc2
    global array_gyn_q_length_chc2
    global array_gyn_occupancy_chc2
    global array_gyn_count_chc2
    array_gyn_count_chc2 = []
    array_gyn_occupancy_chc2 = []
    array_gyn_q_length_chc2 = []
    array_gyn_q_waiting_time_chc2 = []

    # Pediatrics variables
    global ped_count_chc2
    global ped_q_waiting_time_chc2
    global ped_time_chc2

    global array_ped_q_waiting_time_chc2
    global array_ped_q_length_chc2
    global array_ped_occupancy_chc2
    global array_ped_count_chc2
    array_ped_count_chc2 = []
    array_ped_occupancy_chc2 = []
    array_ped_q_length_chc2 = []
    array_ped_q_waiting_time_chc2 = []

    # Dentist variables
    global den_count_chc2
    global den_consul_chc2
    global den_proced_chc2
    global den_q_waiting_time_chc2
    global den_time_chc2

    global array_den_q_waiting_time_chc2
    global array_den_q_length_chc2
    global array_den_occupancy_chc2
    global array_den_count_chc2
    global array_den_cons_chc2
    global array_den_proced_chc2
    array_den_count_chc2 = []
    array_den_cons_chc2 = []
    array_den_proced_chc2 = []
    array_den_occupancy_chc2 = []
    array_den_q_length_chc2 = []
    array_den_q_waiting_time_chc2 = []

    # Emergency variables
    global emergency_count_chc2
    global emergency_time_chc2
    global e_beds_chc2
    global delivery_nurse_chc2
    global emergency_nurse_time_chc2
    global emergency_bed_time_chc2
    global emergency_refer_chc2
    global array_emr_count_chc2
    global array_emr_doc_occupancy_chc2
    global array_emr_staffnurse_occupancy_chc2
    global array_emr_bed_occupancy_chc2
    global array_emr_bed_occupancy1_chc2
    global array_emergency_refer_chc2
    global emr_q_chc2
    global emr_q_waiting_time_chc2
    global array_emr_q_waiting_time_chc2
    global array_emr_q_length_chc2
    global array_emr_q_length_of_stay_chc2
    global emr_q_los_chc2

    array_emr_count_chc2 = []
    array_emr_doc_occupancy_chc2 = []
    array_emr_staffnurse_occupancy_chc2 = []
    array_emr_bed_occupancy_chc2 = []
    array_emr_bed_occupancy1_chc2 = []
    array_emergency_refer_chc2 = []
    array_emr_q_waiting_time_chc2 = []
    array_emr_q_length_chc2 = []
    array_emr_q_length_of_stay_chc2 = []
    emr_q_los_chc2 = []

    # Delivery variables
    global delivery_iat_chc2
    global delivery_count_chc2
    global delivery_bed_chc2
    global delivery_nurse_chc2
    global ipd_nurse_chc2
    global MO_chc2
    global e_beds_chc2
    global delivery_nurse_time_chc2
    global MO_del_time_chc2
    global ipd_nurse_time_chc2
    global childbirth_count_chc2
    global childbirth_referred_chc2
    global array_childbirth_count_chc2
    global array_del_count_chc2
    global array_del_nurse_occupancy_chc2
    global array_del_bed_occupancy_chc2
    global array_childbirth_referred_chc2

    array_del_nurse_occupancy_chc2 = []
    array_del_bed_occupancy_chc2 = []
    array_del_count_chc2 = []
    global referred_chc2
    global array_referred_chc2
    array_referred_chc2 = []
    array_childbirth_referred_chc2 = []
    array_childbirth_count_chc2 = []

    # inpatient department
    global in_beds_chc2
    global ipd_q_chc2
    global ipd_MO_time_chc2
    global surgery_iat_chc2
    global inpatient_del_count_chc2
    global inpatient_count_chc2
    global array_ipd_count_chc2
    global array_ipd_staffnurse_occupancy_chc2
    global array_ipd_bed_occupancy_chc2
    global array_ipd_del_count_chc2
    global array_staffnurse_occupancy_chc2
    global emer_inpatients_chc2
    global array_emer_inpatients_chc2
    global ipd_bed_time_chc2
    global array_ipd_bed_time_chc2
    global ipd_nurse_time_chc2
    global ipd_surgery_count_chc2
    global array_ipd_surgery_count_chc2
    global array_ipd_bed_time_m_chc2
    global array_ip_waiting_time_chc2
    global array_ip_q_length_chc2
    global MO_ipd_chc2
    global ipd_MO_time_chc2
    global array_ipd_MO_occupancy_chc2
    global covid_bed_chc2

    global isolation_bed
    global m_iso_bed_wt
    global array_m_iso_bed_wt

    m_iso_bed_wt = []
    array_m_iso_bed_wt = []
    global m_isolation_bed_wait_time
    m_isolation_bed_wait_time = []

    array_ipd_surgery_count_chc2 = []
    array_ipd_staffnurse_occupancy_chc2 = []
    array_ipd_bed_occupancy_chc2 = []
    array_ipd_count_chc2 = []
    array_ipd_del_count_chc2 = []
    array_staffnurse_occupancy_chc2 = []
    array_emer_inpatients_chc2 = []
    array_ipd_bed_time_chc2 = []
    array_ipd_bed_time_m_chc2 = []
    array_ip_waiting_time_chc2 = []
    array_ip_q_length_chc2 = []
    array_ipd_MO_occupancy_chc2 = []

    # ANC
    global ANC_iat_chc2

    # surgery
    global surgery_iat_chc2
    global surgery_count_chc2
    global doc_surgeon_chc2
    global doc_ans_chc2
    global sur_time_chc2
    global ans_time_chc2
    global ot_nurse_chc2
    global ot_nurse_time_chc2
    global array_ot_doc_occupancy_chc2
    global array_ot_anasthetic_occupancy_chc2
    global array_ot_nurse_occupancy_chc2
    global array_ot_count_chc2
    array_ot_doc_occupancy_chc2 = []
    array_ot_anasthetic_occupancy_chc2 = []
    array_ot_nurse_occupancy_chc2 = []
    array_ot_count_chc2 = []

    # Xray & ecg variables
    global xray_tech_chc2
    global xray_q_chc2
    global xray_q_waiting_time_chc2
    global xray_q_length_chc2
    global array_xray_occupancy_chc2
    global array_xray_q_length_chc2
    global array_xray_q_waiting_time_chc2
    global radio_count_chc2
    global array_radio_count_chc2
    global xray_count_chc2
    global ecg_count_chc2
    global array_xray_count_chc2
    global array_ecg_count_chc2
    global array_radio_q_waiting_time_sys_chc2
    global array_radio_time_chc2
    global xray_time_chc2
    global xray_time_chc2
    global array_xray_time_chc2
    global array_ecg_time_chc2
    global xray_tech_chc2
    global ecg_q_chc2
    global ecg_q_waiting_time_chc2
    global ecg_q_length_chc2
    global array_ecg_occupancy_chc2
    global array_ecg_q_length_chc2
    global array_ecg_q_waiting_time_chc2

    array_radio_q_waiting_time_sys_chc2 = []

    array_xray_occupancy_chc2 = []
    array_xray_q_length_chc2 = []
    array_xray_q_waiting_time_chc2 = []
    array_radio_count_chc2 = []
    array_xray_count_chc2 = []
    array_ecg_count_chc2 = []
    array_radio_time_chc2 = []
    array_xray_time_chc2 = []
    array_ecg_time_chc2 = []

    array_ecg_occupancy_chc2 = []
    array_ecg_q_length_chc2 = []
    array_ecg_q_waiting_time_chc2 = []

    # covid
    global covid_q_chc2
    global home_refer_chc2
    global chc_refer_chc2
    global dh_refer_chc2
    global isolation_ward_refer_from_CHC_chc2
    global array_home_refer_chc2
    global array_chc_refer_chc2

    global array_isolation_ward_refer_from_CHC_chc2
    global d_chc2  # number of days for OPD
    global covid_count_chc2
    global covid_patient_time_chc2
    global array_covid_patient_time_chc2
    global MO_covid_time_chc2
    global array_covid_bed_waiting_time_chc2
    global array_covid_q_length_chc2
    global array_covid_bed_occupancy_chc2
    global covid_generator_chc2
    global phc2chc_count_chc2
    global array_phc2chc_count_chc2
    global array_covid_count_chc2
    global chc2_covid_bed_time
    global array_chc2_covid_bed_occ
    array_chc2_covid_bed_occ = []

    array_phc2chc_count_chc2 = []
    array_covid_count_chc2 = []
    array_covid_bed_occupancy_chc2 = []
    array_covid_bed_waiting_time_chc2 = []
    array_covid_q_length_chc2 = []

    array_chc_refer_chc2 = []
    array_home_refer_chc2 = []

    array_covid_patient_time_chc2 = []
    array_isolation_ward_refer_from_CHC_chc2 = []  # Added October 8

    # New added on jan 6 for calculating proprtions
    # variables and arrays for severe patients
    global d_cc_chc2
    global e_cc_chc2
    global f_cc_chc2
    global d_dh_chc2
    global e_dh_chc2
    global f_dh_chc2
    global array_d_cc_chc2
    global array_e_cc_chc2
    global array_f_cc_chc2
    global array_d_dh_chc2
    global array_e_dh_chc2
    global array_f_dh_chc2
    global t_s_chc2
    global t_d_chc2
    global t_e_chc2
    global t_f_chc2

    # variables and arrays for moderate patients

    global t_c_chc2
    global t_b_chc2
    global t_a_chc2
    global a_cc_chc2
    global b_cc_chc2
    global c_cc_chc2
    global a_dh_chc2
    global b_dh_chc2
    global c_dh_chc2
    global t_m_chc2

    global array_a_cc_chc2
    global array_b_cc_chc2
    global array_c_cc_chc2
    global array_a_dh_chc2
    global array_b_dh_chc2
    global array_c_dh_chc2

    global array_prop_a2cc_chc2_max
    global array_prop_a2dh_chc2_max
    global array_prop_a2cc_chc2_avg
    global array_prop_a2dh_chc2_avg

    global array_prop_b2cc_chc2_max
    global array_prop_b2dh_chc2_max
    global array_prop_b2cc_chc2_avg
    global array_prop_b2dh_chc2_avg

    global array_prop_c2cc_chc2_max
    global array_prop_c2dh_chc2_max
    global array_prop_c2cc_chc2_avg
    global array_prop_c2dh_chc2_avg

    global array_prop_d2cc_chc2_max
    global array_prop_d2dh_chc2_max
    global array_prop_d2cc_chc2_avg
    global array_prop_d2dh_chc2_avg

    global array_prop_e2cc_chc2_max
    global array_prop_e2dh_chc2_max
    global array_prop_e2cc_chc2_avg
    global array_prop_e2dh_chc2_avg

    global array_prop_f2cc_chc2_max
    global array_prop_f2dh_chc2_max
    global array_prop_f2cc_chc2_avg
    global array_prop_f2dh_chc2_avg

    array_d_cc_chc2 = []
    array_e_cc_chc2 = []
    array_f_cc_chc2 = []
    array_d_dh_chc2 = []
    array_e_dh_chc2 = []
    array_f_dh_chc2 = []

    array_a_cc_chc2 = []
    array_b_cc_chc2 = []
    array_c_cc_chc2 = []
    array_a_dh_chc2 = []
    array_b_dh_chc2 = []
    array_c_dh_chc2 = []

    array_prop_a2cc_chc2_max = []
    array_prop_a2dh_chc2_max = []
    array_prop_a2cc_chc2_avg = []
    array_prop_a2dh_chc2_avg = []

    array_prop_b2cc_chc2_max = []
    array_prop_b2dh_chc2_max = []
    array_prop_b2cc_chc2_avg = []
    array_prop_b2dh_chc2_avg = []

    array_prop_c2cc_chc2_max = []
    array_prop_c2dh_chc2_max = []
    array_prop_c2cc_chc2_avg = []
    array_prop_c2dh_chc2_avg = []

    array_prop_d2cc_chc2_max = []
    array_prop_d2dh_chc2_max = []
    array_prop_d2cc_chc2_avg = []
    array_prop_d2dh_chc2_avg = []

    array_prop_e2cc_chc2_max = []
    array_prop_e2dh_chc2_max = []
    array_prop_e2cc_chc2_avg = []
    array_prop_e2dh_chc2_avg = []

    array_prop_f2cc_chc2_max = []
    array_prop_f2dh_chc2_max = []
    array_prop_f2cc_chc2_avg = []
    array_prop_f2dh_chc2_avg = []

    global array_t_s_chc2
    global array_t_d_chc2
    global array_t_e_chc2
    global array_t_f_chc2
    global array_t_m_chc2
    global array_t_a_chc2
    global array_t_b_chc2
    global array_t_c_chc2

    array_t_s_chc2 = []
    array_t_d_chc2 = []
    array_t_e_chc2 = []
    array_t_f_chc2 = []
    array_t_m_chc2 = []
    array_t_a_chc2 = []
    array_t_b_chc2 = []
    array_t_c_chc2 = []

    # admin work
    global admin_work_chc2
    global ip_bed_cap_chc2
    global emergency_iat_chc2

    global moderate_refered_chc1
    global moderate_refered_chc2
    global moderate_refered_chc3
    global array_moderate_refered_chc1
    global array_moderate_refered_chc2
    global array_moderate_refered_chc3

    array_moderate_refered_chc1 = []
    array_moderate_refered_chc2 = []
    array_moderate_refered_chc3 = []

    # CHC 3
    # queue parameters
    global q_len_chc3
    global array_q_len_chc3
    q_len_chc3 = []
    array_q_len_chc3 = []
    global env
    global doc_OPD_chc3
    global doc_Gyn_chc3
    global doc_Ped_chc3
    global doc_Dentist_chc3
    global xray_tech_chc3
    global pharmacist_chc3
    global lab_technician_chc3
    global delivery_nurse_chc3
    global ncd_nurse_chc3
    global registration_clerk_chc3
    global MO_chc3
    global emer_nurse_chc3
    global doc_surgeon_chc3
    global doc_ans_chc3
    # defining salabim queues
    global registration_q_chc3
    global medicine_q_chc3
    global gyn_q_chc3
    global ped_q_chc3
    global den_q_chc3
    global lab_q_chc3
    global xray_q_chc3
    global pharmacy_q_chc3
    global pharmacy_count_chc3

    # registration parameters
    global r_time_lb_chc3  # registration time lower bound
    global r_time_ub_chc3  # registration time upper bound
    global registration_q_waiting_time_chc3
    global registration_q_length_chc3
    global registration_time_chc3
    global total_opds_chc3

    global array_registration_time_chc3
    global array_registration_q_waiting_time_chc3
    global array_registration_q_length_chc3
    global array_registration_occupancy_chc3
    global array_total_patients_chc3

    array_total_patients_chc3 = []
    array_registration_time_chc3 = []
    array_registration_q_waiting_time_chc3 = []
    array_registration_q_length_chc3 = []
    array_registration_occupancy_chc3 = []

    # opd medicine parameters
    global opd_iat_chc3
    global opd_ser_time_mean_chc3
    global opd_ser_time_sd_chc3
    global medicine_count_chc3
    global medicine_cons_time_chc3
    global opd_q_waiting_time_chc3

    global array_opd_patients_chc3
    global array_medicine_doctor_occupancy_chc3
    global array_opd_q_waiting_time_chc3
    global array_opd_q_length_chc3
    global array_medicine_count_chc3
    array_opd_patients_chc3 = []
    array_medicine_doctor_occupancy_chc3 = []
    array_opd_q_waiting_time_chc3 = []
    array_opd_q_length_chc3 = []
    array_medicine_count_chc3 = []

    # NCD nurse variables
    global ncd_count_chc3
    global ncd_time_chc3

    global array_ncd_count_chc3
    global array_ncd_occupancy_chc3
    array_ncd_count_chc3 = []
    array_ncd_occupancy_chc3 = []

    # pharmacist variables
    global pharmacy_time_chc3
    global pharmacy_q_waiting_time_chc3
    global pharmacy_q_length_chc3
    global array_pharmacy_time_chc3
    global array_pharmacy_count_chc3

    global array_pharmacy_q_waiting_time_chc3
    global array_pharmacy_q_length_chc3
    global array_pharmacy_occupancy_chc3
    array_pharmacy_occupancy_chc3 = []
    array_pharmacy_q_length_chc3 = []
    array_pharmacy_q_waiting_time_chc3 = []
    array_pharmacy_time_chc3 = []
    array_pharmacy_count_chc3 = []

    # lab variables
    global lab_time_chc3
    global lab_q_waiting_time_chc3
    global lab_q_length_chc3
    global lab_count_chc3
    global retesting_count_chc3

    global array_lab_q_waiting_time_chc3
    global array_lab_q_length_chc3
    global array_lab_occupancy_chc3
    global array_lab_count_chc3
    global lab_covidcount_chc3
    array_lab_count_chc3 = []
    array_lab_occupancy_chc3 = []
    array_lab_q_length_chc3 = []
    array_lab_q_waiting_time_chc3 = []

    # Gynecology variables
    global gyn_count_chc3
    global gyn_q_waiting_time_chc3
    global gyn_time_chc3

    global array_gyn_q_waiting_time_chc3
    global array_gyn_q_length_chc3
    global array_gyn_occupancy_chc3
    global array_gyn_count_chc3
    array_gyn_count_chc3 = []
    array_gyn_occupancy_chc3 = []
    array_gyn_q_length_chc3 = []
    array_gyn_q_waiting_time_chc3 = []

    # Pediatrics variables
    global ped_count_chc3
    global ped_q_waiting_time_chc3
    global ped_time_chc3

    global array_ped_q_waiting_time_chc3
    global array_ped_q_length_chc3
    global array_ped_occupancy_chc3
    global array_ped_count_chc3
    array_ped_count_chc3 = []
    array_ped_occupancy_chc3 = []
    array_ped_q_length_chc3 = []
    array_ped_q_waiting_time_chc3 = []

    # Dentist variables
    global den_count_chc3
    global den_consul_chc3
    global den_proced_chc3
    global den_q_waiting_time_chc3
    global den_time_chc3

    global array_den_q_waiting_time_chc3
    global array_den_q_length_chc3
    global array_den_occupancy_chc3
    global array_den_count_chc3
    global array_den_cons_chc3
    global array_den_proced_chc3
    array_den_count_chc3 = []
    array_den_cons_chc3 = []
    array_den_proced_chc3 = []
    array_den_occupancy_chc3 = []
    array_den_q_length_chc3 = []
    array_den_q_waiting_time_chc3 = []

    # Emergency variables
    global emergency_count_chc3
    global emergency_time_chc3
    global e_beds_chc3
    global delivery_nurse_chc3
    global emergency_nurse_time_chc3
    global emergency_bed_time_chc3
    global emergency_refer_chc3
    global array_emr_count_chc3
    global array_emr_doc_occupancy_chc3
    global array_emr_staffnurse_occupancy_chc3
    global array_emr_bed_occupancy_chc3
    global array_emr_bed_occupancy1_chc3
    global array_emergency_refer_chc3
    global emr_q_chc3
    global emr_q_waiting_time_chc3
    global array_emr_q_waiting_time_chc3
    global array_emr_q_length_chc3
    global array_emr_q_length_of_stay_chc3
    global emr_q_los_chc3

    array_emr_count_chc3 = []
    array_emr_doc_occupancy_chc3 = []
    array_emr_staffnurse_occupancy_chc3 = []
    array_emr_bed_occupancy_chc3 = []
    array_emr_bed_occupancy1_chc3 = []
    array_emergency_refer_chc3 = []
    array_emr_q_waiting_time_chc3 = []
    array_emr_q_length_chc3 = []
    array_emr_q_length_of_stay_chc3 = []
    emr_q_los_chc3 = []

    # Delivery variables
    global delivery_iat_chc3
    global delivery_count_chc3
    global delivery_bed_chc3
    global delivery_nurse_chc3
    global ipd_nurse_chc3
    global MO_chc3
    global e_beds_chc3
    global delivery_nurse_time_chc3
    global MO_del_time_chc3
    global ipd_nurse_time_chc3
    global childbirth_count_chc3
    global childbirth_referred_chc3
    global array_childbirth_count_chc3
    global array_del_count_chc3
    global array_del_nurse_occupancy_chc3
    global array_del_bed_occupancy_chc3
    global array_childbirth_referred_chc3

    array_del_nurse_occupancy_chc3 = []
    array_del_bed_occupancy_chc3 = []
    array_del_count_chc3 = []
    global referred_chc3
    global array_referred_chc3
    array_referred_chc3 = []
    array_childbirth_referred_chc3 = []
    array_childbirth_count_chc3 = []

    # inpatient department
    global in_beds_chc3
    global ipd_q_chc3
    global ipd_MO_time_chc3
    global surgery_iat_chc3
    global inpatient_del_count_chc3
    global inpatient_count_chc3
    global array_ipd_count_chc3
    global array_ipd_staffnurse_occupancy_chc3
    global array_ipd_bed_occupancy_chc3
    global array_ipd_del_count_chc3
    global array_staffnurse_occupancy_chc3
    global emer_inpatients_chc3
    global array_emer_inpatients_chc3
    global ipd_bed_time_chc3
    global array_ipd_bed_time_chc3
    global ipd_nurse_time_chc3
    global ipd_surgery_count_chc3
    global array_ipd_surgery_count_chc3
    global array_ipd_bed_time_m_chc3
    global array_ip_waiting_time_chc3
    global array_ip_q_length_chc3
    global MO_ipd_chc3
    global ipd_MO_time_chc3
    global array_ipd_MO_occupancy_chc3
    global covid_bed_chc3

    array_ipd_surgery_count_chc3 = []
    array_ipd_staffnurse_occupancy_chc3 = []
    array_ipd_bed_occupancy_chc3 = []
    array_ipd_count_chc3 = []
    array_ipd_del_count_chc3 = []
    array_staffnurse_occupancy_chc3 = []
    array_emer_inpatients_chc3 = []
    array_ipd_bed_time_chc3 = []
    array_ipd_bed_time_m_chc3 = []
    array_ip_waiting_time_chc3 = []
    array_ip_q_length_chc3 = []
    array_ipd_MO_occupancy_chc3 = []

    # ANC
    global ANC_iat_chc3

    # surgery
    global surgery_iat_chc3
    global surgery_count_chc3
    global doc_surgeon_chc3
    global doc_ans_chc3
    global sur_time_chc3
    global ans_time_chc3
    global ot_nurse_chc3
    global ot_nurse_time_chc3
    global array_ot_doc_occupancy_chc3
    global array_ot_anasthetic_occupancy_chc3
    global array_ot_nurse_occupancy_chc3
    global array_ot_count_chc3
    array_ot_doc_occupancy_chc3 = []
    array_ot_anasthetic_occupancy_chc3 = []
    array_ot_nurse_occupancy_chc3 = []
    array_ot_count_chc3 = []

    # Xray & ecg variables
    global xray_tech_chc3
    global xray_q_chc3
    global xray_q_waiting_time_chc3
    global xray_q_length_chc3
    global array_xray_occupancy_chc3
    global array_xray_q_length_chc3
    global array_xray_q_waiting_time_chc3
    global radio_count_chc3
    global array_radio_count_chc3
    global xray_count_chc3
    global ecg_count_chc3
    global array_xray_count_chc3
    global array_ecg_count_chc3
    global array_radio_q_waiting_time_sys_chc3
    global array_radio_time_chc3
    global xray_time_chc3
    global xray_time_chc3
    global array_xray_time_chc3
    global array_ecg_time_chc3
    global xray_tech_chc3
    global ecg_q_chc3
    global ecg_q_waiting_time_chc3
    global ecg_q_length_chc3
    global array_ecg_occupancy_chc3
    global array_ecg_q_length_chc3
    global array_ecg_q_waiting_time_chc3

    array_radio_q_waiting_time_sys_chc3 = []

    array_xray_occupancy_chc3 = []
    array_xray_q_length_chc3 = []
    array_xray_q_waiting_time_chc3 = []
    array_radio_count_chc3 = []
    array_xray_count_chc3 = []
    array_ecg_count_chc3 = []
    array_radio_time_chc3 = []
    array_xray_time_chc3 = []
    array_ecg_time_chc3 = []

    array_ecg_occupancy_chc3 = []
    array_ecg_q_length_chc3 = []
    array_ecg_q_waiting_time_chc3 = []

    # covid
    global covid_q_chc3
    global home_refer_chc3
    global chc_refer_chc3
    global dh_refer_chc3
    global isolation_ward_refer_from_CHC_chc3
    global array_home_refer_chc3
    global array_chc_refer_chc3

    global array_isolation_ward_refer_from_CHC_chc3
    global d_chc3  # number of days for OPD
    global covid_count_chc3
    global covid_patient_time_chc3
    global array_covid_patient_time_chc3
    global MO_covid_time_chc3
    global array_covid_bed_waiting_time_chc3
    global array_covid_q_length_chc3
    global array_covid_bed_occupancy_chc3
    global covid_generator_chc3
    global phc2chc_count_chc3
    global array_phc2chc_count_chc3
    global array_covid_count_chc3
    global chc3_covid_bed_time
    global array_chc3_covid_bed_occ

    array_chc3_covid_bed_occ = []

    array_phc2chc_count_chc3 = []
    array_covid_count_chc3 = []
    array_covid_bed_occupancy_chc3 = []
    array_covid_bed_waiting_time_chc3 = []
    array_covid_q_length_chc3 = []

    array_chc_refer_chc3 = []
    array_home_refer_chc3 = []

    array_covid_patient_time_chc3 = []
    array_isolation_ward_refer_from_CHC_chc3 = []  # Added October 8

    # admin work
    global admin_work_chc3
    global ip_bed_cap_chc3
    global emergency_iat_chc3

    """Commented out due to network integration """

    global warmup_time

    global chc3_moderate_covid
    global chc3_severe_covid
    global chc2_moderate_covid
    global chc2_severe_covid
    global chc1_moderate_covid
    global chc1_severe_covid

    global array_chc3_moderate_covid
    global array_chc3_severe_covid
    global array_chc2_moderate_covid
    global array_chc2_severe_covid
    global array_chc1_moderate_covid
    global array_chc1_severe_covid

    array_chc1_severe_covid = []
    array_chc1_moderate_covid = []
    array_chc2_severe_covid = []
    array_chc2_moderate_covid = []
    array_chc3_severe_covid = []
    array_chc3_moderate_covid = []

    # variables and arrays for severe patients
    global d_cc_chc3
    global e_cc_chc3
    global f_cc_chc3
    global d_dh_chc3
    global e_dh_chc3
    global f_dh_chc3
    global array_d_cc_chc3
    global array_e_cc_chc3
    global array_f_cc_chc3
    global array_d_dh_chc3
    global array_e_dh_chc3
    global array_f_dh_chc3
    global t_s_chc3
    global t_d_chc3
    global t_e_chc3
    global t_f_chc3

    # variables and arrays for moderate patients

    global t_c_chc3
    global t_b_chc3
    global t_a_chc3
    global a_cc_chc3
    global b_cc_chc3
    global c_cc_chc3
    global a_dh_chc3
    global b_dh_chc3
    global c_dh_chc3
    global t_m_chc3

    global array_a_cc_chc3
    global array_b_cc_chc3
    global array_c_cc_chc3
    global array_a_dh_chc3
    global array_b_dh_chc3
    global array_c_dh_chc3

    global array_prop_a2cc_chc3_max
    global array_prop_a2dh_chc3_max
    global array_prop_a2cc_chc3_avg
    global array_prop_a2dh_chc3_avg

    global array_prop_b2cc_chc3_max
    global array_prop_b2dh_chc3_max
    global array_prop_b2cc_chc3_avg
    global array_prop_b2dh_chc3_avg

    global array_prop_c2cc_chc3_max
    global array_prop_c2dh_chc3_max
    global array_prop_c2cc_chc3_avg
    global array_prop_c2dh_chc3_avg

    global array_prop_d2cc_chc3_max
    global array_prop_d2dh_chc3_max
    global array_prop_d2cc_chc3_avg
    global array_prop_d2dh_chc3_avg

    global array_prop_e2cc_chc3_max
    global array_prop_e2dh_chc3_max
    global array_prop_e2cc_chc3_avg
    global array_prop_e2dh_chc3_avg

    global array_prop_f2cc_chc3_max
    global array_prop_f2dh_chc3_max
    global array_prop_f2cc_chc3_avg
    global array_prop_f2dh_chc3_avg

    array_d_cc_chc3 = []
    array_e_cc_chc3 = []
    array_f_cc_chc3 = []
    array_d_dh_chc3 = []
    array_e_dh_chc3 = []
    array_f_dh_chc3 = []

    array_a_cc_chc3 = []
    array_b_cc_chc3 = []
    array_c_cc_chc3 = []
    array_a_dh_chc3 = []
    array_b_dh_chc3 = []
    array_c_dh_chc3 = []

    array_prop_a2cc_chc3_max = []
    array_prop_a2dh_chc3_max = []
    array_prop_a2cc_chc3_avg = []
    array_prop_a2dh_chc3_avg = []

    array_prop_b2cc_chc3_max = []
    array_prop_b2dh_chc3_max = []
    array_prop_b2cc_chc3_avg = []
    array_prop_b2dh_chc3_avg = []

    array_prop_c2cc_chc3_max = []
    array_prop_c2dh_chc3_max = []
    array_prop_c2cc_chc3_avg = []
    array_prop_c2dh_chc3_avg = []

    array_prop_d2cc_chc3_max = []
    array_prop_d2dh_chc3_max = []
    array_prop_d2cc_chc3_avg = []
    array_prop_d2dh_chc3_avg = []

    array_prop_e2cc_chc3_max = []
    array_prop_e2dh_chc3_max = []
    array_prop_e2cc_chc3_avg = []
    array_prop_e2dh_chc3_avg = []

    array_prop_f2cc_chc3_max = []
    array_prop_f2dh_chc3_max = []
    array_prop_f2cc_chc3_avg = []
    array_prop_f2dh_chc3_avg = []

    global array_t_s_chc3
    global array_t_d_chc3
    global array_t_e_chc3
    global array_t_f_chc3
    global array_t_m_chc3
    global array_t_a_chc3
    global array_t_b_chc3
    global array_t_c_chc3

    array_t_s_chc3 = []
    array_t_d_chc3 = []
    array_t_e_chc3 = []
    array_t_f_chc3 = []
    array_t_m_chc3 = []
    array_t_a_chc3 = []
    array_t_b_chc3 = []
    array_t_c_chc3 = []

    global a_dh_chc3
    global a_cc_chc3
    global b_dh_chc3
    global b_cc_chc3
    global c_dh_chc3
    global c_cc_chc3
    global d_dh_chc3
    global d_cc_chc3
    global e_dh_chc3
    global e_cc_chc3
    global f_dh_chc3
    global f_cc_chc3

    a_dh_chc3 = []
    a_cc_chc3 = []
    b_dh_chc3 = []
    b_cc_chc3 = []
    c_dh_chc3 = []
    c_cc_chc3 = []
    d_dh_chc3 = []
    d_cc_chc3 = []
    e_dh_chc3 = []
    e_cc_chc3 = []
    f_dh_chc3 = []
    f_cc_chc3 = []

    global array_moderate_chc3
    global array_severe_chc3
    array_moderate_chc3 = []
    array_severe_chc3 = []

    # PHC1
    # defining system parameters
    global days
    global sim_time1

    # defining Salabim variables/resources
    global env
    global doc_OPD1

    global pharmacist1
    global lab_technician1
    global ipd_nurse1
    global ncd_nurse1

    # defining salabim queues

    global medicine_q1
    global lab_q1
    global pharmacy_q1
    global pharmacy_count1

    # opd medicine parameters
    global opd_iat1
    global opd_ser_time_mean1
    global opd_ser_time_sd1
    global medicine_count1
    global medicine_cons_time1
    global opd_q_waiting_time1

    global array_opd_patients1
    global array_medicine_doctor_occupancy1
    global array_medicine_doctor_occupancy212
    global array_opd_q_waiting_time1
    global array_opd_q_length1
    global array_medicine_count1
    array_opd_patients1 = []
    array_medicine_doctor_occupancy1 = []
    array_medicine_doctor_occupancy212 = []
    array_opd_q_waiting_time1 = []
    array_opd_q_length1 = []
    array_medicine_count1 = []

    # NCD nurse variables
    global ncd_count1
    global ncd_time1

    global array_ncd_count1
    global array_ncd_occupancy1
    array_ncd_count1 = []
    array_ncd_occupancy1 = []

    # pharmacist variables
    global pharmacy_time1
    global pharmacy_q_waiting_time1
    global pharmacy_q_length1
    global array_pharmacy_time1
    global array_pharmacy_count1
    global array_pharmacy_q_waiting_time1
    global array_pharmacy_q_length1
    global array_pharmacy_occupancy1
    array_pharmacy_occupancy1 = []
    array_pharmacy_q_length1 = []
    array_pharmacy_q_waiting_time1 = []
    array_pharmacy_time1 = []
    array_pharmacy_count1 = []

    # lab variables
    global lab_time1
    global lab_q_waiting_time1
    global lab_q_length1
    global lab_count1
    global array_lab_q_waiting_time1
    global array_lab_q_length1
    global array_lab_occupancy1
    global array_lab_count1
    array_lab_count1 = []
    array_lab_occupancy1 = []
    array_lab_q_length1 = []
    array_lab_q_waiting_time1 = []

    # Delivery variables
    global delivery_iat1
    global delivery_count1
    global total1
    global delivery_bed1
    global ipd_nurse1
    global ipd_nurse1
    global doc_OPD1
    global e_beds1
    global delivery_nurse_time1
    global MO_del_time1
    global ipd_nurse_time1
    global childbirth_count1
    global childbirth_referred1
    global array_childbirth_count1
    global array_del_count1
    global array_del_nurse_occupancy1
    global array_del_bed_occupancy1
    global array_childbirth_referred1

    array_del_nurse_occupancy1 = []
    array_del_bed_occupancy1 = []
    array_del_count1 = []
    global referred
    global array_referred1
    array_referred1 = []
    array_childbirth_referred1 = []
    array_childbirth_count1 = []

    # inpatient department
    global in_beds1
    global ipd_q1
    global MO_ipd_time1
    global inpatient_count1
    global array_ipd_count1
    global array_ipd_staffnurse_occupancy1
    global array_ipd_bed_occupancy1
    global array_ipd_del_count1
    global array_staffnurse_occupancy1

    global ipd_bed_time1
    global array_ipd_bed_time1
    global ipd_nurse_time1

    global array_ipd_bed_time_m1
    global array_ip_waiting_time1
    global array_ip_q_length1
    global ipd_MO_time1
    global array_ipd_MO_occupancy1
    global covid_bed1
    global phc1_doc_time
    global array_phc1_doc_time
    array_phc1_doc_time = []

    array_ipd_staffnurse_occupancy1 = []
    array_ipd_bed_occupancy1 = []
    array_ipd_count1 = []
    array_ipd_del_count1 = []
    array_staffnurse_occupancy1 = []
    array_ipd_bed_time1 = []
    array_ipd_bed_time_m1 = []
    array_ip_waiting_time1 = []
    array_ip_q_length1 = []
    array_ipd_MO_occupancy1 = []

    # ANC
    global ANC_iat1
    global IPD1_iat

    # PHC parameter not to be changed
    global d1

    # COVID
    global covid_q1
    global chc_refer1
    global covid_count1
    global dh_refer1
    global isolation_ward_refer1
    global lab_covidcount1
    global retesting_count1
    global home_refer1
    global MO_covid_time1
    global covid_patient_time1
    global fail_count1
    global home_isolation_PHC1
    global array_home_isolation_PHC1

    global array_chc_refer1
    global array_covid_count1
    global array_dh_refer1
    global array_isolation_ward_refer1
    global array_lab_covidcount1
    global array_retesting_count1

    array_lab_covidcount1 = []
    array_isolation_ward_refer1 = []
    array_retesting_count1 = []
    array_chc_refer1 = []
    array_dh_refer1 = []
    array_covid_count1 = []

    global o

    # PHC 1 parameters

    ANC_iat1 = 1440
    opd_iat1 = 4  # overall arrival rate in the hospital opd
    opd_ser_time_mean1 = 0.87  # the service time of the medicine opd (mean)
    opd_ser_time_sd1 = 0.21  # the service time of the medicine opd (sd)
    doc_cap1 = 2  # OPD medicine doctor
    ip_bed_cap1 = 6
    IPD1_iat = 2880
    delivery_iat1 = 1440

    global home_isolation_PHC1
    global home_isolation_PHC2
    global home_isolation_PHC3
    global home_isolation_PHC4
    global home_isolation_PHC5
    global home_isolation_PHC6
    global home_isolation_PHC7
    global home_isolation_PHC8
    global home_isolation_PHC9
    global home_isolation_PHC10

    global array_home_isolation_PHC1
    global array_home_isolation_PHC2
    global array_home_isolation_PHC3
    global array_home_isolation_PHC4
    global array_home_isolation_PHC5
    global array_home_isolation_PHC6
    global array_home_isolation_PHC7
    global array_home_isolation_PHC8
    global array_home_isolation_PHC9
    global array_home_isolation_PHC10

    array_home_isolation_PHC1 = []
    array_home_isolation_PHC2 = []
    array_home_isolation_PHC3 = []
    array_home_isolation_PHC4 = []
    array_home_isolation_PHC5 = []
    array_home_isolation_PHC6 = []
    array_home_isolation_PHC7 = []
    array_home_isolation_PHC8 = []
    array_home_isolation_PHC9 = []
    array_home_isolation_PHC10 = []

    # PHC 2
    # defining system parameters
    global days
    global warmup_time
    global sim_time1

    # defining Salabim variables/resources
    global env
    global doc_OPD_PHC2

    global pharmacist_PHC2
    global lab_technician_PHC2
    global ipd_nurse_PHC2
    global ncd_nurse_PHC2

    global doc_OPD_PHC2

    # defining salabim queues

    global medicine_q_PHC2
    global lab_q_PHC2
    global pharmacy_q_PHC2
    global pharmacy_count_PHC2

    # opd medicine parameters
    global opd_iat_PHC2
    global opd_ser_time_mean_PHC2
    global opd_ser_time_sd_PHC2
    global medicine_count_PHC2
    global medicine_cons_time_PHC2
    global opd_q_waiting_time_PHC2

    global array_opd_patients_PHC2
    global array_medicine_doctor_occupancy_PHC2
    global array_medicine_doctor_occupancy212_PHC2
    global array_opd_q_waiting_time_PHC2
    global array_opd_q_length_PHC2
    global array_medicine_count_PHC2
    array_opd_patients_PHC2 = []
    array_medicine_doctor_occupancy_PHC2 = []
    array_medicine_doctor_occupancy212_PHC2 = []
    array_opd_q_waiting_time_PHC2 = []
    array_opd_q_length_PHC2 = []
    array_medicine_count_PHC2 = []

    # NCD nurse variables
    global ncd_count_PHC2
    global ncd_time_PHC2

    global array_ncd_count_PHC2
    global array_ncd_occupancy_PHC2
    array_ncd_count_PHC2 = []
    array_ncd_occupancy_PHC2 = []

    # pharmacist variables
    global pharmacy_time_PHC2
    global pharmacy_q_waiting_time_PHC2
    global pharmacy_q_length_PHC2
    global array_pharmacy_time_PHC2
    global array_pharmacy_count_PHC2
    global array_pharmacy_q_waiting_time_PHC2
    global array_pharmacy_q_length_PHC2
    global array_pharmacy_occupancy_PHC2

    array_pharmacy_occupancy_PHC2 = []
    array_pharmacy_q_length_PHC2 = []
    array_pharmacy_q_waiting_time_PHC2 = []
    array_pharmacy_time_PHC2 = []
    array_pharmacy_count_PHC2 = []

    # lab variables
    global lab_time_PHC2
    global lab_q_waiting_time_PHC2
    global lab_q_length_PHC2
    global lab_count_PHC2
    global array_lab_q_waiting_time_PHC2
    global array_lab_q_length_PHC2
    global array_lab_occupancy_PHC2
    global array_lab_count_PHC2
    array_lab_count_PHC2 = []
    array_lab_occupancy_PHC2 = []
    array_lab_q_length_PHC2 = []
    array_lab_q_waiting_time_PHC2 = []

    # Delivery variables
    global delivery_iat_PHC2
    global delivery_count_PHC2
    global total_PHC2
    global delivery_bed_PHC2
    global ipd_nurse_PHC2
    global ipd_nurse_PHC2
    global doc_OPD_PHC2
    global e_beds_PHC2
    global delivery_nurse_time_PHC2
    global MO_del_time_PHC2
    global ipd_nurse_time_PHC2
    global childbirth_count_PHC2
    global childbirth_referred_PHC2
    global array_childbirth_count_PHC2
    global array_del_count_PHC2
    global array_del_nurse_occupancy_PHC2
    global array_del_bed_occupancy_PHC2
    global array_childbirth_referred_PHC2

    array_del_nurse_occupancy_PHC2 = []
    array_del_bed_occupancy_PHC2 = []
    array_del_count_PHC2 = []

    global referred_PHC2
    global array_referred2
    array_referred2 = []
    array_childbirth_referred_PHC2 = []
    array_childbirth_count_PHC2 = []

    # inpatient department
    global in_beds_PHC2
    global ipd_q_PHC2
    global MO_ipd_time_PHC2
    global inpatient_count_PHC2
    global array_ipd_count_PHC2
    global array_ipd_staffnurse_occupancy_PHC2
    global array_ipd_bed_occupancy_PHC2
    global array_ipd_del_count_PHC2
    global array_staffnurse_occupancy_PHC2

    global ipd_bed_time_PHC2
    global array_ipd_bed_time_PHC2
    global ipd_nurse_time_PHC2

    global array_ipd_bed_time_m_PHC2
    global array_ip_waiting_time_PHC2
    global array_ip_q_length_PHC2
    global ipd_MO_time_PHC2
    global array_ipd_MO_occupancy_PHC2
    global covid_bed_PHC2
    global phc1_doc_time_PHC2
    global array_phc1_doc_time_PHC2
    array_phc1_doc_time_PHC2 = []

    array_ipd_staffnurse_occupancy_PHC2 = []
    array_ipd_bed_occupancy_PHC2 = []
    array_ipd_count_PHC2 = []
    array_ipd_del_count_PHC2 = []
    array_staffnurse_occupancy_PHC2 = []
    array_ipd_bed_time_PHC2 = []
    array_ipd_bed_time_m_PHC2 = []
    array_ip_waiting_time_PHC2 = []
    array_ip_q_length_PHC2 = []
    array_ipd_MO_occupancy_PHC2 = []

    # ANC
    global ANC_iat_PHC2
    global IPD1_iat_PHC2

    # PHC parameter not to be changed
    global d1_PHC2

    # COVID
    global covid_q_PHC2
    global chc_refer_PHC2
    global covid_count_PHC2
    global dh_refer_PHC2
    global isolation_ward_refer_PHC2
    global lab_covidcount_PHC2
    global retesting_count_PHC2
    global home_refer_PHC2
    global phc2chc_count_PHC2
    global MO_covid_time_PHC2
    global covid_patient_time_PHC2
    global fail_count_PHC2

    global array_chc_refer_PHC2
    global array_covid_count_PHC2
    global array_dh_refer_PHC2
    global array_isolation_ward_refer_PHC2
    global array_lab_covidcount_PHC2
    global array_retesting_count_PHC2

    array_lab_covidcount_PHC2 = []
    array_isolation_ward_refer_PHC2 = []
    array_retesting_count_PHC2 = []
    array_chc_refer_PHC2 = []
    array_dh_refer_PHC2 = []
    array_covid_count_PHC2 = []

    # PHC 2 parameters
    ANC_iat_PHC2 = 1440
    opd_iat_PHC2 = 4  # overall arrival rate in the hospital opd
    opd_ser_time_mean_PHC2 = 0.87  # the service time of the medicine opd (mean)
    opd_ser_time_sd_PHC2 = 0.21  # the service time of the medicine opd (sd)
    doc_cap_PHC2 = 2  # OPD medicine doctor
    ip_bed_cap_PHC2 = 6
    IPD1_iat_PHC2 = 2880
    delivery_iat_PHC2 = 1440

    # PHC 3

    # defining system parameters
    global days
    global warmup_time
    global sim_time1

    # defining Salabim variables/resources
    global env
    global doc_OPD_PHC3

    global pharmacist_PHC3
    global lab_technician_PHC3
    global ipd_nurse_PHC3
    global ncd_nurse_PHC3

    global doc_OPD_PHC3
    global doc_cap_PHC3
    global ip_bed_cap_PHC3

    # defining salabim queues

    global medicine_q_PHC3
    global lab_q_PHC3
    global pharmacy_q_PHC3
    global pharmacy_count_PHC3

    # opd medicine parameters
    global opd_iat_PHC3
    global opd_ser_time_mean_PHC3
    global opd_ser_time_sd_PHC3
    global medicine_count_PHC3
    global medicine_cons_time_PHC3
    global opd_q_waiting_time_PHC3

    global array_opd_patients_PHC3
    global array_medicine_doctor_occupancy_PHC3
    global array_medicine_doctor_occupancy212_PHC3
    global array_opd_q_waiting_time_PHC3
    global array_opd_q_length_PHC3
    global array_medicine_count_PHC3
    array_opd_patients_PHC3 = []
    array_medicine_doctor_occupancy_PHC3 = []
    array_medicine_doctor_occupancy212_PHC3 = []
    array_opd_q_waiting_time_PHC3 = []
    array_opd_q_length_PHC3 = []
    array_medicine_count_PHC3 = []

    # NCD nurse variables
    global ncd_count_PHC3
    global ncd_time_PHC3

    global array_ncd_count_PHC3
    global array_ncd_occupancy_PHC3
    array_ncd_count_PHC3 = []
    array_ncd_occupancy_PHC3 = []

    # pharmacist variables
    global pharmacy_time_PHC3
    global pharmacy_q_waiting_time_PHC3
    global pharmacy_q_length_PHC3
    global array_pharmacy_time_PHC3
    global array_pharmacy_count_PHC3
    global array_pharmacy_q_waiting_time_PHC3
    global array_pharmacy_q_length_PHC3
    global array_pharmacy_occupancy_PHC3

    array_pharmacy_occupancy_PHC3 = []
    array_pharmacy_q_length_PHC3 = []
    array_pharmacy_q_waiting_time_PHC3 = []
    array_pharmacy_time_PHC3 = []
    array_pharmacy_count_PHC3 = []

    # lab variables
    global lab_time_PHC3
    global lab_q_waiting_time_PHC3
    global lab_q_length_PHC3
    global lab_count_PHC3
    global array_lab_q_waiting_time_PHC3
    global array_lab_q_length_PHC3
    global array_lab_occupancy_PHC3
    global array_lab_count_PHC3
    array_lab_count_PHC3 = []
    array_lab_occupancy_PHC3 = []
    array_lab_q_length_PHC3 = []
    array_lab_q_waiting_time_PHC3 = []

    # Delivery variables
    global delivery_iat_PHC3
    global delivery_count_PHC3
    global total_PHC3
    global delivery_bed_PHC3
    global ipd_nurse_PHC3
    global ipd_nurse_PHC3
    global doc_OPD_PHC3
    global e_beds_PHC3
    global delivery_nurse_time_PHC3
    global MO_del_time_PHC3
    global ipd_nurse_time_PHC3
    global childbirth_count_PHC3
    global childbirth_referred_PHC3
    global array_childbirth_count_PHC3
    global array_del_count_PHC3
    global array_del_nurse_occupancy_PHC3
    global array_del_bed_occupancy_PHC3
    global array_childbirth_referred_PHC3

    array_del_nurse_occupancy_PHC3 = []
    array_del_bed_occupancy_PHC3 = []
    array_del_count_PHC3 = []
    global referred_PHC3
    global array_referred3
    array_referred3 = []
    array_childbirth_referred_PHC3 = []
    array_childbirth_count_PHC3 = []

    # inpatient department
    global in_beds_PHC3
    global ipd_q_PHC3
    global MO_ipd_time_PHC3
    global inpatient_count_PHC3
    global array_ipd_count_PHC3
    global array_ipd_staffnurse_occupancy_PHC3
    global array_ipd_bed_occupancy_PHC3
    global array_ipd_del_count_PHC3
    global array_staffnurse_occupancy_PHC3

    global ipd_bed_time_PHC3
    global array_ipd_bed_time_PHC3
    global ipd_nurse_time_PHC3

    global array_ipd_bed_time_m_PHC3
    global array_ip_waiting_time_PHC3
    global array_ip_q_length_PHC3
    global ipd_MO_time_PHC3
    global array_ipd_MO_occupancy_PHC3
    global covid_bed_PHC3
    global phc1_doc_time_PHC3
    global array_phc1_doc_time_PHC3
    array_phc1_doc_time_PHC3 = []

    array_ipd_staffnurse_occupancy_PHC3 = []
    array_ipd_bed_occupancy_PHC3 = []
    array_ipd_count_PHC3 = []
    array_ipd_del_count_PHC3 = []
    array_staffnurse_occupancy_PHC3 = []
    array_ipd_bed_time_PHC2 = []
    array_ipd_bed_time_m_PHC3 = []
    array_ip_waiting_time_PHC3 = []
    array_ip_q_length_PHC3 = []
    array_ipd_MO_occupancy_PHC3 = []

    # ANC
    global ANC_iat_PHC3
    global IPD1_iat_PHC3

    # PHC parameter not to be changed
    global d1_PHC3
    global phc2chc_count_PHC3

    # COVID
    global covid_q_PHC3
    global chc_refer_PHC3
    global covid_count_PHC3
    global dh_refer_PHC3
    global isolation_ward_refer_PHC3
    global lab_covidcount_PHC3
    global retesting_count_PHC3
    global home_refer_PHC3
    global MO_covid_time_PHC3
    global covid_patient_time_PHC3
    global fail_count_PHC3

    global array_chc_refer_PHC3
    global array_covid_count_PHC3
    global array_dh_refer_PHC3
    global array_isolation_ward_refer_PHC3
    global array_lab_covidcount_PHC3
    global array_retesting_count_PHC3

    array_lab_covidcount_PHC3 = []
    array_isolation_ward_refer_PHC3 = []
    array_retesting_count_PHC3 = []
    array_chc_refer_PHC3 = []
    array_dh_refer_PHC3 = []
    array_covid_count_PHC3 = []

    runtime_1 = []
    timedifference = 0

    days = 360
    shifts = 3
    hours = 8

    ANC_iat_PHC3 = 1440
    opd_iat_PHC3 = 4  # overall arrival rate in the hospital opd
    opd_ser_time_mean_PHC3 = 0.87  # the service time of the medicine opd (mean)
    opd_ser_time_sd_PHC3 = 0.21  # the service time of the medicine opd (sd)
    doc_cap_PHC3 = 2  # OPD medicine doctor
    ip_bed_cap_PHC3 = 6
    IPD1_iat_PHC3 = 2880
    delivery_iat_PHC3 = 1440

    days1 = 0

    # PHC 4

    # defining system parameters

    global warmup_time
    global sim_time1

    # defining Salabim variables/resources

    global doc_OPD_PHC4

    global pharmacist_PHC4
    global lab_technician_PHC4
    global ipd_nurse_PHC4
    global ncd_nurse_PHC4

    global doc_OPD_PHC4
    global doc_cap_PHC4
    global ip_bed_cap_PHC4

    # defining salabim queues

    global medicine_q_PHC4
    global lab_q_PHC4
    global pharmacy_q_PHC4
    global pharmacy_count_PHC4

    # opd medicine parameters
    global opd_iat_PHC4
    global opd_ser_time_mean_PHC4
    global opd_ser_time_sd_PHC4
    global medicine_count_PHC4
    global medicine_cons_time_PHC4
    global opd_q_waiting_time_PHC4

    global array_opd_patients_PHC4
    global array_medicine_doctor_occupancy_PHC4
    global array_medicine_doctor_occupancy212_PHC4
    global array_opd_q_waiting_time_PHC4
    global array_opd_q_length_PHC4
    global array_medicine_count_PHC4
    array_opd_patients_PHC4 = []
    array_medicine_doctor_occupancy_PHC4 = []
    array_medicine_doctor_occupancy212_PHC4 = []
    array_opd_q_waiting_time_PHC4 = []
    array_opd_q_length_PHC4 = []
    array_medicine_count_PHC4 = []

    # NCD nurse variables
    global ncd_count_PHC4
    global ncd_time_PHC4

    global array_ncd_count_PHC4
    global array_ncd_occupancy_PHC4
    array_ncd_count_PHC4 = []
    array_ncd_occupancy_PHC4 = []

    # pharmacist variables
    global pharmacy_time_PHC4
    global pharmacy_q_waiting_time_PHC4
    global pharmacy_q_length_PHC4
    global array_pharmacy_time_PHC4
    global array_pharmacy_count_PHC4
    global array_pharmacy_q_waiting_time_PHC4
    global array_pharmacy_q_length_PHC4
    global array_pharmacy_occupancy_PHC4

    array_pharmacy_occupancy_PHC4 = []
    array_pharmacy_q_length_PHC4 = []
    array_pharmacy_q_waiting_time_PHC4 = []
    array_pharmacy_time_PHC4 = []
    array_pharmacy_count_PHC4 = []

    # lab variables
    global lab_time_PHC4
    global lab_q_waiting_time_PHC4
    global lab_q_length_PHC4
    global lab_count_PHC4
    global array_lab_q_waiting_time_PHC4
    global array_lab_q_length_PHC4
    global array_lab_occupancy_PHC4
    global array_lab_count_PHC4
    array_lab_count_PHC4 = []
    array_lab_occupancy_PHC4 = []
    array_lab_q_length_PHC4 = []
    array_lab_q_waiting_time_PHC4 = []

    global total_PHC4
    global ipd_nurse_PHC4
    global ipd_nurse_PHC4
    global doc_OPD_PHC4
    global e_beds_PHC4
    global ipd_nurse_time_PHC4

    global array_del_nurse_occupancy_PHC4

    array_del_nurse_occupancy_PHC4 = []

    # inpatient department
    global in_beds_PHC4
    global ipd_q_PHC4
    global MO_ipd_time_PHC4
    global inpatient_count_PHC4
    global array_ipd_count_PHC4
    global array_ipd_staffnurse_occupancy_PHC4
    global array_ipd_bed_occupancy_PHC4
    global array_ipd_del_count_PHC4
    global array_staffnurse_occupancy_PHC4

    global ipd_bed_time_PHC4
    global array_ipd_bed_time_PHC4
    global ipd_nurse_time_PHC4

    global array_ipd_bed_time_m_PHC4
    global array_ip_waiting_time_PHC4
    global array_ip_q_length_PHC4
    global ipd_MO_time_PHC4
    global array_ipd_MO_occupancy_PHC4
    global covid_bed_PHC4
    global phc1_doc_time_PHC4
    global array_phc1_doc_time_PHC4
    array_phc1_doc_time_PHC4 = []

    array_ipd_staffnurse_occupancy_PHC4 = []
    array_ipd_bed_occupancy_PHC4 = []
    array_ipd_count_PHC4 = []
    array_ipd_del_count_PHC4 = []
    array_staffnurse_occupancy_PHC4 = []
    array_ipd_bed_time_PHC4 = []
    array_ipd_bed_time_m_PHC4 = []
    array_ip_waiting_time_PHC4 = []
    array_ip_q_length_PHC4 = []
    array_ipd_MO_occupancy_PHC4 = []

    global IPD1_iat_PHC4

    # PHC parameter not to be changed
    global d1_PHC4

    # COVID
    global covid_q_PHC4
    global chc_refer_PHC4
    global covid_count_PHC4
    global dh_refer_PHC4
    global isolation_ward_refer_PHC4
    global phc2chc_count_PHC4
    global lab_covidcount_PHC4
    global retesting_count_PHC4
    global home_refer_PHC4
    global MO_covid_time_PHC4
    global covid_patient_time_PHC4
    global fail_count_PHC4

    global array_chc_refer_PHC4
    global array_covid_count_PHC4
    global array_dh_refer_PHC4
    global array_isolation_ward_refer_PHC4
    global array_lab_covidcount_PHC4
    global array_retesting_count_PHC4

    array_lab_covidcount_PHC4 = []
    array_isolation_ward_refer_PHC4 = []
    array_retesting_count_PHC4 = []
    array_chc_refer_PHC4 = []
    array_dh_refer_PHC4 = []
    array_covid_count_PHC4 = []

    opd_iat_PHC4 = 6  # overall arrival rate in the hospital opd
    opd_ser_time_mean_PHC4 = 0.87  # the service time of the medicine opd (mean)
    opd_ser_time_sd_PHC4 = 0.21  # the service time of the medicine opd (sd)
    doc_cap_PHC4 = 1  # OPD medicine doctor
    ip_bed_cap_PHC4 = 6
    IPD1_iat_PHC4 = 2880

    # PHC 5

    global sim_time1

    # defining Salabim variables/resources
    global env
    global doc_OPD_PHC5

    global pharmacist_PHC5
    global lab_technician_PHC5
    global ipd_nurse_PHC5
    global ncd_nurse_PHC5

    global doc_OPD_PHC5
    global doc_cap_PHC5
    global ip_bed_cap_PHC5

    # defining salabim queues

    global medicine_q_PHC5
    global lab_q_PHC5
    global pharmacy_q_PHC5
    global pharmacy_count_PHC5

    # opd medicine parameters
    global opd_iat_PHC5
    global opd_ser_time_mean_PHC5
    global opd_ser_time_sd_PHC5
    global medicine_count_PHC5
    global medicine_cons_time_PHC5
    global opd_q_waiting_time_PHC5

    global array_opd_patients_PHC5
    global array_medicine_doctor_occupancy_PHC5
    global array_medicine_doctor_occupancy212_PHC5
    global array_opd_q_waiting_time_PHC5
    global array_opd_q_length_PHC5
    global array_medicine_count_PHC5
    array_opd_patients_PHC5 = []
    array_medicine_doctor_occupancy_PHC5 = []
    array_medicine_doctor_occupancy212_PHC5 = []
    array_opd_q_waiting_time_PHC5 = []
    array_opd_q_length_PHC5 = []
    array_medicine_count_PHC5 = []

    # NCD nurse variables
    global ncd_count_PHC5
    global ncd_time_PHC5

    global array_ncd_count_PHC5
    global array_ncd_occupancy_PHC5
    array_ncd_count_PHC5 = []
    array_ncd_occupancy_PHC5 = []

    # pharmacist variables
    global pharmacy_time_PHC5
    global pharmacy_q_waiting_time_PHC5
    global pharmacy_q_length_PHC5
    global array_pharmacy_time_PHC5
    global array_pharmacy_count_PHC5
    global array_pharmacy_q_waiting_time_PHC5
    global array_pharmacy_q_length_PHC5
    global array_pharmacy_occupancy_PHC5

    array_pharmacy_occupancy_PHC5 = []
    array_pharmacy_q_length_PHC5 = []
    array_pharmacy_q_waiting_time_PHC5 = []
    array_pharmacy_time_PHC5 = []
    array_pharmacy_count_PHC5 = []

    # lab variables
    global lab_time_PHC5
    global lab_q_waiting_time_PHC5
    global lab_q_length_PHC5
    global lab_count_PHC5
    global array_lab_q_waiting_time_PHC5
    global array_lab_q_length_PHC5
    global array_lab_occupancy_PHC5
    global array_lab_count_PHC5
    array_lab_count_PHC5 = []
    array_lab_occupancy_PHC5 = []
    array_lab_q_length_PHC5 = []
    array_lab_q_waiting_time_PHC5 = []

    # Delivery variables

    global total_PHC5

    global ipd_nurse_PHC5
    global ipd_nurse_PHC5
    global doc_OPD_PHC5
    global e_beds_PHC5

    global MO_del_time_PHC5
    global ipd_nurse_time_PHC5

    global array_del_nurse_occupancy_PHC5

    array_del_nurse_occupancy_PHC5 = []

    # inpatient department
    global in_beds_PHC5
    global ipd_q_PHC5
    global MO_ipd_time_PHC5
    global inpatient_count_PHC5
    global array_ipd_count_PHC5
    global array_ipd_staffnurse_occupancy_PHC5
    global array_ipd_bed_occupancy_PHC5
    global array_ipd_del_count_PHC5
    global array_staffnurse_occupancy_PHC5

    global ipd_bed_time_PHC5
    global array_ipd_bed_time_PHC5
    global ipd_nurse_time_PHC5

    global array_ipd_bed_time_m_PHC5
    global array_ip_waiting_time_PHC5
    global array_ip_q_length_PHC5
    global ipd_MO_time_PHC5
    global array_ipd_MO_occupancy_PHC5
    global covid_bed_PHC5
    global phc1_doc_time_PHC5
    global array_phc1_doc_time_PHC5
    array_phc1_doc_time_PHC5 = []

    array_ipd_staffnurse_occupancy_PHC5 = []
    array_ipd_bed_occupancy_PHC5 = []
    array_ipd_count_PHC5 = []
    array_ipd_del_count_PHC5 = []
    array_staffnurse_occupancy_PHC5 = []
    array_ipd_bed_time_PHC5 = []
    array_ipd_bed_time_m_PHC5 = []
    array_ip_waiting_time_PHC5 = []
    array_ip_q_length_PHC5 = []
    array_ipd_MO_occupancy_PHC5 = []

    # ANC

    global IPD1_iat_PHC5

    # PHC parameter not to be changed
    global d1_PHC5

    # COVID
    global covid_q_PHC5
    global chc_refer_PHC5
    global covid_count_PHC5
    global dh_refer_PHC5
    global phc2chc_count_PHC5
    global isolation_ward_refer_PHC5
    global lab_covidcount_PHC5
    global retesting_count_PHC5
    global home_refer_PHC5
    global MO_covid_time_PHC5
    global covid_patient_time_PHC5
    global fail_count_PHC5

    global array_chc_refer_PHC5
    global array_covid_count_PHC5
    global array_dh_refer_PHC5
    global array_isolation_ward_refer_PHC5
    global array_lab_covidcount_PHC5
    global array_retesting_count_PHC5

    array_lab_covidcount_PHC5 = []
    array_isolation_ward_refer_PHC5 = []
    array_retesting_count_PHC5 = []
    array_chc_refer_PHC5 = []
    array_dh_refer_PHC5 = []
    array_covid_count_PHC5 = []

    days = 360

    opd_iat_PHC5 = 9  # overall arrival rate in the hospital opd
    opd_ser_time_mean_PHC5 = 0.87  # the service time of the medicine opd (mean)
    opd_ser_time_sd_PHC5 = 0.21  # the service time of the medicine opd (sd)
    doc_cap_PHC5 = 1  # OPD medicine doctor
    ip_bed_cap_PHC5 = 6
    IPD1_iat_PHC5 = 2880

    """Commented out due to network integration """


    global sim_time1

    # defining Salabim variables/resources
    global env
    global doc_OPD_PHC6

    global pharmacist_PHC6
    global lab_technician_PHC6
    global ipd_nurse_PHC6
    global ncd_nurse_PHC6

    global doc_OPD_PHC6
    global doc_cap_PHC6
    global ip_bed_cap_PHC6

    # defining salabim queues

    global medicine_q_PHC6
    global lab_q_PHC6
    global pharmacy_q_PHC6
    global pharmacy_count_PHC6

    # opd medicine parameters
    global opd_iat_PHC6
    global opd_ser_time_mean_PHC6
    global opd_ser_time_sd_PHC6
    global medicine_count_PHC6
    global medicine_cons_time_PHC6
    global opd_q_waiting_time_PHC6

    global array_opd_patients_PHC6
    global array_medicine_doctor_occupancy_PHC6
    global array_medicine_doctor_occupancy212_PHC6
    global array_opd_q_waiting_time_PHC6
    global array_opd_q_length_PHC6
    global array_medicine_count_PHC6
    array_opd_patients_PHC6 = []
    array_medicine_doctor_occupancy_PHC6 = []
    array_medicine_doctor_occupancy212_PHC6 = []
    array_opd_q_waiting_time_PHC6 = []
    array_opd_q_length_PHC6 = []
    array_medicine_count_PHC6 = []

    # NCD nurse variables
    global ncd_count_PHC6
    global ncd_time_PHC6

    global array_ncd_count_PHC6
    global array_ncd_occupancy_PHC6
    array_ncd_count_PHC6 = []
    array_ncd_occupancy_PHC6 = []

    # pharmacist variables
    global pharmacy_time_PHC6
    global pharmacy_q_waiting_time_PHC6
    global pharmacy_q_length_PHC6
    global array_pharmacy_time_PHC6
    global array_pharmacy_count_PHC6
    global array_pharmacy_q_waiting_time_PHC6
    global array_pharmacy_q_length_PHC6
    global array_pharmacy_occupancy_PHC6

    array_pharmacy_occupancy_PHC6 = []
    array_pharmacy_q_length_PHC6 = []
    array_pharmacy_q_waiting_time_PHC6 = []
    array_pharmacy_time_PHC6 = []
    array_pharmacy_count_PHC6 = []

    # lab variables
    global lab_time_PHC6
    global lab_q_waiting_time_PHC6
    global lab_q_length_PHC6
    global lab_count_PHC6
    global array_lab_q_waiting_time_PHC6
    global array_lab_q_length_PHC6
    global array_lab_occupancy_PHC6
    global array_lab_count_PHC6
    array_lab_count_PHC6 = []
    array_lab_occupancy_PHC6 = []
    array_lab_q_length_PHC6 = []
    array_lab_q_waiting_time_PHC6 = []

    # Delivery variables
    global delivery_iat_PHC6
    global delivery_count_PHC6
    global total_PHC6
    global delivery_bed_PHC6
    global ipd_nurse_PHC6
    global ipd_nurse_PHC6
    global doc_OPD_PHC6
    global e_beds_PHC6
    global delivery_nurse_time_PHC6
    global MO_del_time_PHC6
    global ipd_nurse_time_PHC6
    global childbirth_count_PHC6
    global childbirth_referred_PHC6
    global array_childbirth_count_PHC6
    global array_del_count_PHC6
    global array_del_nurse_occupancy_PHC6
    global array_del_bed_occupancy_PHC6
    global array_childbirth_referred_PHC6

    array_del_nurse_occupancy_PHC6 = []
    array_del_bed_occupancy_PHC6 = []
    array_del_count_PHC6 = []
    global referred_PHC6
    global array_referred6
    array_referred6 = []
    array_childbirth_referred_PHC6 = []
    array_childbirth_count_PHC6 = []

    # inpatient department
    global in_beds_PHC6
    global ipd_q_PHC6
    global MO_ipd_time_PHC6
    global inpatient_count_PHC6
    global array_ipd_count_PHC6
    global array_ipd_staffnurse_occupancy_PHC6
    global array_ipd_bed_occupancy_PHC6
    global array_ipd_del_count_PHC6
    global array_staffnurse_occupancy_PHC6

    global ipd_bed_time_PHC6
    global array_ipd_bed_time_PHC6
    global ipd_nurse_time_PHC6

    global array_ipd_bed_time_m_PHC6
    global array_ip_waiting_time_PHC6
    global array_ip_q_length_PHC6
    global ipd_MO_time_PHC6
    global array_ipd_MO_occupancy_PHC6
    global covid_bed_PHC6
    global phc1_doc_time_PHC6
    global array_phc1_doc_time_PHC6
    array_phc1_doc_time_PHC6 = []

    array_ipd_staffnurse_occupancy_PHC6 = []
    array_ipd_bed_occupancy_PHC6 = []
    array_ipd_count_PHC6 = []
    array_ipd_del_count_PHC6 = []
    array_staffnurse_occupancy_PHC6 = []
    array_ipd_bed_time_PHC6 = []
    array_ipd_bed_time_m_PHC6 = []
    array_ip_waiting_time_PHC6 = []
    array_ip_q_length_PHC6 = []
    array_ipd_MO_occupancy_PHC6 = []

    # ANC
    global ANC_iat_PHC6
    global IPD1_iat_PHC6

    # PHC parameter not to be changed
    global d1_PHC6

    # COVID
    global covid_q_PHC6
    global chc_refer_PHC6
    global covid_count_PHC6
    global dh_refer_PHC6
    global phc2chc_count_PHC6
    global isolation_ward_refer_PHC6
    global lab_covidcount_PHC6
    global retesting_count_PHC6
    global home_refer_PHC6
    global MO_covid_time_PHC6
    global covid_patient_time_PHC6
    global fail_count_PHC6

    global array_chc_refer_PHC6
    global array_covid_count_PHC6
    global array_dh_refer_PHC6
    global array_isolation_ward_refer_PHC6
    global array_lab_covidcount_PHC6
    global array_retesting_count_PHC6

    array_lab_covidcount_PHC6 = []
    array_isolation_ward_refer_PHC6 = []
    array_retesting_count_PHC6 = []
    array_chc_refer_PHC6 = []
    array_dh_refer_PHC6 = []
    array_covid_count_PHC6 = []

    days = 360
    ANC_iat_PHC6 = 1440
    opd_iat_PHC6 = 4  # overall arrival rate in the hospital opd
    opd_ser_time_mean_PHC6 = 0.87  # the service time of the medicine opd (mean)
    opd_ser_time_sd_PHC6 = 0.21  # the service time of the medicine opd (sd)
    doc_cap_PHC6 = 2  # OPD medicine doctor
    ip_bed_cap_PHC6 = 6
    IPD1_iat_PHC6 = 2880
    delivery_iat_PHC6 = 1440

    global sim_time1

    # defining Salabim variables/resources
    global env
    global doc_OPD_PHC7

    global pharmacist_PHC7
    global lab_technician_PHC7
    global ipd_nurse_PHC7
    global ncd_nurse_PHC7

    global doc_OPD_PHC7
    global doc_cap_PHC7
    global ip_bed_cap_PHC7

    # defining salabim queues

    global medicine_q_PHC7
    global lab_q_PHC7
    global pharmacy_q_PHC7
    global pharmacy_count_PHC7

    # opd medicine parameters
    global opd_iat_PHC7
    global opd_ser_time_mean_PHC7
    global opd_ser_time_sd_PHC7
    global medicine_count_PHC7
    global medicine_cons_time_PHC7
    global opd_q_waiting_time_PHC7

    global array_opd_patients_PHC7
    global array_medicine_doctor_occupancy_PHC7
    global array_medicine_doctor_occupancy212_PHC7
    global array_opd_q_waiting_time_PHC7
    global array_opd_q_length_PHC7
    global array_medicine_count_PHC7
    array_opd_patients_PHC7 = []
    array_medicine_doctor_occupancy_PHC7 = []
    array_medicine_doctor_occupancy212_PHC7 = []
    array_opd_q_waiting_time_PHC7 = []
    array_opd_q_length_PHC7 = []
    array_medicine_count_PHC7 = []

    # NCD nurse variables
    global ncd_count_PHC7
    global ncd_time_PHC7

    global array_ncd_count_PHC7
    global array_ncd_occupancy_PHC7
    array_ncd_count_PHC7 = []
    array_ncd_occupancy_PHC7 = []

    # pharmacist variables
    global pharmacy_time_PHC7
    global pharmacy_q_waiting_time_PHC7
    global pharmacy_q_length_PHC7
    global array_pharmacy_time_PHC7
    global array_pharmacy_count_PHC7
    global array_pharmacy_q_waiting_time_PHC7
    global array_pharmacy_q_length_PHC7
    global array_pharmacy_occupancy_PHC7

    array_pharmacy_occupancy_PHC7 = []
    array_pharmacy_q_length_PHC7 = []
    array_pharmacy_q_waiting_time_PHC7 = []
    array_pharmacy_time_PHC7 = []
    array_pharmacy_count_PHC7 = []

    # lab variables
    global lab_time_PHC7
    global lab_q_waiting_time_PHC7
    global lab_q_length_PHC7
    global lab_count_PHC7
    global array_lab_q_waiting_time_PHC7
    global array_lab_q_length_PHC7
    global array_lab_occupancy_PHC7
    global array_lab_count_PHC7
    array_lab_count_PHC7 = []
    array_lab_occupancy_PHC7 = []
    array_lab_q_length_PHC7 = []
    array_lab_q_waiting_time_PHC7 = []

    global total_PHC7
    global ipd_nurse_PHC7
    global ipd_nurse_PHC7
    global doc_OPD_PHC7
    global e_beds_PHC7
    global ipd_nurse_time_PHC7
    global array_del_nurse_occupancy_PHC7

    array_del_nurse_occupancy_PHC7 = []

    # inpatient department
    global in_beds_PHC7
    global ipd_q_PHC7
    global MO_ipd_time_PHC7
    global inpatient_count_PHC7
    global array_ipd_count_PHC7
    global array_ipd_staffnurse_occupancy_PHC7
    global array_ipd_bed_occupancy_PHC7
    global array_ipd_del_count_PHC7
    global array_staffnurse_occupancy_PHC7

    global ipd_bed_time_PHC7
    global array_ipd_bed_time_PHC7
    global ipd_nurse_time_PHC7

    global array_ipd_bed_time_m_PHC7
    global array_ip_waiting_time_PHC7
    global array_ip_q_length_PHC7
    global ipd_MO_time_PHC7
    global array_ipd_MO_occupancy_PHC7
    global covid_bed_PHC7
    global phc1_doc_time_PHC7
    global array_phc1_doc_time_PHC7
    array_phc1_doc_time_PHC7 = []

    array_ipd_staffnurse_occupancy_PHC7 = []
    array_ipd_bed_occupancy_PHC7 = []
    array_ipd_count_PHC7 = []
    array_ipd_del_count_PHC7 = []
    array_staffnurse_occupancy_PHC7 = []
    array_ipd_bed_time_PHC7 = []
    array_ipd_bed_time_m_PHC7 = []
    array_ip_waiting_time_PHC7 = []
    array_ip_q_length_PHC7 = []
    array_ipd_MO_occupancy_PHC7 = []

    global IPD1_iat_PHC7

    # PHC parameter not to be changed
    global d1_PHC7

    # COVID
    global covid_q_PHC7
    global chc_refer_PHC7
    global covid_count_PHC7
    global dh_refer_PHC7
    global isolation_ward_refer_PHC7
    global phc2chc_count_PHC7
    global lab_covidcount_PHC7
    global retesting_count_PHC7
    global home_refer_PHC7
    global MO_covid_time_PHC7
    global covid_patient_time_PHC7
    global fail_count_PHC7
    global lab_covidcount_PHC7

    global array_chc_refer_PHC7
    global array_covid_count_PHC7
    global array_dh_refer_PHC7
    global array_isolation_ward_refer_PHC7
    global array_lab_covidcount_PHC7
    global array_retesting_count_PHC7

    array_lab_covidcount_PHC7 = []
    array_isolation_ward_refer_PHC7 = []
    array_retesting_count_PHC7 = []
    array_chc_refer_PHC7 = []
    array_dh_refer_PHC7 = []
    array_covid_count_PHC7 = []

    opd_iat_PHC7 = 9  # overall arrival rate in the hospital opd
    opd_ser_time_mean_PHC7 = 0.87  # the service time of the medicine opd (mean)
    opd_ser_time_sd_PHC7 = 0.21  # the service time of the medicine opd (sd)
    doc_cap_PHC7 = 1  # OPD medicine doctor
    ip_bed_cap_PHC7 = 6
    IPD1_iat_PHC7 = 2880

    global sim_time1

    # defining Salabim variables/resources
    global env
    global doc_OPD_PHC8

    global pharmacist_PHC8
    global lab_technician_PHC8
    global ipd_nurse_PHC8
    global ncd_nurse_PHC8

    global doc_OPD_PHC8
    global doc_cap_PHC8
    global ip_bed_cap_PHC8

    # defining salabim queues

    global medicine_q_PHC8
    global lab_q_PHC8
    global pharmacy_q_PHC8
    global pharmacy_count_PHC8

    # opd medicine parameters
    global opd_iat_PHC8
    global opd_ser_time_mean_PHC8
    global opd_ser_time_sd_PHC8
    global medicine_count_PHC8
    global medicine_cons_time_PHC8
    global opd_q_waiting_time_PHC8

    global array_opd_patients_PHC8
    global array_medicine_doctor_occupancy_PHC8
    global array_medicine_doctor_occupancy212_PHC8
    global array_opd_q_waiting_time_PHC8
    global array_opd_q_length_PHC8
    global array_medicine_count_PHC8
    array_opd_patients_PHC8 = []
    array_medicine_doctor_occupancy_PHC8 = []
    array_medicine_doctor_occupancy212_PHC8 = []
    array_opd_q_waiting_time_PHC8 = []
    array_opd_q_length_PHC8 = []
    array_medicine_count_PHC8 = []

    # NCD nurse variables
    global ncd_count_PHC8
    global ncd_time_PHC8

    global array_ncd_count_PHC8
    global array_ncd_occupancy_PHC8
    array_ncd_count_PHC8 = []
    array_ncd_occupancy_PHC8 = []

    # pharmacist variables
    global pharmacy_time_PHC8
    global pharmacy_q_waiting_time_PHC8
    global pharmacy_q_length_PHC8
    global array_pharmacy_time_PHC8
    global array_pharmacy_count_PHC8
    global array_pharmacy_q_waiting_time_PHC8
    global array_pharmacy_q_length_PHC8
    global array_pharmacy_occupancy_PHC8

    array_pharmacy_occupancy_PHC8 = []
    array_pharmacy_q_length_PHC8 = []
    array_pharmacy_q_waiting_time_PHC8 = []
    array_pharmacy_time_PHC8 = []
    array_pharmacy_count_PHC8 = []

    # lab variables
    global lab_time_PHC8
    global lab_q_waiting_time_PHC8
    global lab_q_length_PHC8
    global lab_count_PHC8
    global array_lab_q_waiting_time_PHC8
    global array_lab_q_length_PHC8
    global array_lab_occupancy_PHC8
    global array_lab_count_PHC8
    array_lab_count_PHC8 = []
    array_lab_occupancy_PHC8 = []
    array_lab_q_length_PHC8 = []
    array_lab_q_waiting_time_PHC8 = []

    # Delivery variables
    global delivery_iat_PHC8
    global delivery_count_PHC8
    global total_PHC8
    global delivery_bed_PHC8
    global ipd_nurse_PHC8
    global ipd_nurse_PHC8
    global doc_OPD_PHC8
    global e_beds_PHC8
    global delivery_nurse_time_PHC8
    global MO_del_time_PHC8
    global ipd_nurse_time_PHC8
    global childbirth_count_PHC8
    global childbirth_referred_PHC8
    global array_childbirth_count_PHC8
    global array_del_count_PHC8
    global array_del_nurse_occupancy_PHC8
    global array_del_bed_occupancy_PHC8
    global array_childbirth_referred_PHC8

    array_del_nurse_occupancy_PHC8 = []
    array_del_bed_occupancy_PHC8 = []
    array_del_count_PHC8 = []
    global referred_PHC8
    global array_referred8
    array_referred8 = []
    array_childbirth_referred_PHC8 = []
    array_childbirth_count_PHC8 = []

    # inpatient department
    global in_beds_PHC8
    global ipd_q_PHC8
    global MO_ipd_time_PHC8
    global inpatient_count_PHC8
    global array_ipd_count_PHC8
    global array_ipd_staffnurse_occupancy_PHC8
    global array_ipd_bed_occupancy_PHC8
    global array_ipd_del_count_PHC8
    global array_staffnurse_occupancy_PHC8

    global ipd_bed_time_PHC8
    global array_ipd_bed_time_PHC8
    global ipd_nurse_time_PHC8

    global array_ipd_bed_time_m_PHC8
    global array_ip_waiting_time_PHC8
    global array_ip_q_length_PHC8
    global ipd_MO_time_PHC8
    global array_ipd_MO_occupancy_PHC8
    global covid_bed_PHC8
    global phc1_doc_time_PHC8
    global array_phc1_doc_time_PHC8
    array_phc1_doc_time_PHC8 = []

    array_ipd_staffnurse_occupancy_PHC8 = []
    array_ipd_bed_occupancy_PHC8 = []
    array_ipd_count_PHC8 = []
    array_ipd_del_count_PHC8 = []
    array_staffnurse_occupancy_PHC8 = []
    array_ipd_bed_time_PHC8 = []
    array_ipd_bed_time_m_PHC8 = []
    array_ip_waiting_time_PHC8 = []
    array_ip_q_length_PHC8 = []
    array_ipd_MO_occupancy_PHC8 = []

    # ANC
    global ANC_iat_PHC8
    global IPD1_iat_PHC8

    # PHC parameter not to be changed
    global d1_PHC8

    # COVID
    global covid_q_PHC8
    global chc_refer_PHC8
    global covid_count_PHC8
    global dh_refer_PHC8
    global phc2chc_count_PHC8
    global isolation_ward_refer_PHC8
    global lab_covidcount_PHC8
    global retesting_count_PHC8
    global home_refer_PHC8
    global MO_covid_time_PHC8
    global covid_patient_time_PHC8
    global fail_count_PHC8

    global array_chc_refer_PHC8
    global array_covid_count_PHC8
    global array_dh_refer_PHC8
    global array_isolation_ward_refer_PHC8
    global array_lab_covidcount_PHC8
    global array_retesting_count_PHC8

    array_lab_covidcount_PHC8 = []
    array_isolation_ward_refer_PHC8 = []
    array_retesting_count_PHC8 = []
    array_chc_refer_PHC8 = []
    array_dh_refer_PHC8 = []
    array_covid_count_PHC8 = []

    days = 360

    ANC_iat_PHC8 = 2880
    opd_iat_PHC8 = 6  # overall arrival rate in the hospital opd
    opd_ser_time_mean_PHC8 = 0.87  # the service time of the medicine opd (mean)
    opd_ser_time_sd_PHC8 = 0.21  # the service time of the medicine opd (sd)
    doc_cap_PHC8 = 1  # OPD medicine doctor
    ip_bed_cap_PHC8 = 6
    IPD1_iat_PHC8 = 2880
    delivery_iat_PHC8 = 2880

    global sim_time1

    # defining Salabim variables/resources
    global env
    global doc_OPD_PHC9

    global pharmacist_PHC9
    global lab_technician_PHC9
    global ipd_nurse_PHC9
    global ncd_nurse_PHC9

    global doc_OPD_PHC9
    global doc_cap_PHC9
    global ip_bed_cap_PHC9

    # defining salabim queues

    global medicine_q_PHC9
    global lab_q_PHC9
    global pharmacy_q_PHC9
    global pharmacy_count_PHC9

    # opd medicine parameters
    global opd_iat_PHC9
    global opd_ser_time_mean_PHC9
    global opd_ser_time_sd_PHC9
    global medicine_count_PHC9
    global medicine_cons_time_PHC9
    global opd_q_waiting_time_PHC9

    global array_opd_patients_PHC9
    global array_medicine_doctor_occupancy_PHC9
    global array_medicine_doctor_occupancy212_PHC9
    global array_opd_q_waiting_time_PHC9
    global array_opd_q_length_PHC9
    global array_medicine_count_PHC9
    array_opd_patients_PHC9 = []
    array_medicine_doctor_occupancy_PHC9 = []
    array_medicine_doctor_occupancy212_PHC9 = []
    array_opd_q_waiting_time_PHC9 = []
    array_opd_q_length_PHC9 = []
    array_medicine_count_PHC9 = []

    # NCD nurse variables
    global ncd_count_PHC9
    global ncd_time_PHC9

    global array_ncd_count_PHC9
    global array_ncd_occupancy_PHC9
    array_ncd_count_PHC9 = []
    array_ncd_occupancy_PHC9 = []

    # pharmacist variables
    global pharmacy_time_PHC9
    global pharmacy_q_waiting_time_PHC9
    global pharmacy_q_length_PHC9
    global array_pharmacy_time_PHC9
    global array_pharmacy_count_PHC9
    global array_pharmacy_q_waiting_time_PHC9
    global array_pharmacy_q_length_PHC9
    global array_pharmacy_occupancy_PHC9

    array_pharmacy_occupancy_PHC9 = []
    array_pharmacy_q_length_PHC9 = []
    array_pharmacy_q_waiting_time_PHC9 = []
    array_pharmacy_time_PHC9 = []
    array_pharmacy_count_PHC9 = []

    # lab variables
    global lab_time_PHC9
    global lab_q_waiting_time_PHC9
    global lab_q_length_PHC9
    global lab_count_PHC9
    global array_lab_q_waiting_time_PHC9
    global array_lab_q_length_PHC9
    global array_lab_occupancy_PHC9
    global array_lab_count_PHC9
    array_lab_count_PHC9 = []
    array_lab_occupancy_PHC9 = []
    array_lab_q_length_PHC9 = []
    array_lab_q_waiting_time_PHC9 = []

    # Delivery variables
    global delivery_iat_PHC9
    global delivery_count_PHC9
    global total_PHC9
    global delivery_bed_PHC9
    global ipd_nurse_PHC9
    global ipd_nurse_PHC9
    global doc_OPD_PHC9
    global e_beds_PHC9
    global delivery_nurse_time_PHC9
    global MO_del_time_PHC9
    global ipd_nurse_time_PHC9
    global childbirth_count_PHC9
    global childbirth_referred_PHC9
    global array_childbirth_count_PHC9
    global array_del_count_PHC9
    global array_del_nurse_occupancy_PHC9
    global array_del_bed_occupancy_PHC9
    global array_childbirth_referred_PHC9

    array_del_nurse_occupancy_PHC9 = []
    array_del_bed_occupancy_PHC9 = []
    array_del_count_PHC9 = []
    global referred_PHC9
    global array_referred9
    array_referred9 = []
    array_childbirth_referred_PHC9 = []
    array_childbirth_count_PHC9 = []

    # inpatient department
    global in_beds_PHC9
    global ipd_q_PHC9
    global MO_ipd_time_PHC9
    global inpatient_count_PHC9
    global array_ipd_count_PHC9
    global array_ipd_staffnurse_occupancy_PHC9
    global array_ipd_bed_occupancy_PHC9
    global array_ipd_del_count_PHC9
    global array_staffnurse_occupancy_PHC9

    global ipd_bed_time_PHC9
    global array_ipd_bed_time_PHC9
    global ipd_nurse_time_PHC9

    global array_ipd_bed_time_m_PHC9
    global array_ip_waiting_time_PHC9
    global array_ip_q_length_PHC9
    global ipd_MO_time_PHC9
    global array_ipd_MO_occupancy_PHC9
    global covid_bed_PHC9
    global phc1_doc_time_PHC9
    global array_phc1_doc_time_PHC9
    array_phc1_doc_time_PHC9 = []

    array_ipd_staffnurse_occupancy_PHC9 = []
    array_ipd_bed_occupancy_PHC9 = []
    array_ipd_count_PHC9 = []
    array_ipd_del_count_PHC9 = []
    array_staffnurse_occupancy_PHC9 = []
    array_ipd_bed_time_PHC9 = []
    array_ipd_bed_time_m_PHC9 = []
    array_ip_waiting_time_PHC9 = []
    array_ip_q_length_PHC9 = []
    array_ipd_MO_occupancy_PHC9 = []

    # ANC
    global ANC_iat_PHC9
    global IPD1_iat_PHC9

    # PHC parameter not to be changed
    global d1_PHC9

    # COVID
    global covid_q_PHC9
    global chc_refer_PHC9
    global covid_count_PHC9
    global dh_refer_PHC9
    global phc2chc_count_PHC9
    global isolation_ward_refer_PHC9
    global lab_covidcount_PHC9
    global retesting_count_PHC9
    global home_refer_PHC9
    global MO_covid_time_PHC9
    global covid_patient_time_PHC9
    global fail_count_PHC9

    global array_chc_refer_PHC9
    global array_covid_count_PHC9
    global array_dh_refer_PHC9
    global array_isolation_ward_refer_PHC9
    global array_lab_covidcount_PHC9
    global array_retesting_count_PHC9

    array_lab_covidcount_PHC9 = []
    array_isolation_ward_refer_PHC9 = []
    array_retesting_count_PHC9 = []
    array_chc_refer_PHC9 = []
    array_dh_refer_PHC9 = []
    array_covid_count_PHC9 = []

    days = 360

    ANC_iat_PHC9 = 1440
    opd_iat_PHC9 = 4  # overall arrival rate in the hospital opd
    opd_ser_time_mean_PHC9 = 0.87  # the service time of the medicine opd (mean)
    opd_ser_time_sd_PHC9 = 0.21  # the service time of the medicine opd (sd)
    doc_cap_PHC9 = 2  # OPD medicine doctor
    ip_bed_cap_PHC9 = 6
    IPD1_iat_PHC9 = 2880
    delivery_iat_PHC9 = 1440

    global sim_time1

    # defining Salabim variables/resources
    global env
    global doc_OPD_PHC10

    global pharmacist_PHC10
    global lab_technician_PHC10
    global ipd_nurse_PHC10
    global ncd_nurse_PHC10

    global doc_OPD_PHC10
    global doc_cap_PHC10
    global ip_bed_cap_PHC10

    # defining salabim queues

    global medicine_q_PHC10
    global lab_q_PHC10
    global pharmacy_q_PHC10
    global pharmacy_count_PHC10

    # opd medicine parameters
    global opd_iat_PHC10
    global opd_ser_time_mean_PHC10
    global opd_ser_time_sd_PHC10
    global medicine_count_PHC10
    global medicine_cons_time_PHC10
    global opd_q_waiting_time_PHC10

    global array_opd_patients_PHC10
    global array_medicine_doctor_occupancy_PHC10
    global array_medicine_doctor_occupancy212_PHC10
    global array_opd_q_waiting_time_PHC10
    global array_opd_q_length_PHC10
    global array_medicine_count_PHC10
    array_opd_patients_PHC10 = []
    array_medicine_doctor_occupancy_PHC10 = []
    array_medicine_doctor_occupancy212_PHC10 = []
    array_opd_q_waiting_time_PHC10 = []
    array_opd_q_length_PHC10 = []
    array_medicine_count_PHC10 = []

    # NCD nurse variables
    global ncd_count_PHC10
    global ncd_time_PHC10

    global array_ncd_count_PHC10
    global array_ncd_occupancy_PHC10
    array_ncd_count_PHC10 = []
    array_ncd_occupancy_PHC10 = []

    # pharmacist variables
    global pharmacy_time_PHC10
    global pharmacy_q_waiting_time_PHC10
    global pharmacy_q_length_PHC10
    global array_pharmacy_time_PHC10
    global array_pharmacy_count_PHC10
    global array_pharmacy_q_waiting_time_PHC10
    global array_pharmacy_q_length_PHC10
    global array_pharmacy_occupancy_PHC10

    array_pharmacy_occupancy_PHC10 = []
    array_pharmacy_q_length_PHC10 = []
    array_pharmacy_q_waiting_time_PHC10 = []
    array_pharmacy_time_PHC10 = []
    array_pharmacy_count_PHC10 = []

    # lab variables
    global lab_time_PHC10
    global lab_q_waiting_time_PHC10
    global lab_q_length_PHC10
    global lab_count_PHC10
    global array_lab_q_waiting_time_PHC10
    global array_lab_q_length_PHC10
    global array_lab_occupancy_PHC10
    global array_lab_count_PHC10
    array_lab_count_PHC10 = []
    array_lab_occupancy_PHC10 = []
    array_lab_q_length_PHC10 = []
    array_lab_q_waiting_time_PHC10 = []

    # Delivery variables
    global delivery_iat_PHC10
    global delivery_count_PHC10
    global total_PHC10
    global delivery_bed_PHC10
    global ipd_nurse_PHC10
    global ipd_nurse_PHC10
    global doc_OPD_PHC10
    global e_beds_PHC10
    global delivery_nurse_time_PHC10
    global MO_del_time_PHC10
    global ipd_nurse_time_PHC10
    global childbirth_count_PHC10
    global childbirth_referred_PHC10
    global array_childbirth_count_PHC10
    global array_del_count_PHC10
    global array_del_nurse_occupancy_PHC10
    global array_del_bed_occupancy_PHC10
    global array_childbirth_referred_PHC10

    array_del_nurse_occupancy_PHC10 = []
    array_del_bed_occupancy_PHC10 = []
    array_del_count_PHC10 = []
    global referred_PHC10
    global array_referred10
    array_referred10 = []
    array_childbirth_referred_PHC10 = []
    array_childbirth_count_PHC10 = []

    # inpatient department
    global in_beds_PHC10
    global ipd_q_PHC10
    global MO_ipd_time_PHC10
    global inpatient_count_PHC10
    global array_ipd_count_PHC10
    global array_ipd_staffnurse_occupancy_PHC10
    global array_ipd_bed_occupancy_PHC10
    global array_ipd_del_count_PHC10
    global array_staffnurse_occupancy_PHC10

    global ipd_bed_time_PHC10
    global array_ipd_bed_time_PHC10
    global ipd_nurse_time_PHC10

    global array_ipd_bed_time_m_PHC10
    global array_ip_waiting_time_PHC10
    global array_ip_q_length_PHC10
    global ipd_MO_time_PHC10
    global array_ipd_MO_occupancy_PHC10
    global covid_bed_PHC10
    global phc1_doc_time_PHC10
    global array_phc1_doc_time_PHC10
    array_phc1_doc_time_PHC10 = []

    array_ipd_staffnurse_occupancy_PHC10 = []
    array_ipd_bed_occupancy_PHC10 = []
    array_ipd_count_PHC10 = []
    array_ipd_del_count_PHC10 = []
    array_staffnurse_occupancy_PHC10 = []
    array_ipd_bed_time_PHC10 = []
    array_ipd_bed_time_m_PHC10 = []
    array_ip_waiting_time_PHC10 = []
    array_ip_q_length_PHC10 = []
    array_ipd_MO_occupancy_PHC10 = []

    # ANC
    global ANC_iat_PHC10
    global IPD1_iat_PHC10

    # PHC parameter not to be changed
    global d1_PHC10

    # COVID
    global covid_q_PHC10
    global chc_refer_PHC10
    global covid_count_PHC10
    global dh_refer_PHC10
    global phc2chc_count_PHC10
    global isolation_ward_refer_PHC10
    global lab_covidcount_PHC10
    global retesting_count_PHC10
    global home_refer_PHC10
    global MO_covid_time_PHC10
    global covid_patient_time_PHC10
    global fail_count_PHC10

    global array_chc_refer_PHC10
    global array_covid_count_PHC10
    global array_dh_refer_PHC10
    global array_isolation_ward_refer_PHC10
    global array_lab_covidcount_PHC10
    global array_retesting_count_PHC10

    array_lab_covidcount_PHC10 = []
    array_isolation_ward_refer_PHC10 = []
    array_retesting_count_PHC10 = []
    array_chc_refer_PHC10 = []
    array_dh_refer_PHC10 = []
    array_covid_count_PHC10 = []

    ANC_iat_PHC10 = 1440
    opd_iat_PHC10 = 4  # overall arrival rate in the hospital opd
    opd_ser_time_mean_PHC10 = 0.87  # the service time of the medicine opd (mean)
    opd_ser_time_sd_PHC10 = 0.21  # the service time of the medicine opd (sd)
    doc_cap_PHC10 = 2  # OPD medicine doctor
    ip_bed_cap_PHC10 = 6
    IPD1_iat_PHC10 = 2880
    delivery_iat_PHC10 = 1440

    global ipd_bed_wt_chc2
    global ipd_bed_wt_chc1
    global ipd_bed_wt_chc3

    global array_ipd_bed_wt_chc2
    global array_ipd_bed_wt_chc1
    global array_ipd_bed_wt_chc3

    array_ipd_bed_wt_chc2 = []
    array_ipd_bed_wt_chc1 = []
    array_ipd_bed_wt_chc3 = []

    # DH

    global Covid_iat
    global DH_mild_count
    global array_DH_mild_count
    array_DH_mild_count = []

    # defining salabim resources
    global env
    global doctor_DH_Gen
    global doctor_DH_Oxygen
    global doctor_DH_Ventilator
    global nurse_DH_Gen
    global nurse_DH_Oxygen
    global nurse_DH_Ventilator
    global nurse_DH_sample_collection
    global ICU_ventilator
    global ICU_oxygen
    global General_bed_DH
    global Receptionist
    global triagedoctor
    global lab_technician_DH
    global doc_cap  # number of doctors
    global nurse_cap
    global Generalbed_cap
    global ICUoxygen_cap
    global ICUventilator_cap
    global receptionist_cap

    # Defining salabim queues
    global Generalward_waitingline
    global ICU_oxygen_waitingline
    global ICU_ventilator_waitingline
    global waitingline_registration
    global waitingline_triage
    global CovidPatients_waitingline_DH
    global waitingline_DH_lab

    global CovidPatients_list
    global Moderate_Patients_List
    global Severe_Patients_List
    global gen_exit_list
    global gen_icuoxygen_exit_list
    global gen_icuventilator_exit_list
    global icu_ventilator_list
    global icu_oxygen_icuventilator_gen_exit
    global icu_oxygen_gen_exit
    global icu_ventilator_gen_exit
    global icu_ventilator_icuoxygen_gen_list
    global DH_retest_list
    global doc_occupancy_DH_Gen
    global doc_occupancy_DH_Oxygen
    global doc_occupancy_DH_Ventilator
    global nurse_occupancy_DH_Gen
    global nurse_occupancy_DH_Oxygen
    global nurse_occupancy_DH_Ventilator
    global sample_collctn_nurse_occupancy
    global Generalward_bedoccupancy
    global ICUward_oxygenoccupancy
    global ICUward_ventilatoroccupancy
    global receptionistoccupancy
    global DH_lab_occupancy

    global CovidPatients_DH_list
    global DH_to_Home_refer_patients_list
    global DH_to_CCC_refer_patients_list
    global DH_admitted_patients_list
    global DH_Nurse_sample_collection_wait_time_list
    global retesting_count_DH_list

    global doc_totaltime_DH_Gen
    global doc_totaltime_DH_Oxygen
    global doc_totaltime_DH_Ventilator
    global nurse_totaltime_DH_Gen
    global nurse_totaltime_DH_Oxygen
    global nurse_totaltime_DH_Ventilator
    global DH_sample_collection_nurse_total_time
    global receptionist_totaltime
    global Generalbed_totaltime
    global ICUoxygen_totaltime
    global ICUventilator_totaltime
    global DH_total_lab_time

    global waittime_registration
    global waittime_triage
    global waitime_generalbed
    global waittime_ICUoxygen
    global waittime_ICUventilator
    global waittime_DH_lab

    global registration_time2
    global registration_util2
    global dh_ven_wait
    global array_dh_ven_wait
    array_dh_ven_wait = []

    # count of patients
    global moderate_total
    global moderate_A
    global moderate_B
    global moderate_C
    global severe_total
    global severe_D
    global severe_E
    global severe_F
    global severe_E2F
    global severe_F2E
    global moderate_refer
    global severe_refer
    global array_moderate_refer
    global array_severe_refer

    array_moderate_refer = []
    array_severe_refer = []

    global array_moderate_total
    global array_moderate_A
    global array_moderate_B
    global array_moderate_C
    global array_severe_total
    global array_severe_D
    global array_severe_E
    global array_severe_F
    global array_severe_E2F
    global array_severe_F2E

    array_moderate_total = []
    array_moderate_A = []
    array_moderate_B = []
    array_moderate_C = []
    array_severe_total = []
    array_severe_F = []
    array_severe_E = []
    array_severe_D = []
    array_severe_E2F = []
    array_severe_F2E = []

    global chc3_ipd_occupancy
    global chc3_ipd_wait
    chc3_ipd_occupancy = []
    chc3_ipd_wait = []
    #  COVID care centre
    # isolation
    global isolation_bed
    global isolation_count
    global array_isolation_count
    array_isolation_count = []

    # general
    global G_bed
    global general_count
    global array_general_count
    global G_nurse
    global G_doctor

    array_general_count = []

    # ICU-O
    global O_bed
    global O_count
    global array_O_count
    global general_ward
    global general_ward
    global O_nurse
    global O_doctor

    array_O_count = []

    # ICU-V
    global V_bed
    global V_count
    global array_V_count
    global V_nurse
    global V_doctor

    # patient count
    global A_count
    global B_count
    global C_count
    global D_count
    global E_count
    global F_count
    global recovered
    global moderate_count
    global dead
    global severe_count
    global array_A_count
    global array_B_count
    global array_C_count
    global array_D_count
    global array_E_count
    global array_F_count
    global array_moderate_count
    global array_severe_count
    global array_dead
    global array_recovered

    array_A_count = []
    array_B_count = []
    array_C_count = []
    array_D_count = []
    array_E_count = []
    array_F_count = []
    array_moderate_count = []
    array_severe_count = []
    array_dead = []
    array_recovered = []

    # time of nurses
    global G_nurse_time
    global O_nurse_time
    global V_nurse_time
    global array_G_nurse_occupancy
    global array_O_nurse_occupancy
    global array_V_nurse_occupancy
    global array_G_nurse_occupancy1
    global array_O_nurse_occupancy1
    global array_V_nurse_occupancy1

    global array_prop_dh_2_cc_a_avg
    global array_prop_dh_2_cc_b_avg
    global array_prop_dh_2_cc_c_avg
    global array_prop_dh_2_cc_d_avg
    global array_prop_dh_2_cc_e_avg
    global array_prop_dh_2_cc_f_avg

    # DH arrays for calculating daily average and max values
    array_prop_dh_2_cc_a_avg = []
    array_prop_dh_2_cc_b_avg = []
    array_prop_dh_2_cc_c_avg = []
    array_prop_dh_2_cc_d_avg = []
    array_prop_dh_2_cc_e_avg = []
    array_prop_dh_2_cc_f_avg = []

    global array_prop_dh_2_cc_a_max
    global array_prop_dh_2_cc_b_max
    global array_prop_dh_2_cc_c_max
    global array_prop_dh_2_cc_d_max
    global array_prop_dh_2_cc_e_max
    global array_prop_dh_2_cc_f_max

    array_prop_dh_2_cc_a_max = []
    array_prop_dh_2_cc_b_max = []
    array_prop_dh_2_cc_c_max = []
    array_prop_dh_2_cc_d_max = []
    array_prop_dh_2_cc_e_max = []
    array_prop_dh_2_cc_f_max = []

    global O_nurse_time
    array_G_nurse_occupancy = []
    array_O_nurse_occupancy = []
    array_V_nurse_occupancy = []
    array_G_nurse_occupancy1 = []
    array_O_nurse_occupancy1 = []
    array_V_nurse_occupancy1 = []

    # DH Jan 10
    global dh_2_cc_a
    global dh_2_cc_b
    global dh_2_cc_c
    global dh_2_cc_d
    global dh_2_cc_e
    global dh_2_cc_f

    global dh_total_a
    global dh_total_b
    global dh_total_c
    global dh_total_d
    global dh_total_e
    global dh_total_f

    global array_dh_2_cc_a
    global array_dh_2_cc_b
    global array_dh_2_cc_c
    global array_dh_2_cc_d
    global array_dh_2_cc_e
    global array_dh_2_cc_f

    global array_dh_total_a
    global array_dh_total_b
    global array_dh_total_c
    global array_dh_total_d
    global array_dh_total_e
    global array_dh_total_f
    global array_dh_death

    array_dh_total_a = []
    array_dh_total_b = []
    array_dh_total_c = []
    array_dh_total_d = []
    array_dh_death = []
    array_dh_total_e = []
    array_dh_total_f = []

    array_dh_2_cc_a = []
    array_dh_2_cc_b = []
    array_dh_2_cc_c = []
    array_dh_2_cc_d = []
    array_dh_2_cc_e = []
    array_dh_2_cc_f = []

    global array_prop_dh_2_cc_a
    global array_prop_dh_2_cc_b
    global array_prop_dh_2_cc_c
    global array_prop_dh_2_cc_d
    global array_prop_dh_2_cc_e
    global array_prop_dh_2_cc_f

    array_prop_dh_2_cc_a = []
    array_prop_dh_2_cc_b = []
    array_prop_dh_2_cc_c = []
    array_prop_dh_2_cc_d = []
    array_prop_dh_2_cc_e = []
    array_prop_dh_2_cc_f = []

    # time of doctors
    global G_doctor_time
    global O_doctor_time
    global V_doctor_time
    global array_G_doctor_occupancy
    global array_O_doctor_occupancy
    global array_V_doctor_occupancy
    global array_G_doctor_occupancy1
    global array_O_doctor_occupancy1
    global array_V_doctor_occupancy1

    array_G_doctor_occupancy = []
    array_O_doctor_occupancy = []
    array_V_doctor_occupancy = []

    array_G_doctor_occupancy1 = []
    array_O_doctor_occupancy1 = []
    array_V_doctor_occupancy1 = []

    # waiting time and bed occupancy
    global array_g_bed_wt
    global array_iso_bed_wt
    global array_o_bed_wt
    global array_v_bed_wt
    global array_g_bed_occ
    global array_o_bed_occ
    global array_v_bed_occ
    global lab_covidcount

    array_g_bed_wt = []
    array_o_bed_wt = []
    array_iso_bed_wt = []
    array_v_bed_wt = []
    array_g_bed_occ = []
    array_o_bed_occ = []
    array_v_bed_occ = []
    array_V_count = []

    global dh_2_cc_b_ox
    global dh_2_cc_c_ven
    global array_dh_2_cc_b_ox
    global array_dh_2_cc_c_ven
    global array_prop_dh_2_cc_b_ox
    global array_prop_dh_2_cc_c_ven
    global array_prop_dh_2_cc_b_ox_avg
    global array_prop_dh_2_cc_c_ven_avg
    global array_prop_dh_2_cc_b_ox_max
    global array_prop_dh_2_cc_c_ven_max

    array_dh_2_cc_b_ox = []
    array_dh_2_cc_c_ven = []
    array_prop_dh_2_cc_b_ox = []
    array_prop_dh_2_cc_c_ven = []
    array_prop_dh_2_cc_b_ox_avg = []
    array_prop_dh_2_cc_c_ven_avg = []
    array_prop_dh_2_cc_b_ox_max = []
    array_prop_dh_2_cc_c_ven_max = []


    global F_DH
    F_DH = 0
    global D_DH
    D_DH = 0
    global cc_iso_q

    global array_isolation_bed_occupancy

    array_isolation_bed_occupancy = []
    # covid center finished

    registration_util2 = []
    doc_occupancy_DH_Gen = []
    doc_occupancy_DH_Oxygen = []
    doc_occupancy_DH_Ventilator = []
    nurse_occupancy_DH_Gen = []
    nurse_occupancy_DH_Oxygen = []
    nurse_occupancy_DH_Ventilator = []
    sample_collctn_nurse_occupancy = []
    Generalward_bedoccupancy = []
    ICUward_oxygenoccupancy = []
    ICUward_ventilatoroccupancy = []
    receptionistoccupancy = []
    DH_lab_occupancy = []

    waittime_registration = []
    waittime_DH_lab = []
    waittime_triage = []
    waitime_generalbed = []
    waittime_ICUoxygen = []
    waittime_ICUventilator = []

    DH_Nurse_sample_collection_wait_time_list = []

    CovidPatients_DH_list = []
    DH_to_Home_refer_patients_list = []
    DH_to_CCC_refer_patients_list = []
    DH_admitted_patients_list = []

    gen_exit_list = []
    gen_icuoxygen_exit_list = []
    gen_icuventilator_exit_list = []
    icu_ventilator_list = []
    icu_oxygen_icuventilator_gen_exit = []
    icu_oxygen_gen_exit = []
    icu_ventilator_gen_exit = []
    icu_ventilator_icuoxygen_gen_list = []
    CovidPatients_list = []  # to store no of patients generated in each replication
    retesting_count_DH_list = []

    doc_totaltime_DH_Gen = 0
    doc_totaltime_DH_Oxygen = 0
    doc_totaltime_DH_Ventilator = 0
    nurse_totaltime_DH_Gen = 0
    nurse_totaltime_DH_Oxygen = 0
    nurse_totaltime_DH_Ventilator = 0
    DH_sample_collection_nurse_total_time = 0
    receptionist_totaltime = 0
    DH_total_lab_time = 0
    Generalbed_totaltime = 0
    ICUoxygen_totaltime = 0
    ICUventilator_totaltime = 0

    doc_DH_Gen_cap = 2  # number of doctors/shift
    doc_DH_Oxygen_cap = 2  # number of doctors/shift
    doc_DH_Ventilator_cap = 1  # number of doctors/shift
    nurse_DH_Gen_cap = 2
    nurse_DH_Oxygen_cap = 3
    nurse_DH_Ventilator_cap = 2
    Generalbed_cap = 70
    ICUoxygen_cap = 20
    ICUventilator_cap = 10
    receptionist_cap = 1
    triagedoctor_cap = 1
    # COVID capacities
    global cc_gen_nurse_cap
    global cc_ox_nurse_cap
    global cc_ven_nurse_cap
    global cc_gen_doc_cap
    global cc_ox_doc_cap
    global cc_ven_doc_cap
    global cc_iso_bed
    global cc_gen_bed
    global cc_ox_bed
    global cc_ven_bed


    cc_iso_bed = 300
    cc_gen_bed = 150
    cc_ox_bed = 50
    cc_ven_bed = 30
    cc_gen_nurse_cap = cc_gen_bed/50    # /50 beds
    cc_ox_nurse_cap = cc_ox_bed/7       # /7 beds
    cc_ven_nurse_cap = cc_ven_bed/5     # /5 beds
    cc_gen_doc_cap = cc_gen_bed/50      # (one per 50 beds)
    cc_ox_doc_cap = cc_ox_bed/10        # (one per 10 beds)
    cc_ven_doc_cap = cc_ven_bed/10      # (one per 10 beds)

    # inter facility distance
    global chc3_to_dh_dist
    global chc3_to_cc_dist
    global chc2_to_dh_dist
    global chc2_to_cc_dist
    global chc1_to_dh_dist
    global chc1_to_cc_dist
    global array_chc3_to_dh
    global array_chc3_to_cc
    global array_chc2_to_dh
    global array_chc2_to_cc
    global array_chc1_to_dh
    global array_chc1_to_cc

    array_chc3_to_dh = []
    array_chc3_to_cc = []
    array_chc2_to_dh = []
    array_chc2_to_cc = []
    array_chc1_to_dh = []
    array_chc1_to_cc = []

    # nEW ADDITIONS phcS
    global phc10_to_cc_severe_case
    global phc10_to_cc_dist
    global phc10_2_cc

    global phc9_to_cc_severe_case
    global phc9_to_cc_dist
    global phc9_2_cc

    global phc8_to_cc_severe_case
    global phc8_to_cc_dist
    global phc8_2_cc

    global phc7_to_cc_severe_case
    global phc7_to_cc_dist
    global phc7_2_cc

    global phc6_to_cc_severe_case
    global phc6_to_cc_dist
    global phc6_2_cc

    global phc5_to_cc_severe_case
    global phc5_to_cc_dist
    global phc5_2_cc

    global phc4_to_cc_severe_case
    global phc4_to_cc_dist
    global phc4_2_cc

    global phc3_to_cc_severe_case
    global phc3_to_cc_dist
    global phc3_2_cc

    global phc2_to_cc_severe_case
    global phc2_to_cc_dist
    global phc2_2_cc

    global phc2_to_cc_severe_case
    global phc2_to_cc_dist
    global phc2_2_cc

    global phc1_to_cc_severe_case
    global phc1_to_cc_dist
    global phc1_2_cc
    "New additions CHCS"
    global chc1_to_cc_severe_case
    global chc1_2_cc
    global chc1_2_dh
    global chc1_to_cc_moderate_case

    global chc3_to_cc_moderate_case
    global chc3_2_dh
    global chc3_2_cc
    global chc3_to_cc_severe_case

    global chc2_to_cc_severe_case
    global chc2_2_cc
    global chc2_2_dh
    global chc2_to_cc_moderate_case
    # distance facility
    phc1_2_cc = p[0]
    phc2_2_cc = p[1]
    phc3_2_cc = 7
    phc4_2_cc = 12
    phc5_2_cc = 35.4
    phc6_2_cc = 31
    phc7_2_cc = 20.9
    phc8_2_cc = 21.2
    phc9_2_cc = 14.6
    phc10_2_cc = 6.2
    chc1_2_cc = 35
    chc2_2_cc = 34
    chc3_2_cc = 26
    chc1_2_dh = 35
    chc3_2_dh = 26
    chc2_2_dh = 35

    global array_phc1_to_cc_severe_case
    global array_phc2_to_cc_severe_case
    global array_phc3_to_cc_severe_case
    global array_phc4_to_cc_severe_case
    global array_phc5_to_cc_severe_case
    global array_phc6_to_cc_severe_case
    global array_phc7_to_cc_severe_case
    global array_phc8_to_cc_severe_case
    global array_phc9_to_cc_severe_case
    global array_phc10_to_cc_severe_case

    array_phc1_to_cc_severe_case = []
    array_phc2_to_cc_severe_case = []
    array_phc3_to_cc_severe_case = []
    array_phc4_to_cc_severe_case = []
    array_phc5_to_cc_severe_case = []
    array_phc6_to_cc_severe_case = []
    array_phc7_to_cc_severe_case = []
    array_phc8_to_cc_severe_case = []
    array_phc9_to_cc_severe_case = []
    array_phc10_to_cc_severe_case = []

    global array_phc1_to_cc_dist
    global array_phc2_to_cc_dist
    global array_phc3_to_cc_dist
    global array_phc4_to_cc_dist
    global array_phc5_to_cc_dist
    global array_phc6_to_cc_dist
    global array_phc7_to_cc_dist
    global array_phc8_to_cc_dist
    global array_phc9_to_cc_dist
    global array_phc10_to_cc_dist
    array_phc1_to_cc_dist = []
    array_phc2_to_cc_dist = []
    array_phc3_to_cc_dist = []
    array_phc4_to_cc_dist = []
    array_phc5_to_cc_dist = []
    array_phc6_to_cc_dist = []
    array_phc7_to_cc_dist = []
    array_phc8_to_cc_dist = []
    array_phc9_to_cc_dist = []
    array_phc10_to_cc_dist = []



    global array_chc1_to_cc_severe_case
    global array_chc1_to_cc_moderate_case

    global array_chc3_to_cc_moderate_case
    global array_chc3_to_cc_severe_case

    global array_chc2_to_cc_severe_case
    global array_chc2_to_cc_moderate_case

    array_chc1_to_cc_severe_case = []
    array_chc1_to_cc_moderate_case = []
    array_chc2_to_cc_severe_case = []
    array_chc2_to_cc_moderate_case = []
    array_chc3_to_cc_severe_case = []
    array_chc3_to_cc_moderate_case = []

    # COVID PHC iat
    global covid_iat_PHC1
    global covid_iat_PHC2
    global covid_iat_PHC3
    global covid_iat_PHC4
    global covid_iat_PHC5
    global covid_iat_PHC6
    global covid_iat_PHC7
    global covid_iat_PHC8
    global covid_iat_PHC9
    global covid_iat_PHC10
    Covid_iat = 30
    a = 105
    covid_iat_PHC1 = a
    covid_iat_PHC2 = a
    covid_iat_PHC3 = a
    covid_iat_PHC4 = a
    covid_iat_PHC5 = a
    covid_iat_PHC6 = a
    covid_iat_PHC7 = a
    covid_iat_PHC8 = a
    covid_iat_PHC9 = a
    covid_iat_PHC10 = a

    # CHC covid iat
    global chc2_covid_iat
    global chc1_covid_iat
    global chc3_covid_iat

    chc1_covid_iat = 30
    chc2_covid_iat = 30
    chc3_covid_iat = 30
    # CHC
    # CHC1
    # tring
    replications = 10
    warmup_time = 6 * 30 * 24 * 60  # months*days*hours*minutes
    months = 1
    day = 29
    hours = 24
    minutes = 60
    run_time = months * day * hours * minutes
    days = 0
    days1 = 0
    delivery_iat = 1440
    surgery_iat = 2360.65*2
    ANC_iat = 1440
    emergency_iat = 309*2
    r_time_lb, r_time_ub = 0.5, 1.5
    registration_q_waiting_time = []
    registration_q_length = []
    reg_clerks = 1
    opd_iat_chc1 = 2.975  # overall arrival rate in the hospital opd
    opd_ser_time_mean = .87  # the service time of the medicine opd (mean)
    opd_ser_time_sd = 0.21  # the service time of the medicine opd (sd)
    doc_cap = 1  # OPD medicine doctor
    ip_bed_cap = 7
    covid_bed_cap_chc1 = 7
    global c_bed_wait
    global array_c_bed_wait
    global array_opd_q_man_wait_time
    array_opd_q_man_wait_time = []
    c_bed_wait = []
    array_c_bed_wait = []

    # CHC2
    delivery_iat_chc2 = 550
    surgery_iat_chc2 = 734.78*2
    ANC_iat_chc2 = 550
    emergency_iat_chc2 = 111*2
    r_time_lb_chc2, r_time_ub_chc2 = 0.5, 1.5
    registration_q_waiting_time_chc2 = []
    registration_q_length_chc2 = []
    reg_clerks = 1
    opd_iat_chc2 = 1.24  # overall arrival rate in the hospital opd
    opd_ser_time_mean_chc2 = .87  # the service time of the medicine opd (mean)
    opd_ser_time_sd_chc2 = 0.21  # the service time of the medicine opd (sd)
    doc_cap_chc2 = 2  # OPD medicine doctor
    ip_bed_cap_chc2 = 7
    covid_bed_cap_chc2 = 8
    global c_bed_wait_chc2
    global array_c_bed_wait_chc2
    global array_c_bed_wait_chc3
    global c_bed_wait_chc3
    c_bed_wait_chc2 = []
    c_bed_wait_chc3 = []
    array_c_bed_wait_chc2 = []
    array_c_bed_wait_chc3 = []

    global chc1_max_bed_occ_covid
    global chc2_max_bed_occ_covid
    global chc3_max_bed_occ_covid

    chc1_max_bed_occ_covid = []
    chc2_max_bed_occ_covid = []
    chc3_max_bed_occ_covid = []

    # CHC 3
    days1 = 0
    c_bed_wait_chc3 = []
    delivery_iat_chc3 = 1204
    surgery_iat_chc3 = 207*2
    ANC_iat_chc3 = 1200
    emergency_iat_chc3 = 165*2
    r_time_lb_chc3, r_time_ub_chc3 = 0.5, 1.5
    registration_q_waiting_time_chc3 = []
    registration_q_length_chc3 = []
    reg_clerks = 1
    opd_iat_chc3 = 1.4  # overall arrival rate in the hospital opd
    opd_ser_time_mean_chc3 = .87  # the service time of the medicine opd (mean)
    opd_ser_time_sd_chc3 = 0.21  # the service time of the medicine opd (sd)
    doc_cap_chc3 = 2  # OPD medicine doctor
    ip_bed_cap_chc3 = 7
    covid_bed_cap_chc3 = 8

    global dh_time
    dh_time = 0

    global distance
    distance = []
    global j
    for i in range(0, replications):
        j = 0
        array_t_s_chc1 = []
        # variables for data collection in each replication
        c_bed_wait = []
        c_bed_wait_chc2 = []
        c_bed_wait_chc3 = []
        medicine_cons_time = 0  # records consultation time per replication
        medicine_count = 0  # records number of patients in OPD medicine
        registration_time = 0  # records total time per replication
        registration_q_waiting_time = []
        registration_q_length = []
        total_opds = 0  # total outpatients all inclusive
        opd_q_waiting_time = []
        ncd_count = 0
        ncd_time = 0
        pharmacy_time = 0
        pharmacy_q_waiting_time = []
        pharmacy_q_length = []
        lab_time = 0
        lab_q_waiting_time = []
        lab_q_length = []
        lab_count = 0
        gyn_count = 0
        gyn_q_waiting_time = []
        gyn_time = 0
        ped_count = 0
        ped_q_waiting_time = []
        ped_time = 0
        den_count = 0
        den_q_waiting_time = []
        den_time = 0
        den_proced = 0
        den_consul = 0
        emergency_count = 0
        emergency_bed_time = 0
        emergency_time = 0
        emergency_nurse_time = 0
        emergency_refer = 0
        emr_q_waiting_time = 0
        delivery_count = 0
        delivery_nurse_time = 0
        childbirth_referred = 0
        childbirth_count = 0
        MO_del_time = 0
        ipd_nurse_time = 0
        ipd_MO_time_chc1 = 0
        inpatient_count = 0
        ipd_surgery_count = 0
        # PatientGenerator.total_OPD_patients = 0
        ipd_MO_time_chc1 = 0
        inpatient_del_count = 0  # del patients shifted to ipd
        emer_inpatients = 0  # patients from emergency shifted to ipd (30%)
        emr_q_waiting_time = []
        ipd_bed_time = 0
        sur_time = 0
        ot_nurse_time = 0
        ans_time = 0
        surgery_count = 0
        radio_count = 0
        xray_count = 0
        ecg_count = 0
        referred = 0
        admin_work_chc1 = 0  # admin work
        xray_q_waiting_time = []
        xray_time = 0
        xray_time = 0
        ecg_q_waiting_time = []
        pharmacy_count = 0
        home_refer = 0
        chc_refer = 0
        dh_refer_chc1 = 0
        isolation_ward_refer_from_CHC = 0
        d = 0
        covid_count = 0
        covid_patient_time_chc1 = 0
        MO_covid_time_chc1 = 0
        phc2chc_count = 0
        lab_covidcount = 0
        l = 0
        o = 0
        chc1_covid_bed_time = 0
        moderate_refered_chc3 = 0
        moderate_refered_chc2 = 0
        moderate_refered_chc1 = 0
        q_len_chc1 = []
        q_len_chc2 = []
        q_len_chc3 = []
        t_m_chc1 = 0
        t_a_chc1 = 0
        t_b_chc1 = 0
        t_c_chc1 = 0
        t_d_chc1 = 0
        t_e_chc1 = 0
        t_f_chc1 = 0
        t_s_chc1 = 0
        a_cc_chc1 = 0
        b_cc_chc1 = 0
        c_cc_chc1 = 0
        d_cc_chc1 = 0
        e_cc_chc1 = 0
        f_cc_chc1 = 0
        a_dh_chc1 = 0
        b_dh_chc1 = 0
        c_dh_chc1 = 0
        d_dh_chc1 = 0
        e_dh_chc1 = 0
        f_dh_chc1 = 0

        # CHC 2
        medicine_cons_time_chc2 = 0  # records consultation time per replication
        medicine_count_chc2 = 0  # records number of patients in OPD medicine
        registration_time_chc2 = 0  # records total time per replication
        registration_q_waiting_time_chc2 = []
        registration_q_length_chc2 = []
        total_opds_chc2 = 0  # total outpatients all inclusive
        opd_q_waiting_time_chc2 = []
        ncd_count_chc2 = 0
        ncd_time_chc2 = 0
        pharmacy_time_chc2 = 0
        pharmacy_q_waiting_time_chc2 = []
        pharmacy_q_length_chc2 = []
        lab_time_chc2 = 0
        lab_q_waiting_time_chc2 = []
        lab_q_length_chc2 = []
        lab_count_chc2 = 0
        gyn_count_chc2 = 0
        gyn_q_waiting_time_chc2 = []
        gyn_time_chc2 = 0
        ped_count_chc2 = 0
        ped_q_waiting_time_chc2 = []
        ped_time_chc2 = 0
        den_count_chc2 = 0
        den_q_waiting_time_chc2 = []
        den_time_chc2 = 0
        den_proced_chc2 = 0
        den_consul_chc2 = 0
        emergency_count_chc2 = 0
        emergency_bed_time_chc2 = 0
        emergency_time_chc2 = 0
        emergency_nurse_time_chc2 = 0
        emergency_refer_chc2 = 0
        emr_q_waiting_time_chc2 = 0
        delivery_count_chc2 = 0
        delivery_nurse_time_chc2 = 0
        childbirth_referred_chc2 = 0
        childbirth_count_chc2 = 0
        MO_del_time_chc2 = 0
        ipd_nurse_time_chc2 = 0
        ipd_MO_time_chc2 = 0
        inpatient_count_chc2 = 0
        ipd_surgery_count_chc2 = 0
        PatientGenerator_chc2.total_OPD_patients_chc2 = 0
        ipd_MO_time_chc2 = 0
        inpatient_del_count_chc2 = 0  # del patients shifted to ipd
        emer_inpatients_chc2 = 0  # patients from emergency shifted to ipd (30%)
        emr_q_waiting_time_chc2 = []
        ipd_bed_time_chc2 = 0
        sur_time_chc2 = 0
        ot_nurse_time_chc2 = 0
        ans_time_chc2 = 0
        surgery_count_chc2 = 0
        radio_count_chc2 = 0
        xray_count_chc2 = 0
        ecg_count_chc2 = 0
        referred_chc2 = 0
        admin_work_chc2 = 0  # admin work
        xray_q_waiting_time_chc2 = []
        xray_time_chc2 = 0
        xray_time_chc2 = 0
        ecg_q_waiting_time_chc2 = []
        pharmacy_count_chc2 = 0
        home_refer_chc2 = 0
        chc_refer_chc2 = 0
        dh_refer_chc2 = 0
        isolation_ward_refer_from_CHC_chc2 = 0
        d_chc2 = 0
        covid_count_chc2 = 0
        covid_patient_time_chc2 = 0
        MO_covid_time_chc2 = 0
        phc2chc_count_chc2 = 0
        lab_covidcount_chc2 = 0
        chc2_covid_bed_time = 0

        t_m_chc2 = 0
        t_a_chc2 = 0
        t_b_chc2 = 0
        t_c_chc2 = 0
        t_d_chc2 = 0
        t_e_chc2 = 0
        t_f_chc2 = 0
        t_s_chc2 = 0
        a_cc_chc2 = 0
        b_cc_chc2 = 0
        c_cc_chc2 = 0
        d_cc_chc2 = 0
        e_cc_chc2 = 0
        f_cc_chc2 = 0
        a_dh_chc2 = 0
        b_dh_chc2 = 0
        c_dh_chc2 = 0
        d_dh_chc2 = 0
        e_dh_chc2 = 0
        f_dh_chc2 = 0

        # CHC 3
        medicine_cons_time_chc3 = 0  # records consultation time per replication
        medicine_count_chc3 = 0  # records number of patients in OPD medicine
        registration_time_chc3 = 0  # records total time per replication
        registration_q_waiting_time_chc3 = []
        registration_q_length_chc3 = []
        total_opds_chc3 = 0  # total outpatients all inclusive
        opd_q_waiting_time_chc3 = []
        ncd_count_chc3 = 0
        ncd_time_chc3 = 0
        pharmacy_time_chc3 = 0
        pharmacy_q_waiting_time_chc3 = []
        pharmacy_q_length_chc3 = []
        lab_time_chc3 = 0
        lab_q_waiting_time_chc3 = []
        lab_q_length_chc3 = []
        lab_count_chc3 = 0
        gyn_count_chc3 = 0
        gyn_q_waiting_time_chc3 = []
        gyn_time_chc3 = 0
        ped_count_chc3 = 0
        ped_q_waiting_time_chc3 = []
        ped_time_chc3 = 0
        den_count_chc3 = 0
        den_q_waiting_time_chc3 = []
        den_time_chc3 = 0
        den_proced_chc3 = 0
        den_consul_chc3 = 0
        emergency_count_chc3 = 0
        emergency_bed_time_chc3 = 0
        emergency_time_chc3 = 0
        emergency_nurse_time_chc3 = 0
        emergency_refer_chc3 = 0
        emr_q_waiting_time_chc3 = 0
        delivery_count_chc3 = 0
        delivery_nurse_time_chc3 = 0
        childbirth_referred_chc3 = 0
        childbirth_count_chc3 = 0
        MO_del_time_chc3 = 0
        ipd_nurse_time_chc3 = 0
        ipd_MO_time_chc3 = 0
        inpatient_count_chc3 = 0
        ipd_surgery_count_chc3 = 0
        PatientGenerator_chc3.total_OPD_patients_chc2 = 0
        ipd_MO_time_chc3 = 0
        inpatient_del_count_chc3 = 0  # del patients shifted to ipd
        emer_inpatients_chc3 = 0  # patients from emergency shifted to ipd (30%)
        emr_q_waiting_time_chc3 = []
        ipd_bed_time_chc3 = 0
        sur_time_chc3 = 0
        ot_nurse_time_chc3 = 0
        ans_time_chc3 = 0
        surgery_count_chc3 = 0
        radio_count_chc3 = 0
        xray_count_chc3 = 0
        ecg_count_chc3 = 0
        referred_chc3 = 0
        admin_work_chc3 = 0  # admin work
        xray_q_waiting_time_chc3 = []
        xray_time_chc3 = 0
        xray_time_chc3 = 0
        ecg_q_waiting_time_chc3 = []
        pharmacy_count_chc3 = 0
        home_refer_chc3 = 0
        chc_refer_chc3 = 0
        dh_refer_chc3 = 0
        isolation_ward_refer_from_CHC_chc3 = 0
        d_chc3 = 0
        covid_count_chc3 = 0
        covid_patient_time_chc3 = 0
        MO_covid_time_chc3 = 0
        phc2chc_count_chc3 = 0
        lab_covidcount_chc3 = 0
        ipd_bed_wt_chc2 = []
        ipd_bed_wt_chc1 = []
        ipd_bed_wt_chc3 = []
        chc3_covid_bed_time = 0
        retesting_count_chc1 = 0
        retesting_count_chc2 = 0
        retesting_count_chc3 = 0

        # all chcs interfacility distance
        chc3_to_dh_dist = []
        chc3_to_cc_dist = []
        chc2_to_dh_dist = []
        chc2_to_cc_dist = []
        chc1_to_dh_dist = []
        chc1_to_cc_dist = []
        


        t_m_chc3 = 0
        t_a_chc3 = 0
        t_b_chc3 = 0
        t_c_chc3 = 0
        t_d_chc3 = 0
        t_e_chc3 = 0
        t_f_chc3 = 0
        t_s_chc3 = 0
        a_cc_chc3 = 0
        b_cc_chc3 = 0
        c_cc_chc3 = 0
        d_cc_chc3 = 0
        e_cc_chc3 = 0
        f_cc_chc3 = 0
        a_dh_chc3 = 0
        b_dh_chc3 = 0
        c_dh_chc3 = 0
        d_dh_chc3 = 0
        e_dh_chc3 = 0
        f_dh_chc3 = 0

        # PHC1
        phc1_to_cc_dist = []
        phc2_to_cc_dist = []
        phc3_to_cc_dist = []
        phc4_to_cc_dist = []
        phc5_to_cc_dist = []
        phc6_to_cc_dist = []
        phc7_to_cc_dist = []
        phc8_to_cc_dist = []
        phc9_to_cc_dist = []
        phc10_to_cc_dist = []

        medicine_cons_time1 = 0  # records consultation time per replication
        medicine_count1 = 0  # records number of patients in OPD medicine
        MO_del_time1 = 0  # total outpatients all inclusive
        opd_q_waiting_time1 = []
        ncd_count1 = 0
        ncd_time1 = 0
        pharmacy_time1 = 0
        pharmacy_q_waiting_time1 = []
        pharmacy_q_length1 = []
        lab_time1 = 0
        lab_q_waiting_time1 = []
        lab_q_length1 = []
        lab_count1 = 0
        delivery_count1 = 0
        total1 = 0
        delivery_nurse_time1 = 0
        childbirth_referred1 = 0
        childbirth_count1 = 0
        fail_count1 = 0
        ipd_nurse_time1 = 0
        ipd_MO_time1 = 0
        inpatient_count1 = 0

        PatientGenerator1.total_OPD_patients = 0
        MO_ipd_time1 = 0
        inpatient_del_count = 0  # del patients shifted to ipd
        ipd_bed_time1 = 0
        referred = 0
        admin_work1 = 0  # admin work
        pharmacy_count1 = 0
        home_refer1 = 0
        chc_refer1 = 0
        dh_refer1 = 0
        isolation_ward_refer1 = 0  # added October 8
        covid_count1 = 0
        covid_patient_time1 = 0
        MO_covid_time1 = 0
        retesting_count1 = 0
        lab_covidcount1 = 0
        phc1_doc_time = 0
        d1 = 0
        home_isolation_PHC1 = 0

        # PHC2
        medicine_cons_time_PHC2 = 0  # records consultation time per replication
        medicine_count_PHC2 = 0  # records number of patients in OPD medicine
        MO_del_time_PHC2 = 0  # total outpatients all inclusive
        opd_q_waiting_time_PHC2 = []
        ncd_count_PHC2 = 0
        ncd_time_PHC2 = 0
        pharmacy_time_PHC2 = 0
        pharmacy_q_waiting_time_PHC2 = []
        pharmacy_q_length_PHC2 = []
        lab_time_PHC2 = 0
        lab_q_waiting_time_PHC2 = []
        lab_q_length_PHC2 = []
        lab_count_PHC2 = 0
        delivery_count_PHC2 = 0
        total_PHC2 = 0
        delivery_nurse_time_PHC2 = 0
        childbirth_referred_PHC2 = 0
        childbirth_count_PHC2 = 0
        fail_count_PHC2 = 0
        ipd_nurse_time_PHC2 = 0
        ipd_MO_time_PHC2 = 0
        inpatient_count_PHC2 = 0

        PatientGenerator_PHC2.total_OPD_patients_PHC2 = 0
        MO_ipd_time_PHC2 = 0

        ipd_bed_time_PHC2 = 0
        referred_PHC2 = 0

        pharmacy_count_PHC2 = 0
        home_refer_PHC2 = 0
        phc2chc_count_PHC2 = 0
        chc_refer_PHC2 = 0
        dh_refer_PHC2 = 0
        isolation_ward_refer_PHC2 = 0  # added October 8
        covid_count_PHC2 = 0
        covid_patient_time_PHC2 = 0
        MO_covid_time_PHC2 = 0
        retesting_count_PHC2 = 0
        lab_covidcount_PHC2 = 0
        phc1_doc_time_PHC2 = 0
        d1_PHC2 = 0
        home_isolation_PHC2 = 0

        # PHC 3
        medicine_cons_time_PHC3 = 0  # records consultation time per replication
        medicine_count_PHC3 = 0  # records number of patients in OPD medicine
        MO_del_time_PHC3 = 0  # total outpatients all inclusive
        opd_q_waiting_time_PHC3 = []
        ncd_count_PHC3 = 0
        ncd_time_PHC3 = 0
        pharmacy_time_PHC3 = 0
        pharmacy_q_waiting_time_PHC3 = []
        pharmacy_q_length_PHC3 = []
        lab_time_PHC3 = 0
        lab_q_waiting_time_PHC3 = []
        lab_q_length_PHC3 = []
        lab_count_PHC3 = 0
        delivery_count_PHC3 = 0
        total_PHC3 = 0
        delivery_nurse_time_PHC3 = 0
        childbirth_referred_PHC3 = 0
        childbirth_count_PHC3 = 0
        fail_count_PHC3 = 0
        ipd_nurse_time_PHC3 = 0
        ipd_MO_time_PHC3 = 0
        inpatient_count_PHC3 = 0

        PatientGenerator_PHC3.total_OPD_patients_PHC3 = 0
        MO_ipd_time_PHC3 = 0

        ipd_bed_time_PHC3 = 0
        referred_PHC3 = 0
        admin_work1 = 0  # admin work
        pharmacy_count_PHC3 = 0
        home_refer_PHC3 = 0
        chc_refer_PHC3 = 0
        dh_refer_PHC3 = 0
        phc2chc_count_PHC3 = 0
        isolation_ward_refer_PHC3 = 0  # added October 8
        covid_count_PHC3 = 0
        covid_patient_time_PHC3 = 0
        MO_covid_time_PHC3 = 0
        retesting_count_PHC3 = 0
        lab_covidcount_PHC3 = 0
        phc1_doc_time_PHC3 = 0
        d1_PHC3 = 0
        home_isolation_PHC3 = 0

        # PHC 4
        medicine_cons_time_PHC4 = 0  # records consultation time per replication
        medicine_count_PHC4 = 0  # records number of patients in OPD medicine
        MO_del_time_PHC4 = 0  # total outpatients all inclusive
        opd_q_waiting_time_PHC4 = []
        ncd_count_PHC4 = 0
        ncd_time_PHC4 = 0
        pharmacy_time_PHC4 = 0
        pharmacy_q_waiting_time_PHC4 = []
        pharmacy_q_length_PHC4 = []
        lab_time_PHC4 = 0
        lab_q_waiting_time_PHC4 = []
        lab_q_length_PHC4 = []
        lab_count_PHC4 = 0
        total_PHC4 = 0
        delivery_nurse_time_PHC4 = 0
        fail_count_PHC4 = 0
        ipd_nurse_time_PHC4 = 0
        ipd_MO_time_PHC4 = 0
        inpatient_count_PHC4 = 0

        PatientGenerator_PHC4.total_OPD_patients_PHC4 = 0
        MO_ipd_time_PHC4 = 0
        inpatient_del_count_PHC4 = 0  # del patients shifted to ipd
        ipd_bed_time_PHC4 = 0
        referred_PHC4 = 0
        admin_work4 = 0  # admin work
        pharmacy_count_PHC4 = 0
        home_refer_PHC4 = 0
        chc_refer_PHC4 = 0
        dh_refer_PHC4 = 0
        phc2chc_count_PHC4 = 0
        isolation_ward_refer_PHC4 = 0  # added October 8
        covid_count_PHC4 = 0
        covid_patient_time_PHC4 = 0
        MO_covid_time_PHC4 = 0
        retesting_count_PHC4 = 0
        lab_covidcount_PHC4 = 0
        phc1_doc_time_PHC4 = 0
        d1_PHC4 = 0
        home_isolation_PHC4 = 0

        # PHC 5
        medicine_cons_time_PHC5 = 0  # records consultation time per replication
        medicine_count_PHC5 = 0  # records number of patients in OPD medicine
        MO_del_time_PHC5 = 0  # total outpatients all inclusive
        opd_q_waiting_time_PHC5 = []
        ncd_count_PHC5 = 0
        ncd_time_PHC5 = 0
        pharmacy_time_PHC5 = 0
        pharmacy_q_waiting_time_PHC5 = []
        pharmacy_q_length_PHC5 = []
        lab_time_PHC5 = 0
        lab_q_waiting_time_PHC5 = []
        lab_q_length_PHC5 = []
        lab_count_PHC5 = 0
        delivery_count_PHC5 = 0
        total_PHC5 = 0
        delivery_nurse_time_PHC5 = 0

        fail_count_PHC5 = 0
        ipd_nurse_time_PHC5 = 0
        ipd_MO_time_PHC5 = 0
        inpatient_count_PHC5 = 0

        PatientGenerator_PHC5.total_OPD_patients_PHC5 = 0
        MO_ipd_time_PHC5 = 0
        ipd_bed_time_PHC5 = 0
        admin_work5 = 0  # admin work
        pharmacy_count_PHC5 = 0
        home_refer_PHC5 = 0
        chc_refer_PHC5 = 0
        dh_refer_PHC5 = 0
        phc2chc_count_PHC5 = 0
        isolation_ward_refer_PHC5 = 0  # added October 8
        covid_count_PHC5 = 0
        covid_patient_time_PHC5 = 0
        MO_covid_time_PHC5 = 0
        retesting_count_PHC5 = 0
        lab_covidcount_PHC5 = 0
        phc1_doc_time_PHC5 = 0
        d1_PHC5 = 0
        home_isolation_PHC5 = 0

        # PHC 6
        medicine_cons_time_PHC6 = 0  # records consultation time per replication
        medicine_count_PHC6 = 0  # records number of patients in OPD medicine
        MO_del_time_PHC6 = 0  # total outpatients all inclusive
        opd_q_waiting_time_PHC6 = []
        ncd_count_PHC6 = 0
        ncd_time_PHC6 = 0
        pharmacy_time_PHC6 = 0
        pharmacy_q_waiting_time_PHC6 = []
        pharmacy_q_length_PHC6 = []
        lab_time_PHC6 = 0
        lab_q_waiting_time_PHC6 = []
        lab_q_length_PHC6 = []
        lab_count_PHC6 = 0
        delivery_count_PHC6 = 0
        total_PHC6 = 0
        delivery_nurse_time_PHC6 = 0
        childbirth_referred_PHC6 = 0
        childbirth_count_PHC6 = 0
        fail_count_PHC6 = 0
        ipd_nurse_time_PHC6 = 0
        ipd_MO_time_PHC6 = 0
        inpatient_count_PHC6 = 0

        PatientGenerator_PHC6.total_OPD_patients_PHC6 = 0
        MO_ipd_time_PHC6 = 0
        inpatient_del_count_PHC6 = 0  # del patients shifted to ipd
        ipd_bed_time_PHC6 = 0
        referred_PHC6 = 0
        admin_work6 = 0  # admin work
        pharmacy_count_PHC6 = 0
        home_refer_PHC6 = 0
        chc_refer_PHC6 = 0
        dh_refer_PHC6 = 0
        phc2chc_count_PHC6 = 0
        isolation_ward_refer_PHC6 = 0  # added October 8
        covid_count_PHC6 = 0
        covid_patient_time_PHC6 = 0
        MO_covid_time_PHC6 = 0
        retesting_count_PHC6 = 0
        lab_covidcount_PHC6 = 0
        phc1_doc_time_PHC6 = 0
        d1_PHC6 = 0
        home_isolation_PHC6 = 0

        # PHC 7
        medicine_cons_time_PHC7 = 0  # records consultation time per replication
        medicine_count_PHC7 = 0  # records number of patients in OPD medicine
        MO_del_time_PHC7 = 0  # total outpatients all inclusive
        opd_q_waiting_time_PHC7 = []
        ncd_count_PHC7 = 0
        ncd_time_PHC7 = 0
        pharmacy_time_PHC7 = 0
        pharmacy_q_waiting_time_PHC7 = []
        pharmacy_q_length_PHC7 = []
        lab_time_PHC7 = 0
        lab_q_waiting_time_PHC7 = []
        lab_q_length_PHC7 = []
        lab_count_PHC7 = 0
        total_PHC7 = 0
        delivery_nurse_time_PHC7 = 0
        fail_count_PHC7 = 0
        ipd_nurse_time_PHC7 = 0
        ipd_MO_time_PHC7 = 0
        inpatient_count_PHC7 = 0

        PatientGenerator_PHC7.total_OPD_patients_PHC7 = 0
        MO_ipd_time_PHC7 = 0
        ipd_bed_time_PHC7 = 0
        admin_work7 = 0  # admin work
        pharmacy_count_PHC7 = 0
        home_refer_PHC7 = 0
        chc_refer_PHC7 = 0
        dh_refer_PHC7 = 0
        phc2chc_count_PHC7 = 0
        isolation_ward_refer_PHC7 = 0  # added October 8
        covid_count_PHC7 = 0
        covid_patient_time_PHC7 = 0
        MO_covid_time_PHC7 = 0
        retesting_count_PHC7 = 0
        lab_covidcount_PHC7 = 0
        phc1_doc_time_PHC7 = 0
        d1_PHC7 = 0
        home_isolation_PHC7 = 0
        lab_covidcount7 = 0

        # PHC 8
        medicine_cons_time_PHC8 = 0  # records consultation time per replication
        medicine_count_PHC8 = 0  # records number of patients in OPD medicine
        MO_del_time_PHC8 = 0  # total outpatients all inclusive
        opd_q_waiting_time_PHC8 = []
        ncd_count_PHC8 = 0
        ncd_time_PHC8 = 0
        pharmacy_time_PHC8 = 0
        pharmacy_q_waiting_time_PHC8 = []
        pharmacy_q_length_PHC8 = []
        lab_time_PHC8 = 0
        lab_q_waiting_time_PHC8 = []
        lab_q_length_PHC8 = []
        lab_count_PHC8 = 0
        delivery_count_PHC8 = 0
        total_PHC8 = 0
        delivery_nurse_time_PHC8 = 0
        childbirth_referred_PHC8 = 0
        childbirth_count_PHC8 = 0
        fail_count_PHC8 = 0
        ipd_nurse_time_PHC8 = 0
        ipd_MO_time_PHC8 = 0
        inpatient_count_PHC8 = 0

        PatientGenerator_PHC8.total_OPD_patients_PHC8 = 0
        MO_ipd_time_PHC8 = 0
        inpatient_del_count_PHC8 = 0  # del patients shifted to ipd
        ipd_bed_time_PHC8 = 0
        referred_PHC8 = 0
        admin_work8 = 0  # admin work
        pharmacy_count_PHC8 = 0
        home_refer_PHC8 = 0
        chc_refer_PHC8 = 0
        dh_refer_PHC8 = 0
        phc2chc_count_PHC8 = 0
        isolation_ward_refer_PHC8 = 0  # added October 8
        covid_count_PHC8 = 0
        covid_patient_time_PHC8 = 0
        MO_covid_time_PHC8 = 0
        retesting_count_PHC8 = 0
        lab_covidcount_PHC8 = 0
        phc1_doc_time_PHC8 = 0
        d1_PHC8 = 0
        home_isolation_PHC8 = 0

        # PHC 9
        medicine_cons_time_PHC9 = 0  # records consultation time per replication
        medicine_count_PHC9 = 0  # records number of patients in OPD medicine
        MO_del_time_PHC9 = 0  # total outpatients all inclusive
        opd_q_waiting_time_PHC9 = []
        ncd_count_PHC9 = 0
        ncd_time_PHC9 = 0
        pharmacy_time_PHC9 = 0
        pharmacy_q_waiting_time_PHC9 = []
        pharmacy_q_length_PHC9 = []
        lab_time_PHC9 = 0
        lab_q_waiting_time_PHC9 = []
        lab_q_length_PHC9 = []
        lab_count_PHC9 = 0
        delivery_count_PHC9 = 0
        total_PHC9 = 0
        delivery_nurse_time_PHC9 = 0
        childbirth_referred_PHC9 = 0
        childbirth_count_PHC9 = 0
        fail_count_PHC9 = 0
        ipd_nurse_time_PHC9 = 0
        ipd_MO_time_PHC9 = 0
        inpatient_count_PHC9 = 0

        PatientGenerator_PHC9.total_OPD_patients_PHC9 = 0
        MO_ipd_time_PHC9 = 0
        inpatient_del_count_PHC9 = 0  # del patients shifted to ipd
        ipd_bed_time_PHC9 = 0
        referred_PHC9 = 0
        admin_work9 = 0  # admin work
        pharmacy_count_PHC9 = 0
        home_refer_PHC9 = 0
        chc_refer_PHC9 = 0
        dh_refer_PHC9 = 0
        phc2chc_count_PHC9 = 0
        isolation_ward_refer_PHC9 = 0  # added October 8
        covid_count_PHC9 = 0
        covid_patient_time_PHC9 = 0
        MO_covid_time_PHC9 = 0
        retesting_count_PHC9 = 0
        lab_covidcount_PHC9 = 0
        phc1_doc_time_PHC9 = 0
        d1_PHC9 = 0
        home_isolation_PHC9 = 0

        # PHC 10
        medicine_cons_time_PHC10 = 0  # records consultation time per replication
        medicine_count_PHC10 = 0  # records number of patients in OPD medicine
        MO_del_time_PHC10 = 0  # total outpatients all inclusive
        opd_q_waiting_time_PHC10 = []
        ncd_count_PHC10 = 0
        ncd_time_PHC10 = 0
        pharmacy_time_PHC10 = 0
        pharmacy_q_waiting_time_PHC10 = []
        pharmacy_q_length_PHC10 = []
        lab_time_PHC10 = 0
        lab_q_waiting_time_PHC10 = []
        lab_q_length_PHC10 = []
        lab_count_PHC10 = 0
        delivery_count_PHC10 = 0
        total_PHC10 = 0
        delivery_nurse_time_PHC10 = 0
        childbirth_referred_PHC10 = 0
        childbirth_count_PHC10 = 0
        fail_count_PHC10 = 0
        ipd_nurse_time_PHC10 = 0
        ipd_MO_time_PHC10 = 0
        inpatient_count_PHC10 = 0

        PatientGenerator_PHC10.total_OPD_patients_PHC10 = 0
        MO_ipd_time_PHC10 = 0
        inpatient_del_count_PHC10 = 0  # del patients shifted to ipd
        ipd_bed_time_PHC10 = 0
        referred_PHC10 = 0
        admin_work10 = 0  # admin work
        pharmacy_count_PHC10 = 0
        home_refer_PHC10 = 0
        chc_refer_PHC10 = 0
        dh_refer_PHC10 = 0
        phc2chc_count_PHC10 = 0
        isolation_ward_refer_PHC10 = 0  # added October 8
        covid_count_PHC10 = 0
        covid_patient_time_PHC10 = 0
        MO_covid_time_PHC10 = 0
        retesting_count_PHC10 = 0
        lab_covidcount_PHC10 = 0
        phc1_doc_time_PHC10 = 0
        d1_PHC10 = 0
        home_isolation_PHC10 = 0
        phc1_to_cc_severe_case = 0
        phc2_to_cc_severe_case = 0
        phc3_to_cc_severe_case = 0
        phc4_to_cc_severe_case = 0
        phc5_to_cc_severe_case = 0
        phc6_to_cc_severe_case = 0
        phc7_to_cc_severe_case = 0
        phc8_to_cc_severe_case = 0
        phc9_to_cc_severe_case = 0
        phc10_to_cc_severe_case = 0

        # DH
        dh_2_cc_b_ox = 0
        dh_2_cc_c_ven = 0
        doc_totaltime_DH_Gen = 0
        doc_totaltime_DH_Oxygen = 0
        doc_totaltime_DH_Ventilator = 0
        nurse_totaltime_DH_Gen = 0
        nurse_totaltime_DH_Oxygen = 0
        nurse_totaltime_DH_Ventilator = 0
        DH_sample_collection_nurse_total_time = 0
        receptionist_totaltime = 0
        DH_total_lab_time = 0
        Generalbed_totaltime = 0
        ICUoxygen_totaltime = 0
        ICUventilator_totaltime = 0
        DHPatients.receptionistservicetime = []
        DHPatients.triageservicetime = []
        DoctorDH_Gen.doc_DH_time_Gen = []
        DoctorDH_Oxygen.doc_DH_time_Oxygen = []
        DoctorDH_Ventilator.doc_DH_time_Ventilator = []
        NurseDH_Gen.nurse_DH_time_Gen = []
        NurseDH_Oxygen.nurse_DH_time_Oxygen = []
        NurseDH_Ventilator.nurse_DH_time_Ventilator = []
        DHPatients.generalbedtime = []
        DHPatients.icuoxygentime = []
        DHPatients.icuventilatortime = []

        DHPatients.receptionwaitingtime = []
        DHPatientTest.DH_lab_waiting_time = []
        DHPatients.triagewaitingtime = []
        DHPatients.generalbedwaitingtime = []
        DHPatients.icuoxygenwaitingtime = []
        DHPatients.icuventilatorwaitingtime = []
        dh_ven_wait = []

        DHPatientTest.DH_Nurse_sample_collection_time = []
        DHPatientTest.DH_Doctor_initial_doctor_test_time = []

        DHPatientTest.DH_Nurse_sample_collection_wait_time = []

        DHPatients.No_of_covid_patients = 0
        DHPatients.moderate_gen_to_exit = 0
        DHPatients.moderate_gen_to_icu_to_gen_exit = 0
        DHPatients.moderate_gen_to_ventilator_to_gen_exit = 0
        DHPatients.severe_ventilator_dead = 0
        DHPatients.R1 = 0
        DHPatients.R2 = 0
        DHPatients.R3 = 0
        DHPatients.R4 = 0
        dh_2_cc_b_ox = 0
        dh_2_cc_c_ven = 0

        DHPatientTest.CovidPatients_DH = 0
        DHPatientTest.DH_to_CCC_refer = 0
        DHPatientTest.DH_to_Home_refer = 0

        DHPatients.moderate_gen_refer_CCC = 0
        DHPatients.severe_icu_to_gen_refer_CCC = 0
        DHPatients.severe_ventilator_to_gen_refer_CCC = 0
        DHPatients.severe_ventilator_dead_refer_CCC = 0
        DH_mild_count = 0
        moderate_total = 0
        moderate_A = 0
        moderate_B = 0
        moderate_C = 0
        severe_total = 0
        severe_D = 0
        severe_E = 0
        severe_F = 0
        severe_E2F = 0
        severe_F2E = 0
        moderate_refer = 0
        severe_refer = 0

        dh_2_cc_a = 0
        dh_2_cc_b = 0
        dh_2_cc_c = 0
        dh_2_cc_d = 0
        dh_2_cc_e = 0
        dh_2_cc_f = 0
        dh_time = 0
        dh_total_a = 0
        dh_total_b = 0
        dh_total_c = 0
        dh_total_d = 0
        dh_total_e = 0
        dh_total_f = 0

        # COVID center
        isolation_count = 0
        general_count = 0
        V_count = 0
        O_count = 0
        A_count = 0
        B_count = 0
        C_count = 0
        D_count = 0
        E_count = 0
        F_count = 0
        recovered = 0
        dead = 0
        moderate_count = 0
        severe_count = 0
        lab_covidcount = 0
        V_doctor_time = 0
        O_doctor_time = 0
        G_doctor_time = 0

        V_nurse_time = 0
        O_nurse_time = 0
        G_nurse_time = 0


        m_iso_bed_wt = []

        # CHC new addition
        chc1_to_cc_moderate_case = 0
        chc1_to_cc_severe_case = 0
        chc2_to_cc_moderate_case = 0
        chc2_to_cc_severe_case = 0
        chc3_to_cc_moderate_case = 0
        chc3_to_cc_severe_case = 0

        # CHC count covid
        chc1_severe_covid = 0
        chc1_moderate_covid = 0
        chc2_severe_covid = 0
        chc2_moderate_covid = 0
        chc3_severe_covid = 0
        chc3_moderate_covid = 0

        # CHC
        env = sim.Environment(trace=False, random_seed="", time_unit='minutes')
        sim_time = warmup_time + run_time
        # defining salabim resources
        # Doctors

        # CHC 1
        # defining salabim resources
        # Doctors
        doc_OPD = sim.Resource("General Medicine OPD", capacity=doc_cap)
        doc_Gyn = sim.Resource("Gyn & Obs OPD", capacity=1)
        doc_Ped = sim.Resource("Pediatrics OPD", capacity=1)
        doc_Dentist = sim.Resource("Dental OPD", capacity=1)
        MO = sim.Resource("Medical Officer", capacity=1)
        doc_ans = sim.Resource("Anaesthetist", capacity=1)
        doc_surgeon = sim.Resource("Surgeon", capacity=1)
        MO_ipd_chc1 = sim.Resource("IPD doctor", capacity=1)
        # Other staff
        pharmacist = sim.Resource("Pharmacist", capacity=2)
        lab_technician = sim.Resource("Lab Technician", capacity=1)
        xray_tech = sim.Resource("Xray technician", capacity=1)
        registration_clerk = sim.Resource("Registration Clerk", capacity=reg_clerks)
        # Beds
        e_beds = sim.Resource("Beds emergency", capacity=6)
        delivery_bed = sim.Resource("Delivery bed", capacity=1)
        in_beds = sim.Resource("Inpatient beds", capacity=ip_bed_cap)
        covid_bed_chc1 = sim.Resource("Covid beds", capacity=covid_bed_cap_chc1)
        # nurses
        ipd_nurse = sim.Resource("Staff nurses", capacity=1)  # 3 nurses
        emer_nurse = sim.Resource("Emergency dept nurse", capacity=1)  # 3 nurses
        ncd_nurse = sim.Resource("NCD nurse", capacity=1)  # 1 nurse
        delivery_nurse = sim.Resource("Emergency Staff nurse", capacity=1)  # 3 nurses
        ot_nurse = sim.Resource("OT Nurse", capacity=1)
        # defining salabim queues
        registration_q = sim.Queue("Registration queue")
        medicine_q = sim.Queue("Medicine OPD queue")
        pharmacy_q = sim.Queue("Pharmacy queue")
        lab_q = sim.Queue("Lab queue")
        gyn_q = sim.Queue("Gynecologist queue")
        ped_q = sim.Queue("Pediatrician queue")
        den_q = sim.Queue("Dental OPD queue")
        xray_q = sim.Queue("Xray queue")
        ecg_q = sim.Queue("ECG queue")
        emr_q = sim.Queue("Emergency Queue")
        ipd_q = sim.Queue("IPD Queue")
        covid_q = sim.Queue()

        # CHC 2 defining salabim resources
        # Doctors
        doc_OPD_chc2 = sim.Resource("General Medicine OPD", capacity=doc_cap_chc2)
        doc_Gyn_chc2 = sim.Resource("Gyn & Obs OPD", capacity=1)
        doc_Ped_chc2 = sim.Resource("Pediatrics OPD", capacity=1)
        doc_Dentist_chc2 = sim.Resource("Dental OPD", capacity=1)
        MO_chc2 = sim.Resource("Medical Officer", capacity=1)
        doc_ans_chc2 = sim.Resource("Anaesthetist", capacity=1)
        doc_surgeon_chc2 = sim.Resource("Surgeon", capacity=1)
        MO_ipd_chc2 = sim.Resource("IPD doctor", capacity=1)
        # Other staff
        pharmacist_chc2 = sim.Resource("Pharmacist", capacity=2)
        lab_technician_chc2 = sim.Resource("Lab Technician", capacity=1)
        xray_tech_chc2 = sim.Resource("Xray technician", capacity=1)
        registration_clerk_chc2 = sim.Resource("Registration Clerk", capacity=reg_clerks)
        # Beds
        e_beds_chc2 = sim.Resource("Beds emergency", capacity=3)
        delivery_bed_chc2 = sim.Resource("Delivery bed", capacity=1)
        in_beds_chc2 = sim.Resource("Inpatient beds", capacity=ip_bed_cap_chc2)
        covid_bed_chc2 = sim.Resource("Covid beds", capacity=covid_bed_cap_chc2)
        # nurses
        ipd_nurse_chc2 = sim.Resource("Staff nurses", capacity=1)  # 3 nurses
        emer_nurse_chc2 = sim.Resource("Emergency dept nurse", capacity=1)  # 3 nurses
        ncd_nurse_chc2 = sim.Resource("NCD nurse", capacity=1)  # 1 nurse
        delivery_nurse_chc2 = sim.Resource("Emergency Staff nurse", capacity=1)  # 3 nurses
        ot_nurse_chc2 = sim.Resource("OT Nurse", capacity=1)
        # defining salabim queues
        registration_q_chc2 = sim.Queue("Registration queue")
        medicine_q_chc2 = sim.Queue("Medicine OPD queue")
        pharmacy_q_chc2 = sim.Queue("Pharmacy queue")
        lab_q_chc2 = sim.Queue("Lab queue")
        gyn_q_chc2 = sim.Queue("Gynecologist queue")
        ped_q_chc2 = sim.Queue("Pediatrician queue")
        den_q_chc2 = sim.Queue("Dental OPD queue")
        xray_q_chc2 = sim.Queue("Xray queue")
        ecg_q_chc2 = sim.Queue("ECG queue")
        emr_q_chc2 = sim.Queue("Emergency Queue")
        ipd_q_chc2 = sim.Queue("IPD Queue")
        covid_q_chc2 = sim.Queue()

        # # CHC 3 defining salabim resources
        # Doctors
        doc_OPD_chc3 = sim.Resource("General Medicine OPD", capacity=doc_cap_chc3)
        doc_Gyn_chc3 = sim.Resource("Gyn & Obs OPD", capacity=1)
        doc_Ped_chc3 = sim.Resource("Pediatrics OPD", capacity=1)
        doc_Dentist_chc3 = sim.Resource("Dental OPD", capacity=1)
        MO_chc3 = sim.Resource("Medical Officer", capacity=1)
        doc_ans_chc3 = sim.Resource("Anaesthetist", capacity=1)
        doc_surgeon_chc3 = sim.Resource("Surgeon", capacity=1)
        MO_ipd_chc3 = sim.Resource("IPD doctor", capacity=1)
        # Other staff
        pharmacist_chc3 = sim.Resource("Pharmacist", capacity=2)
        lab_technician_chc3 = sim.Resource("Lab Technician", capacity=1)
        xray_tech_chc3 = sim.Resource("Xray technician", capacity=1)
        registration_clerk_chc3 = sim.Resource("Registration Clerk", capacity=reg_clerks)
        # Beds
        e_beds_chc3 = sim.Resource("Beds emergency", capacity=6)
        delivery_bed_chc3 = sim.Resource("Delivery bed", capacity=1)
        in_beds_chc3 = sim.Resource("Inpatient beds", capacity=ip_bed_cap_chc3)
        covid_bed_chc3 = sim.Resource("Covid beds", capacity=covid_bed_cap_chc3)

        # nurses
        ipd_nurse_chc3 = sim.Resource("Staff nurses", capacity=1)  # 3 nurses
        emer_nurse_chc3 = sim.Resource("Emergency dept nurse", capacity=1)  # 3 nurses
        ncd_nurse_chc3 = sim.Resource("NCD nurse", capacity=1)  # 1 nurse
        delivery_nurse_chc3 = sim.Resource("Emergency Staff nurse", capacity=1)  # 3 nurses
        ot_nurse_chc3 = sim.Resource("OT Nurse", capacity=1)
        # defining salabim queues
        registration_q_chc3 = sim.Queue("Registration queue")
        medicine_q_chc3 = sim.Queue("Medicine OPD queue")
        pharmacy_q_chc3 = sim.Queue("Pharmacy queue")
        lab_q_chc3 = sim.Queue("Lab queue")
        gyn_q_chc3 = sim.Queue("Gynecologist queue")
        ped_q_chc3 = sim.Queue("Pediatrician queue")
        den_q_chc3 = sim.Queue("Dental OPD queue")
        xray_q_chc3 = sim.Queue("Xray queue")
        ecg_q_chc3 = sim.Queue("ECG queue")
        emr_q_chc3 = sim.Queue("Emergency Queue")
        ipd_q_chc3 = sim.Queue("IPD Queue")
        covid_q_chc3 = sim.Queue()

        # PHC1
        # defining salabim resources
        # Doctors
        doc_OPD1 = sim.Resource("General Medicine OPD", capacity=doc_cap1)
        # Other staff
        pharmacist1 = sim.Resource("Pharmacist", capacity=1)
        lab_technician1 = sim.Resource("Lab Technician", capacity=1)

        # Beds
        delivery_bed1 = sim.Resource("Delivery bed", capacity=1)
        in_beds1 = sim.Resource("Inpatient beds", capacity=6)
        # nurses
        ipd_nurse1 = sim.Resource("Staff nurses", capacity=3)
        ncd_nurse1 = sim.Resource("NCD nurse", capacity=1)
        # defining salabim queues
        medicine_q1 = sim.Queue("Medicine OPD queue")
        pharmacy_q1 = sim.Queue("Pharmacy queue")
        lab_q1 = sim.Queue("Lab queue")
        covid_q1 = sim.Queue()

        # PHC 2
        # defining salabim resources
        # Doctors
        doc_OPD_PHC2 = sim.Resource("General Medicine OPD", capacity=doc_cap_PHC2)
        # Other staff
        pharmacist_PHC2 = sim.Resource("Pharmacist", capacity=1)
        lab_technician_PHC2 = sim.Resource("Lab Technician", capacity=1)

        # Beds
        delivery_bed_PHC2 = sim.Resource("Delivery bed", capacity=1)
        in_beds_PHC2 = sim.Resource("Inpatient beds", capacity=6)
        # nurses
        ipd_nurse_PHC2 = sim.Resource("Staff nurses", capacity=3)
        ncd_nurse_PHC2 = sim.Resource("NCD nurse", capacity=1)
        # defining salabim queues
        medicine_q_PHC2 = sim.Queue("Medicine OPD queue")
        pharmacy_q_PHC2 = sim.Queue("Pharmacy queue")
        lab_q_PHC2 = sim.Queue("Lab queue")
        covid_q_PHC2 = sim.Queue()

        # PHC 3
        # defining salabim resources
        # Doctors
        doc_OPD_PHC3 = sim.Resource("General Medicine OPD", capacity=doc_cap_PHC3)
        # Other staff
        pharmacist_PHC3 = sim.Resource("Pharmacist", capacity=1)
        lab_technician_PHC3 = sim.Resource("Lab Technician", capacity=1)

        # Beds
        delivery_bed_PHC3 = sim.Resource("Delivery bed", capacity=1)
        in_beds_PHC3 = sim.Resource("Inpatient beds", capacity=6)
        # nurses
        ipd_nurse_PHC3 = sim.Resource("Staff nurses", capacity=3)
        ncd_nurse_PHC3 = sim.Resource("NCD nurse", capacity=1)
        # defining salabim queues
        medicine_q_PHC3 = sim.Queue("Medicine OPD queue")
        pharmacy_q_PHC3 = sim.Queue("Pharmacy queue")
        lab_q_PHC3 = sim.Queue("Lab queue")
        covid_q_PHC3 = sim.Queue()

        # PHC 4
        # defining salabim resources
        # Doctors
        doc_OPD_PHC4 = sim.Resource("General Medicine OPD", capacity=doc_cap_PHC4)
        # Other staff
        pharmacist_PHC4 = sim.Resource("Pharmacist", capacity=1)
        lab_technician_PHC4 = sim.Resource("Lab Technician", capacity=1)

        # Beds

        in_beds_PHC4 = sim.Resource("Inpatient beds", capacity=6)
        # nurses
        ipd_nurse_PHC4 = sim.Resource("Staff nurses", capacity=3)
        ncd_nurse_PHC4 = sim.Resource("NCD nurse", capacity=1)
        # defining salabim queues
        medicine_q_PHC4 = sim.Queue("Medicine OPD queue")
        pharmacy_q_PHC4 = sim.Queue("Pharmacy queue")
        lab_q_PHC4 = sim.Queue("Lab queue")
        covid_q_PHC4 = sim.Queue()

        # PHC 5
        # defining salabim resources
        # Doctors
        doc_OPD_PHC5 = sim.Resource("General Medicine OPD", capacity=doc_cap_PHC5)
        # Other staff
        pharmacist_PHC5 = sim.Resource("Pharmacist", capacity=1)
        lab_technician_PHC5 = sim.Resource("Lab Technician", capacity=1)

        # Beds
        delivery_bed_PHC5 = sim.Resource("Delivery bed", capacity=1)
        in_beds_PHC5 = sim.Resource("Inpatient beds", capacity=6)
        # nurses
        ipd_nurse_PHC5 = sim.Resource("Staff nurses", capacity=3)
        ncd_nurse_PHC5 = sim.Resource("NCD nurse", capacity=1)
        # defining salabim queues
        medicine_q_PHC5 = sim.Queue("Medicine OPD queue")
        pharmacy_q_PHC5 = sim.Queue("Pharmacy queue")
        lab_q_PHC5 = sim.Queue("Lab queue")
        covid_q_PHC5 = sim.Queue()

        # PHC 6
        # defining salabim resources
        # Doctors
        doc_OPD_PHC6 = sim.Resource("General Medicine OPD", capacity=doc_cap_PHC6)
        # Other staff
        pharmacist_PHC6 = sim.Resource("Pharmacist", capacity=1)
        lab_technician_PHC6 = sim.Resource("Lab Technician", capacity=1)

        # Beds
        delivery_bed_PHC6 = sim.Resource("Delivery bed", capacity=1)
        in_beds_PHC6 = sim.Resource("Inpatient beds", capacity=6)
        # nurses
        ipd_nurse_PHC6 = sim.Resource("Staff nurses", capacity=3)
        ncd_nurse_PHC6 = sim.Resource("NCD nurse", capacity=1)
        # defining salabim queues
        medicine_q_PHC6 = sim.Queue("Medicine OPD queue")
        pharmacy_q_PHC6 = sim.Queue("Pharmacy queue")
        lab_q_PHC6 = sim.Queue("Lab queue")
        covid_q_PHC6 = sim.Queue()

        # PHC 7
        # defining salabim resources
        # Doctors
        doc_OPD_PHC7 = sim.Resource("General Medicine OPD", capacity=doc_cap_PHC7)
        # Other staff
        pharmacist_PHC7 = sim.Resource("Pharmacist", capacity=1)
        lab_technician_PHC7 = sim.Resource("Lab Technician", capacity=1)

        # Beds

        in_beds_PHC7 = sim.Resource("Inpatient beds", capacity=6)
        # nurses
        ipd_nurse_PHC7 = sim.Resource("Staff nurses", capacity=3)
        ncd_nurse_PHC7 = sim.Resource("NCD nurse", capacity=1)
        # defining salabim queues
        medicine_q_PHC7 = sim.Queue("Medicine OPD queue")
        pharmacy_q_PHC7 = sim.Queue("Pharmacy queue")
        lab_q_PHC7 = sim.Queue("Lab queue")
        covid_q_PHC7 = sim.Queue()

        # PHC 8
        # defining salabim resources
        # Doctors
        doc_OPD_PHC8 = sim.Resource("General Medicine OPD", capacity=doc_cap_PHC8)
        # Other staff
        pharmacist_PHC8 = sim.Resource("Pharmacist", capacity=1)
        lab_technician_PHC8 = sim.Resource("Lab Technician", capacity=1)

        # Beds
        delivery_bed_PHC8 = sim.Resource("Delivery bed", capacity=1)
        in_beds_PHC8 = sim.Resource("Inpatient beds", capacity=6)
        # nurses
        ipd_nurse_PHC8 = sim.Resource("Staff nurses", capacity=3)
        ncd_nurse_PHC8 = sim.Resource("NCD nurse", capacity=1)
        # defining salabim queues
        medicine_q_PHC8 = sim.Queue("Medicine OPD queue")
        pharmacy_q_PHC8 = sim.Queue("Pharmacy queue")
        lab_q_PHC8 = sim.Queue("Lab queue")
        covid_q_PHC8 = sim.Queue()

        # PHC 9
        # defining salabim resources
        # Doctors
        doc_OPD_PHC9 = sim.Resource("General Medicine OPD", capacity=doc_cap_PHC9)
        # Other staff
        pharmacist_PHC9 = sim.Resource("Pharmacist", capacity=1)
        lab_technician_PHC9 = sim.Resource("Lab Technician", capacity=1)

        # Beds
        delivery_bed_PHC9 = sim.Resource("Delivery bed", capacity=1)
        in_beds_PHC9 = sim.Resource("Inpatient beds", capacity=6)
        # nurses
        ipd_nurse_PHC9 = sim.Resource("Staff nurses", capacity=3)
        ncd_nurse_PHC9 = sim.Resource("NCD nurse", capacity=1)
        # defining salabim queues
        medicine_q_PHC9 = sim.Queue("Medicine OPD queue")
        pharmacy_q_PHC9 = sim.Queue("Pharmacy queue")
        lab_q_PHC9 = sim.Queue("Lab queue")
        covid_q_PHC9 = sim.Queue()

        # PHC 10
        # defining salabim resources
        # Doctors
        doc_OPD_PHC10 = sim.Resource("General Medicine OPD", capacity=doc_cap_PHC10)
        # Other staff
        pharmacist_PHC10 = sim.Resource("Pharmacist", capacity=1)
        lab_technician_PHC10 = sim.Resource("Lab Technician", capacity=1)

        # Beds
        delivery_bed_PHC10 = sim.Resource("Delivery bed", capacity=1)
        in_beds_PHC10 = sim.Resource("Inpatient beds", capacity=6)
        # nurses
        ipd_nurse_PHC10 = sim.Resource("Staff nurses", capacity=3)
        ncd_nurse_PHC10 = sim.Resource("NCD nurse", capacity=1)
        # defining salabim queues
        medicine_q_PHC10 = sim.Queue("Medicine OPD queue")
        pharmacy_q_PHC10 = sim.Queue("Pharmacy queue")
        lab_q_PHC10 = sim.Queue("Lab queue")
        covid_q_PHC10 = sim.Queue()

        # DH

        Receptionist = sim.Resource("Receptionist", capacity=receptionist_cap)
        triagedoctor = sim.Resource("Triaging Doctor", capacity=triagedoctor_cap)
        doctor_DH_Gen = sim.Resource('Doctor', capacity=doc_DH_Gen_cap)
        doctor_DH_Oxygen = sim.Resource('Doctor', capacity=doc_DH_Oxygen_cap)
        doctor_DH_Ventilator = sim.Resource('Doctor', capacity=doc_DH_Ventilator_cap)
        nurse_DH_Gen = sim.Resource("Gen Nurse", capacity=nurse_DH_Gen_cap)
        nurse_DH_Oxygen = sim.Resource(" Oxygen Nurse", capacity=nurse_DH_Oxygen_cap)
        nurse_DH_Ventilator = sim.Resource("Ventilator Nurse", capacity=nurse_DH_Ventilator_cap)
        nurse_DH_sample_collection = sim.Resource("Sample Collection nurse", capacity=1)
        General_bed_DH = sim.Resource("General bed", capacity=Generalbed_cap)
        ICU_oxygen = sim.Resource("ICUbed with oxygen", capacity=ICUoxygen_cap)
        ICU_ventilator = sim.Resource("ICUbed with ventilator", capacity=ICUventilator_cap)
        lab_technician_DH = sim.Resource("lab_technician_DH", capacity=1)

        waitingline_registration = sim.Queue("waitigline_registrationcounter")
        waitingline_triage = sim.Queue("waitingline_triage")
        Generalward_waitingline = sim.Queue("waitingline_generalbed")
        ICU_oxygen_waitingline = sim.Queue("waitingline_ICUoxygen")
        ICU_ventilator_waitingline = sim.Queue("waitingline_ICUventilator")
        CovidPatients_waitingline_DH = sim.Queue("waitingline_CovidPatientsDH")
        waitingline_DH_lab = sim.Queue("waitingline_DHLab")

        # CHC
        PatientGenerator()
        Emergency_patient()
        Delivery_patient_generator()
        Surgery_patient_generator()
        ANC()
        CovidGenerator()

        # chc 2
        PatientGenerator_chc2()
        Emergency_patient_chc2()
        Delivery_patient_generator_chc2()
        Surgery_patient_generator_chc2()
        ANC_chc2()
        CovidGenerator_chc2()
        # chc 3
        PatientGenerator_chc3()
        Emergency_patient_chc3()
        Delivery_patient_generator_chc3()
        Surgery_patient_generator_chc3()
        ANC_chc3()
        CovidGenerator_chc3()

        # PHC1

        PatientGenerator1()
        Delivery_patient_generator1()
        IPD_PatientGenerator1()
        ANC1()
        CovidGenerator1()

        # PHC 2
        PatientGenerator_PHC2()
        Delivery_patient_generator_PHC2()
        IPD_PatientGenerator_PHC2()
        ANC_PHC2()
        CovidGenerator_PHC2()

        # PHC 3
        PatientGenerator_PHC3()
        Delivery_patient_generator_PHC3()
        IPD_PatientGenerator_PHC3()
        ANC_PHC3()
        CovidGenerator_PHC3()

        # PHC 4
        PatientGenerator_PHC4()
        IPD_PatientGenerator_PHC4()
        CovidGenerator_PHC4()

        # PHC 5
        PatientGenerator_PHC5()
        IPD_PatientGenerator_PHC5()
        CovidGenerator_PHC5()

        # PHC6

        PatientGenerator_PHC6()
        Delivery_patient_generator_PHC6()
        IPD_PatientGenerator_PHC6()
        ANC_PHC6()
        CovidGenerator_PHC6()

        # PHC7

        PatientGenerator_PHC7()
        IPD_PatientGenerator_PHC7()
        CovidGenerator_PHC7()

        # PHC 8

        PatientGenerator_PHC8()
        Delivery_patient_generator_PHC8()
        IPD_PatientGenerator_PHC8()
        ANC_PHC8()
        CovidGenerator_PHC8()

        # PHC 9
        PatientGenerator_PHC9()
        Delivery_patient_generator_PHC9()
        IPD_PatientGenerator_PHC9()
        ANC_PHC9()
        CovidGenerator_PHC9()

        # PHC 10
        PatientGenerator_PHC10()
        Delivery_patient_generator_PHC10()
        IPD_PatientGenerator_PHC10()
        ANC_PHC10()
        CovidGenerator_PHC10()

        # DH
        DHPatient(name='')
        DHPatientTest(name='')
        DoctorDH_Gen(name='')
        DoctorDH_Oxygen(name='')
        DoctorDH_Ventilator(name='')
        NurseDH_Gen(name='')
        NurseDH_Oxygen(name='')
        NurseDH_Ventilator(name='')
        RetestingDH(name='')

        # Covid centre

        isolation_bed = sim.Resource("Isolation beds", capacity=cc_iso_bed)
        G_bed = sim.Resource("General beds", capacity=cc_gen_bed)
        O_bed = sim.Resource("Oxygen beds", capacity=cc_ox_bed)
        V_bed = sim.Resource("Ventilator beds", capacity=cc_ven_bed)
        cc_iso_q = sim.Queue()
        # nurses

        G_nurse = sim.Resource("General ward nurse", capacity=cc_gen_nurse_cap)  # total 15 doctors in 3 shifts
        O_nurse = sim.Resource("Oxygen ward nurse", capacity=cc_ox_nurse_cap)  # this is per shift
        V_nurse = sim.Resource("Ventilator ward nurse", capacity=cc_ven_nurse_cap)

        # Doctors
        G_doctor = sim.Resource("General ward doctor", capacity=cc_gen_doc_cap)
        O_doctor = sim.Resource("Oxygen ward doctor", capacity=cc_ox_doc_cap)
        V_doctor = sim.Resource("Ventilator ward doctor", capacity=cc_ven_doc_cap)
        cc_ventilator_TypeF(name='')
        env.run(till=(warmup_time + run_time))

        isolation_bed.print_statistics()
        print("Replications completed {}".format(i + 1))
        # adding entries in arrays. these are used for replication wise data

        # adding entries in arrays. these are used for replication wise data
        # 1. Registration data
        array_registration_time.append(registration_time)
        array_registration_q_waiting_time.append(np.mean(np.array(registration_q_waiting_time)))
        array_registration_q_length.append(registration_q.length[warmup_time].mean())
        array_registration_occupancy.append(registration_time / (run_time * reg_clerks / 3))
        array_total_patients.append(total_opds)
        # 2. OPD medicine data
        array_medicine_count.append(medicine_count)
        array_opd_patients.append(PatientGenerator.total_OPD_patients)
        array_medicine_doctor_occupancy.append(
            ((admin_work_chc1 + medicine_cons_time + covid_patient_time_chc1) / (420 * day * months * doc_cap)))
        array_opd_q_waiting_time.append(np.mean(np.array(opd_q_waiting_time)))
        array_opd_q_man_wait_time.append(np.array(medicine_q.length_of_stay[warmup_time].mean()))
        array_opd_q_length.append(medicine_q.length[warmup_time].mean())
        # 3. NCD nurse data
        array_ncd_count.append(ncd_count)
        array_ncd_occupancy.append((ncd_time / (run_time / 3)))
        # 4. Pharmacy data
        array_pharmacy_time.append(pharmacy_time)
        array_pharmacy_occupancy.append(
            (admin_work_chc1 + pharmacy_time) / (480 * 2 * day * months))  # 2 is the capacity, 3 is shifts in a day
        array_pharmacy_q_waiting_time.append(np.mean(np.array(pharmacy_q_waiting_time)))
        array_pharmacy_q_length.append(pharmacy_q.length[warmup_time].mean())
        array_pharmacy_count.append(pharmacy_count)
        # 5. Lab data
        array_lab_count.append(lab_count)
        array_lab_occupancy.append((lab_time) / (420 * day * months * 2))  # 2 is the capacity, 3 is shifts in a day
        array_lab_q_waiting_time.append(np.mean(np.array(lab_q_waiting_time)))
        array_lab_q_length.append(lab_q.length[warmup_time].mean())

        # 8. Emergency data
        array_emr_count.append(emergency_count)
        emr_q_los.append(e_beds.requesters().length_of_stay[warmup_time].mean())
        array_emr_q_length_of_stay.append(emr_q.length_of_stay[warmup_time].mean())
        array_emr_bed_occupancy.append(emergency_bed_time / (3 * run_time))
        array_emr_doc_occupancy.append((emergency_time + MO_del_time + admin_work_chc1 * 2) / (
                run_time / 2))  # multiplying by 3 because the admin time is for all 3 doctors individually

        array_emr_staffnurse_occupancy.append((emergency_nurse_time + admin_work_chc1) / run_time)
        array_emr_bed_occupancy1.append(e_beds.occupancy[warmup_time].mean())
        array_emergency_refer.append(emergency_refer)
        array_emr_q_length.append(emr_q.length[warmup_time].mean())
        array_emr_q_waiting_time.append((np.sum(np.array(emr_q_waiting_time))) / len(emr_q_waiting_time))
        # 9. Delivery data
        array_referred.append(referred)
        array_del_count.append(delivery_count)
        array_del_bed_occupancy.append(delivery_bed.occupancy[warmup_time].mean())
        array_del_nurse_occupancy.append(delivery_nurse_time / run_time)
        array_childbirth_referred.append(childbirth_referred)
        array_childbirth_count.append(childbirth_count)
        # 10. Inpatient data
        array_ipd_bed_occupancy.append(in_beds.occupancy[warmup_time].mean())
        array_ipd_MO_occupancy.append((ipd_MO_time_chc1 + MO_covid_time_chc1 + admin_work_chc1 * 3) / (
                months * day * 21 * 60))  # multiplying by 3 because the admin time is for all 3 doctors individually
        array_ipd_staffnurse_occupancy.append(ipd_nurse.occupancy[warmup_time].mean())
        array_staffnurse_occupancy.append((ipd_nurse_time + admin_work_chc1) / (months * day * 21 * 60))
        array_ipd_count.append(inpatient_count)
        array_ipd_del_count.append(inpatient_del_count)
        array_emer_inpatients.append(emer_inpatients)
        array_ipd_surgery_count.append(ipd_surgery_count)
        array_ipd_bed_time_m.append(ipd_bed_time / (run_time * ip_bed_cap))
        array_ip_waiting_time_chc1.append(in_beds.requesters().length_of_stay[warmup_time].mean())
        array_ip_q_length.append(ipd_q.length[warmup_time].mean())
        # 11. OT data
        array_ot_count.append(surgery_count)
        array_ot_doc_occupancy.append(sur_time / run_time)
        array_ot_anasthetic_occupancy.append(ans_time / run_time)
        array_ot_nurse_occupancy.append(ot_nurse_time / run_time)
        # 12. Xray variables
        array_xray_occupancy.append((xray_time + admin_work_chc1) / run_time)
        array_xray_q_waiting_time.append((np.sum(np.array(xray_q_waiting_time)) / len(xray_q_waiting_time)))
        array_xray_q_length.append(xray_q.length[warmup_time].mean())
        array_xray_count.append(xray_count)
        array_radio_q_waiting_time_sys.append(xray_q.length_of_stay[warmup_time].mean())
        array_xray_time.append(xray_time)
        # 13. ECG variables
        array_ecg_count.append(ecg_count)
        array_ecg_occupancy.append((xray_time + admin_work_chc1) / run_time)
        array_ecg_q_waiting_time.append((np.sum(np.array(ecg_q_waiting_time)) / len(ecg_q_waiting_time)))
        array_ecg_q_length.append(ecg_q.length[warmup_time].mean())
        array_ecg_time.append(xray_time)
        # covid
        array_covid_bed_occupancy.append(covid_bed_chc1.occupancy[warmup_time].mean())
        chc1_max_bed_occ_covid.append(covid_bed_chc1.occupancy[warmup_time].maximum())

        array_covid_q_length.append(covid_bed_chc1.requesters().length[warmup_time].mean())
        array_covid_bed_waiting_time.append(covid_bed_chc1.requesters().length_of_stay[warmup_time].mean())
        array_phc2chc_count.append(phc2chc_count + phc2chc_count_PHC2 + phc2chc_count_PHC3 + phc2chc_count_PHC4)
        array_covid_count.append(covid_count)
        array_isolation_ward_refer_from_CHC.append(isolation_ward_refer_from_CHC)
        array_c_bed_wait.append(np.mean(np.array(c_bed_wait)))
        array_moderate_refered_chc1.append(moderate_refered_chc1)
        array_ipd_bed_wt_chc2.append(np.mean(np.array(ipd_bed_wt_chc2)))
        array_ipd_bed_wt_chc1.append(np.mean(np.array(ipd_bed_wt_chc1)))
        array_ipd_bed_wt_chc3.append(np.mean(np.array(ipd_bed_wt_chc3)))
        array_dh_refer_chc1.append(dh_refer_chc1)
        array_chc1_covid_bed_occ.append(chc1_covid_bed_time / (run_time * covid_bed_cap_chc1))
        array_q_len_chc1.append(np.mean(np.array(q_len_chc1)))

        # CHC 2
        array_q_len_chc2.append(np.mean(np.array(q_len_chc2)))
        # adding entries in arrays. these are used for replication wise data
        # 1. Registration data
        array_registration_time_chc2.append(registration_time_chc2)
        array_registration_q_waiting_time_chc2.append(np.mean(np.array(registration_q_waiting_time_chc2)))
        array_registration_q_length_chc2.append(registration_q_chc2.length[warmup_time].mean())
        array_registration_occupancy_chc2.append(registration_time_chc2 / (run_time * reg_clerks / 3))
        array_total_patients_chc2.append(total_opds_chc2)
        # 2. OPD medicine data
        array_medicine_count_chc2.append(medicine_count_chc2)
        array_opd_patients_chc2.append(PatientGenerator_chc2.total_OPD_patients_chc2)
        array_medicine_doctor_occupancy_chc2.append(
            ((admin_work_chc2 + medicine_cons_time_chc2 + covid_patient_time_chc2) / (
                    420 * day * months * doc_cap_chc2)))
        array_opd_q_waiting_time_chc2.append(np.mean(np.array(opd_q_waiting_time_chc2)))
        array_opd_q_length_chc2.append(medicine_q_chc2.length[warmup_time].mean())
        # 3. NCD nurse data
        array_ncd_count_chc2.append(ncd_count_chc2)
        array_ncd_occupancy_chc2.append((ncd_time_chc2 / (run_time / 3)))
        # 4. Pharmacy data
        array_pharmacy_time_chc2.append(pharmacy_time_chc2)
        array_pharmacy_occupancy_chc2.append(
            (pharmacy_time_chc2) / (420 * 2 * day * months))  # 2 is the capacity, 3 is shifts in a day
        array_pharmacy_q_waiting_time_chc2.append(np.mean(np.array(pharmacy_q_waiting_time_chc2)))
        array_pharmacy_q_length_chc2.append(pharmacy_q_chc2.length[warmup_time].mean())
        array_pharmacy_count_chc2.append(pharmacy_count_chc2)
        # 5. Lab data
        array_lab_count_chc2.append(lab_count_chc2)
        array_lab_occupancy_chc2.append(
            (lab_time_chc2) / (420 * day * months * 2))  # 2 is the capacity, 3 is shifts in a day
        array_lab_q_waiting_time_chc2.append(np.mean(np.array(lab_q_waiting_time_chc2)))
        array_lab_q_length_chc2.append(lab_q_chc2.length[warmup_time].mean())
        # 7. Pediatrics OPD data
        array_ped_count_chc2.append(ped_count_chc2)
        array_ped_occupancy_chc2.append((ped_time_chc2) / (run_time / 3))  # 3 is shifts in a day
        array_ped_q_waiting_time_chc2.append(np.mean(np.array(ped_q_waiting_time_chc2)))
        array_ped_q_length_chc2.append(ped_q_chc2.length[warmup_time].mean())
        # 7. Dental OPD data
        array_den_count_chc2.append(den_count_chc2)
        array_den_proced_chc2.append(den_proced_chc2)
        array_den_cons_chc2.append(den_consul_chc2)
        array_den_occupancy_chc2.append((den_time_chc2 + admin_work_chc2) / (420 * day * months))
        # array_den_q_waiting_time.append((np.mean(np.array(den_q_waiting_time))))
        array_den_q_waiting_time_chc2.append((np.average(np.array(den_q_waiting_time_chc2))))
        array_den_q_length_chc2.append(den_q_chc2.length[warmup_time].mean())

        # 8. Emergency data
        array_emr_count_chc2.append(emergency_count_chc2)
        emr_q_los_chc2.append(e_beds_chc2.requesters().length_of_stay[warmup_time].mean())
        array_emr_q_length_of_stay_chc2.append(emr_q_chc2.length_of_stay[warmup_time].mean())
        array_emr_bed_occupancy_chc2.append(emergency_bed_time_chc2 / (3 * run_time))
        array_emr_doc_occupancy_chc2.append((emergency_time_chc2 + MO_del_time_chc2 + admin_work_chc2) / (
                21 * 60 * months * day / 2))  # multiplying by 3 because the admin time is for all 3 doctors individually

        array_emr_staffnurse_occupancy_chc2.append(
            (emergency_nurse_time_chc2 + admin_work_chc2) / 21 * 60 * months * day)
        array_emr_bed_occupancy1_chc2.append(e_beds_chc2.occupancy[warmup_time].mean())
        array_emergency_refer_chc2.append(emergency_refer_chc2)
        array_emr_q_length_chc2.append(emr_q_chc2.length[warmup_time].mean())
        array_emr_q_waiting_time_chc2.append((np.average(np.array(emr_q_waiting_time_chc2))))
        # 9. Delivery data
        array_referred.append(referred_chc2)
        array_del_count_chc2.append(delivery_count_chc2)
        array_del_bed_occupancy_chc2.append(delivery_bed_chc2.occupancy[warmup_time].mean())
        array_del_nurse_occupancy_chc2.append(delivery_nurse_time_chc2 / run_time)
        array_childbirth_referred_chc2.append(childbirth_referred_chc2)
        array_childbirth_count_chc2.append(childbirth_count_chc2)
        # 10. Inpatient data
        array_ipd_bed_occupancy_chc2.append(in_beds_chc2.occupancy[warmup_time].mean())
        array_ipd_MO_occupancy_chc2.append((ipd_MO_time_chc2 +
                                            MO_covid_time_chc2 + admin_work_chc2 * 3) / (
                                                   months * day * 21 * 60))  # multiplying by 3 because the admin time is for all 3 doctors individually

        array_ipd_staffnurse_occupancy_chc2.append(ipd_nurse_chc2.occupancy[warmup_time].mean())
        array_staffnurse_occupancy_chc2.append((ipd_nurse_time_chc2 + admin_work_chc2) / (months * day * 21 * 60))
        array_ipd_count_chc2.append(inpatient_count_chc2)
        array_ipd_del_count_chc2.append(inpatient_del_count_chc2)
        array_emer_inpatients_chc2.append(emer_inpatients_chc2)
        array_ipd_surgery_count_chc2.append(ipd_surgery_count_chc2)
        array_ipd_bed_time_m_chc2.append(ipd_bed_time_chc2 / (run_time * ip_bed_cap_chc2))
        array_ip_waiting_time_chc2.append(in_beds_chc2.requesters().length_of_stay
                                          [warmup_time].mean())
        array_ip_q_length_chc2.append(ipd_q_chc2.length[warmup_time].mean())
        # 11. OT data
        array_ot_count_chc2.append(surgery_count_chc2)
        array_ot_doc_occupancy_chc2.append(sur_time_chc2 / run_time)
        array_ot_anasthetic_occupancy_chc2.append(ans_time_chc2 / run_time)
        array_ot_nurse_occupancy_chc2.append(ot_nurse_time_chc2 / run_time)
        # 12. Xray variables
        array_xray_occupancy_chc2.append((xray_time_chc2) / (run_time / 3))
        array_xray_q_waiting_time_chc2.append(
            (np.sum(np.average(xray_q_waiting_time_chc2))))
        array_xray_q_length_chc2.append(xray_q_chc2.length[warmup_time].mean())
        array_xray_count_chc2.append(xray_count_chc2)
        array_radio_q_waiting_time_sys_chc2.append(xray_q_chc2.length_of_stay[warmup_time].mean())
        array_xray_time_chc2.append(xray_time_chc2)
        # 13. ECG variables
        array_ecg_count_chc2.append(ecg_count_chc2)
        array_ecg_occupancy_chc2.append((xray_time_chc2) / run_time / 3)
        array_ecg_q_waiting_time_chc2.append((np.average(np.array(ecg_q_waiting_time_chc2))))
        array_ecg_q_length_chc2.append(ecg_q_chc2.length[warmup_time].mean())
        array_ecg_time_chc2.append(xray_time_chc2)
        # covid
        chc2_max_bed_occ_covid.append(covid_bed_chc2.occupancy[warmup_time].maximum())
        array_covid_bed_occupancy_chc2.append(covid_bed_chc2.occupancy[warmup_time].mean())
        array_covid_q_length_chc2.append(covid_bed_chc2.requesters().length[warmup_time].mean())
        array_covid_bed_waiting_time_chc2.append(covid_bed_chc2.requesters().length_of_stay[warmup_time].mean())
        array_phc2chc_count_chc2.append(phc2chc_count_PHC5 + phc2chc_count_PHC6 + phc2chc_count_PHC7)
        array_covid_count_chc2.append(covid_count_chc2)
        array_isolation_ward_refer_from_CHC_chc2.append(isolation_ward_refer_from_CHC_chc2)
        array_moderate_refered_chc2.append(moderate_refered_chc2)
        array_chc2_covid_bed_occ.append(chc2_covid_bed_time / (run_time * covid_bed_cap_chc2))
        array_dh_refer_chc2.append(dh_refer_chc2)
        array_c_bed_wait_chc2.append(np.mean(np.array(c_bed_wait_chc2)))

        # CHC 3
        array_q_len_chc3.append(np.mean(np.array(q_len_chc3)))
        # adding entries in arrays. these are used for replication wise data
        # 1. Registration data
        array_registration_time_chc3.append(registration_time_chc3)
        array_registration_q_waiting_time_chc3.append(np.mean(np.array(registration_q_waiting_time_chc3)))
        array_registration_q_length_chc3.append(registration_q_chc3.length[warmup_time].mean())
        array_registration_occupancy_chc3.append(registration_time_chc3 / (run_time * reg_clerks / 3))
        array_total_patients_chc3.append(total_opds_chc3)
        # 2. OPD medicine data
        array_medicine_count_chc3.append(medicine_count_chc3)
        array_opd_patients_chc3.append(PatientGenerator_chc3.total_OPD_patients_chc2)
        array_medicine_doctor_occupancy_chc3.append(
            ((admin_work_chc3 + medicine_cons_time_chc3 + covid_patient_time_chc3) / (
                    420 * day * months * doc_cap_chc3)))
        array_opd_q_waiting_time_chc3.append(np.mean(np.array(opd_q_waiting_time_chc3)))
        array_opd_q_length_chc3.append(medicine_q_chc3.length[warmup_time].mean())
        # 3. NCD nurse data
        array_ncd_count_chc3.append(ncd_count_chc3)
        array_ncd_occupancy_chc3.append((ncd_time_chc3 / (run_time / 3)))
        # 4. Pharmacy data
        array_pharmacy_time_chc3.append(pharmacy_time_chc3)
        array_pharmacy_occupancy_chc3.append(
            pharmacy_time_chc3 / (420 * 2 * day * months))  # 2 is the capacity, 3 is shifts in a day
        array_pharmacy_q_waiting_time_chc3.append(np.mean(np.array(pharmacy_q_waiting_time_chc3)))
        array_pharmacy_q_length_chc3.append(pharmacy_q_chc3.length[warmup_time].mean())
        array_pharmacy_count_chc3.append(pharmacy_count_chc3)
        # 5. Lab data
        array_lab_count_chc3.append(lab_count_chc3)
        array_lab_occupancy_chc3.append(
            (lab_time_chc3) / (420 * day * months * 2))  # 2 is the capacity, 3 is shifts in a day
        array_lab_q_waiting_time_chc3.append(np.mean(np.array(lab_q_waiting_time_chc3)))
        array_lab_q_length_chc3.append(lab_q_chc3.length[warmup_time].mean())
        # 7. Pediatrics OPD data
        array_ped_count_chc3.append(ped_count_chc3)
        array_ped_occupancy_chc3.append((ped_time_chc3) / (run_time / 3))  # 3 is shifts in a day
        array_ped_q_waiting_time_chc3.append(np.mean(np.array(ped_q_waiting_time_chc3)))
        array_ped_q_length_chc3.append(ped_q_chc3.length[warmup_time].mean())
        # 7. Dental OPD data
        array_den_count_chc3.append(den_count_chc3)
        array_den_proced_chc3.append(den_proced_chc3)
        array_den_cons_chc3.append(den_consul_chc3)
        array_den_occupancy_chc3.append((den_time_chc3) / (480 * day * months))
        # array_den_q_waiting_time.append((np.mean(np.array(den_q_waiting_time))))
        array_den_q_waiting_time_chc3.append(np.average(np.array(den_q_waiting_time_chc3)))
        array_den_q_length_chc3.append(den_q_chc3.length[warmup_time].mean())

        # 8. Emergency data
        array_emr_count_chc3.append(emergency_count_chc3)
        emr_q_los_chc3.append(e_beds_chc3.requesters().length_of_stay[warmup_time].mean())
        array_emr_q_length_of_stay_chc3.append(emr_q_chc3.length_of_stay[warmup_time].mean())
        array_emr_bed_occupancy_chc3.append(emergency_bed_time_chc3 / (3 * run_time))
        array_emr_doc_occupancy_chc3.append((emergency_time_chc3 + MO_del_time_chc3 + admin_work_chc3 * 2) / (
                run_time / 2))  # multiplying by 3 because the admin time is for all 3 doctors individually

        array_emr_staffnurse_occupancy_chc3.append((emergency_nurse_time_chc3 + admin_work_chc3) / run_time)
        array_emr_bed_occupancy1_chc3.append(e_beds_chc3.occupancy[warmup_time].mean())
        array_emergency_refer_chc3.append(emergency_refer_chc3)
        array_emr_q_length_chc3.append(emr_q_chc3.length[warmup_time].mean())
        array_emr_q_waiting_time_chc3.append((np.average(np.array(emr_q_waiting_time_chc3))))
        # 9. Delivery data
        array_referred_chc3.append(referred_chc3)
        array_del_count_chc3.append(delivery_count_chc3)
        array_del_bed_occupancy_chc3.append(delivery_bed_chc3.occupancy[warmup_time].mean())
        array_del_nurse_occupancy_chc3.append(delivery_nurse_time_chc3 / run_time)
        array_childbirth_referred_chc3.append(childbirth_referred_chc3)
        array_childbirth_count_chc3.append(childbirth_count_chc3)
        # 10. Inpatient data
        array_ipd_bed_occupancy_chc3.append(in_beds_chc3.occupancy[warmup_time].mean())
        array_ipd_MO_occupancy_chc3.append((ipd_MO_time_chc3 +
                                            MO_covid_time_chc3 + admin_work_chc3 * 3) / (
                                                   months * day * 21 * 60))  # multiplying by 3 because the admin time is for all 3 doctors individually
        chc3_ipd_occupancy.append(in_beds_chc3.occupancy[warmup_time].mean())
        chc3_ipd_wait.append(in_beds_chc3.requesters().length_of_stay[warmup_time].mean())
        array_ipd_staffnurse_occupancy_chc3.append(ipd_nurse_chc3.occupancy[warmup_time].mean())
        array_staffnurse_occupancy_chc3.append((ipd_nurse_time_chc3 + admin_work_chc3) / (months * day * 21 * 60))
        array_ipd_count_chc3.append(inpatient_count_chc3)
        array_ipd_del_count_chc3.append(inpatient_del_count_chc3)
        array_emer_inpatients_chc3.append(emer_inpatients_chc3)
        array_ipd_surgery_count_chc3.append(ipd_surgery_count_chc3)
        array_ipd_bed_time_m_chc3.append(ipd_bed_time_chc3 / (run_time * ip_bed_cap_chc3))
        array_ip_waiting_time_chc3.append(
            in_beds_chc3.requesters().length_of_stay[warmup_time].mean())
        array_ip_q_length_chc3.append(ipd_q_chc3.length[warmup_time:warmup_time + run_time].mean())
        # 11. OT data
        array_ot_count_chc3.append(surgery_count_chc3)
        array_ot_doc_occupancy_chc3.append(sur_time_chc3 / run_time / 3)
        array_ot_anasthetic_occupancy_chc3.append(ans_time_chc3 / run_time / 3)
        array_ot_nurse_occupancy_chc3.append(ot_nurse_time_chc3 / run_time / 3)
        # 12. Xray variables
        array_xray_occupancy_chc3.append((xray_time_chc3 + admin_work_chc3) / run_time)
        array_xray_q_waiting_time_chc3.append(
            (np.average(np.array(xray_q_waiting_time_chc3))))
        array_xray_q_length_chc3.append(xray_q_chc3.length[warmup_time].mean())
        array_xray_count_chc3.append(xray_count_chc3)
        array_radio_q_waiting_time_sys_chc3.append(xray_q_chc3.length_of_stay[warmup_time].mean())
        array_xray_time_chc3.append(xray_time_chc3)
        # 13. ECG variables
        array_ecg_count_chc3.append(ecg_count_chc3)
        array_ecg_occupancy_chc3.append((xray_time_chc3 + admin_work_chc3) / run_time)
        array_ecg_q_waiting_time_chc3.append((np.average(np.array(ecg_q_waiting_time_chc3))))
        array_ecg_q_length_chc3.append(ecg_q_chc3.length[warmup_time].mean())
        array_ecg_time_chc3.append(xray_time_chc3)
        # covid
        chc3_max_bed_occ_covid.append(covid_bed_chc3.occupancy[warmup_time].maximum())
        array_covid_bed_occupancy_chc3.append(covid_bed_chc3.occupancy[warmup_time].mean())
        array_covid_q_length_chc3.append(covid_bed_chc3.requesters().length[warmup_time].mean())
        array_covid_bed_waiting_time_chc3.append(covid_bed_chc3.requesters().length_of_stay[warmup_time].mean())
        array_phc2chc_count_chc3.append(phc2chc_count_PHC8 + phc2chc_count_PHC9 + phc2chc_count_PHC10)
        array_covid_count_chc3.append(covid_count_chc3)
        array_isolation_ward_refer_from_CHC_chc3.append(isolation_ward_refer_from_CHC_chc3)
        array_moderate_refered_chc3.append(moderate_refered_chc3)
        array_dh_refer_chc3.append(dh_refer_chc3)
        array_c_bed_wait_chc3.append(np.mean(np.array(c_bed_wait_chc3)))
        array_chc3_covid_bed_occ.append(chc3_covid_bed_time / (run_time * covid_bed_cap_chc3))
        totaldistance = 0
        # all chcs inter facility distance
        array_chc3_to_dh.append(np.sum(np.array(chc3_to_dh_dist)))
        array_chc3_to_cc.append(np.sum(np.array(chc3_to_cc_dist)))
        array_chc2_to_dh.append(np.sum(np.array(chc2_to_dh_dist)))
        array_chc2_to_cc.append(np.sum(np.array(chc2_to_cc_dist)))
        array_chc1_to_dh.append(np.sum(np.array(chc1_to_dh_dist)))
        array_chc1_to_cc.append(np.sum(np.array(chc1_to_cc_dist)))

        array_chc1_severe_covid.append(chc1_severe_covid)
        array_chc1_moderate_covid.append(chc1_moderate_covid)
        array_chc2_severe_covid.append(chc2_severe_covid)
        array_chc2_moderate_covid.append(chc2_moderate_covid)
        array_chc3_severe_covid.append(chc3_severe_covid)
        array_chc3_moderate_covid.append(chc3_moderate_covid)

        # PHC1
        # adding entries in arrays. these are used for replication wise data
        # 1. OPD medicine data
        array_medicine_count1.append(medicine_count1)
        array_opd_patients1.append(PatientGenerator1.total_OPD_patients)
        array_phc1_doc_time.append(phc1_doc_time / (420 * doc_cap1 * 360))
        array_medicine_doctor_occupancy1.append(((medicine_cons_time1 + ipd_MO_time1 + MO_del_time1) /
                                                 (420 * day * months * doc_cap1)))
        array_medicine_doctor_occupancy212.append(medicine_cons_time1 / (420 * day * months * doc_cap1))
        array_opd_q_waiting_time1.append(np.mean(np.array(opd_q_waiting_time1)))
        array_opd_q_length1.append(medicine_q1.length[warmup_time].mean())
        # 2. NCD nurse data
        array_ncd_count1.append(ncd_count1)
        array_ncd_occupancy1.append(((ncd_time1 + admin_work1) / (420 * day * months)))
        # 3. Pharmacy data
        array_pharmacy_time1.append(pharmacy_time1)
        array_pharmacy_occupancy1.append(
            (pharmacy_time1) / (420 * 1 * day * months))  # 2 is the capacity, 3 is shifts in a day
        array_pharmacy_q_waiting_time1.append(np.mean(np.array(pharmacy_q_waiting_time1)))
        array_pharmacy_q_length1.append(pharmacy_q1.length[warmup_time].mean())
        array_pharmacy_count1.append(pharmacy_count1)
        # 4. Lab data
        array_lab_count1.append(lab_count1)
        array_lab_occupancy1.append((lab_time1) / (420 * day * months))  # 2 is the capacity, 3 is shifts in a day
        array_lab_q_waiting_time1.append(np.mean(np.array(lab_q_waiting_time1)))
        array_lab_q_length1.append(lab_q1.length[warmup_time].mean())
        # 9. Delivery data
        array_referred1.append(referred)
        array_del_count1.append(delivery_count1)
        # array_del_bed_occupancy1.append(delivery_bed1.occupancy[3*30*24*60: 3*30*24*60 + 12*30*24*60].mean())
        array_del_bed_occupancy1.append(
            delivery_bed1.occupancy[warmup_time].mean())

        array_childbirth_referred1.append(fail_count1)
        array_childbirth_count1.append(childbirth_count1)
        # 10. Inpatient data
        array_ipd_bed_occupancy1.append(
            in_beds1.occupancy[3 * 30 * 24 * 60:3 * 30 * 24 * 60 + 12 * 30 * 24 * 60].mean())
        # array_ipd_MO_occupancy1.append((ipd_MO_time1 + MO_covid_time1 + admin_work1 * 3) / run_time)  # multiplying by 3 because the admin time is for all 3 doctors individually
        array_ipd_staffnurse_occupancy1.append(ipd_nurse1.occupancy[warmup_time].mean())
        # changed here, below. Admin time changed and denominator (months*day*hours*minutes)
        # changed here
        # for PHC staff nurse we have taken 1 hour of admin time per nurse per day
        array_staffnurse_occupancy1.append(
            (delivery_nurse_time1 + ipd_nurse_time1 + (180 * day * months)) / (months * day * 21 * 60))
        array_ipd_count1.append(inpatient_count1)
        array_ipd_bed_time_m1.append(ipd_bed_time1 / (run_time * ip_bed_cap1))
        array_ip_waiting_time1.append(in_beds1.requesters().length_of_stay[warmup_time].mean())
        # covid
        array_covid_count1.append(covid_count1)
        array_chc_refer1.append(chc_refer1)
        array_dh_refer1.append(dh_refer1)
        array_isolation_ward_refer1.append(isolation_ward_refer1)
        array_lab_covidcount1.append(lab_covidcount1)
        array_retesting_count1.append(retesting_count1)
        array_home_isolation_PHC1.append(home_isolation_PHC1)

        # PHC 2
        # adding entries in arrays. these are used for replication wise data
        # 1. OPD medicine data
        array_medicine_count_PHC2.append(medicine_count_PHC2)
        array_opd_patients_PHC2.append(PatientGenerator_PHC2.total_OPD_patients_PHC2)
        array_phc1_doc_time_PHC2.append(phc1_doc_time_PHC2 / (420 * doc_cap_PHC2 * 360))
        array_medicine_doctor_occupancy_PHC2.append(((medicine_cons_time_PHC2 + ipd_MO_time_PHC2 + MO_del_time_PHC2) /
                                                     (420 * day * months * doc_cap_PHC2)))
        array_medicine_doctor_occupancy212_PHC2.append(medicine_cons_time_PHC2 / (420 * day * months * doc_cap_PHC2))
        array_opd_q_waiting_time_PHC2.append(np.mean(np.array(opd_q_waiting_time_PHC2)))
        array_opd_q_length_PHC2.append(medicine_q_PHC2.length[warmup_time].mean())
        # 2. NCD nurse data
        array_ncd_count_PHC2.append(ncd_count_PHC2)
        array_ncd_occupancy_PHC2.append(((ncd_time_PHC2 + admin_work1) / (420 * day * months)))
        # 3. Pharmacy data
        array_pharmacy_time_PHC2.append(pharmacy_time_PHC2)
        array_pharmacy_occupancy_PHC2.append(
            (pharmacy_time_PHC2) / (420 * 1 * day * months))  # 2 is the capacity, 3 is shifts in a day
        array_pharmacy_q_waiting_time_PHC2.append(np.mean(np.array(pharmacy_q_waiting_time_PHC2)))
        array_pharmacy_q_length_PHC2.append(pharmacy_q_PHC2.length[warmup_time].mean())
        array_pharmacy_count_PHC2.append(pharmacy_count_PHC2)
        # 4. Lab data
        array_lab_count_PHC2.append(lab_count_PHC2)
        array_lab_occupancy_PHC2.append(
            (lab_time_PHC2) / (420 * day * months))  # 2 is the capacity, 3 is shifts in a day
        array_lab_q_waiting_time_PHC2.append(np.mean(np.array(lab_q_waiting_time_PHC2)))
        array_lab_q_length_PHC2.append(lab_q_PHC2.length[warmup_time].mean())
        # 9. Delivery data
        array_referred2.append(referred_PHC2)
        array_del_count_PHC2.append(delivery_count_PHC2)
        # array_del_bed_occupancy1.append(delivery_bed1.occupancy[3*30*24*60: 3*30*24*60 + 12*30*24*60].mean())
        array_del_bed_occupancy_PHC2.append(
            delivery_bed_PHC2.occupancy[warmup_time].mean())

        array_childbirth_referred_PHC2.append(fail_count_PHC2)
        array_childbirth_count_PHC2.append(childbirth_count_PHC2)
        # 10. Inpatient data
        array_ipd_bed_occupancy_PHC2.append(
            in_beds_PHC2.occupancy[3 * 30 * 24 * 60:3 * 30 * 24 * 60 + 12 * 30 * 24 * 60].mean())
        # array_ipd_MO_occupancy1.append((ipd_MO_time1 + MO_covid_time1 + admin_work1 * 3) / run_time)  # multiplying by 3 because the admin time is for all 3 doctors individually
        array_ipd_staffnurse_occupancy_PHC2.append(ipd_nurse_PHC2.occupancy[warmup_time].mean())
        # changed here, below. Admin time changed and denominator (months*day*hours*minutes)
        # changed here
        array_staffnurse_occupancy_PHC2.append(
            (delivery_nurse_time_PHC2 + ipd_nurse_time_PHC2 + (180 * day * months)) / (months * day * 21 * 60))
        array_ipd_count_PHC2.append(inpatient_count_PHC2)
        array_ipd_bed_time_m_PHC2.append(ipd_bed_time_PHC2 / (run_time * ip_bed_cap_PHC2))
        array_ip_waiting_time_PHC2.append(in_beds_PHC2.requesters().length_of_stay[warmup_time].mean())
        # covid
        array_covid_count_PHC2.append(covid_count_PHC2)
        array_chc_refer_PHC2.append(chc_refer_PHC2)
        array_dh_refer_PHC2.append(dh_refer_PHC2)
        array_isolation_ward_refer_PHC2.append(isolation_ward_refer_PHC2)
        array_lab_covidcount_PHC2.append(lab_covidcount_PHC2)
        array_retesting_count_PHC2.append(retesting_count_PHC2)
        array_home_isolation_PHC2.append(home_isolation_PHC2)

        # PHC 3
        # adding entries in arrays. these are used for replication wise data
        # 1. OPD medicine data
        array_medicine_count_PHC3.append(medicine_count_PHC3)
        array_opd_patients_PHC3.append(PatientGenerator_PHC3.total_OPD_patients_PHC3)
        array_phc1_doc_time_PHC3.append(phc1_doc_time_PHC3 / (420 * doc_cap_PHC3 * day * months))
        array_medicine_doctor_occupancy_PHC3.append(((medicine_cons_time_PHC3 + ipd_MO_time_PHC3 + MO_del_time_PHC3) /
                                                     (420 * day * months * doc_cap_PHC3)))
        array_medicine_doctor_occupancy212_PHC3.append(medicine_cons_time_PHC3 / (420 * day * months * doc_cap_PHC3))
        array_opd_q_waiting_time_PHC3.append(np.mean(np.array(opd_q_waiting_time_PHC3)))
        array_opd_q_length_PHC3.append(medicine_q_PHC3.length[warmup_time].mean())
        # 2. NCD nurse data
        array_ncd_count_PHC3.append(ncd_count_PHC3)
        array_ncd_occupancy_PHC3.append(((ncd_time_PHC3 + admin_work1) / (420 * day * months)))
        # 3. Pharmacy data
        array_pharmacy_time_PHC3.append(pharmacy_time_PHC3)
        array_pharmacy_occupancy_PHC3.append(
            (pharmacy_time_PHC3) / (420 * 1 * day * months))  # 2 is the capacity, 3 is shifts in a day
        array_pharmacy_q_waiting_time_PHC3.append(np.mean(np.array(pharmacy_q_waiting_time_PHC3)))
        array_pharmacy_q_length_PHC3.append(pharmacy_q_PHC3.length[warmup_time].mean())
        array_pharmacy_count_PHC3.append(pharmacy_count_PHC3)
        # 4. Lab data
        array_lab_count_PHC3.append(lab_count_PHC3)
        array_lab_occupancy_PHC3.append(
            (lab_time_PHC3) / (420 * day * months))  # 2 is the capacity, 3 is shifts in a day
        array_lab_q_waiting_time_PHC3.append(np.mean(np.array(lab_q_waiting_time_PHC3)))
        array_lab_q_length_PHC3.append(lab_q_PHC3.length[warmup_time].mean())
        # 9. Delivery data
        array_referred3.append(referred_PHC3)
        array_del_count_PHC3.append(delivery_count_PHC3)
        # array_del_bed_occupancy1.append(delivery_bed1.occupancy[3*30*24*60: 3*30*24*60 + 12*30*24*60].mean())
        array_del_bed_occupancy_PHC3.append(
            delivery_bed_PHC3.occupancy[warmup_time].mean())

        array_childbirth_referred_PHC3.append(fail_count_PHC3)
        array_childbirth_count_PHC3.append(childbirth_count_PHC3)
        # 10. Inpatient data
        array_ipd_bed_occupancy_PHC3.append(
            in_beds_PHC3.occupancy[3 * 30 * 24 * 60:3 * 30 * 24 * 60 + 12 * 30 * 24 * 60].mean())
        # array_ipd_MO_occupancy1.append((ipd_MO_time1 + MO_covid_time1 + admin_work1 * 3) / run_time)  # multiplying by 3 because the admin time is for all 3 doctors individually
        array_ipd_staffnurse_occupancy_PHC3.append(ipd_nurse_PHC3.occupancy[warmup_time].mean())
        # changed here, below. Admin time changed and denominator (months*day*hours*minutes)
        # changed here
        array_staffnurse_occupancy_PHC3.append(
            (delivery_nurse_time_PHC3 + ipd_nurse_time_PHC3 + (180 * day * months)) / (months * day * 21 * 60))
        array_ipd_count_PHC3.append(inpatient_count_PHC3)
        array_ipd_bed_time_m_PHC3.append(ipd_bed_time_PHC3 / (run_time * ip_bed_cap_PHC3))
        array_ip_waiting_time_PHC3.append(in_beds_PHC3.requesters().length_of_stay[warmup_time].mean())
        # covid
        array_covid_count_PHC3.append(covid_count_PHC3)
        array_chc_refer_PHC3.append(chc_refer_PHC3)
        array_dh_refer_PHC3.append(dh_refer_PHC3)
        array_isolation_ward_refer_PHC3.append(isolation_ward_refer_PHC3)
        array_lab_covidcount_PHC3.append(lab_covidcount_PHC3)
        array_retesting_count_PHC3.append(retesting_count_PHC3)
        array_home_isolation_PHC3.append(home_isolation_PHC3)

        # PHC 4
        # adding entries in arrays. these are used for replication wise data
        # 1. OPD medicine data
        array_medicine_count_PHC4.append(medicine_count_PHC4)
        array_opd_patients_PHC4.append(PatientGenerator_PHC4.total_OPD_patients_PHC4)
        array_phc1_doc_time_PHC4.append(phc1_doc_time_PHC4 / (420 * doc_cap_PHC4 * 360))
        array_medicine_doctor_occupancy_PHC4.append(((medicine_cons_time_PHC4 + ipd_MO_time_PHC4 + MO_del_time_PHC4) /
                                                     (420 * day * months * doc_cap_PHC4)))
        array_medicine_doctor_occupancy212_PHC4.append(medicine_cons_time_PHC4 / (420 * day * months * doc_cap_PHC4))
        array_opd_q_waiting_time_PHC4.append(np.mean(np.array(opd_q_waiting_time_PHC4)))
        array_opd_q_length_PHC4.append(medicine_q_PHC4.length[warmup_time].mean())
        # 2. NCD nurse data
        array_ncd_count_PHC4.append(ncd_count_PHC4)
        array_ncd_occupancy_PHC4.append(((ncd_time_PHC4 + admin_work4) / (420 * day * months)))
        # 3. Pharmacy data
        array_pharmacy_time_PHC4.append(pharmacy_time_PHC4)
        array_pharmacy_occupancy_PHC4.append(
            (pharmacy_time_PHC4) / (420 * 1 * day * months))  # 2 is the capacity, 3 is shifts in a day
        array_pharmacy_q_waiting_time_PHC4.append(np.mean(np.array(pharmacy_q_waiting_time_PHC4)))
        array_pharmacy_q_length_PHC4.append(pharmacy_q_PHC4.length[warmup_time].mean())
        array_pharmacy_count_PHC4.append(pharmacy_count_PHC4)
        # 4. Lab data
        array_lab_count_PHC4.append(lab_count_PHC4)
        array_lab_occupancy_PHC4.append(
            (lab_time_PHC4) / (420 * day * months))  # 2 is the capacity, 3 is shifts in a day
        array_lab_q_waiting_time_PHC4.append(np.mean(np.array(lab_q_waiting_time_PHC4)))
        array_lab_q_length_PHC4.append(lab_q_PHC4.length[warmup_time].mean())
        # 9. Delivery data
        # array_referred4.append(referred_PHC4)
        # array_del_count_PHC4.append(delivery_count_PHC4)
        # array_del_bed_occupancy1.append(delivery_bed1.occupancy[3*30*24*60: 3*30*24*60 + 12*30*24*60].mean())
        # array_del_bed_occupancy_PHC3.append(
        #     delivery_bed_PHC3.occupancy[warmup_time].mean())

        # array_childbirth_referred_PHC3.append(fail_count_PHC3)
        # array_childbirth_count_PHC3.append(childbirth_count_PHC3)
        # 10. Inpatient data
        array_ipd_bed_occupancy_PHC4.append(
            in_beds_PHC4.occupancy[3 * 30 * 24 * 60:3 * 30 * 24 * 60 + 12 * 30 * 24 * 60].mean())
        # array_ipd_MO_occupancy1.append((ipd_MO_time1 + MO_covid_time1 + admin_work1 * 3) / run_time)  # multiplying by 3 because the admin time is for all 3 doctors individually
        array_ipd_staffnurse_occupancy_PHC4.append(ipd_nurse_PHC4.occupancy[warmup_time].mean())
        # changed here, below. Admin time changed and denominator (months*day*hours*minutes)
        # changed here
        array_staffnurse_occupancy_PHC4.append(
            (delivery_nurse_time_PHC4 + ipd_nurse_time_PHC4 + (180 * day * months)) / (months * day * 21 * 60))
        array_ipd_count_PHC4.append(inpatient_count_PHC4)
        array_ipd_bed_time_m_PHC4.append(ipd_bed_time_PHC4 / (run_time * ip_bed_cap_PHC4))
        array_ip_waiting_time_PHC4.append(in_beds_PHC4.requesters().length_of_stay[warmup_time].mean())
        # covid
        array_covid_count_PHC4.append(covid_count_PHC4)
        array_chc_refer_PHC4.append(chc_refer_PHC4)
        array_dh_refer_PHC4.append(dh_refer_PHC4)
        array_isolation_ward_refer_PHC4.append(isolation_ward_refer_PHC4)
        array_lab_covidcount_PHC4.append(lab_covidcount_PHC4)
        array_retesting_count_PHC4.append(retesting_count_PHC4)
        array_home_isolation_PHC4.append(home_isolation_PHC4)

        # PHC 5
        # adding entries in arrays. these are used for replication wise data
        # 1. OPD medicine data
        array_medicine_count_PHC5.append(medicine_count_PHC5)
        array_opd_patients_PHC5.append(PatientGenerator_PHC5.total_OPD_patients_PHC5)
        array_phc1_doc_time_PHC5.append(phc1_doc_time_PHC5 / (420 * doc_cap_PHC5 * 360))
        array_medicine_doctor_occupancy_PHC5.append(((medicine_cons_time_PHC5 + ipd_MO_time_PHC5 + MO_del_time_PHC5) /
                                                     (420 * day * months * doc_cap_PHC5)))
        array_medicine_doctor_occupancy212_PHC5.append(medicine_cons_time_PHC5 / (420 * day * months * doc_cap_PHC5))
        array_opd_q_waiting_time_PHC5.append(np.mean(np.array(opd_q_waiting_time_PHC5)))
        array_opd_q_length_PHC5.append(medicine_q_PHC5.length[warmup_time].mean())
        # 2. NCD nurse data
        array_ncd_count_PHC5.append(ncd_count_PHC5)
        array_ncd_occupancy_PHC5.append(((ncd_time_PHC5 + admin_work5) / (420 * day * months)))
        # 3. Pharmacy data
        array_pharmacy_time_PHC5.append(pharmacy_time_PHC5)
        array_pharmacy_occupancy_PHC5.append(
            (pharmacy_time_PHC5) / (420 * 1 * day * months))  # 2 is the capacity, 3 is shifts in a day
        array_pharmacy_q_waiting_time_PHC5.append(np.mean(np.array(pharmacy_q_waiting_time_PHC5)))
        array_pharmacy_q_length_PHC5.append(pharmacy_q_PHC5.length[warmup_time].mean())
        array_pharmacy_count_PHC5.append(pharmacy_count_PHC5)
        # 4. Lab data
        array_lab_count_PHC5.append(lab_count_PHC5)
        array_lab_occupancy_PHC5.append(
            (lab_time_PHC5) / (420 * day * months))  # 2 is the capacity, 3 is shifts in a day
        array_lab_q_waiting_time_PHC5.append(np.mean(np.array(lab_q_waiting_time_PHC5)))
        array_lab_q_length_PHC5.append(lab_q_PHC5.length[warmup_time].mean())
        # 9. Delivery data
        # array_referred3.append(referred_PHC3)
        # array_del_count_PHC3.append(delivery_count_PHC3)
        # # array_del_bed_occupancy1.append(delivery_bed1.occupancy[3*30*24*60: 3*30*24*60 + 12*30*24*60].mean())
        # array_del_bed_occupancy_PHC3.append(
        #     delivery_bed_PHC3.occupancy[warmup_time].mean())
        #
        # array_childbirth_referred_PHC3.append(fail_count_PHC3)
        # array_childbirth_count_PHC3.append(childbirth_count_PHC3)
        # 10. Inpatient data
        array_ipd_bed_occupancy_PHC5.append(
            in_beds_PHC5.occupancy[3 * 30 * 24 * 60:3 * 30 * 24 * 60 + 12 * 30 * 24 * 60].mean())
        # array_ipd_MO_occupancy1.append((ipd_MO_time1 + MO_covid_time1 + admin_work1 * 3) / run_time)  # multiplying by 3 because the admin time is for all 3 doctors individually
        array_ipd_staffnurse_occupancy_PHC5.append(ipd_nurse_PHC5.occupancy[warmup_time].mean())
        # changed here, below. Admin time changed and denominator (months*day*hours*minutes)
        # changed here
        array_staffnurse_occupancy_PHC5.append(
            (delivery_nurse_time_PHC5 + ipd_nurse_time_PHC5 + (180 * day * months)) / (months * day * 21 * 60))
        array_ipd_count_PHC5.append(inpatient_count_PHC5)
        array_ipd_bed_time_m_PHC5.append(ipd_bed_time_PHC5 / (run_time * ip_bed_cap_PHC5))
        array_ip_waiting_time_PHC5.append(in_beds_PHC5.requesters().length_of_stay[warmup_time].mean())
        # covid
        array_covid_count_PHC5.append(covid_count_PHC5)
        array_chc_refer_PHC5.append(chc_refer_PHC5)
        array_dh_refer_PHC5.append(dh_refer_PHC5)
        array_isolation_ward_refer_PHC5.append(isolation_ward_refer_PHC5)
        array_lab_covidcount_PHC5.append(lab_covidcount_PHC5)
        array_retesting_count_PHC5.append(retesting_count_PHC5)
        array_home_isolation_PHC5.append(home_isolation_PHC5)

        # PHC 6
        # adding entries in arrays. these are used for replication wise data
        # 1. OPD medicine data
        array_medicine_count_PHC6.append(medicine_count_PHC6)
        array_opd_patients_PHC6.append(PatientGenerator_PHC6.total_OPD_patients_PHC6)
        array_phc1_doc_time_PHC6.append(phc1_doc_time_PHC6 / (420 * doc_cap_PHC6 * 360))
        array_medicine_doctor_occupancy_PHC6.append(((medicine_cons_time_PHC6 + ipd_MO_time_PHC6 + MO_del_time_PHC6) /
                                                     (420 * day * months * doc_cap_PHC6)))
        array_medicine_doctor_occupancy212_PHC6.append(medicine_cons_time_PHC6 / (420 * day * months * doc_cap_PHC6))
        array_opd_q_waiting_time_PHC6.append(np.mean(np.array(opd_q_waiting_time_PHC6)))
        array_opd_q_length_PHC6.append(medicine_q_PHC6.length[warmup_time].mean())
        # 2. NCD nurse data
        array_ncd_count_PHC6.append(ncd_count_PHC6)
        array_ncd_occupancy_PHC6.append(((ncd_time_PHC6 + admin_work6) / (420 * day * months)))
        # 3. Pharmacy data
        array_pharmacy_time_PHC6.append(pharmacy_time_PHC6)
        array_pharmacy_occupancy_PHC6.append(
            (pharmacy_time_PHC6) / (420 * 1 * day * months))  # 2 is the capacity, 3 is shifts in a day
        array_pharmacy_q_waiting_time_PHC6.append(np.mean(np.array(pharmacy_q_waiting_time_PHC6)))
        array_pharmacy_q_length_PHC6.append(pharmacy_q_PHC6.length[warmup_time].mean())
        array_pharmacy_count_PHC6.append(pharmacy_count_PHC6)
        # 4. Lab data
        array_lab_count_PHC6.append(lab_count_PHC6)
        array_lab_occupancy_PHC6.append(
            (lab_time_PHC6) / (420 * day * months))  # 2 is the capacity, 3 is shifts in a day
        array_lab_q_waiting_time_PHC6.append(np.mean(np.array(lab_q_waiting_time_PHC6)))
        array_lab_q_length_PHC6.append(lab_q_PHC6.length[warmup_time].mean())
        # 9. Delivery data
        array_referred6.append(referred_PHC6)
        array_del_count_PHC6.append(delivery_count_PHC6)
        # array_del_bed_occupancy1.append(delivery_bed1.occupancy[3*30*24*60: 3*30*24*60 + 12*30*24*60].mean())
        array_del_bed_occupancy_PHC6.append(
            delivery_bed_PHC6.occupancy[warmup_time].mean())

        array_childbirth_referred_PHC6.append(fail_count_PHC6)
        array_childbirth_count_PHC6.append(childbirth_count_PHC6)
        # 10. Inpatient data
        array_ipd_bed_occupancy_PHC6.append(
            in_beds_PHC6.occupancy[3 * 30 * 24 * 60:3 * 30 * 24 * 60 + 12 * 30 * 24 * 60].mean())
        # array_ipd_MO_occupancy1.append((ipd_MO_time1 + MO_covid_time1 + admin_work1 * 3) / run_time)  # multiplying by 3 because the admin time is for all 3 doctors individually
        array_ipd_staffnurse_occupancy_PHC6.append(ipd_nurse_PHC6.occupancy[warmup_time].mean())
        # changed here, below. Admin time changed and denominator (months*day*hours*minutes)
        # changed here
        array_staffnurse_occupancy_PHC6.append(
            (delivery_nurse_time_PHC6 + ipd_nurse_time_PHC6 + (180 * day * months)) / (months * day * 21 * 60))
        array_ipd_count_PHC6.append(inpatient_count_PHC6)
        array_ipd_bed_time_m_PHC6.append(ipd_bed_time_PHC6 / (run_time * ip_bed_cap_PHC6))
        array_ip_waiting_time_PHC6.append(in_beds_PHC6.requesters().length_of_stay[warmup_time].mean())
        # covid
        array_covid_count_PHC6.append(covid_count_PHC6)
        array_chc_refer_PHC6.append(chc_refer_PHC6)
        array_dh_refer_PHC6.append(dh_refer_PHC6)
        array_isolation_ward_refer_PHC6.append(isolation_ward_refer_PHC6)
        array_lab_covidcount_PHC6.append(lab_covidcount_PHC6)
        array_retesting_count_PHC6.append(retesting_count_PHC6)
        array_home_isolation_PHC6.append(home_isolation_PHC6)

        # PHC 7
        # adding entries in arrays. these are used for replication wise data
        # 1. OPD medicine data
        array_medicine_count_PHC7.append(medicine_count_PHC7)
        array_opd_patients_PHC7.append(PatientGenerator_PHC7.total_OPD_patients_PHC7)
        array_phc1_doc_time_PHC7.append(phc1_doc_time_PHC7 / (420 * doc_cap_PHC7 * 360))
        array_medicine_doctor_occupancy_PHC7.append(((medicine_cons_time_PHC7 + ipd_MO_time_PHC7 + MO_del_time_PHC7) /
                                                     (420 * day * months * doc_cap_PHC7)))
        array_medicine_doctor_occupancy212_PHC7.append(medicine_cons_time_PHC7 / (420 * day * months * doc_cap_PHC7))
        array_opd_q_waiting_time_PHC7.append(np.mean(np.array(opd_q_waiting_time_PHC7)))
        array_opd_q_length_PHC7.append(medicine_q_PHC7.length[warmup_time].mean())
        # 2. NCD nurse data
        array_ncd_count_PHC7.append(ncd_count_PHC7)
        array_ncd_occupancy_PHC7.append(((ncd_time_PHC7 + admin_work7) / (420 * day * months)))
        # 3. Pharmacy data
        array_pharmacy_time_PHC7.append(pharmacy_time_PHC7)
        array_pharmacy_occupancy_PHC7.append(
            (pharmacy_time_PHC7) / (420 * 1 * day * months))  # 2 is the capacity, 3 is shifts in a day
        array_pharmacy_q_waiting_time_PHC7.append(np.mean(np.array(pharmacy_q_waiting_time_PHC7)))
        array_pharmacy_q_length_PHC7.append(pharmacy_q_PHC7.length[warmup_time].mean())
        array_pharmacy_count_PHC7.append(pharmacy_count_PHC7)
        # 4. Lab data
        array_lab_count_PHC7.append(lab_count_PHC7)
        array_lab_occupancy_PHC7.append(
            (lab_time_PHC7) / (420 * day * months))  # 2 is the capacity, 3 is shifts in a day
        array_lab_q_waiting_time_PHC7.append(np.mean(np.array(lab_q_waiting_time_PHC7)))
        array_lab_q_length_PHC7.append(lab_q_PHC7.length[warmup_time].mean())
        # 9. Delivery data
        # array_referred4.append(referred_PHC4)
        # array_del_count_PHC4.append(delivery_count_PHC4)
        # array_del_bed_occupancy1.append(delivery_bed1.occupancy[3*30*24*60: 3*30*24*60 + 12*30*24*60].mean())
        # array_del_bed_occupancy_PHC3.append(
        #     delivery_bed_PHC3.occupancy[warmup_time].mean())

        # array_childbirth_referred_PHC3.append(fail_count_PHC3)
        # array_childbirth_count_PHC3.append(childbirth_count_PHC3)
        # 10. Inpatient data
        array_ipd_bed_occupancy_PHC7.append(
            in_beds_PHC7.occupancy[3 * 30 * 24 * 60:3 * 30 * 24 * 60 + 12 * 30 * 24 * 60].mean())
        # array_ipd_MO_occupancy1.append((ipd_MO_time1 + MO_covid_time1 + admin_work1 * 3) / run_time)  # multiplying by 3 because the admin time is for all 3 doctors individually
        array_ipd_staffnurse_occupancy_PHC7.append(ipd_nurse_PHC7.occupancy[warmup_time].mean())
        # changed here, below. Admin time changed and denominator (months*day*hours*minutes)
        # changed here
        array_staffnurse_occupancy_PHC7.append(
            (delivery_nurse_time_PHC7 + ipd_nurse_time_PHC7 + (180 * day * months)) / (months * day * 21 * 60))
        array_ipd_count_PHC7.append(inpatient_count_PHC7)
        array_ipd_bed_time_m_PHC7.append(ipd_bed_time_PHC7 / (run_time * ip_bed_cap_PHC7))
        array_ip_waiting_time_PHC7.append(in_beds_PHC7.requesters().length_of_stay[warmup_time].mean())
        # covid
        array_covid_count_PHC7.append(covid_count_PHC7)
        array_chc_refer_PHC7.append(chc_refer_PHC7)
        array_dh_refer_PHC7.append(dh_refer_PHC7)
        array_isolation_ward_refer_PHC7.append(isolation_ward_refer_PHC7)
        array_lab_covidcount_PHC7.append(lab_covidcount_PHC7)
        array_retesting_count_PHC7.append(retesting_count_PHC7)
        array_home_isolation_PHC7.append(home_isolation_PHC7)

        # PHC 8
        # adding entries in arrays. these are used for replication wise data
        # 1. OPD medicine data
        array_medicine_count_PHC8.append(medicine_count_PHC8)
        array_opd_patients_PHC8.append(PatientGenerator_PHC8.total_OPD_patients_PHC8)
        array_phc1_doc_time_PHC8.append(phc1_doc_time_PHC8 / (420 * doc_cap_PHC8 * 360))
        array_medicine_doctor_occupancy_PHC8.append(((medicine_cons_time_PHC8 + ipd_MO_time_PHC8 + MO_del_time_PHC8) /
                                                     (420 * day * months * doc_cap_PHC8)))
        array_medicine_doctor_occupancy212_PHC8.append(medicine_cons_time_PHC8 / (420 * day * months * doc_cap_PHC8))
        array_opd_q_waiting_time_PHC8.append(np.mean(np.array(opd_q_waiting_time_PHC8)))
        array_opd_q_length_PHC8.append(medicine_q_PHC8.length[warmup_time].mean())
        # 2. NCD nurse data
        array_ncd_count_PHC8.append(ncd_count_PHC8)
        array_ncd_occupancy_PHC8.append(((ncd_time_PHC8 + admin_work8) / (420 * day * months)))
        # 3. Pharmacy data
        array_pharmacy_time_PHC8.append(pharmacy_time_PHC8)
        array_pharmacy_occupancy_PHC8.append(
            (pharmacy_time_PHC8) / (420 * 1 * day * months))  # 2 is the capacity, 3 is shifts in a day
        array_pharmacy_q_waiting_time_PHC8.append(np.mean(np.array(pharmacy_q_waiting_time_PHC8)))
        array_pharmacy_q_length_PHC8.append(pharmacy_q_PHC8.length[warmup_time].mean())
        array_pharmacy_count_PHC8.append(pharmacy_count_PHC8)
        # 4. Lab data
        array_lab_count_PHC8.append(lab_count_PHC8)
        array_lab_occupancy_PHC8.append(
            (lab_time_PHC8) / (420 * day * months))  # 2 is the capacity, 3 is shifts in a day
        array_lab_q_waiting_time_PHC8.append(np.mean(np.array(lab_q_waiting_time_PHC8)))
        array_lab_q_length_PHC8.append(lab_q_PHC8.length[warmup_time].mean())
        # 9. Delivery data
        array_referred8.append(referred_PHC8)
        array_del_count_PHC8.append(delivery_count_PHC8)
        # array_del_bed_occupancy1.append(delivery_bed1.occupancy[3*30*24*60: 3*30*24*60 + 12*30*24*60].mean())
        array_del_bed_occupancy_PHC8.append(
            delivery_bed_PHC8.occupancy[warmup_time].mean())

        array_childbirth_referred_PHC8.append(fail_count_PHC8)
        array_childbirth_count_PHC8.append(childbirth_count_PHC8)
        # 10. Inpatient data
        array_ipd_bed_occupancy_PHC8.append(
            in_beds_PHC8.occupancy[3 * 30 * 24 * 60:3 * 30 * 24 * 60 + 12 * 30 * 24 * 60].mean())
        # array_ipd_MO_occupancy1.append((ipd_MO_time1 + MO_covid_time1 + admin_work1 * 3) / run_time)  # multiplying by 3 because the admin time is for all 3 doctors individually
        array_ipd_staffnurse_occupancy_PHC8.append(ipd_nurse_PHC8.occupancy[warmup_time].mean())
        # changed here, below. Admin time changed and denominator (months*day*hours*minutes)
        # changed here
        array_staffnurse_occupancy_PHC8.append(
            (delivery_nurse_time_PHC8 + ipd_nurse_time_PHC8 + (180 * day * months)) / (months * day * 21 * 60))
        array_ipd_count_PHC8.append(inpatient_count_PHC8)
        array_ipd_bed_time_m_PHC8.append(ipd_bed_time_PHC8 / (run_time * ip_bed_cap_PHC8))
        array_ip_waiting_time_PHC8.append(in_beds_PHC8.requesters().length_of_stay[warmup_time].mean())
        # covid
        array_covid_count_PHC8.append(covid_count_PHC8)
        array_chc_refer_PHC8.append(chc_refer_PHC8)
        array_dh_refer_PHC8.append(dh_refer_PHC8)
        array_isolation_ward_refer_PHC8.append(isolation_ward_refer_PHC8)
        array_lab_covidcount_PHC8.append(lab_covidcount_PHC8)
        array_retesting_count_PHC8.append(retesting_count_PHC8)
        array_home_isolation_PHC8.append(home_isolation_PHC8)

        # adding entries in arrays. these are used for replication wise data

        # PHC 9
        # adding entries in arrays. these are used for replication wise data
        # 1. OPD medicine data
        array_medicine_count_PHC9.append(medicine_count_PHC9)
        array_opd_patients_PHC9.append(PatientGenerator_PHC9.total_OPD_patients_PHC9)
        array_phc1_doc_time_PHC9.append(phc1_doc_time_PHC9 / (420 * doc_cap_PHC9 * 360))
        array_medicine_doctor_occupancy_PHC9.append(((medicine_cons_time_PHC9 + ipd_MO_time_PHC9 + MO_del_time_PHC9) /
                                                     (420 * day * months * doc_cap_PHC9)))
        array_medicine_doctor_occupancy212_PHC9.append(medicine_cons_time_PHC9 / (420 * day * months * doc_cap_PHC9))
        array_opd_q_waiting_time_PHC9.append(np.mean(np.array(opd_q_waiting_time_PHC9)))
        array_opd_q_length_PHC9.append(medicine_q_PHC9.length[warmup_time].mean())
        # 2. NCD nurse data
        array_ncd_count_PHC9.append(ncd_count_PHC9)
        array_ncd_occupancy_PHC9.append(((ncd_time_PHC9 + admin_work9) / (420 * day * months)))
        # 3. Pharmacy data
        array_pharmacy_time_PHC9.append(pharmacy_time_PHC9)
        array_pharmacy_occupancy_PHC9.append(
            (pharmacy_time_PHC9) / (420 * 1 * day * months))  # 2 is the capacity, 3 is shifts in a day
        array_pharmacy_q_waiting_time_PHC9.append(np.mean(np.array(pharmacy_q_waiting_time_PHC9)))
        array_pharmacy_q_length_PHC9.append(pharmacy_q_PHC9.length[warmup_time].mean())
        array_pharmacy_count_PHC9.append(pharmacy_count_PHC9)
        # 4. Lab data
        array_lab_count_PHC9.append(lab_count_PHC9)
        array_lab_occupancy_PHC9.append(
            (lab_time_PHC9) / (420 * day * months))  # 2 is the capacity, 3 is shifts in a day
        array_lab_q_waiting_time_PHC9.append(np.mean(np.array(lab_q_waiting_time_PHC9)))
        array_lab_q_length_PHC9.append(lab_q_PHC9.length[warmup_time].mean())
        # 9. Delivery data
        array_referred9.append(referred_PHC9)
        array_del_count_PHC9.append(delivery_count_PHC9)
        # array_del_bed_occupancy1.append(delivery_bed1.occupancy[3*30*24*60: 3*30*24*60 + 12*30*24*60].mean())
        array_del_bed_occupancy_PHC9.append(
            delivery_bed_PHC9.occupancy[warmup_time].mean())

        array_childbirth_referred_PHC9.append(fail_count_PHC9)
        array_childbirth_count_PHC9.append(childbirth_count_PHC9)
        # 10. Inpatient data
        array_ipd_bed_occupancy_PHC9.append(
            in_beds_PHC9.occupancy[3 * 30 * 24 * 60:3 * 30 * 24 * 60 + 12 * 30 * 24 * 60].mean())
        # array_ipd_MO_occupancy1.append((ipd_MO_time1 + MO_covid_time1 + admin_work1 * 3) / run_time)  # multiplying by 3 because the admin time is for all 3 doctors individually
        array_ipd_staffnurse_occupancy_PHC9.append(ipd_nurse_PHC9.occupancy[warmup_time].mean())
        # changed here, below. Admin time changed and denominator (months*day*hours*minutes)
        # changed here
        array_staffnurse_occupancy_PHC9.append(
            (delivery_nurse_time_PHC9 + ipd_nurse_time_PHC9 + (180 * day * months)) / (months * day * 21 * 60))
        array_ipd_count_PHC9.append(inpatient_count_PHC9)
        array_ipd_bed_time_m_PHC9.append(ipd_bed_time_PHC9 / (run_time * ip_bed_cap_PHC9))
        array_ip_waiting_time_PHC9.append(in_beds_PHC9.requesters().length_of_stay[warmup_time].mean())
        # covid
        array_covid_count_PHC9.append(covid_count_PHC9)
        array_chc_refer_PHC9.append(chc_refer_PHC9)
        array_dh_refer_PHC9.append(dh_refer_PHC9)
        array_isolation_ward_refer_PHC9.append(isolation_ward_refer_PHC9)
        array_lab_covidcount_PHC9.append(lab_covidcount_PHC9)
        array_retesting_count_PHC9.append(retesting_count_PHC9)
        array_home_isolation_PHC9.append(home_isolation_PHC9)

        # PHC 10
        # adding entries in arrays. these are used for replication wise data
        # 1. OPD medicine data
        array_medicine_count_PHC10.append(medicine_count_PHC10)
        array_opd_patients_PHC10.append(PatientGenerator_PHC10.total_OPD_patients_PHC10)
        array_phc1_doc_time_PHC10.append(phc1_doc_time_PHC10 / (420 * doc_cap_PHC9 * 360))
        array_medicine_doctor_occupancy_PHC10.append(
            ((medicine_cons_time_PHC10 + ipd_MO_time_PHC10 + MO_del_time_PHC10) /
             (420 * day * months * doc_cap_PHC10)))
        array_medicine_doctor_occupancy212_PHC10.append(medicine_cons_time_PHC10 / (420 * day * months * doc_cap_PHC9))
        array_opd_q_waiting_time_PHC10.append(np.mean(np.array(opd_q_waiting_time_PHC10)))
        array_opd_q_length_PHC10.append(medicine_q_PHC10.length[warmup_time].mean())
        # 2. NCD nurse data
        array_ncd_count_PHC10.append(ncd_count_PHC10)
        array_ncd_occupancy_PHC10.append(((ncd_time_PHC10 + admin_work10) / (420 * day * months)))
        # 3. Pharmacy data
        array_pharmacy_time_PHC10.append(pharmacy_time_PHC10)
        array_pharmacy_occupancy_PHC10.append(
            (pharmacy_time_PHC10) / (420 * 1 * day * months))  # 2 is the capacity, 3 is shifts in a day
        array_pharmacy_q_waiting_time_PHC10.append(np.mean(np.array(pharmacy_q_waiting_time_PHC10)))
        array_pharmacy_q_length_PHC10.append(pharmacy_q_PHC10.length[warmup_time].mean())
        array_pharmacy_count_PHC10.append(pharmacy_count_PHC10)
        # 4. Lab data
        array_lab_count_PHC10.append(lab_count_PHC10)
        array_lab_occupancy_PHC10.append(
            (lab_time_PHC10) / (420 * day * months))  # 2 is the capacity, 3 is shifts in a day
        array_lab_q_waiting_time_PHC10.append(np.mean(np.array(lab_q_waiting_time_PHC10)))
        array_lab_q_length_PHC10.append(lab_q_PHC10.length[warmup_time].mean())
        # 9. Delivery data
        array_referred10.append(referred_PHC10)
        array_del_count_PHC10.append(delivery_count_PHC10)
        # array_del_bed_occupancy1.append(delivery_bed1.occupancy[3*30*24*60: 3*30*24*60 + 12*30*24*60].mean())
        array_del_bed_occupancy_PHC10.append(
            delivery_bed_PHC10.occupancy[warmup_time].mean())

        array_childbirth_referred_PHC10.append(fail_count_PHC10)
        array_childbirth_count_PHC10.append(childbirth_count_PHC10)
        # 10. Inpatient data
        array_ipd_bed_occupancy_PHC10.append(
            in_beds_PHC10.occupancy[3 * 30 * 24 * 60:3 * 30 * 24 * 60 + 12 * 30 * 24 * 60].mean())
        # array_ipd_MO_occupancy1.append((ipd_MO_time1 + MO_covid_time1 + admin_work1 * 3) / run_time)  # multiplying by 3 because the admin time is for all 3 doctors individually
        array_ipd_staffnurse_occupancy_PHC10.append(ipd_nurse_PHC10.occupancy[warmup_time].mean())
        # changed here, below. Admin time changed and denominator (months*day*hours*minutes)
        # changed here
        array_staffnurse_occupancy_PHC10.append(
            (delivery_nurse_time_PHC10 + ipd_nurse_time_PHC10 + (180 * day * months)) / (months * day * 21 * 60))
        array_ipd_count_PHC10.append(inpatient_count_PHC10)
        array_ipd_bed_time_m_PHC10.append(ipd_bed_time_PHC10 / (run_time * ip_bed_cap_PHC10))
        array_ip_waiting_time_PHC10.append(in_beds_PHC10.requesters().length_of_stay[warmup_time].mean())
        # covid
        array_covid_count_PHC10.append(covid_count_PHC10)
        array_chc_refer_PHC10.append(chc_refer_PHC10)
        array_dh_refer_PHC10.append(dh_refer_PHC10)
        array_isolation_ward_refer_PHC10.append(isolation_ward_refer_PHC10)
        array_lab_covidcount_PHC10.append(lab_covidcount_PHC10)
        array_retesting_count_PHC10.append(retesting_count_PHC10)
        array_home_isolation_PHC10.append(home_isolation_PHC10)

        # PHC new additions
        # Number of cases
        array_phc1_to_cc_severe_case.append(np.sum(np.array(phc1_to_cc_severe_case)))
        array_phc2_to_cc_severe_case.append(np.sum(np.array(phc2_to_cc_severe_case)))
        array_phc3_to_cc_severe_case.append(np.sum(np.array(phc3_to_cc_severe_case)))
        array_phc4_to_cc_severe_case.append(np.sum(np.array(phc4_to_cc_severe_case)))
        array_phc5_to_cc_severe_case.append(np.sum(np.array(phc5_to_cc_severe_case)))
        array_phc6_to_cc_severe_case.append(np.sum(np.array(phc6_to_cc_severe_case)))
        array_phc7_to_cc_severe_case.append(np.sum(np.array(phc7_to_cc_severe_case)))
        array_phc8_to_cc_severe_case.append(np.sum(np.array(phc8_to_cc_severe_case)))
        array_phc9_to_cc_severe_case.append(np.sum(np.array(phc9_to_cc_severe_case)))
        array_phc10_to_cc_severe_case.append(np.sum(np.array(phc10_to_cc_severe_case)))

        # Distance travelled
        array_phc1_to_cc_dist.append(np.sum(np.array(phc1_to_cc_dist)))
        array_phc2_to_cc_dist.append(np.sum(np.array(phc2_to_cc_dist)))
        array_phc3_to_cc_dist.append(np.sum(np.array(phc3_to_cc_dist)))
        array_phc4_to_cc_dist.append(np.sum(np.array(phc4_to_cc_dist)))
        array_phc5_to_cc_dist.append(np.sum(np.array(phc5_to_cc_dist)))
        array_phc6_to_cc_dist.append(np.sum(np.array(phc6_to_cc_dist)))
        array_phc7_to_cc_dist.append(np.sum(np.array(phc7_to_cc_dist)))
        array_phc8_to_cc_dist.append(np.sum(np.array(phc8_to_cc_dist)))
        array_phc9_to_cc_dist.append(np.sum(np.array(phc9_to_cc_dist)))
        array_phc10_to_cc_dist.append(np.sum(np.array(phc10_to_cc_dist)))

        totaldistance += (np.sum(np.array(chc3_to_cc_dist)) + np.sum(np.array(chc2_to_cc_dist)) +
                            np.sum(np.array(chc1_to_cc_dist)) + np.sum(np.array(phc1_to_cc_dist)) +
                          np.sum(np.array(phc2_to_cc_dist)) + np.sum(np.array(phc3_to_cc_dist)) +
                          np.sum(np.array(phc4_to_cc_dist)) + np.sum(np.array(phc5_to_cc_dist)) +
                          np.sum(np.array(phc6_to_cc_dist)) + np.sum(np.array(phc7_to_cc_dist)) +
                          np.sum(np.array(phc8_to_cc_dist)) + np.sum(np.array(phc9_to_cc_dist)) +
                          np.sum(np.array(phc10_to_cc_dist)))

        distance.append(totaldistance)
        print("total distance", totaldistance)

        #return distance

        # CHC 1 new addition
        array_chc1_to_cc_moderate_case.append(np.sum(np.array(chc1_to_cc_moderate_case)))
        array_chc1_to_cc_severe_case.append(np.sum(np.array(chc1_to_cc_severe_case)))
        array_chc2_to_cc_moderate_case.append(np.sum(np.array(chc2_to_cc_moderate_case)))
        array_chc2_to_cc_severe_case.append(np.sum(np.array(chc2_to_cc_severe_case)))
        array_chc3_to_cc_moderate_case.append(np.sum(np.array(chc3_to_cc_moderate_case)))
        array_chc3_to_cc_severe_case.append(np.sum(np.array(chc3_to_cc_severe_case)))

        # CHC proportion
        # fring

        with np.errstate(divide='ignore', invalid='ignore'):
            # A type patients
            a_dh_chc1 = np.true_divide(array_a_dh_chc1, np.array(array_t_a_chc1))
            a_cc_chc1 = np.true_divide(array_a_cc_chc1, np.array(array_t_a_chc1))
            a_dh_chc1[a_dh_chc1 == np.inf] = 0
            a_cc_chc1[a_cc_chc1 == np.inf] = 0
            a_dh_chc1 = np.nan_to_num(a_dh_chc1)
            a_cc_chc1 = np.nan_to_num(a_cc_chc1)

            # B type patients
            b_dh_chc1 = np.true_divide(array_b_dh_chc1, np.array(array_t_b_chc1))
            b_cc_chc1 = np.true_divide(array_b_cc_chc1, np.array(array_t_b_chc1))
            b_dh_chc1[b_dh_chc1 == np.inf] = 0
            b_cc_chc1[b_cc_chc1 == np.inf] = 0
            b_dh_chc1 = np.nan_to_num(b_dh_chc1)
            b_cc_chc1 = np.nan_to_num(b_cc_chc1)
            # C type patients
            c_dh_chc1 = np.true_divide(array_c_dh_chc1, np.array(array_t_c_chc1))
            c_cc_chc1 = np.true_divide(array_c_cc_chc1, np.array(array_t_c_chc1))
            c_dh_chc1[c_dh_chc1 == np.inf] = 0
            c_cc_chc1[c_cc_chc1 == np.inf] = 0
            c_dh_chc1 = np.nan_to_num(c_dh_chc1)
            c_cc_chc1 = np.nan_to_num(c_cc_chc1)
            # D type
            d_dh_chc1 = np.true_divide(array_d_dh_chc1, np.array(array_t_d_chc1))
            d_cc_chc1 = np.true_divide(array_d_cc_chc1, np.array(array_t_d_chc1))
            d_dh_chc1[d_dh_chc1 == np.inf] = 0
            d_cc_chc1[d_cc_chc1 == np.inf] = 0
            d_dh_chc1 = np.nan_to_num(d_dh_chc1)
            d_cc_chc1 = np.nan_to_num(d_cc_chc1)
            # E type
            e_dh_chc1 = np.true_divide(array_e_dh_chc1, np.array(array_t_e_chc1))
            e_cc_chc1 = np.true_divide(array_e_cc_chc1, np.array(array_t_e_chc1))
            e_dh_chc1[e_dh_chc1 == np.inf] = 0
            e_cc_chc1[e_cc_chc1 == np.inf] = 0
            e_dh_chc1 = np.nan_to_num(e_dh_chc1)
            e_cc_chc1 = np.nan_to_num(e_cc_chc1)
            # F type
            f_dh_chc1 = np.true_divide(array_f_dh_chc1, np.array(array_t_f_chc1))
            f_cc_chc1 = np.true_divide(array_f_cc_chc1, np.array(array_t_f_chc1))
            f_dh_chc1[f_dh_chc1 == np.inf] = 0
            f_cc_chc1[f_cc_chc1 == np.inf] = 0
            f_dh_chc1 = np.nan_to_num(f_dh_chc1)
            f_cc_chc1 = np.nan_to_num(f_cc_chc1)

        array_t_a_chc1 = []
        array_t_b_chc1 = []
        array_t_c_chc1 = []
        array_t_d_chc1 = []
        array_t_e_chc1 = []
        array_t_f_chc1 = []
        array_a_dh_chc1 = []
        array_a_cc_chc1 = []
        array_b_dh_chc1 = []
        array_b_cc_chc1 = []
        array_c_dh_chc1 = []
        array_c_cc_chc1 = []
        array_d_dh_chc1 = []
        array_d_cc_chc1 = []
        array_e_dh_chc1 = []
        array_e_cc_chc1 = []
        array_f_dh_chc1 = []
        array_f_cc_chc1 = []
        array_t_d_chc1 = []

        array_severe_chc1.append(np.mean(np.array(array_t_s_chc1)))
        array_moderate_chc1.append(np.mean(np.array(array_t_m_chc1)))

        array_prop_a2cc_chc1_max.append(max(a_cc_chc1))
        array_prop_a2dh_chc1_max.append(max(a_dh_chc1))
        array_prop_a2cc_chc1_avg.append(np.mean(a_cc_chc1))
        array_prop_a2dh_chc1_avg.append(np.mean(a_dh_chc1))

        array_prop_b2cc_chc1_max.append(max(np.array(b_cc_chc1)))
        array_prop_b2dh_chc1_max.append(max(np.array(b_dh_chc1)))
        array_prop_b2cc_chc1_avg.append(np.mean(np.array(b_cc_chc1)))
        array_prop_b2dh_chc1_avg.append(np.mean(np.array(b_dh_chc1)))

        array_prop_c2cc_chc1_max.append(max(np.array(c_cc_chc1)))
        array_prop_c2dh_chc1_max.append(max(np.array(c_dh_chc1)))
        array_prop_c2cc_chc1_avg.append(np.mean(np.array(c_cc_chc1)))
        array_prop_c2dh_chc1_avg.append(np.mean(np.array(c_dh_chc1)))

        array_prop_d2cc_chc1_max.append(max(np.array(d_cc_chc1)))
        array_prop_d2dh_chc1_max.append(max(d_dh_chc1))  # np.array(array_d_dh_chc1
        array_prop_d2cc_chc1_avg.append(np.mean(np.array(d_cc_chc1)))
        array_prop_d2dh_chc1_avg.append(np.mean(np.array(d_dh_chc1)))

        array_prop_e2cc_chc1_max.append(max(np.array(e_cc_chc1)))
        array_prop_e2dh_chc1_max.append(max(np.array(e_dh_chc1)))
        array_prop_e2cc_chc1_avg.append(np.mean(np.array(e_cc_chc1)))
        array_prop_e2dh_chc1_avg.append(np.mean(np.array(e_dh_chc1)))

        array_prop_f2cc_chc1_max.append(max(np.array(f_cc_chc1)))
        array_prop_f2dh_chc1_max.append(max(np.array(f_dh_chc1)))
        array_prop_f2cc_chc1_avg.append(np.mean(np.array(f_cc_chc1)))
        array_prop_f2dh_chc1_avg.append(np.mean(np.array(f_dh_chc1)))

        # CHC 2

        # CHC proportion parameters
        with np.errstate(divide='ignore', invalid='ignore'):
            # A type patients
            a_dh_chc2 = np.true_divide(array_a_dh_chc2, np.array(array_t_a_chc2))
            a_cc_chc2 = np.true_divide(array_a_cc_chc2, np.array(array_t_a_chc2))
            a_dh_chc2[a_dh_chc2 == np.inf] = 0
            a_cc_chc2[a_cc_chc2 == np.inf] = 0
            a_dh_chc2 = np.nan_to_num(a_dh_chc2)
            a_cc_chc2 = np.nan_to_num(a_cc_chc2)

            # B type patients
            b_dh_chc2 = np.true_divide(array_b_dh_chc2, np.array(array_t_b_chc2))
            b_cc_chc2 = np.true_divide(array_b_cc_chc2, np.array(array_t_b_chc2))
            b_dh_chc2[b_dh_chc2 == np.inf] = 0
            b_cc_chc2[b_cc_chc2 == np.inf] = 0
            b_dh_chc2 = np.nan_to_num(b_dh_chc2)
            b_cc_chc2 = np.nan_to_num(b_cc_chc2)
            # C type patients
            c_dh_chc2 = np.true_divide(array_c_dh_chc2, np.array(array_t_c_chc2))
            c_cc_chc2 = np.true_divide(array_c_cc_chc2, np.array(array_t_c_chc2))
            c_dh_chc2[c_dh_chc2 == np.inf] = 0
            c_cc_chc2[c_cc_chc2 == np.inf] = 0
            c_dh_chc2 = np.nan_to_num(c_dh_chc2)
            c_cc_chc2 = np.nan_to_num(c_cc_chc2)
            # D type
            d_dh_chc2 = np.true_divide(array_d_dh_chc2, np.array(array_t_d_chc2))
            d_cc_chc2 = np.true_divide(array_d_cc_chc2, np.array(array_t_d_chc2))
            d_dh_chc2[d_dh_chc2 == np.inf] = 0
            d_cc_chc2[d_cc_chc2 == np.inf] = 0
            d_dh_chc2 = np.nan_to_num(d_dh_chc2)
            d_cc_chc2 = np.nan_to_num(d_cc_chc2)
            # E type
            e_dh_chc2 = np.true_divide(array_e_dh_chc2, np.array(array_t_e_chc2))
            e_cc_chc2 = np.true_divide(array_e_cc_chc2, np.array(array_t_e_chc2))
            e_dh_chc2[e_dh_chc2 == np.inf] = 0
            e_cc_chc2[e_cc_chc2 == np.inf] = 0
            e_dh_chc2 = np.nan_to_num(e_dh_chc2)
            e_cc_chc2 = np.nan_to_num(e_cc_chc2)
            # F type
            f_dh_chc2 = np.true_divide(array_f_dh_chc2, np.array(array_t_f_chc2))
            f_cc_chc2 = np.true_divide(array_f_cc_chc2, np.array(array_t_f_chc2))
            f_dh_chc2[f_dh_chc2 == np.inf] = 0
            f_cc_chc2[f_cc_chc2 == np.inf] = 0
            f_dh_chc2 = np.nan_to_num(f_dh_chc2)
            f_cc_chc2 = np.nan_to_num(f_cc_chc2)

        array_t_a_chc2 = []
        array_t_b_chc2 = []
        array_t_c_chc2 = []
        array_t_d_chc2 = []
        array_t_e_chc2 = []
        array_t_f_chc2 = []
        array_a_dh_chc2 = []
        array_a_cc_chc2 = []
        array_b_dh_chc2 = []
        array_b_cc_chc2 = []
        array_c_dh_chc2 = []
        array_c_cc_chc2 = []
        array_d_dh_chc2 = []
        array_d_cc_chc2 = []
        array_e_dh_chc2 = []
        array_e_cc_chc2 = []
        array_f_dh_chc2 = []
        array_f_cc_chc2 = []

        array_severe_chc2.append(np.mean(np.array(array_t_s_chc2)))
        array_moderate_chc2.append(np.mean(np.array(array_t_m_chc2)))

        array_prop_a2cc_chc2_max.append(max(a_cc_chc2))
        array_prop_a2dh_chc2_max.append(max(a_dh_chc2))
        array_prop_a2cc_chc2_avg.append(np.mean(a_cc_chc2))
        array_prop_a2dh_chc2_avg.append(np.mean(a_dh_chc2))

        array_prop_b2cc_chc2_max.append(max(np.array(b_cc_chc2)))
        array_prop_b2dh_chc2_max.append(max(np.array(b_dh_chc2)))
        array_prop_b2cc_chc2_avg.append(np.mean(np.array(b_cc_chc2)))
        array_prop_b2dh_chc2_avg.append(np.mean(np.array(b_dh_chc2)))

        array_prop_c2cc_chc2_max.append(max(np.array(c_cc_chc2)))
        array_prop_c2dh_chc2_max.append(max(np.array(c_dh_chc2)))
        array_prop_c2cc_chc2_avg.append(np.mean(np.array(c_cc_chc2)))
        array_prop_c2dh_chc2_avg.append(np.mean(np.array(c_dh_chc2)))

        array_prop_d2cc_chc2_max.append(max(np.array(d_cc_chc2)))
        array_prop_d2dh_chc2_max.append(max(d_dh_chc2))  # np.array(array_d_dh_chc1
        array_prop_d2cc_chc2_avg.append(np.mean(np.array(d_cc_chc2)))
        array_prop_d2dh_chc2_avg.append(np.mean(np.array(d_dh_chc2)))

        array_prop_e2cc_chc2_max.append(max(np.array(e_cc_chc2)))
        array_prop_e2dh_chc2_max.append(max(np.array(e_dh_chc2)))
        array_prop_e2cc_chc2_avg.append(np.mean(np.array(e_cc_chc2)))
        array_prop_e2dh_chc2_avg.append(np.mean(np.array(e_dh_chc2)))

        array_prop_f2cc_chc2_max.append(max(np.array(f_cc_chc2)))
        array_prop_f2dh_chc2_max.append(max(np.array(f_dh_chc2)))
        array_prop_f2cc_chc2_avg.append(np.mean(np.array(f_cc_chc2)))
        array_prop_f2dh_chc2_avg.append(np.mean(np.array(f_dh_chc2)))

        # CHC3

        with np.errstate(divide='ignore', invalid='ignore'):
            # A type patients
            a_dh_chc3 = np.true_divide(array_a_dh_chc3, np.array(array_t_a_chc3))
            a_cc_chc3 = np.true_divide(array_a_cc_chc3, np.array(array_t_a_chc3))
            a_dh_chc3[a_dh_chc3 == np.inf] = 0
            a_cc_chc3[a_cc_chc3 == np.inf] = 0
            a_dh_chc3 = np.nan_to_num(a_dh_chc3)
            a_cc_chc3 = np.nan_to_num(a_cc_chc3)

            # B type patients
            b_dh_chc3 = np.true_divide(array_b_dh_chc3, np.array(array_t_b_chc3))
            b_cc_chc3 = np.true_divide(array_b_cc_chc3, np.array(array_t_b_chc3))
            b_dh_chc3[b_dh_chc3 == np.inf] = 0
            b_cc_chc3[b_cc_chc3 == np.inf] = 0
            b_dh_chc3 = np.nan_to_num(b_dh_chc3)
            b_cc_chc3 = np.nan_to_num(b_cc_chc3)
            # C type patients
            c_dh_chc3 = np.true_divide(array_c_dh_chc3, np.array(array_t_c_chc3))
            c_cc_chc3 = np.true_divide(array_c_cc_chc3, np.array(array_t_c_chc3))
            c_dh_chc3[c_dh_chc3 == np.inf] = 0
            c_cc_chc3[c_cc_chc3 == np.inf] = 0
            c_dh_chc3 = np.nan_to_num(c_dh_chc3)
            c_cc_chc3 = np.nan_to_num(c_cc_chc3)
            # D type
            d_dh_chc3 = np.true_divide(array_d_dh_chc3, np.array(array_t_d_chc3))
            d_cc_chc3 = np.true_divide(array_d_cc_chc3, np.array(array_t_d_chc3))
            d_dh_chc3[d_dh_chc3 == np.inf] = 0
            d_cc_chc3[d_cc_chc3 == np.inf] = 0
            d_dh_chc3 = np.nan_to_num(d_dh_chc3)
            d_cc_chc3 = np.nan_to_num(d_cc_chc3)
            # E type
            e_dh_chc3 = np.true_divide(array_e_dh_chc3, np.array(array_t_e_chc3))
            e_cc_chc3 = np.true_divide(array_e_cc_chc3, np.array(array_t_e_chc3))
            e_dh_chc3[e_dh_chc3 == np.inf] = 0
            e_cc_chc3[e_cc_chc3 == np.inf] = 0
            e_dh_chc3 = np.nan_to_num(e_dh_chc3)
            e_cc_chc3 = np.nan_to_num(e_cc_chc3)
            # F type
            f_dh_chc3 = np.true_divide(array_f_dh_chc3, np.array(array_t_f_chc3))
            f_cc_chc3 = np.true_divide(array_f_cc_chc3, np.array(array_t_f_chc3))
            f_dh_chc3[f_dh_chc3 == np.inf] = 0
            f_cc_chc3[f_cc_chc3 == np.inf] = 0
            f_dh_chc3 = np.nan_to_num(f_dh_chc3)
            f_cc_chc3 = np.nan_to_num(f_cc_chc3)

        array_t_a_chc3 = []
        array_t_b_chc3 = []
        array_t_c_chc3 = []
        array_t_d_chc3 = []
        array_t_e_chc3 = []
        array_t_f_chc3 = []
        array_a_dh_chc3 = []
        array_a_cc_chc3 = []
        array_b_dh_chc3 = []
        array_b_cc_chc3 = []
        array_c_dh_chc3 = []
        array_c_cc_chc3 = []
        array_d_dh_chc3 = []
        array_d_cc_chc3 = []
        array_e_dh_chc3 = []
        array_e_cc_chc3 = []
        array_f_dh_chc3 = []
        array_f_cc_chc3 = []

        array_severe_chc3.append(np.mean(np.array(array_t_s_chc3)))
        array_moderate_chc3.append(np.mean(np.array(array_t_m_chc3)))

        array_prop_a2cc_chc3_max.append(max(a_cc_chc3))
        array_prop_a2dh_chc3_max.append(max(a_dh_chc3))
        array_prop_a2cc_chc3_avg.append(np.mean(a_cc_chc3))
        array_prop_a2dh_chc3_avg.append(np.mean(a_dh_chc3))

        array_prop_b2cc_chc3_max.append(max(np.array(b_cc_chc3)))
        array_prop_b2dh_chc3_max.append(max(np.array(b_dh_chc3)))
        array_prop_b2cc_chc3_avg.append(np.mean(np.array(b_cc_chc3)))
        array_prop_b2dh_chc3_avg.append(np.mean(np.array(b_dh_chc3)))

        array_prop_c2cc_chc3_max.append(max(np.array(c_cc_chc3)))
        array_prop_c2dh_chc3_max.append(max(np.array(c_dh_chc3)))
        array_prop_c2cc_chc3_avg.append(np.mean(np.array(c_cc_chc3)))
        array_prop_c2dh_chc3_avg.append(np.mean(np.array(c_dh_chc3)))

        array_prop_d2cc_chc3_max.append(max(np.array(d_cc_chc3)))
        array_prop_d2dh_chc3_max.append(max(d_dh_chc3))  # np.array(array_d_dh_chc1
        array_prop_d2cc_chc3_avg.append(np.mean(np.array(d_cc_chc3)))
        array_prop_d2dh_chc3_avg.append(np.mean(np.array(d_dh_chc3)))

        array_prop_e2cc_chc3_max.append(max(np.array(e_cc_chc3)))
        array_prop_e2dh_chc3_max.append(max(np.array(e_dh_chc3)))
        array_prop_e2cc_chc3_avg.append(np.mean(np.array(e_cc_chc3)))
        array_prop_e2dh_chc3_avg.append(np.mean(np.array(e_dh_chc3)))

        array_prop_f2cc_chc3_max.append(max(np.array(f_cc_chc3)))
        array_prop_f2dh_chc3_max.append(max(np.array(f_dh_chc3)))
        array_prop_f2dh_chc3_avg.append(np.mean(np.array(f_dh_chc3)))
        array_prop_f2cc_chc3_avg.append(np.mean(np.array(f_cc_chc3)))

        # DH
        with np.errstate(divide='ignore', invalid='ignore'):
            # A type patients
            array_prop_dh_2_cc_a = np.true_divide(np.array(array_dh_2_cc_a), np.array(array_dh_total_a))
            array_prop_dh_2_cc_a[array_prop_dh_2_cc_a == np.inf] = 0
            array_prop_dh_2_cc_a = np.nan_to_num(array_prop_dh_2_cc_a)
            # B type patients
            array_prop_dh_2_cc_b = np.true_divide(np.array(array_dh_2_cc_b), np.array(array_dh_total_b))
            array_prop_dh_2_cc_b[array_prop_dh_2_cc_b == np.inf] = 0
            array_prop_dh_2_cc_b = np.nan_to_num(array_prop_dh_2_cc_b)
            # C type patients
            array_prop_dh_2_cc_c = np.true_divide(np.array(array_dh_2_cc_c), np.array(array_dh_total_c))
            array_prop_dh_2_cc_c[array_prop_dh_2_cc_c == np.inf] = 0
            array_prop_dh_2_cc_c = np.nan_to_num(array_prop_dh_2_cc_c)
            # D type patients
            array_prop_dh_2_cc_d = np.true_divide(np.array(array_dh_2_cc_d), np.array(array_dh_total_d))
            array_prop_dh_2_cc_d[array_prop_dh_2_cc_d == np.inf] = 0
            array_prop_dh_2_cc_d = np.nan_to_num(array_prop_dh_2_cc_d)
            # E type patients
            array_prop_dh_2_cc_e = np.true_divide(np.array(array_dh_2_cc_e), np.array(array_dh_total_e))
            array_prop_dh_2_cc_e[array_prop_dh_2_cc_e == np.inf] = 0
            array_prop_dh_2_cc_e = np.nan_to_num(array_prop_dh_2_cc_e)
            # F type patients
            array_prop_dh_2_cc_f = np.true_divide(np.array(array_dh_2_cc_f), np.array(array_dh_total_f))
            array_prop_dh_2_cc_f[array_prop_dh_2_cc_f == np.inf] = 0
            array_prop_dh_2_cc_f = np.nan_to_num(array_prop_dh_2_cc_f)

        array_prop_dh_2_cc_a_max.append(max(array_prop_dh_2_cc_a))
        array_prop_dh_2_cc_a_avg.append(np.mean(array_prop_dh_2_cc_a))

        array_prop_dh_2_cc_b_max.append(max(array_prop_dh_2_cc_b))
        array_prop_dh_2_cc_b_avg.append(np.mean(array_prop_dh_2_cc_b))

        array_prop_dh_2_cc_c_max.append(max(array_prop_dh_2_cc_c))
        array_prop_dh_2_cc_c_avg.append(np.mean(array_prop_dh_2_cc_c))

        array_prop_dh_2_cc_d_max.append(max(array_prop_dh_2_cc_d))
        array_prop_dh_2_cc_d_avg.append(np.mean(array_prop_dh_2_cc_d))

        array_prop_dh_2_cc_e_max.append(max(array_prop_dh_2_cc_e))
        array_prop_dh_2_cc_e_avg.append(np.mean(array_prop_dh_2_cc_e))

        array_prop_dh_2_cc_f_max.append(max(array_prop_dh_2_cc_f))
        array_prop_dh_2_cc_f_avg.append(np.mean(array_prop_dh_2_cc_f))
        array_dh_death.append(np.sum(np.array(array_dh_total_d)))
                                     
        with np.errstate(divide='ignore', invalid='ignore'):

            array_prop_dh_2_cc_b_ox = np.true_divide(np.array(array_dh_2_cc_b_ox), np.array(array_dh_total_b))
            array_prop_dh_2_cc_b_ox[array_prop_dh_2_cc_b_ox == np.inf] = 0
            array_prop_dh_2_cc_b_ox = np.nan_to_num(array_prop_dh_2_cc_b_ox)
            array_prop_dh_2_cc_c_ven = np.true_divide(np.array(array_dh_2_cc_c_ven), np.array(array_dh_total_c))
            array_prop_dh_2_cc_c_ven[array_prop_dh_2_cc_c_ven == np.inf] = 0
            array_prop_dh_2_cc_c_ven = np.nan_to_num(array_prop_dh_2_cc_c_ven)
        array_prop_dh_2_cc_b_ox_avg.append(np.mean(array_prop_dh_2_cc_b_ox))
        array_prop_dh_2_cc_c_ven_avg.append(np.mean(array_prop_dh_2_cc_c_ven))
        array_prop_dh_2_cc_b_ox_max.append(max(array_prop_dh_2_cc_b_ox))
        array_prop_dh_2_cc_c_ven_max.append(max(array_prop_dh_2_cc_c_ven))

        array_dh_2_cc_b_ox = []
        array_dh_2_cc_c_ven = []
        array_dh_total_a = []
        array_dh_total_b = []
        array_dh_total_c = []
        array_dh_total_d = []
        array_dh_total_e = []
        array_dh_total_f = []
        array_prop_dh_2_cc_c_ven = []
        array_prop_dh_2_cc_b_ox = []

        array_dh_2_cc_a = []
        array_dh_2_cc_b = []
        array_dh_2_cc_c = []
        array_dh_2_cc_d = []
        array_dh_2_cc_e = []
        array_dh_2_cc_f = []

        CovidPatients_list.append(DHPatient.Covid_count)
        DHPatient.Covid_count = 0
        gen_exit_list.append(DHPatients.moderate_gen_to_exit)
        gen_icuoxygen_exit_list.append(DHPatients.moderate_gen_to_icu_to_gen_exit)
        gen_icuventilator_exit_list.append(DHPatients.moderate_gen_to_ventilator_to_gen_exit)
        icu_ventilator_list.append(DHPatients.severe_ventilator_dead)
        icu_oxygen_icuventilator_gen_exit.append(DHPatients.R1)
        icu_oxygen_gen_exit.append(DHPatients.R2)
        icu_ventilator_gen_exit.append(DHPatients.R4)
        icu_ventilator_icuoxygen_gen_list.append(DHPatients.R3)
        DH_to_CCC_refer_patients_list.append(
            DHPatients.moderate_gen_refer_CCC + DHPatients.severe_icu_to_gen_refer_CCC + DHPatients.severe_ventilator_to_gen_refer_CCC + DHPatients.severe_ventilator_dead_refer_CCC)
        retesting_count_DH_list.append(RetestingDH.retesting_count_DH)
        RetestingDH.retesting_count_DH = 0

        doc_totaltime_DH_Gen = sum(DoctorDH_Gen.doc_DH_time_Gen) + sum(DHPatientTest.DH_Doctor_initial_doctor_test_time)
        d111 = doc_totaltime_DH_Gen / (21 * 60 * day * months * doc_DH_Gen_cap)
        doc_occupancy_DH_Gen.append(d111)
        doc_totaltime_DH_Oxygen = sum(DoctorDH_Oxygen.doc_DH_time_Oxygen)
        d112 = doc_totaltime_DH_Oxygen / (21 * 60 * day * months * doc_DH_Oxygen_cap)
        doc_occupancy_DH_Oxygen.append(d112)
        doc_totaltime_DH_Ventilator = sum(DoctorDH_Ventilator.doc_DH_time_Ventilator)
        d113 = doc_totaltime_DH_Ventilator / (21 * 60 * day * months * doc_DH_Ventilator_cap)
        doc_occupancy_DH_Ventilator.append(d113)
        nurse_totaltime_DH_Gen = sum(NurseDH_Gen.nurse_DH_time_Gen)
        n111 = nurse_totaltime_DH_Gen / (21 * 60 * day * months * nurse_DH_Gen_cap)
        nurse_occupancy_DH_Gen.append(n111)
        nurse_totaltime_DH_Oxygen = sum(NurseDH_Oxygen.nurse_DH_time_Oxygen)
        n112 = nurse_totaltime_DH_Oxygen / (21 * 60 * day * months * nurse_DH_Oxygen_cap)
        nurse_occupancy_DH_Oxygen.append(n112)
        nurse_totaltime_DH_Ventilator = sum(NurseDH_Ventilator.nurse_DH_time_Ventilator)
        n113 = nurse_totaltime_DH_Ventilator / (21 * 60 * day * months * nurse_DH_Ventilator_cap)
        nurse_occupancy_DH_Ventilator.append(n113)
        DH_sample_collection_nurse_total_time = sum(DHPatientTest.DH_Nurse_sample_collection_time)
        n114 = DH_sample_collection_nurse_total_time / (21 * 60 * day * months * 1)
        sample_collctn_nurse_occupancy.append(n114)
        receptionist_totaltime = sum(DHPatients.receptionistservicetime)
        r11 = receptionist_totaltime / (21 * 60 * day * months * receptionist_cap)
        receptionistoccupancy.append(r11)
        DH_total_lab_time = sum(DHPatientTest.DH_lab_time)
        dhl = DH_total_lab_time / (21 * 60 * day * months * 1)
        DH_lab_occupancy.append(dhl)
        Generalbed_totaltime = sum(DHPatients.generalbedtime)
        g11 = Generalbed_totaltime / (1440 * day * months * Generalbed_cap)
        Generalward_bedoccupancy.append(g11)
        ICUoxygen_totaltime = sum(DHPatients.icuoxygentime)
        j11 = ICUoxygen_totaltime / (1440 * day * months * ICUoxygen_cap)
        ICUward_oxygenoccupancy.append(j11)
        ICUventilator_totaltime = sum(DHPatients.icuventilatortime)
        k11 = ICUventilator_totaltime / (1440 * day * months * ICUventilator_cap)
        ICUward_ventilatoroccupancy.append(k11)

        reg_waittime = sum(DHPatients.receptionwaitingtime)
        reg1 = reg_waittime / (DHPatients.No_of_covid_patients)
        waittime_registration.append(reg1)
        dhlab_wt = sum(DHPatientTest.DH_lab_waiting_time)
        wtl = dhlab_wt / (DHPatientTest.CovidPatients_DH)
        waittime_DH_lab.append(wtl)
        dh_nurse_sampletime = sum(DHPatientTest.DH_Nurse_sample_collection_wait_time)
        dh_nurse_colctn = dh_nurse_sampletime / (DHPatientTest.CovidPatients_DH)
        DH_Nurse_sample_collection_wait_time_list.append(dh_nurse_colctn)
        triage_waittime = sum(DHPatients.triagewaitingtime)
        triage1 = triage_waittime / (DHPatients.No_of_covid_patients)
        waittime_triage.append(triage1)
        genbed_waittime = sum(DHPatients.generalbedwaitingtime)
        genbed1 = genbed_waittime / (
                DHPatients.moderatepatients + DHPatients.R2 + DHPatients.R4 + DHPatients.moderate_gen_to_ventilator_to_gen_exit + DHPatients.moderate_gen_to_ventilator_to_gen_exit)
        waitime_generalbed.append(genbed1)
        icuventilator_waittime = sum(DHPatients.icuventilatorwaitingtime)
        icuventilator1 = icuventilator_waittime / (
                DHPatients.severe_ventilator_dead + DHPatients.R1 + DHPatients.moderate_gen_to_ventilator_to_gen_exit)
        waittime_ICUventilator.append(icuventilator1)
        icuoxygen_waittime = sum(DHPatients.icuoxygenwaitingtime)
        icuoxygen1 = icuoxygen_waittime / (DHPatients.R3 + DHPatients.moderate_gen_to_icu_to_gen_exit)
        waittime_ICUoxygen.append(icuoxygen1)

        array_DH_mild_count.append(DH_mild_count)
        array_dh_ven_wait.append(np.mean(np.array(dh_ven_wait)))

        # DH patient count updation
        array_moderate_total.append(moderate_total)
        array_moderate_A.append(moderate_A)
        array_moderate_B.append(moderate_B)
        array_moderate_C.append(moderate_C)
        array_severe_total.append(severe_total)
        array_severe_F.append(severe_F)
        array_severe_F2E.append(severe_F2E)
        array_severe_E2F.append(severe_E2F)
        array_severe_E.append(severe_E)
        array_severe_D.append(severe_D)
        array_moderate_refer.append(moderate_refer)
        array_severe_refer.append(severe_refer)

        # COVID center
        # Data storage
        # 1. Nurse
        array_G_nurse_occupancy.append(G_nurse.occupancy[warmup_time:(warmup_time + run_time)].mean())
        array_O_nurse_occupancy.append(O_nurse.occupancy[warmup_time].mean())
        array_V_nurse_occupancy.append(V_nurse.occupancy[warmup_time].mean())
        array_G_nurse_occupancy1.append(G_nurse_time / (3*cc_gen_nurse_cap * 420 * day * months))
        array_O_nurse_occupancy1.append(O_nurse_time / (3*cc_ox_nurse_cap * 420 * day * months))
        array_V_nurse_occupancy1.append(V_nurse_time / (3*cc_ven_nurse_cap * 420 * day * months))

        # 2. Doctor

        array_G_doctor_occupancy1.append(G_doctor_time / (
                3 * 420 * day * months * cc_gen_doc_cap))  # 5 is the cap of doct. divided by three because there are 3 shifts in day
        array_O_doctor_occupancy1.append(O_doctor_time / (3 * 420 * day * months * cc_ox_doc_cap))
        array_V_doctor_occupancy1.append(V_doctor_time / (3 * 420 * day * months * cc_ven_doc_cap))

        # 3. Patient count
        array_isolation_count.append(isolation_count)
        array_A_count.append((A_count))
        array_B_count.append((B_count))
        array_C_count.append((C_count))
        array_D_count.append((D_count))
        array_E_count.append((E_count))
        array_F_count.append((F_count))
        array_moderate_count.append(moderate_count)
        array_recovered.append(recovered)
        array_dead.append(dead)
        array_severe_count.append(severe_count)

        # 4. Waiting time & occupancy of bed
        array_m_iso_bed_wt.append(np.mean(np.array(m_iso_bed_wt)))
       # print(" here",array_m_iso_bed_wt)
        array_g_bed_wt.append(G_bed.requesters().length_of_stay[warmup_time].mean())
        array_o_bed_wt.append(O_bed.requesters().length_of_stay[warmup_time].mean())
        array_v_bed_wt.append(V_bed.requesters().length_of_stay[warmup_time].mean())
        array_iso_bed_wt.append(isolation_bed.requesters().length_of_stay[warmup_time].mean())
        array_g_bed_occ.append(G_bed.occupancy[warmup_time].mean())
        array_o_bed_occ.append(O_bed.occupancy[warmup_time].mean())
        array_v_bed_occ.append(V_bed.occupancy[warmup_time].mean())
        array_isolation_bed_occupancy.append(isolation_bed.occupancy[warmup_time].mean())


import datetime
p = [24.0, 12.0, 4.0, 32.984845004941285, 14.422205101855956, 14.422205101855956, 16.0, 25.612496949731394, 37.73592452822641, 31.240998703626616, 21.540659228538015, 12.649110640673518, 24.331050121192877, 12.649110640673518]

if __name__ == '__main__':
    a1 = datetime.datetime.now()
    main(p)

df = pd.DataFrame({
    # "Total registered OPDs": np.transpose(np.array(array_opd_patients)),
    "OPD patient count": np.transpose(np.array(array_medicine_count)),
    "Childbirth cases": np.transpose(np.array(array_childbirth_count)),
    "Childbirth referred": np.transpose(np.array(array_childbirth_referred)),
    "Delivery count": np.transpose(np.array(array_del_count)),
    "Inpatient surgery count": np.transpose(np.array(array_ipd_surgery_count)),
    # "Inpatient d_count": np.transpose(np.array(array_ipd_del_count)),
    "Inpatient e_count": np.transpose(np.array(array_emer_inpatients)),
    "Total covid patients CHC": np.transpose(np.array(array_covid_count)),
    "Covid refered from PHC": np.transpose(np.array(array_phc2chc_count)),
    "COVID severe count": np.transpose(np.array(array_chc1_severe_covid)),
    "COVID moderate count": np.transpose(np.array(array_chc1_moderate_covid)),
    "Severe patients referred to DH": np.transpose(np.array(array_dh_refer_chc1)),
    "Covid Patients referred from CHC for Institutional Quarantine in Covid Care Center": np.transpose(
        np.array(array_isolation_ward_refer_from_CHC)),

    "Moderate patients refered to DH": np.transpose(np.array(array_moderate_refered_chc1)),
    "Moderate patients refered to CC": np.transpose(np.array(array_chc1_to_cc_moderate_case)),
    "Severe patients refered to CC": np.transpose(np.array(array_chc1_to_cc_severe_case)),
    "Inpatient doc occupan": np.transpose(np.array(array_ipd_MO_occupancy)),
    "Manual IPD bed wait time": np.transpose(np.array(array_ipd_bed_wt_chc1)),
    "Manual Inpatiend bed occ": np.transpose(np.array(array_ipd_bed_time_m)),
    "IPD nurse manual util": np.transpose(np.array(array_staffnurse_occupancy)),
    "OPD medicine occupancy": np.transpose(np.array(array_medicine_doctor_occupancy)),
    "OPD medicine queue waiting time": np.transpose(np.array(array_opd_q_waiting_time)),
    "OPD medicine queue length": np.transpose(np.array(array_opd_q_length)),
    "Covid bed manual waiting time": np.transpose(np.array(array_c_bed_wait)),
    "Covid bed length queue": np.transpose(np.array(array_covid_q_length)),
    "Manual Covid bed occ": np.transpose(np.array(array_chc1_covid_bed_occ)),
    "COVID bed max occupancy": np.transpose(np.array(chc1_max_bed_occ_covid)),
    "Lab occupancy": np.transpose(np.array(array_lab_occupancy)),
    "Lab waiting time ": np.transpose(np.array(array_lab_q_waiting_time)),
    "People in queue after OPD hours": np.transpose(np.array(array_q_len_chc1)),
    "Distance from CHC to CC": np.transpose(np.array(array_chc1_to_cc)),
    "Distance from CHC to DH": np.transpose(np.array(array_chc1_to_dh)),
    "Max prop of A-type patients referred to CC on a day": np.transpose(np.array(array_prop_a2cc_chc1_max)),
    "Max prop of B-type patients referred to CC on a day": np.transpose(np.array(array_prop_b2cc_chc1_max)),
    "Max prop of C-type patients referred to CC on a day": np.transpose(np.array(array_prop_c2cc_chc1_max)),
    "Max prop of D-type patients referred to CC on a day": np.transpose(np.array(array_prop_d2cc_chc1_max)),
    "Max prop of E-type patients referred to CC on a day": np.transpose(np.array(array_prop_e2cc_chc1_max)),
    "Max prop of F-type patients referred to CC on a day": np.transpose(np.array(array_prop_f2cc_chc1_max)),

    "Max prop of A-type patients referred to DH on a day": np.transpose(np.array(array_prop_a2dh_chc1_max)),
    "Max prop of B-type patients referred to DH on a day": np.transpose(np.array(array_prop_b2dh_chc1_max)),
    "Max prop of C-type patients referred to DH on a day": np.transpose(np.array(array_prop_c2dh_chc1_max)),
    "Max prop of D-type patients referred to DH on a day": np.transpose(np.array(array_prop_d2dh_chc1_max)),
    "Max prop of E-type patients referred to DH on a day": np.transpose(np.array(array_prop_e2dh_chc1_max)),
    "Max prop of F-type patients referred to DH on a day": np.transpose(np.array(array_prop_f2dh_chc1_max)),

    "Avg  prop of A-type patients referred to CC on a day": np.transpose(np.array(array_prop_a2cc_chc1_avg)),
    "Avg prop of B-type patients referred to CC on a day": np.transpose(np.array(array_prop_b2cc_chc1_avg)),
    "Avg prop of C-type patients referred to CC on a day": np.transpose(np.array(array_prop_c2cc_chc1_avg)),
    "Avg prop of D-type patients referred to CC on a day": np.transpose(np.array(array_prop_d2cc_chc1_avg)),
    "Avg prop of E-type patients referred to CC on a day": np.transpose(np.array(array_prop_e2cc_chc1_avg)),
    "Avg prop of F-type patients referred to CC on a day": np.transpose(np.array(array_prop_f2cc_chc1_avg)),

    "Avg prop of A-type patients referred to DH on a day": np.transpose(np.array(array_prop_a2dh_chc1_avg)),
    "Avg prop of B-type patients referred to DH on a day": np.transpose(np.array(array_prop_b2dh_chc1_avg)),
    "Avg prop of C-type patients referred to DH on a day": np.transpose(np.array(array_prop_c2dh_chc1_avg)),
    "Avg prop of D-type patients referred to DH on a day": np.transpose(np.array(array_prop_d2dh_chc1_avg)),
    "Avg prop of E-type patients referred to DH on a day": np.transpose(np.array(array_prop_e2dh_chc1_avg)),
    "Avg prop of F-type patients referred to DH on a day": np.transpose(np.array(array_prop_f2dh_chc1_avg)),
    "Avg/day severe patients": np.transpose(np.array(array_severe_chc1)),
    "Avg/day moderate patients ": np.transpose(np.array(array_moderate_chc1)),

})
df_CHC2 = pd.DataFrame({

    # "Total registered OPDs": np.transpose(np.array(array_opd_patients_chc2)),
    "OPD patient count": np.transpose(np.array(array_medicine_count_chc2)),
    # "NCD patient count": np.transpose(np.array(array_ncd_count_chc2)),
    # "Pharmacy patient count":np.transpose(np.array(array_pharmacy_count_chc2)),
    "Childbirth cases": np.transpose(np.array(array_childbirth_count_chc2)),
    "Childbirth referred": np.transpose(np.array(array_childbirth_referred_chc2)),
    "Delivery count": np.transpose(np.array(array_del_count_chc2)),
    "Inpatient surgery count": np.transpose(np.array(array_ipd_surgery_count_chc2)),
    # "Inpatient d_count": np.transpose(np.array(array_ipd_del_count_chc2)),
    "Inpatient e_count": np.transpose(np.array(array_emer_inpatients_chc2)),
    "Total covid patients CHC": np.transpose(np.array(array_covid_count_chc2)),
    "Covid refered from PHC": np.transpose(np.array(array_phc2chc_count_chc2)),
    "COVID severe count": np.transpose(np.array(array_chc2_severe_covid)),
    "COVID moderate count": np.transpose(np.array(array_chc2_moderate_covid)),
    "Severe patients referred to DH": np.transpose(np.array(array_dh_refer_chc2)),
    "Covid Patients referred from CHC for Institutional Quarantine in Covid Care Center": np.transpose(
        np.array(array_isolation_ward_refer_from_CHC_chc2)),
    "Moderate patients refered to DH": np.transpose(np.array(array_moderate_refered_chc2)),
    "Moderate patients refered to CC": np.transpose(np.array(array_chc2_to_cc_moderate_case)),
    "Severe patients refered to CC": np.transpose(np.array(array_chc2_to_cc_severe_case)),
    "Inpatient doc occupan": np.transpose(np.array(array_ipd_MO_occupancy_chc2)),
    "Inpatient bed waiting time": np.transpose(np.array(array_ip_waiting_time_chc2)),
    "Manual IPD bed wait time": np.transpose(np.array(array_ipd_bed_wt_chc2)),
    "Manual Inpatient bed occ": np.transpose(np.array(array_ipd_bed_time_m_chc2)),
    "IPD nurse manual util": np.transpose(np.array(array_staffnurse_occupancy_chc2)),
    "OPD medicine occupancy": np.transpose(np.array(array_medicine_doctor_occupancy_chc2)),
    "OPD medicine queue waiting time": np.transpose(np.array(array_opd_q_waiting_time_chc2)),
    "OPD medicine queue length": np.transpose(np.array(array_opd_q_length_chc2)),
    "Covid bed waiting time": np.transpose(np.array(array_covid_bed_waiting_time_chc2)),
    "Covid bed length queue": np.transpose(np.array(array_covid_q_length_chc2)),
    "COVID bed max occupancy": np.transpose(np.array(chc2_max_bed_occ_covid)),
    "Manual Covid bed occ": np.transpose(np.array(array_chc2_covid_bed_occ)),
    "Lab occupancy": np.transpose(np.array(array_lab_occupancy_chc2)),
"Lab waiting time ": np.transpose(np.array(array_lab_q_waiting_time_chc2)),
    "People in queue after OPD hours": np.transpose(np.array(array_q_len_chc2)),
    "Distance from CHC to CC": np.transpose(np.array(array_chc2_to_cc)),
    "Distance from CHC to DH": np.transpose(np.array(array_chc2_to_dh)),

    "Max prop of A-type patients referred to CC on a day": np.transpose(np.array(array_prop_a2cc_chc2_max)),
    "Max prop of B-type patients referred to CC on a day": np.transpose(np.array(array_prop_b2cc_chc2_max)),
    "Max prop of C-type patients referred to CC on a day": np.transpose(np.array(array_prop_c2cc_chc2_max)),
    "Max prop of D-type patients referred to CC on a day": np.transpose(np.array(array_prop_d2cc_chc2_max)),
    "Max prop of E-type patients referred to CC on a day": np.transpose(np.array(array_prop_e2cc_chc2_max)),
    "Max prop of F-type patients referred to CC on a day": np.transpose(np.array(array_prop_f2cc_chc2_max)),

    "Max prop of A-type patients referred to DH on a day": np.transpose(np.array(array_prop_a2dh_chc2_max)),
    "Max prop of B-type patients referred to DH on a day": np.transpose(np.array(array_prop_b2dh_chc2_max)),
    "Max prop of C-type patients referred to DH on a day": np.transpose(np.array(array_prop_c2dh_chc2_max)),
    "Max prop of D-type patients referred to DH on a day": np.transpose(np.array(array_prop_d2dh_chc2_max)),
    "Max prop of E-type patients referred to DH on a day": np.transpose(np.array(array_prop_e2dh_chc2_max)),
    "Max prop of F-type patients referred to DH on a day": np.transpose(np.array(array_prop_f2dh_chc2_max)),

    "Avg  prop of A-type patients referred to CC on a day": np.transpose(np.array(array_prop_a2cc_chc2_avg)),
    "Avg prop of B-type patients referred to CC on a day": np.transpose(np.array(array_prop_b2cc_chc2_avg)),
    "Avg prop of C-type patients referred to CC on a day": np.transpose(np.array(array_prop_c2cc_chc2_avg)),
    "Avg prop of D-type patients referred to CC on a day": np.transpose(np.array(array_prop_d2cc_chc2_avg)),
    "Avg prop of E-type patients referred to CC on a day": np.transpose(np.array(array_prop_e2cc_chc2_avg)),
    "Avg prop of F-type patients referred to CC on a day": np.transpose(np.array(array_prop_f2cc_chc2_avg)),

    "Avg prop of A-type patients referred to DH on a day": np.transpose(np.array(array_prop_a2dh_chc2_avg)),
    "Avg prop of B-type patients referred to DH on a day": np.transpose(np.array(array_prop_b2dh_chc2_avg)),
    "Avg prop of C-type patients referred to DH on a day": np.transpose(np.array(array_prop_c2dh_chc2_avg)),
    "Avg prop of D-type patients referred to DH on a day": np.transpose(np.array(array_prop_d2dh_chc2_avg)),
    "Avg prop of E-type patients referred to DH on a day": np.transpose(np.array(array_prop_e2dh_chc2_avg)),
    "Avg prop of F-type patients referred to DH on a day": np.transpose(np.array(array_prop_f2dh_chc2_avg)),
    "Avg/day severe patients": np.transpose(np.array(array_severe_chc2)),
    "Avg/day moderate patients ": np.transpose(np.array(array_moderate_chc2)),


})

df_CHC3 = pd.DataFrame({
    # "Total registered OPDs": np.transpose(np.array(array_opd_patients_chc3)),
    "OPD patient count": np.transpose(np.array(array_medicine_count_chc3)),
    # "Pediatrician patient count": np.transpose(np.array(array_ped_count_chc3)),
    # "NCD patient count": np.transpose(np.array(array_ncd_count_chc3)),
    # "Pharmacy patient count":np.transpose(np.array(array_pharmacy_count_chc3)),
    "Childbirth cases": np.transpose(np.array(array_childbirth_count_chc3)),
    "Childbirth referred": np.transpose(np.array(array_childbirth_referred_chc3)),
    "Delivery count": np.transpose(np.array(array_del_count_chc3)),
    "Inpatient surgery count": np.transpose(np.array(array_ipd_surgery_count_chc3)),
    # "Inpatient d_count": np.transpose(np.array(array_ipd_del_count_chc3)),
    "Inpatient e_count": np.transpose(np.array(array_emer_inpatients_chc3)),
    "Total covid patients CHC": np.transpose(np.array(array_covid_count_chc3)),
    "COVID severe count": np.transpose(np.array(array_chc3_severe_covid)),
    "COVID moderate count": np.transpose(np.array(array_chc3_moderate_covid)),
    "Covid refered from PHC": np.transpose(np.array(array_phc2chc_count_chc3)),
    "Severe patients referred to DH": np.transpose(np.array(array_dh_refer_chc1)),
    "Covid Patients referred from CHC for Institutional Quarantine in Covid Care Center": np.transpose(
        np.array(array_isolation_ward_refer_from_CHC_chc3)),
    "Moderate patients refered to DH": np.transpose(np.array(array_moderate_refered_chc3)),
    "Moderate patients referred to CC": np.transpose(np.array(array_chc3_to_cc_moderate_case)),
    "Severe patients referred to CC": np.transpose(np.array(array_chc3_to_cc_severe_case)),
    "Inpatient doc occupan": np.transpose(np.array(array_ipd_MO_occupancy_chc3)),
    "Inpatient bed occ system": np.transpose(np.array(chc3_ipd_occupancy)),
    "Inpatient bed wait system": np.transpose(np.array(chc3_ipd_wait)),
    "Manual IPD bed wait time": np.transpose(np.array(array_ipd_bed_wt_chc3)),
    "Manual Inpatiend bed occ": np.transpose(np.array(array_ipd_bed_time_m_chc3)),
    "COVID bed max occupancy": np.transpose(np.array(chc3_max_bed_occ_covid)),
    "IPD nurse manual util": np.transpose(np.array(array_staffnurse_occupancy_chc3)),

    "OPD medicine occupancy": np.transpose(np.array(array_medicine_doctor_occupancy_chc3)),
    "OPD medicine queue waiting time": np.transpose(np.array(array_opd_q_waiting_time_chc3)),
    "OPD medicine queue length": np.transpose(np.array(array_opd_q_length_chc3)),
    "Covid bed waiting time": np.transpose(np.array(array_covid_bed_waiting_time_chc3)),
    "Manual Covid bed occ": np.transpose(np.array(array_chc3_covid_bed_occ)),
    "Covid bed length queue": np.transpose(np.array(array_covid_q_length_chc3)),
    "Manual covid bed waiting time": np.transpose(np.array(array_c_bed_wait_chc3)),
    "Lab occupancy": np.transpose(np.array(array_lab_occupancy_chc3)),
    "Lab waiting time ": np.transpose(np.array(array_lab_q_waiting_time_chc3)),
    "People in queue after OPD hours": np.transpose(np.array(array_q_len_chc3)),
    "Distance from CHC to CC": np.transpose(np.array(array_chc3_to_cc)),
    "Distance from CHC to DH": np.transpose(np.array(array_chc3_to_dh)),


    "inpatient bed waiting time": np.transpose(np.array(array_ip_waiting_time_chc3)),
    "Max prop of A-type patients referred to CC on a day": np.transpose(np.array(array_prop_a2cc_chc3_max)),
    "Max prop of B-type patients referred to CC on a day": np.transpose(np.array(array_prop_b2cc_chc3_max)),
    "Max prop of C-type patients referred to CC on a day": np.transpose(np.array(array_prop_c2cc_chc3_max)),
    "Max prop of D-type patients referred to CC on a day": np.transpose(np.array(array_prop_d2cc_chc3_max)),
    "Max prop of E-type patients referred to CC on a day": np.transpose(np.array(array_prop_e2cc_chc3_max)),
    "Max prop of F-type patients referred to CC on a day": np.transpose(np.array(array_prop_f2cc_chc3_max)),

    "Max prop of A-type patients referred to DH on a day": np.transpose(np.array(array_prop_a2dh_chc3_max)),
    "Max prop of B-type patients referred to DH on a day": np.transpose(np.array(array_prop_b2dh_chc3_max)),
    "Max prop of C-type patients referred to DH on a day": np.transpose(np.array(array_prop_c2dh_chc3_max)),
    "Max prop of D-type patients referred to DH on a day": np.transpose(np.array(array_prop_d2dh_chc3_max)),
    "Max prop of E-type patients referred to DH on a day": np.transpose(np.array(array_prop_e2dh_chc3_max)),
    "Max prop of F-type patients referred to DH on a day": np.transpose(np.array(array_prop_f2dh_chc3_max)),

    "Avg  prop of A-type patients referred to CC on a day": np.transpose(np.array(array_prop_a2cc_chc3_avg)),
    "Avg prop of B-type patients referred to CC on a day": np.transpose(np.array(array_prop_b2cc_chc3_avg)),
    "Avg prop of C-type patients referred to CC on a day": np.transpose(np.array(array_prop_c2cc_chc3_avg)),
    "Avg prop of D-type patients referred to CC on a day": np.transpose(np.array(array_prop_d2cc_chc3_avg)),
    "Avg prop of E-type patients referred to CC on a day": np.transpose(np.array(array_prop_e2cc_chc3_avg)),
    "Avg prop of F-type patients referred to CC on a day": np.transpose(np.array(array_prop_f2cc_chc3_avg)),

    "Avg prop of A-type patients referred to DH on a day": np.transpose(np.array(array_prop_a2dh_chc3_avg)),
    "Avg prop of B-type patients referred to DH on a day": np.transpose(np.array(array_prop_b2dh_chc3_avg)),
    "Avg prop of C-type patients referred to DH on a day": np.transpose(np.array(array_prop_c2dh_chc3_avg)),
    "Avg prop of D-type patients referred to DH on a day": np.transpose(np.array(array_prop_d2dh_chc3_avg)),
    "Avg prop of E-type patients referred to DH on a day": np.transpose(np.array(array_prop_e2dh_chc3_avg)),
    "Avg prop of F-type patients referred to DH on a day": np.transpose(np.array(array_prop_f2dh_chc3_avg)),
    "Avg/day severe patients": np.transpose(np.array(array_severe_chc3)),
    "Avg/day moderate patients ": np.transpose(np.array(array_moderate_chc3)),

})

df1 = pd.DataFrame({

    "Mean OPD medicine queue waiting time": [np.mean(np.array(array_opd_q_waiting_time1)),
np.mean(np.array(array_opd_q_waiting_time_PHC2)),
np.mean(np.array(array_opd_q_waiting_time_PHC3)),
np.mean(np.array(array_opd_q_waiting_time_PHC4)),
np.mean(np.array(array_opd_q_waiting_time_PHC5)),
np.mean(np.array(array_opd_q_waiting_time_PHC6)),
np.mean(np.array(array_opd_q_waiting_time_PHC7)),
np.mean(np.array(array_opd_q_waiting_time_PHC8)),
np.mean(np.array(array_opd_q_waiting_time_PHC9)),
np.mean(np.array(array_opd_q_waiting_time_PHC10))],

"Std dev OPD medicine queue waiting time": [np.std(np.array(array_opd_q_waiting_time1)),
np.std(np.array(array_opd_q_waiting_time_PHC2)),
np.std(np.array(array_opd_q_waiting_time_PHC3)),
np.std(np.array(array_opd_q_waiting_time_PHC4)),
np.std(np.array(array_opd_q_waiting_time_PHC5)),
np.std(np.array(array_opd_q_waiting_time_PHC6)),
np.std(np.array(array_opd_q_waiting_time_PHC7)),
np.std(np.array(array_opd_q_waiting_time_PHC8)),
np.std(np.array(array_opd_q_waiting_time_PHC9)),
np.std(np.array(array_opd_q_waiting_time_PHC10))],

 "Mean OPD medicine queue waiting time": [np.mean(np.array(array_lab_q_waiting_time1)),
np.mean(np.array(array_lab_q_waiting_time_PHC2)),
np.mean(np.array(array_lab_q_waiting_time_PHC3)),
np.mean(np.array(array_lab_q_waiting_time_PHC4)),
np.mean(np.array(array_lab_q_waiting_time_PHC5)),
np.mean(np.array(array_lab_q_waiting_time_PHC6)),
np.mean(np.array(array_lab_q_waiting_time_PHC7)),
np.mean(np.array(array_lab_q_waiting_time_PHC8)),
np.mean(np.array(array_lab_q_waiting_time_PHC9)),
np.mean(np.array(array_lab_q_waiting_time_PHC10))],

"Std dev OPD medicine queue waiting time": [np.std(np.array(array_lab_q_waiting_time1)),
np.std(np.array(array_lab_q_waiting_time_PHC2)),
np.std(np.array(array_lab_q_waiting_time_PHC3)),
np.std(np.array(array_lab_q_waiting_time_PHC4)),
np.std(np.array(array_lab_q_waiting_time_PHC5)),
np.std(np.array(array_lab_q_waiting_time_PHC6)),
np.std(np.array(array_lab_q_waiting_time_PHC7)),
np.std(np.array(array_lab_q_waiting_time_PHC8)),
np.std(np.array(array_lab_q_waiting_time_PHC9)),
np.std(np.array(array_lab_q_waiting_time_PHC10))],

    "Mean OPD medicine occupancy": [np.mean(np.array(array_medicine_doctor_occupancy1)),
np.mean(np.array(array_medicine_doctor_occupancy_PHC2)),
np.mean(np.array(array_medicine_doctor_occupancy_PHC3)),
np.mean(np.array(array_medicine_doctor_occupancy_PHC4)),
np.mean(np.array(array_medicine_doctor_occupancy_PHC5)),
np.mean(np.array(array_medicine_doctor_occupancy_PHC6)),
np.mean(np.array(array_medicine_doctor_occupancy_PHC7)),
np.mean(np.array(array_medicine_doctor_occupancy_PHC8)),
np.mean(np.array(array_medicine_doctor_occupancy_PHC9)),
np.mean(np.array(array_medicine_doctor_occupancy_PHC10))],

    "STD OPD medicine occupancy": [np.std(np.array(array_medicine_doctor_occupancy1)),
np.std(np.array(array_medicine_doctor_occupancy_PHC2)),
np.std(np.array(array_medicine_doctor_occupancy_PHC3)),
np.std(np.array(array_medicine_doctor_occupancy_PHC4)),
np.std(np.array(array_medicine_doctor_occupancy_PHC5)),
np.std(np.array(array_medicine_doctor_occupancy_PHC6)),
np.std(np.array(array_medicine_doctor_occupancy_PHC7)),
np.std(np.array(array_medicine_doctor_occupancy_PHC8)),
np.std(np.array(array_medicine_doctor_occupancy_PHC9)),
np.std(np.array(array_medicine_doctor_occupancy_PHC10))],

    "Manual Inpatient bed occ": [np.mean(np.array(array_ipd_bed_time_m1)),
np.mean(np.array(array_ipd_bed_time_m_PHC2)),
np.mean(np.array(array_ipd_bed_time_m_PHC3)),
np.mean(np.array(array_ipd_bed_time_m_PHC4)),
np.mean(np.array(array_ipd_bed_time_m_PHC5)),
np.mean(np.array(array_ipd_bed_time_m_PHC6)),
np.mean(np.array(array_ipd_bed_time_m_PHC7)),
np.mean(np.array(array_ipd_bed_time_m_PHC8)),
np.mean(np.array(array_ipd_bed_time_m_PHC9)),
np.mean(np.array(array_ipd_bed_time_m_PHC10))],

    "STD Manual Inpatient bed occ": [np.std(np.array(array_ipd_bed_time_m1)),
np.std(np.array(array_ipd_bed_time_m_PHC2)),
np.std(np.array(array_ipd_bed_time_m_PHC3)),
np.std(np.array(array_ipd_bed_time_m_PHC4)),
np.std(np.array(array_ipd_bed_time_m_PHC5)),
np.std(np.array(array_ipd_bed_time_m_PHC6)),
np.std(np.array(array_ipd_bed_time_m_PHC7)),
np.std(np.array(array_ipd_bed_time_m_PHC8)),
np.std(np.array(array_ipd_bed_time_m_PHC9)),
np.std(np.array(array_ipd_bed_time_m_PHC10))],

    "Mean Lab occupancy": [np.mean(np.array(array_lab_occupancy1)),
np.mean(np.array(array_lab_occupancy_PHC2)),
np.mean(np.array(array_lab_occupancy_PHC3)),
np.mean(np.array(array_lab_occupancy_PHC4)),
np.mean(np.array(array_lab_occupancy_PHC5)),
np.mean(np.array(array_lab_occupancy_PHC6)),
np.mean(np.array(array_lab_occupancy_PHC7)),
np.mean(np.array(array_lab_occupancy_PHC8)),
np.mean(np.array(array_lab_occupancy_PHC9)),
np.mean(np.array(array_lab_occupancy_PHC10))],

"Std Lab occupancy": [np.std(np.array(array_lab_occupancy1)),
np.std(np.array(array_lab_occupancy_PHC2)),
np.std(np.array(array_lab_occupancy_PHC3)),
np.std(np.array(array_lab_occupancy_PHC4)),
np.std(np.array(array_lab_occupancy_PHC5)),
np.std(np.array(array_lab_occupancy_PHC6)),
np.std(np.array(array_lab_occupancy_PHC7)),
np.std(np.array(array_lab_occupancy_PHC8)),
np.std(np.array(array_lab_occupancy_PHC9)),
np.std(np.array(array_lab_occupancy_PHC10))],

        "Mean IPD Nurse occ": [np.mean(np.array(array_staffnurse_occupancy1)),
np.mean(np.array(array_staffnurse_occupancy_PHC2)),
np.mean(np.array(array_staffnurse_occupancy_PHC3)),
np.mean(np.array(array_staffnurse_occupancy_PHC4)),
np.mean(np.array(array_staffnurse_occupancy_PHC5)),
np.mean(np.array(array_staffnurse_occupancy_PHC6)),
np.mean(np.array(array_staffnurse_occupancy_PHC7)),
np.mean(np.array(array_staffnurse_occupancy_PHC8)),
np.mean(np.array(array_staffnurse_occupancy_PHC9)),
np.mean(np.array(array_staffnurse_occupancy_PHC10)),
                          ],

        "Std IPD Nurse occ": [np.std(np.array(array_staffnurse_occupancy1)),
np.std(np.array(array_staffnurse_occupancy_PHC2)),
np.std(np.array(array_staffnurse_occupancy_PHC3)),
np.std(np.array(array_staffnurse_occupancy_PHC4)),
np.std(np.array(array_staffnurse_occupancy_PHC5)),
np.std(np.array(array_staffnurse_occupancy_PHC6)),
np.std(np.array(array_staffnurse_occupancy_PHC7)),
np.std(np.array(array_staffnurse_occupancy_PHC8)),
np.std(np.array(array_staffnurse_occupancy_PHC9)),
np.std(np.array(array_staffnurse_occupancy_PHC10)),
                          ]})
new = []
new1 = []
new2 = []
new3 = []
new_PHC2 = []
new1_PHC2 = []
new2_PHC2 = []
new3_PHC2 = []
new_PHC3 = []
new1_PHC3 = []
new2_PHC3 = []
new3_PHC3 = []

new_PHC4 = []
new1_PHC4 = []
new2_PHC4 = []
new3_PHC4 = []
new_PHC5 = []
new1_PHC5 = []
new2_PHC5 = []
new3_PHC5 = []
new_PHC6 = []
new1_PHC6 = []
new2_PHC6 = []
new3_PHC6 = []

new_PHC7 = []
new1_PHC7 = []
new2_PHC7 = []
new3_PHC7 = []
new_PHC8 = []
new1_PHC8 = []
new2_PHC8 = []
new3_PHC8 = []

new_PHC9 = []
new1_PHC9 = []
new2_PHC9 = []
new3_PHC9 = []

new_PHC10 = []
new1_PHC10 = []
new2_PHC10 = []
new3_PHC10 = []


with np.errstate(divide='ignore', invalid='ignore'):
    new = np.true_divide(np.array(array_isolation_ward_refer1), np.array(array_covid_count1))
    new[new == np.inf] = 0
    new = np.nan_to_num(new)
    new1 = np.true_divide(np.array(array_chc_refer1), np.array(array_covid_count1))
    new1[new1 == np.inf] = 0
    new1 = np.nan_to_num(new1)
    new2 = np.true_divide(np.array(array_phc1_to_cc_severe_case), np.array(array_covid_count1))
    new2[new2 == np.inf] = 0
    new2 = np.nan_to_num(new2)
    new3 = np.true_divide(np.array(array_dh_refer1), np.array(array_covid_count1))
    new3[new3 == np.inf] = 0
    new3 = np.nan_to_num(new3)

    new_PHC2 = np.true_divide(np.array(array_isolation_ward_refer_PHC2), np.array(array_covid_count_PHC2))
    new_PHC2[new_PHC2 == np.inf] = 0
    new_PHC2 = np.nan_to_num(new_PHC2)
    new1_PHC2 = np.true_divide(np.array(array_chc_refer_PHC2), np.array(array_covid_count_PHC2))
    new1_PHC2[new1_PHC2 == np.inf] = 0
    new1_PHC2 = np.nan_to_num(new1)
    new2_PHC2 = np.true_divide(np.array(array_phc2_to_cc_severe_case), np.array(array_covid_count_PHC2))
    new2_PHC2[new2 == np.inf] = 0
    new2_PHC2= np.nan_to_num(new2_PHC2)
    new3_PHC2= np.true_divide(np.array(array_dh_refer1), np.array(array_covid_count1))
    new3_PHC2[new3_PHC2 == np.inf] = 0
    new3_PHC2 = np.nan_to_num(new3_PHC2)

    new_PHC3 = np.true_divide(np.array(array_isolation_ward_refer_PHC3), np.array(array_covid_count_PHC3))
    new_PHC3[new_PHC3 == np.inf] = 0
    new_PHC3 = np.nan_to_num(new_PHC3)
    new1_PHC3 = np.true_divide(np.array(array_chc_refer_PHC3), np.array(array_covid_count_PHC3))
    new1_PHC3[new1_PHC3 == np.inf] = 0
    new1_PHC3 = np.nan_to_num(new1_PHC3)
    new2_PHC3 = np.true_divide(np.array(array_phc3_to_cc_severe_case), np.array(array_covid_count_PHC3))
    new2_PHC3[new2_PHC3 == np.inf] = 0
    new2_PHC3 = np.nan_to_num(new2_PHC3)
    new3_PHC3 = np.true_divide(np.array(array_dh_refer_PHC3), np.array(array_covid_count_PHC3))
    new3_PHC3[new3_PHC3 == np.inf] = 0
    new3_PHC3 = np.nan_to_num(new3_PHC3)

    new_PHC4 = np.true_divide(np.array(array_isolation_ward_refer_PHC4), np.array(array_covid_count_PHC4))
    new_PHC4[new_PHC4 == np.inf] = 0
    new_PHC4 = np.nan_to_num(new_PHC4)
    new1_PHC4 = np.true_divide(np.array(array_chc_refer_PHC4), np.array(array_covid_count_PHC4))
    new1_PHC4[new1_PHC4 == np.inf] = 0
    new1_PHC4 = np.nan_to_num(new1_PHC4)
    new2_PHC4 = np.true_divide(np.array(array_phc4_to_cc_severe_case), np.array(array_covid_count_PHC4))
    new2_PHC4[new2_PHC4 == np.inf] = 0
    new2_PHC4 = np.nan_to_num(new2_PHC4)
    new3_PHC4 = np.true_divide(np.array(array_dh_refer_PHC4), np.array(array_covid_count_PHC4))
    new3_PHC4[new3_PHC4 == np.inf] = 0
    new3_PHC4 = np.nan_to_num(new3_PHC4)

    new_PHC5 = np.true_divide(np.array(array_isolation_ward_refer_PHC5), np.array(array_covid_count_PHC5))
    new_PHC5[new_PHC5 == np.inf] = 0
    new_PHC5 = np.nan_to_num(new_PHC5)
    new1_PHC5 = np.true_divide(np.array(array_chc_refer_PHC5), np.array(array_covid_count_PHC5))
    new1_PHC5[new1_PHC5 == np.inf] = 0
    new1_PHC5 = np.nan_to_num(new1_PHC5)
    new2_PHC5 = np.true_divide(np.array(array_phc5_to_cc_severe_case), np.array(array_covid_count_PHC5))
    new2_PHC5[new2_PHC5 == np.inf] = 0
    new2_PHC5 = np.nan_to_num(new2_PHC5)
    new3_PHC5 = np.true_divide(np.array(array_dh_refer_PHC5), np.array(array_covid_count_PHC5))
    new3_PHC5[new3_PHC5 == np.inf] = 0
    new3_PHC5 = np.nan_to_num(new3_PHC5)

    new_PHC6 = np.true_divide(np.array(array_isolation_ward_refer_PHC6), np.array(array_covid_count_PHC6))
    new_PHC6[new_PHC6 == np.inf] = 0
    new_PHC6 = np.nan_to_num(new_PHC6)
    new1_PHC6 = np.true_divide(np.array(array_chc_refer_PHC6), np.array(array_covid_count_PHC6))
    new1_PHC6[new1_PHC6 == np.inf] = 0
    new1_PHC6 = np.nan_to_num(new1_PHC6)
    new2_PHC6 = np.true_divide(np.array(array_phc6_to_cc_severe_case), np.array(array_covid_count_PHC6))
    new2_PHC6[new2_PHC6 == np.inf] = 0
    new2_PHC6 = np.nan_to_num(new2_PHC6)
    new3_PHC6 = np.true_divide(np.array(array_dh_refer_PHC6), np.array(array_covid_count_PHC6))
    new3_PHC6[new3_PHC6 == np.inf] = 0
    new3_PHC6 = np.nan_to_num(new3_PHC6)

    new_PHC7 = np.true_divide(np.array(array_isolation_ward_refer_PHC7), np.array(array_covid_count_PHC7))
    new_PHC7[new_PHC7 == np.inf] = 0
    new_PHC7 = np.nan_to_num(new_PHC7)
    new1_PHC7 = np.true_divide(np.array(array_chc_refer_PHC7), np.array(array_covid_count_PHC7))
    new1_PHC7[new1_PHC7 == np.inf] = 0
    new1_PHC7 = np.nan_to_num(new1_PHC7)
    new2_PHC7 = np.true_divide(np.array(array_phc7_to_cc_severe_case), np.array(array_covid_count_PHC7))
    new2_PHC7[new2_PHC7 == np.inf] = 0
    new2_PHC7 = np.nan_to_num(new2_PHC7)
    new3_PHC7 = np.true_divide(np.array(array_dh_refer_PHC7), np.array(array_covid_count_PHC7))
    new3_PHC7[new3_PHC7 == np.inf] = 0
    new3_PHC7 = np.nan_to_num(new3_PHC7)

    new_PHC8 = np.true_divide(np.array(array_isolation_ward_refer_PHC8), np.array(array_covid_count_PHC8))
    new_PHC8[new_PHC8 == np.inf] = 0
    new_PHC8 = np.nan_to_num(new_PHC8)
    new1_PHC8 = np.true_divide(np.array(array_chc_refer_PHC8), np.array(array_covid_count_PHC8))
    new1_PHC8[new1_PHC8 == np.inf] = 0
    new1_PHC8 = np.nan_to_num(new1_PHC8)
    new2_PHC8 = np.true_divide(np.array(array_phc8_to_cc_severe_case), np.array(array_covid_count_PHC8))
    new2_PHC8[new2_PHC8 == np.inf] = 0
    new2_PHC8 = np.nan_to_num(new2_PHC8)
    new3_PHC8 = np.true_divide(np.array(array_dh_refer_PHC8), np.array(array_covid_count_PHC8))
    new3_PHC8[new3_PHC8 == np.inf] = 0
    new3_PHC8 = np.nan_to_num(new3_PHC8)

    new_PHC9 = np.true_divide(np.array(array_isolation_ward_refer_PHC9), np.array(array_covid_count_PHC9))
    new_PHC9[new_PHC9 == np.inf] = 0
    new_PHC9 = np.nan_to_num(new_PHC9)
    new1_PHC9 = np.true_divide(np.array(array_chc_refer_PHC9), np.array(array_covid_count_PHC9))
    new1_PHC9[new1_PHC9 == np.inf] = 0
    new1_PHC9 = np.nan_to_num(new1_PHC9)
    new2_PHC9 = np.true_divide(np.array(array_phc9_to_cc_severe_case), np.array(array_covid_count_PHC9))
    new2_PHC9[new2_PHC9 == np.inf] = 0
    new2_PHC9 = np.nan_to_num(new2_PHC9)
    new3_PHC9 = np.true_divide(np.array(array_dh_refer_PHC9), np.array(array_covid_count_PHC9))
    new3_PHC9[new3_PHC9 == np.inf] = 0
    new3_PHC9 = np.nan_to_num(new3_PHC9)

    new_PHC10 = np.true_divide(np.array(array_isolation_ward_refer_PHC10), np.array(array_covid_count_PHC10))
    new_PHC10[new_PHC10 == np.inf] = 0
    new_PHC10 = np.nan_to_num(new_PHC10)
    new1_PHC10 = np.true_divide(np.array(array_chc_refer_PHC10), np.array(array_covid_count_PHC10))
    new1_PHC10[new1_PHC10 == np.inf] = 0
    new1_PHC10 = np.nan_to_num(new1_PHC10)
    new2_PHC10 = np.true_divide(np.array(array_phc10_to_cc_severe_case), np.array(array_covid_count_PHC10))
    new2_PHC10[new2_PHC10 == np.inf] = 0
    new2_PHC10 = np.nan_to_num(new2_PHC10)
    new3_PHC10 = np.true_divide(np.array(array_dh_refer_PHC10), np.array(array_covid_count_PHC10))
    new3_PHC10[new3_PHC10 == np.inf] = 0
    new3_PHC10 = np.nan_to_num(new3_PHC10)



df222 = pd.DataFrame({"Prop institutional" : (new),
                      "Prop refererd to CHC":(new1),
                      "Prop referred to CC": (new3),
                      "Prop referred to DH": (new2),
                      "2 Prop institutional": (new_PHC2),
                      "2 Prop refererd to CHC": (new1_PHC2),
                      "2 Prop referred to CC": (new3_PHC2),
                      "2 Prop referred to DH": (new2_PHC2),
                      "3 Prop institutional": (new_PHC3),
                      "3 Prop refererd to CHC": (new1_PHC3),
                      "3 Prop referred to CC": (new3_PHC3),
                      "3 Prop referred to DH": (new2_PHC3),
                      "4 Prop institutional": (new_PHC4),
                      "4 Prop refererd to CHC": (new1_PHC4),
                      "4 Prop referred to CC": (new3_PHC4),
                      "4 Prop referred to DH": (new2_PHC4),
                      "5 Prop institutional": (new_PHC5),
                      "5 Prop refererd to CHC": (new1_PHC5),
                      "5 Prop referred to CC": (new3_PHC5),
                      "5 Prop referred to DH": (new2_PHC5),
                      "6 Prop institutional": (new_PHC6),
                      "6 Prop refererd to CHC": (new1_PHC6),
                      "6 Prop referred to CC": (new3_PHC6),
                      "6 Prop referred to DH": (new2_PHC6),
                      "7 Prop institutional": (new_PHC7),
                      "7Prop refererd to CHC": (new1_PHC7),
                      "7 Prop referred to CC": (new3_PHC7),
                      "7 Prop referred to DH": (new2_PHC7),
                      "8Prop institutional": (new_PHC8),
                      "8 Prop refererd to CHC": (new1_PHC8),
                      "8  Prop referred to CC": (new3_PHC8),
                      "8 Prop referred to DH": (new2_PHC8),
                      "9 Prop institutional": (new_PHC9),
                      "9 Prop refererd to CHC": (new1_PHC9),
                      "9 Prop referred to CC": (new3_PHC9),
                      "9 Prop referred to DH": (new2_PHC9),
                      "10 Prop institutional": (new_PHC10),
                      "Prop refererd to CHC": (new1_PHC10),
                      "Prop referred to CC": (new3_PHC10),
                      "Prop referred to DH": (new2_PHC10),

                      })


df2 = pd.DataFrame({
    #"Covid Patients Count": (np.transpose(np.array(CovidPatients_list))),
    "DH Gen Doc Occupancy": (np.transpose(np.array(doc_occupancy_DH_Gen))),
    "DH Oxygen Doc Occupancy": (np.transpose(np.array(doc_occupancy_DH_Oxygen))),
    "DH Ventilator Doc Occupancy": (np.transpose(np.array(doc_occupancy_DH_Ventilator))),
    "DH Gen Nurse Occupancy": (np.transpose(np.array(nurse_occupancy_DH_Gen))),
    "DH Oxygen Nurse Occupancy": (np.transpose(np.array(nurse_occupancy_DH_Oxygen))),
    "DH Ventilator Nurse Occupancy": (np.transpose(np.array(nurse_occupancy_DH_Ventilator))),
    #"DH Sample Collection Nurse Occuoancy": (np.transpose(np.array(sample_collctn_nurse_occupancy))),
    #"DH Receptionist Occupancy": (np.transpose(np.array(receptionistoccupancy))),
    "DH General bed Occupancy": (np.transpose(np.array(Generalward_bedoccupancy))),
    "DH ICU oxygen bed Occupancy": (np.transpose(np.array(ICUward_oxygenoccupancy))),
    "DH ICU ventilator Occupancy": (np.transpose(np.array(ICUward_ventilatoroccupancy))),
    #"DH Registration waiting Time": (np.transpose(np.array(waittime_registration))),
    #"DH Triage waiting Time": (np.transpose(np.array(waittime_triage))),
    "DH General ward waiting Time": (np.transpose(np.array(waitime_generalbed))),
    "DH ICU oxygen bed waiting Time": (np.transpose(np.array(waittime_ICUoxygen))),
    #"DH ICU ventilator Time": (np.transpose(np.array(waittime_ICUventilator))),
    "DH waiting time manual": (np.transpose(np.array(array_dh_ven_wait))),
    #"DH Nurse sample collection waiting Time": (np.transpose(np.array(DH_Nurse_sample_collection_wait_time_list))),
    "DH Lab waiting Time": (np.transpose(np.array(waittime_DH_lab))),
    "DH death:": np.transpose(np.array(array_dh_death)),

    "Max type A referred to CC": np.transpose(np.array(array_prop_dh_2_cc_a_max)),
    "Max type B referred to CC": np.transpose(np.array(array_prop_dh_2_cc_b_max)),
    "Max type C referred to CC": np.transpose(np.array(array_prop_dh_2_cc_c_max)),
    "Max type D referred to CC": np.transpose(np.array(array_prop_dh_2_cc_d_max)),
    "Max type E referred to CC": np.transpose(np.array(array_prop_dh_2_cc_e_max)),
    "Max type F referred to CC": np.transpose(np.array(array_prop_dh_2_cc_f_max)),
    "Max type B referred to CC for ICU ox bed": np.transpose(np.array(array_prop_dh_2_cc_b_ox_max)),
    "Max type C referred to CC for ICU ven bed": np.transpose(np.array(array_prop_dh_2_cc_c_ven_max)),
    "Avg type A referred to CC": np.transpose(np.array(array_prop_dh_2_cc_a_avg)),
    "Avg type B referred to CC": np.transpose(np.array(array_prop_dh_2_cc_b_avg)),
    "Avg type C referred to CC": np.transpose(np.array(array_prop_dh_2_cc_c_avg)),
    "Avg type D referred to CC": np.transpose(np.array(array_prop_dh_2_cc_d_avg)),
    "Avg type E referred to CC": np.transpose(np.array(array_prop_dh_2_cc_e_avg)),
    "Avg type F referred to CC": np.transpose(np.array(array_prop_dh_2_cc_f_avg)),
    "Avg type B referred to CC for ICU ox bed": np.transpose(np.array(array_prop_dh_2_cc_b_ox_avg)),
    "Avg type C referred to CC for ICU ven bed": np.transpose(np.array(array_prop_dh_2_cc_c_ven_avg)),
    "Moderate  patient count" : np.transpose(np.array(array_moderate_total)),
    "A  patient count" : np.transpose(np.array(array_moderate_A)),
    "B  patient count" : np.transpose(np.array(array_moderate_B)),
    "C  patient count" : np.transpose(np.array(array_moderate_C)),
    "Severe  patient count" : np.transpose(np.array(array_severe_total)),
    "D  patient count" : np.transpose(np.array(array_severe_D)),
    "E  patient count" : np.transpose(np.array(array_severe_E)),
    "F  patient count" : np.transpose(np.array(array_severe_F)),

})

df3 = pd.DataFrame({
    "General ward nurse manual util": np.transpose(np.array(array_G_nurse_occupancy1)),
#"ICU ox ward nurse util": np.transpose(np.array(array_O_nurse_occupancy)),
    "ICU ox ward nurse manual util": np.transpose(np.array(array_O_nurse_occupancy1)),
 #   "ICU ven ward nurse util": np.transpose(np.array(array_V_nurse_occupancy)),
    "ICU ven ward nurse manual util": np.transpose(np.array(array_V_nurse_occupancy1)),
    "General ward doc manual util": np.transpose(np.array(array_G_doctor_occupancy1)),
    "ICU ox ward doc manual util": np.transpose(np.array(array_O_doctor_occupancy1)),
    "ICU ven ward doc manual util": np.transpose(np.array(array_V_doctor_occupancy1)),
    "General ward bed util": np.transpose(np.array(array_g_bed_occ)),
    "ICU ox ward bed util": np.transpose(np.array(array_o_bed_occ)),
    "ICU ven ward bed util": np.transpose(np.array(array_v_bed_occ)),
    "Isolation ward Occupancy": np.transpose(np.array(array_isolation_bed_occupancy)),
    "Gen ward bed wait time": np.transpose(np.array(array_g_bed_wt)),
    "ICU oxward bed wait time": np.transpose(np.array(array_o_bed_wt)),
    "ICU ven ward bed wait time": np.transpose(np.array(array_v_bed_wt)),
    "Iso ward bed wait time": np.transpose(np.array(array_iso_bed_wt)),
    "Iso ward manual wait time": np.transpose(np.array(array_m_iso_bed_wt)),
    "Number of isolation cases": np.transpose(np.array(array_isolation_count)),
    "Number of severe cases": np.transpose(np.array(array_severe_count)),
    "Number of type A cases": np.transpose(np.array(array_A_count)),
    "Number of type B cases": np.transpose(np.array(array_B_count)),
    "Number of type C cases": np.transpose(np.array(array_C_count)),
    "Number of type D cases": np.transpose(np.array(array_D_count)),
    "Number of type E cases": np.transpose(np.array(array_E_count)),
    "Number of type F cases": np.transpose(np.array(array_F_count)),
})

tyu = pd.ExcelWriter('SimulationOutput4.xlsx', engine='xlsxwriter')

df3.transpose().to_excel(tyu, sheet_name="CC")
df1.transpose().to_excel(tyu, sheet_name="PHC1")
df_CHC2.transpose().to_excel(tyu, sheet_name="CHC1")
df.transpose().to_excel(tyu, sheet_name="CHC2")
df_CHC3.transpose().to_excel(tyu, sheet_name="CHC3")
df2.transpose().to_excel(tyu, sheet_name="DH")
df222.transpose().to_excel(tyu, sheet_name = "new")
tyu.save()
a2 = datetime.datetime.now()
print(a2 - a1)
