from django.test import SimpleTestCase

from elasticsearch_metrics.imps import elastic6
from elasticsearch_metrics.registry import registry
from elasticsearch_metrics.tests.dummy6app.metrics import Dummy6Metric


class MetricWithAppLabel(elastic6.Metric):
    class Meta:
        app_label = "dummy6app"


class TestTimeseriesTypeRegistry(SimpleTestCase):
    def test_recordtype_in_app_is_in_registry(self):
        assert "dummy6app" in registry.all_recordtypes
        assert registry.all_recordtypes["dummy6app"]["dummy6metric"] is Dummy6Metric

    def test_recordtype_with_explicit_label_set_is_in_registry(self):
        assert (
            registry.all_recordtypes["dummy6app"]["metricwithapplabel"]
            is MetricWithAppLabel
        )

    def test_conflicting_recordtype(self):
        with self.assertRaises(RuntimeError):

            class MetricWithAppLabel(elastic6.Metric):
                class Meta:
                    app_label = "dummy6app"

    def test_get_recordtype(self):
        assert registry.get_recordtype("dummy6app", "Dummy6Metric") is Dummy6Metric
        assert registry.get_recordtype("dummy6app.Dummy6Metric") is Dummy6Metric

        with self.assertRaises(LookupError) as excinfo:
            registry.get_recordtype("dummy6app", "DoesNotExist")
        assert (
            "App 'dummy6app' doesn't have a 'DoesNotExist' metric."
            in excinfo.exception.args[0]
        )

        with self.assertRaises(LookupError) as excinfo:
            registry.get_recordtype("notanapp", "Dummy6Metric")
        assert (
            "No metrics found in app with label 'notanapp'."
            in excinfo.exception.args[0]
        )

    def test_get_recordtypes(self):
        class AnotherMetric(elastic6.Metric):
            class Meta:
                app_label = "anotherapp"

        assert Dummy6Metric in registry.get_recordtypes()
        assert AnotherMetric in registry.get_recordtypes()
        assert Dummy6Metric in registry.get_recordtypes(app_label="dummy6app")
        assert AnotherMetric not in registry.get_recordtypes(app_label="dummy6app")

        with self.assertRaises(LookupError) as excinfo:
            list(registry.get_recordtypes("notanapp"))
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

        assert elastic6.Metric not in registry.get_recordtypes()
        assert AbstractMetric not in registry.get_recordtypes()
        assert ConcreteMetric in registry.get_recordtypes()
