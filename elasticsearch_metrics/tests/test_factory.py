import factory

from elasticsearch_metrics.imps import elastic6
from elasticsearch_metrics.factory import MetricFactory
from elasticsearch_metrics.tests._test_util import MockSaveTestCase
from elasticsearch_metrics.tests.dummy6app.metrics import Dummy6Metric


class MyDummyMetricFactory(MetricFactory):
    my_int = factory.Faker("pyint")

    class Meta:
        model = Dummy6Metric


class TestTestFactory(MockSaveTestCase):
    def test_build(self):
        metric = MyDummyMetricFactory.build()
        assert isinstance(metric, elastic6.Metric)
        assert isinstance(metric.my_int, int)

    def test_save(self):
        metric = MyDummyMetricFactory()
        assert isinstance(metric, elastic6.Metric)
        assert self.mocked_es6_save.call_count == 1
