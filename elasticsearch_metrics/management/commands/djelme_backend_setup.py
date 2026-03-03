from django.core.management.base import BaseCommand, CommandError

from elasticsearch_metrics.apps import IMPS_SETTING
from elasticsearch_metrics.registry import registry
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
            help=f"name of a backend configured in settings.{IMPS_SETTING}",
        )

    def handle(self, *args, **options):
        style = color_style()
        _app_label = options["app_label"]
        _backend_name = options["backend"]
        if _app_label:
            if _app_label not in registry.all_recordtypes:
                raise CommandError(
                    "No recordtypes found for app '{}'".format(options["app_label"])
                )
            app_labels = [_app_label]
        else:
            app_labels = registry.all_recordtypes.keys()
        if _backend_name:
            self.stdout.write(f"Using djelme backend {_backend_name!r}")
        for app_label in app_labels:
            self.stdout.write(
                "Syncing recordtypes for app: '{}'".format(app_label),
                style.MIGRATE_HEADING,
            )
            _each_recordtype = (
                registry.each_recordtype(app_label=app_label, backend_name=_backend_name)
                if _backend_name
                else registry.each_recordtype(app_label=app_label)
            )
            for _recordtype in _each_recordtype:
                self.stdout.write(f"  Setting up {_recordtype!r}...")
                _recordtype.sync_index_template()

        self.stdout.write("Synchronized recordtypes.", style.SUCCESS)
