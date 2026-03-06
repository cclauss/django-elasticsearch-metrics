import collections
import dataclasses
import importlib
import weakref

from django.apps import apps

from elasticsearch_metrics.protocols import (
    ProtoDjelmeBackend,
    ProtoDjelmeRecord,
    ProtoDjelmeImp,
)
from elasticsearch_metrics.util.django import find_app_label_for_type

__all__ = ("djelme_registry",)


@dataclasses.dataclass
class _DjelmeRegistry:
    """_DjelmeRegistry keeps track of configured backends and record types (similar to how
    django.apps.registry.Apps keeps track of Model classes).

    Meant to be treated as a singleton -- use the instance at `djelme_registry`.

    Imps should call `djelme_registry.register_recordtype` whenever a non-abstract
    record-type class is defined.

    `djelme_registry.register_backend` should be called based on settings
    """

    # nested mapping from app labels => record-type names => record classes
    # (using weakref so if the class is destroyed, no longer registered)
    all_recordtypes: collections.abc.MutableMapping[
        str, collections.abc.MutableMapping[str, type[ProtoDjelmeRecord]]
    ] = dataclasses.field(
        default_factory=lambda: collections.defaultdict(
            lambda: weakref.WeakValueDictionary[str, type]()
        )
    )

    # nested mapping from backend_name => imp_module_name => imp backend config dictionary
    # (note, only one imp module allowed per backend (for now))
    all_backends: dict[str, dict[str, dict[str, str]]] = dataclasses.field(
        default_factory=dict,
    )

    ###
    # `register` methods: for adding items to the registry

    def register_backend(
        self, backend_name: str, imp_module_name: str, imp_kwargs: dict[str, str]
    ) -> None:
        if backend_name in self.all_backends:
            raise RuntimeError(f"duplicate imps named {backend_name!r}")
        self.all_backends[backend_name] = {imp_module_name: imp_kwargs}

    def register_recordtype(
        self,
        recordtype: type[ProtoDjelmeRecord],
        *,
        app_label: str = "",
    ) -> None:
        """Add a record type to the registry."""
        _app_label = app_label or find_app_label_for_type(recordtype)
        app_recordtypes = self.all_recordtypes[_app_label]
        recordtype_name = recordtype.__name__.lower()
        if recordtype_name in app_recordtypes:
            # Raise an error for conflicting recordtype names (same behavior as apps.register_model)
            raise RuntimeError(
                "Conflicting '{}' recordtypes in application '{}': {} and {}.".format(
                    recordtype_name,
                    _app_label,
                    app_recordtypes[recordtype_name],
                    recordtype,
                )
            )
        app_recordtypes[recordtype_name] = recordtype

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
        return next(_each_matching_app_label, None)

    def get_backend(
        self, backend_name: str, namespace_prefix: str = ""
    ) -> ProtoDjelmeBackend:
        _imp_module, _imp_kwargs = self._lookup_imp_module(backend_name)
        return _imp_module.djelme_backend(backend_name, _imp_kwargs, namespace_prefix)

    def get_imp_module(
        self, imp_module_name: str = "", *, backend_name: str = ""
    ) -> ProtoDjelmeImp:
        _to_import = imp_module_name
        if backend_name:
            assert not imp_module_name  # one or the other
            _registered_module_name, _ = self._lookup_backend(backend_name)
            _to_import = _registered_module_name
        return _import_imp_module(_to_import)

    def get_default_backend(self, from_module_name: str) -> ProtoDjelmeBackend:
        return self.get_backend(self.get_default_backend_name(from_module_name))

    def get_default_backend_name(self, from_module_name: str) -> str:
        self.all_backends[backend_name] = {imp_module_name: imp_kwargs}
        (_backend_name,) = (
            _backend.backend_name
            for _backend in self.each_backend()
            if self._is_type_downstream_of_module(...
        return _backend_name

    ###
    # `each` methods: for iterating over each registered

    def each_recordtype(
        self,
        *,
        app_label: str = "",
    ) -> collections.abc.Iterator[type[ProtoDjelmeRecord]]:
        """Iterate registered metric classes, optionally filtered on an app_label"""
        apps.check_apps_ready()  # ensure django setup done
        _app_labels = [app_label] if app_label else self.all_recordtypes.keys()
        for _app_label in _app_labels:
            for _recordtype in self.all_recordtypes[_app_label].values():
                yield _recordtype

    def each_backend_name(
        self,
        *,
        imp_module_name: str = "",
    ) -> collections.abc.Iterator[str]:
        apps.check_apps_ready()  # ensure django setup done
        for _backend_name, _imp_config in self.all_backends.items():
            if (not imp_module_name) or (imp_module_name in _imp_config):
                yield _backend_name

    def each_backend(
        self,
        *,
        imp_module_name: str = "",
    ) -> collections.abc.Iterator[ProtoDjelmeBackend]:
        for _backend_name in self.each_backend_name(imp_module_name=imp_module_name):
            yield self.get_backend(_backend_name)

    def each_app_label(self) -> collections.abc.Iterable[str]:
        yield from self.all_recordtypes.keys()

    ###
    # private methods

    def _lookup_backend(self, backend_name: str) -> tuple[str, dict[str, str]]:
        try:
            _backend_settings = self.all_backends[backend_name]
        except KeyError as _e:
            raise LookupError(f"unknown imp {backend_name!r}") from _e
        assert len(_backend_settings) == 1
        ((_imp_module_name, _imp_kwargs),) = _backend_settings.items()
        return (_imp_module_name, _imp_kwargs)

    def _lookup_imp_module(
        self, backend_name: str
    ) -> tuple[ProtoDjelmeImp, dict[str, str]]:
        _imp_module_name, _imp_kwargs = self._lookup_backend(backend_name)
        return (_import_imp_module(_imp_module_name), _imp_kwargs)

    def _get_recordtypes_for_app(
        self, app_label: str
    ) -> collections.abc.Mapping[str, type]:
        if app_label not in self.all_recordtypes:
            raise LookupError(
                "No recordtypes found in app with label '{}'.".format(app_label)
            )
        return self.all_recordtypes[app_label]

    def _is_type_downstream_of_module(self, given_type: type, module_name: str) -> bool:
        _upstream_modules = (_cls.__module__ for _cls in given_type.__mro__)
        return module_name in _upstream_modules


def _import_imp_module(imp_module_name: str) -> ProtoDjelmeImp:
    try:
        _imp_module = importlib.import_module(imp_module_name)
    except ImportError as _error:
        raise ValueError(f"could not import {imp_module_name!r}") from _error
    assert isinstance(_imp_module, ProtoDjelmeImp)
    return _imp_module


###
# module public api

djelme_registry = _DjelmeRegistry()
registry = djelme_registry  # back-compat synonym?
