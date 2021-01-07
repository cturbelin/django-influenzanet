'''
Created on Mar 1, 2020

Modify a survey according to a json file describing each modifications


@author: clementturbelin
'''
from optparse import make_option
from django.core.management.base import BaseCommand
from apps.pollster import models
from django.db import transaction
from xml.etree import ElementTree
from apps.pollster.models import TranslationOption, TranslationQuestion,\
    TranslationQuestionRow, TranslationQuestionColumn, TranslationSurvey

def as_trans(xml, prev):
    if xml is None or xml.text is None or xml.text == '':
        if prev is None:
            return ''
        return prev
    return xml.text


class Command(BaseCommand):
    help = 'Update a survey translation from an xml definition'
    option_list = BaseCommand.option_list + (
        make_option('-f', '--file', action='store', type="string",
                    dest='file',
                    help='json file with actions to make on survey'),
        make_option('-s', '--survey', action='store',  dest='survey', help='Target survey shortname'),
        make_option('-c', '--commit', action='store_true',  dest='commit', help='Validate changes (dont by default'),
    )

    def get_question(self, name):
        r = models.Question.objects.get(survey=self.survey, data_name=name)
        return(r)

    def handle(self, *args, **options):

        self.verbosity = int(options.get('verbosity'))

        commit = options.get('commit')
        file = options.get('file')
        shortname = options.get('survey')

        if file is None:
            raise Exception("File not provided")

        root = ElementTree.parse(file).getroot()

        self.survey = models.Survey.objects.get(shortname=shortname)
        print "Found Survey %s %d "  % (shortname, self.survey.id)

        language = root.attrib.get('language')

        try:
            translation = TranslationSurvey.objects.get(survey=self.survey, language=language)
        except TranslationSurvey.DoesNotExist:
            print "Unable to find translation for survey %s with language %s" % (shortname, language)
            return

        self.questions = {}
        for q in self.survey.questions:
            self.questions[q.data_name] = q

        commited = False
        with transaction.commit_manually():
            try:
                idx = 0
                for action in root:
                    self.translate(action, translation)
                    idx = idx + 1
            except Exception as e:
                print "Exception at element %d" % (idx, )
                transaction.rollback()
                raise

            if commit:
                transaction.commit()
                commited = True
            else:
                transaction.rollback()

        if commited:
            print "Changed has been made on survey " + self.survey.shortname

    def translate(self, action, translation):
        attr = action.attrib
        if not 'type' in attr:
            raise Exception("type tag is not provided")
        type = attr['type']
        if not 'question' in attr:
            raise Exception("question tag is not provided")

        data_name = attr['question']
        question = self.questions.get(data_name)
        if question is None:
            raise Exception("Unable to find question '%s'" % (data_name))

        if type == "question":
            self.translate_question(question, translation, action)

        if type == "option":
            self.translate_option(question, translation, action)

        if type == "row":
            self.translate_row(question, translation, action)

        if type == "column":
            self.translate_column(question, translation, action)

    def translate_question(self, question, translation, action):
        try:
            trans = TranslationQuestion.objects.get(question=question, translation=translation)
        except TranslationQuestion.DoesNotExist:
            raise Exception("Unable to find translation fo question '%s'" % (question.data_name))
        title = action.find('title')
        description = action.find('description')
        trans.title = as_trans(title, trans.title)
        trans.description = as_trans(description, trans.description)
        trans.save()

    def translate_option(self, question, translation, action):

        value = action.attrib.get('value')
        if value is None:
            raise Exception("Value not found")
        try:
            option = models.Option.objects.get(question=question, value=value)
        except models.Option.DoesNotExist:
            raise Exception("Unable to find option with value '%s' for question '%s'" % (value, question.data_name))
        try:
            trans = TranslationOption.objects.get(option=option, translation=translation)
        except TranslationOption.DoesNotExist:
            raise Exception("Unable to find translation fo option '%s' of %s" % (value, question.data_name))
        text = action.find('text')
        description = action.find('description')
        trans.text = as_trans(text, trans.text)
        trans.description = as_trans(description, trans.description)
        trans.save()

    def translate_row(self, question, translation, action):
        value = action.attrib.get('ordinal')
        if value is None:
            raise Exception("Value not found")
        try:
            row = models.QuestionRow.objects.get(question=question, ordinal=value)
        except models.QuestionRow:
            raise Exception("Unable to find row with ordinal '%s' for question '%s'" % (value, question.data_name))
        try:
            trans = TranslationQuestionRow.objects.get(row=row, translation=translation)
        except TranslationQuestionRow.DoesNotExist:
            raise Exception("Unable to find translation for row '%s' of  %s" % (str(value), question.data_name))

        title = action.find('title')
        trans.title = as_trans(title, trans.title)
        trans.save()

    def translate_column(self, question, translation, action):
        value = action.attrib.get('ordinal')
        if value is None:
            raise Exception("Value not found")
        try:
            column = models.QuestionColumn.objects.get(question=question, ordinal=value)
        except models.QuestionColumn:
            raise Exception("Unable to find column with ordinal '%s' for question '%s'" % (value, question.data_name))
        try:
            trans = TranslationQuestionColumn.objects.get(column=column, translation=translation)
        except TranslationQuestionColumn.DoesNotExist:
            raise Exception("Unable to find translation for column '%s' of  %s" % (str(value), question.data_name))

        title = action.find('title')
        trans.title = as_trans(title, trans.title)
        trans.save()

