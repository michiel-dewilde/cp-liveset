from __future__ import annotations

import pytest

from cp_liveset import init_sound, x9format
from cp_liveset.soundmodels import LiveSetSound


def _as_sound(v):
    return v if isinstance(v, LiveSetSound) else LiveSetSound.model_validate(v)


def _init_sound_blob():
    return x9format.sound_to_blob(init_sound())


def test_x9_stores_newly_mapped_and_bit_expanded_fields(sound_1_1):
    s = sound_1_1
    s.zones[0].transmit_switches_1 = 21       # bits 0,2,4 - stored bit-expanded
    s.zones[2].transpose_octave = 66
    s.zones[1].transpose_semitone = 70
    s.master_eq.eq_gain1 = 80
    s.common.fc1_limit_low = 12
    s.sections.epiano.additional.pan = 90
    s.sections.piano.common.octave_shift = 65
    s.additional.tempo_raw = [5, 50]          # repacked 7-bit<->16-bit
    back = x9format.blob_to_sound(x9format.sound_to_blob(s))
    assert back.zones[0].transmit_switches_1 == 21
    assert back.zones[2].transpose_octave == 66
    assert back.zones[1].transpose_semitone == 70
    assert back.master_eq.eq_gain1 == 80
    assert back.common.fc1_limit_low == 12
    assert back.sections.epiano.additional.pan == 90
    assert back.sections.piano.common.octave_shift == 65
    assert back.additional.tempo_raw == [5, 50]


def test_blob_roundtrip_idempotent(sound_1_1):
    blob1 = x9format.sound_to_blob(sound_1_1)
    ls2 = x9format.blob_to_sound(blob1)
    blob2 = x9format.sound_to_blob(ls2)
    # the fields not stored in the X9 format are zeroed on first decode (bar
    # the format-version stamps, filled with constants the writer also omits),
    # so re-encoding the decoded LiveSetSound must reproduce the same blob.
    assert blob1 == blob2


def test_x9p_build_parse_roundtrip(factory_doc):
    page1 = {(1, s): _as_sound(factory_doc["pages"]["1"][str(s)]) for s in range(1, 9)}
    data = x9format.build_x9p(page1, 1, fill=init_sound())
    back = x9format.parse_container(data)

    assert set(back) == set(page1)
    for key, sound in page1.items():
        assert x9format.sound_to_blob(back[key]) == x9format.sound_to_blob(sound)


def test_x9p_fill_used_for_missing_sets(sound_1_1):
    data = x9format.build_x9p({(3, 1): sound_1_1}, 3, fill=init_sound())
    back = x9format.parse_container(data)
    assert set(back) == {(3, s) for s in range(1, 9)}
    assert x9format.sound_to_blob(back[(3, 1)]) == x9format.sound_to_blob(sound_1_1)
    for s in range(2, 9):
        assert x9format.sound_to_blob(back[(3, s)]) == _init_sound_blob()


def test_x9p_other_pages_ignored(sound_1_1):
    data = x9format.build_x9p({(4, 1): sound_1_1}, 3, fill=init_sound())
    back = x9format.parse_container(data)
    assert set(back) == {(3, s) for s in range(1, 9)}
    assert all(x9format.sound_to_blob(ls) == _init_sound_blob() for ls in back.values())


def test_x9s_build_parse_roundtrip(sound_1_1):
    data = x9format.build_x9s(3, 5, sound_1_1)
    back = x9format.parse_container(data)
    assert set(back) == {(3, 5)}
    assert x9format.sound_to_blob(back[(3, 5)]) == x9format.sound_to_blob(sound_1_1)


def test_x9l_build_parse_roundtrip(factory_doc):
    sounds = {
        (int(p), int(s)): _as_sound(ls)
        for p, sets in factory_doc["pages"].items() for s, ls in sets.items()
    }
    data = x9format.build_x9l(sounds, fill=init_sound())
    back = x9format.parse_container(data)

    # .X9L always holds all 160 slots (pages 1-20); the sample sounds occupy
    # their slots, every other slot is filled with Init Sound.
    assert set(back) == {(p, s) for p in range(1, 21) for s in range(1, 9)}
    init_blob = x9format.sound_to_blob(init_sound())
    for key in back:
        expected = sounds[key] if key in sounds else None
        if expected is not None:
            assert x9format.sound_to_blob(back[key]) == x9format.sound_to_blob(expected)
        else:
            assert x9format.sound_to_blob(back[key]) == init_blob


def test_x9l_rejects_pages_above_limit(sound_1_1):
    with pytest.raises(ValueError):
        x9format.build_x9l({(x9format.X9L_PAGE_COUNT + 1, 1): sound_1_1},
                            fill=init_sound())


def test_parse_container_rejects_non_ysfc():
    with pytest.raises(ValueError):
        x9format.parse_container(b"not a container at all")


def _rebuild_with_sections(data, sections):
    """Re-emit a YSFC container from (tag, raw-chunk) sections, fixing the
    catalogue offsets — a stand-in for a different-but-conformant writer."""
    import struct
    header = bytearray(data[:0x40])
    header[0x20:0x24] = struct.pack(">I", 8 * len(sections))
    out = bytearray(header) + bytearray(8 * len(sections))
    offs = []
    for _tag, chunk in sections:
        offs.append(len(out))
        out += chunk
    for i, (tag, _c) in enumerate(sections):
        o = 0x40 + 8 * i
        out[o:o + 4] = tag
        out[o + 4:o + 8] = struct.pack(">I", offs[i])
    return bytes(out)


def test_parse_is_catalogue_driven_not_position_dependent(sound_1_1):
    """A valid container whose chunks are reordered (and carries an unrelated
    chunk) must still parse: sections are resolved by the catalogue, not by a
    fixed position or order."""
    import struct

    data = x9format.build_x9l({(3, 5): sound_1_1}, fill=init_sound())
    cat = x9format._parse_catalogue(data)

    def section_bytes(off):
        ln = struct.unpack(">I", data[off + 4:off + 8])[0]
        return data[off:off + 8 + ln]

    sections = [(tag, section_bytes(off)) for tag, off in cat.items()]
    junk = (b"JUNK", b"JUNK" + struct.pack(">I", 4) + b"\xde\xad\xbe\xef")
    scrambled = _rebuild_with_sections(data, [junk, *reversed(sections)])

    expected = x9format.parse_container(data)
    actual = x9format.parse_container(scrambled)
    assert set(actual) == set(expected)
    for key in expected:
        assert x9format.sound_to_blob(actual[key]) == x9format.sound_to_blob(expected[key])
    assert actual[(3, 5)].common.name == sound_1_1.common.name


def test_parse_rejects_missing_dlst(sound_1_1):
    """An ELST present but no DLST in the catalogue is rejected by tag, not by
    silently mis-walking to whatever follows."""
    import struct

    data = x9format.build_x9s(3, 5, sound_1_1)
    cat = x9format._parse_catalogue(data)

    def section_bytes(off):
        ln = struct.unpack(">I", data[off + 4:off + 8])[0]
        return data[off:off + 8 + ln]

    elst = (b"ELST", section_bytes(cat[b"ELST"]))
    broken = _rebuild_with_sections(data, [elst])  # DLST dropped
    with pytest.raises(ValueError, match="DLST"):
        x9format.parse_container(broken)
