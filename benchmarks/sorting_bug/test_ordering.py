from ordering import ascending


def test_ascending():
    assert ascending([3, 1, 2]) == [1, 2, 3]


def test_empty():
    assert ascending([]) == []
