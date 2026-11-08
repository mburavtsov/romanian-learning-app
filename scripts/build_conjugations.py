#!/usr/bin/env python3
"""
Build data/conjugations.json: present tense of the first N verbs of verbs.json.

Source: cooljugator.com/ro — one page per verb. Present-tense forms sit in
<div id="present1"> ... <div id="present6">, each with <div class="meta-form">.
Cooljugator has no page for roughly a third of the deck, so dexonline.ro is the
fallback (its inflection table holds the same six forms).
The result is written once and committed, so the bot never scrapes at runtime.

Usage (from project root):
    uv run scripts/build_conjugations.py [N]     # default 50

Output:
    {"a face": ["fac", "faci", "face", "facem", "faceți", "fac"]}
Keys are the "ro" values from verbs.json. Verbs whose page has no complete
present tense are skipped and listed at the end.
"""

import html
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
VERBS_PATH = DATA_DIR / "verbs.json"
OUTPUT_PATH = DATA_DIR / "conjugations.json"
USER_AGENT = "romanian-learning-app dataset builder (github.com/mburavtsov/romanian-learning-app)"
DELAY_SECONDS = 1.0


def parse_present(page: str) -> list[str] | None:
    """Return the six present-tense forms (eu, tu, el/ea, noi, voi, ei/ele)."""
    parts = re.split(r'id="present([1-6])"', page)[1:]
    forms: dict[int, str] = {}
    for number, chunk in zip(parts[::2], parts[1::2]):
        match = re.search(r'class="meta-form">([^<]*)<', chunk)
        if match and html.unescape(match.group(1)).strip():
            forms.setdefault(int(number), html.unescape(match.group(1)).strip())
    if len(forms) != 6:
        return None
    return [forms[i] for i in range(1, 7)]


PERSONS = ["I (eu)", "a II-a (tu)", "a III-a (el, ea)", "I (noi)", "a II-a (voi)", "a III-a (ei, ele)"]
PERSON_RE = re.compile(r">\s*(" + "|".join(re.escape(p) for p in PERSONS) + r")\s*<")


def parse_dexonline(page: str) -> list[str] | None:
    """Same six forms, read from the dexonline inflection table (fallback)."""
    forms: dict[str, str] = {}
    for match in PERSON_RE.finditer(page):
        cell = re.search(r'<td class="form">(.*?)</td>', page[match.end():match.end() + 800], re.S)
        if cell is None:
            continue
        item = re.search(r"<li[^>]*>(.*?)</li>", cell.group(1), re.S)
        text = html.unescape(re.sub(r"<[^>]+>", "", item.group(1) if item else cell.group(1))).strip()
        forms.setdefault(match.group(1), "" if text == "—" else text)
    if len(forms) != 6 or not all(forms.values()):
        return None
    return [forms[person] for person in PERSONS]


def get(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", "replace")


def fetch(verb_ro: str) -> list[str]:
    base = verb_ro.removeprefix("a ").strip()
    forms = parse_present(get("https://cooljugator.com/ro/" + urllib.parse.quote(base)))
    if forms is not None:
        return forms
    forms = parse_dexonline(get("https://dexonline.ro/definitie/" + urllib.parse.quote(base)))
    if forms is None:
        raise ValueError("no complete present tense from cooljugator or dexonline")
    return forms


def main() -> None:
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    verbs = json.loads(VERBS_PATH.read_text(encoding="utf-8"))[:count]

    result: dict[str, list[str]] = {}
    skipped: list[str] = []
    for i, verb in enumerate(verbs, 1):
        try:
            result[verb["ro"]] = fetch(verb["ro"])
            print(f"{i:>3}/{len(verbs)} {verb['ro']:<16} " + " / ".join(result[verb["ro"]]))
        except Exception as exc:  # noqa: BLE001 - one bad page must not stop the run
            skipped.append(verb["ro"])
            print(f"{i:>3}/{len(verbs)} {verb['ro']:<16} SKIPPED: {exc}")
        time.sleep(DELAY_SECONDS)

    OUTPUT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSaved {len(result)} verbs to {OUTPUT_PATH}")
    if skipped:
        print(f"Skipped {len(skipped)}: {', '.join(skipped)}")


if __name__ == "__main__":
    main()
