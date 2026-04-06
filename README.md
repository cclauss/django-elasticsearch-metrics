# django-elasticsearch-metrics ("djelme" for short)

Django app for storing time-series metrics in Elasticsearch.

`django-elasticsearch-metrics` on pypi: https://pypi.org/project/django-elasticsearch-metrics

python importables:
- `elasticsearch_metrics`
- `elasticsearch_metrics.imps.elastic8` (an implementation with elasticsearch 8)
- `elasticsearch_metrics.imps.elastic6` (an implementation with elasticsearch 6; deprecated)
- ...

## Pre-requisites

* Python >=3.10
* Django 4.2, 5.1, or 5.2
* Elasticsearch 8 (or 6, for deprecated back-compat)

## Install

```
pip install django-elasticsearch-metrics
```

## Quickstart

Add `"elasticseach_metrics"` to `INSTALLED_APPS`.

```python
# ... in your django project settings.py ...
INSTALLED_APPS += ["elasticsearch_metrics"]
```

Configure at least one djelme backend:
```python
# ... in your django project settings.py ...
DJELME_BACKENDS = {
    "my-es8-backend": {  # a name from and for you 
        "elasticsearch_metrics.imps.elastic8": {  # importable djelme implementation
            # dictionary of kwargs for the imp's `djelme_backend` constructor
            # (in this case passed thru as kwargs to `elasticsearch8.Elasticsearch`)
            "hosts": "https://my-elastic8.example:9200",
        },
    },
}
```

In one of your apps, add record types in `metrics.py`


```python
# myapp/metrics.py

from elasticsearch_metrics.imps.elastic8 import EventRecord


class UsageRecord(EventRecord):
    item_id: int

    class Index:
        using = "my-es8-backend"  # backend name -- required if multiple backends use the same imp
```

Either enable autosetup...
```python
# ... in your django project settings file ...
DJELME_AUTOSETUP = True
```

...or be sure to run the `djelme_backend_setup` management command before trying to store anything.
```shell
# This will create an index template for usagerecord timeseries indexes
python manage.py djelme_backend_setup
```

Now add some data:

```python
from myapp.metrics import UsageRecord

# By default we create an index for each day.
# Therefore, this will persist the document
# to an index named for the record type and date
UsageRecord.record(item_id='my.item.id')
```

Go forth and search!

```python
# get an instance of `elasticsearch8.dsl.Search` that queries all timeseries indexes of this type:
UsageRecord.search()

# or get a `Search` for a given time range (from_when <= timestamp < until_when)
UsageRecord.search_timeseries_range((1999,), (2001,))  # in or after 1999; before 2001
UsageRecord.search_timeseries_range((2050, 12), (2051,))  # in 2050-12
UsageRecord.search_timeseries_range(datetime.date(2030, 1, 1), datetime.date(2030, 2, 1))  # in 2030-01
```

## Timeseries indexes

By default, behind the scenes, a new elasticsearch index is created for each record type for each day
in which a record is saved (using UTC timezone). You can change this for a record type by setting
`Meta.timedepth`, or change the default timedepth with the setting `DJELME_DEFAULT_TIMEDEPTH` (see below).

```python
class MyEventWithMonthlyIndexes(EventRecord):
    class Meta:
        timedepth = 2  # year and month
```

- index per year: `timedepth = 1`
- index per month: `timedepth = 2`
- index per day: `timedepth = 3` (default)
- index per hour: `timedepth = 4`


## Index settings

You can configure the index settings that will be set on the index template
and used for each new timeseries index with `Index.settings` on a record type.

```python
class UsageRecord(EventRecord):
    item_id: int

    class Index:
        settings = {"number_of_shards": 2, "refresh_interval": "5s"}
```

## Index templates

Each record type will have its own [index template](https://www.elastic.co/guide/en/elasticsearch/reference/current/indices-templates.html).
The index template name and glob pattern are computed from the app label
for the containing app and the class's name. For example, a `UsageRecord`
class defined in `myapp/metrics.py` will have an index template with the
name `myapp_usagerecord` and a template glob pattern of `myapp_usagerecord_*`.

If you declare a record type outside of an app, you will need to set `app_label`.


```python
class UsageRecord(EventRecord):
    class Meta:
        app_label = "myapp"
```

Alternatively, you can set `template_name` and/or `template` explicitly.

```python
class UsageRecord(EventRecord):
    item_id: int

    class Meta:
        template_name = "myapp_pviews"
        template = "myapp_pviews_*"
```

## Abstract record types

```python
from elasticsearch_metrics.imps.elastic8 import EventRecord


class MyBaseMetric(EventRecord):
    item_id: int

    class Meta:
        abstract = True


class UsageRecord(MyBaseMetric):
    class Meta:
        app_label = "myapp"
```

## Configuration

* `DJELME_BACKENDS`: Named backends for storing or searching records from your django app
  -- nested mapping from backend name (any string, your choice) to python-importable paths
  for modules that (like `"elasticsearch_metrics.imps.elastic8"`)
  to "imp kwargs" config dictionaries given to the imp module's `djelme_backend` constructor
  ```python
  # ... in your django project settings.py ...
  DJELME_BACKENDS = {
      "my-es8-backend": {  # a name from and for you 
          "elasticsearch_metrics.imps.elastic8": {  # importable djelme implementation
              # dictionary of kwargs for the imp's `djelme_backend` constructor
              # (in this case passed thru as kwargs to `elasticsearch8.Elasticsearch`)
              "hosts": "https://my-elastic8.example:9200",
          },
      },
  }
  ```

* `DJELME_AUTOSETUP`: Optional feature, default `False` --
    set `True` to run backend setup automatically when your django app starts
    (like creating index templates in elasticsearch, if they don't already exist)

* `DJELME_DEFAULT_TIMEDEPTH`: Set the granularity of timeseries indexes by the number of "time parts" in index names
    ```
    DJELME_DEFAULT_TIMEDEPTH = 1  # yearly indexes; YYYY
    DJELME_DEFAULT_TIMEDEPTH = 2  # monthly indexes; YYYY.MM
    DJELME_DEFAULT_TIMEDEPTH = 3  # daily indexes; YYYY.MM.DD (this is the default)
    DJELME_DEFAULT_TIMEDEPTH = 4  # hourly indexes; YYYY.MM.DD.HH
    ```
    you can also set `Meta.timedepth` on a specific record type; this will take precedence

## Management commands

* `djelme_backend_types`: Pretty-print a listing of all registered record types.
* `djelme_backend_setup`: Ensure that index templates have been created for your record types.
* `djelme_backend_check`: Check if index templates are in sync. Exits
    with an error code if any templates are out of sync.

<!-- * `clean_metrics` : Clean old data using [curator](https://curator.readthedocs.io/en/latest/). -->
<!--  -->
<!-- ``` -->
<!-- python manage.py clean_metrics myapp.UsageRecord --older-than 45 --time-unit days -->
<!-- ``` -->

## Signals

Signals are located in the `elasticsearch_metrics.signals` module.

* `pre_index_template_create(Metric, index_template, using)`: Sent before `PUT`ting a new index
    template into Elasticsearch.
* `post_index_template_create(Metric, index_template, using)`: Sent after `PUT`ting a new index
    template into Elasticsearch.
* `pre_save(Metric, instance, using, index)`: Sent at the beginning of a
    Metric's `save()` method.
* `post_save(Metric, instance, using, index)`: Sent at the end of a
    Metric's `save()` method.

## Caveats

* `_source` is disabled by default on metric indices in order to save
    disk space. For most metrics use cases, Users will not need to retrieve the source
    JSON documents. Be sure to understand the consequences of
    this: https://www.elastic.co/guide/en/elasticsearch/reference/current/mapping-source-field.html#_disabling_source .
    To enable `_source`, you can override it in `class Meta`.

```python
class MyMetric(EventRecord):
    class Meta:
        source = metrics.MetaField(enabled=True)
```

## Resources

* [Elasticsearch as a Time Series Data Store](https://www.elastic.co/blog/elasticsearch-as-a-time-series-data-store)
* [Pythonic Analytics with Elasticsearch](https://www.elastic.co/blog/pythonic-analytics-with-elasticsearch)
* [In Search of Agile Time Series Database](https://taowen.gitbooks.io/tsdb/content/index.html)

## License

MIT Licensed.
