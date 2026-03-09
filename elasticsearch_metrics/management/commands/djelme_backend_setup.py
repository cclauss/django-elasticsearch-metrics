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
            for _backend_name, _recordtypes in djelme_registry.each_recordtype_by_backend(_app_label):
                _backend = djelme_registry.get_backend(_backend_name)
                self.stdout.write(f"  Using backend {_backend.backend_name!r}...")
                for _recordtype in _recordtypes:
                    self.stdout.write(f"  Setting up {_recordtype!r}...")
                _backend.djelme_setup(_recordtypes)

        self.stdout.write("Synchronized recordtypes.", style.SUCCESS)
