import io
from typing import cast

import pytest

from hassil import Intents, recognize
from hassil.expression import TextChunk
from hassil.intents import TextSlotList

TEST_YAML = """
language: "en"
intents:
  TurnOnTV:
    data:
      - sentences:
        - "turn on [the] TV in <area>"
        - "turn on <area> TV"
        slots:
          domain: "media_player"
          name: "roku"
  SetBrightness:
    data:
      - sentences:
        - "set [the] brightness in <area> to <brightness>"
        slots:
          domain: "light"
          name: "all"
      - sentences:
        - "set [the] brightness of <name> to <brightness>"
        requires_context:
          domain: "light"
        slots:
          domain: "light"
  GetTemperature:
    data:
      - sentences:
        - "<what_is> [the] temperature in <area>"
        slots:
          domain: "climate"
  CloseCover:
    data:
      - sentences:
        - "close <name>"
        requires_context:
          domain: "cover"
        slots:
          domain: "cover"
  Play:
    data:
      - sentences:
          - "play <name>"
        excludes_context:
          domain:
            - "cover"
            - "light"
expansion_rules:
  area: "[the] {area}"
  name: "[the] {name}"
  brightness: "{brightness_pct} [percent]"
  what_is: "(what's | whats | what is)"
lists:
  brightness_pct:
    range:
      type: percentage
      from: 0
      to: 100
skip_words:
  - "please"
"""


@pytest.fixture
def intents():
    with io.StringIO(TEST_YAML) as test_file:
        return Intents.from_yaml(test_file)


@pytest.fixture
def slot_lists():
    return {
        "area": TextSlotList.from_tuples(
            [("kitchen", "area.kitchen"), ("living room", "area.living_room")]
        ),
        "name": TextSlotList.from_tuples(
            [
                ("hue", "light.hue", {"domain": "light"}),
                (
                    "garage door",
                    "cover.garage_door",
                    {"domain": "cover"},
                ),
                (
                    "roku",
                    "media_player.roku",
                    {"domain": "media_player"},
                ),
            ]
        ),
    }


# pylint: disable=redefined-outer-name
def test_turn_on(intents, slot_lists):
    result = recognize("turn on kitchen TV, please", intents, slot_lists=slot_lists)
    assert result is not None
    assert result.intent.name == "TurnOnTV"

    area = result.entities["area"]
    assert area.name == "area"
    assert area.value == "area.kitchen"

    # From YAML
    assert result.entities["domain"].value == "media_player"
    assert result.entities["name"].value == "roku"


# pylint: disable=redefined-outer-name
def test_brightness_area(intents, slot_lists):
    result = recognize(
        "set the brightness in the living room to 75%", intents, slot_lists=slot_lists
    )
    assert result is not None
    assert result.intent.name == "SetBrightness"

    assert result.entities["area"].value == "area.living_room"
    assert result.entities["brightness_pct"].value == 75

    # From YAML
    assert result.entities["domain"].value == "light"
    assert result.entities["name"].value == "all"


# pylint: disable=redefined-outer-name
def test_brightness_name(intents, slot_lists):
    result = recognize(
        "set brightness of the hue to 50%", intents, slot_lists=slot_lists
    )
    assert result is not None
    assert result.intent.name == "SetBrightness"

    assert result.entities["name"].value == "light.hue"
    assert result.entities["brightness_pct"].value == 50

    # From YAML
    assert result.entities["domain"].value == "light"


# pylint: disable=redefined-outer-name
def test_brightness_not_cover(intents, slot_lists):
    result = recognize(
        "set brightness of the garage door to 50%", intents, slot_lists=slot_lists
    )
    assert result is None


# pylint: disable=redefined-outer-name
def test_temperature(intents, slot_lists):
    result = recognize(
        "what is the temperature in the living room?", intents, slot_lists=slot_lists
    )
    assert result is not None
    assert result.intent.name == "GetTemperature"

    assert result.entities["area"].value == "area.living_room"

    # From YAML
    assert result.entities["domain"].value == "climate"


# pylint: disable=redefined-outer-name
def test_close_name(intents, slot_lists):
    result = recognize("close the garage door", intents, slot_lists=slot_lists)
    assert result is not None
    assert result.intent.name == "CloseCover"

    assert result.entities["name"].value == "cover.garage_door"

    # From YAML
    assert result.entities["domain"].value == "cover"


# pylint: disable=redefined-outer-name
def test_close_not_light(intents, slot_lists):
    result = recognize("close the hue", intents, slot_lists=slot_lists)
    assert result is None


# pylint: disable=redefined-outer-name
def test_play(intents, slot_lists):
    result = recognize("play roku", intents, slot_lists=slot_lists)
    assert result is not None
    assert result.intent.name == "Play"

    assert result.entities["name"].value == "media_player.roku"


# pylint: disable=redefined-outer-name
def test_play_no_cover(intents, slot_lists):
    result = recognize("play the garage door", intents, slot_lists=slot_lists)
    assert result is None


def test_lists_no_template() -> None:
    """Ensure list values are plain text."""
    yaml_text = """
    language: "en"
    intents: {}
    lists:
      test:
        values:
          - "[a | b]"
    """

    with io.StringIO(yaml_text) as test_file:
        intents = Intents.from_yaml(test_file)

    test_list = cast(TextSlotList, intents.slot_lists["test"])
    text_in = test_list.values[0].text_in
    assert isinstance(text_in, TextChunk)
    assert text_in.text == "[a | b]"


def test_list_text_normalized() -> None:
    """Ensure list text in values are normalized."""
    yaml_text = """
    language: "en"
    intents:
      TestIntent:
        data:
          - sentences:
            - "run {test_name}"
    lists:
      test_name:
        values:
          - "tEsT    1"
    """

    with io.StringIO(yaml_text) as test_file:
        intents = Intents.from_yaml(test_file)

    result = recognize("run test 1", intents)
    assert result is not None
    assert result.entities["test_name"].value == "tEsT    1"


def test_skip_prefix() -> None:
    yaml_text = """
    language: "en"
    intents:
      TestIntent:
        data:
          - sentences:
            - "run {test_name}"
    lists:
      test_name:
        values:
          - "test"
    skip_words:
      - "the"
    """

    with io.StringIO(yaml_text) as test_file:
        intents = Intents.from_yaml(test_file)

    result = recognize("run the test", intents)
    assert result is not None
    assert result.entities["test_name"].value == "test"
