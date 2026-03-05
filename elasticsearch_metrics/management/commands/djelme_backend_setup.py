from django.core.management.base import BaseCommand, CommandError

from elasticsearch_metrics.apps import BACKENDS_SETTING
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
        parser.add_argument(
            "--backend",
            type=str,
            help=f"name of a backend configured in settings.{BACKENDS_SETTING}",
        )

    def handle(self, *args, **options):
        style = color_style()
        _given_app_label = options["app_label"]
        _backend_name = options["backend"]
        _app_labels: list[str]
        if _given_app_label:
            if _given_app_label not in djelme_registry.all_recordtypes:
                raise CommandError(f"No recordtypes found for app {_given_app_label!r}")
            _app_labels = [_given_app_label]
        else:
            _app_labels = list(djelme_registry.all_recordtypes.keys())
        if _backend_name:
            self.stdout.write(f"Using djelme backend {_backend_name!r}")
        _backends = (
            [djelme_registry.get_backend(_backend_name)]
            if _backend_name
            else list(djelme_registry.each_backend())
        )
        for app_label in _app_labels:
            self.stdout.write(
                "Syncing recordtypes for app: '{}'".format(app_label),
                style.MIGRATE_HEADING,
            )
            for _backend in _backends:
                for _recordtype in djelme_registry.each_recordtype(
                    app_label=app_label, backend_name=_backend.backend_name
                ):
                    self.stdout.write(f"  Setting up {_recordtype!r}...")
                    _backend.setup_timeseries_indexes([_recordtype])

        self.stdout.write("Synchronized recordtypes.", style.SUCCESS)
