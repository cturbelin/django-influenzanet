'''
Anonymize user account (or remove)

@author: clementturbelin
'''
from django.core.management.base import BaseCommand
from optparse import make_option
from apps.pollster import models
from django.conf import settings
from django.contrib.auth.models import UNUSABLE_PASSWORD, User
from apps.survey.models import SurveyUser
from django.db import connection,transaction
from ...models import USE_ANONYMIZE, ACTION_ANONYMZE, ACTION_DELETE, AnonymizedUser
import datetime

class Command(BaseCommand):
    help = 'Anonymize account from survey info'

    option_list = BaseCommand.option_list + (
        make_option('-c', '--commit', action='store_true',  dest='commit', help='Validate changes (dont by default'),
        make_option('-d', '--debug', action='store_true',  dest='debug', help='Debug mode (show query)'),
    )

    def get_data_tables(self):
        query = "select table_name from information_schema.tables where \"table_schema\"='public' and \"table_type\"='BASE TABLE' and \"table_name\" like %(like)s and table_name != %(table)s"
        cursor = connection.cursor()
        if self.debug :
            print(query)
        cursor.execute(query, {'like': 'pollster_results_%', 'table': self.survey_table()})
        results = cursor.fetchall()
        cursor.close()
        return [ r[0] for r in results ]
        
    def survey_table(self):
        return "pollster_results_%s" % (self.survey_name)

    def get_ano_requests(self):
        cursor = connection.cursor()
        query = 'select \"id\", \"user\", \"Q1\" from %s where \"user\" not in(select user_id from influenzanet_anonymizeduser)' % (self.survey_table())
        if self.debug :
            print(query)
        cursor.execute(query)
        results = cursor.fetchall()
        cursor.close()
        data = []
        for r in results:
            d = dict(zip(['id','user','action'], r))
            data.append(d)
        return data

    def handle(self, *args, **options):

        commit = options.get('commit')
        self.debug = options.get('debug')

        if not USE_ANONYMIZE:
            raise Exception("Anonymize feature is not activated")

        self.survey_name = getattr(settings, 'IFN_ANONYMIZE_SURVEY', None)
        
        if self.survey_name is None:
            raise Exception("Anonymize survey is not configured, please define IFN_ANONYMIZE_SURVEY in settings")

        self.data_tables = self.get_data_tables()
        print("found %d tables" % len(self.data_tables))
        print(','.join(self.data_tables))
        commited = False
        with transaction.commit_manually():
            try:
                for req in self.get_ano_requests():
                    user_id = req['user']
                    if req['action'] == 1:
                        action = ACTION_DELETE
                        action_label = "Remove"
                    else:
                        action = ACTION_ANONYMZE
                        action_label = "Anonymize"

                    print("Handling request %d User %d for %s" % (req['id'], user_id, action_label))
                    try:
                        user = User.objects.get(id=user_id)
                    except User.DoesNotExist:
                        print("User %d not found ?" % (user_id))
                        continue
                    self.anonymize(user)
                    if action == ACTION_DELETE:
                        self.delete(user_id)
                    a = AnonymizedUser()
                    a.action = action
                    a.user = user
                    a.request_id = req['id']
                    a.save()
            except Exception as e:
                transaction.rollback()
                raise
            if commit:
                transaction.commit()
                commited = True
            else:
                transaction.rollback()
        if commited:
            print("Changed has been made on the database")
        else:
            print("No change has been made, add --commit option to make the changes")
                
    def anonymize(self, user):
        user_id = user.id
        print("Anonymize user %d" % (user_id))
        uid = "ano-%d" % (user_id)
        user.username= uid
        user.first_name = "anonymized"
        user.last_name = "anonymized"
        user.email = "%s@anonymized.local" % uid
        user.password = UNUSABLE_PASSWORD
        user.is_active = False
        user.save()

        for su in SurveyUser.objects.filter(user=user):
            su.name = "participant-%d" % (su.id)
            su.save()

    def get_user_count(self, table, user_id):
        cursor = connection.cursor()
        query = "select count(*) from %s where \"user\"=%d" % (table, user_id)
        if self.debug :
            print(query)
        cursor.execute(query)
        results = cursor.fetchone()
        cursor.close()
        return results[0]

    def delete_user_data(self, table, user_id):   
        if table == self.survey_table():
            print("Cannot remove from %s " % (self.survey_table()))
            return 0
        cursor = connection.cursor()
        query = "delete from %s where \"user\"=%d" % (table, user_id)
        if self.debug :
            print(query)
        cursor.execute(query)
        count = cursor.rowcount
        cursor.close()
        return count

    def delete(self, user_id):
        print("Delete data for user %d" % (user_id))
        for table in self.data_tables:
            count = self.get_user_count(table, user_id)
            affected = self.delete_user_data(table, user_id)
            print("  - table %s : %d rows, %d removed" % (table, count, affected))