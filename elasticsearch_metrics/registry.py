import collections
import dataclasses
import functools
import importlib

from django.apps import apps

from elasticsearch_metrics.protocols import (
    ProtoTimeseriesImp,
    ProtoTimeseriesRecord,
    ProtoTimeseriesImpModule,
)


@dataclasses.dataclass
class TimeseriesTypeRegistry:
    """TimeseriesTypeRegistry keeping track of TimeseriesRecord classes (similar to how
    django.apps.registry.Apps keeps track of Model classes).

    Every time a TimeseriesRecord subtype is defined, TimeseriesRecord.__init_subclass__
    calls timeseries_type_registry.register which creates an entry in all_recordtypes.
    """

    # mapping of app labels => record-type names => record classes
    all_recordtypes: dict[str, dict[str, type]] = dataclasses.field(
        default_factory=lambda: collections.defaultdict(dict),
    )

    # mapping of imp names => (imp module path, imp config)
    configured_imps: dict[str, tuple[str, dict[str, str]]] = dataclasses.field(
        default_factory=dict,
    )

    ###
    # `register` methods: for adding items to the registry

    def register_recordtype(
        self, app_label: str, record_cls: type[ProtoTimeseriesRecord]
    ) -> None:
        """Add a record type to the registry."""
        app_recordtypes = self.all_recordtypes[app_label]
        recordtype_name = record_cls.__name__.lower()
        if recordtype_name in app_recordtypes:
            # Raise an error for conflicting metrics (same behavior as apps.register_model)
            raise RuntimeError(
                "Conflicting '{}' metrics in application '{}': {} and {}.".format(
                    recordtype_name,
                    app_label,
                    app_recordtypes[recordtype_name],
                    record_cls,
                )
            )
        app_recordtypes[recordtype_name] = record_cls

    def register_imp(
        self, imp_name: str, imp_module_path: str, imp_kwargs: dict[str, str]
    ) -> None:
        if imp_name in self.configured_imps:
            raise RuntimeError(f"duplicate imps named {imp_name!r}")
        self.configured_imps[imp_name] = (imp_module_path, imp_kwargs)

    ###
    # `get` methods: for accessing specific items in the registry

    def get_recordtype(
        self, app_label: str, recordtype_name: str | None = None
    ) -> type:
        """Return the metric matching the given app_label and model_name.

        As a shortcut, app_label may be in the form <app_label>.<model_name>.

        model_name is case-insensitive.

        Raise LookupError if no application exists with this label, or no
        metric exists with this name in the application. Raise ValueError if
        called with a single argument that doesn't contain exactly one dot.
        """
        apps.check_apps_ready()

        if recordtype_name is None:
            app_label, recordtype_name = app_label.split(".")

        app_recordtypes = self._get_recordtypes_for_app(app_label)
        try:
            return app_recordtypes[recordtype_name.lower()]
        except KeyError as e:
            raise LookupError(
                "App '{}' doesn't have a '{}' metric.".format(
                    app_label, recordtype_name
                )
            ) from e

    def get_imp_module(self, imp_name: str) -> ProtoTimeseriesImp:
        try:
            _imp_module_path, _ = self.configured_imps[imp_name]
        except KeyError as _e:
            raise LookupError(f"unknown imp {imp_name!r}") from _e
        return _import_imp_module(_imp_module_path)

    def get_imp(self, imp_name: str, namespace_prefix: str = "") -> ProtoTimeseriesImp:
        try:
            _imp_module_path, _imp_kwargs = self.configured_imps[imp_name]
        except KeyError as _e:
            raise LookupError(f"unknown imp {imp_name!r}") from _e
        _mod = _import_imp_module(_imp_module_path)
        return _mod.djelme_imp(imp_name, _imp_kwargs, namespace_prefix)

    ###
    # `each` methods: for iterating over each registered

    def each_recordtype(
        self,
        app_label: str = "",
        imp_name: str | None = None,
    ) -> collections.abc.Iterator[type]:
        """Iterate registered metric classes, optionally filtered on an app_label and/or imp_name."""
        apps.check_apps_ready()
        _imp_module = None if imp_name is None else self.get_imp_module(imp_name)
        app_labels = [app_label] if app_label else self.all_recordtypes.keys()
        for app_label in app_labels:
            for _recordtype in self._get_recordtypes_for_app(app_label).values():
                if (_imp_module is None) or self._is_type_downstream_of_module(
                    _recordtype, _imp_module.__name__
                ):
                    yield _recordtype

    def each_imp(self) -> collections.abc.Iterator[ProtoTimeseriesImp]:
        for _imp_name in self.configured_imps.keys():
            yield self.get_imp(_imp_name)

    ###
    # callback methods
    def on_app_ready(self) -> None:
        for _imp_module_path, _imp_names in self._imps_by_module().items():
            _imp_module = _import_imp_module(_imp_module_path)
            _imp_module.djelme_when_ready(map(self.get_imp, _imp_names))

    ###
    # private methods

    def _get_recordtypes_for_app(self, app_label: str) -> dict[str, type]:
        if app_label not in self.all_recordtypes:
            raise LookupError(
                "No recordtypes found in app with label '{}'.".format(app_label)
            )
        return self.all_recordtypes[app_label]

    def _is_type_downstream_of_module(self, given_type: type, module_name: str) -> bool:
        _upstream_modules = (_cls.__module__ for _cls in given_type.__mro__)
        return module_name in _upstream_modules

    def _imps_by_module(self) -> dict[str, list[str]]:
        _by_module = collections.defaultdict(list)
        for _imp_name, (_imp_module_path, _) in self.configured_imps.items():
            _by_module[_imp_module_path].append(_imp_name)
        return _by_module


@functools.lru_cache
def _import_imp_module(imp_module_path: str) -> ProtoTimeseriesImpModule:
    try:
        _imp_module = importlib.import_module(imp_module_path)
    except ImportError as _error:
        raise ValueError(f"could not import {imp_module_path!r}") from _error
    assert isinstance(_imp_module, ProtoTimeseriesImpModule)
    return _imp_module


###
# module public api

timeseries_type_registry = TimeseriesTypeRegistry()
registry = timeseries_type_registry  # convenience?
