"""
Parameter maps for the CP88/CP73 "Live Set Sound" MIDI Bulk Dump.

Source of truth: CP88_CP73_supplementary_manual_En_v200_H0.pdf,
"MIDI Data Table" / "MIDI PARAMETER CHANGE TABLE (BULK CONTROL)"
(pages 20-25), and CP88_owners_manual_En_F0.pdf:
  https://data.yamaha.com/files/download/other_assets/7/1243337/CP88_CP73_supplementary_manual_En_v200_H0.pdf
  https://data.yamaha.com/files/download/other_assets/7/1180527/CP88_owners_manual_En_F0.pdf

All addresses are (high, mid, low) byte tuples as used in the
SysEx Bulk Dump / Parameter Change messages:

    F0 43 0n 7F 1C bh bl 08 ah am al dd...dd cc F7   (Bulk Dump)
    F0 43 2n 7F 1C 08 ah am al F7                    (Bulk Dump Request)

Group Number = 7F 1C, Model ID = 08 for all blocks below.
"""

from __future__ import annotations

SECTION_NAMES = ("piano", "epiano", "sub")


def _fields(size, entries):
    """Build a full, gap-free field list for a block of `size` bytes.

    `entries` is a list of (offset, name, size) for the named fields.
    Any byte offsets not covered are filled in as reserved_<offset> (size 1).
    Returns an ordered list of (offset, name, size, kind), where kind fully
    determines the field's value type: "ascii" (str), "byte" (single int),
    or "bytes" (list of ints).
    """
    covered = set()
    fields = []
    for offset, name, fsize in entries:
        for o in range(offset, offset + fsize):
            if o in covered:
                raise ValueError(f"overlapping field at offset {o:#x} ({name})")
            covered.add(o)
        kind = "ascii" if name == "name" else ("byte" if fsize == 1 else "bytes")
        fields.append((offset, name, fsize, kind))
    for o in range(size):
        if o not in covered:
            fields.append((o, f"reserved_0x{o:02x}", 1, "byte"))
    fields.sort(key=lambda f: f[0])
    return fields


# ---------------------------------------------------------------------------
# Soundmondo Format Version  (address 00 7F 00, size 4 bytes)
# Included as the first data block of every Live Set Sound bulk dump.
# ---------------------------------------------------------------------------
SOUNDMONDO_SIZE = 4
SOUNDMONDO_ADDR = (0x00, 0x7F, 0x00)
SOUNDMONDO_FIELDS = _fields(SOUNDMONDO_SIZE, [
    (0x00, "soundmondo_format_version_major", 1),  # default 01
    (0x01, "soundmondo_format_version_minor", 1),  # default 04
    (0x02, "soundmondo_format_version_bugfix", 1),  # default 00
])

# ---------------------------------------------------------------------------
# Master EQ  (address 20 40 00, size 0x14 = 20 bytes)
# Included as the second data block of every Live Set Sound bulk dump.
# ---------------------------------------------------------------------------
MASTER_EQ_SIZE = 0x14
MASTER_EQ_ADDR = (0x20, 0x40, 0x00)
MASTER_EQ_FIELDS = _fields(MASTER_EQ_SIZE, [
    (0x00, "eq_gain1", 1),  # -12dB - +12dB, default 40
    (0x08, "eq_gain3", 1),  # -12dB - +12dB, default 40
    (0x09, "eq_frequency3", 1),  # 100Hz - 10kHz, default 1C
    (0x10, "eq_gain5", 1),  # -12dB - +12dB, default 40
    (0x13, "eq_on_off", 1),  # Off/On, default 00
])


# ---------------------------------------------------------------------------
# Live Set Sound Common  (address 46 00 00, size 0x30 = 48 bytes)
# ---------------------------------------------------------------------------
COMMON_SIZE = 0x30
COMMON_ADDR = (0x46, 0x00, 0x00)
COMMON_FIELDS = _fields(COMMON_SIZE, [
    (0x00, "name", 15),  # 15 ASCII chars (0x20-0x7F), "Live Set Sound Name 1..15"
    (0x0F, "bulk_format_version", 1),  # fixed 02
    (0x11, "zone_mode_switch", 1),
    (0x12, "advanced_zone_mode_switch", 1),
    (0x13, "live_set_eq_mode_switch", 1),
    (0x14, "modulation_lever_assign", 1),
    (0x15, "tg_transpose", 1),
    (0x16, "split_point", 1),
    (0x17, "modulation_lever_limit_low", 1),
    (0x18, "modulation_lever_limit_high", 1),
    (0x19, "fc1_assign", 1),
    (0x1A, "fc2_assign", 1),
    (0x1B, "fc1_limit_low", 1),
    (0x1C, "fc1_limit_high", 1),
    (0x1D, "fc2_limit_low", 1),
    (0x1E, "fc2_limit_high", 1),
    (0x20, "depth_knob_section_select", 1),
    (0x21, "piano_touch_sensitivity_depth", 1),
    (0x22, "epiano_touch_sensitivity_depth", 1),
    (0x23, "sub_touch_sensitivity_depth", 1),
    (0x24, "delay_switch", 1),
    (0x25, "delay_type", 1),
    (0x26, "delay_feedback", 1),
    (0x27, "delay_time", 1),
    (0x28, "reverb_switch", 1),
    (0x29, "piano_touch_sensitivity_offset", 1),
    (0x2A, "epiano_touch_sensitivity_offset", 1),
    (0x2B, "reverb_time", 1),
    (0x2C, "sub_touch_sensitivity_offset", 1),
    (0x2D, "piano_pitch_modulation_speed", 1),
    (0x2E, "epiano_pitch_modulation_speed", 1),
    (0x2F, "sub_pitch_modulation_speed", 1),
])

# ---------------------------------------------------------------------------
# Live Set Sound Additional  (address 46 01 00, size 0x10 = 16 bytes)
# ---------------------------------------------------------------------------
ADDITIONAL_SIZE = 0x10
ADDITIONAL_ADDR = (0x46, 0x01, 0x00)
ADDITIONAL_FIELDS = _fields(ADDITIONAL_SIZE, [
    (0x01, "tempo_delay_time", 1),
    (0x02, "tempo_raw", 2),  # 2-byte value (msb*128+lsb)/10 = BPM; default 07 04 = 90.0 BPM
])

# ---------------------------------------------------------------------------
# Zone  (address 4A zz 00, zz = 00-03, size 0x10 = 16 bytes each)
# ---------------------------------------------------------------------------
ZONE_SIZE = 0x10
ZONE_COUNT = 4


def zone_addr(zz: int):
    return (0x4A, zz, 0x00)


ZONE_FIELDS = _fields(ZONE_SIZE, [
    (0x00, "zone_switch", 1),
    (0x01, "transmit_channel", 1),
    (0x02, "transpose_octave", 1),
    (0x03, "transpose_semitone", 1),
    (0x04, "note_limit_low", 1),
    (0x05, "note_limit_high", 1),
    (0x07, "midi_volume", 1),
    (0x08, "midi_pan", 1),
    (0x09, "midi_bank_msb", 1),
    (0x0A, "midi_bank_lsb", 1),
    (0x0B, "midi_program_number", 1),
    (0x0C, "transmit_switches_1", 1),  # bit0 BankSel,1 PC,2 Vol,3 Pan,4 Note
    (0x0D, "transmit_switches_2", 1),  # bit0 PB,1 MW,2 FC1,3 FC2,4 FS,5 Sus
])

# ---------------------------------------------------------------------------
# Section Common  (address 50 0p 00, p = 0 Piano / 1 E.Piano / 2 Sub, size 0x18)
# ---------------------------------------------------------------------------
SECTION_COMMON_SIZE = 0x18
SECTION_SPECIFIC_SIZE = 0x1C
SECTION_ADDITIONAL_SIZE = 0x10


def section_common_addr(p: int):
    return (0x50, 0x00 + p, 0x00)


def section_specific_addr(p: int):
    return (0x50, 0x10 + p, 0x00)


def section_additional_addr(p: int):
    return (0x50, 0x20 + p, 0x00)


SECTION_COMMON_FIELDS = _fields(SECTION_COMMON_SIZE, [
    (0x00, "current_category", 1),
    (0x01, "category1_voice_number", 1),
    (0x02, "category2_voice_number", 1),
    (0x03, "category3_voice_number", 1),
    (0x04, "category4_voice_number", 1),
    (0x05, "advanced_sound_mode_voice_number", 1),
    (0x06, "advanced_sound_mode_switch", 1),
    (0x07, "section_switch", 1),
    (0x08, "split_mode", 1),
    (0x09, "octave_shift", 1),
    (0x0A, "section_volume", 1),
    (0x0B, "tone", 1),
    (0x0C, "advanced_sound_mode_extra_voice_number", 1),
    (0x0D, "pitch_bend_range", 1),
    (0x0F, "pitch_modulation_depth", 1),
    (0x11, "receive_expression", 1),
    (0x12, "receive_sustain", 1),
    (0x13, "receive_sostenuto", 1),
    (0x14, "receive_soft", 1),
    (0x16, "delay_depth", 1),
    (0x17, "reverb_depth", 1),
])

# ---------------------------------------------------------------------------
# Section Specific  (address 50 1p 00, p = 0 Piano / 1 E.Piano / 2 Sub, size 0x1C)
# Field meanings only apply to the relevant section, but all bytes are
# present (and preserved) for every section.
# ---------------------------------------------------------------------------
SECTION_SPECIFIC_FIELDS = _fields(SECTION_SPECIFIC_SIZE, [
    (0x00, "piano_damper_resonance_switch", 1),
    (0x01, "bulk_format_version", 1),  # fixed 01
    (0x02, "piano_damper_resonance_damper_control", 1),
    (0x03, "piano_damper_resonance_dry_wet_balance", 1),
    (0x04, "piano_effect_switch", 1),
    (0x05, "piano_effect_type", 1),
    (0x06, "piano_effect_depth", 1),
    (0x08, "epiano_effect1_switch", 1),
    (0x09, "epiano_effect1_type", 1),
    (0x0A, "epiano_effect1_depth", 1),
    (0x0B, "epiano_effect1_rate", 1),
    (0x0C, "epiano_effect2_switch", 1),
    (0x0D, "epiano_effect2_type", 1),
    (0x0E, "epiano_effect2_depth", 1),
    (0x0F, "epiano_effect2_speed", 1),
    (0x10, "epiano_drive_switch", 1),
    (0x11, "epiano_drive", 1),
    (0x14, "sub_effect_switch", 1),
    (0x15, "sub_effect_type", 1),
    (0x16, "sub_effect_depth", 1),
    (0x17, "sub_effect_speed", 1),
    (0x18, "sub_attack", 1),
    (0x19, "sub_release", 1),
])

# ---------------------------------------------------------------------------
# Section Additional  (address 50 2p 00, p = 0 Piano / 1 E.Piano / 2 Sub, size 0x10)
# ---------------------------------------------------------------------------
SECTION_ADDITIONAL_FIELDS = _fields(SECTION_ADDITIONAL_SIZE, [
    (0x01, "mono_poly", 1),
    (0x02, "portamento_switch", 1),
    (0x03, "portamento_time", 1),
    (0x04, "portamento_mode", 1),
    (0x05, "portamento_time_mode", 1),
    (0x08, "pan", 1),
])

# ---------------------------------------------------------------------------
# Bulk Header / Footer (address 0E pp 0n / 0F pp 0n, size 0)
# pp = User Live Set Page (00-27 = pages 1-40), n = Set/Program number (0-7)
# ---------------------------------------------------------------------------
HEADER_HIGH = 0x0E
FOOTER_HIGH = 0x0F

PAGE_COUNT = 40
SETS_PER_PAGE = 8


def check_page_set(page: int, set_no: int):
    """Validate a user-facing (1-based) page/set address."""
    if not (1 <= page <= PAGE_COUNT):
        raise ValueError(f"page must be 1-{PAGE_COUNT}, got {page}")
    if not (1 <= set_no <= SETS_PER_PAGE):
        raise ValueError(f"set must be 1-{SETS_PER_PAGE}, got {set_no}")


def header_addr(pp: int, n: int):
    return (HEADER_HIGH, pp, n)


def footer_addr(pp: int, n: int):
    return (FOOTER_HIGH, pp, n)


# ---------------------------------------------------------------------------
# Block lists for one Live Set Sound bulk dump: 17 data blocks, which the
# device sends bracketed by a Bulk Header and Bulk Footer (19 messages total).
# Each entry: (block_key, address, size, fields)
# ---------------------------------------------------------------------------
def _data_blocks():
    blocks = [
        ("soundmondo", SOUNDMONDO_ADDR, SOUNDMONDO_SIZE, SOUNDMONDO_FIELDS),
        ("master_eq", MASTER_EQ_ADDR, MASTER_EQ_SIZE, MASTER_EQ_FIELDS),
        ("common", COMMON_ADDR, COMMON_SIZE, COMMON_FIELDS),
        ("additional", ADDITIONAL_ADDR, ADDITIONAL_SIZE, ADDITIONAL_FIELDS),
    ]
    for zz in range(ZONE_COUNT):
        blocks.append((f"zone_{zz}", zone_addr(zz), ZONE_SIZE, ZONE_FIELDS))
    for p, sec in enumerate(SECTION_NAMES):
        blocks.append((f"section_{sec}_common", section_common_addr(p),
                        SECTION_COMMON_SIZE, SECTION_COMMON_FIELDS))
    for p, sec in enumerate(SECTION_NAMES):
        blocks.append((f"section_{sec}_specific", section_specific_addr(p),
                        SECTION_SPECIFIC_SIZE, SECTION_SPECIFIC_FIELDS))
    for p, sec in enumerate(SECTION_NAMES):
        blocks.append((f"section_{sec}_additional", section_additional_addr(p),
                        SECTION_ADDITIONAL_SIZE, SECTION_ADDITIONAL_FIELDS))
    return tuple(blocks)


DATA_BLOCKS = _data_blocks()


def sound_blocks(pp: int, n: int):
    """All 19 blocks (header + DATA_BLOCKS + footer) in device dump order."""
    return [("header", header_addr(pp, n), 0, []),
            *DATA_BLOCKS,
            ("footer", footer_addr(pp, n), 0, [])]


# Bank Select MSB/LSB + Program Change used to switch Live Set Sounds via MIDI
# (page 19/20 of the supplementary manual): MSB=63 (0x3F), LSB=pp, PC=n
LIVE_SET_BANK_MSB = 0x3F
