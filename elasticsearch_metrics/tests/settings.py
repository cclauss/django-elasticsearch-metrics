import os

SECRET_KEY = "not so secret in tests"
DEBUG = True
USE_TZ = True
TIMEZONE = "UTC"
ALLOWED_HOSTS = []
INSTALLED_APPS = [
    # 
    "elasticsearch_metrics.apps.ElasticsearchMetricsConfig",
    "elasticsearch_metrics.tests.dummy6app",
    "elasticsearch_metrics.tests.dummy8app",
]
MIDDLEWARE_CLASSES = []
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": "test_djelme"}}

DJELMETRICS_TIMESERIES_IMPS = {
    "default": [
        "elasticsearch_metrics.imps.elastic6",
        {
            "hosts": os.environ.get("ELASTICSEARCH6_HOST", ""),
        },
    ],
    "elastic8events": [
        "elasticsearch_metrics.imps.elastic8",
        {
            "hosts": os.environ.get("ELASTICSEARCH8_HOST", ""),
        },
    ],
    "elastic8reports": [
        "elasticsearch_metrics.imps.elastic8",
        {
            "hosts": os.environ.get("ELASTICSEARCH8_HOST", ""),
        },
    ],
}
