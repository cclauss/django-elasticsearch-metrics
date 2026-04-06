from django.test import SimpleTestCase

from elasticsearch_metrics.imps import elastic6
from elasticsearch_metrics.registry import djelme_registry
from elasticsearch_metrics.tests.dummy6app.metrics import Dummy6Metric
from elasticsearch_metrics.tests.dummy8app.metrics import Dummy8Event


class MetricWithAppLabel(elastic6.Metric):
    class Meta:
        app_label = "dummy6app"


class TestTimeseriesTypeRegistry(SimpleTestCase):
    def test_conflicting_recordtype(self):
        with self.assertRaises(RuntimeError):

            class MetricWithAppLabel(elastic6.Metric):
                class Meta:
                    app_label = "dummy6app"

    def test_get_recordtype(self):
        assert (
            djelme_registry.get_recordtype("dummy6app", "Dummy6Metric") is Dummy6Metric
        )
        assert djelme_registry.get_recordtype("dummy6app.Dummy6Metric") is Dummy6Metric
        assert djelme_registry.get_recordtype("dummy8app", "Dummy8Event") is Dummy8Event
        assert djelme_registry.get_recordtype("dummy8app.Dummy8Event") is Dummy8Event

        with self.assertRaises(LookupError) as excinfo:
            djelme_registry.get_recordtype("dummy6app", "DoesNotExist")
        assert (
            "App 'dummy6app' doesn't have a 'DoesNotExist' metric."
            in excinfo.exception.args[0]
        )

        with self.assertRaises(LookupError) as excinfo:
            djelme_registry.get_recordtype("notanapp", "Dummy6Metric")
        assert (
            "No recordtypes found in app with label 'notanapp'."
            in excinfo.exception.args[0]
        )

    def test_get_recordtypes(self):
        class AnotherMetric(elastic6.Metric):
            class Meta:
                app_label = "anotherapp"

        assert Dummy6Metric in djelme_registry.each_recordtype()
        assert AnotherMetric in djelme_registry.each_recordtype()
        assert Dummy6Metric in djelme_registry.each_recordtype(app_label="dummy6app")
        assert AnotherMetric not in djelme_registry.each_recordtype(
            app_label="dummy6app"
        )

        with self.assertRaises(LookupError) as excinfo:
            list(djelme_registry.each_recordtype(app_label="notanapp"))
        assert (
            "No recordtypes found in app with label 'notanapp'."
            in excinfo.exception.args[0]
        )

    def test_get_recordtypes_excludes_abstract_recordtypes(self):
        class AbstractMetric(elastic6.Metric):
            class Meta:
                abstract = True

        class ConcreteMetric(AbstractMetric):
            class Meta:
                app_label = "anotherapp"

        assert elastic6.Metric not in djelme_registry.each_recordtype()
        assert AbstractMetric not in djelme_registry.each_recordtype()
        assert ConcreteMetric in djelme_registry.each_recordtype()
