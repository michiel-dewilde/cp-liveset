"""
Lookup tables and default values used by the concise `yaml` Live Set format
(see yamlformat.py).

FIELD_DEFAULTS: the "standard"/default value for every (block_key, field_name)
pair that appears in a Live Set Sound dict (LiveSetSound.model_dump()). Stored
in data/field_defaults.json, originally computed as the mode (most common
value) across all 160 Live Set Sounds of a factory-reset CP88, with two
explicit overrides per the YAML format spec:

  - `section_switch` always defaults to 0 (off), regardless of the computed
    mode (Piano's mode is 1/on, since it's on in most factory presets).
  - `category{N}_voice_number` defaults to 0 (displayed as instrument 1).
    These are also always shown explicitly (as `instrument:`) whenever the
    section is on, even when equal to the default.

All enum/lookup tables below are taken from
CP88_CP73_supplementary_manual_En_v200_H0.pdf ("MIDI Data Table" /
"MIDI PARAMETER CHANGE TABLE (BULK CONTROL)", pages 14-25) and
cp88_cp73_en_om_d0_text/06_DATA LIST.xlsx ("Voice List" /
"Control Change Number List" sheets, from Yamaha's CP88/CP73 Data List
.zip download). The supplementary manual:
  https://data.yamaha.com/files/download/other_assets/7/1243337/CP88_CP73_supplementary_manual_En_v200_H0.pdf
"""

from __future__ import annotations

import json
from importlib import resources

# ---------------------------------------------------------------------------
# Field defaults
# ---------------------------------------------------------------------------


def _load_field_defaults() -> dict:
    with resources.files(__package__).joinpath("data/field_defaults.json").open(
            "r", encoding="utf-8") as f:
        defaults = json.load(f)
    for sec in ("piano", "epiano", "sub"):
        defaults[f"section_{sec}_common.section_switch"] = 0
        defaults[f"section_{sec}_common.category1_voice_number"] = 0
        defaults[f"section_{sec}_common.category2_voice_number"] = 0
        defaults[f"section_{sec}_common.category3_voice_number"] = 0
        defaults[f"section_{sec}_common.category4_voice_number"] = 0
    return defaults


FIELD_DEFAULTS = _load_field_defaults()


# ---------------------------------------------------------------------------
# Voice List (CP88_CP73_supplementary_manual_En_v200_H0.pdf, pages 9-10,
# "Additional new Voices" / "Voice List", firmware v2.00+).
#
# This supersedes the smaller table in CP88_owners_manual_En_F0.pdf (page 39):
# each Voice section still has 4 categories selected by the "Voice category
# selector" rotary, but firmware v2.00 added many more voices per category,
# no longer numbered contiguously across a single 1-57 space (e.g. "CFX2" and
# "Imperial+" are addressed via a different CC than the rest of "Grand
# Piano"). The "categoryN_voice_number" field is therefore the 0-based
# position ("No." - 1) of the voice within its category's list below, as
# selected by the "Voice select switch".
#
# Per section: ordered list of (category_name, [voice_name, ...]) in "No."
# order; categoryN_voice_number = list index.
# ---------------------------------------------------------------------------

SECTION_CATEGORIES = {
    "piano": [
        ("Grand Piano", [
            "CFX", "Imperial", "S700", "Digi Piano", "C7", "CF3",
            "Nashville C3", "Live CF3", "Hamburg Grand", "CFX2", "Imperial+",
        ]),
        ("Upright Piano", ["U1", "SU7", "Felt Piano"]),
        ("CP", ["CP80 1", "CP80 2"]),
        ("Layered Piano", ["Piano Strings", "Piano Synth"]),
    ],
    "epiano": [
        ("Rd", [
            "78Rd", "75Rd Funky", "73Rd", "67Rd Dark", "67Rd Bright",
            "73Rd Studio", "74Rd Stage",
        ]),
        ("Wr", ["Wr Warm", "Wr Bright", "Wr Wide"]),
        ("Clv", ["Clavi B", "Clavi S", "Harpsichord"]),
        ("DX", ["DX Legend", "DX Woody", "DX FTine", "DX 7 II", "DX Mellow", "DX Crisp"]),
    ],
    "sub": [
        ("Pad/Strings", [
            "Mellow Pad", "Spectrum", "Back Pad", "Air Choir", "Natural Str",
            "Warm Strings", "OB Strings", "Section Str", "Fat Saw Pad",
            "Noble Pad", "Pop Pad", "Analog Pad", "Itopia", "Marcato Str",
            "Slow Str", "Tape Str", "Oct Syn Str", "Angel Pad", "Mystic Pad",
            "JP Strings", "Pop Syn Str", "Fast Strings", "Pizzicato",
            "Dark Light", "Digi Pad", "Lite Strings", "Unison Str", "Violin",
            "Cello",
        ]),
        ("Organ", [
            "Bright Bars", "Click Organ", "Draw Organ 1", "All Bars Out",
            "Draw Organ 2", "60s Combo", "Compact", "Panther", "Pipe Organ 1",
            "Pipe Organ 2", "Accordion", "Musette",
        ]),
        ("Chromatic Perc.", [
            "Glocken", "Vibraphone", "Xylophone", "Marimba", "Brightness",
            "Nice Bell", "Stack Bell", "Jazz Vibes", "Marimba 2", "Kalimba",
            "Heaven Bell",
        ]),
        ("Others", [
            "Syn Lead 1", "Syn Lead 2", "Syn Bass", "E.Bass", "A.Bass",
            "Steel Gt", "Clean Gt", "Syn Brass", "Sine Lead", "Sync Saw",
            "Dirty Hook", "Classic Mini", "Funky Mini", "Nu Mini",
            "80s Pop Bass", "Sub Bass", "Unison Bass", "Finger Bass", "Brass",
            "Syn Brass 2", "OB Brass 1", "OB Brass 2", "Jazz Flute",
            "Tape Flute", "Harmonica", "Classic Gt", "Steel Gt 2", "Sf. Brass",
            "12Strings Gt", "Clean Gt 2", "Syn Brass 3", "Horn", "Sax Section",
            "Soprano Sax", "Alto Sax", "Tenor Sax", "Baritone Sax",
            "Soft Square", "Calliope Lead", "1o1 Bass",
        ]),
    ],
}


def category_name(section: str, category_index: int) -> str:
    """The category name as printed on the control panel (used verbatim in
    the `category:` field and as `instrument:` map keys)."""
    return SECTION_CATEGORIES[section][category_index][0]


def category_index_from_name(section: str, name: str) -> int | None:
    for i, (cat_name, _voices) in enumerate(SECTION_CATEGORIES[section]):
        if cat_name == name:
            return i
    return None


# ---------------------------------------------------------------------------
# Advanced Sound Mode: a single global Voice List (Voice List "No." 1-127,
# CC88_CP73_supplementary_manual_En_v200_H0.pdf pages 9-10), spanning all 3
# sections' voices combined ("Advanced Sound Mode Voice Number" raw =
# No. - 1, confirmed against a live device). Numbers 128/129 are the two
# "Extra Voice" entries (CFX2/Imperial+), selected via
# advanced_sound_mode_voice_number == 0x7F together with
# advanced_sound_mode_extra_voice_number == 0/1. 130 (extra == 2) is unmapped.
# ---------------------------------------------------------------------------
ADVANCED_VOICES: dict[int, str] = {
    1: "CFX", 2: "Imperial", 3: "S700", 4: "Digi Piano",
    5: "U1", 6: "SU7",
    7: "CP80 1", 8: "CP80 2",
    9: "Piano Strings", 10: "Piano Synth",
    11: "78Rd", 12: "75Rd Funky", 13: "73Rd",
    14: "Wr Warm", 15: "Wr Bright",
    16: "Clavi B", 17: "Clavi S", 18: "Harpsichord",
    19: "DX Legend", 20: "DX Woody", 21: "DX FTine", 22: "DX 7 II", 23: "DX Mellow", 24: "DX Crisp",
    25: "Mellow Pad", 26: "Spectrum", 27: "Back Pad", 28: "Air Choir",
    29: "Natural Str", 30: "Warm Strings", 31: "OB Strings", 32: "Section Str",
    33: "Bright Bars", 34: "Click Organ", 35: "Draw Organ 1", 36: "All Bars Out",
    37: "Draw Organ 2", 38: "60s Combo", 39: "Compact", 40: "Panther", 41: "Pipe Organ 1", 42: "Pipe Organ 2",
    43: "Glocken", 44: "Vibraphone", 45: "Xylophone", 46: "Marimba", 47: "Brightness", 48: "Nice Bell", 49: "Stack Bell",
    50: "Syn Lead 1", 51: "Syn Lead 2", 52: "Syn Bass", 53: "E.Bass", 54: "A.Bass", 55: "Steel Gt", 56: "Clean Gt", 57: "Syn Brass",
    58: "C7",
    59: "67Rd Dark", 60: "67Rd Bright",
    61: "Wr Wide",
    62: "Fat Saw Pad", 63: "Noble Pad", 64: "Pop Pad", 65: "Analog Pad", 66: "Itopia", 67: "Marcato Str", 68: "Slow Str", 69: "Tape Str", 70: "Oct Syn Str",
    71: "Jazz Vibes", 72: "Marimba 2", 73: "Kalimba", 74: "Heaven Bell",
    75: "Sine Lead", 76: "Sync Saw", 77: "Dirty Hook", 78: "Classic Mini", 79: "Funky Mini", 80: "Nu Mini",
    81: "80s Pop Bass", 82: "Sub Bass", 83: "Unison Bass", 84: "Finger Bass", 85: "Brass", 86: "Syn Brass 2", 87: "OB Brass 1", 88: "OB Brass 2",
    89: "Jazz Flute", 90: "Tape Flute", 91: "Harmonica",
    92: "CF3", 93: "73Rd Studio", 94: "74Rd Stage", 95: "Nashville C3", 96: "Live CF3",
    97: "Angel Pad", 98: "Mystic Pad", 99: "JP Strings", 100: "Pop Syn Str", 101: "Fast Strings", 102: "Pizzicato",
    103: "Accordion",
    104: "Classic Gt", 105: "Steel Gt 2", 106: "Sf. Brass",
    107: "Hamburg Grand", 108: "Felt Piano",
    109: "Dark Light", 110: "Digi Pad", 111: "Lite Strings", 112: "Unison Str", 113: "Violin", 114: "Cello",
    115: "Musette",
    116: "12Strings Gt", 117: "Clean Gt 2", 118: "Syn Brass 3", 119: "Horn", 120: "Sax Section",
    121: "Soprano Sax", 122: "Alto Sax", 123: "Tenor Sax", 124: "Baritone Sax",
    125: "Soft Square", 126: "Calliope Lead", 127: "1o1 Bass",
    128: "CFX2", 129: "Imperial+",
}

_ADVANCED_VOICE_NUMBERS = {name: no for no, name in ADVANCED_VOICES.items()}


def advanced_voice_name(number: int) -> str | None:
    return ADVANCED_VOICES.get(number)


def advanced_voice_number(name: str) -> int | None:
    return _ADVANCED_VOICE_NUMBERS.get(name)


def advanced_number_to_raw(number: int) -> tuple[int, int]:
    """1-130 -> (advanced_sound_mode_voice_number, advanced_sound_mode_extra_voice_number)."""
    if 1 <= number <= 127:
        return number - 1, 0
    if 128 <= number <= 130:
        return 0x7F, number - 128
    raise ValueError(f"advanced voice number {number} out of range (1-130)")


def advanced_raw_to_number(voice_raw: int, extra_raw: int) -> int:
    """Inverse of advanced_number_to_raw."""
    if voice_raw == 0x7F:
        return 128 + extra_raw
    return voice_raw + 1


# ---------------------------------------------------------------------------
# Assignable controller (Modulation Lever / FC1 / FC2) targets
#
# cp88_cp73_en_om_d0_text/06_DATA LIST.xlsx, "Control Change Number List".
# Range is 0-63, 65, 67-118, 119 (USB Audio Volume); 64 (Sustain) and
# 66 (Sostenuto) cannot be selected.
# ---------------------------------------------------------------------------
CC_NAMES = {
    0: "Bank Select MSB",
    1: "Modulation",
    4: "Pedal Wah",
    5: "Portamento Time",
    6: "Data Entry MSB",
    7: "All Volume",
    10: "Pan",
    11: "Expression",
    12: "P: Select",
    13: "P: Volume",
    14: "P: Tone",
    15: "P: Damper Reso",
    16: "P: Effect SW",
    17: "P: Effect Depth",
    18: "E: Select",
    19: "E: Volume",
    20: "E: Tone",
    21: "E: Drive SW",
    22: "E: Drive Depth",
    23: "E: Effect 1 SW",
    24: "E: Effect 1 Depth",
    25: "E: Effect 1 Rate",
    26: "E: Effect 2 SW",
    27: "E: Effect 2 Depth",
    28: "E: Effect 2 Speed",
    29: "S: Select",
    30: "S: Volume",
    31: "S: Tone",
    32: "Bank Select LSB",
    38: "Data Entry LSB",
    65: "Portamento",
    67: "Soft",
    68: "S: Effect SW",
    71: "Resonance",
    72: "S: Release",
    73: "S: Attack",
    74: "Cutoff",
    75: "S: Effect Depth",
    76: "S: Effect Speed",
    77: "P: Delay Depth",
    78: "E: Delay Depth",
    79: "S: Delay Depth",
    80: "Delay Time",
    81: "P: Reverb Depth",
    82: "E: Reverb Depth",
    83: "S: Reverb Depth",
    84: "Portamento Ctrl",
    85: "Reverb Time",
    86: "Master EQ SW",
    87: "Master EQ High",
    88: "Master EQ Mid",
    89: "Master EQ Freq",
    90: "Master EQ Low",
    91: "All Reverb Depth",
    92: "Delay Feedback",
    93: "All Delay Depth",
    94: "Effect 4 Depth",
    95: "Effect 5 Depth",
    96: "Data Increment",
    97: "Data Decrement",
    98: "NRPN LSB",
    99: "NRPN MSB",
    100: "RPN LSB",
    101: "RPN MSB",
    102: "P: SW",
    103: "P: Split",
    104: "P: Octave",
    105: "P: Effect Type",
    106: "E: SW",
    107: "E: Split",
    108: "E: Octave",
    109: "E: Effect 1 Type",
    110: "E: Effect 2 Type",
    111: "S: SW",
    112: "S: Split",
    113: "S: Octave",
    114: "S: Effect Type",
    115: "Delay SW",
    116: "Delay Effect Type",
    117: "Reverb SW",
    118: "Depth Knob Select",
    119: "USB Audio Volume",
}


# ---------------------------------------------------------------------------
# Simple enums
# ---------------------------------------------------------------------------
DEPTH_KNOB_SECTION = {0: "All", 1: "Piano", 2: "E.Piano", 3: "Sub"}
DELAY_TYPE = {0: "Analog", 1: "Digital", 2: "Tempo"}
SPLIT_MODE = {0: "L&R", 1: "L", 2: "R"}
MONO_POLY = {0: "Mono", 1: "Poly"}
PORTAMENTO_MODE = {0: "Fingered", 1: "Full-time"}
PORTAMENTO_TIME_MODE = {0: "Rate", 1: "Time"}

PIANO_EFFECT_TYPE = {0: "Comp", 1: "Dist/OD", 2: "Drive", 3: "Chorus"}
EPIANO_EFFECT1_TYPE = {0: "A.Pan", 1: "Trem", 2: "R.Mod", 3: "T.Wah", 4: "P.Wah", 5: "Comp"}
EPIANO_EFFECT2_TYPE = {0: "Cho1", 1: "Cho2", 2: "Fla", 3: "Pha1", 4: "Pha2", 5: "Pha3"}
SUB_EFFECT_TYPE = {0: "Cho/Fla", 1: "Rotary", 2: "Trem", 3: "Dist/OD"}

TEMPO_DELAY_TIME = {
    0: "1/32 Tri.", 1: "1/64 Dot.", 2: "1/32", 3: "1/16 Tri.", 4: "1/32 Dot.",
    5: "1/16", 6: "1/8 Tri.", 7: "1/16 Dot.", 8: "1/8", 9: "1/4 Tri.",
    10: "1/8 Dot.", 11: "1/4", 12: "1/2 Tri.", 13: "1/4 Dot.", 14: "1/2",
}

# ---------------------------------------------------------------------------
# Note names (Split Point / Note Limit Low/High), C-2 - G8, raw 0-127
# (Yamaha numbering: note number 60 = C3)
# ---------------------------------------------------------------------------
_NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def note_name(raw: int) -> str:
    octave = raw // 12 - 2
    return f"{_NOTE_NAMES[raw % 12]}{octave}"


# ---------------------------------------------------------------------------
# Master EQ Frequency 3 (raw 0x0E-0x36 = 14-54)
# ---------------------------------------------------------------------------
_EQ_FREQ_LABELS = [
    "100Hz", "110Hz", "125Hz", "140Hz", "160Hz", "180Hz", "200Hz", "225Hz",
    "250Hz", "280Hz", "315Hz", "355Hz", "400Hz", "450Hz", "500Hz", "560Hz",
    "630Hz", "700Hz", "800Hz", "900Hz", "1.0kHz", "1.1kHz", "1.2kHz", "1.4kHz",
    "1.6kHz", "1.8kHz", "2.0kHz", "2.2kHz", "2.5kHz", "2.8kHz", "3.2kHz",
    "3.6kHz", "4.0kHz", "4.5kHz", "5.0kHz", "5.6kHz", "6.3kHz", "7.0kHz",
    "8.0kHz", "9.0kHz", "10kHz",
]
EQ_FREQ3 = {14 + i: label for i, label in enumerate(_EQ_FREQ_LABELS)}


# ---------------------------------------------------------------------------
# +/-64-centered values (octave shift, transpose, pan, EQ gain, pitch bend
# range, etc.): raw 0-127, displayed as a signed offset from 64.
# ---------------------------------------------------------------------------


def signed64(raw: int) -> int:
    return raw - 64


def unsigned64(value: int) -> int:
    return value + 64
