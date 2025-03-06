
from ..colonization.colonization import ColonizationPlugin

import pathlib
from os import path

def setupPlugin():
    class Config(dict):
        def __getattr__(self, key):
            return self[key]
        def __setattr__(self, key, value):
            self[key] = value

    config = Config()
    config.app_dir_path = pathlib.Path('%LocalAppData%\\EDMarketConnector')
    return ColonizationPlugin(config)


def test_addConstruction():
    plugin = setupPlugin()
    plugin.addConstruction("My Name")

    assert plugin.constructions[0].name == "My Name"

    c = plugin.addConstruction("Different name", 'Surface - Planetary Port - Outpost - Industrial')
    c.setStation(None, "Planetary Construction Site: Test", 123456)
    c.deliver("emergencypowercells", 48)

    assert plugin.constructions[1].name == "Different name"
    assert plugin.constructions[1].stationName == "Planetary Construction Site: Test"
    assert plugin.constructions[1].marketId == 123456
    


    