from datetime import datetime, timedelta

from django.test import SimpleTestCase

from elasticsearch_metrics.imps import elastic6


class TestDate(SimpleTestCase):
    def test_timezone_utc(self):
        with self.settings(TIMEZONE="UTC"):
            field = elastic6.Date()
            self._assert_tz(field._default_timezone, timedelta(0))

    def test_timezone_chicago(self):
        with self.settings(TIMEZONE="America/Chicago"):
            field = elastic6.Date()
            self._assert_tz(field._default_timezone, timedelta(hours=-6))

    def _assert_tz(self, actual_tzinfo, expected_tz_offset: timedelta):
        _time = datetime(1999, 1, 1)
        self.assertEqual(actual_tzinfo.utcoffset(_time), expected_tz_offset)
