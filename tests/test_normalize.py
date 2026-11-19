import pytest

from ilfootball.resolve.normalize import name_key, normalize_name


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Eran Zahavi", "eran zahavi"),
        ("  ERAN   ZAHAVI ", "eran zahavi"),
        ("Dor Peretz-Levi", "dor peretz levi"),
        ("Mu'nas Dabbur", "munas dabbur"),
        ("Bnei Sakhnin F.C.", "bnei sakhnin fc"),
        ("José Ramírez", "jose ramirez"),
        ("עֵרָן זְהָבִי", "ערנ זהבי"),
        ("מכבי ת״א", "מכבי תא"),
        ("הפועל ב׳׳ש", "הפועל בש"),
    ],
)
def test_normalize_name(raw, expected):
    assert normalize_name(raw) == expected


def test_name_key_is_order_insensitive():
    assert name_key("Zahavi Eran") == name_key("Eran Zahavi") == "eran zahavi"
