import unittest
from hodl.simulation.main import *


class HodlTestCase(unittest.TestCase):
    @classmethod
    def config(cls):
        return SimulationStore.config()
