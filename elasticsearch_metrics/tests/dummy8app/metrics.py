from elasticsearch8.dsl import Keyword, Text, mapped_field, analyzer, tokenizer
from elasticsearch_metrics.imps import elastic8 as djelme

dot_path_analyzer = analyzer(
    "dot_path_analyzer",
    tokenizer=tokenizer("dot_path_tokenizer", "path_hierarchy", delimiter="."),
)


class Dummy8Event(djelme.EventRecord):
    intensity: int

    class Index:
        using = "my_elastic8_events"


class Dummy8EventWithExplicitNamePrefix(djelme.EventRecord):
    intenzity: int

    class Meta:
        timeseries_name_prefix = "dummy8evenz"
        timeseries_recordtype_name = "eventlog"

    class Index:
        using = "my_elastic8_events"


class ThingHappened(djelme.EventRecord):
    thing_id: str | None = mapped_field(Keyword(), default=None)
    happen_code: str | None = mapped_field(Keyword(), default=None)
    dot_path: str | None = mapped_field(Text(analyzer=dot_path_analyzer), default=None)

    class Index:
        settings = {"refresh_interval": "-1"}
        using = "my_elastic8_events"

    class Meta:
        timeseries_recordtype_name = "happen"
        timepattern_depth = 2


# TODO: tests using ThingHappeningsReport
class ThingHappeningsReport(djelme.CyclicRecord):
    item_id: str = Keyword()
    item_type: str = Keyword()

    class Index:
        settings = {"refresh_interval": "-1"}
        using = "my_elastic8_reports"

    class Meta:
        timeseries_name_prefix = "blarg"
