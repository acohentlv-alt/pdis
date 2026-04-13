from pdis.signals import _year_band, _floor_adjustment, _YEAR_ADJUSTMENT


def test_year_band_old():
    assert _year_band(1955) == "old"
    assert _YEAR_ADJUSTMENT["old"] == -0.18


def test_year_band_mid_old():
    assert _year_band(1975) == "mid_old"


def test_year_band_mid():
    assert _year_band(2000) == "mid"


def test_year_band_new():
    assert _year_band(2015) == "new"
    assert _YEAR_ADJUSTMENT["new"] == 0.05


def test_year_band_null_falls_to_mid():
    assert _year_band(None) == "mid"
    assert _YEAR_ADJUSTMENT["mid"] == 0.0


def test_floor_1_no_penalty():
    assert _floor_adjustment(1, False) == 0.0


def test_floor_2_minus_3pct_no_elevator():
    assert _floor_adjustment(2, False) == -0.03


def test_floor_5_minus_12pct_no_elevator():
    assert _floor_adjustment(5, False) == -0.12


def test_floor_10_capped_at_minus_15pct():
    assert _floor_adjustment(10, False) == -0.15


def test_elevator_negates_floor_penalty():
    assert _floor_adjustment(5, True) == 0.0


def test_floor_none_no_penalty():
    assert _floor_adjustment(None, False) == 0.0
