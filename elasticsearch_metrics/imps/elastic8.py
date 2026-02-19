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
    "PeriodicReport",
)
from collections.abc import Iterator
import dataclasses
import datetime
import logging

from django.apps import apps
from django.conf import settings
from django.utils import timezone
from elasticsearch8.exceptions import NotFoundError
from elasticsearch8.dsl import Document, connections
from elasticsearch8.dsl._sync.document import IndexMeta

from elasticsearch_metrics import signals
from elasticsearch_metrics import exceptions
from elasticsearch_metrics.registry import timeseries_type_registry
from elasticsearch_metrics.protocols import ProtoTimeseriesImp

DEFAULT_DATE_FORMAT = "%Y.%m.%d"

logger = logging.getLogger(__name__)


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


@dataclasses.dataclass(frozen=True)
class TimeseriesIndexName:
    namespace_prefix: str
    app_label: str
    recordtype_name: str
    time_coverage: str

    def __str__(self) -> str:
        return f"{self.namespace_prefix}_{self.app_label}_{self.recordtype_name}_{self.time_coverage}"


class TimeseriesRecord(DjelmeRecord):
    timestamp: datetime.datetime

    class Meta:
        abstract = True

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if not cls.is_abstract:
            timeseries_type_registry.register_recordtype(cls.app_label, cls)

    @classmethod
    def init(cls, index=None, using=None):
        """Create the index and populate the mappings in elasticsearch.

        overrides elasticsearch.Document.init
        """
        assert not cls.is_abstract
        cls.sync_index_template(using=using)
        return super().init(index=index or cls.get_timeseries_index_name(), using=using)

    @classmethod
    def get_timeseries_index_template(cls):
        """Return an `IndexTemplate <elasticsearch_dsl.IndexTemplate>` for this metric."""
        return cls._index.as_template(
            template_name=cls._template_name,
            pattern=cls.index_name_wildcard,
        )

    @classmethod
    @property
    def template_name(cls) -> str:
        return (
            cls._get_meta_attr("template_name")
            or f"{cls.app_label}_{cls.__name__.lower()}"
        )

    @classmethod
    @property
    def index_name_wildcard(cls) -> str:
        return f"{cls.template_name}_*"

    @classmethod
    def get_template_name(cls) -> str:
        _template_name = cls.get_meta_setting("template_name")
        if not _template_name:
            # If template_name not specified in class Meta,
            # compute it as <app label>_<lowercased class name>
            _cls_name = cls.__name__.lower()
            _template_name = f"{cls.app_label}_{_cls_name}"
        return _template_name

    @classmethod
    def get_timeseries_index_name(cls, datestamp: datetime.date | None = None) -> str:
        datestamp = datestamp or timezone.now().date()
        # TODO: configure format on cls, fallback to app-wide setting
        dateformat = getattr(
            settings, "ELASTICSEARCH_METRICS_DATE_FORMAT", DEFAULT_DATE_FORMAT
        )
        date_formatted = datetime.date.strftime(dateformat)
        return "{}_{}".format(cls._template_name, date_formatted)

    ######
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
        index = cls.get_timeseries_index_name(timestamp)
        instance.save(index=index)
        return instance

    def save(self, using=None, index=None, validate=True, **kwargs):
        """Same as `Document.save`, except will save into the index determined
        by the metric's timestamp field.
        """
        self.timestamp = self.timestamp or timezone.now()
        if not index:
            index = self.get_timeseries_index_name(date=self.timestamp)

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
        return index or cls.index_name_wildcard


class EventLog(TimeseriesRecord):
    timestamp: datetime.datetime
    event_label: str
    event_tags: list[str]


class PeriodicReport(TimeseriesRecord):
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
            _indexname_wildcard = _metric_type.index_name_wildcard
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
