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
    Dummy8EventWithExplicitNamePrefix,
    ThingHappened,
    ThingHappeningsReport,
)


def _es8_client(
    backend_name: str = "my_elastic8_events",
) -> elasticsearch8.Elasticsearch:
    _backend = djelme_registry.get_backend(backend_name)
    assert isinstance(_backend, djelme.DjelmeElastic8Backend)
    return _backend.elastic8_client


class TestFormatIndexName(SimpleDjelmeTestCase):
    def test_format_timeseries_index_name(self):
        date = dt.date(2020, 2, 14)
        self.assertEqual(
            Dummy8Event.format_timeseries_index_name(date),
            "dummy8app_dummy8event_2020_02_14_",
        )

    def test_format_timeseries_index_name__cls_timedepth(self):
        date = dt.date(2020, 2, 14)
        self.assertEqual(
            ThingHappened.format_timeseries_index_name(date),
            "dummy8app_happen_2020_",
        )
        self.assertEqual(
            ThingHappeningsReport.format_timeseries_index_name(date),
            "blarg_thinghappeningsreport_2020_02_14_",
        )

    def test_format_index_name_respects_date_format_setting(self):
        with self.settings(DJELME_DEFAULT_TIMEDEPTH=4):
            date = dt.date(2020, 2, 14)
            self.assertEqual(
                Dummy8Event.format_timeseries_index_name(date),
                "dummy8app_dummy8event_2020_02_14_00_",
            )
            self.assertEqual(
                ThingHappened.format_timeseries_index_name(date),
                "dummy8app_happen_2020_",  # ThingHappened.Meta has timedepth=1
            )


class TestFormatIndexPattern(SimpleDjelmeTestCase):
    def test_format_timeseries_index_pattern(self):
        _timeparts = (2020, 2, 14, 0, 1, 2)
        self.assertEqual(
            Dummy8Event.format_timeseries_index_pattern(_timeparts),
            "dummy8app_dummy8event_2020_02_14_*",
        )

    def test_format_timeseries_index_pattern__cls_timedepth(self):
        _timeparts = (2020, 2, 14)
        self.assertEqual(
            ThingHappened.format_timeseries_index_pattern(_timeparts),
            "dummy8app_happen_2020_*",
        )
        self.assertEqual(
            ThingHappeningsReport.format_timeseries_index_pattern(_timeparts),
            "blarg_thinghappeningsreport_2020_02_14_*",
        )

    def test_format_index_pattern_respects_date_format_setting(self):
        with self.settings(DJELME_DEFAULT_TIMEDEPTH=4):
            _timeparts = (2020, 2, 14, 0, 1, 2)
            self.assertEqual(
                Dummy8Event.format_timeseries_index_pattern(_timeparts),
                "dummy8app_dummy8event_2020_02_14_00_*",
            )
            self.assertEqual(
                ThingHappened.format_timeseries_index_pattern(_timeparts),
                "dummy8app_happen_2020_*",  # ThingHappened.Meta has timedepth=1
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

    # regression test
    def test_mappings_are_not_shared(self):
        template1 = Dummy8Event.get_timeseries_template().to_dict()
        template2 = (
            Dummy8EventWithExplicitNamePrefix.get_timeseries_template().to_dict()
        )
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
        template = Dummy8EventWithExplicitNamePrefix.get_timeseries_template()
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


class TestCreateAndSearch(RealElasticTestCase, autosetup_djelme_backends=True):
    def test_create_document(self):
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
        assert _fetched_doc.thing_id == _doc.thing_id == _thing_id
        assert _fetched_doc.happen_code == _doc.happen_code == _happen_code

        # index mappings should match the index template
        name = _doc.djelme_index_name()
        mapping = _es8_client().indices.get_mapping(index=name)
        properties = mapping[name]["mappings"]["properties"]
        assert properties["timestamp"] == {"type": "date"}
        assert properties["thing_id"] == {"type": "keyword"}
        assert properties["happen_code"] == {"type": "keyword"}

    def test_search(self): ...  # TODO


class TestInit(RealElasticTestCase, autosetup_djelme_backends=False):
    def test_init(self):
        ThingHappened.init()
        name = ThingHappened.format_timeseries_index_name()
        mapping = _es8_client().indices.get_mapping(index=name)
        properties = mapping[name]["mappings"]["properties"]
        assert properties["timestamp"] == {"type": "date"}
        assert properties["thing_id"] == {"type": "keyword"}
        assert properties["happen_code"] == {"type": "keyword"}

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
