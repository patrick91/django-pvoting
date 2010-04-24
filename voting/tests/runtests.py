import os, sys

project = os.path.realpath(os.path.join(os.path.dirname(os.path.realpath(__file__)), '../../'))

sys.path.append(project)

os.environ['DJANGO_SETTINGS_MODULE'] = 'voting.tests.settings'

from django.test.simple import DjangoTestSuiteRunner

test = DjangoTestSuiteRunner()

failures = test.run_tests(('voting', ))

if failures:
    sys.exit(failures)
