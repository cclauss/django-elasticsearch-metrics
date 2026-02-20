from elasticsearch_metrics.imps.elastic8 import (
    EventLog,
    CyclicReport,
)


class Dummy8Event(EventLog):
    intensity: int


class Dummy8EventWithExplicitNamePrefix(EventLog):
    intenzity: int

    class Meta:
        index_name_prefix = "dummy8evenz"


class Dummy8Report(CyclicReport):
    intestines: int
