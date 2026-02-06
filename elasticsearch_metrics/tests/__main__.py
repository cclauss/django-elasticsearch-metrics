"""elasticsearch_metrics.tests.__main__: run the tests

a convenience for running with `python3 -m elasticsearch_metrics.tests`
"""

if __name__ == '__main__':
    import os
    import django
    import django.core.management

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "elasticsearch_metrics.tests.settings")
    django.setup()
    django.core.management.call_command("test", "--failfast", "--keepdb")

    # TODO: lint with flake8, mypy, ...
