"""elasticsearch_metrics.tests.__main__: run all the tests

a convenience for running with `python3 -m elasticsearch_metrics.tests`
"""

import argparse
import os
import subprocess

_DEVLOOP_DJANGOTEST_ARGS = ("--failfast", "--pdb")

_parser = argparse.ArgumentParser()
_parser.add_argument("--lint", action="store_true")  # _args.lint
_parser.add_argument("--test", action="store_true")  # _args.test
_parser.add_argument("-d", "--devloop", action="store_true")  # _args.devloop
_parser.add_argument("-c", "--coverage", action="store_true")  # _args.coverage
_parser.add_argument("passthru_test_args", nargs="*")


def run_tests(passthru_test_args: tuple[str, ...] = (), coverage: bool = False) -> None:
    print_header("tests")
    os.environ.setdefault(
        "DJANGO_SETTINGS_MODULE", "elasticsearch_metrics.tests.settings"
    )
    _argstart = (
        ("poetry", "run", "coverage", "run")
        if coverage
        else ("poetry", "run", "python")
    )
    _run(*_argstart, "manage.py", "test", *passthru_test_args)


def print_header(*args: str) -> None:
    _argstr = " ".join(args)
    print()
    print(_argstr)
    print("=" * len(_argstr))
    print()


def _run(*args: str, header: str = "") -> None:
    print_header(header) if header else print_header(*args)
    subprocess.run(args, check=True)  # stop on error


def run_lint() -> None:
    _run("poetry", "run", "flake8")
    _run("poetry", "run", "black", "--check", ".")
    # TODO: mypy?


if __name__ == "__main__":
    _args = _parser.parse_args()
    _run_all = not any((_args.test, _args.lint))

    if _run_all or _args.test:
        run_tests(
            passthru_test_args=(_DEVLOOP_DJANGOTEST_ARGS if _args.devloop else ()),
            coverage=_args.coverage,
        )

    if _run_all or _args.lint:
        run_lint()

    if _args.coverage:
        _run(
            "poetry",
            "run",
            "coverage",
            "report",
            "--skip-covered",
            "--sort=-miss",
            "--omit=elasticsearch_metrics/tests/__main__.py",
            header="uncovered code",
        )

    print("\n\n== all done ==")
