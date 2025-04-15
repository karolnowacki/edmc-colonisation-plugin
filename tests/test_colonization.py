import pathlib
from os import path

def setupPlugin():
    from ..colonization.colonization import ColonizationPlugin
    return ColonizationPlugin()

def test_addConstruction():
    plugin = setupPlugin()
    plugin.colonisationConstructionDepot("SYS", "Station", 1, 0.2, False, False, {})

    assert plugin.currentConstruction.getName() == "Station"    


    