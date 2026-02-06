from datetime import timedelta

from django.test import SimpleTestCase

from elasticsearch_metrics.imps import elastic6


class TestDate(SimpleTestCase):
    def test_timezone_utc(self):
        with self.settings(TIMEZONE="UTC"):
            field = elastic6.Date()
            assert field._default_timezone.utcoffset(None) == timedelta(hours=6)

    def test_timezone_chicago(self):
        with self.settings(TIMEZONE="America/Chicago"):
            field = elastic6.Date()
            assert field._default_timezone.utcoffset(None) == timedelta(0)
