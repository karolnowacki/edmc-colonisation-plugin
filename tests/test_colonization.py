from ..colonization.colonization import ColonizationPlugin


def test_add_construction() -> None:
    plugin = ColonizationPlugin()
    plugin.colonisation_construction_depot("SYS", "Station", 1, 0.2, False, False, {})

    assert plugin.current_construction
    assert plugin.current_construction.get_name() == "Station"
