from elasticsearch8.dsl import Keyword, mapped_field
from elasticsearch_metrics.imps import elastic8 as djelme


class Dummy8Event(djelme.EventLog):
    intensity: int

    class Index:
        using = "elastic8events"


class Dummy8EventWithExplicitNamePrefix(djelme.EventLog):
    intenzity: int

    class Meta:
        timeseries_name_prefix = "dummy8evenz"
        timeseries_type_name = "eventlog"

    class Index:
        using = "elastic8events"


class ThingHappened(djelme.EventLog):
    thing_id: str | None = mapped_field(Keyword(), default=None)
    happen_code: str | None = mapped_field(Keyword(), default=None)

    class Index:
        settings = {"refresh_interval": "-1"}
        using = "elastic8events"

    class Meta:
        timeseries_type_name = "happen"


# TODO: tests using ThingHappeningsReport
class ThingHappeningsReport(djelme.CyclicReport):
    item_id: str = Keyword()
    item_type: str = Keyword()

    class Index:
        settings = {"refresh_interval": "-1"}
        using = "elastic8reports"

    class Meta:
        timeseries_name_prefix = "iv"
