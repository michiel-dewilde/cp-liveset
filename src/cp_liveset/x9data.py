"""
Field-position tables and baseline blob for the YSFC ".X9*" Live Set Sound
container formats (.X9A/.X9L/.X9P/.X9S).

Each Live Set Sound is stored as a fixed-size 367-byte "blob". The mapping
between blob bytes and the SysEx data blocks (paramap.py) was reverse-
engineered by sending sounds with controlled, distinctive values over MIDI,
exporting them from a CP88, and correlating every blob byte/bit against the
device's read-back model (the device clamps/forces many fields on MIDI
receive, so the read-back is the ground truth). It reproduces the device's
own export byte-for-byte and round-trips idempotently.

- FIELD_POSITIONS: model bytes stored directly, one blob byte each.
- BIT_POSITIONS: model bytes stored bit-expanded (the per-zone transmit
  switches), one blob byte per bit. Each zone uses 11 consecutive blob bytes:
  transmit_switches_1 bits [4,0,1,2,3] then transmit_switches_2 bits [0..5].
- REPACK_POSITIONS: a model field carried as two 7-bit SysEx bytes
  (msb*128 + lsb) but stored in the file as a 16-bit little-endian value in
  two 8-bit blob bytes (lo, hi). Only the tempo uses this.

189 of the 244 non-reserved fields are stored; the rest are genuinely
absent (mostly a section's inactive-instrument-type effect parameters, which
the device force-constants, plus format-version stamps). Absent fields decode
as 0, except the fixed format-version stamps (FIELD_POSITIONS-absent but
deterministic), which blob_to_sound fills from FIXED_VERSION_FIELDS. The blob's
8 trailing bytes are a device chunk (count 4 + 4 panel-only bytes) defaulting to
``00 00 00 04 40 40 40 40``.
"""

from __future__ import annotations

BLOB_SIZE = 367

# (block_key, field_name, sub_offset_within_field, blob_position)
FIELD_POSITIONS: list[tuple[str, str, int, int]] = [
    ('common', 'zone_mode_switch', 0, 25),
    ('common', 'advanced_zone_mode_switch', 0, 26),
    ('common', 'tg_transpose', 0, 27),
    ('common', 'split_point', 0, 28),
    ('common', 'depth_knob_section_select', 0, 31),
    ('common', 'modulation_lever_assign', 0, 32),
    ('common', 'modulation_lever_limit_low', 0, 33),
    ('common', 'modulation_lever_limit_high', 0, 34),
    ('common', 'fc1_assign', 0, 35),
    ('common', 'fc1_limit_low', 0, 36),
    ('common', 'fc1_limit_high', 0, 37),
    ('common', 'fc2_assign', 0, 38),
    ('common', 'fc2_limit_low', 0, 39),
    ('common', 'fc2_limit_high', 0, 40),
    ('common', 'live_set_eq_mode_switch', 0, 41),
    ('master_eq', 'eq_on_off', 0, 42),
    ('master_eq', 'eq_gain1', 0, 43),
    ('master_eq', 'eq_gain3', 0, 44),
    ('master_eq', 'eq_frequency3', 0, 45),
    ('master_eq', 'eq_gain5', 0, 46),
    ('common', 'delay_switch', 0, 51),
    ('common', 'delay_type', 0, 52),
    ('common', 'delay_time', 0, 53),
    ('common', 'delay_feedback', 0, 54),
    ('section_piano_common', 'delay_depth', 0, 55),
    ('section_epiano_common', 'delay_depth', 0, 56),
    ('section_sub_common', 'delay_depth', 0, 57),
    ('additional', 'tempo_delay_time', 0, 58),
    ('common', 'reverb_switch', 0, 65),
    ('common', 'reverb_time', 0, 66),
    ('section_piano_common', 'reverb_depth', 0, 67),
    ('section_epiano_common', 'reverb_depth', 0, 68),
    ('section_sub_common', 'reverb_depth', 0, 69),
    ('zone_0', 'zone_switch', 0, 78),
    ('zone_0', 'transmit_channel', 0, 79),
    ('zone_0', 'transpose_octave', 0, 80),
    ('zone_0', 'transpose_semitone', 0, 81),
    ('zone_0', 'note_limit_low', 0, 82),
    ('zone_0', 'note_limit_high', 0, 83),
    ('zone_0', 'midi_bank_msb', 0, 95),
    ('zone_0', 'midi_bank_lsb', 0, 96),
    ('zone_0', 'midi_program_number', 0, 97),
    ('zone_0', 'midi_volume', 0, 98),
    ('zone_0', 'midi_pan', 0, 99),
    ('zone_1', 'zone_switch', 0, 104),
    ('zone_1', 'transmit_channel', 0, 105),
    ('zone_1', 'transpose_octave', 0, 106),
    ('zone_1', 'transpose_semitone', 0, 107),
    ('zone_1', 'note_limit_low', 0, 108),
    ('zone_1', 'note_limit_high', 0, 109),
    ('zone_1', 'midi_bank_msb', 0, 121),
    ('zone_1', 'midi_bank_lsb', 0, 122),
    ('zone_1', 'midi_program_number', 0, 123),
    ('zone_1', 'midi_volume', 0, 124),
    ('zone_1', 'midi_pan', 0, 125),
    ('zone_2', 'zone_switch', 0, 130),
    ('zone_2', 'transmit_channel', 0, 131),
    ('zone_2', 'transpose_octave', 0, 132),
    ('zone_2', 'transpose_semitone', 0, 133),
    ('zone_2', 'note_limit_low', 0, 134),
    ('zone_2', 'note_limit_high', 0, 135),
    ('zone_2', 'midi_bank_msb', 0, 147),
    ('zone_2', 'midi_bank_lsb', 0, 148),
    ('zone_2', 'midi_program_number', 0, 149),
    ('zone_2', 'midi_volume', 0, 150),
    ('zone_2', 'midi_pan', 0, 151),
    ('zone_3', 'zone_switch', 0, 156),
    ('zone_3', 'transmit_channel', 0, 157),
    ('zone_3', 'transpose_octave', 0, 158),
    ('zone_3', 'transpose_semitone', 0, 159),
    ('zone_3', 'note_limit_low', 0, 160),
    ('zone_3', 'note_limit_high', 0, 161),
    ('zone_3', 'midi_bank_msb', 0, 173),
    ('zone_3', 'midi_bank_lsb', 0, 174),
    ('zone_3', 'midi_program_number', 0, 175),
    ('zone_3', 'midi_volume', 0, 176),
    ('zone_3', 'midi_pan', 0, 177),
    ('section_piano_common', 'current_category', 0, 186),
    ('section_piano_common', 'category1_voice_number', 0, 187),
    ('section_piano_common', 'category2_voice_number', 0, 188),
    ('section_piano_common', 'category3_voice_number', 0, 189),
    ('section_piano_common', 'category4_voice_number', 0, 190),
    ('section_piano_common', 'advanced_sound_mode_voice_number', 0, 191),
    ('section_piano_common', 'section_switch', 0, 192),
    ('section_piano_common', 'split_mode', 0, 193),
    ('section_piano_common', 'octave_shift', 0, 194),
    ('section_piano_common', 'section_volume', 0, 195),
    ('section_piano_common', 'tone', 0, 196),
    ('section_piano_common', 'pitch_bend_range', 0, 197),
    ('section_piano_common', 'pitch_modulation_depth', 0, 198),
    ('section_piano_common', 'receive_expression', 0, 199),
    ('section_piano_common', 'receive_sustain', 0, 200),
    ('section_piano_common', 'receive_sostenuto', 0, 201),
    ('section_piano_common', 'receive_soft', 0, 202),
    ('section_piano_common', 'advanced_sound_mode_switch', 0, 205),
    ('common', 'piano_pitch_modulation_speed', 0, 206),
    ('common', 'piano_touch_sensitivity_depth', 0, 207),
    ('common', 'piano_touch_sensitivity_offset', 0, 208),
    ('section_piano_additional', 'mono_poly', 0, 209),
    ('section_piano_additional', 'portamento_switch', 0, 210),
    ('section_piano_additional', 'portamento_time', 0, 211),
    ('section_piano_additional', 'portamento_mode', 0, 212),
    ('section_piano_additional', 'portamento_time_mode', 0, 213),
    ('section_piano_additional', 'pan', 0, 214),
    ('section_piano_specific', 'piano_damper_resonance_switch', 0, 219),
    ('section_piano_specific', 'piano_effect_switch', 0, 220),
    ('section_piano_specific', 'piano_effect_type', 0, 221),
    ('section_piano_specific', 'piano_effect_depth', 0, 222),
    ('section_piano_specific', 'piano_damper_resonance_damper_control', 0, 239),
    ('section_piano_specific', 'piano_damper_resonance_dry_wet_balance', 0, 240),
    ('section_epiano_common', 'current_category', 0, 245),
    ('section_epiano_common', 'category1_voice_number', 0, 246),
    ('section_epiano_common', 'category2_voice_number', 0, 247),
    ('section_epiano_common', 'category3_voice_number', 0, 248),
    ('section_epiano_common', 'category4_voice_number', 0, 249),
    ('section_epiano_common', 'advanced_sound_mode_voice_number', 0, 250),
    ('section_epiano_common', 'section_switch', 0, 251),
    ('section_epiano_common', 'split_mode', 0, 252),
    ('section_epiano_common', 'octave_shift', 0, 253),
    ('section_epiano_common', 'section_volume', 0, 254),
    ('section_epiano_common', 'tone', 0, 255),
    ('section_epiano_common', 'pitch_bend_range', 0, 256),
    ('section_epiano_common', 'pitch_modulation_depth', 0, 257),
    ('section_epiano_common', 'receive_expression', 0, 258),
    ('section_epiano_common', 'receive_sustain', 0, 259),
    ('section_epiano_common', 'receive_sostenuto', 0, 260),
    ('section_epiano_common', 'receive_soft', 0, 261),
    ('section_epiano_common', 'advanced_sound_mode_switch', 0, 264),
    ('common', 'epiano_pitch_modulation_speed', 0, 265),
    ('common', 'epiano_touch_sensitivity_depth', 0, 266),
    ('common', 'epiano_touch_sensitivity_offset', 0, 267),
    ('section_epiano_additional', 'mono_poly', 0, 268),
    ('section_epiano_additional', 'portamento_switch', 0, 269),
    ('section_epiano_additional', 'portamento_time', 0, 270),
    ('section_epiano_additional', 'portamento_mode', 0, 271),
    ('section_epiano_additional', 'portamento_time_mode', 0, 272),
    ('section_epiano_additional', 'pan', 0, 273),
    ('section_epiano_specific', 'epiano_effect1_switch', 0, 282),
    ('section_epiano_specific', 'epiano_effect1_type', 0, 283),
    ('section_epiano_specific', 'epiano_effect1_depth', 0, 284),
    ('section_epiano_specific', 'epiano_effect1_rate', 0, 285),
    ('section_epiano_specific', 'epiano_effect2_switch', 0, 286),
    ('section_epiano_specific', 'epiano_effect2_type', 0, 287),
    ('section_epiano_specific', 'epiano_effect2_depth', 0, 288),
    ('section_epiano_specific', 'epiano_effect2_speed', 0, 289),
    ('section_epiano_specific', 'epiano_drive_switch', 0, 290),
    ('section_epiano_specific', 'epiano_drive', 0, 291),
    ('section_sub_common', 'current_category', 0, 304),
    ('section_sub_common', 'category1_voice_number', 0, 305),
    ('section_sub_common', 'category2_voice_number', 0, 306),
    ('section_sub_common', 'category3_voice_number', 0, 307),
    ('section_sub_common', 'category4_voice_number', 0, 308),
    ('section_sub_common', 'advanced_sound_mode_voice_number', 0, 309),
    ('section_sub_common', 'section_switch', 0, 310),
    ('section_sub_common', 'split_mode', 0, 311),
    ('section_sub_common', 'octave_shift', 0, 312),
    ('section_sub_common', 'section_volume', 0, 313),
    ('section_sub_common', 'tone', 0, 314),
    ('section_sub_common', 'pitch_bend_range', 0, 315),
    ('section_sub_common', 'pitch_modulation_depth', 0, 316),
    ('section_sub_common', 'receive_expression', 0, 317),
    ('section_sub_common', 'receive_sustain', 0, 318),
    ('section_sub_common', 'receive_sostenuto', 0, 319),
    ('section_sub_common', 'receive_soft', 0, 320),
    ('section_sub_common', 'advanced_sound_mode_switch', 0, 323),
    ('common', 'sub_pitch_modulation_speed', 0, 324),
    ('common', 'sub_touch_sensitivity_depth', 0, 325),
    ('common', 'sub_touch_sensitivity_offset', 0, 326),
    ('section_sub_additional', 'mono_poly', 0, 327),
    ('section_sub_additional', 'portamento_switch', 0, 328),
    ('section_sub_additional', 'portamento_time', 0, 329),
    ('section_sub_additional', 'portamento_mode', 0, 330),
    ('section_sub_additional', 'portamento_time_mode', 0, 331),
    ('section_sub_additional', 'pan', 0, 332),
    ('section_sub_specific', 'sub_effect_switch', 0, 351),
    ('section_sub_specific', 'sub_effect_type', 0, 352),
    ('section_sub_specific', 'sub_effect_depth', 0, 353),
    ('section_sub_specific', 'sub_effect_speed', 0, 354),
    ('section_sub_specific', 'sub_attack', 0, 355),
    ('section_sub_specific', 'sub_release', 0, 356),
]

# (block_key, field_name, sub_offset_within_field, bit_index, blob_position)
BIT_POSITIONS: list[tuple[str, str, int, int, int]] = [
    ('zone_0', 'transmit_switches_1', 0, 4, 84),
    ('zone_0', 'transmit_switches_1', 0, 0, 85),
    ('zone_0', 'transmit_switches_1', 0, 1, 86),
    ('zone_0', 'transmit_switches_1', 0, 2, 87),
    ('zone_0', 'transmit_switches_1', 0, 3, 88),
    ('zone_0', 'transmit_switches_2', 0, 0, 89),
    ('zone_0', 'transmit_switches_2', 0, 1, 90),
    ('zone_0', 'transmit_switches_2', 0, 2, 91),
    ('zone_0', 'transmit_switches_2', 0, 3, 92),
    ('zone_0', 'transmit_switches_2', 0, 4, 93),
    ('zone_0', 'transmit_switches_2', 0, 5, 94),
    ('zone_1', 'transmit_switches_1', 0, 4, 110),
    ('zone_1', 'transmit_switches_1', 0, 0, 111),
    ('zone_1', 'transmit_switches_1', 0, 1, 112),
    ('zone_1', 'transmit_switches_1', 0, 2, 113),
    ('zone_1', 'transmit_switches_1', 0, 3, 114),
    ('zone_1', 'transmit_switches_2', 0, 0, 115),
    ('zone_1', 'transmit_switches_2', 0, 1, 116),
    ('zone_1', 'transmit_switches_2', 0, 2, 117),
    ('zone_1', 'transmit_switches_2', 0, 3, 118),
    ('zone_1', 'transmit_switches_2', 0, 4, 119),
    ('zone_1', 'transmit_switches_2', 0, 5, 120),
    ('zone_2', 'transmit_switches_1', 0, 4, 136),
    ('zone_2', 'transmit_switches_1', 0, 0, 137),
    ('zone_2', 'transmit_switches_1', 0, 1, 138),
    ('zone_2', 'transmit_switches_1', 0, 2, 139),
    ('zone_2', 'transmit_switches_1', 0, 3, 140),
    ('zone_2', 'transmit_switches_2', 0, 0, 141),
    ('zone_2', 'transmit_switches_2', 0, 1, 142),
    ('zone_2', 'transmit_switches_2', 0, 2, 143),
    ('zone_2', 'transmit_switches_2', 0, 3, 144),
    ('zone_2', 'transmit_switches_2', 0, 4, 145),
    ('zone_2', 'transmit_switches_2', 0, 5, 146),
    ('zone_3', 'transmit_switches_1', 0, 4, 162),
    ('zone_3', 'transmit_switches_1', 0, 0, 163),
    ('zone_3', 'transmit_switches_1', 0, 1, 164),
    ('zone_3', 'transmit_switches_1', 0, 2, 165),
    ('zone_3', 'transmit_switches_1', 0, 3, 166),
    ('zone_3', 'transmit_switches_2', 0, 0, 167),
    ('zone_3', 'transmit_switches_2', 0, 1, 168),
    ('zone_3', 'transmit_switches_2', 0, 2, 169),
    ('zone_3', 'transmit_switches_2', 0, 3, 170),
    ('zone_3', 'transmit_switches_2', 0, 4, 171),
    ('zone_3', 'transmit_switches_2', 0, 5, 172),
]

# (block_key, field_name, lo_blob_position, hi_blob_position): a two-byte
# (msb, lsb) 7-bit model field stored as a 16-bit little-endian value.
REPACK_POSITIONS: list[tuple[str, str, int, int]] = [
    ('additional', 'tempo_raw', 59, 60),
]

# Fixed format-version stamps the X9 blob does not store. They would decode as
# 0 from the blob, but every valid Live Set Sound carries the constants below
# (the same values the SysEx Bulk Dump and Init Sound use). blob_to_sound fills
# them on read so an X9-derived sound matches its MIDI form for these fields --
# which also keeps them out of the concise YAML's `raw:` fallback. They are not
# in FIELD_POSITIONS, so sound_to_blob still drops them and X9 round-trips stay
# byte-exact.
# (block_key, field_name, canonical_value)
FIXED_VERSION_FIELDS: list[tuple[str, str, int]] = [
    ('soundmondo', 'soundmondo_format_version_major', 1),
    ('soundmondo', 'soundmondo_format_version_minor', 4),
    ('soundmondo', 'soundmondo_format_version_bugfix', 0),
    ('common', 'bulk_format_version', 2),
    ('section_piano_specific', 'bulk_format_version', 1),
    ('section_epiano_specific', 'bulk_format_version', 1),
    ('section_sub_specific', 'bulk_format_version', 1),
]

# 367-byte baseline blob: the fixed YSFC framing every Live Set Sound blob
# shares, with every per-sound byte left 0. sound_to_blob() overwrites the
# name region (bytes 4-18) and all FIELD/BIT/REPACK_POSITIONS per Live Set
# Sound, so those positions carry no information here -- this constant encodes
# no captured Live Set Sound, only the structural bytes that are invariant
# across every fresh device export: block type/size markers, format-version
# stamps, and the device's trailing panel-only chunk (count 4 + four 0x40
# bytes) at 359-366. Verified: the resulting blobs are byte-identical to the
# device's own export.
_BASELINE_STRUCTURE: dict[int, int] = {
    3: 0x10,
    23: 0x17,
    29: 0x0b, 30: 0x04,
    50: 0x0a,
    64: 0x05,
    73: 0x04,
    77: 0x16, 103: 0x16, 129: 0x16, 155: 0x16,    # zone block markers
    181: 0x03, 185: 0x1d,
    218: 0x16, 244: 0x1d,                          # piano / epiano block markers
    277: 0x16, 303: 0x1d,                          # sub block markers
    336: 0x16,
    362: 0x04, 363: 0x40, 364: 0x40, 365: 0x40, 366: 0x40,   # trailing chunk
}


def _build_baseline() -> bytes:
    blob = bytearray(BLOB_SIZE)
    for pos, value in _BASELINE_STRUCTURE.items():
        blob[pos] = value
    return bytes(blob)


BASELINE_BLOB: bytes = _build_baseline()
