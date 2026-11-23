import re

import pytest

from app import content
from tools.build_stages import STAGE_IDS

PILOT = ["lb", "cache", "queue"]


@pytest.mark.parametrize("lid", PILOT)
def test_pilot_lessons_have_all_ten_stages_in_order(lid):
    st = content.stages()[lid]["stages"]
    assert [s["id"] for s in st] == STAGE_IDS
    assert all(s["title"] for s in st)


def test_only_real_lessons_have_stages():
    assert set(content.stages()) <= set(content.lesson_index())


@pytest.mark.parametrize("lid", PILOT)
def test_proof_questions_are_well_formed_and_have_a_real_answer(lid):
    qs = content.stages()[lid]["stages"][-1]["questions"]
    assert len(qs) >= 3
    for q in qs:
        assert len(q["options"]) == 4 and len(set(q["options"])) == 4
        assert 0 <= q["answer"] < 4 and q["why"]


def test_correct_answers_are_not_always_in_the_same_position():
    pos = [q["answer"] for lid in PILOT for q in content.stages()[lid]["stages"][-1]["questions"]]
    assert len(set(pos)) >= 3 and max(pos.count(p) for p in set(pos)) <= len(pos) // 2


@pytest.mark.parametrize("lid", PILOT)
def test_each_pilot_lesson_has_design_checks_and_tutor_prompts(lid):
    d = content.stages()[lid]
    design = [s for s in d["stages"] if s["id"] == "design"][0]
    assert len(design["checks"]) >= 4 and design["prompt"]
    assert len(d["tutor"]) == 3


def test_worked_numbers_are_arithmetically_right():
    text = lambda lid: " ".join(" ".join(s.get("steps", [])) for s in content.stages()[lid]["stages"])
    assert 0.9 * 1 + 0.1 * 50 == pytest.approx(5.9) and "5.9 ms" in text("cache")
    assert 0.95 * 1 + 0.05 * 50 == pytest.approx(3.45) and "3.45 ms" in text("cache")
    assert 800 / 3 == pytest.approx(267, abs=0.5) and "267" in text("lb")
    assert 30 * (100 - 40) == 1800 and 1800 / (40 - 20) == 90 and "1,800" in text("queue") and "90 seconds" in text("queue")
    # proof answers
    assert 0.8 * 2 + 0.2 * 100 == pytest.approx(21.6)
    assert 5000 * 0.10 == 500 and 5000 * 0.02 == 100


def test_the_lesson_api_returns_stages_only_for_pilot_lessons(client):
    r = client.get("/api/lessons/cache").json()
    assert [s["id"] for s in r["stages"]] == STAGE_IDS and len(r["tutor_prompts"]) == 3
    assert "stages" not in client.get("/api/lessons/net").json()


def test_stage_html_has_no_scripts():
    for d in content.stages().values():
        assert not re.search(r"<script|onerror|onclick", str(d), re.I)
