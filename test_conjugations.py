import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "scripts"))
import build_conjugations as bc  # noqa: E402

COOLJUGATOR_PAGE = """
<div class="conjugation-cell" id="present1" style="order: 1;"><div class="forms-wrapper">
<div class="meta-form"> fac</div></div></div>
<div class="conjugation-cell" id="present2" style="order: 2;"><div class="forms-wrapper">
<div class="meta-form"> faci</div></div></div>
<div class="conjugation-cell" id="present3" style="order: 3;"><div class="forms-wrapper">
<div class="meta-form"> face</div></div></div>
<div class="conjugation-cell" id="present4" style="order: 4;"><div class="forms-wrapper">
<div class="meta-form"> facem</div></div></div>
<div class="conjugation-cell" id="present5" style="order: 5;"><div class="forms-wrapper">
<div class="meta-form"> face&#539;i</div></div></div>
<div class="conjugation-cell" id="present6" style="order: 6;"><div class="forms-wrapper">
<div class="meta-form"> fac</div></div></div>
"""

DEXONLINE_PAGE = """
<tr><td class="inflection">singular</td><td class="inflection person">I (eu)</td>
<td class="form"><ul class="commaList"><li>permit</li></ul></td><td class="form">(să) permit</td></tr>
<tr><td class="inflection person">a II-a (tu)</td>
<td class="form"><ul class="commaList"><li>permi<span>ț</span>i</li></ul></td><td class="form">(să) permiți</td></tr>
<tr><td class="inflection person">a III-a (el, ea)</td>
<td class="form"><ul class="commaList"><li>permite</li></ul></td><td class="form">(să) permită</td></tr>
<tr><td class="inflection">plural</td><td class="inflection person">I (noi)</td>
<td class="form"><ul class="commaList"><li>permitem</li></ul></td><td class="form">(să) permitem</td></tr>
<tr><td class="inflection person">a II-a (voi)</td>
<td class="form"><ul class="commaList"><li>permiteți</li></ul></td><td class="form">(să) permiteți</td></tr>
<tr><td class="inflection person">a III-a (ei, ele)</td>
<td class="form"><ul class="commaList"><li>permit</li></ul></td><td class="form">(să) permită</td></tr>
"""


def test_parses_cooljugator_page():
    assert bc.parse_present(COOLJUGATOR_PAGE) == ["fac", "faci", "face", "facem", "faceți", "fac"]


def test_parses_dexonline_page():
    assert bc.parse_dexonline(DEXONLINE_PAGE) == [
        "permit", "permiți", "permite", "permitem", "permiteți", "permit",
    ]


def test_incomplete_pages_are_rejected():
    assert bc.parse_present(COOLJUGATOR_PAGE.replace('id="present6"', 'id="x"')) is None
    # a defective verb has no 1st person: "—" must not be treated as a form
    assert bc.parse_dexonline(DEXONLINE_PAGE.replace("<li>permit</li>", "<li>—</li>", 1)) is None
