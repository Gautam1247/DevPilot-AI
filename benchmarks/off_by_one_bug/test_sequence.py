from sequence import inclusive_numbers


def test_inclusive():
    assert inclusive_numbers(3) == [1, 2, 3]


def test_empty():
    assert inclusive_numbers(0) == []
