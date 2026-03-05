from elasticsearch8.dsl import Text, mapped_field, analyzer, tokenizer
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
    thing_id: str = ''
    happen_code: str = ''
    dot_path: str = mapped_field(Text(analyzer=dot_path_analyzer), default='')
    commentary: str = mapped_field(Text(), default='')

    class Index:
        settings = {"refresh_interval": "-1"}
        using = "my_elastic8_events"

    class Meta:
        timeseries_recordtype_name = "happen"
        timedepth = 2


# TODO: tests using ThingHappeningsReport
class ThingHappeningsReport(djelme.CyclicRecord):
    item_id: str
    item_type: str

    class Index:
        settings = {"refresh_interval": "-1"}
        using = "my_elastic8_reports"

    class Meta:
        timeseries_name_prefix = "blarg"
