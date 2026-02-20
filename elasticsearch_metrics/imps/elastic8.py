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
import collections
import dataclasses
import datetime
import logging

from django.apps import apps
from django.utils import timezone
from elasticsearch8.exceptions import NotFoundError
from elasticsearch8.dsl import Document, connections, IndexTemplate, mapped_field
from elasticsearch8.dsl._sync.document import IndexMeta

from elasticsearch_metrics import signals
from elasticsearch_metrics import exceptions
from elasticsearch_metrics.registry import timeseries_type_registry
from elasticsearch_metrics.protocols import ProtoTimeseriesImp
from elasticsearch_metrics.util import timeseries_naming

logger = logging.getLogger(__name__)


_DEFAULT_TIMEPATTERN_DEPTH = 2  # xxxx_xx


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

    @classmethod
    def record(cls, *, using=None, **kwargs):
        """Persist a record in Elasticsearch."""
        _instance = cls(**kwargs)
        _instance.save(using=using)
        return _instance


class TimeseriesRecord(DjelmeRecord):
    timestamp: datetime.datetime = mapped_field(default_factory=timezone.now)

    class Meta:
        abstract = True

    @classmethod
    def init(cls, index=None, using=None):
        """Create the index and populate the mappings in elasticsearch.

        overrides elasticsearch.Document.init
        """
        assert not cls.is_abstract
        # to init timeseries indexes, create only the template
        cls.sync_index_template(using=using)
        if index:  # unless specific index requested
            return super().init(index=index, using=using)

    @classmethod
    def format_timeseries_index_name(cls, timestamp: datetime.date) -> str:
        return timeseries_naming.format_index_name(
            prefix=cls.timeseries_name_prefix,
            recordtype=cls.__name__,
            timeparts=timeseries_naming.timeparts_from_date(
                timestamp, cls._timepattern_depth
            ),
        )

    @classmethod
    @property
    def timeseries_template(cls) -> IndexTemplate:
        return cls._index.as_template(
            template_name=cls.timeseries_template_name,
            pattern=cls.format_timeseries_index_pattern(),
        )

    @classmethod
    @property
    def timeseries_template_name(cls) -> str:
        return timeseries_naming.format_template_name(
            cls.timeseries_name_prefix, cls.__name__.lower()
        )

    @classmethod
    @property
    def timeseries_name_prefix(cls) -> str:
        return cls._get_meta_attr("timeseries_name_prefix") or cls.app_label

    @classmethod
    def format_timeseries_index_pattern(cls, timeparts: tuple[int, ...] = ()) -> str:
        return timeseries_naming.format_index_pattern(
            prefix=cls.timeseries_name_prefix,
            recordtype=cls.__name__,
            timeparts=timeparts,
        )

    @classmethod
    @property
    def _timepattern_depth(cls) -> int:
        return cls._get_meta_attr("timepattern_depth", _DEFAULT_TIMEPATTERN_DEPTH)

    @classmethod
    def _default_index(cls, index=None):
        """Overrides Document._default_index so that .search, .get, etc.
        use the metric's template pattern as the default index
        """
        assert not cls.is_abstract
        return index or cls.format_timeseries_index_pattern()

    @property
    def timeseries_index_name(self) -> str:
        assert self.timestamp is not None
        return self.format_timeseries_index_name(self.timestamp)

    def save(self, using=None, index=None, **kwargs):
        """save the record

        overrides `Document.save` to choose a timeseries index based on `self.timestamp`
        """
        if self.timestamp is None:
            self.timestamp = timezone.now()  # HACK: why default_factory no work?
        if index is None:
            index = self.timeseries_index_name
        signals.pre_save.send(self.__class__, instance=self, using=using, index=index)
        ret = super().save(using=using, index=index, **kwargs)
        signals.post_save.send(self.__class__, instance=self, using=using, index=index)
        return ret

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


class EventLog(TimeseriesRecord):
    # TODO: EventLog expiration

    class Meta:
        abstract = True


class CyclicReport(TimeseriesRecord):
    covers_from: datetime.date
    covers_until: datetime.date

    class Meta:
        abstract = True


@dataclasses.dataclass
class DjelmeElastic8Imp:
    """DjelmeElastic8Imp: the elastic8 implementation of djelme (for use by generic djelme code)"""

    imp_name: str
    imp_kwargs: dict[str, str]  # pass-thru to elasticsearch connection kwargs
    namespace_prefix: str = ""

    @property
    def elastic8_client(self):
        # assumes `connections.configure` was already called
        return connections.get_connection(self.imp_name)

    def setup_timeseries_indexes(self) -> None:
        for _metric_type in self._each_recordtype():
            # TODO: logger.info
            _metric_type.sync_index_template(using=self.elastic8_client)

    def teardown_timeseries_indexes(self) -> None:
        for _metric_type in self._each_recordtype():
            _indexname_wildcard = _metric_type.format_timeseries_index_pattern()
            _templatename = _metric_type._template_name
            self.elastic8_client.indices.delete(index=_indexname_wildcard)
            try:
                self.elastic8_client.indices.delete_template(_templatename)
            except NotFoundError:
                pass

    def _each_recordtype(self) -> collections.abc.Iterator[type]:
        for _type in timeseries_type_registry.each_recordtype(imp_name=self.imp_name):
            assert issubclass(_type, DjelmeRecord)
            yield _type


djelme_imp = DjelmeElastic8Imp  # for ProtoTimeseriesImpModule


def djelme_when_ready(  # for ProtoTimeseriesImpModule
    imps: collections.abc.Iterable[ProtoTimeseriesImp],
) -> None:
    connections.configure(**{_imp.imp_name: _imp.imp_kwargs for _imp in imps})
