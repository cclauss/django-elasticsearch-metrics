import itertools
import operator

from django.core.management.base import BaseCommand, CommandError

from elasticsearch_metrics.registry import djelme_registry
from elasticsearch_metrics.management.color import color_style


class Command(BaseCommand):
    help = "Ensures index templates exist for all Metric classes."

    def add_arguments(self, parser):
        parser.add_argument(
            "app_label",
            nargs="?",
            help="App label of an application to synchronize the state.",
        )

    def handle(self, *args, **options):
        style = color_style()
        _given_app_label = str(options["app_label"])
        _given_backend_name = str(options["backend"])
        _app_labels: list[str]
        if _given_app_label:
            if _given_app_label not in djelme_registry.all_recordtypes:
                raise CommandError(f"No recordtypes found for app {_given_app_label!r}")
            _app_labels = [_given_app_label]
        else:
            _app_labels = list(djelme_registry.all_recordtypes.keys())
        for _app_label in _app_labels:
            self.stdout.write(
                "Syncing recordtypes for app: '{}'".format(_app_label),
                style.MIGRATE_HEADING,
            )
            # TODO: recordtype.backend_name removed
            _namegetter = operator.attrgetter("backend_name")
            for _backend_name, _each_recordtype in itertools.groupby(
                sorted(
                    djelme_registry.each_recordtype(app_label=_app_label),
                    key=_namegetter,
                ),
                key=_namegetter,
            ):
                _recordtypes = list(_each_recordtype)
                _using_backend = _given_backend_name or _backend_name
                self.stdout.write(f"  Using backend {_using_backend!r}...")
                _backend = djelme_registry.get_backend(_using_backend)
                for _recordtype in _recordtypes:
                    self.stdout.write(f"  Setting up {_recordtype!r}...")
                _backend.djelme_setup(_recordtypes)

        self.stdout.write("Synchronized recordtypes.", style.SUCCESS)
