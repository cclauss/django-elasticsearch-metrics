# Contributing
(TODO: update)

## Setting up for development

* Create and activate a new virtual environment
* `pip install -e '.[dev]'`
* Install django: `pip install django`
* (Optional but recommended) Run elasticsearch: `docker-compose up`

* Run tests and checks:

```
# Run all tests (requires elasticsearch to be running)
python3 -m elasticsearch_metrics.tests
```
```
# Run only linting (not tests)
python3 -m elasticsearch_metrics.tests --lint
```
```
# Run only tests (not linting)
python3 -m elasticsearch_metrics.tests --test
```

* Run the shell with:

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
