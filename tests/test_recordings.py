from pathlib import Path

import pytest

from whispo.recordings import format_duration, stakeholder_from_filename


@pytest.mark.parametrize(
    "filename, expected",
    [
        # Date-prefixed → date stripped, name title-cased
        ("2026-05-20-jane.m4a", "Jane"),
        ("2026_05_20_bob.opus", "Bob"),
        ("20260520-alice-cooper.m4a", "Alice Cooper"),
        ("05-20-26 jane doe.wav", "Jane Doe"),
        # Plain names
        ("jane.m4a", "Jane"),
        ("product_strategy_interview.m4a", "Product Strategy"),
        # Trailing recorder/source tags stripped
        ("bob_recording.mp3", "Bob"),
        ("jane-zoom-call.m4a", "Jane"),
        ("alice_meet.opus", "Alice"),
        # Empty/edge cases
        (".m4a", ""),
    ],
)
def test_stakeholder_from_filename(filename: str, expected: str) -> None:
    assert stakeholder_from_filename(Path(filename)) == expected


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
