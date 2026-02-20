"""elasticsearch_metrics.tests.__main__: run the tests

a convenience for running with `python3 -m elasticsearch_metrics.tests`
"""

import argparse
from subprocess import run

_DJANGOTEST_ARGS = ["--failfast", "--pdb"]

_parser = argparse.ArgumentParser()
_parser.add_argument("--no-lint", action="store_true")
_parser.add_argument("--no-test", action="store_true")
_parser.add_argument("passthru_test_args", nargs="*")


def run_tests(passthru_test_args=()):
    run(
        ["python3", "manage.py", "test", *passthru_test_args],
        check=True,
        env={"DJANGO_SETTINGS_MODULE": "elasticsearch_metrics.tests.settings"},
    )


def run_lint():
    run("poetry run flake8", check=True)
    run("poetry run black --check", check=True)
    # TODO: mypy?


if __name__ == "__main__":
    _args = _parser.parse_args()

    if not _args.no_test:
        run_tests(_args.passthru_args)

    if not _args.no_lint:
        run_lint()
