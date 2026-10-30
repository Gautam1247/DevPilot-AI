from pricing import apply_discount


def test_twenty_percent():
    assert apply_discount(100, 20) == 80


def test_no_discount():
    assert apply_discount(100, 0) == 100
