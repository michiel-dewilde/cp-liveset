from __future__ import annotations

import pydantic
import pytest

from cp_liveset import codec, paramap
from cp_liveset.soundmodels import LiveSetSound, Section, Sections


def test_roundtrip_against_sample_sounds(factory_doc):
    for _page_str, sets in factory_doc["pages"].items():
        for _set_str, sound in sets.items():
            ls = LiveSetSound.model_validate(sound)
            assert ls.model_dump() == sound


def test_name_field_strips_trailing_nulls(sound_1_1):
    sound_1_1.common.name = "Foo" + "\x00" * 12
    assert sound_1_1.common.name == "Foo"


def test_name_keeps_trailing_spaces(sound_1_1):
    # The model strips trailing NULs but keeps trailing spaces. The sample
    # "Test 1-1" name is space-padded to the full 15-character field, so it
    # stays 15 characters in both the model and JSON.
    assert sound_1_1.common.name == "Test 1-1       "
    assert len(sound_1_1.common.name) == 15
    assert sound_1_1.model_dump(mode="json")["common"]["name"] == "Test 1-1       "


def test_short_name_re_pads_with_nuls_to_15_bytes(sound_1_1):
    # A name shorter than 15 characters is re-padded to the fixed 15-byte
    # field with NULs when encoded (e.g. the 10-char "Init Sound").
    sound_1_1.common.name = "Init Sound"
    name_bytes = codec.sound_to_blocks(sound_1_1)["common"][0:15]
    assert name_bytes == b"Init Sound" + b"\x00" * 5


def test_validate_assignment_enforces_range(sound_1_1):
    with pytest.raises(pydantic.ValidationError):
        sound_1_1.zones[0].zone_switch = 200


def test_validate_assignment_enforces_name_length(sound_1_1):
    with pytest.raises(pydantic.ValidationError):
        sound_1_1.common.name = "x" * 16


def test_extra_fields_forbidden(sound_1_1):
    with pytest.raises(pydantic.ValidationError):
        sound_1_1.common.unknown_field = 1
    with pytest.raises(pydantic.ValidationError):
        LiveSetSound.model_validate({**sound_1_1.model_dump(), "extra": 1})


def test_zones_have_fixed_length(sound_1_1):
    assert len(sound_1_1.zones) == paramap.ZONE_COUNT


def test_sections_have_expected_names():
    assert set(Sections.model_fields.keys()) == set(paramap.SECTION_NAMES)
    assert set(Section.model_fields.keys()) == {"common", "specific", "additional"}
