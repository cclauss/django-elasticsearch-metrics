"""elasticsearch_metrics.tests.__main__: run all the tests

a convenience for running with `python3 -m elasticsearch_metrics.tests`
"""

import argparse
import os
import subprocess

_DEVLOOP_DJANGOTEST_ARGS = ["--failfast", "--pdb"]

_parser = argparse.ArgumentParser()
_parser.add_argument("--lint", action="store_true")  # _args.lint
_parser.add_argument("--test", action="store_true")  # _args.test
_parser.add_argument("-d", "--devloop", action="store_true")  # _args.devloop
_parser.add_argument("passthru_test_args", nargs="*")


def run_tests(passthru_test_args=()):
    import django
    import django.core.management

    _print_header("django-admin", "test", *passthru_test_args)
    os.environ.setdefault(
        "DJANGO_SETTINGS_MODULE", "elasticsearch_metrics.tests.settings"
    )
    django.setup()
    django.core.management.call_command("test", *passthru_test_args)
    # ? _run("poetry", "run", "python", "manage.py", "test", *passthru_test_args)


def _print_header(*args):
    _argstr = " ".join(args)
    print()
    print(_argstr)
    print("#" * len(_argstr))
    print()


def _run(*args):
    _print_header(*args)
    subprocess.run(args, check=True)


def run_lint():
    _run("flake8")
    _run("black", "--check", "--quiet", ".")
    # TODO: mypy?


if __name__ == "__main__":
    _args = _parser.parse_args()
    _run_all = not any((_args.test, _args.lint))

    if _run_all or _args.test:
        run_tests(_DEVLOOP_DJANGOTEST_ARGS if _args.devloop else ())

    if _run_all or _args.lint:
        run_lint()

    print("\n-- all done --")
