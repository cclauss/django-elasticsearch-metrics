import abc
import contextlib
from unittest import mock

from django.test import TestTestCase
from django.db import connections

from project.celery import app as celery_app
from share.search.daemon import IndexerDaemonControl
from share.search.index_messenger import IndexMessenger
from share.search import index_strategy
from tests.share.search import patch_index_strategy


# base class for testing with actual elasticsearch running
class RealElasticTestCase(SimpleTestCase, abc.ABC):
    def setUp(self):
        super().setUp()
        self.enterContext(mock.patch('share.models.core._setup_user_token_and_groups'))
        self.index_strategy = self.get_index_strategy()
        self.index_strategy.pls_teardown()  # in case it already exists
        self.enterContext(patch_index_strategy(self.index_strategy))
        self.index_messenger = IndexMessenger(
            celery_app=celery_app,
            index_strategys=[self.index_strategy],
        )
        self._assert_setup_happypath()

    def tearDown(self):
        super().tearDown()
        self.index_strategy.pls_teardown()
        # HACK: copied from TransactionTestCase._fixture_setup; restores db
        # to the state from before TransactionTestCase clobbered it (relies
        # on how django 3.2 implements `serialized_rollback = True`, above)
        connections['default'].creation.deserialize_db_from_string(
            connections['default']._test_serialized_contents
        )
