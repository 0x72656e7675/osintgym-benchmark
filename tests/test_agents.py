import json
import sys
from pathlib import Path

import pytest

from osintgym.agents.command import CommandAgent
from osintgym.agents.llm import Call, LLMAgent, Settings, Turn
from osintgym.runner import run
from osintgym.tasks import generate

HARNESS = Path(__file__).with_name("tiny_harness.py")


@pytest.fixture(scope="module")
def exif_task():
    world, tasks = generate()
    return world, next(t for t in tasks if t.family == "imint.geolocate" and t.variant == "exif")


class ScriptedProvider:
    """Stands in for a model: reads the page, then the original file's metadata, then answers."""

    def __init__(self):
        self.settings = Settings(model="scripted")

    def start(self, prompt):
        return {"prompt": prompt, "observations": []}

    def step(self, convo, ctx):
        seen = convo["observations"]
        if not seen:
            seed = convo["prompt"].split("Seed:\n- ", 1)[1].split("\n", 1)[0]
            return Turn([Call("1", "http_get", {"url": seed})])
        if len(seen) == 1:
            original = seen[0].split("Download original [", 1)[1].split("]", 1)[0]
            return Turn([Call("2", "image_metadata", {"url": original})])
        meta = json.loads(seen[1])
        answer = {"location": {"lat": meta["GPSLatitude"], "lon": meta["GPSLongitude"]}}
        return Turn([Call("3", "submit_answer", {"status": "answered", "answer": answer, "evidence": [], "report": "",
                                                  "confidence": 0.9})])

    def answer(self, convo, turn, results):
        convo["observations"].extend(observation.text for _, observation in results)

    def say(self, convo, text):
        pass


def test_reference_harness_loop_uses_the_tools_through_the_gateway(exif_task):
    world, task = exif_task
    result = run(world, [task], LLMAgent(ScriptedProvider(), label="scripted-provider"))["results"][0]
    assert result["solved"], result
    assert result["requests"] >= 2 and result["usage"]["steps"] == 2


def test_command_harness_receives_card_and_proxy(exif_task):
    world, task = exif_task
    result = run(world, [task], CommandAgent(f"{sys.executable} {HARNESS}"))["results"][0]
    assert result["requests"] == 1
    assert result["status"] == "answered"
    assert result["usage"]["input_tokens"] == 7
