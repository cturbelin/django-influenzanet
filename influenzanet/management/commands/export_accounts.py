from django.core.management.base import BaseCommand
from apps.survey.models import SurveyUser
from django.contrib.auth.models import User
import json
from datetime import datetime
class Command(BaseCommand):
    help = 'Export user accounts'

    args = '<output>'

    def handle(self, *args, **options):

        users = []

        for user in User.objects.filter(is_active=True):
            u = {'login': user.username, 'date_joined': user.date_joined.strftime("%m-%d-%YT%H:%M:%S"), 'email': user.email, 'is_staff': user.is_staff}
            participants = SurveyUser.objects.filter(user=user, deleted=False)
            pp = []
            for su in participants:
                pp.append({'gid': su.global_id, 'name': su.name})
            u['profiles'] = pp
            users.append(u)

        output = args[0]

        with open(output, 'w') as f:
            json.dump(users, f)
        print("%d users exported" % len(users))
        
