"""Tests for the procedural background artwork."""

import random

from ui.backdrop import _walk, hero_line_svg, market_tile_svg


def test_closed_walk_is_seamless():
    """The market tile repeats horizontally, so its walk must end where it starts."""
    w = _walk(random.Random(3), 96, 1.0, closed=True)
    assert abs(w[-1] - w[0]) < 1e-9


def test_artwork_is_deterministic():
    assert market_tile_svg() == market_tile_svg()
    assert hero_line_svg("Swaps") == hero_line_svg("Swaps")
    assert hero_line_svg("Swaps")[0] != hero_line_svg("Forwards")[0]


def test_hero_end_marker_inside_box():
    _, x, y = hero_line_svg("Interest Rate Swaps")
    assert 0 <= x <= 100 and 0 <= y <= 100
