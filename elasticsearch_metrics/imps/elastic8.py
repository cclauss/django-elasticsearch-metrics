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
    'TimeseriesRecord',
    'EventLog',
    'PeriodicReport',
)
from collections import ChainMap
import dataclasses
import datetime
import logging
import typing

from django.conf import settings
from django.utils import timezone
from elasticsearch8.exceptions import NotFoundError
from elasticsearch8.dsl import Document, connections
from elasticsearch8.dsl.document import MetaField
from elasticsearch8.dsl.index import Index

from elasticsearch_metrics import signals
from elasticsearch_metrics import exceptions
from elasticsearch_metrics.registry import registry

# Fields should be imported from this module
from elasticsearch_metrics.field import *  # noqa: F40
from elasticsearch_metrics.field import Date

DEFAULT_DATE_FORMAT = "%Y.%m.%d"

logger = logging.getLogger(__name__)


# TODO: do index inheritance without metaclasses
# class IndexInheritanceMeta(IndexMeta):
#     # override elasticsearch8.document.IndexMeta.construct_index
#     # so Index attrs are inherited
#     # and each subtype gets their own index (`opts` is never None)
#     @classmethod
#     def construct_index(cls, opts, bases):
#         parent_configs = [
#             base._index.to_dict() for base in bases if hasattr(base, "_index")
#         ]
#         chained_opts = (
#             ChainMap(ReadonlyAttrMap(opts), *parent_configs)
#             if opts
#             else ChainMap(*parent_configs)
#         )
#         # since chained_opts is not None, IndexMeta.construct_index won't reuse the index from a parent type
#         return super().construct_index(chained_opts, bases)
# 

# class TimeseriesIndexMeta(IndexMeta):
#     """Metaclass for the base `TimeseriesRecord` class."""
# 
#     def __new__(mcls, name, bases, attrs):  # noqa: B902
#         new_cls = super().__new__(mcls, name, bases, attrs)
# 
#         meta = attrs.get("Meta", None)
#         module = attrs.get("__module__")
# 
#         # Also ensure initialization is only performed for subclasses of TimeseriesRecord
#         # (excluding TimeseriesRecord class itself).
#         if isinstance(new_cls, TimeseriesIndexMeta) 
#         if any(
#             isinstance(b, TimeseriesIndexMeta) and (b is not BaseTimeseriesDoc)
#             for b in bases
#         ):
#             return new_cls
# 
# 
#     def _register_timeseries_indexset(self, ...):
#         template_name = getattr(meta, "template_name", None)
#         template = getattr(meta, "template", None)
#         abstract = getattr(meta, "abstract", False)
# 
#         app_label = getattr(meta, "app_label", None)
#         # Look for an application configuration to attach the model to.
#         app_config = apps.get_containing_app_config(module)
#         if app_label is None:
#             if app_config is None:
#                 if not abstract:
#                     raise RuntimeError(
#                         "TimeseriesRecord class %s.%s doesn't declare an explicit "
#                         "app_label and isn't in an application in "
#                         "INSTALLED_APPS." % (module, name)
#                     )
#             else:
#                 app_label = app_config.label
# 
#         if not template_name or not template:
#             metric_name = new_cls.__name__.lower()
#             # If template_name not specified in class Meta,
#             # compute it as <app label>_<lowercased class name>
#             if not template_name:
#                 template_name = "{}_{}".format(app_label, metric_name)
#             # template is <app label>_<lowercased class name>-*
#             template = template or "{}_{}_*".format(app_label, metric_name)
# 
#         new_cls._template_name = template_name
#         new_cls._template_pattern = template
#         # Abstract base metrics can't be instantiated and don't appear in
#         # the list of metrics for an app.
#         if not abstract:
#             registry.register_recordtype(app_label, new_cls)
#         return new_cls
# 
#     # Override IndexMeta.construct_index so that
#     # a new Index is created for every metric class
#     # and Index attrs are inherited
#     @classmethod
#     def construct_index(cls, opts, bases):
#         parent_configs = [
#             base._index.to_dict() for base in bases if hasattr(base, "_index")
#         ]
#         if opts:
#             index_config = ChainMap(ReadonlyAttrMap(opts), *parent_configs)
#         else:
#             index_config = ChainMap(*parent_configs)
# 
#         i = Index(
#             index_config.get("name", "*"),
#             using=index_config.get("using", "default"),
#         )
#         i.settings(**index_config.get("settings", {}))
#         i.aliases(**index_config.get("aliases", {}))
#         for a in index_config.get("analyzers", ()):
#             i.analyzer(a)
#         return i
# 
# 

class TimeseriesRecord(Document):
    """Base document
    """

    timestamp = Date(doc_values=True, required=True)

    class Meta:
        source = MetaField(enabled=False)
        abstract = True

    def __init_subclass__(cls, **kwargs):
        # (sidenote: simpler? way to register subclasses, compared to metaclasses)
        super().__init_subclass__(**kwargs)
        # TODO: register cls with metrics registry
        if not cls.get_meta_setting('abstract'):
            registry.register_recordtype(cls.get_app_label(), cls)

    @classmethod
    def init(cls, index=None, using=None):
        """Create the index and populate the mappings in elasticsearch."""
        cls.sync_index_template(using=using)
        return super().init(index=index or cls.get_timeseries_index_name(), using=using)

    @classmethod
    def get_timeseries_index_template(cls):
        """Return an `IndexTemplate <elasticsearch_dsl.IndexTemplate>` for this metric."""
        return cls._index.as_template(
            template_name=cls._template_name, pattern=cls._template_pattern
        )

    @classmethod
    def get_template_pattern(cls) -> str:
        return f"{cls.get_template_name()}_*"

    @classmethod
    def get_template_pattern(cls) -> str:
        if not template_name:
            metric_name = new_cls.__name__.lower()
            # If template_name not specified in class Meta,
            # compute it as <app label>_<lowercased class name>
            template_name = f"{app_label}_{metric_name}"

        new_cls._template_name = template_name

    @classmethod
    def get_app_label(cls) -> str:
        _app_label = self.get_meta_setting("app_label")
        if _app_label is None:
            # Look for an application configuration to attach the model to.
            app_config = apps.get_containing_app_config(module)
            if app_config is None:
                if not self.get_meta_setting("abstract"):
                    raise RuntimeError(
                        "Metric class %s.%s doesn't declare an explicit "
                        "app_label and isn't in an application in "
                        "INSTALLED_APPS." % (module, name)
                    )
            else:
                _app_label = app_config.label
        assert isinstance(_app_label, str)
        return _app_label

    @classmethod
    def get_meta_setting(cls, setting_name: str) -> typing.Any:
        _meta_settings_cls = getattr(cls, 'Meta', None)
        return getattr(_meta_settings_cls, setting_name, None)

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
    def get_timeseries_index_name(cls, datestamp: datetime.date | None = None) -> str:
        datestamp = datestamp or timezone.now().date()
        # TODO: configure format on cls, fallback to app-wide setting
        dateformat = getattr(
            settings, "ELASTICSEARCH_METRICS_DATE_FORMAT", DEFAULT_DATE_FORMAT
        )
        date_formatted = date.strftime(dateformat)
        return "{}_{}".format(cls._template_name, date_formatted)

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
        return index or cls._template_pattern


class EventLog(TimeseriesRecord):
    timestamp: datetime.datetime
    event_label: str
    event_tags: list[str]


class PeriodicReport(TimeseriesRecord):
    timestamp: datetime.datetime
    report_label: str
    report_coverage: ...  # timespan


@dataclasses.dataclass
class DjelmeElastic8Imp(ProtoTimeseriesImp):
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
        for _metric_type in self._each_metric_type():
            # TODO: logger.info
            _metric_type.sync_index_template(using=self.elastic6_client)

    def teardown_timeseries_indexes(self) -> None:
        for _metric_type in self._each_metric_type():
            _indexname_wildcard = _metric_type._template_pattern
            _templatename = _metric_type._template_name
            self.elastic6_client.indices.delete(index=_indexname_wildcard)
            try:
                self.elastic6_client.indices.delete_template(_templatename)
            except NotFoundError:
                pass

    def _each_metric_type(self) -> Iterator[type[Metric]]:
        for _metric in registry.each_recordtype(imp_name=self.imp_name):
            assert issubclass(_metric, Metric)
            yield _metric


djelme_imp_from_config = DjelmeElastic8Imp  # for ProtoDjelmetricsImpModule
