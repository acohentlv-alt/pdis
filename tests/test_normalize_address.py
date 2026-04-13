from pdis.signals import _normalize_address


def test_hebrew_city_with_hyphen():
    c, s, h = _normalize_address("תל אביב-יפו", "דיזנגוף", "10")
    assert c == "תל אביב יפו"
    assert s == "דיזנגוף"
    assert h == "10"


def test_house_number_with_letter_suffix():
    _, _, h = _normalize_address("X", "Y", "10א")
    assert h == "10"


def test_house_number_range():
    _, _, h = _normalize_address("X", "Y", "10-12")
    assert h == "10"


def test_house_number_fraction():
    _, _, h = _normalize_address("X", "Y", "5/3")
    assert h == "5"


def test_house_number_no_digits():
    _, _, h = _normalize_address("X", "Y", "אא")
    assert h == ""


def test_collapse_whitespace():
    c, s, _ = _normalize_address("  תל   אביב  ", "  שדרות   רוטשילד  ", "1")
    assert c == "תל אביב"
    assert s == "שדרות רוטשילד"


def test_null_inputs():
    c, s, h = _normalize_address(None, None, None)
    assert c == ""
    assert s == ""
    assert h == ""
