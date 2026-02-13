from django.test import SimpleTestCase

from elasticsearch_metrics.imps import elastic6
from elasticsearch_metrics.registry import registry
from elasticsearch_metrics.tests.dummy6app.metrics import Dummy6Metric


class MetricWithAppLabel(elastic6.Metric):
    class Meta:
        app_label = "dummy6app"


class TestDjelmetricsRegistry(SimpleTestCase):
    def test_metric_in_app_is_in_registry(self):
        assert "dummy6app" in registry.all_metrics
        assert registry.all_metrics["dummy6app"]["dummy6metric"] is Dummy6Metric

    def test_metric_with_explicit_label_set_is_in_registry(self):
        assert (
            registry.all_metrics["dummy6app"]["metricwithapplabel"]
            is MetricWithAppLabel
        )

    def test_conflicting_metric(self):
        with self.assertRaises(RuntimeError):

            class MetricWithAppLabel(elastic6.Metric):
                class Meta:
                    app_label = "dummy6app"

    def test_get_metric(self):
        assert registry.get_metric("dummy6app", "Dummy6Metric") is Dummy6Metric
        assert registry.get_metric("dummy6app.Dummy6Metric") is Dummy6Metric

        with self.assertRaises(LookupError) as excinfo:
            registry.get_metric("dummy6app", "DoesNotExist")
        assert (
            "App 'dummy6app' doesn't have a 'DoesNotExist' metric."
            in excinfo.exception.args[0]
        )

        with self.assertRaises(LookupError) as excinfo:
            registry.get_metric("notanapp", "Dummy6Metric")
        assert (
            "No metrics found in app with label 'notanapp'."
            in excinfo.exception.args[0]
        )

    def test_get_metrics(self):
        class AnotherMetric(elastic6.Metric):
            class Meta:
                app_label = "anotherapp"

        assert Dummy6Metric in registry.get_metrics()
        assert AnotherMetric in registry.get_metrics()
        assert Dummy6Metric in registry.get_metrics(app_label="dummy6app")
        assert AnotherMetric not in registry.get_metrics(app_label="dummy6app")

        with self.assertRaises(LookupError) as excinfo:
            list(registry.get_metrics("notanapp"))
        assert (
            "No metrics found in app with label 'notanapp'."
            in excinfo.exception.args[0]
        )

    def test_get_metrics_excludes_abstract_metrics(self):
        class AbstractMetric(elastic6.Metric):
            class Meta:
                abstract = True

        class ConcreteMetric(AbstractMetric):
            class Meta:
                app_label = "anotherapp"

        assert elastic6.Metric not in registry.get_metrics()
        assert AbstractMetric not in registry.get_metrics()
        assert ConcreteMetric in registry.get_metrics()
