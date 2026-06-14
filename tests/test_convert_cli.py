from __future__ import annotations

import io
import json
import os
import tempfile

import pytest
from ruamel.yaml import YAML

from cp_liveset import LiveSetCollection, init_sound, x9format
from cp_liveset.cli import main as cli_main
from cp_liveset.soundmodels import LiveSetSound

from _samples import make_sample_doc

# A multi-sound input source, written to a JSON file once for the whole module
# (used wherever a test just needs several real sounds to convert from).
_fd, _SAMPLE_PATH = tempfile.mkstemp(suffix=".json")
with os.fdopen(_fd, "w", encoding="utf-8") as _f:
    json.dump(make_sample_doc(), _f)
DEFAULTS_SRC = f"json:{_SAMPLE_PATH}"


def _as_sound(v):
    return v if isinstance(v, LiveSetSound) else LiveSetSound.model_validate(v)


def _blobs(group):
    return {key: x9format.sound_to_blob(_as_sound(sound)) for key, sound in group.items()}


def _read_json_group(path) -> LiveSetCollection:
    with open(path, "r", encoding="utf-8") as f:
        return LiveSetCollection.from_json(json.load(f))


def _write_json_group(group, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(LiveSetCollection(group).to_json(), f)


def _read_x9_group(path) -> LiveSetCollection:
    with open(path, "rb") as f:
        return LiveSetCollection.from_x9(f.read())


def test_convert_produces_no_output_on_success(tmp_path, capsys):
    out = tmp_path / "out.json"
    cli_main(["convert", "-i", DEFAULTS_SRC, "1:1", "-o", f"json:{out}"])
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_convert_json_stdout_stdin(capsys, factory_doc, monkeypatch):
    cli_main(["convert", "-i", DEFAULTS_SRC, "1:1", "-o", "json:-"])
    written = capsys.readouterr().out

    monkeypatch.setattr("sys.stdin", io.StringIO(written))
    cli_main(["convert", "-i", "json:-", "-o", "yaml:-"])
    out = capsys.readouterr().out
    assert f'name: {factory_doc["pages"]["1"]["1"]["common"]["name"].rstrip(" ")}' in out


def test_convert_defaults_remap_to_x9p(tmp_path, factory_doc):
    out = tmp_path / "page5.X9P"
    cli_main(["convert", "-i", DEFAULTS_SRC, "1:1-8=5:1-8", "-o", f"x9p:{out}"])
    group = _read_x9_group(out)
    assert set(group) == {(5, s) for s in range(1, 9)}
    expected = {(5, s): factory_doc["pages"]["1"][str(s)] for s in range(1, 9)}
    assert _blobs(group) == _blobs(expected)


def test_convert_defaults_remap_to_x9s(tmp_path, factory_doc):
    out = tmp_path / "set.X9S"
    cli_main(["convert", "-i", DEFAULTS_SRC, "1:1=12:3", "-o", f"x9s:{out}"])
    group = _read_x9_group(out)
    assert _blobs(group) == _blobs({(12, 3): factory_doc["pages"]["1"]["1"]})


def test_convert_x9s_read_side_page_override_keeps_set(tmp_path, factory_doc):
    src = tmp_path / "set.X9S"
    cli_main(["convert", "-i", DEFAULTS_SRC, "1:1=3:5", "-o", f"x9s:{src}"])

    out = tmp_path / "out.json"
    cli_main(["convert", "-i", f"x9s:{src}:7", "-o", f"json:{out}"])
    assert set(_read_json_group(out)) == {(7, 5)}


def test_convert_x9s_read_side_page_and_set_override(tmp_path, factory_doc):
    src = tmp_path / "set.X9S"
    cli_main(["convert", "-i", DEFAULTS_SRC, "1:1=3:5", "-o", f"x9s:{src}"])

    out = tmp_path / "out.json"
    cli_main(["convert", "-i", f"x9s:{src}:7:2", "-o", f"json:{out}"])
    assert set(_read_json_group(out)) == {(7, 2)}


def test_convert_x9p_read_side_page_override(tmp_path, factory_doc):
    src = tmp_path / "page1.X9P"
    cli_main(["convert", "-i", DEFAULTS_SRC, "1:1-8", "-o", f"x9p:{src}"])

    out = tmp_path / "out.json"
    cli_main(["convert", "-i", f"x9p:{src}:9", "-o", f"json:{out}"])
    assert set(_read_json_group(out)) == {(9, s) for s in range(1, 9)}


def test_convert_x9p_write_side_page_override_mixed_sources(tmp_path, factory_doc):
    out = tmp_path / "page9.X9P"
    cli_main(["convert", "-i", DEFAULTS_SRC, "1:1", "3:2", "-o", f"x9p:{out}:9"])
    group = _read_x9_group(out)
    assert set(group) == {(9, s) for s in range(1, 9)}
    assert _blobs({0: group[(9, 1)]}) == _blobs({0: factory_doc["pages"]["1"]["1"]})
    assert _blobs({0: group[(9, 2)]}) == _blobs({0: factory_doc["pages"]["3"]["2"]})


def test_convert_x9p_write_side_conflicting_set_numbers_errors(tmp_path):
    out = tmp_path / "page9.X9P"
    with pytest.raises(SystemExit):
        cli_main(["convert", "-i", DEFAULTS_SRC, "1:1", "3:1", "-o", f"x9p:{out}:9"])


def test_convert_cardinality_mismatch_errors(tmp_path):
    out = tmp_path / "out.json"
    with pytest.raises(SystemExit):
        cli_main(["convert", "-i", DEFAULTS_SRC, "1:1=5:1-2", "-o", f"json:{out}"])


def test_convert_rtmidi_input_unknown_port_errors(tmp_path):
    out = tmp_path / "out.json"
    with pytest.raises(SystemExit):
        cli_main(["convert", "-i", "rtmidi:NoSuchPortXYZ", "1:*", "-o", f"json:{out}"])


def test_convert_rtmidi_input_no_spec_downloads_only_what_output_needs(
        device_port_spec, tmp_path, factory_doc):
    out = tmp_path / "out.json"
    # no selection on -i: only the (1,1) pair the -o spec needs is downloaded.
    cli_main(["convert", "-i", f"rtmidi:{device_port_spec}", "-o", f"json:{out}", "1:1"])
    group = _read_json_group(out)
    assert set(group) == {(1, 1)}
    assert group[(1, 1)].common.name


def test_convert_multiple_inputs_merge(tmp_path, factory_doc):
    out = tmp_path / "out.json"
    cli_main([
        "convert",
        "-i", DEFAULTS_SRC, "1:1-8=1:1-8",
        "-i", DEFAULTS_SRC, "2:3=1:5",
        "-o", f"json:{out}",
    ])
    group = _read_json_group(out)
    assert set(group) == {(1, s) for s in range(1, 9)}
    for s in range(1, 9):
        if s == 5:
            assert group[(1, 5)] == _as_sound(factory_doc["pages"]["2"]["3"])
        else:
            assert group[(1, s)] == _as_sound(factory_doc["pages"]["1"][str(s)])


def test_convert_multiple_outputs(tmp_path, factory_doc):
    out1 = tmp_path / "out1.json"
    out2 = tmp_path / "out2.json"
    cli_main(["convert", "-i", DEFAULTS_SRC, "1:1=1:1", "-o", f"json:{out1}", "-o", f"json:{out2}"])
    expected = {(1, 1): _as_sound(factory_doc["pages"]["1"]["1"])}
    assert _read_json_group(out1) == expected
    assert _read_json_group(out2) == expected


def _load_yaml(text):
    return YAML().load(io.StringIO(text))


def test_convert_single_command_two_independent_streams(tmp_path, factory_doc):
    # Two independent input->output "streams" handled by a single 'convert'
    # invocation, both addressed at 1:1 on their respective endpoints, both
    # also landing on slot 1:1 of the shared working set (a literal
    # collision). Left-to-right processing means: -i Ai merges into the
    # working set, -o Ao snapshots it (== Ai), then -i Bi overwrites slot
    # 1:1 in the working set, and -o Bo snapshots that (== Bi).
    ai, bi = tmp_path / "ai.json", tmp_path / "bi.json"
    ao, bo = tmp_path / "ao.json", tmp_path / "bo.json"

    sound_a = _as_sound(factory_doc["pages"]["1"]["1"])
    sound_b = _as_sound(factory_doc["pages"]["2"]["1"])
    assert sound_a != sound_b

    _write_json_group({(1, 1): sound_a}, str(ai))
    _write_json_group({(1, 1): sound_b}, str(bi))

    cli_main([
        "convert",
        "-i", f"json:{ai}", "1:1",
        "-o", f"json:{ao}",
        "-i", f"json:{bi}", "1:1",
        "-o", f"json:{bo}",
    ])

    assert _read_json_group(ao) == {(1, 1): sound_a}
    assert _read_json_group(bo) == {(1, 1): sound_b}
    assert _read_json_group(ao) == _read_json_group(ai)
    assert _read_json_group(bo) == _read_json_group(bi)


def test_convert_overwrite_prompt_accepted(tmp_path, factory_doc, monkeypatch):
    out = tmp_path / "out.json"
    out.write_text("stale")
    monkeypatch.setattr("builtins.input", lambda prompt: "y")
    cli_main(["convert", "-i", DEFAULTS_SRC, "1:1", "-o", f"json:{out}"])
    assert set(_read_json_group(out)) == {(1, 1)}


def test_convert_overwrite_prompt_declined(tmp_path, monkeypatch):
    out = tmp_path / "out.json"
    out.write_text("stale")
    monkeypatch.setattr("builtins.input", lambda prompt: "n")
    with pytest.raises(SystemExit):
        cli_main(["convert", "-i", DEFAULTS_SRC, "1:1", "-o", f"json:{out}"])
    assert out.read_text() == "stale"


def test_convert_overwrite_yes_skips_prompt(tmp_path, factory_doc, monkeypatch):
    out = tmp_path / "out.json"
    out.write_text("stale")

    def _no_input(prompt):
        raise AssertionError("should not prompt with --yes")
    monkeypatch.setattr("builtins.input", _no_input)
    cli_main(["convert", "-i", DEFAULTS_SRC, "1:1", "-o", f"json:{out}", "--yes"])
    assert set(_read_json_group(out)) == {(1, 1)}


def test_convert_overwrite_no_errors_without_prompt(tmp_path, monkeypatch):
    out = tmp_path / "out.json"
    out.write_text("stale")

    def _no_input(prompt):
        raise AssertionError("should not prompt with --no")
    monkeypatch.setattr("builtins.input", _no_input)
    with pytest.raises(SystemExit):
        cli_main(["convert", "-i", DEFAULTS_SRC, "1:1", "-o", f"json:{out}", "--no"])
    assert out.read_text() == "stale"


def test_convert_no_prompt_for_new_file(tmp_path, factory_doc, monkeypatch):
    out = tmp_path / "out.json"

    def _no_input(prompt):
        raise AssertionError("should not prompt for a new file")
    monkeypatch.setattr("builtins.input", _no_input)
    cli_main(["convert", "-i", DEFAULTS_SRC, "1:1", "-o", f"json:{out}"])
    assert set(_read_json_group(out)) == {(1, 1)}


def test_convert_no_input_x9p_with_page_all_init_sound(tmp_path):
    out = tmp_path / "blank.X9P"
    cli_main(["convert", "-o", f"x9p:{out}:5"])
    group = _read_x9_group(out)
    assert set(group) == {(5, s) for s in range(1, 9)}
    for s in range(1, 9):
        assert _blobs({0: group[(5, s)]}) == _blobs({0: init_sound()})


def test_convert_no_input_x9l_all_init_sound(tmp_path):
    out = tmp_path / "blank.X9L"
    cli_main(["convert", "-o", f"x9l:{out}"])
    group = _read_x9_group(out)
    for page in range(1, x9format.X9L_PAGE_COUNT + 1):
        for s in range(1, 9):
            assert _blobs({0: group[(page, s)]}) == _blobs({0: init_sound()})


def test_convert_no_input_x9s_with_identity_init_sound(tmp_path):
    out = tmp_path / "blank.X9S"
    cli_main(["convert", "-o", f"x9s:{out}:12:2"])
    group = _read_x9_group(out)
    assert set(group) == {(12, 2)}
    assert _blobs(group) == _blobs({(12, 2): init_sound()})


def test_convert_no_input_x9s_without_set_errors(tmp_path):
    out = tmp_path / "blank.X9S"
    with pytest.raises(SystemExit):
        cli_main(["convert", "-o", f"x9s:{out}:12"])


def test_convert_no_input_x9p_without_page_errors(tmp_path):
    out = tmp_path / "blank.X9P"
    with pytest.raises(SystemExit):
        cli_main(["convert", "-o", f"x9p:{out}"])


def test_convert_no_output_validates_input(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text('{"format": "not-the-right-format", "pages": {}}')
    with pytest.raises(SystemExit):
        cli_main(["convert", "-i", f"json:{bad}"])


def test_convert_output_before_input(tmp_path, factory_doc):
    # Under left-to-right processing, an -o before any -i takes its snapshot
    # of the (still-empty) working set before the later -i merges anything
    # into it, so the output ends up empty (even though the input itself is
    # read during phase 1).
    out = tmp_path / "out.json"
    cli_main(["convert", "-o", f"json:{out}", "-i", DEFAULTS_SRC, "1:1"])
    assert set(_read_json_group(out)) == set()


def test_convert_no_prompt_for_stdout(capsys, factory_doc, monkeypatch):
    def _no_input(prompt):
        raise AssertionError("should not prompt for stdout")
    monkeypatch.setattr("builtins.input", _no_input)
    cli_main(["convert", "-i", DEFAULTS_SRC, "1:1", "-o", "json:-"])
    capsys.readouterr()


def test_convert_midi_file_roundtrip(tmp_path, factory_doc):
    mid = tmp_path / "sets.mid"
    out = tmp_path / "out.json"
    cli_main(["convert", "-i", DEFAULTS_SRC, "1:1-2", "-o", f"midi:{mid}"])
    cli_main(["convert", "-i", f"midi:{mid}", "-o", f"json:{out}"])
    group = _read_json_group(out)
    assert set(group) == {(1, 1), (1, 2)}
    assert group[(1, 1)] == _as_sound(factory_doc["pages"]["1"]["1"])


def test_convert_syx_file_roundtrip(tmp_path, factory_doc):
    syx = tmp_path / "sets.syx"
    out = tmp_path / "out.json"
    cli_main(["convert", "-i", DEFAULTS_SRC, "1:1-2", "-o", f"syx:{syx}"])
    # a .syx file is a bare concatenation of F0..F7 SysEx messages
    raw = syx.read_bytes()
    assert raw[0] == 0xF0 and raw[-1] == 0xF7
    cli_main(["convert", "-i", f"syx:{syx}", "-o", f"json:{out}"])
    group = _read_json_group(out)
    assert set(group) == {(1, 1), (1, 2)}
    assert group[(1, 1)] == _as_sound(factory_doc["pages"]["1"]["1"])


def test_convert_syx_inferred_from_extension(tmp_path):
    syx = tmp_path / "sets.syx"
    out = tmp_path / "out.json"
    cli_main(["convert", "-i", DEFAULTS_SRC, "1:1", "-o", str(syx)])
    cli_main(["convert", "-i", str(syx), "-o", str(out)])
    assert set(_read_json_group(out)) == {(1, 1)}


def test_inspect_json(tmp_path, factory_doc, capsys):
    src = tmp_path / "src.json"
    _write_json_group({(1, 1): _as_sound(factory_doc["pages"]["1"]["1"])}, str(src))
    cli_main(["inspect", f"json:{src}"])
    out = _load_yaml(capsys.readouterr().out)
    assert out == {1: {1: factory_doc["pages"]["1"]["1"]["common"]["name"].rstrip(" ")}}


def test_inspect_rtmidi_without_device_errors():
    with pytest.raises(SystemExit):
        cli_main(["inspect", "rtmidi:NoSuchPortXYZ"])


def test_inspect_with_spec(capsys, factory_doc):
    cli_main(["inspect", DEFAULTS_SRC, "1:5", "2:1-3"])
    out = _load_yaml(capsys.readouterr().out)
    assert out == {
        1: {5: factory_doc["pages"]["1"]["5"]["common"]["name"].rstrip(" ")},
        2: {
            1: factory_doc["pages"]["2"]["1"]["common"]["name"].rstrip(" "),
            2: factory_doc["pages"]["2"]["2"]["common"]["name"].rstrip(" "),
            3: factory_doc["pages"]["2"]["3"]["common"]["name"].rstrip(" "),
        },
    }


def test_inspect_rejects_remap_spec():
    with pytest.raises(SystemExit):
        cli_main(["inspect", DEFAULTS_SRC, "1:1=2:1"])


def test_select_writes_midi_file(tmp_path, capsys):
    import mido

    out = tmp_path / "switch.mid"
    cli_main(["select", f"midi:{out}", "7:3"])
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""
    mid = mido.MidiFile(str(out))
    msgs = [m for m in mid.tracks[0] if not m.is_meta]
    assert [m.type for m in msgs] == ["control_change", "control_change", "program_change"]
    assert msgs[1].value == 6  # page 7 -> LSB 6
    assert msgs[2].program == 2  # set 3 -> program 2


def test_select_invalid_sound_id_errors():
    with pytest.raises(SystemExit):
        cli_main(["select", "midi:switch.mid", "41:1"])


def test_select_rejects_non_midi_rtmidi_endpoint(tmp_path):
    out = tmp_path / "out.json"
    with pytest.raises(SystemExit):
        cli_main(["select", f"json:{out}", "7:3"])


def test_select_rtmidi(device_port_spec, capsys):
    cli_main(["select", f"rtmidi:{device_port_spec}", "1:1"])
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""
