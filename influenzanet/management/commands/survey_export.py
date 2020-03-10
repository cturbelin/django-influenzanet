'''
Created on Mar 1, 2020

Modify a survey according to a json file describing each modifications


@author: clementturbelin
'''
from django.core.management.base import BaseCommand
from apps.pollster import models
from django.template import loader
import datetime

class Command(BaseCommand):
    help = 'Export xml definitions for intake & weekly'
   
    option_list = BaseCommand.option_list + (
    )
      
    def handle(self, *args, **options):
        now = datetime.datetime.now()
        file_id = format(now, '%Y-%m-%d-%H%M')
        
        self.export_survey("weekly", file_id)
        self.export_survey('intake', file_id)
        
    def export_survey(self, shortname, file_id):
        
        survey = models.Survey.objects.get(shortname=shortname) 
        print "Found Survey %s %d "  % (shortname, survey.id)
        
        xml = loader.render_to_string('pollster/survey_export.xml', { "survey": survey }, context_instance=None)
       
        fn = shortname + '_' + file_id + '.xml'
        f = open(fn, 'w')
        f.write(xml)
        f.close()
        