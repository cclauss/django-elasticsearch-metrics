from elasticsearch_metrics.imps.elastic8 import (
    EventLog,
    PeriodicReport,
)


class Dummy8Event(EventLog):
    intensity: int


class Dummy8EventWithExplicitTemplateName(EventLog):
    intenzity: int

    class Meta:
        template_name = "dummy8evenz"


class Dummy8Report(PeriodicReport):
    intestines: int
