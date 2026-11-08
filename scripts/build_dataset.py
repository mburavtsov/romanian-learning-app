"""
One-time dataset builder.
Downloads the Romanian Wiktionary extract from kaikki.org, filters for verbs
with English translations, ranks by word frequency, and writes the top N
entries to data/verbs.json.

Usage (from project root):
    uv run --extra scripts scripts/build_dataset.py
"""

import gzip
import json
import logging
import sys
import urllib.request
from pathlib import Path

try:
    from wordfreq import word_frequency
except ImportError:
    print("ERROR: wordfreq is not installed. Run: uv run --extra scripts scripts/build_dataset.py")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

KAIKKI_URL = (
    "https://kaikki.org/dictionary/Romanian/kaikki.org-dictionary-Romanian.jsonl.gz"
)
DATA_DIR = Path(__file__).parent.parent / "data"
OUTPUT_PATH = DATA_DIR / "verbs.json"
TOP_N = 500
MIN_FREQ = 1e-05   # drop verbs rarer than this (filters obscure technical terms)
MIN_GLOSS_LEN = 3  # skip glosses that are just punctuation or tags
MIN_WORD_LEN = 2   # skip words shorter than this

# These tokens appear frequently in corpora but are NOT Romanian infinitives
# (they are auxiliaries, particles, or conjugated forms)
NON_VERB_TOKENS = {
    # Conjugated / auxiliary / particle forms — not infinitives
    "la", "va", "ar", "ai", "vor", "au", "am", "sunt", "e", "o", "care",
    "este", "era", "are", "pot", "fie", "vom", "veti", "veți",
    "vei", "ați", "aș", "om", "ii",
}


def clean_gloss(gloss: str) -> str:
    """Keep the first meaningful part of a gloss."""
    # Many glosses look like: "to do, to make (something)"
    # Strip trailing parenthetical notes
    for sep in ("(", ";"):
        if sep in gloss:
            gloss = gloss[: gloss.index(sep)].strip()
    # Trim trailing punctuation / whitespace
    return gloss.strip(" .,;:")


def third_person(entry: dict) -> str | None:
    """3rd person singular present — the form only a verb has (not the noun homograph)."""
    for form in entry.get("forms", []):
        tags = set(form.get("tags") or [])
        if {"present", "singular", "third-person"} <= tags and "subjunctive" not in tags:
            candidate = (form.get("form") or "").strip()
            if candidate and " " not in candidate:
                return candidate
    return None


def extract_verbs(gz_path: Path) -> list[dict]:
    verbs = []
    seen_ro = set()

    log.info("Parsing %s …", gz_path)
    with gzip.open(gz_path, "rt", encoding="utf-8") as f:
        for line in f:
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            if entry.get("pos") != "verb":
                continue
            if entry.get("lang") != "Romanian":
                continue

            # Inflected forms are separate entries ("dau", "știe"); skip them.
            if any(sense.get("form_of") for sense in entry.get("senses", [])):
                continue

            word_ro = entry.get("word", "").strip()
            if not word_ro or word_ro in seen_ro:
                continue

            # Extract first usable English gloss
            en_gloss = None
            for sense in entry.get("senses", []):
                for g in sense.get("glosses", []):
                    cleaned = clean_gloss(g)
                    # Skip inflected-form entries
                    # Wiktionary marks them with " of " or grammatical category keywords
                    lower = cleaned.lower()
                    if " of " in lower:
                        continue
                    if any(k in lower for k in ("indicative", "subjunctive", "imperative", "participle", "infinitive")):
                        continue
                    if len(cleaned) >= MIN_GLOSS_LEN and not cleaned.startswith("("):
                        en_gloss = cleaned
                        break
                if en_gloss:
                    break

            if not en_gloss:
                continue

            # Skip too-short words and known non-infinitive tokens
            if len(word_ro) < MIN_WORD_LEN or word_ro in NON_VERB_TOKENS:
                continue

            # Skip phrasal/multi-word entries (e.g. "face bine", "se face bine")
            # Allow simple reflexives: "se face" (one word after "se ")
            bare = word_ro[3:] if word_ro.startswith("se ") else word_ro
            if " " in bare:
                continue

            # Ensure standard Romanian infinitive citation form ("a …")
            ro_display = word_ro if word_ro.startswith("a ") else f"a {word_ro}"

            seen_ro.add(word_ro)
            verbs.append(
                {"ro": ro_display, "en": en_gloss, "_base": word_ro, "_third": third_person(entry)}
            )

    log.info("Found %d unique verbs with English glosses.", len(verbs))
    return verbs


def rank_and_trim(verbs: list[dict], top_n: int) -> list[dict]:
    log.info("Ranking by frequency …")
    for v in verbs:
        # Rank on the 3rd person present ("face", "casează"), not the base form:
        # "casa" and "război" are common as nouns and would rank as if they were verbs.
        v["_freq"] = word_frequency(v["_third"] or v["_base"], "ro")

    verbs.sort(key=lambda v: v["_freq"], reverse=True)

    # Drop verbs below the minimum frequency threshold
    before = len(verbs)
    verbs = [v for v in verbs if v["_freq"] >= MIN_FREQ]
    log.info("Filtered %d rare verbs (freq < %.0e). %d remaining.", before - len(verbs), MIN_FREQ, len(verbs))

    top = verbs[:top_n]

    log.info("Top %d verbs. Most frequent: %s", top_n, [v["ro"] for v in top[:10]])
    return top


def main() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    gz_path = DATA_DIR / "kaikki-romanian.jsonl.gz"

    if not gz_path.exists():
        log.info("Downloading kaikki.org Romanian dataset (~30 MB) …")
        urllib.request.urlretrieve(KAIKKI_URL, gz_path)
        log.info("Download complete: %s", gz_path)
    else:
        log.info("Reusing cached file: %s", gz_path)

    verbs = extract_verbs(gz_path)
    top_verbs = rank_and_trim(verbs, TOP_N)

    # Strip internal fields before saving
    output = [{"ro": v["ro"], "en": v["en"]} for v in top_verbs]

    OUTPUT_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("Saved %d verbs to %s", len(output), OUTPUT_PATH)


if __name__ == "__main__":
    main()
