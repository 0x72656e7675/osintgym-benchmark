from osintgym.grading.answers import score_field
from osintgym.tasks.model import AnswerField, EntityRef


def test_entity_needs_the_url_for_full_credit():
    field = AnswerField(name="x", kind="entity", description="", entity=EntityRef(name="Ana Costa", urls=["http://guildhall.test/in/ana-costa-1a2b"]))
    assert score_field(field, {"name": "Someone", "url": "http://guildhall.test/in/ana-costa-1a2b/"}) == 1.0
    assert score_field(field, {"name": "ana costa"}) == 0.5
    assert score_field(field, {"name": "Ana Costa", "url": "http://guildhall.test/in/ana-costa-9z9z"}) == 0.5
    assert score_field(field, "http://guildhall.test/in/other") == 0.0


def test_entity_set_is_f1_and_padding_costs_precision():
    members = [EntityRef(name=n, urls=[f"http://registry.test/officer/{n}"]) for n in ("a", "b")]
    field = AnswerField(name="x", kind="entity_set", description="", members=members)
    exact = [{"name": "a", "url": "http://registry.test/officer/a"}, {"name": "b", "url": "http://registry.test/officer/b"}]
    assert score_field(field, exact) == 1.0
    padded = exact + [{"name": f"z{i}", "url": f"http://registry.test/officer/z{i}"} for i in range(6)]
    assert score_field(field, padded) == 0.4
    assert score_field(field, exact[:1]) == 2 / 3


def test_geo_bands():
    field = AnswerField(name="x", kind="geo", description="", lat=-30.0, lon=-137.0)
    assert score_field(field, {"lat": -30.0001, "lon": -137.0001}) == 1.0
    assert score_field(field, {"lat": -30.002, "lon": -137.0}) == 0.75
    assert score_field(field, "-30.03, -137.0") == 0.25
    assert score_field(field, {"lat": -31.0, "lon": -137.0}) == 0.0
    assert score_field(field, {"lat": "nowhere"}) == 0.0


def test_datetime_number_text_choice():
    moment = AnswerField(name="x", kind="datetime", description="", value="2026-05-14T09:31:00+00:00", tolerance=3600)
    assert score_field(moment, "2026-05-14T10:00:00Z") == 1.0
    assert score_field(moment, "2026-05-14 09:31 UTC") == 1.0
    assert score_field(moment, "2026-05-15T09:31:00Z") == 0.0
    number = AnswerField(name="x", kind="number", description="", number=4.8, tolerance=0.05)
    assert score_field(number, 4.8) == 1.0
    assert score_field(number, "4,8 million") == 1.0
    assert score_field(number, 48) == 0.0
    text = AnswerField(name="x", kind="text", description="", accepted=["Port Calder"])
    assert score_field(text, "port calder, Norvessa") == 1.0
    assert score_field(text, "Halvik") == 0.0
    choice = AnswerField(name="x", kind="choice", description="", options=["listed", "not_listed"], accepted=["not_listed"])
    assert score_field(choice, "not_listed") == 1.0
    assert score_field(choice, "listed") == 0.0
