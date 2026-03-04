"""elasticsearch_metrics.tests.__main__: run all the tests

a convenience for running with `python3 -m elasticsearch_metrics.tests`
"""

import argparse
import coverage
import os
import subprocess

_DEVLOOP_DJANGOTEST_ARGS = ["--failfast", "--pdb"]

_parser = argparse.ArgumentParser()
_parser.add_argument("--lint", action="store_true")  # _args.lint
_parser.add_argument("--test", action="store_true")  # _args.test
_parser.add_argument("-d", "--devloop", action="store_true")  # _args.devloop
_parser.add_argument("-c", "--coverage", action="store_true")  # _args.coverage
_parser.add_argument("passthru_test_args", nargs="*")


def run_tests(passthru_test_args=()):
    import django
    import django.core.management

    print_header("tests")
    os.environ.setdefault(
        "DJANGO_SETTINGS_MODULE", "elasticsearch_metrics.tests.settings"
    )
    django.setup()
    django.core.management.call_command("test", *passthru_test_args)
    # ? _run("poetry", "run", "python", "manage.py", "test", *passthru_test_args)


def print_header(*args):
    _argstr = " ".join(args)
    print()
    print(_argstr)
    print("=" * len(_argstr))
    print()


def _run(*args):
    subprocess.run(args, check=True)  # stop on error


def run_lint():
    print_header("flake8")
    _run("poetry", "run", "flake8")
    print_header("black")
    _run("poetry", "run", "black", "--check", ".")
    # TODO: mypy?


if __name__ == "__main__":
    _args = _parser.parse_args()
    _run_all = not any((_args.test, _args.lint))

    if _run_all or _args.test:
        if _args.coverage:
            _cov = coverage.Coverage()
            _cov.start()
        run_tests(_DEVLOOP_DJANGOTEST_ARGS if _args.devloop else ())
        if _args.coverage:
            _cov.stop()
            _cov.save()
            print_header("uncoverage")
            _cov.report(
                skip_covered=True,
                sort="cover",
                omit=["elasticsearch_metrics/tests/__main__.py"],
            )

    if _run_all or _args.lint:
        run_lint()

    print("\n-- all done --")
