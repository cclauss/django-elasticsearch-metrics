import unittest
import datetime as dt

from django.utils import timezone

import elasticsearch8
from elasticsearch8.dsl import (
    ComposableIndexTemplate,
    MetaField,
)

from elasticsearch_metrics import signals
from elasticsearch_metrics.imps import elastic8 as djelme
from elasticsearch_metrics.exceptions import (
    IndexTemplateNotFoundError,
    IndexTemplateOutOfSyncError,
)
from elasticsearch_metrics.registry import djelme_registry
from elasticsearch_metrics.tests._test_util import (
    SimpleDjelmeTestCase,
    MockSaveTestCase,
    RealElasticTestCase,
)
from elasticsearch_metrics.tests.dummy8app.metrics import (
    Dummy8Event,
    Monthly8Event,
    ThingHappened,
    ThingHappeningsReport,
)


def _es8_client(
    backend_name: str = "my_elastic8_events",
) -> elasticsearch8.Elasticsearch:
    _backend = djelme_registry.get_backend(backend_name)
    assert isinstance(_backend, djelme.DjelmeElastic8Backend)
    return _backend.elastic8_client


class TestNamesAndPatterns(SimpleDjelmeTestCase):
    def test_format_timeseries_index_name(self):
        date = dt.date(2020, 2, 14)
        self.assertEqual(
            Dummy8Event.format_timeseries_index_name(date),
            "dummy8app_dummy8event_2020_02_14_",
        )
        self.assertEqual(
            Monthly8Event.format_timeseries_index_name(date),
            "dummy8evenz_eventlog_2020_02_",
        )
        self.assertEqual(
            ThingHappened.format_timeseries_index_name(date),
            "dummy8app_happen_2020_",
        )
        self.assertEqual(
            ThingHappeningsReport.format_timeseries_index_name(date),
            "blarg_thinghappeningsreport_2020_02_",
        )

    def test_format_index_name_respects_date_format_setting(self):
        with self.settings(DJELME_DEFAULT_TIMEDEPTH=4):
            date = dt.date(2020, 2, 14)
            # no timedepth set; use default setting
            self.assertEqual(
                Dummy8Event.format_timeseries_index_name(date),
                "dummy8app_dummy8event_2020_02_14_00_",
            )
            # timedepth set; ignore default setting
            self.assertEqual(
                Monthly8Event.format_timeseries_index_name(date),
                "dummy8evenz_eventlog_2020_02_",
            )
            self.assertEqual(
                ThingHappened.format_timeseries_index_name(date),
                "dummy8app_happen_2020_",
            )
            self.assertEqual(
                ThingHappeningsReport.format_timeseries_index_name(date),
                "blarg_thinghappeningsreport_2020_02_",
            )

    def test_format_timeseries_index_pattern__lotsa_parts(self):
        _timeparts = (2020, 2, 14, 0, 1, 2)
        self.assertEqual(
            Dummy8Event.format_timeseries_index_pattern(_timeparts),
            "dummy8app_dummy8event_2020_02_14_*",
        )
        self.assertEqual(
            Monthly8Event.format_timeseries_index_pattern(_timeparts),
            "dummy8evenz_eventlog_2020_02_*",
        )
        self.assertEqual(
            ThingHappened.format_timeseries_index_pattern(_timeparts),
            "dummy8app_happen_2020_*",
        )
        self.assertEqual(
            ThingHappeningsReport.format_timeseries_index_pattern(_timeparts),
            "blarg_thinghappeningsreport_2020_02_*",
        )

    def test_format_timeseries_index_pattern__some_parts(self):
        _timeparts = (2020, 2, 14)
        self.assertEqual(
            Dummy8Event.format_timeseries_index_pattern(_timeparts),
            "dummy8app_dummy8event_2020_02_14_*",
        )
        self.assertEqual(
            Monthly8Event.format_timeseries_index_pattern(_timeparts),
            "dummy8evenz_eventlog_2020_02_*",
        )
        self.assertEqual(
            ThingHappened.format_timeseries_index_pattern(_timeparts),
            "dummy8app_happen_2020_*",
        )
        self.assertEqual(
            ThingHappeningsReport.format_timeseries_index_pattern(_timeparts),
            "blarg_thinghappeningsreport_2020_02_*",
        )

    def test_format_timeseries_index_pattern__one_part(self):
        _timeparts = (2020,)
        self.assertEqual(
            Dummy8Event.format_timeseries_index_pattern(_timeparts),
            "dummy8app_dummy8event_2020_*",
        )
        self.assertEqual(
            Monthly8Event.format_timeseries_index_pattern(_timeparts),
            "dummy8evenz_eventlog_2020_*",
        )
        self.assertEqual(
            ThingHappened.format_timeseries_index_pattern(_timeparts),
            "dummy8app_happen_2020_*",
        )
        self.assertEqual(
            ThingHappeningsReport.format_timeseries_index_pattern(_timeparts),
            "blarg_thinghappeningsreport_2020_*",
        )

    def test_format_index_pattern_respects_date_format_setting(self):
        with self.settings(DJELME_DEFAULT_TIMEDEPTH=4):
            _timeparts = (2020, 2, 14, 0, 1, 2)
            self.assertEqual(
                Dummy8Event.format_timeseries_index_pattern(_timeparts),
                "dummy8app_dummy8event_2020_02_14_00_*",
            )
            self.assertEqual(
                Monthly8Event.format_timeseries_index_pattern(_timeparts),
                "dummy8evenz_eventlog_2020_02_*",
            )
            self.assertEqual(
                ThingHappened.format_timeseries_index_pattern(_timeparts),
                "dummy8app_happen_2020_*",
            )


class TestGetIndexTemplate(SimpleDjelmeTestCase):
    def test_get_index_template_returns_template_with_correct_name_and_pattern(self):
        template = ThingHappened.get_timeseries_template()
        self.assertIsInstance(template, ComposableIndexTemplate)
        self.assertEqual(template._template_name, "dummy8app_happen__template")
        _template_dict = template.to_dict()
        self.assertEqual(_template_dict["index_patterns"], ["dummy8app_happen_*"])

    def test_get_index_template_respects_index_settings(self):
        template = ThingHappened.get_timeseries_template()
        assert template._index.to_dict()["settings"] == {
            "refresh_interval": "-1",
            "analysis": {
                "analyzer": {
                    "dot_path_analyzer": {
                        "tokenizer": "dot_path_tokenizer",
                        "type": "custom",
                    }
                },
                "tokenizer": {
                    "dot_path_tokenizer": {
                        "delimiter": ".",
                        "type": "path_hierarchy",
                    }
                },
            },
        }

    def test_get_index_template_creates_template_with_mapping(self):
        template = ThingHappened.get_timeseries_template()
        mappings = template.to_dict()["template"]["mappings"]
        properties = mappings["properties"]
        assert "timestamp" in properties
        assert properties["timestamp"] == {"type": "date"}
        assert properties["thing_id"] == {"type": "keyword"}
        assert properties["happen_code"] == {"type": "keyword"}

    def test_mappings_are_not_shared(self):
        template1 = Dummy8Event.get_timeseries_template().to_dict()
        template2 = Monthly8Event.get_timeseries_template().to_dict()
        assert "intensity" in template1["template"]["mappings"]["properties"]
        assert "intenzity" not in template1["template"]["mappings"]["properties"]
        assert "intensity" not in template2["template"]["mappings"]["properties"]
        assert "intenzity" in template2["template"]["mappings"]["properties"]

    def test_get_index_template_default_template_name(self):
        template = Dummy8Event.get_timeseries_template()
        assert isinstance(template, ComposableIndexTemplate)
        assert template._template_name == "dummy8app_dummy8event__template"
        assert "dummy8app_dummy8event_*" in template.to_dict()["index_patterns"]

    def test_get_index_template_uses_app_label_in_class_meta(self):
        class MyRecord(djelme.TimeseriesRecord):
            class Index:
                using = "my_elastic8_events"

            class Meta:
                app_label = "myapp"

        template = MyRecord.get_timeseries_template()
        assert template._template_name == "myapp_myrecord__template"

    def test_template_name_defined_with_no_template_falls_back_to_default_template(
        self,
    ):
        template = Monthly8Event.get_timeseries_template()
        # prefix and recordtype specified in class Meta
        assert template._template_name == "dummy8evenz_eventlog__template"
        # template pattern generated using same options
        assert "dummy8evenz_eventlog_*" in template.to_dict()["index_patterns"]

    def test_inheritance(self):
        class MyBaseRecord(djelme.TimeseriesRecord):
            label: str

            class Index:
                settings = {"number_of_shards": 2}
                using = "my_elastic8_events"

            class Meta:
                abstract = True

        class ConcreteRecord(MyBaseRecord):
            class Meta:
                app_label = "dummy8app"

        template = ConcreteRecord.get_timeseries_template()
        assert template._template_name == "dummy8app_concreterecord__template"
        assert template._index.to_dict()["settings"] == {"number_of_shards": 2}

    def test_source_may_be_enabled(self):
        class MyRecord(djelme.TimeseriesRecord):
            class Index:
                using = "my_elastic8_events"

            class Meta:
                app_label = "dummy8app"
                timeseries_recordtype_name = "myrecord"
                source = MetaField(enabled=True)

        template = MyRecord.get_timeseries_template()
        template_dict = template.to_dict()
        doc = template_dict["template"]["mappings"]
        assert doc["_source"]["enabled"] is True


class TestRecord(MockSaveTestCase):
    def test_calls_save(self):
        timestamp = dt.datetime(2017, 8, 21)
        p = ThingHappened.record(timestamp=timestamp, thing_id="abc12")
        assert self.mocked_es8_save.call_count == 1
        assert p.timestamp == timestamp
        assert p.timestamp_parts == "2017.8.21.0.0.0"
        assert p.thing_id == "abc12"

    @unittest.mock.patch.object(timezone, "now")
    def test_defaults_timestamp_to_now(self, mock_now):
        fake_now = dt.datetime(2016, 8, 21)
        mock_now.return_value = fake_now

        p = ThingHappened.record(thing_id="abc12")
        assert self.mocked_es8_save.call_count == 1
        assert p.timestamp == fake_now


class TestSignals(MockSaveTestCase):
    @unittest.mock.patch.object(ThingHappened, "get_timeseries_template")
    def test_create_record_sends_signals(self, mock_timeseries_template):
        mock_pre_index_template_listener = unittest.mock.Mock()
        mock_post_index_template_listener = unittest.mock.Mock()
        signals.pre_index_template_create.connect(mock_pre_index_template_listener)
        signals.post_index_template_create.connect(mock_post_index_template_listener)
        ThingHappened.sync_index_template()
        assert mock_pre_index_template_listener.call_count == 1
        assert mock_post_index_template_listener.call_count == 1
        pre_call_kwargs = mock_pre_index_template_listener.call_args[1]
        assert "index_template" in pre_call_kwargs
        assert "using" in pre_call_kwargs

        post_call_kwargs = mock_pre_index_template_listener.call_args[1]
        assert "index_template" in post_call_kwargs
        assert "using" in post_call_kwargs

    def test_save_sends_signals(self):
        mock_pre_save_listener = unittest.mock.Mock()
        mock_post_save_listener = unittest.mock.Mock()
        signals.pre_save.connect(mock_pre_save_listener, sender=ThingHappened)
        signals.post_save.connect(mock_post_save_listener, sender=ThingHappened)

        thing_id = "12345"
        happen_code = "zyxwv"
        doc = ThingHappened(thing_id=thing_id, happen_code=happen_code)
        doc.save()

        assert mock_pre_save_listener.call_count == 1
        pre_save_kwargs = mock_pre_save_listener.call_args[1]
        assert isinstance(pre_save_kwargs["instance"], ThingHappened)
        assert "index" in pre_save_kwargs
        assert "using" in pre_save_kwargs
        assert pre_save_kwargs["sender"] is ThingHappened

        assert mock_post_save_listener.call_count == 1
        post_save_kwargs = mock_pre_save_listener.call_args[1]
        assert isinstance(post_save_kwargs["instance"], ThingHappened)
        assert "index" in post_save_kwargs
        assert "using" in post_save_kwargs
        assert post_save_kwargs["sender"] is ThingHappened


class TestRealCreate(RealElasticTestCase, autosetup_djelme_backends=True):
    def test_save(self):
        _thing_id = "12345"
        _happen_code = "zyxwv"
        _doc = ThingHappened(thing_id=_thing_id, happen_code=_happen_code)
        _doc.save()
        assert _doc.timestamp is not None
        _fetched_doc = ThingHappened.get(
            id=_doc.meta.id, index=_doc.djelme_index_name()
        )
        assert _fetched_doc
        assert _fetched_doc.timestamp == _doc.timestamp
        assert _fetched_doc.timestamp_parts == _doc.timestamp_parts
        assert _fetched_doc.thing_id == _doc.thing_id == _thing_id
        assert _fetched_doc.happen_code == _doc.happen_code == _happen_code

        # index mappings should match the index template
        name = _doc.djelme_index_name()
        mapping = _es8_client().indices.get_mapping(index=name)
        properties = mapping[name]["mappings"]["properties"]
        assert properties["timestamp"] == {"type": "date"}
        assert properties["thing_id"] == {"type": "keyword"}
        assert properties["happen_code"] == {"type": "keyword"}

    def test_record(self):
        _thing_id = "54321"
        _happen_code = "abcde"
        _doc = ThingHappened.record(thing_id=_thing_id, happen_code=_happen_code)
        assert _doc.timestamp is not None
        _fetched_doc = ThingHappened.get(
            id=_doc.meta.id, index=_doc.djelme_index_name()
        )
        assert _fetched_doc
        assert _fetched_doc.timestamp == _doc.timestamp
        assert _fetched_doc.timestamp_parts == _doc.timestamp_parts
        assert _fetched_doc.thing_id == _doc.thing_id == _thing_id
        assert _fetched_doc.happen_code == _doc.happen_code == _happen_code

        # index mappings should match the index template
        name = _doc.djelme_index_name()
        mapping = _es8_client().indices.get_mapping(index=name)
        properties = mapping[name]["mappings"]["properties"]
        assert properties["timestamp"] == {"type": "date"}
        assert properties["thing_id"] == {"type": "keyword"}
        assert properties["happen_code"] == {"type": "keyword"}


class TestInit(RealElasticTestCase, autosetup_djelme_backends=False):
    def test_init(self):
        ThingHappened.init()
        _client = _es8_client()
        _template_name = ThingHappened.get_timeseries_template_name()
        _index_pattern = ThingHappened.format_timeseries_index_pattern()
        _template_resp = _client.indices.get_index_template(name=_template_name)
        (_t_info,) = _template_resp["index_templates"]
        self.assertEqual(_t_info["name"], _template_name)
        self.assertEqual(
            _t_info["index_template"]["index_patterns"],
            [_index_pattern],
        )
        _properties = _t_info["index_template"]["template"]["mappings"]["properties"]
        self.assertEqual(_properties["timestamp"], {"type": "date"})
        self.assertEqual(_properties["thing_id"], {"type": "keyword"})
        self.assertEqual(_properties["happen_code"], {"type": "keyword"})
        # no indexes; only the template
        self.assertFalse(list(ThingHappened.each_timeseries_index()))

    def test_check_djelme_setup(self):
        with self.assertRaises(IndexTemplateNotFoundError):
            assert ThingHappened.check_djelme_setup() is False
        ThingHappened.sync_index_template()
        assert ThingHappened.check_djelme_setup() is True

        # When settings change, template is out of sync
        ThingHappened._index.settings(
            **{"refresh_interval": "1s", "number_of_shards": 1, "number_of_replicas": 2}
        )
        with self.assertRaises(IndexTemplateOutOfSyncError) as excinfo:
            assert ThingHappened.check_djelme_setup() is False
        error = excinfo.exception
        assert error.settings_in_sync is False
        assert error.mappings_in_sync is True
        assert error.patterns_in_sync is True

        ThingHappened.sync_index_template()
        assert ThingHappened.check_djelme_setup() is True


class TestDailyIndexes(RealElasticTestCase, autosetup_djelme_backends=True):
    def setUp(self):
        super().setUp()
        Dummy8Event.record(timestamp=dt.datetime(1234, 5, 6), intensity=1)
        Dummy8Event.record(timestamp=dt.datetime(1234, 5, 6, 7), intensity=2)
        Dummy8Event.record(timestamp=dt.datetime(1234, 5, 7), intensity=3)
        Dummy8Event.record(timestamp=dt.datetime(1234, 6, 1), intensity=7)
        Dummy8Event.record(timestamp=dt.datetime(1235, 5, 6), intensity=111)
        Dummy8Event.record(timestamp=dt.datetime(2345, 6, 9), intensity=11)
        Dummy8Event.record(timestamp=dt.datetime(2345, 7, 9), intensity=13)
        Dummy8Event.refresh_timeseries_indexes()

    def test_indexes(self):
        _index_names = {_name for _name, _ in Dummy8Event.each_timeseries_index()}
        self.assertEqual(
            _index_names,
            {
                "dummy8app_dummy8event_1234_05_06_",
                "dummy8app_dummy8event_1234_05_07_",
                "dummy8app_dummy8event_1234_06_01_",
                "dummy8app_dummy8event_1235_05_06_",
                "dummy8app_dummy8event_2345_06_09_",
                "dummy8app_dummy8event_2345_07_09_",
            },
        )

    def test_search(self):
        def _assert_intens(hits, expected_intensities):
            _actual = {_hit.intensity for _hit in hits}
            self.assertEqual(_actual, expected_intensities)

        _assert_intens(
            Dummy8Event.search(),
            {1, 2, 3, 7, 11, 13, 111},
        )
        _assert_intens(
            Dummy8Event.search_timeseries_range((1234,), (1235,)),
            {1, 2, 3, 7},
        )
        _assert_intens(
            Dummy8Event.search_timeseries_range((1233,), (1234,)),
            set(),
        )
        _assert_intens(
            Dummy8Event.search_timeseries_range(
                dt.date(1234, 5, 6), dt.date(1234, 5, 7)
            ),
            {1, 2},
        )
        _assert_intens(
            Dummy8Event.search_timeseries_range((1234, 6), dt.date(2345, 7, 1)),
            {7, 111, 11},
        )
        _assert_intens(
            Dummy8Event.search_timeseries_range((1234, 5, 6, 2), (1234, 5, 7)),
            {2},
        )


class TestMonthlyIndexes(RealElasticTestCase, autosetup_djelme_backends=True):
    def setUp(self):
        super().setUp()
        Monthly8Event.record(timestamp=dt.datetime(1234, 5, 6), intenzity=1)
        Monthly8Event.record(timestamp=dt.datetime(1234, 5, 6, 7), intenzity=2)
        Monthly8Event.record(timestamp=dt.datetime(1234, 5, 7), intenzity=3)
        Monthly8Event.record(timestamp=dt.datetime(1234, 6, 1), intenzity=7)
        Monthly8Event.record(timestamp=dt.datetime(1235, 5, 6), intenzity=111)
        Monthly8Event.record(timestamp=dt.datetime(2345, 6, 9), intenzity=11)
        Monthly8Event.record(timestamp=dt.datetime(2345, 7, 9), intenzity=13)
        Monthly8Event.refresh_timeseries_indexes()

    def test_indexes(self):
        _index_names = {_name for _name, _ in Monthly8Event.each_timeseries_index()}
        self.assertEqual(
            _index_names,
            {
                "dummy8evenz_eventlog_1234_05_",
                "dummy8evenz_eventlog_1234_06_",
                "dummy8evenz_eventlog_1235_05_",
                "dummy8evenz_eventlog_2345_06_",
                "dummy8evenz_eventlog_2345_07_",
            },
        )

    def test_search(self):
        def _assert_intenz(hits, expected_intenzities):
            _actual = {_hit.intenzity for _hit in hits}
            self.assertEqual(_actual, expected_intenzities)

        _assert_intenz(
            Monthly8Event.search(),
            {1, 2, 3, 7, 11, 13, 111},
        )
        _assert_intenz(
            Monthly8Event.search_timeseries_range((1234,), (1235,)),
            {1, 2, 3, 7},
        )
        _assert_intenz(
            Monthly8Event.search_timeseries_range((1233,), (1234,)),
            set(),
        )
        _assert_intenz(
            Monthly8Event.search_timeseries_range(
                dt.date(1234, 5, 6), dt.date(1234, 5, 7)
            ),
            {1, 2},
        )
        _assert_intenz(
            Monthly8Event.search_timeseries_range((1234, 6), dt.date(2345, 7, 1)),
            {7, 111, 11},
        )
        _assert_intenz(
            Monthly8Event.search_timeseries_range((1234, 5, 6, 2), (1234, 5, 7)),
            {2},
        )


class TestYearlyIndexes(RealElasticTestCase, autosetup_djelme_backends=True):
    def setUp(self):
        super().setUp()
        ThingHappened.record(timestamp=dt.datetime(1234, 5, 6), thing_id="a")
        ThingHappened.record(timestamp=dt.datetime(1234, 5, 6, 7), thing_id="b")
        ThingHappened.record(timestamp=dt.datetime(1234, 5, 7), thing_id="c")
        ThingHappened.record(timestamp=dt.datetime(1234, 6, 1), thing_id="d")
        ThingHappened.record(timestamp=dt.datetime(1235, 5, 6), thing_id="e")
        ThingHappened.record(timestamp=dt.datetime(2345, 6, 9), thing_id="f")
        ThingHappened.record(timestamp=dt.datetime(2345, 7, 9), thing_id="g")
        ThingHappened.refresh_timeseries_indexes()

    def test_indexes(self):
        _index_names = {_name for _name, _ in ThingHappened.each_timeseries_index()}
        self.assertEqual(
            _index_names,
            {
                "dummy8app_happen_1234_",
                "dummy8app_happen_1235_",
                "dummy8app_happen_2345_",
            },
        )

    def test_search(self):
        def _assert_things(hits, expected_thing_ids):
            _actual = {_hit.thing_id for _hit in hits}
            self.assertEqual(_actual, expected_thing_ids)

        _assert_things(
            ThingHappened.search(),
            {"a", "b", "c", "d", "e", "f", "g"},
        )
        _assert_things(
            ThingHappened.search_timeseries_range((1234,), (1235,)),
            {"a", "b", "c", "d"},
        )
        _assert_things(
            ThingHappened.search_timeseries_range((1233,), (1234,)),
            set(),
        )
        _assert_things(
            ThingHappened.search_timeseries_range(
                dt.date(1234, 5, 6), dt.date(1234, 5, 7)
            ),
            {"a", "b"},
        )
        _assert_things(
            ThingHappened.search_timeseries_range((1234, 6), dt.date(2345, 7, 1)),
            {"d", "e", "f"},
        )
        _assert_things(
            ThingHappened.search_timeseries_range((1234, 5, 6, 2), (1234, 5, 7)),
            {"b"},
        )
