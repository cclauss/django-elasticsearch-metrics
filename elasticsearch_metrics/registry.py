import collections
import dataclasses
import importlib

from django.apps import apps

from elasticsearch_metrics.protocols import (
    ProtoDjelmeBackend,
    ProtoTimeseriesRecord,
    ProtoDjelmeImp,
)


@dataclasses.dataclass
class TimeseriesTypeRegistry:
    """TimeseriesTypeRegistry keeping track of TimeseriesRecord classes (similar to how
    django.apps.registry.Apps keeps track of Model classes).

    Every time a TimeseriesRecord subtype is defined, TimeseriesRecord.__init_subclass__
    calls djelme_registry.register which creates an entry in all_recordtypes.
    """

    # nested mapping of app labels => record-type names => record classes
    all_recordtypes: dict[str, dict[str, type]] = dataclasses.field(
        default_factory=lambda: collections.defaultdict(dict),
    )

    # nested mapping of backend_name => imp_module_path => imp config dictionary
    # (note, only one imp module allowed per backend (for now))
    all_backends: dict[str, tuple[str, dict[str, str]]] = dataclasses.field(
        default_factory=dict,
    )

    ###
    # `register` methods: for adding items to the registry

    def register_recordtype(
        self, record_cls: type[ProtoTimeseriesRecord], *, app_label: str = ""
    ) -> None:
        """Add a record type to the registry."""
        _app_label = app_label or self._find_app_label(record_cls)
        app_recordtypes = self.all_recordtypes[_app_label]
        recordtype_name = record_cls.__name__.lower()
        if recordtype_name in app_recordtypes:
            # Raise an error for conflicting metrics (same behavior as apps.register_model)
            raise RuntimeError(
                "Conflicting '{}' metrics in application '{}': {} and {}.".format(
                    recordtype_name,
                    _app_label,
                    app_recordtypes[recordtype_name],
                    record_cls,
                )
            )
        app_recordtypes[recordtype_name] = record_cls

    def register_backend(
        self, backend_name: str, imp_module_path: str, imp_kwargs: dict[str, str]
    ) -> None:
        if backend_name in self.all_backends:
            raise RuntimeError(f"duplicate imps named {backend_name!r}")
        self.all_backends[backend_name] = {imp_module_path: imp_kwargs}

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

    def get_recordtype_app_label(self, recordtype: type) -> str | None:
        _each_matching_app_label = (
            _app_label
            for _app_label, _types in self.all_recordtypes.items()
            if _types.get(recordtype.__name__.lower()) is recordtype
        )
        _res = next(_each_matching_app_label, None)
        if not _res:
            breakpoint()
        return _res

    def get_backend(self, backend_name: str, namespace_prefix: str = "") -> ProtoDjelmeBackend:
        _imp_module, _imp_kwargs = self._lookup_imp_module(backend_name)
        return _imp_module.djelme_backend(backend_name, _imp_kwargs, namespace_prefix)

    def get_imp_module(
        self, imp_module_path: str = "", *, backend_name: str = ""
    ) -> ProtoDjelmeImp:
        _to_import = imp_module_path
        if backend_name:
            assert not imp_module_path  # one or the other
            _registered_module_path, _ = self._lookup_backend(backend_name)
            _to_import = _registered_module_path
        return _import_imp_module(_to_import)

    ###
    # `each` methods: for iterating over each registered

    def each_recordtype(
        self,
        app_label: str = "",
        backend_name: str = "",
    ) -> collections.abc.Iterator[type]:
        """Iterate registered metric classes, optionally filtered on an app_label and/or backend_name."""
        apps.check_apps_ready()  # ensure django setup done
        _imp_module = self.get_imp_module(backend_name=backend_name) if backend_name else None
        app_labels = [app_label] if app_label else self.all_recordtypes.keys()
        for app_label in app_labels:
            for _recordtype in self._get_recordtypes_for_app(app_label).values():
                if (_imp_module is None) or self._is_type_downstream_of_module(
                    _recordtype, _imp_module.__name__
                ):
                    yield _recordtype

    def each_backend_name(
        self,
        *,
        imp_module_path: str = "",
    ) -> collections.abc.Iterator[str]:
        apps.check_apps_ready()  # ensure django setup done
        for _imp_name, _imp_config in self.all_backends.items():
            if (not imp_module_path) or (imp_module_path in _imp_config):
                yield _imp_name

    def each_backend(
        self,
        *,
        imp_module_path: str = "",
    ) -> collections.abc.Iterator[ProtoDjelmeBackend]:
        apps.check_apps_ready()  # ensure django setup done
        for _backend_name in self.each_backend_name(imp_module_path=imp_module_path):
            yield self.get_backend(_backend_name)

    def each_app_label(self) -> collections.abc.Iterable[str]:
        return self.all_recordtypes.keys()

    ###
    # private methods

    def _lookup_backend(self, backend_name: str) -> tuple[str, dict[str, str]]:
        try:
            _backend_settings = self.all_backends[backend_name]
        except KeyError as _e:
            raise LookupError(f"unknown imp {backend_name!r}") from _e
        assert len(_backend_settings) == 1
        ((_imp_module_path, _imp_kwargs),) = _backend_settings.items()
        return (_imp_module_path, _imp_kwargs)

    def _lookup_imp_module(
        self, backend_name: str
    ) -> tuple[ProtoDjelmeImp, dict[str, str]]:
        _imp_module_path, _imp_kwargs = self._lookup_backend(backend_name)
        return (_import_imp_module(_imp_module_path), _imp_kwargs)

    def _get_recordtypes_for_app(self, app_label: str) -> dict[str, type]:
        if app_label not in self.all_recordtypes:
            raise LookupError(
                "No recordtypes found in app with label '{}'.".format(app_label)
            )
        return self.all_recordtypes[app_label]

    def _is_type_downstream_of_module(self, given_type: type, module_name: str) -> bool:
        _upstream_modules = (_cls.__module__ for _cls in given_type.__mro__)
        return module_name in _upstream_modules

    def _find_app_label(self, given_type: type) -> str:
        # Look for an application configuration to attach the model to.
        _containing_app_configs = sorted(
            (
                _app_config
                for _app_config in apps.get_app_configs()
                if given_type.__module__.startswith(_app_config.module.__name__)
            ),
            key=lambda _config: len(_config.module.__name__),
            reverse=True,  # longest module name first
        )
        if not _containing_app_configs:
            raise RuntimeError(
                f"type {given_type.__module__}.{given_type.__qualname__} "
                "doesn't declare an explicit app_label and isn't in an "
                "application in INSTALLED_APPS."
            )
        _app_config = _containing_app_configs[0]
        return _app_config.label


def _import_imp_module(imp_module_path: str) -> ProtoDjelmeImp:
    try:
        _imp_module = importlib.import_module(imp_module_path)
    except ImportError as _error:
        raise ValueError(f"could not import {imp_module_path!r}") from _error
    return _imp_module


###
# module public api

djelme_registry = TimeseriesTypeRegistry()
registry = djelme_registry  # convenience?
