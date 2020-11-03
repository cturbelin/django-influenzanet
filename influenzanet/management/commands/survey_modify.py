'''
Created on Mar 1, 2020

Modify a survey according to a json file describing each modifications


@author: clementturbelin
'''
from optparse import make_option
from django.core.management.base import BaseCommand
from apps.pollster import models
from django.utils import simplejson
from django.db import transaction, connection
from django.db.models import Max
from influenzanet import datasets
import unicodedata
from xml.etree import ElementTree
from apps.pollster.models import TranslationOption, TranslationQuestion,\
    TranslationQuestionRow, TranslationQuestionColumn

TYPES = dict(models.QUESTION_TYPE_CHOICES)
TYPE_SINGLE = 'single-choice'
TYPE_MULTIPLE = 'multiple-choice'
TYPE_MATRIX_SELECT = 'matrix-select'

DATATYPE_NUMERIC = 'Numeric'
DATATYPE_TEXT = 'Text'
DATATYPE_DATE = 'Date'
ACTIONS = ['add_question', 'add_option']

DATA_TYPES = [DATATYPE_NUMERIC, DATATYPE_TEXT, DATATYPE_DATE]

RULES = {
 'show': {'js':'wok.pollster.rules.ShowQuestion'},
 'hide': {'js':'wok.pollster.rules.HideQuestion'},
 'exclusive': {'js':'wok.pollster.rules.Exclusive'},
 'fill': {'js':'wok.pollster.rules.Fill', 'object_options': True},
 'showoption': {'js':'wok.pollster.rules.ShowOptions', 'object_options': True},
 'hideoption': {'js':'wok.pollster.rules.HideOptions', 'object_options': True},
 'checkoption': {'js': 'wok.pollster.rules.CheckOptions', 'object_options': True },
 'uncheckoption': {'js': 'wok.pollster.rules.UncheckOptions', 'object_options': True },
 'futurefill': {'js':'wok.pollster.rules.FutureFill', 'object_options': True},
 'futureshow': {'js':'wok.pollster.rules.FutureShowQuestion'},
 'futurehide': {'js':'wok.pollster.rules.FutureHideQuestion'}
}

class Command(BaseCommand):
    help = 'Update a survey for with a json definition'
    option_list = BaseCommand.option_list + (
        make_option('-f', '--file', action='store', type="string",
                    dest='file',
                    help='json file with actions to make on survey'),
        make_option('-s', '--survey', action='store',  dest='survey', help='Target survey shortname'),
        make_option('-c', '--commit', action='store_true',  dest='commit', help='Validate changes (dont by default'),
        make_option('-l', '--locale', action='store', type="string", dest='locale', help='Validate changes (dont by default', default='en'),
        make_option('-t', '--translation', action='store_true',  dest='translation', help='Create translation file', default=False),
        make_option('-u', '--update-table', action='store_true',  dest='update_table', help='Update table columns (only with commit)', default=False),
    )

    def get_question(self, name):
        try:
            r = models.Question.objects.get(survey=self.survey, data_name=name)
        except models.Question.DoesNotExist:
            raise Exception("Question named '%s' doesnt found" % (name, ))
        return(r)

    def get_datatype(self, name):
        r = models.QuestionDataType.objects.get(title=name)
        return(r)

    def get_ruledef(self, name):
        name = str(name)
        name = name.lower()
        if not name in RULES:
            raise Exception("Uknown rule type '%s'" % (name, ))
        rule_def = RULES.get(name)
        return rule_def

    def get_ruletype(self, name):
        rule_def = self.get_ruledef(name)
        r = models.RuleType.objects.get(js_class=rule_def['js'])
        return r

    def handle(self, *args, **options):

        self.verbosity = int(options.get('verbosity'))

        commit = options.get('commit')
        json_file = options.get('file')
        self.locale = options.get('locale')
        shortname = options.get('survey')
        translation_file = options.get('translation')
        update_table = options.get('update_table')
        if json_file is None:
            raise Exception("File not provided")

        update_def = simplejson.load(open(json_file, 'r'))

        if shortname is None:
            if 'survey' in update_def:
                shortname = update_def['survey']
            else:
                raise Exception("No survey name defined in update file")

        try:
            self.survey = models.Survey.objects.get(shortname=shortname)
        except models.Survey.DoesNotExist:
            print "Unable to find survey '%s'" % shortname
            return
        print "Found Survey %s %d "  % (shortname, self.survey.id)

        # New translations
        self.new_translations = []

        self.translations = list(models.TranslationSurvey.objects.filter(survey=self.survey))

        # Get the db fields list before modification
        self.fields_before = self.get_survey_fields()

        if not 'actions' in update_def:
            raise Exception('"Action" entry not defined in json file')

        actions = update_def['actions']

        # List of added names or duplicates
        self.questions_names = []
        for field in self.fields_before:
            self.questions_names.append(field[0])

        commited = False
        with transaction.commit_manually():
            try:
                idx = 0
                for action in actions:
                    print "Action %d <%s>" % (idx, action['action'] )

                    if(action['action'] == 'add_question'):
                        self.action_add_question(action)

                    if(action['action'] == 'add_option'):
                        self.action_add_option(action)

                    if(action['action'] == 'hide_question'):
                        self.action_hide_question(action)

                    if(action['action'] == 'modify_question'):
                        self.action_modify_question(action)

                    if(action['action'] == 'modify_option'):
                        self.action_modify_option(action)

                    idx = idx + 1
            except Exception as e:
                transaction.rollback()
                raise

            self.fields_after = self.get_survey_fields()

            if commit:
                transaction.commit()
                commited = True
            else:
                transaction.rollback()

        if commited:
            print("Changed has been made on survey " + self.survey.shortname)

        self.build_fields(update_table and commited)
        if translation_file:
            self.build_translations()

    def get_survey_fields(self):
        """
         Get the columns list defined for this survey
        """
        fields = []
        for question in self.survey.questions:
            fields += question.as_fields()
        return fields


    def build_fields(self, update):
        """
            Create SQL modification for data tables from fields
        """
        after = dict(self.fields_after)
        before = dict(self.fields_before)
        to_add = []

        for name in after.keys():
            if not name in before:
                to_add.append( (name, after[name]) )

        qn = connection.ops.quote_name

        sql_data_types = connection.creation.data_types

        sql = []
        for f in to_add:
            (name, field) = f

            sql_type = sql_data_types[field.get_internal_type()]

            # Do not apply not null constraint because there are already data in the table
            # Existing rows will have NULL value for the newly created columns
            #if not field.null:
            #    sql_type += ' NOT NULL'
            column = field.db_column or name

            sql_type = sql_type % {'column': column }

            sql_name = qn(column)

            if self.verbosity > 1:
                print("Adding %s : %s %s" % (name, sql_name, sql_type))

            s = "ADD COLUMN %s %s" % (sql_name, sql_type)

            sql.append(s)

        table = self.survey.shortname

        table = qn('pollster_results_' + table)

        alter_table = "ALTER TABLE  "+ table

        query =  alter_table +"\n" + ",\n".join(sql) + ";\n"

        fn = self.survey.shortname +'.sql'
        f = open(fn, 'w')
        f.write(query)
        f.close()
        print("Modifications to apply to "+ table+" are in "+ fn)

        if(update):
            print("Updating data table")
            try:
                cursor = connection.cursor()
                cursor.execute(query)
                print("Table '%s' updated with success" % (table, ))
            except:
                print("Error during table update")
                raise


    def build_translations(self):
        root = ElementTree.Element('translations')
        root.set('survey', self.survey.shortname)
        root.set('language', 'en')
        for r in self.new_translations:
            x = ElementTree.SubElement(root, 'translate')
            x.set('type', r['type'])
            x.set('question', str(r['question']))
            if r['type'] == 'row' or r['type'] == 'column':
                x.set('ordinal', str(r['ordinal']))
            if r['type'] == 'option':
                x.set('value', str(r['value']))
            for v in ['title','description','text']:
                if v in r:
                    e = ElementTree.Element(v + '_org')
                    e.text = r[v]
                    x.append(e)

                    e = ElementTree.Element(v)
                    e.text = r[v]
                    x.append(e)

        fn = self.survey.shortname + '.i18n.xml'
        f = open(fn, 'w')
        f.write(ElementTree.tostring(root, encoding='utf-8'))
        f.close()

    def action_hide_question(self, action):
        p = action['params']
        if p is None:
            raise Exception("Params expected")
        name = p['question']
        question = self.get_question(name)

        if self.verbosity > 1:
            print("Add option in " + self.str_question(question))

        question.starts_hidden = True

        question.save()

        rules = models.Rule.objects.filter(object_question=question)
        for rule in rules:
            print("delete " + self.str_rule(rule))
            rule.delete()

        prune = p.get('prune_options', False)
        keep_options = p.get('keep_options', [])
        if not isinstance(keep_options, list):
            raise Exception("keep_options must be a list")

        if prune:
            options = list(question.options)
            for o in options:
                if o.value in keep_options:
                    continue
                o.delete()

    def action_prune_options(self, action):
        p = action['params']
        if p is None:
            raise Exception("Params expected")
        name = p['question']
        question = self.get_question(name)

        if self.verbosity > 1:
            print("Add option in " + self.str_question(question))

        options = list(question.options)

    def action_add_option(self, action):
        p = action['params']
        if p is None:
            raise Exception("Params expected")
        name = p['question']
        question = self.get_question(name)

        if self.verbosity > 1:
            print("Add option in " + self.str_question(question))


        xoptions = p['options']

        added_options = []
        for xo in xoptions:
            value= xo['value']
            try:
                o_old = models.Option.objects.get(question=question, value=value)
                raise Exception("Option with value '%s' already exists in question '%s'" % (value, name))
            except models.Option.DoesNotExist:
                pass

            o = models.Option()
            o.question = question
            o.text = xo['title']
            o.value = value
            o.is_open = False
            o.starts_hidden = False
            if 'after' in xo:
                after = xo['after']
                ordinal = self.redorder_options(question.id, after)
            else:
                max_ordinal = models.Option.objects.filter(question=question).aggregate(ordinal=Max('ordinal'))
                ordinal = max_ordinal['ordinal'] + 1
            o.ordinal = ordinal
            o.save()
            added_options.append(o)
            print(self.str_option(o))

            self.translate_option(o, xo['title'])
        if 'rules' in p:
            xrules = p['rules']
            for xr in xrules:
                target = self.get_question(xr['object'])
                subject = question
                rule_type = self.get_ruletype(xr["type"])

                try:
                    r = models.Rule.objects.get(subject_question=subject, object_question=target, rule_type=rule_type)
                except models.Rule.DoesNotExist, e:
                    print(e)
                    raise Exception("Unable to find rule %s %s(%d) -> %s(%d)" % (rule_type.id, subject.data_name, subject.id, target.data_name, target.id))

                #print("Found "+ self.str_rule(r))

                options_in = None

                if 'in' in xr:
                    options_in = xr['in']

                any_added = True
                for o in added_options:
                    if options_in is None:
                        to_add = True
                    else:
                        to_add = o.value in options_in
                    if to_add:
                        any_added = True
                        #print(" -> Adding " + self.str_option(o))
                        r.subject_options.add(o)

                if any_added:
                    r.save()
                    print(" Rule after "+ self.str_rule(r))


    def action_add_question(self, action):
        p = action['params']
        if p is None:
            raise Exception("Params expected")
        q = models.Question()
        name = p['name']

        if name is None:
            raise Exception("Name expected")

        if name in self.questions_names:
            raise Exception("Name '%s' already in use" % (name))

        max_ordinal = models.Question.objects.filter(survey=self.survey).aggregate(ordinal=Max('ordinal'))
        max_ordinal = max_ordinal['ordinal'] + 1

        q.data_name = name
        self.questions_names.append(name)

        if 'after' in p:
            ordinal = self.redorder_questions(p['after'])
            if self.verbosity > 1:
                print "Using after '%s' : %d" % (p['after'], ordinal)
        else:
            ordinal = max_ordinal

        q.ordinal = ordinal
        q.title = p['title']

        if 'description' in p:
            q.description = p['description']

        if 'is_mandatory' in p:
            q.is_mandatory = bool(p['is_mandatory'])

        q.survey = self.survey
        if 'hidden' in p:
            if not isinstance(p['hidden'], bool):
                raise Exception("Hidden must be boolean")
            q.starts_hidden = p["hidden"]
        else:
            q.starts_hidden = False
        q.regex = ''

        question_type = p['type']

        if not question_type in TYPES:
            raise Exception("Unknown type '%s'" % question_type)
        q.type = question_type
        data_type = p['data_type']
        dt = self.get_datatype(data_type)
        q.data_type = dt

        if 'open_type' in p:
            q.open_option_data_type = self.get_datatype(p['open_type'])

        q.save()

        print(" Adding " + self.str_question(q))
        self.translate_question(q, q.title, q.description)

        if 'options' in p:
            self.add_question_options(q, p['options'])

        if 'options_from' in p:
            self.add_question_options_from(q, p['options_from'])

        if 'rows' in p:
            rows = p['rows']
            if not isinstance(rows, list) or not len(rows) > 0:
                raise Exception("Rows must be a list")
            self.add_question_rows(q, rows)

        # Add columns
        if 'columns' in p:
            columns = p['columns']
            if not isinstance(columns, list) or not len(columns) > 0:
                raise Exception("columns must be a list")
            self.add_question_columns(q, columns)


        if 'rules' in p:
            rules = p['rules']
            if not isinstance(rules, list) or not len(rules) > 0:
                raise Exception("Rules must be a list")
            rid = 0
            for xr in rules:
                rule = models.Rule()
                subject_options = None
                object_options = None

                x_rule_type = xr['type']

                try:
                    rtype = self.get_ruletype(x_rule_type)
                    if x_rule_type == "exclusive":
                        subject_question = q
                        exclusive_options = xr['options']
                        subject_options = self.get_target_options(q, {'in': exclusive_options })
                        object_options = self.get_target_options(q, {'not': exclusive_options })
                    else:
                        subject_question = self.get_question(xr["from"])
                        if 'options' in xr:
                            subject_options = self.get_target_options(subject_question, xr['options'])
                        if 'to_options' in xr:
                            object_options = self.get_target_options(q, xr['to_options'])
                except Exception as e:
                    e.message += "Error in rule %d : %s" % (rid, e.message)
                    raise

                self.check_rule(x_rule_type, subject_question, subject_options, q, object_options)

                rule.rule_type = rtype
                if 'sufficient' in xr:
                    rule.is_sufficient = xr['sufficient']
                else:
                    rule.is_sufficient = True

                rule.subject_question = subject_question
                rule.object_question = q
                rule.save()
                # Now update dependencies
                if subject_options is not None:
                    rule.subject_options = subject_options

                if object_options is not None:
                    rule.object_options = object_options
                rule.save()
                if self.verbosity > 0:
                    print("   + " + self.str_rule(rule))
                rid = rid + 1

    def check_rule(self, rule_type, subject_question, subject_options, object_question, object_options):
        rule_def = self.get_ruledef(rule_type)
        if rule_def.get('object_options', False) and object_options is None:
            raise Exception("Rule '%s' requires object_options" % rule_type)

    def action_modify_option(self, action):
        p = action['params']
        if p is None:
            raise Exception("Params expected")
        name = p['name']

        if name is None:
            raise Exception("Name expected")

        q = self.get_question(name)

        if not 'value' in p:
            raise Exception("value parameter is expected to identify option")

        value = p['value']

        o = models.Option.objects.get(question=q, value=value)

        if 'title' in p:
            o.text = p['title']

        if 'description' in p:
            o.description = p['description']

        if 'hidden' in p:
            if not isinstance(p['hidden'], bool):
                raise Exception("Hidden must be boolean")
            o.starts_hidden = p["hidden"]

        if 'after' in p:
            after = p['after']
            ordinal = self.redorder_options(q.id, after)
        else:
            max_ordinal = models.Option.objects.filter(question=q).aggregate(ordinal=Max('ordinal'))
            ordinal = max_ordinal['ordinal'] + 1
        o.ordinal = ordinal
        o.save()

    def action_modify_question(self, action):
        p = action['params']
        if p is None:
            raise Exception("Params expected")
        name = p['name']

        if name is None:
            raise Exception("Name expected")

        q = self.get_question(name)

        if 'after' in p:
            ordinal = self.redorder_questions(p['after'])
            if self.verbosity > 1:
                print "Using after '%s' : %d" % (p['after'], ordinal)

            q.ordinal = ordinal

        if 'title' in p:
            q.title = p['title']

        if 'description' in p:
            q.description = p['description']

        if 'is_mandatory' in p:
            q.is_mandatory = bool(p['is_mandatory'])

        if 'hidden' in p:
            if not isinstance(p['hidden'], bool):
                raise Exception("Hidden must be boolean")
            q.starts_hidden = p["hidden"]

        print(" Modifying " + self.str_question(q))
        q.save()

        if 'rules' in p:
            rules = p['rules']
            if not isinstance(rules, list) or not len(rules) > 0:
                raise Exception("Rules must be a list")
            rid = 0
            for xr in rules:
                rule = models.Rule()
                subject_options = None
                object_options = None

                x_rule_type = xr['type']

                try:
                    rtype = self.get_ruletype(x_rule_type)
                    if x_rule_type == "exclusive":
                        subject_question = q
                        exclusive_options = xr['options']
                        subject_options = self.get_target_options(q, {'in': exclusive_options })
                        object_options = self.get_target_options(q, {'not': exclusive_options })
                    else:
                        subject_question = self.get_question(xr["from"])
                        if 'options' in xr:
                            subject_options = self.get_target_options(subject_question, xr['options'])
                        if 'to_options' in xr:
                            object_options = self.get_target_options(q, xr['to_options'])

                except Exception as e:
                    e.message += "Error in rule %d : %s" % (rid, e.message)
                    raise

                self.check_rule(x_rule_type, subject_question, subject_options, q, object_options)

                rule.rule_type = rtype
                if 'sufficient' in xr:
                    rule.is_sufficient = xr['sufficient']
                else:
                    rule.is_sufficient = True

                rule.subject_question = subject_question
                rule.object_question = q
                rule.save()
                # Now update dependencies
                if subject_options is not None:
                    rule.subject_options = subject_options

                if object_options is not None:
                    rule.object_options = object_options
                rule.save()
                if self.verbosity > 0:
                    print("   + " + self.str_rule(rule))
                rid = rid + 1

    def action_add_rules(self, action):
        p = action['params']
        if p is None:
            raise Exception("Params expected")
        name = p['name']

        if name is None:
            raise Exception("Name expected")

        q = self.get_question(name)

        if 'rules' in p:
            rules = p['rules']
            if not isinstance(rules, list) or not len(rules) > 0:
                raise Exception("Rules must be a list")
            rid = 0
            for xr in rules:
                rule = models.Rule()
                subject_options = None
                object_options = None

                x_rule_type = xr['type']

                try:
                    rtype = self.get_ruletype(x_rule_type)
                    if x_rule_type == "exclusive":
                        subject_question = q
                        exclusive_options = xr['options']
                        subject_options = self.get_target_options(q, {'in': exclusive_options })
                        object_options = self.get_target_options(q, {'not': exclusive_options })
                    else:
                        subject_question = self.get_question(xr["from"])
                        if 'options' in xr:
                            subject_options = self.get_target_options(subject_question, xr['options'])
                except Exception as e:
                    e.message += "Error in rule %d : %s" % (rid, e.message)
                    raise
                rule.rule_type = rtype
                if 'sufficient' in xr:
                    rule.is_sufficient = xr['sufficient']
                else:
                    rule.is_sufficient = True

                rule.subject_question = subject_question
                rule.object_question = q
                rule.save()
                # Now update dependencies
                if subject_options is not None:
                    rule.subject_options = subject_options

                if object_options is not None:
                    rule.object_options = object_options
                rule.save()

                if self.verbosity > 0:
                    print("   + " + self.str_rule(rule))
                rid = rid + 1

    def add_question_options_from(self, question, options_from):

        blank_value = options_from.get('blank_value', None)

        options = []

        def sorter(text):
            try:
                text = unicode(text, 'utf-8')
            except (TypeError, NameError): # unicode is a default on python 3
                pass
            text = unicodedata.normalize('NFD', text)
            text = text.encode('ascii', 'ignore')
            text = text.lower()
            return text

        localized = False
        if 'dataset' in options_from:
            dataset_name = options_from['dataset']
            if dataset_name == 'countries':
                data = datasets.get_data_file('countries/' + self.locale)
                localized = True
                for k,v in data['countries'].items():
                    options.append({'value': k, 'title': v})
        if 'order' in options_from and options_from['order']:
            options.sort(cmp=None, key=lambda r : sorter(r['title']), reverse=False)

        if not blank_value is None:
            blank_title = options_from.get('blank_title', '--')
            options.insert(0, {'value': blank_value, 'title': blank_title })

        self.add_question_options(question, options, localized=localized)

    def add_question_options(self, question, xoptions, localized=False):
        option_ordinal = 0
        for xoption in xoptions:
            option_ordinal += 1
            option = models.Option()
            option.ordinal = option_ordinal
            option.question = question
            option.is_virtual = False # Virtual options are not handled yet
            virtual_type = ''
            option.virtual_inf =  ''
            option.virtual_sup = ''
            option.virtual_regex = ''
            option.text = xoption['title']
            option.value = xoption['value']
            option.is_open = False
            option.starts_hidden = False

            if 'open' in xoption:
                option.is_open = True
                if question.open_option_data_type is None:
                    raise Exception("Please set open option data type for this question")

            option.save()
            print "  + " + self.str_option(option)
            self.translate_option(option, option.text, localized=localized)

    def add_question_rows(self, question, rows):
        rid = 1 # row def index, for errors
        ordinals = [] # ordinals (must be unique)
        for xr in rows:

            # Ordinal are used to build the data name for response of a matrix question
            # So it's mandatory
            if not 'ordinal' in xr:
                raise Exception("'ordinal' is required for row definition in row %d" % (rid, ))

            o = int(xr['ordinal'])
            if not o > 0:
                raise Exception("Ordinal must be positive integer")

            if o in ordinals:
                raise Exception("Ordinal for row must be unique, %d already defined in row %d" % (o, rid))

            if not 'title' in xr:
                raise Exception("'title' is required row %d" % (rid, ))

            ordinals.append(o)

            row = models.QuestionRow()
            row.question = question
            row.ordinal = o
            row.title = xr['title']
            row.save()

            self.translate_question_row(row, row.title)

            rid = rid + 1


    def add_question_columns(self, question, columns):
        rid = 1 # row def index, for errors
        ordinals = []
        for xr in columns:

            # Ordinal are used to build the data name for response of a matrix question
            # So it's mandatory
            if not 'ordinal' in xr:
                raise Exception("'ordinal' is required for column definition in column %d" % (rid, ))

            o = int(xr['ordinal'])
            if not o > 0:
                raise Exception("Ordinal must be positive integer in column %d " % (rid, ))

            if o in ordinals:
                raise Exception("Ordinal for columns must be unique, %d already defined in column %d" % (o, rid))

            if not 'title' in xr:
                raise Exception("'title' is required columns %d" % (rid, ))

            ordinals.append(o)

            column = models.QuestionColumn()
            column.question = question
            column.ordinal = o
            column.title = xr['title']
            column.save()

            self.translate_question_column(column, column.title)

            rid = rid + 1


    def get_target_options(self, question, oo):
        subject_options = None
        all_options = question.options
        if isinstance(oo, unicode) or isinstance(oo, str):
            oo = str(oo) # should not contains non ascci chars
            if oo == "all":
                subject_options = all_options
        if isinstance(oo, dict):
            values = None
            if 'not' in oo:
                values = oo['not']
                op = 'not'
            if 'in' in oo:
                values = oo['in']
                op = 'in'
            if not isinstance(values, list) or len(values) == 0:
                raise Exception("options values must be a list")
            subject_options = []
            for o in all_options:
                in_option = o.value in values
                if op == 'in' and in_option:
                    subject_options.append(o)
                if op == 'not' and not in_option:
                    subject_options.append(o)
        if subject_options is None:
            raise Exception("Unable to find option definitions")
        return subject_options

    def translate_option(self, option, text, localized=False):
        for st in self.translations:
            t = TranslationOption()
            t.translation = st
            t.option = option
            t.text = text
            t.save()
            if self.verbosity > 1:
                print(self.str_trans_option(t))
        if not localized:
            self.new_translations.append({'type': 'option', 'value': option.value, 'text': option.text, 'description': option.description, 'question': option.question.data_name })

    def translate_question(self, question, title, description=None):
        for st in self.translations:
            t = TranslationQuestion()
            t.translation = st
            t.question = question
            t.title = title
            t.description = description
            t.save()
            if self.verbosity > 1:
                print(self.str_trans_question(t))
        self.new_translations.append({'type': 'question', 'question': question.data_name, 'title': question.title, 'description': question.description})

    def translate_question_row(self, row, title):
        for st in self.translations:
            t = TranslationQuestionRow()
            t.translation = st
            t.row = row
            t.title = title
            t.save()
            if self.verbosity > 1:
                print(self.str_trans_question_row(t))
        self.new_translations.append({'type': 'row', 'question': row.question.data_name, 'ordinal': row.ordinal, 'title': row.title})


    def translate_question_column(self, column, title):
        for st in self.translations:
            t = TranslationQuestionColumn()
            t.translation = st
            t.column = column
            t.title = title
            t.save()
            if self.verbosity > 1:
                print(self.str_trans_question_column(t))
        self.new_translations.append({'type': 'column', 'question': column.question.data_name, 'ordinal': column.ordinal, 'title': column.title})

    def redorder_options(self, question_id, after):
        """
        Reorder options to insert a new option.
        Return the ordinal value to assign to the new option
        if after < 0 then place the ordinal as first
        """
        # Get fresh question with all options
        question = models.Question.objects.get(id=question_id)
        options = list(question.options) # fresh iterator
        ordinal = None
        if after < 0:
            ordinal = 1
        else:
            for o in options:
                if o.value == after:
                    ordinal = o.ordinal
            if ordinal is None:
                raise Exception("Unknown after value '%s'" % (after) )
            ordinal = ordinal + 1 # Target ordinal
        for o in options:
            # Migrate ordinal greater or equal to the target ordinal
            if o.ordinal >= ordinal:
                o.ordinal = o.ordinal + 1
                o.save()
        return ordinal

    def redorder_questions(self, after):
        """
            Reorder questions to insert a new question. Return the ordinal value to assign to the new question
        """
        ordinal = None
        for o in self.survey.questions:
            if o.data_name == after:
                ordinal = o.ordinal
        if ordinal is None:
            raise Exception("Unknown after question '%s'" % (after) )
        for o in self.survey.questions:
            if o.ordinal > ordinal:
                # Shift all values by 2, to keep a order value at ordinal + 1 (for the inserted question)
                o.ordinal = o.ordinal + 2
                o.save()
        return ordinal + 1


    def str_question(self, q):
        if q is None:
            return "Question<None>"
        s = "Q<%s, %s>" % (q.id, q.data_name)
        return s

    def str_option(self, option):
        return '<Option id=%s, ord=%d, value=%s,"%s">' % (option.id, option.ordinal, option.value, option.text)

    def str_trans_option(self, to):
        return '<TransOption %s,%s,"%s">' % (to.translation.id, to.option.id, to.text)

    def str_trans_question(self, to):
        return '<TransQuestion %s,%s,"%s">' % (to.translation.id, to.question.id, to.title)

    def str_trans_question_row(self, to):
        return '<TransRow %s,%s,"%s">' % (to.translation.id, to.row.id, to.title)

    def str_trans_question_column(self, to):
        return '<TransColumn %s,%s,"%s">' % (to.translation.id, to.column.id, to.title)

    def str_options(self, options):
        if options is None:
            return '<None>'
        oo = []
        for o in options:
            oo.append(o.value)
        return '[' + ','.join(oo) + ']'

    def str_rule(self, rule):
        s = 'Rule<from ' + self.str_question(rule.subject_question)
        if rule.subject_options is not None:
            oo = rule.subject_options.all()
            s += self.str_options(oo)
        s += ' target ' + self.str_question(rule.object_question)
        if rule.object_options is not None:
            oo = rule.object_options.all()
            s += self.str_options(oo)
        s+= ",S"
        if rule.is_sufficient:
            s += "+"
        else:
            s += "-"
        s += ">"
        return s