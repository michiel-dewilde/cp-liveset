from __future__ import annotations

import argparse

import pytest

from cp_liveset.cli import (
    _resolve_port,
    parse_endpoint,
    parse_sound_id,
    parse_select_endpoint,
)


def test_parse_endpoint_unknown_word_is_error():
    # 'defaults' was a former endpoint; it is now just an unknown bare word.
    with pytest.raises(argparse.ArgumentTypeError):
        parse_endpoint("defaults")


@pytest.mark.parametrize("fmt", ["json", "yaml", "x9a", "x9l"])
def test_parse_endpoint_simple_formats(fmt):
    assert parse_endpoint(f"{fmt}:myfile.ext") == (fmt, "myfile.ext")


def test_parse_endpoint_midi_no_device_id():
    assert parse_endpoint("midi:myfile.ext") == ("midi", ("myfile.ext", 0))


def test_parse_endpoint_midi_with_device_id():
    assert parse_endpoint("midi:myfile.mid:5") == ("midi", ("myfile.mid", 5))


def test_parse_endpoint_syx_with_device_id():
    assert parse_endpoint("syx:dump.syx:5") == ("syx", ("dump.syx", 5))


def test_parse_endpoint_infers_syx_from_extension():
    assert parse_endpoint("dump.syx") == ("syx", ("dump.syx", 0))


def test_parse_endpoint_midi_invalid_device_id():
    with pytest.raises(argparse.ArgumentTypeError):
        parse_endpoint("midi:myfile.mid:99")


def test_parse_endpoint_rtmidi_name_port():
    assert parse_endpoint("rtmidi:CP88") == ("rtmidi", ("CP88", "CP88", 0))


def test_parse_endpoint_rtmidi_name_port_with_device_id():
    assert parse_endpoint("rtmidi:CP88:5") == ("rtmidi", ("CP88", "CP88", 5))


def test_parse_endpoint_rtmidi_name_port_containing_colon():
    assert parse_endpoint("rtmidi:Foo:1:0") == ("rtmidi", ("Foo:1", "Foo:1", 0))
    assert parse_endpoint("rtmidi:Foo:1:5") == ("rtmidi", ("Foo:1", "Foo:1", 5))


def test_parse_endpoint_rtmidi_different_ports_by_number():
    assert parse_endpoint("rtmidi:1:2") == ("rtmidi", ("1", "2", 0))


def test_parse_endpoint_rtmidi_different_ports_by_number_with_device_id():
    assert parse_endpoint("rtmidi:1:2:5") == ("rtmidi", ("1", "2", 5))


def test_parse_endpoint_rtmidi_invalid_device_id():
    with pytest.raises(argparse.ArgumentTypeError):
        parse_endpoint("rtmidi:CP88:99")


def test_parse_endpoint_rtmidi_name_starting_with_digit_errors():
    with pytest.raises(argparse.ArgumentTypeError):
        parse_endpoint("rtmidi:5x:CP88")


def test_parse_endpoint_x9p_no_suffix():
    assert parse_endpoint("x9p:mypage.X9P") == ("x9p", ("mypage.X9P", None))


def test_parse_endpoint_x9p_with_page():
    assert parse_endpoint("x9p:mypage.X9P:7") == ("x9p", ("mypage.X9P", 7))


def test_parse_endpoint_x9p_invalid_page():
    with pytest.raises(argparse.ArgumentTypeError):
        parse_endpoint("x9p:mypage.X9P:41")


def test_parse_endpoint_x9s_no_suffix():
    assert parse_endpoint("x9s:myset.X9S") == ("x9s", ("myset.X9S", None, None))


def test_parse_endpoint_x9s_page_only():
    assert parse_endpoint("x9s:myset.X9S:3") == ("x9s", ("myset.X9S", 3, None))


def test_parse_endpoint_x9s_page_and_set():
    assert parse_endpoint("x9s:myset.X9S:3:7") == ("x9s", ("myset.X9S", 3, 7))


def test_parse_endpoint_x9s_invalid_set():
    with pytest.raises(argparse.ArgumentTypeError):
        parse_endpoint("x9s:myset.X9S:3:9")


def test_parse_endpoint_unknown_format():
    with pytest.raises(argparse.ArgumentTypeError):
        parse_endpoint("bogus:foo")


def test_parse_endpoint_missing_colon():
    with pytest.raises(argparse.ArgumentTypeError):
        parse_endpoint("noformat")


@pytest.mark.parametrize("ext, fmt", [
    ("json", "json"),
    ("yaml", "yaml"),
    ("yml", "yaml"),
    ("x9a", "x9a"),
    ("x9l", "x9l"),
])
def test_parse_endpoint_infers_format_from_extension(ext, fmt):
    assert parse_endpoint(f"myfile.{ext}") == (fmt, f"myfile.{ext}")


@pytest.mark.parametrize("ext", ["mid", "midi"])
def test_parse_endpoint_infers_midi_format_from_extension(ext):
    assert parse_endpoint(f"myfile.{ext}") == ("midi", (f"myfile.{ext}", 0))


def test_parse_endpoint_infers_format_case_insensitively():
    assert parse_endpoint("myfile.YAML") == ("yaml", "myfile.YAML")
    assert parse_endpoint("myfile.YML") == ("yaml", "myfile.YML")


def test_parse_endpoint_infers_x9p_no_suffix():
    assert parse_endpoint("mypage.X9P") == ("x9p", ("mypage.X9P", None))


def test_parse_endpoint_infers_x9p_with_page():
    assert parse_endpoint("mypage.X9P:7") == ("x9p", ("mypage.X9P", 7))


def test_parse_endpoint_infers_x9s_page_and_set():
    assert parse_endpoint("myset.X9S:3:7") == ("x9s", ("myset.X9S", 3, 7))


def test_parse_endpoint_infers_format_with_drive_letter():
    assert parse_endpoint(r"C:\data\myset.json") == ("json", r"C:\data\myset.json")


def test_parse_endpoint_infers_x9p_with_page_and_drive_letter():
    assert parse_endpoint(r"C:\data\mypage.X9P:7") == ("x9p", (r"C:\data\mypage.X9P", 7))


def test_parse_endpoint_no_extension_and_no_prefix_is_error():
    with pytest.raises(argparse.ArgumentTypeError):
        parse_endpoint("myfile")


def test_parse_endpoint_explicit_prefix_still_wins():
    # an explicit "yaml:" prefix is honored even if the location's own
    # extension would otherwise be inferred differently.
    assert parse_endpoint("yaml:myfile.json") == ("yaml", "myfile.json")


def test_parse_sound_id():
    assert parse_sound_id("7:3") == (7, 3)


def test_parse_sound_id_missing_colon():
    with pytest.raises(argparse.ArgumentTypeError):
        parse_sound_id("7")


def test_parse_sound_id_not_integers():
    with pytest.raises(argparse.ArgumentTypeError):
        parse_sound_id("a:b")


def test_parse_sound_id_page_out_of_range():
    with pytest.raises(argparse.ArgumentTypeError):
        parse_sound_id("41:1")


def test_parse_sound_id_set_out_of_range():
    with pytest.raises(argparse.ArgumentTypeError):
        parse_sound_id("1:9")


def test_parse_select_endpoint_midi():
    assert parse_select_endpoint("midi:switch.mid") == ("midi", ("switch.mid", 0))


def test_parse_select_endpoint_rtmidi():
    assert parse_select_endpoint("rtmidi:CP88") == ("rtmidi", ("CP88", "CP88", 0))


def test_parse_select_endpoint_rejects_other_formats():
    with pytest.raises(argparse.ArgumentTypeError):
        parse_select_endpoint("json:foo.json")


def test_resolve_port_by_number():
    assert _resolve_port("0", ["A 0", "B 1"], "input") == "A 0"
    assert _resolve_port("1", ["A 0", "B 1"], "input") == "B 1"


def test_resolve_port_by_name():
    names = ["CP88/CP73-1 0", "CP88/CP73-2 1"]
    assert _resolve_port("CP88/CP73-1 0", names, "input") == "CP88/CP73-1 0"
    assert _resolve_port("CP88/CP73-2 1", names, "output") == "CP88/CP73-2 1"


def test_resolve_port_by_unique_prefix():
    names = ["CP88/CP73-1 0", "CP88/CP73-2 1"]
    assert _resolve_port("CP88/CP73-1", names, "input") == "CP88/CP73-1 0"
    assert _resolve_port("CP88/CP73-2", names, "output") == "CP88/CP73-2 1"


def test_resolve_port_number_out_of_range():
    with pytest.raises(ValueError):
        _resolve_port("1", ["A 0"], "input")


def test_resolve_port_unknown_name():
    with pytest.raises(ValueError):
        _resolve_port("X", ["A 0"], "input")


def test_resolve_port_ambiguous_prefix():
    with pytest.raises(ValueError):
        _resolve_port("X", ["X 0", "X 1"], "input")
