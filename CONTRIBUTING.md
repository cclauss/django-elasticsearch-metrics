# Contributing
(TODO: update)

## Code conventions


## Setting up local devloop

### 0. get the code
for example:
```
git clone https://github.com/CenterForOpenScience/django-elasticsearch-metrics.git djelme
cd djelme
```

### 1. put environment together
create and activate a [python virtual environment](https://docs.python.org/3.14/tutorial/venv.html)
with python version 3.10+ -- there are many tools for this; you may already have your own way.

here's an example using `venv` (in python's standard lib) to create the virtual environment in a `.venv` directory, with bash:
```
python -m venv .venv && source .venv/bin/activate
```

install dependencies (listed in `pyproject.toml`), including the `dev` extra (and maybe `anydjango`) -- here's an example using `pip`:
```
pip install -e '.[dev,anydjango]'
```

### Run tests and checks

these expect elasticsearches to be running and configured in `elasticsearch_metrics/tests/settings.py` (or set environment variables `ELASTICSEARCH6_URL` and `ELASTICSEARCH8_URL`) -- see `using docker-style container tools`, below, for one way to do that

running the python module `elasticsearch_metrics.tests` will run tests and linting checks
-- should always pass before merging to `main`

```
python -m elasticsearch_metrics.tests
```
optional args:
- `--devloop`: adds `--failfast --pdb` to test args
- `--coverage`: print code coverage report
- `--test`: run only tests (not linting)
- `--lint`: run only linting checks (not tests)

see `elasticsearch_metrics/tests/__main__.py` for more details

### Run the shell with:

```
konch allow
konch
```

### (Optional) Run tests in tox

To run tests against the full environment matrix (all supported Python
and Django versions), we use `tox`.

NOTE: will skip Python versions not found in this environment
-- to run all python versions, need to install them

Run the tests with tox:

```
tox
```

### (optional) using docker-style container tools
see `testbox.Containerfile` and `docker-compose.yml` -- running `testbox` runs `python -m elasticsearch_metrics.tests`

(note: examples use `pc` aliased to a `docker-compose` equivalent)

start elasticsearches in the background
```
pc up -d elasticsearch6 elasticsearch8
```

run tests and lint
```
pc up testbox
```

example devloop -- use current code, debugger on error, stop on failure
```
pc run --build --rm --no-deps testbox poetry run python -m elasticsearch_metrics.tests --devloop
```
