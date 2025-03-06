
from ..colonization.requirements import requirements

def test_types():
    assert type(requirements.types()) is list

def test_get():
    assert requirements.get(requirements.types()[10])['needed']['steel'] > 0
    assert requirements.get(None) == {}