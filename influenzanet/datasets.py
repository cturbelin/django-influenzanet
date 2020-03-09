
from os.path import dirname
from django.utils import simplejson

def get_data_path():
    return dirname(__file__) + '/data'

def get_data_file(name):
    path = get_data_path()
    
    file = path + '/' + name + '.json'
    
    return simplejson.load(open(file, 'r'))