import os

SECRET_KEY = "not so secret in tests"
DEBUG = True
USE_TZ = True
TIMEZONE = 'UTC'
ALLOWED_HOSTS = []
INSTALLED_APPS = [
    "elasticsearch_metrics.apps.ElasticsearchMetricsConfig",
    "elasticsearch_metrics.tests.dummy6app",
    # "elasticsearch_metrics.tests.dummy8app",
]
MIDDLEWARE_CLASSES = []
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": "test_djelme"}}

DJELMETRICS_IMPS = {
    "elastic6foo": {
        "DJELMETRICS_IMP": "elasticsearch_metrics.imps.elastic6",
        "host": os.environ.get("ELASTICSEARCH6_HOST"),
    },
    # "elastic8foo": {
    #     "DJELMETRICS_IMP": "elasticsearch_metrics.imps.elastic8",
    #     "host": os.environ.get("ELASTICSEARCH8_HOST"),
    # },
    # "elastic8bar": {
    #     "DJELMETRICS_IMP": "elasticsearch_metrics.imps.elastic8",
    #     "host": os.environ.get("ELASTICSEARCH8_HOST"),
    # },
}
