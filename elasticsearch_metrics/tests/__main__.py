"""elasticsearch_metrics.tests.__main__: run all the tests

a convenience for running with `python3 -m elasticsearch_metrics.tests`
"""

import argparse
import collections
import os
import subprocess
import sys

_parser = argparse.ArgumentParser()
_parser.add_argument("--lint", action="store_true")  # _args.lint
_parser.add_argument("--test", action="store_true")  # _args.test
_parser.add_argument("--autofix", action="store_true")  # _args.autofix
_parser.add_argument("--no-coverage", action="store_true")  # _args.no_coverage


def run_tests(
    passthru_test_args: collections.abc.Iterable[str] = (),
    coverage: bool = False,
) -> None:
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
    try:
        subprocess.run(args, check=True)  # stop on error
    except subprocess.CalledProcessError as _e:
        print(f"\n\n^^ errored ({_e.returncode}) ^^")
        sys.exit()


def run_lint() -> None:
    _run("poetry", "run", "flake8")
    _run("poetry", "run", "black", "--check", ".")
    # TODO: passing mypy config
    # _run("poetry", "run", "mypy", "elasticsearch_metrics")


def run_autofix() -> None:
    _run("poetry", "run", "flake8", "--fix")
    _run("poetry", "run", "black", ".")


def _print_coverage_report() -> None:
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


if __name__ == "__main__":
    _args, _other_args = _parser.parse_known_args()
    # running without args same as `--test --lint`
    _no_args = not any((_args.lint, _args.test, _args.autofix))
    _yes_test = _no_args or _args.test
    _yes_lint = _no_args or _args.lint
    _yes_coverage = _yes_test and not _args.no_coverage

    if _args.autofix:
        run_autofix()

    if _yes_test:
        run_tests(passthru_test_args=_other_args, coverage=_yes_coverage)

    if _yes_lint:
        run_lint()

    if _yes_coverage:
        _print_coverage_report()

    print("\n\n== all done ==")
