"""elasticsearch_metrics.elastic8: store events and reports in elasticsearch 8

>>> from elasticsearch_metrics.imps.elastic8 import EventRecord
>>> class TheThingHappened(EventRecord):
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
    "EventRecord",
    "CyclicRecord",
)
import collections
import dataclasses
import datetime
import logging
import typing

import django
from django.conf import settings
from elasticsearch8.exceptions import NotFoundError
from elasticsearch8 import Elasticsearch as Elastic8Client
from elasticsearch8 import dsl as esdsl
from elasticsearch8.dsl._sync.document import IndexMeta

from elasticsearch_metrics import signals
from elasticsearch_metrics import exceptions
from elasticsearch_metrics.registry import djelme_registry
from elasticsearch_metrics.protocols import (
    ProtoDjelmeBackend,
    ProtoCountedUsage,
    ProtoDjelmeRecord,
)
from elasticsearch_metrics.util import timeseries_naming
from elasticsearch_metrics.util.unique_together import get_unique_id
from elasticsearch_metrics.util.anon_enough import opaque_sessionhour_id

logger = logging.getLogger(__name__)


_DEFAULT_TIMEDEPTH_SETTING = "DJELME_DEFAULT_TIMEDEPTH"
_DEFAULT_TIMEDEPTH = 3  # xxxx_xx_xx_ (daily)


###
# invasive hacky changes to elasticsearch8.dsl

# change default mapping for `str` annotations from Text to Keyword:
esdsl.document_base.DocumentOptions.type_annotation_map[str] = (esdsl.Keyword, {})


# changes to document metaclass behavior
class _DjelmeRecordtypeMetaclass(IndexMeta):
    """Metaclass for the base `DjelmeRecordtype` class.

    overrides behavior in elasticsearch-py's `IndexMeta` to allow
    additional config in a type's `class Meta`
    """

    Meta: type

    # override IndexMeta.__new__, to do a few things differently
    def __new__(mcls, name, bases, attrs):  # noqa: B902
        # save `class Meta` to un-remove it later
        _cls_meta = attrs.get("Meta") or type("Meta", (), {})
        # call IndexMeta.__new__
        _cls = super().__new__(mcls, name, bases, attrs)
        assert isinstance(_cls, _DjelmeRecordtypeMetaclass)
        # un-remove `class Meta` for later use
        if "Meta" in _cls.__dict__:
            for _attrname, _attrval in _cls_meta.__dict__.items():
                if not hasattr(_cls.Meta, _attrname):
                    setattr(_cls.Meta, _attrname, _attrval)
        else:  # guarantee non-inherited Meta
            _cls.Meta = _cls_meta
        # workaround elasticsearch.dsl inheriting only fields, not defaults
        for _b in bases:
            for _fieldname, _default in getattr(_b, "_defaults", {}).items():
                _cls._defaults.setdefault(_fieldname, _default)
        # and register concrete record types with the djelme registry
        if not _cls.is_abstract:
            assert issubclass(_cls, DjelmeRecordtype)
            _given_using = _cls._index._using
            _default_backend = (
                _given_using
                if isinstance(_given_using, str)
                and (_given_using in djelme_registry.all_backends)
                else ""
            )
            djelme_registry.register_recordtype(
                _cls,
                imp_module_name=__name__,
                app_label=_cls._get_meta_attr("app_label", None),
                default_backend=_default_backend,
            )
        return _cls

    def _get_meta_attr(self, attr_name: str, default: typing.Any = None) -> typing.Any:
        _meta = getattr(self, "Meta", None)
        return getattr(_meta, attr_name, default)

    @property
    def is_abstract(self) -> bool:
        return bool(self._get_meta_attr("abstract", False))

    @property
    def app_label(self) -> str | None:
        return djelme_registry.get_recordtype_app_label(self)


class DjelmeRecordtype(esdsl.Document, metaclass=_DjelmeRecordtypeMetaclass):
    """a subclass of elasticsearch8.dsl.Document, with conveniences

    >>> class MyAbstractRecord(DjelmeRecordtype):
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
    unique_id: str = esdsl.mapped_field(esdsl.Keyword(), default="")  # filled on save

    class Meta:
        abstract = True

    @classmethod
    def record(
        cls, *, using: str | None = None, **kwargs: typing.Any
    ) -> "typing.Self":  # typing.Self added in py 3.11 -- str annotation until 3.10 eol
        """Persist a record in Elasticsearch."""
        _instance = cls(**kwargs)
        _instance.save(using=using)
        return _instance

    @classmethod
    def check_djelme_setup(cls, using: str | None = None) -> bool:
        return bool(cls._index.get(using=using))

    @classmethod
    def _djelme_teardown(cls, es_client):
        cls._index.delete(using=es_client)

    @classmethod
    def _get_using(
        cls, using: str | Elastic8Client | None = None
    ) -> str | Elastic8Client:
        """get the elasticsearch8 connection name to use

        overrides elasticsearch8.Document._get_using to allow
        getting connection name from a djelme backend and default
        to the first configured backend that uses this imp module
        """
        _backend: ProtoDjelmeBackend | None = None
        if using in (None, "default"):
            _backend = djelme_registry.get_backend_for_recordtype(cls)
        elif isinstance(using, str) and (using in djelme_registry.all_backends):
            _backend = djelme_registry.get_backend(using)
        if _backend is not None:
            assert isinstance(_backend, DjelmeElastic8Backend)
            return _backend._elastic8dsl_connection_name
        return super()._get_using(using)

    def save(
        self,
        using: str | Elastic8Client | None = None,
        index: str | None = None,
        validate: bool = True,
        skip_empty: bool = True,
        return_doc_meta: bool = False,
        **kwargs: typing.Any,
    ) -> typing.Any:
        """save the record

        overrides `save` to populate document_id and send pre_save/post_save signals
        """
        self._populate_unique_id()
        signals.pre_save.send(self.__class__, instance=self, using=using, index=index)
        _saved = super().save(
            using=using, index=index, validate=validate, skip_empty=skip_empty, **kwargs
        )
        signals.post_save.send(self.__class__, instance=self, using=using, index=index)
        return _saved

    def _populate_unique_id(self) -> None:
        _unique_id = self._get_unique_id()
        assert _unique_id or not self.UNIQUE_TOGETHER_FIELDS
        self.unique_id = _unique_id or ""
        # make it unique by setting doc id in elasticsearch
        if _unique_id and not self.meta.id:
            self.meta.id = _unique_id

    def _get_unique_id(self) -> str | None:
        """
        Get a unique document id by hashing values of "unique together"
        fields for "ON CONFLICT UPDATE" behavior -- if the document
        already exists, it will be replaced rather than duplicated.
        Cannot detect/avoid conflicts this way, but that's ok.
        """
        if not self.UNIQUE_TOGETHER_FIELDS:
            return None
        return get_unique_id(
            (getattr(self, _field_name) for _field_name in self.UNIQUE_TOGETHER_FIELDS)
        )


class TimeseriesRecord(DjelmeRecordtype):
    timestamp: datetime.datetime = esdsl.mapped_field(
        default_factory=lambda: django.utils.timezone.now()
    )
    # the 'version' field type allows range queries on semver-like strings
    # that fit perfectly with "timeparts" representation of a UTC datetime
    # as a sequence of integers -- helps to avoid time zones and date math
    # (e.g. '2000' < '2000.5.10' < '2000.5.20.20.20' < '2000.11' < '2001')
    timestamp_parts: str = esdsl.mapped_field(esdsl.Version(), default="")

    class Meta:
        abstract = True

    ###
    # class methods

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
    def search(cls, *, index=None, **kwargs):
        return super().search(
            index=(index or cls.format_timeseries_index_pattern()),
            **kwargs,
        )

    @classmethod
    def search_timeseries_range(
        cls,
        from_when: tuple[int, ...] | datetime.date,
        until_when: tuple[int, ...] | datetime.date,
        **kwargs: typing.Any,
    ) -> typing.Any:
        _index_pattern = cls.format_timeseries_index_pattern_for_range(
            from_when, until_when
        )
        _timedepth = cls.get_timedepth()
        _timestamp_q = esdsl.query.Range(
            "timestamp_parts",
            gte=timeseries_naming.semverlike_timeparts(from_when, timedepth=_timedepth),
            lt=timeseries_naming.semverlike_timeparts(until_when, timedepth=_timedepth),
        )
        return cls.search(index=_index_pattern).filter(_timestamp_q)

    @classmethod
    def _djelme_teardown(cls, es8_client: Elastic8Client) -> None:
        _indexname_wildcard = cls.format_timeseries_index_pattern()
        _indices = es8_client.indices.get(index=_indexname_wildcard, features=",")
        for _index_name in _indices.keys():
            es8_client.indices.delete(index=_index_name)
        _templatename = cls.get_timeseries_template_name()
        try:
            es8_client.indices.delete_index_template(name=_templatename)
        except NotFoundError:
            pass

    @classmethod
    def format_timeseries_index_name(
        cls, timestamp: datetime.date | None = None
    ) -> str:
        return timeseries_naming.format_index_name_for_date(
            timestamp or django.utils.timezone.now(),
            prefix=cls.get_timeseries_name_prefix(),
            recordtype=cls.get_timeseries_recordtype_name(),
            timedepth=cls.get_timedepth(),
        )

    @classmethod
    def get_timeseries_template(cls) -> esdsl.ComposableIndexTemplate:
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
        _recordtype_name = cls._get_meta_attr(
            "timeseries_recordtype_name", cls.__name__
        )
        assert isinstance(_recordtype_name, str)
        return _recordtype_name

    @classmethod
    def get_timeseries_name_prefix(cls) -> str:
        _name_prefix = cls._get_meta_attr("timeseries_name_prefix") or cls.app_label
        assert isinstance(_name_prefix, str)
        return _name_prefix

    @classmethod
    def format_timeseries_index_pattern(cls, timeparts: tuple[int, ...] = ()) -> str:
        return timeseries_naming.format_index_pattern(
            prefix=cls.get_timeseries_name_prefix(),
            recordtype=cls.get_timeseries_recordtype_name(),
            timeparts=timeparts,
            max_timedepth=cls.get_timedepth(),
        )

    @classmethod
    def format_timeseries_index_pattern_for_range(
        cls,
        from_when: tuple[int, ...] | datetime.date,
        until_when: tuple[int, ...] | datetime.date,
    ) -> str:
        return timeseries_naming.format_index_pattern_for_range(
            cls.get_timeseries_name_prefix(),
            cls.get_timeseries_recordtype_name(),
            from_when,
            until_when,
            timedepth=cls.get_timedepth(),
        )

    @classmethod
    def get_timedepth(cls) -> int:
        _default_timedepth = getattr(
            settings, _DEFAULT_TIMEDEPTH_SETTING, _DEFAULT_TIMEDEPTH
        )
        _timedepth = cls._get_meta_attr("timedepth", _default_timedepth)
        assert isinstance(_timedepth, int)
        return _timedepth

    @classmethod
    def _default_index(cls, index=None):
        """Overrides Document._default_index so that .search, .get, etc.
        use the metric's template pattern as the default index
        """
        assert not cls.is_abstract
        return index or cls.format_timeseries_index_pattern()

    @classmethod
    def sync_index_template(cls, using=None):  # -> ComposableIndexTemplate:
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
    def check_djelme_setup(cls, using: str | Elastic8Client | None = None) -> bool:
        """Check if class is in sync with index template in Elasticsearch.

        :raise: IndexTemplateNotFoundError if index template does not exist.
        :raise: IndexTemplateOutOfSyncError if mappings, settings, or index patterns
            are out of sync.
        :return: True if index template exsits and mappings, settings, and index patterns
            are in sync.
        """
        super().check_djelme_setup()
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

    ###
    # instance methods

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.timestamp_parts = self._build_timestamp_parts()

    def _build_timestamp_parts(self) -> str:
        return timeseries_naming.full_semverlike_timeparts(self.timestamp)

    def djelme_index_name(self) -> str:
        assert self.timestamp is not None
        return self.format_timeseries_index_name(self.timestamp)

    def save(
        self,
        using: str | Elastic8Client | None = None,
        index: str | None = None,
        validate: bool = True,
        skip_empty: bool = True,
        return_doc_meta: bool = False,
        **kwargs: typing.Any,
    ) -> typing.Any:
        """save the record

        overrides `save` to choose a timeseries index based on `self.timestamp`
        """
        assert self.timestamp is not None
        if index is None:
            index = self.djelme_index_name()
        ret = super().save(using=using, index=index, **kwargs)
        return ret


# TODO: EventRecord expiration
# class EventRecord(TimeseriesRecord, ProtoExpirableRecord?):
class EventRecord(TimeseriesRecord):

    class Meta:
        abstract = True


# class CountedUsageRecord(EventRecord, ProtoCountedUsage):
class CountedUsageRecord(EventRecord):
    """
    fields correspond to defined terms from COUNTER
    https://cop5.projectcounter.org/en/5.0.2/appendices/a-glossary-of-terms.html
    """

    # for ProtoCountedUsage:
    platform_iri: str = esdsl.mapped_field(required=True, default="")
    database_iri: str = esdsl.mapped_field(required=True, default="")
    item_iri: str = esdsl.mapped_field(required=True, default="")
    sessionhour_id: str = esdsl.mapped_field(esdsl.Keyword(), default="")
    within_iris: list[str] = esdsl.mapped_field(esdsl.Keyword(), default_factory=list)

    class Meta:
        abstract = True

    @classmethod
    def record(
        cls,
        *,
        # each usage record needs a sessionhour_id -- for migrating old data, can set explicitly...
        sessionhour_id: str = "",
        # ...but when saving new data, give either the dirty identifying strings:
        user_id: str = "",
        session_id: str = "",
        request_host: str = "",
        request_useragent: str = "",
        # ...or a django request to infer from
        django_request: django.http.HttpRequest | None = None,
        # additional kwargs presumed to give field values
        **kwargs: typing.Any,
    ) -> "typing.Self":  # typing.Self added in py 3.11 -- str annotation until 3.10 eol
        """CountedUsageRecord.record(...): construct and save a record"""
        _useragent = (
            request_useragent
            if (request_useragent or (django_request is None))
            else django_request.META.get("HTTP_USER_AGENT", "")
        )
        _host = (
            request_host
            if (request_host or (django_request is None))
            else django_request.get_host()
        )
        _sessionhour_id = kwargs.pop("sessionhour_id", None) or opaque_sessionhour_id(
            client_session_id=session_id,
            user_id=user_id,
            request_host=_useragent,
            request_useragent=_host,
        )
        _new_record = super().record(**kwargs, sessionhour_id=_sessionhour_id)
        assert isinstance(_new_record, cls)
        return _new_record


class CyclicRecord(TimeseriesRecord):
    """CyclicRecord: for recording a measurement on a periodic basis"""

    covers_from: datetime.datetime  # type: ignore[misc]
    covers_before: datetime.datetime  # type: ignore[misc]

    class Meta:
        abstract = True


@dataclasses.dataclass
class DjelmeElastic8Backend:
    """DjelmeElastic8Backend: elastic8 backend for djelme (for use by generic djelme code)"""

    backend_name: str
    imp_kwargs: dict[str, str]  # pass-thru to elasticsearch connection kwargs
    namespace_prefix: str = ""

    def djelme_backend_name(self) -> str:  # for ProtoDjelmeBackend
        return self.backend_name

    def djelme_imp_kwargs(self) -> dict[str, str]:  # for ProtoDjelmeBackend
        return self.imp_kwargs

    @property
    def elastic8_client(self) -> Elastic8Client:
        # assumes `connections.configure` was already called
        return esdsl.connections.get_connection(self._elastic8dsl_connection_name)

    @property
    def _elastic8dsl_connection_name(self) -> str:
        return self.backend_name

    @property
    def _elastic8dsl_connection_kwargs(self) -> dict[str, typing.Any]:
        return self.imp_kwargs

    def djelme_setup(self, recordtypes: collections.abc.Iterable[type]) -> None:
        # for ProtoDjelmeBackend
        for _recordtype in recordtypes:
            # TODO: logger.info
            assert issubclass(_recordtype, DjelmeRecordtype)
            _recordtype.init(using=self._elastic8dsl_connection_name)

    def djelme_teardown(self, recordtypes: collections.abc.Iterable[type]) -> None:
        # for ProtoDjelmeBackend
        for _recordtype in recordtypes:
            assert issubclass(_recordtype, DjelmeRecordtype)
            _recordtype._djelme_teardown(self.elastic8_client)


if __debug__ and typing.TYPE_CHECKING:
    # for static type-checking; verify intent
    _: type[ProtoCountedUsage] = CountedUsageRecord
    __: type[ProtoDjelmeBackend] = DjelmeElastic8Backend
    ___: type[ProtoDjelmeRecord] = DjelmeRecordtype

###
# names expected by ProtoDjelmeImp

djelme_backend = DjelmeElastic8Backend  # for ProtoDjelmeImp


def djelme_when_ready(  # for ProtoDjelmeImp
    backends: collections.abc.Iterable[ProtoDjelmeBackend],
) -> None:
    esdsl.connections.configure(
        **{
            _backend._elastic8dsl_connection_name: _backend._elastic8dsl_connection_kwargs
            for _backend in backends
            if isinstance(_backend, DjelmeElastic8Backend)
        }
    )
