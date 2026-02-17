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
                    "No metrics found for app '{}'".format(options["app_label"])
                )
            app_labels = [options["app_label"]]
        else:
            app_labels = registry.all_recordtypes.keys()
        for app_label in app_labels:
            self.stdout.write(
                "Metrics for '{}':".format(app_label), style.MIGRATE_HEADING
            )
            for metric in registry.each_recordtype(app_label=app_label):
                metric_name = style.METRIC(metric.__name__)
                template_name = metric._template_name
                template_pattern = style.ES_TEMPLATE(metric._template_pattern)
                self.stdout.write(
                    "  {metric_name} -> {template_name} ({template_pattern})".format(
                        **locals()
                    )
                )
