from __future__ import annotations

import io
import json

import mido
import pytest

from cp_liveset import (
    JSON_FORMAT,
    YAML_FORMAT,
    LiveSetSound,
    LiveSetCollection,
    init_sound,
    make_yaml,
)
from cp_liveset import x9format


def _as_sound(v):
    return v if isinstance(v, LiveSetSound) else LiveSetSound.model_validate(v)


def _blobs(group):
    return {key: x9format.sound_to_blob(sound) for key, sound in group.items()}


@pytest.fixture
def small_group(factory_doc):
    return LiveSetCollection({
        (1, 1): _as_sound(factory_doc["pages"]["1"]["1"]),
        (5, 3): _as_sound(factory_doc["pages"]["5"]["3"]),
    })


# --------------------------------------------------------------------------- mapping behavior

def test_mapping_basics(sound_1_1):
    group = LiveSetCollection()
    assert len(group) == 0
    assert not group
    group[(2, 3)] = sound_1_1
    assert group[(2, 3)] is sound_1_1
    assert (2, 3) in group
    assert len(group) == 1
    del group[(2, 3)]
    assert (2, 3) not in group


def test_iteration_is_page_major_sorted(sound_1_1):
    group = LiveSetCollection()
    for pair in [(3, 1), (1, 5), (1, 2), (2, 8)]:
        group[pair] = sound_1_1
    assert list(group) == [(1, 2), (1, 5), (2, 8), (3, 1)]
    assert [pair for pair, _ in group.items()] == [(1, 2), (1, 5), (2, 8), (3, 1)]


def test_constructor_accepts_mapping_and_pairs(sound_1_1):
    a = LiveSetCollection({(1, 1): sound_1_1})
    b = LiveSetCollection([((1, 1), sound_1_1)])
    assert a == b


def test_eq_against_plain_dict(sound_1_1):
    group = LiveSetCollection({(1, 1): sound_1_1})
    assert group == {(1, 1): sound_1_1}
    assert group != {(1, 2): sound_1_1}
    assert group != {}
    assert group != 42


def test_update_merges_and_overwrites(factory_doc):
    a = _as_sound(factory_doc["pages"]["1"]["1"])
    b = _as_sound(factory_doc["pages"]["2"]["1"])
    group = LiveSetCollection({(1, 1): a, (1, 2): a})
    group.update({(1, 2): b, (3, 3): b})
    assert group == {(1, 1): a, (1, 2): b, (3, 3): b}


@pytest.mark.parametrize("key", [(0, 1), (41, 1), (1, 0), (1, 9)])
def test_setitem_rejects_out_of_range_keys(sound_1_1, key):
    group = LiveSetCollection()
    with pytest.raises(ValueError):
        group[key] = sound_1_1


@pytest.mark.parametrize("key", ["1:1", 1, (1,), (1, 2, 3), ("a", "b")])
def test_setitem_rejects_malformed_keys(sound_1_1, key):
    group = LiveSetCollection()
    with pytest.raises(TypeError):
        group[key] = sound_1_1


def test_setitem_rejects_non_sound_values():
    group = LiveSetCollection()
    with pytest.raises(TypeError):
        group[(1, 1)] = {"common": {"name": "not a LiveSetSound"}}


def test_missing_key_raises_keyerror():
    group = LiveSetCollection()
    with pytest.raises(KeyError):
        group[(1, 1)]


def test_repr_shows_names_and_truncates(factory_doc):
    one = LiveSetCollection({(1, 1): _as_sound(factory_doc["pages"]["1"]["1"])})
    assert repr(one) == "LiveSetCollection({(1, 1): 'Test 1-1'})"
    full = LiveSetCollection(
        {(p, s): _as_sound(factory_doc["pages"][str(p)][str(s)])
         for p in range(1, 6) for s in range(1, 9)})
    assert "... 32 more" in repr(full)


# --------------------------------------------------------------------------- JSON

def test_json_roundtrip_through_serialization(small_group):
    doc = small_group.to_json()
    assert doc["format"] == JSON_FORMAT
    back = LiveSetCollection.from_json(json.loads(json.dumps(doc)))
    assert back == small_group


def test_to_json_uses_string_keys_and_plain_types(small_group):
    doc = small_group.to_json()
    assert set(doc["pages"]) == {"1", "5"}
    assert set(doc["pages"]["5"]) == {"3"}
    assert isinstance(doc["pages"]["1"]["1"], dict)


def test_from_json_rejects_wrong_format(small_group):
    doc = small_group.to_json()
    doc["format"] = "something-else"
    with pytest.raises(ValueError):
        LiveSetCollection.from_json(doc)
    with pytest.raises(ValueError):
        LiveSetCollection.from_json({})


def test_empty_group_json_roundtrip():
    assert LiveSetCollection.from_json(LiveSetCollection().to_json()) == {}


# --------------------------------------------------------------------------- YAML

def _yaml_text(group):
    buf = io.StringIO()
    make_yaml().dump(group.to_yaml(), buf)
    return buf.getvalue()


def test_yaml_roundtrip(small_group):
    node = small_group.to_yaml()
    assert node["format"] == YAML_FORMAT
    assert LiveSetCollection.from_yaml(node) == small_group


def test_yaml_roundtrip_through_text_is_canonical(small_group):
    text1 = _yaml_text(small_group)
    back = LiveSetCollection.from_yaml(make_yaml().load(io.StringIO(text1)))
    assert back == small_group
    assert _yaml_text(back) == text1


def test_from_yaml_rejects_wrong_format(small_group):
    node = small_group.to_yaml()
    node["format"] = "something-else"
    with pytest.raises(ValueError):
        LiveSetCollection.from_yaml(node)


# --------------------------------------------------------------------------- SysEx

def test_sysex_roundtrip(small_group):
    messages = small_group.to_sysex()
    assert len(messages) == 19 * len(small_group)
    assert all(isinstance(m, mido.Message) and m.type == "sysex" for m in messages)
    assert LiveSetCollection.from_sysex(messages) == small_group


def test_from_sysex_accepts_raw_bytes(small_group):
    raw = [bytes([0xF0, *m.data, 0xF7]) for m in small_group.to_sysex()]
    assert LiveSetCollection.from_sysex(raw) == small_group


def test_from_sysex_ignores_non_sysex_messages(small_group):
    messages = small_group.to_sysex()
    messages.insert(0, mido.Message("note_on", note=60))
    messages.insert(1, mido.MetaMessage("set_tempo", tempo=500000))
    messages.append(mido.Message("program_change", program=3))
    assert LiveSetCollection.from_sysex(messages) == small_group


def test_from_sysex_rejects_foreign_sysex_by_default(small_group):
    messages = small_group.to_sysex()
    # a non-Yamaha (universal) SysEx message
    messages.insert(0, mido.Message("sysex", data=[0x7E, 0x7F, 0x06, 0x01]))
    with pytest.raises(ValueError):
        LiveSetCollection.from_sysex(messages)


def test_from_sysex_ignore_unknown_skips_foreign_sysex(small_group):
    messages = small_group.to_sysex()
    messages.insert(0, mido.Message("sysex", data=[0x7E, 0x7F, 0x06, 0x01]))
    messages.append(mido.Message("sysex", data=[0x41, 0x10, 0x42]))  # foreign (Roland)
    assert LiveSetCollection.from_sysex(messages, ignore_unknown=True) == small_group


def test_from_sysex_rejects_non_message_objects():
    with pytest.raises(TypeError):
        LiveSetCollection.from_sysex(["not a message"])


def test_from_sysex_empty_is_empty_group():
    assert LiveSetCollection.from_sysex([]) == {}


def test_to_sysex_embeds_device_id(small_group):
    messages = small_group.to_sysex(device_id=5)
    # raw byte 2 of a Bulk Dump is 0x0n with n = device number; mido's
    # .data drops the F0, so it is data[1].
    assert all(m.data[1] == 0x05 for m in messages)
    assert LiveSetCollection.from_sysex(messages) == small_group


def test_to_sysex_rejects_bad_device_id(small_group):
    with pytest.raises(ValueError):
        small_group.to_sysex(device_id=16)


# --------------------------------------------------------------------------- X9 containers

def test_x9s_roundtrip(sound_1_1):
    group = LiveSetCollection({(3, 5): sound_1_1})
    data = group.to_x9s()
    back = LiveSetCollection.from_x9(data)
    assert set(back) == {(3, 5)}
    assert _blobs(back) == _blobs(group)


def test_x9s_requires_exactly_one(sound_1_1):
    with pytest.raises(ValueError):
        LiveSetCollection().to_x9s()
    with pytest.raises(ValueError):
        LiveSetCollection({(1, 1): sound_1_1, (1, 2): sound_1_1}).to_x9s()


def test_x9p_roundtrip_inferred_page(factory_doc):
    page1 = LiveSetCollection(
        {(1, s): _as_sound(factory_doc["pages"]["1"][str(s)]) for s in range(1, 9)})
    back = LiveSetCollection.from_x9(page1.to_x9p())
    assert set(back) == set(page1)
    assert _blobs(back) == _blobs(page1)


def test_x9p_fills_missing_sets_with_init_sound(sound_1_1):
    group = LiveSetCollection({(3, 1): sound_1_1})
    back = LiveSetCollection.from_x9(group.to_x9p())
    assert set(back) == {(3, s) for s in range(1, 9)}
    assert _blobs({0: back[(3, 1)]}) == _blobs({0: sound_1_1})
    init_blob = x9format.sound_to_blob(init_sound())
    for s in range(2, 9):
        assert x9format.sound_to_blob(back[(3, s)]) == init_blob


def test_x9p_empty_without_page_errors():
    with pytest.raises(ValueError):
        LiveSetCollection().to_x9p()


def test_x9p_mixed_pages_without_page_errors(sound_1_1):
    group = LiveSetCollection({(3, 1): sound_1_1, (4, 1): sound_1_1})
    with pytest.raises(ValueError):
        group.to_x9p()


def test_x9p_explicit_page_must_match_keys(sound_1_1):
    group = LiveSetCollection({(3, 1): sound_1_1})
    with pytest.raises(ValueError):
        group.to_x9p(page=9)


def test_x9p_explicit_page_empty_group_all_init_sound():
    back = LiveSetCollection.from_x9(LiveSetCollection().to_x9p(page=9))
    assert set(back) == {(9, s) for s in range(1, 9)}
    init_blob = x9format.sound_to_blob(init_sound())
    assert all(x9format.sound_to_blob(ls) == init_blob for ls in back.values())


def test_x9l_roundtrip_and_fill(sound_1_1):
    group = LiveSetCollection({(1, 1): sound_1_1})
    back = LiveSetCollection.from_x9(group.to_x9l())
    assert set(back) == {(p, s) for p in range(1, 21) for s in range(1, 9)}
    assert _blobs({0: back[(1, 1)]}) == _blobs({0: sound_1_1})
    init_blob = x9format.sound_to_blob(init_sound())
    assert x9format.sound_to_blob(back[(1, 2)]) == init_blob
    assert x9format.sound_to_blob(back[(20, 8)]) == init_blob


def test_x9l_rejects_pages_above_20(sound_1_1):
    group = LiveSetCollection({(21, 1): sound_1_1})
    with pytest.raises(ValueError):
        group.to_x9l()


def test_from_x9_rejects_garbage():
    with pytest.raises(ValueError):
        LiveSetCollection.from_x9(b"definitely not a YSFC container")


# --------------------------------------------------------------------------- presets

def test_init_sound_instances_are_independent():
    a = init_sound()
    b = init_sound()
    a.common.name = "Changed        "
    assert b.common.name == "Init Sound"
