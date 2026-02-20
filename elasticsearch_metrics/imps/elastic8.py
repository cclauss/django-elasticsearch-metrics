"""elasticsearch_metrics.elastic8: store events and reports in elasticsearch 8

>>> from elasticsearch_metrics.imps.elastic8 import EventLog
>>> class TheThingHappened(EventLog):
...     intensity: int
...
...     class Index:  # elasticsearch index settings
...         settings = {
...             "number_of_shards": 2,
...             "refresh_interval": "5s",
...         }
"""

__all__ = (
    "TimeseriesRecord",
    "EventLog",
    "CyclicReport",
)
from collections.abc import Iterator
import dataclasses
import datetime
import logging

from django.apps import apps
from django.conf import settings
from django.utils import timezone
from elasticsearch8.exceptions import NotFoundError
from elasticsearch8.dsl import Document, connections, Keyword, IndexTemplate
from elasticsearch8.dsl._sync.document import IndexMeta

from elasticsearch_metrics import signals
from elasticsearch_metrics import exceptions
from elasticsearch_metrics.registry import timeseries_type_registry
from elasticsearch_metrics.protocols import ProtoTimeseriesImp
from elasticsearch_metrics.util import timeseries_naming

logger = logging.getLogger(__name__)

_DEFAULT_TIMEPART_DEPTH = 2  # xxxx_xx

class _DjelmeRecordMeta(IndexMeta):
    """Metaclass for the base `DjelmeRecord` class.

    overrides behavior in elasticsearch-py's `IndexMeta` to allow
    additional config in a type's `class Meta`

    >>> class MyAbstractRecord(DjelmeRecord):
    ...     foo: int
    ...     class Meta:
    ...         abstract = True
    ...         blargl = 5
    >>> MyAbstractRecord.Meta.blargl
    5
    >>> MyAbstractRecord.Meta.abstract
    True
    >>> MyAbstractRecord.is_abstract
    True
    >>> MyAbstractRecord.app_label
    'elasticsearch_metrics'
    """

    _TYPECONFIG_CLS = "Meta"

    def __new__(mcls, name, bases, attrs):  # noqa: B902
        # override IndexMeta.__new__, which removes `class Meta`
        _doc_type_meta = attrs.get("Meta", None)
        _cls = super().__new__(mcls, name, bases, attrs)
        if _doc_type_meta is not None:
            if hasattr(_cls, "Meta"):
                for _attrname, _attrval in _doc_type_meta.__dict__.items():
                    if not hasattr(_cls.Meta, _attrname):
                        setattr(_cls.Meta, _attrname, _attrval)
            else:
                _cls.Meta = _doc_type_meta
        # register non-abstract subtypes
        if not _cls.is_abstract:
            timeseries_type_registry.register_recordtype(_cls.app_label, _cls)
        return _cls

    def _get_meta_attr(self, attr_name: str, default=None) -> bool:
        _meta = getattr(self, "Meta", None)
        return getattr(_meta, attr_name, default)

    @property
    def is_abstract(self) -> bool:
        return self._get_meta_attr("abstract", False)

    @property
    def app_label(self) -> str:
        _app_label = self._get_meta_attr("app_label")
        if _app_label is None:
            _app_label = self._find_app_label()
        assert isinstance(_app_label, str)
        return _app_label

    def _find_app_label(self) -> str:
        # Look for an application configuration to attach the model to.
        _containing_app_configs = sorted(
            (
                _app_config
                for _app_config in apps.get_app_configs()
                if self.__module__.startswith(_app_config.module.__name__)
            ),
            key=lambda _config: len(_config.module.__name__),
            reverse=True,  # longest module name first
        )
        if not _containing_app_configs:
            raise RuntimeError(
                "document class %s.%s doesn't declare an explicit "
                "app_label and isn't in an application in "
                "INSTALLED_APPS." % (self.__module__, self.__qualname__)
            )
        _app_config = _containing_app_configs[0]
        return _app_config.label


class DjelmeRecord(Document, metaclass=_DjelmeRecordMeta):
    """a subclass of elasticsearch8.dsl.Document, with conveniences"""

    class Meta:
        abstract = True


class TimeseriesRecord(DjelmeRecord):
    timestamp: datetime.datetime

    class Meta:
        abstract = True

    @classmethod
    def init(cls, index=None, using=None):
        """Create the index and populate the mappings in elasticsearch.

        overrides elasticsearch.Document.init
        """
        assert not cls.is_abstract
        cls.sync_index_template(using=using)
        return super().init(
            index=index or str(cls.get_index_timepattern()), using=using
        )

    @classmethod
    @property
    def timeseries_template(cls) -> IndexTemplate:
        return cls._index.as_template(
            template_name=cls.timeseries_template_name,
            pattern=cls.timeseries_index_pattern,
        )

    @classmethod
    @property
    def timeseries_template_name(cls) -> str:
        return timeseries_naming.format_template_name(cls.timeseries_index_prefix, cls.__name__.lower())

    @classmethod
    @property
    def timeseries_index_prefix(cls) -> str:
        return cls._get_meta_attr("index_name_prefix") or cls.app_label

    @classmethod
    @property
    def timeseries_index_pattern(cls) -> str:
        return timeseries_naming.format_pattern(
            prefix=cls.timeseries_index_prefix,
            recordtype=cls.__name__,
        )

    @classmethod
    def full_timepattern(cls) -> TimeseriesIndexNamePattern:
        """
        """
        return TimeseriesIndexNamePattern(
            prefix=cls.app_label,
            recordtype=TimeseriesIndexNamePattern.format_timepart(cls.__name__),
        )

    @classmethod
    def _timepattern_for_timespan(
        cls, start_timeparts: tuple[int, ...], end_timeparts: tuple[int, ...]
    ) -> TimeseriesIndexNamePattern:
        """
        """
        cls._get_meta_attr("timepart_depth", _DEFAULT_TIMEPART_DEPTH)
        return cls.full_timepattern().replace(timeparts=...)

    ######
    # TODO: revisit the following

    @classmethod
    def sync_index_template(cls, using=None):
        """Sync the index template for this metric in Elasticsearch."""
        index_template = cls.get_timeseries_index_template()
        signals.pre_index_template_create.send(
            cls, index_template=index_template, using=using
        )
        index_template.save(using=using)
        signals.post_index_template_create.send(
            cls, index_template=index_template, using=using
        )
        return index_template

    @classmethod
    def check_index_template(cls, using=None):
        """Check if class is in sync with index template in Elasticsearch.

        :raise: IndexTemplateNotFoundError if index template does not exist.
        :raise: IndexTemplateOutOfSyncError if mappings, settings, or index patterns
            are out of sync.
        :return: True if index template exsits and mappings, settings, and index patterns
            are in sync.
        """
        client = connections.get_connection(using or "default")
        try:
            template = client.indices.get_template(cls._template_name)
        except NotFoundError as client_error:
            template_name = cls._template_name
            metric_name = cls.__name__
            raise exceptions.IndexTemplateNotFoundError(
                "{template_name} does not exist for {metric_name}".format(**locals()),
                client_error=client_error,
            ) from client_error
        else:
            current_data = list(template.values())[0]
            template_data = cls.get_timeseries_index_template().to_dict()

            mappings_in_sync = current_data["mappings"] == template_data["mappings"]
            if "settings" in current_data and "index" in current_data["settings"]:
                current_settings = current_data["settings"]["index"]
                template_settings = template_data.get("settings", {})
                # ES automatically casts number_of_shards and number_of_replicas to a string
                # so we need to cast before we compare
                # TODO: Are there other settings that need to be handled?
                number_settings = {"number_of_shards", "number_of_replicas"}
                for setting in number_settings:
                    if setting in template_settings:
                        template_settings[setting] = str(template_settings[setting])
                settings_in_sync = current_settings == template_settings
            else:
                settings_in_sync = True
            patterns_in_sync = (
                current_data["index_patterns"] == template_data["index_patterns"]
            )

            if not all([mappings_in_sync, settings_in_sync, patterns_in_sync]):
                template_name = cls._template_name
                metric_name = cls.__name__
                word_map = {
                    "mappings": mappings_in_sync,
                    "patterns": patterns_in_sync,
                    "settings": settings_in_sync,
                }
                out_of_sync = ", ".join(
                    [key for key, value in word_map.items() if not value]
                )
                raise exceptions.IndexTemplateOutOfSyncError(
                    "{template_name} is out of sync with {metric_name} ({out_of_sync})".format(
                        **locals()
                    ),
                    mappings_in_sync=mappings_in_sync,
                    patterns_in_sync=patterns_in_sync,
                    settings_in_sync=settings_in_sync,
                )
            return True

    @classmethod
    def record(cls, timestamp=None, **kwargs):
        """Persist a metric in Elasticsearch.

        :param datetime timestamp: Timestamp for the metric.
        """
        instance = cls(timestamp=timestamp, **kwargs)
        index = str(cls.get_index_timepattern(timestamp))
        instance.save(index=index)
        return instance

    def save(self, using=None, index=None, validate=True, **kwargs):
        """Same as `Document.save`, except will save into the index determined
        by the metric's timestamp field.
        """
        self.timestamp = self.timestamp or timezone.now()
        if not index:
            index = str(self.get_index_timepattern(datestamp=self.timestamp))

        cls = self.__class__
        signals.pre_save.send(cls, instance=self, using=using, index=index)
        ret = super(TimeseriesRecord, self).save(
            using=using, index=index, validate=validate, **kwargs
        )
        signals.post_save.send(cls, instance=self, using=using, index=index)
        return ret

    @classmethod
    def _default_index(cls, index=None):
        """Overrides Document._default_index so that .search, .get, etc.
        use the metric's template pattern as the default index
        """
        assert not cls.is_abstract
        return index or cls.timeseries_index_pattern


class EventLog(TimeseriesRecord):
    timestamp: datetime.datetime
    event_label: str = Keyword()
    event_tags: list[str]


class CyclicReport(TimeseriesRecord):
    timestamp: datetime.datetime
    report_label: str
    report_coverage: str


@dataclasses.dataclass
class DjelmeElastic8Imp(
    ProtoTimeseriesImp
):  # for ProtoTimeseriesImpModule.djelme_imp_from_config
    """DjelmeElastic8Imp: the elastic8 implementation of djelme (for use by generic djelme code)"""

    imp_name: str
    imp_config: dict[str, str]
    namespace_prefix: str = ""

    @property
    def elastic8_client(self):
        # assumes `configure` was already called
        return connections.get_connection(self.imp_name)

    def configure(self) -> None:
        connections.configure(**{self.imp_name: self.imp_config})

    def setup_timeseries_indexes(self) -> None:
        for _metric_type in self._each_recordtype():
            # TODO: logger.info
            _metric_type.sync_index_template(using=self.elastic6_client)

    def teardown_timeseries_indexes(self) -> None:
        for _metric_type in self._each_recordtype():
            _indexname_wildcard = _metric_type.timeseries_index_pattern
            _templatename = _metric_type._template_name
            self.elastic6_client.indices.delete(index=_indexname_wildcard)
            try:
                self.elastic6_client.indices.delete_template(_templatename)
            except NotFoundError:
                pass

    def _each_recordtype(self) -> Iterator[type]:
        for _type in timeseries_type_registry.each_recordtype(imp_name=self.imp_name):
            assert issubclass(_type, DjelmeRecord)
            yield _type


djelme_imp_from_config = DjelmeElastic8Imp  # for ProtoTimeseriesImpModule
