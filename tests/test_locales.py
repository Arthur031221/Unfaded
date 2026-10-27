import json
import re
from pathlib import Path

import pytest

WEB = Path(__file__).resolve().parents[1] / "src" / "unfaded" / "web"
LOCALES = sorted((WEB / "locales").glob("*.json"))
ENGLISH = json.loads((WEB / "locales" / "en.json").read_text(encoding="utf-8"))


def placeholders(text: str) -> set[str]:
    return set(re.findall(r"\{(\w+)\}", text))


def test_nine_languages_ship():
    assert {p.stem for p in LOCALES} == {"en", "zh-TW", "zh-CN", "ja", "ko", "es", "fr", "de", "pt-BR"}


def test_every_language_is_listed_in_the_switcher():
    source = (WEB / "i18n.js").read_text(encoding="utf-8")
    for path in LOCALES:
        assert re.search(rf'["\']?{re.escape(path.stem)}["\']?:\s*"', source), path.stem


@pytest.mark.parametrize("path", LOCALES, ids=lambda p: p.stem)
def test_keys_and_placeholders_match_english(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    assert set(data) == set(ENGLISH)
    for key, value in data.items():
        assert value.strip(), key
        assert placeholders(value) == placeholders(ENGLISH[key]), key


def test_every_key_used_in_the_page_exists():
    used = set(re.findall(r'data-i18n(?:-[a-z]+)?="([\w.]+)"', (WEB / "index.html").read_text(encoding="utf-8")))
    code = (WEB / "app.js").read_text(encoding="utf-8")
    used |= set(re.findall(r'\bt\("([\w.]+)"', code))
    assert used - set(ENGLISH) == set()
