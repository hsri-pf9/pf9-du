import os
from unittest import TestCase
from pecan import set_config
from pecan.testing import load_test_app

__all__ = ['FunctionalTest']

class FunctionalTest(TestCase):
    """
    Used for functional tests where you need to test your
    literal application and its integration with the framework.
    """
    pass
