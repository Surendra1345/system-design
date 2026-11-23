"""Guards for the learning content, so a tidy-up cannot reintroduce guessable quizzes or broken markup."""
import re
from collections import Counter
from html.parser import HTMLParser

from app import content

LESSONS = content.lessons_doc()["lessons"]
VOID = {"br", "hr", "img", "input"}


def test_every_quiz_has_four_distinct_options_and_a_reason():
    for l in LESSONS:
        q = l["quiz"]
        assert len(q["o"]) == 4 and len({o.strip().lower() for o in q["o"]}) == 4, l["id"]
        assert 0 <= q["a"] < 4 and q["q"].strip().endswith("?") and len(q["w"]) > 25, l["id"]


def test_the_right_answer_cannot_be_guessed_from_its_position_or_length():
    pos = Counter(l["quiz"]["a"] for l in LESSONS)
    assert all(pos[i] >= len(LESSONS) * 0.15 for i in range(4)) and max(pos.values()) <= len(LESSONS) * 0.4, pos
    much_longer = 0
    for l in LESSONS:
        q = l["quiz"]
        lens = [len(o) for i, o in enumerate(q["o"]) if i != q["a"]]
        much_longer += len(q["o"][q["a"]]) > max(lens) * 1.4
    assert much_longer <= len(LESSONS) * 0.1, much_longer


class _Check(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack, self.bad = [], []

    def handle_starttag(self, tag, attrs):
        if tag not in VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if self.stack and self.stack[-1] == tag:
            self.stack.pop()
        else:
            self.bad.append(tag)


def test_lesson_html_is_well_formed():
    for l in LESSONS:
        for text in [l["sum"]] + [s["b"] for s in l["sec"]] + l["breaks"]:
            c = _Check()
            c.feed(text)
            assert not c.bad and not c.stack, (l["id"], text[:60])


def test_every_lesson_is_complete_and_has_something_to_play():
    ex = content.explain()
    for l in LESSONS:
        assert l["id"] in ex and all(ex[l["id"]][k] for k in ("what", "why", "use", "avoid", "example", "takeaways")), l["id"]
        assert l["id"] == "projects" or (l["sec"] and len(l["breaks"]) >= 3 and content.game_type(l["id"])), l["id"]


def test_no_leftover_placeholders():
    blob = " ".join(re.sub(r"<[^>]+>", " ", s["b"]) for l in LESSONS for s in l["sec"]).lower()
    assert not re.search(r"\btodo\b|lorem ipsum|fixme|xxx", blob)
