import pytest
from rif.datagen import rotamers
from rif.util import rcl


@pytest.mark.skipif('not rcl.HAVE_PYROSETTA')
def test_rotamers():
    assert rotamers.get_rotamer_coords()