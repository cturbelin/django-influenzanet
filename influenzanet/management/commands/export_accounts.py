from collections import Counter
from sqlite3 import Date
from django.core.management.base import BaseCommand
from apps.survey.models import SurveyUser
from django.contrib.auth.models import User
from django.conf import settings
from django.db import connection

import json
from datetime import datetime

def fetch_one_dict(query, params=None):
    cursor = connection.cursor()
    cursor.execute(query, params)
    r = cursor.fetchone()
    if not r:
        return None
    desc = cursor.description
    columns = []
    for col in desc:
        columns.append(col[0])
    r = dict(zip(columns, r))
    return r 

def calc_age(ym, timestamp):
    if ym is None or ym == "":
        return None
    y, m = ym.split('-')
    birth_date = datetime(int(y), int(m), 15, 0, 0, 0)
    delta = timestamp - birth_date
    days = delta.days
    if days > 0:
        return int(round(days / 365, 0))
    return None


class Command(BaseCommand):
    help = 'Export user accounts'

    #args = '<output>'

    def find_data_tables(self, max=5):
        self.intake_tables = []
        self.weekly_tables = []
        if hasattr(settings, "HISTORICAL_TABLES"):
            hh = getattr(settings, "HISTORICAL_TABLES")
            years = [ int(x) for x in hh.keys() ]
            years.sort(reverse=True)
            years = years[0:max]
            for y in years:
                h = hh.get(str(y))
                self.intake_tables.append(h['intake'])
                self.weekly_tables.append(h['weekly'])
        else:
            self.intake_tables.append("pollster_results_intake")
            self.weekly_tables.append("pollster_results_weekly")
        

    def find_last_intake(self, gid):
        indexes = range(0, len(self.intake_tables) - 1)
        for i in indexes:
            weekly_table = self.weekly_tables[i]
            intake_table = self.intake_tables[i]
            query = "select \"timestamp\", \"Q2\" from " + intake_table + " where \"global_id\"=%s order by \"timestamp\" desc limit 1"
            data = fetch_one_dict(query, [gid])
            if data is None:
                continue
            data['age'] = calc_age(data['Q2'], data['timestamp'])

            return data            
        return None

    def find_main_profile(self, profiles):
        adults = []
        for index, p in enumerate(profiles): 
            d = self.find_last_intake(p['gid'])
            if d is not None:
                age = d['age']
                if age is not None:
                    p['age'] = age
                    p['adult'] = age >= 18
                    adults.append(index)
        main_from = None
        if len(adults) > 0 :
            idx = adults[0]
            if len(adults) == 1:
                main_from = "single_adult"
            else:
                main_from = "first_adult"
            profiles[idx]['main'] = True
            profiles[idx]['main_from'] = main_from
        return profiles, main_from


    def handle(self, *args, **options):

        self.find_data_tables()
        
        users = []

        counter = Counter()
       
        for user in User.objects.filter(is_active=True):
            u = {'login': user.username, 'date_joined': user.date_joined.strftime("%m-%d-%YT%H:%M:%S"), 'email': user.email, 'is_staff': user.is_staff}
            participants = SurveyUser.objects.filter(user=user, deleted=False)
            pp = []
            for su in participants:
                pp.append({'gid': su.global_id, 'name': su.name, 'sid': su.id})

            if len(pp) > 0:
                if len(pp) > 1:
                    pp, main_from = self.find_main_profile(pp)
                    if main_from is not None:
                        counter[main_from] += 1
                    else:
                        counter['unknown'] += 1
                else:
                    pp[0]['main'] = True
                    counter['single_account'] += 1
                counter['count_profiles'] += len(pp)
            u['profiles'] = pp
            users.append(u)

        print(counter)

        output = args[0]

        with open(output, 'w') as f:
            json.dump(users, f)
        print("%d users exported" % len(users))
        
