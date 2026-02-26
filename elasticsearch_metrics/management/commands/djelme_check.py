import sys
import logging
from django.core.management.base import BaseCommand, CommandError

from django.utils.termcolors import colorize

from elasticsearch_metrics.registry import registry
from elasticsearch_metrics import exceptions
from elasticsearch_metrics.management.color import color_style


class Command(BaseCommand):
    help = "Check if registered recordtypes have a corresponding index templates in Elasticsearch."

    def add_arguments(self, parser):
        parser.add_argument("app_label", nargs="?", help="App label of an application.")

    def handle(self, *args, **options):
        # Avoid elasticsearch requests from getting logged
        logging.getLogger("elasticsearch").setLevel(logging.CRITICAL)
        style = color_style()
        if options["app_label"]:
            if options["app_label"] not in registry.all_recordtypes:
                raise CommandError(
                    "No recordtypes found for app '{}'".format(options["app_label"])
                )
            app_labels = [options["app_label"]]
        else:
            app_labels = list(registry.each_imp_app_label())

        out_of_sync_count = 0
        self.stdout.write("Checking for outdated index templates...")
        for app_label in app_labels:
            for _recordtype in registry.each_recordtype(app_label=app_label):
                try:
                    _recordtype.check_index_template()
                except (
                    exceptions.IndexTemplateNotFoundError,
                    exceptions.IndexTemplateOutOfSyncError,
                ) as error:
                    self.stdout.write("  " + error.args[0])
                    out_of_sync_count += 1

        if out_of_sync_count:
            self.stdout.write(
                "{} index template(s) not set up.".format(out_of_sync_count),
                style.ERROR,
            )
            cmd = colorize("python manage.py djelme_setup", opts=("bold",))
            self.stdout.write("Run {cmd} to set up index templates.".format(cmd=cmd))
            sys.exit(1)
        else:
            self.stdout.write("All djelme recordtypes set up.", style.SUCCESS)
