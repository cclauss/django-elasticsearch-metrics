from elasticsearch_metrics.imps import elastic6


class Dummy6Metric(elastic6.Metric):
    my_int = elastic6.Integer()


class Dummy6MetricWithExplicitTemplateName(elastic6.Metric):
    my_keyword = elastic6.Keyword()

    class Meta:
        template_name = "dummy6metric"


class Dummy6MetricWithExplicitTemplatePattern(elastic6.Metric):
    class Meta:
        template = "dummy6metric-*"
