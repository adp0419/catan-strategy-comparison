import pytest

from src.sim.seeds import CHECK_START, EVAL_START, TUNE_END
from src.sim.tune import SeedBlocks, variants


def test_seed_ranges_do_not_overlap():
    assert TUNE_END < CHECK_START < EVAL_START


def test_seed_blocks_are_fresh_and_bounded():
    blocks = SeedBlocks(100)
    assert [blocks.take() for _ in range(3)] == [1, 101, 201]
    blocks.next = TUNE_END - 50
    with pytest.raises(RuntimeError):
        blocks.take()


def test_variants():
    assert variants("vp", 8.0) == [16.0, 4.0]
    assert variants("reach_depth", 1) == [2]
    assert variants("reach_depth", 4) == [3]
