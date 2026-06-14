from __future__ import annotations

import pydantic
import pytest

from cp_liveset import codec, paramap, sysex


def test_sound_blocks_roundtrip(sound_1_1):
    block_data = codec.sound_to_blocks(sound_1_1)
    back = codec.sound_from_blocks(block_data)
    assert back == sound_1_1


def test_sound_to_messages_and_back(sound_1_1):
    messages = codec.sound_to_messages(0, 1, 1, sound_1_1)
    assert len(messages) == 19  # header + 17 data blocks + footer
    parsed = codec.sound_from_messages(messages)
    assert (parsed.page, parsed.set_no, parsed.device_no) == (1, 1, 0)
    assert parsed.sound == sound_1_1


def test_sound_from_messages_any_order(sound_1_1):
    messages = codec.sound_to_messages(0, 1, 1, sound_1_1)
    assert codec.sound_from_messages(list(reversed(messages))).sound == sound_1_1


def test_sound_to_messages_rejects_out_of_range_page_set(sound_1_1):
    with pytest.raises(ValueError, match="page must be"):
        codec.sound_to_messages(0, paramap.PAGE_COUNT + 1, 1, sound_1_1)
    with pytest.raises(ValueError, match="set must be"):
        codec.sound_to_messages(0, 1, 0, sound_1_1)


def test_sound_from_messages_rejects_multiple_headers(sound_1_1):
    messages = codec.sound_to_messages(0, 1, 1, sound_1_1)
    with pytest.raises(ValueError, match="multiple Bulk Header"):
        codec.sound_from_messages(messages + [messages[0]])


def test_sound_from_messages_rejects_duplicate_block(sound_1_1):
    messages = codec.sound_to_messages(0, 1, 1, sound_1_1)
    with pytest.raises(ValueError, match="duplicate data block"):
        codec.sound_from_messages(messages + [messages[1]])


def test_sound_from_messages_rejects_missing_block(sound_1_1):
    messages = codec.sound_to_messages(0, 1, 1, sound_1_1)
    with pytest.raises(ValueError, match="missing block 'soundmondo'"):
        codec.sound_from_messages(messages[:1] + messages[2:])


def test_sound_from_messages_rejects_mixed_device_numbers(sound_1_1):
    messages = codec.sound_to_messages(0, 1, 1, sound_1_1)
    other_dev = codec.sound_to_messages(1, 1, 1, sound_1_1)
    with pytest.raises(ValueError, match="multiple device numbers"):
        codec.sound_from_messages([messages[0]] + other_dev[1:])


def test_sound_from_messages_rejects_mismatched_footer(sound_1_1):
    messages = codec.sound_to_messages(0, 1, 1, sound_1_1)
    wrong_footer = sysex.build_bulk_dump(0, paramap.footer_addr(0, 1), b"")
    with pytest.raises(ValueError, match="does not match Bulk Header"):
        codec.sound_from_messages(messages[:-1] + [wrong_footer])


def test_iter_sounds_from_messages(sound_1_1):
    stream = (codec.sound_to_messages(0, 1, 1, sound_1_1)
              + codec.sound_to_messages(0, 2, 3, sound_1_1))
    results = list(codec.iter_sounds_from_messages(stream))
    assert [(r.page, r.set_no) for r in results] == [(1, 1), (2, 3)]
    assert all(r.sound == sound_1_1 for r in results)


def test_iter_sounds_ignores_strays_outside_bracket(sound_1_1):
    messages = codec.sound_to_messages(0, 1, 1, sound_1_1)
    stream = [messages[1]] + messages  # stray data block before the header
    results = list(codec.iter_sounds_from_messages(stream))
    assert [(r.page, r.set_no) for r in results] == [(1, 1)]


def test_iter_sounds_rejects_unterminated_group(sound_1_1):
    messages = codec.sound_to_messages(0, 1, 1, sound_1_1)
    with pytest.raises(ValueError, match="unterminated"):
        list(codec.iter_sounds_from_messages(messages[:-1]))


def test_iter_sounds_rejects_header_inside_group(sound_1_1):
    messages = codec.sound_to_messages(0, 1, 1, sound_1_1)
    with pytest.raises(ValueError, match="Bulk Header inside"):
        list(codec.iter_sounds_from_messages(messages[:-1] + messages))


def test_name_field_max_length(sound_1_1):
    with pytest.raises(pydantic.ValidationError, match="at most 15 characters"):
        sound_1_1.common.name = "A" * 16


def test_name_field_rejects_non_ascii(sound_1_1):
    with pytest.raises(pydantic.ValidationError, match="pattern"):
        sound_1_1.common.name = "Grüße"


def test_name_field_strips_trailing_nulls(sound_1_1):
    sound_1_1.common.name = "Foo\x00\x00"
    assert sound_1_1.common.name == "Foo"


def test_encode_block_rejects_overlong_values(sound_1_1):
    # model_copy(update=...) bypasses pydantic validation, so the encoder's
    # own guards are the last line of defense against corrupting a block.
    bad_common = sound_1_1.common.model_copy(update={"name": "A" * 16})
    with pytest.raises(ValueError, match="exceeds 15 bytes"):
        codec._encode_block(bad_common, paramap.COMMON_FIELDS, paramap.COMMON_SIZE)
    bad_additional = sound_1_1.additional.model_copy(update={"tempo_raw": [1, 2, 3]})
    with pytest.raises(ValueError, match="expected 2 bytes"):
        codec._encode_block(bad_additional, paramap.ADDITIONAL_FIELDS, paramap.ADDITIONAL_SIZE)
