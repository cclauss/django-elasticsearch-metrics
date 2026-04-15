class DjelmeError(Exception):
    """Base class from which all django-elasticsearch-metrics -related exceptions inherit."""


class DjelmeSetupError(DjelmeError):
    """for errors that might be solved by `djelme_backend_setup`"""


class IndexNotFoundError(DjelmeSetupError):
    """specific index not found"""

    def __init__(self, message, client_error):
        self.client_error = client_error
        super().__init__(message, client_error)


class IndexOutOfSyncError(DjelmeSetupError):
    """specific index has different mappings than expected"""


class IndexTemplateNotFoundError(DjelmeSetupError):
    """index template not found"""

    def __init__(self, message, client_error):
        self.client_error = client_error
        super().__init__(message, client_error)


class IndexTemplateOutOfSyncError(DjelmeSetupError):
    """index template has different mappings, settings, or patterns than expected"""

    def __init__(self, message, mappings_in_sync, patterns_in_sync, settings_in_sync):
        self.mappings_in_sync = mappings_in_sync
        self.patterns_in_sync = patterns_in_sync
        self.settings_in_sync = settings_in_sync
        super().__init__(message, mappings_in_sync, patterns_in_sync, settings_in_sync)
