# Contributing
(TODO: update)

## Setting up for development

* Create and activate a new virtual environment
* `pip install -e '.[dev]'`
* Install django: `pip install django`
* (Optional but recommended) Run elasticsearch: `docker-compose up`

* Run tests using the following commands:

```
# Run all tests (requires elasticsearch to be running)
python3 -m elasticsearch_metrics.tests

# Check syntax
flake8
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
