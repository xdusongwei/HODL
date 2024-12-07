import unittest
from hodl.tools import LocateTools, VariableTools
from hodl.simulation.main import *


class HodlTestCase(unittest.TestCase):
    @classmethod
    def ci_config_path(cls):
        return LocateTools.locate_file('tests/ci/config.toml')


    def config(self):
        config_path = self.ci_config_path()
        return VariableTools(config_path)
