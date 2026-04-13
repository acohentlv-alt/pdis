"""Tests for Phase 2B-1 adjusted-total math."""
import pytest
from pdis.signals import _year_band, _DEFAULT_FA, _MAX_NEGATIVE_ADJUSTMENT


def test_default_fa_values_match_phase_2a():
    assert _DEFAULT_FA["year_old_pref_pct"] == -18.0
    assert _DEFAULT_FA["year_mid_old_pref_pct"] == -8.0
    assert _DEFAULT_FA["year_mid_pref_pct"] == 0.0
    assert _DEFAULT_FA["year_new_pref_pct"] == 5.0
    assert _DEFAULT_FA["walkup_pct_per_floor"] == 3.0


def test_max_negative_cap():
    assert _MAX_NEGATIVE_ADJUSTMENT == -0.50


def test_year_band_boundaries():
    assert _year_band(1959) == "old"
    assert _year_band(1960) == "mid_old"
    assert _year_band(1989) == "mid_old"
    assert _year_band(1990) == "mid"
    assert _year_band(2009) == "mid"
    assert _year_band(2010) == "new"
