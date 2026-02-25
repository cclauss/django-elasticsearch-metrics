from django.core.management.base import BaseCommand, CommandError

from elasticsearch_metrics.registry import registry
from elasticsearch_metrics.management.color import color_style


class Command(BaseCommand):
    help = "Pretty-print a listing of all registered metrics."

    def add_arguments(self, parser):
        parser.add_argument("app_label", nargs="?", help="App label of an application.")

    def handle(self, *args, **options):
        style = color_style()
        if options["app_label"]:
            if options["app_label"] not in registry.all_recordtypes:
                raise CommandError(
                    "No recordtypes found for app '{}'".format(options["app_label"])
                )
            app_labels = [options["app_label"]]
        else:
            app_labels = registry.all_recordtypes.keys()
        for app_label in app_labels:
            self.stdout.write(
                "Recordtypes for '{}':".format(app_label), style.MIGRATE_HEADING
            )
            for _imp in registry.each_imp(app_label=app_label):
            for _recordtype in registry.each_recordtype(app_label=app_label):
                _metric_name = style.METRIC(_recordtype.__name__)
                _template_name = _recordtype.timeseries_template_name
                _template_pattern = style.ES_TEMPLATE(_recordtype.timeseries_template_pattern)
                self.stdout.write(
                    f"  {_metric_name} -> {_template_name} ({_template_pattern})"
                )
