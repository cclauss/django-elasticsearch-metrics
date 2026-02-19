from elasticsearch_metrics.imps.elastic8 import (
    EventLog,
    PeriodicReport,
)


class Dummy8Event(EventLog):
    intensity: int


class Dummy8EventWithExplicitNamePrefix(EventLog):
    intenzity: int

    class Meta:
        name_prefix = "dummy8evenz"


class Dummy8Report(PeriodicReport):
    intestines: int
