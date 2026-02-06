"""elasticsearch_metrics.tests.__main__: run the tests

a convenience for running with `python3 -m elasticsearch_metrics.tests`
"""

if __name__ == '__main__':
    from django.core import management

    management.call_command("test", "--failfast", "--keepdb")

    # TODO: lint with flake8, mypy, ...
