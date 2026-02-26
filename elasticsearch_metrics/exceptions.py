class DjelmeError(Exception):
    """Base class from which all django-elasticsearch-metrics -related exceptions inherit."""


class TimeseriesSetupError(DjelmeError):
    """for errors that might be solved by `djelme_setup`"""


class IndexTemplateNotFoundError(TimeseriesSetupError):
    def __init__(self, message, client_error):
        self.client_error = client_error
        super().__init__(message, client_error)


class IndexTemplateOutOfSyncError(TimeseriesSetupError):
    def __init__(self, message, mappings_in_sync, patterns_in_sync, settings_in_sync):
        self.mappings_in_sync = mappings_in_sync
        self.patterns_in_sync = patterns_in_sync
        self.settings_in_sync = settings_in_sync
        super().__init__(message, mappings_in_sync, patterns_in_sync, settings_in_sync)
