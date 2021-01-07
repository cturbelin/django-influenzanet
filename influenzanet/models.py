from optparse import make_option
from django.db import models
from django.conf import settings
from django.contrib.auth.models import User

USE_ANONYMIZE = getattr(settings,'IFN_USE_ANONYMIZE', False)

ACTION_ANONYMZE = 'ANO'
ACTION_DELETE = 'DEL'

ACTIONS_TYPE = (
      (ACTION_ANONYMZE, 'Anonymized'),
      (ACTION_DELETE, 'Deleted'),
)

if USE_ANONYMIZE:
    class AnonymizedUser(models.Model):
        user = models.OneToOneField(User, primary_key=True)
        date = models.DateTimeField(auto_now_add=True)
        action = models.CharField(max_length=3, choices=ACTIONS_TYPE)
        request_id = models.IntegerField(null=False)
else:
    # Fake class just to be able to run the app without failing, but command wil not work obviously
    class AnonymizedUser:
        pass

