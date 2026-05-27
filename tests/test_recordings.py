import pytest

from whispo.recordings import format_duration


@pytest.mark.parametrize(
    "seconds, expected",
    [
        (0, "0:00"),
        (45, "0:45"),
        (60, "1:00"),
        (173, "2:53"),
        (3600, "1:00:00"),
        (3725, "1:02:05"),
        (None, "?"),
    ],
)
def test_format_duration(seconds, expected) -> None:
    assert format_duration(seconds) == expected
