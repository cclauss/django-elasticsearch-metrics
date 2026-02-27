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
import typing

from django.utils import timezone
from elasticsearch8.exceptions import NotFoundError
from elasticsearch8 import Elasticsearch as Elastic8Client
from elasticsearch8.dsl import (
    Document,
    connections,
    ComposableIndexTemplate,
    mapped_field,
    Keyword,
)
from elasticsearch8.dsl._sync.document import IndexMeta

from elasticsearch_metrics import signals
from elasticsearch_metrics import exceptions
from elasticsearch_metrics.registry import djelme_registry
from elasticsearch_metrics.protocols import ProtoTimeseriesImp
from elasticsearch_metrics.util import timeseries_naming
from elasticsearch_metrics.util.anon_enough import opaque_key

logger = logging.getLogger(__name__)


_DEFAULT_TIMEPATTERN_DEPTH = 2  # xxxx_xx


class _DjelmeRecordMeta(IndexMeta):
    """Metaclass for the base `DjelmeRecord` class.

    overrides behavior in elasticsearch-py's `IndexMeta` to allow
    additional config in a type's `class Meta`
    """

    def __new__(mcls, name, bases, attrs):  # noqa: B902
        # override IndexMeta.__new__, which removes `class Meta`
        _doc_type_meta = attrs.get("Meta") or type("Meta", (), {})
        _cls = super().__new__(mcls, name, bases, attrs)
        if "Meta" in _cls.__dict__:
            for _attrname, _attrval in _doc_type_meta.__dict__.items():
                if not hasattr(_cls.Meta, _attrname):
                    setattr(_cls.Meta, _attrname, _attrval)
        else:
            _cls.Meta = _doc_type_meta
        # register non-abstract subtypes
        if not _cls.is_abstract:
            djelme_registry.register_recordtype(
                _cls, app_label=_cls._get_meta_attr("app_label", None)
            )
        return _cls

    def _get_meta_attr(self, attr_name: str, default=None):
        _meta = getattr(self, "Meta", None)
        return getattr(_meta, attr_name, default)

    @property
    def is_abstract(self) -> bool:
        return self._get_meta_attr("abstract", False)

    @property
    def app_label(self) -> str | None:
        return djelme_registry.get_recordtype_app_label(self)


class DjelmeRecord(Document, metaclass=_DjelmeRecordMeta):
    """a subclass of elasticsearch8.dsl.Document, with conveniences

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

    >>> class MyConcreteRecord(MyAbstractRecord):
    ...     bar: int
    ...     class Meta:
    ...         bleg = 7
    >>> MyConcreteRecord.Meta.bleg
    7
    >>> MyConcreteRecord.is_abstract
    False
    >>> MyConcreteRecord.app_label
    'elasticsearch_metrics'
    """

    UNIQUE_TOGETHER_FIELDS: typing.ClassVar[collections.abc.Iterable[str]] = ()
    unique_id: str = Keyword()

    class Meta:
        abstract = True

    @classmethod
    def record(cls, *, using=None, **kwargs):
        """Persist a record in Elasticsearch."""
        _instance = cls(**kwargs)
        _instance.save(using=using)
        return _instance

    @classmethod
    def _get_using(cls, using: str | Elastic8Client = None) -> str | Elastic8Client:
        """get the elasticsearch8 connection name to use

        overrides elasticsearch8.Document._get_using to allow
        getting connection name from a djelme imp and default
        to the first configured imp that uses this imp module
        """
        _imp = None
        if using in (None, "default"):
            _each_imp = djelme_registry.each_imp(imp_module_path=__name__)
            _imp = next(_each_imp, None)
        elif isinstance(using, str) and (using in djelme_registry.configured_imps):
            _imp = djelme_registry.get_imp(using)
        if _imp is not None:
            assert isinstance(_imp, DjelmeElastic8Imp)
            return _imp._elastic8dsl_connection_name
        return super()._get_using(using)

    def save(self, *, using=None, index=None, **kwargs):
        """save the record

        overrides `save` to populate document_id and send pre_save/post_save signals
        """
        self._populate_unique_id()
        signals.pre_save.send(self.__class__, instance=self, using=using, index=index)
        _saved = super().save(using=using, index=index, **kwargs)
        signals.post_save.send(self.__class__, instance=self, using=using, index=index)
        return _saved

    def _populate_unique_id(self) -> None:
        _unique_id = self._get_unique_id()
        assert _unique_id or not self.UNIQUE_TOGETHER_FIELDS
        if self.unique_id and (self.unique_id != _unique_id):
            raise RuntimeError("unique_id set to a wrong value! prefer not setting it")
        self.unique_id = _unique_id
        if _unique_id and not self.meta.id:
            self.meta.id = _unique_id  # set doc id, but don't error if it's already set

    def _get_unique_id(self) -> str:
        """
        Get a unique document id by hashing values of "unique together"
        fields for "ON CONFLICT UPDATE" behavior -- if the document
        already exists, it will be replaced rather than duplicated.
        Cannot detect/avoid conflicts this way, but that's ok.
        """
        _key_values = []
        for _field_name in self.UNIQUE_TOGETHER_FIELDS:
            _field_value = getattr(self, _field_name)
            if not _field_value or (
                isinstance(_field_value, collections.abc.Iterable)
                and not isinstance(_field_value, str)
            ):
                raise ValueError(
                    f"expected non-empty str-able value in field {_field_name!r}; got {_field_value!r}"
                )
            _key_values.append(_field_value)
        return opaque_key(_key_values) if _key_values else ""


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
        return super().init(
            index=(index or cls.format_timeseries_index_name()),
            using=cls._get_using(using),
        )

    @classmethod
    def format_timeseries_index_name(
        cls, timestamp: datetime.date | None = None
    ) -> str:
        _timeparts = timeseries_naming.timeparts_from_date(
            timestamp or timezone.now(),
            cls.get_timepattern_depth(),
        )
        return timeseries_naming.format_index_name(
            prefix=cls.get_timeseries_name_prefix(),
            recordtype=cls.get_timeseries_recordtype_name(),
            timeparts=_timeparts,
        )

    @classmethod
    def get_timeseries_template(cls) -> ComposableIndexTemplate:
        return cls._index.as_composable_template(
            template_name=cls.get_timeseries_template_name(),
            pattern=cls.format_timeseries_index_pattern(),
        )

    @classmethod
    def get_timeseries_template_name(cls) -> str:
        return timeseries_naming.format_template_name(
            cls.get_timeseries_name_prefix(), cls.get_timeseries_recordtype_name()
        )

    @classmethod
    def get_timeseries_recordtype_name(cls) -> str:
        return cls._get_meta_attr("timeseries_recordtype_name", cls.__name__)

    @classmethod
    def get_timeseries_name_prefix(cls) -> str:
        return cls._get_meta_attr("timeseries_name_prefix") or cls.app_label

    @classmethod
    def format_timeseries_index_pattern(cls, timeparts: tuple[int, ...] = ()) -> str:
        return timeseries_naming.format_index_pattern(
            prefix=cls.get_timeseries_name_prefix(),
            recordtype=cls.get_timeseries_recordtype_name(),
            timeparts=timeparts,
        )

    @classmethod
    def get_timepattern_depth(cls) -> int:
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

    def save(self, *, index=None, **kwargs):
        """save the record

        overrides `save` to choose a timeseries index based on `self.timestamp`
        """
        if self.timestamp is None:
            self.timestamp = timezone.now()  # HACK: why default_factory no work?
        if index is None:
            index = self.timeseries_index_name
        ret = super().save(index=index, **kwargs)
        return ret

    @classmethod
    def sync_index_template(cls, using=None) -> ComposableIndexTemplate:
        """Sync the index template for this metric in Elasticsearch."""
        _template = cls.get_timeseries_template()
        signals.pre_index_template_create.send(
            cls, index_template=_template, using=using
        )
        _template.save(using=cls._get_using(using))
        signals.post_index_template_create.send(
            cls, index_template=_template, using=using
        )
        return _template

    @classmethod
    def check_index_template(cls, using=None):
        """Check if class is in sync with index template in Elasticsearch.

        :raise: IndexTemplateNotFoundError if index template does not exist.
        :raise: IndexTemplateOutOfSyncError if mappings, settings, or index patterns
            are out of sync.
        :return: True if index template exsits and mappings, settings, and index patterns
            are in sync.
        """
        client = cls._get_connection(using)
        try:
            _template_response = client.indices.get_index_template(
                name=cls.get_timeseries_template_name()
            )
        except NotFoundError as client_error:
            raise exceptions.IndexTemplateNotFoundError(
                f"{cls.get_timeseries_template_name()} does not exist for {cls.__name__}",
                client_error=client_error,
            ) from client_error
        else:
            (_current_index_dict,) = _template_response["index_templates"]
            assert _current_index_dict["name"] == cls.get_timeseries_template_name()
            _current_template = _current_index_dict["index_template"]["template"]
            _current_patterns = _current_index_dict["index_template"]["index_patterns"]
            _current_mappings = _current_template["mappings"]
            _current_settings = _current_template.get("settings", {}).get("index")
            _expected_template_dict = cls.get_timeseries_template().to_dict()
            _expected_template = _expected_template_dict["template"]
            _expected_patterns = _expected_template_dict["index_patterns"]
            _expected_mappings = _expected_template["mappings"]
            _expected_settings = _expected_template.get("settings")
            if _expected_settings:
                # ES automatically casts integer settings to string
                for _name, _val in list(_expected_settings.items()):
                    if isinstance(_val, int):
                        _expected_settings[_name] = str(_val)
            mappings_in_sync = _current_mappings == _expected_mappings
            settings_in_sync = _current_settings == _expected_settings
            patterns_in_sync = _current_patterns == _expected_patterns

            if not all([mappings_in_sync, settings_in_sync, patterns_in_sync]):
                word_map = {
                    "mappings": mappings_in_sync,
                    "patterns": patterns_in_sync,
                    "settings": settings_in_sync,
                }
                out_of_sync = ", ".join(
                    [key for key, value in word_map.items() if not value]
                )
                raise exceptions.IndexTemplateOutOfSyncError(
                    f"{cls.get_timeseries_template_name()} is out of sync with {cls.__name__} ({out_of_sync})",
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
    covers_before: datetime.date

    class Meta:
        abstract = True


@dataclasses.dataclass
class DjelmeElastic8Imp:
    """DjelmeElastic8Imp: the elastic8 implementation of djelme (for use by generic djelme code)"""

    imp_name: str
    imp_kwargs: dict[str, str]  # pass-thru to elasticsearch connection kwargs
    namespace_prefix: str = ""

    @property
    def elastic8_client(self) -> Elastic8Client:
        # assumes `connections.configure` was already called
        return connections.get_connection(self._elastic8dsl_connection_name)

    @property
    def _elastic8dsl_connection_name(self) -> str:
        return self.imp_name

    @property
    def _elastic8dsl_connection_kwargs(self) -> dict:
        return self.imp_kwargs

    def setup_timeseries_indexes(self) -> None:
        for _recordtype in self._each_recordtype():
            # TODO: logger.info
            _recordtype.sync_index_template(using=self.elastic8_client)

    def teardown_timeseries_indexes(self) -> None:
        for _recordtype in self._each_recordtype():
            _indexname_wildcard = _recordtype.format_timeseries_index_pattern()
            _indices = self.elastic8_client.indices.get(
                index=_indexname_wildcard, features=","
            )
            for _index_name in _indices.keys():
                self.elastic8_client.indices.delete(index=_index_name)
            _templatename = _recordtype.get_timeseries_template_name()
            try:
                self.elastic8_client.indices.delete_index_template(name=_templatename)
            except NotFoundError:
                pass

    def _each_recordtype(self) -> collections.abc.Iterator[type[DjelmeRecord]]:
        for _type in djelme_registry.each_recordtype(imp_name=self.imp_name):
            assert issubclass(_type, DjelmeRecord)
            yield _type


djelme_imp = DjelmeElastic8Imp  # for ProtoTimeseriesImpModule


def djelme_when_ready(  # for ProtoTimeseriesImpModule
    imps: collections.abc.Iterable[ProtoTimeseriesImp],
) -> None:
    assert all(isinstance(_imp, DjelmeElastic8Imp) for _imp in imps)
    connections.configure(
        **{
            _imp._elastic8dsl_connection_name: _imp._elastic8dsl_connection_kwargs
            for _imp in imps
        }
    )
