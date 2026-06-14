"""
Concise YAML Live Set format ("yaml").

Only encodes values that differ from the "standard" defaults in
yamldata.FIELD_DEFAULTS. A Live Set Sound Section (Piano/E.Piano/Sub) is
considered "off" by default; "instrument 1" (raw voice number 0) is the
default instrument for each section's active category.

A `raw:` map (keyed by `block_key.field_name` or `block_key.field_name[i]`)
is used as a fallback for any field not otherwise represented, so that
`json -> yaml -> json` is always exact. `yaml -> json -> yaml` (and
`yaml -> json -> yaml -> json`) is canonical: re-emitting a Live Set Sound
already in this format produces byte-identical YAML.
"""

from __future__ import annotations

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap

from . import paramap
from .soundmodels import (
    Additional,
    Common,
    LiveSetSound,
    MasterEq,
    Section,
    SectionAdditional,
    SectionCommon,
    SectionSpecific,
    Sections,
    SoundMondo,
    Zone,
)
from .yamldata import (
    DELAY_TYPE,
    DEPTH_KNOB_SECTION,
    EPIANO_EFFECT1_TYPE,
    EPIANO_EFFECT2_TYPE,
    EQ_FREQ3,
    FIELD_DEFAULTS,
    MONO_POLY,
    PIANO_EFFECT_TYPE,
    PORTAMENTO_MODE,
    PORTAMENTO_TIME_MODE,
    SECTION_CATEGORIES,
    SPLIT_MODE,
    SUB_EFFECT_TYPE,
    TEMPO_DELAY_TIME,
    advanced_number_to_raw,
    advanced_raw_to_number,
    CC_NAMES,
    advanced_voice_name,
    advanced_voice_number,
    category_index_from_name,
    category_name,
    note_name,
    signed64,
    unsigned64,
)

YAML_FORMAT = "cp88-cp73-liveset-yaml-v1"


def make_yaml() -> YAML:
    """Return a new ruamel.yaml YAML instance configured for this format's
    canonical output style (block style, 2-space mapping indent, no line
    wrapping). Re-dumping a document produced by these settings is what the
    `yaml -> json -> yaml` byte-identical guarantee is defined against."""
    yaml = YAML()
    yaml.default_flow_style = False
    yaml.width = 4096
    yaml.indent(mapping=2, sequence=4, offset=2)
    return yaml


# ---------------------------------------------------------------------------
# Field transforms
# ---------------------------------------------------------------------------
def _id(x):
    return x


def _enc_bool(r):
    return bool(r)


def _dec_bool(d):
    return 1 if d else 0


def _enc_plus1(r):
    return r + 1


def _dec_plus1(d):
    return d - 1


_NOTE_NAME_TO_RAW = {note_name(raw): raw for raw in range(128)}


def _note_codec(enc=_id, dec=_id):
    """Note-valued fields (split point, note limits): yaml shows the note
    name (e.g. "D#2"); input accepts either the name or the raw MIDI note
    number. No eol comment is emitted (only the instrument voice number, which
    mirrors the device display, is annotated)."""
    def enc_fn(raw):
        return note_name(enc(raw))

    def dec_fn(value):
        encoded = _NOTE_NAME_TO_RAW[value] if isinstance(value, str) else value
        return dec(encoded)

    return enc_fn, dec_fn, None


def _enum_codec(table, enc=_id, dec=_id):
    """For "multiple choice" fields with a small fixed set of named options
    (`table`: encoded value -> name). Yaml shows the option's name; input
    accepts either the name or the underlying number. No eol comment is emitted
    (only the instrument voice number, which mirrors the device display, is
    annotated); a value with no listed name is written as the bare number."""
    reverse = {v: k for k, v in table.items()}

    def enc_fn(raw):
        encoded = enc(raw)
        return table.get(encoded, encoded)

    def dec_fn(value):
        encoded = reverse[value] if isinstance(value, str) else value
        return dec(encoded)

    return enc_fn, dec_fn, None


# Tempo (`additional.tempo_raw` = [msb, lsb]) encodes a 14-bit value
# V = msb*128 + lsb. The device's BPM is V/10, so the factory default [7, 4]
# (V = 900) is 90.0 BPM, and the panel's 42.0-240.0 BPM range is V 420-2400
# (confirmed on a real CP88). The yaml shows the BPM as a one-decimal number
# when V is in that range, and otherwise keeps the raw [msb, lsb] list (so any
# value still round-trips exactly). On read, either a number or a [msb, lsb]
# list is taken.
_TEMPO_MIN_V = 420     # 42.0 BPM
_TEMPO_MAX_V = 2400    # 240.0 BPM


def _enc_tempo(raw):
    v = raw[0] * 128 + raw[1]
    if _TEMPO_MIN_V <= v <= _TEMPO_MAX_V:
        return round(v / 10, 1)
    return list(raw)


def _dec_tempo(value):
    if isinstance(value, (list, tuple)):
        return list(value)
    v = round(float(value) * 10)
    return [v // 128, v % 128]


# A FieldSpec: (field_name, yaml_path (tuple of str), encode, decode, comment_fn or None)
FieldSpec = tuple


# ---------------------------------------------------------------------------
# Section field specs (apply to each of piano / epiano / sub)
# ---------------------------------------------------------------------------
SECTION_COMMON_SPECS: list[FieldSpec] = [
    ("split_mode", ("split_mode",), *_enum_codec(SPLIT_MODE)),
    ("octave_shift", ("octave_shift",), signed64, unsigned64, None),
    ("section_volume", ("volume",), _id, _id, None),
    ("tone", ("tone",), _id, _id, None),
    ("pitch_bend_range", ("pitch_bend_range",), signed64, unsigned64, None),
    ("pitch_modulation_depth", ("pitch_modulation_depth",), _id, _id, None),
    ("receive_expression", ("receive", "expression"), _enc_bool, _dec_bool, None),
    ("receive_sustain", ("receive", "sustain"), _enc_bool, _dec_bool, None),
    ("receive_sostenuto", ("receive", "sostenuto"), _enc_bool, _dec_bool, None),
    ("receive_soft", ("receive", "soft"), _enc_bool, _dec_bool, None),
    ("delay_depth", ("delay_depth",), _id, _id, None),
    ("reverb_depth", ("reverb_depth",), _id, _id, None),
]

SECTION_SPECIFIC_SPECS: list[FieldSpec] = [
    ("piano_damper_resonance_switch", ("damper_resonance", "on"), _enc_bool, _dec_bool, None),
    ("piano_damper_resonance_damper_control", ("damper_resonance", "control"), _id, _id, None),
    ("piano_damper_resonance_dry_wet_balance", ("damper_resonance", "balance"), _id, _id, None),
    ("piano_effect_switch", ("piano_effect", "on"), _enc_bool, _dec_bool, None),
    ("piano_effect_type", ("piano_effect", "type"), *_enum_codec(PIANO_EFFECT_TYPE)),
    ("piano_effect_depth", ("piano_effect", "depth"), _id, _id, None),
    ("epiano_effect1_switch", ("epiano_effect1", "on"), _enc_bool, _dec_bool, None),
    ("epiano_effect1_type", ("epiano_effect1", "type"), *_enum_codec(EPIANO_EFFECT1_TYPE)),
    ("epiano_effect1_depth", ("epiano_effect1", "depth"), _id, _id, None),
    ("epiano_effect1_rate", ("epiano_effect1", "rate"), _id, _id, None),
    ("epiano_effect2_switch", ("epiano_effect2", "on"), _enc_bool, _dec_bool, None),
    ("epiano_effect2_type", ("epiano_effect2", "type"), *_enum_codec(EPIANO_EFFECT2_TYPE)),
    ("epiano_effect2_depth", ("epiano_effect2", "depth"), _id, _id, None),
    ("epiano_effect2_speed", ("epiano_effect2", "speed"), _id, _id, None),
    ("epiano_drive_switch", ("epiano_drive", "on"), _enc_bool, _dec_bool, None),
    ("epiano_drive", ("epiano_drive", "depth"), _id, _id, None),
    ("sub_effect_switch", ("sub_effect", "on"), _enc_bool, _dec_bool, None),
    ("sub_effect_type", ("sub_effect", "type"), *_enum_codec(SUB_EFFECT_TYPE)),
    ("sub_effect_depth", ("sub_effect", "depth"), _id, _id, None),
    ("sub_effect_speed", ("sub_effect", "speed"), _id, _id, None),
    ("sub_attack", ("sub_envelope", "attack"), _id, _id, None),
    ("sub_release", ("sub_envelope", "release"), _id, _id, None),
]


def _section_specific_specs(sec: str) -> list[FieldSpec]:
    """Per-section view of SECTION_SPECIFIC_SPECS with the redundant leading
    "<section>_" stripped from a block key that repeats the section name.

    Each section's `specific` block physically carries all three sections'
    effect parameters, but only its own are meaningful and these specs are
    already nested under the section key in the YAML -- so under `sub:`,
    `sub_effect` becomes `effect` and `sub_envelope` becomes `envelope`.
    Foreign-section fields (the inert copies that only surface if a file sets
    one) keep their prefix, so they stay unambiguous against the active block.
    """
    prefix = f"{sec}_"
    specs: list[FieldSpec] = []
    for field, path, enc, dec, comment_fn in SECTION_SPECIFIC_SPECS:
        if path and path[0].startswith(prefix):
            path = (path[0][len(prefix):], *path[1:])
        specs.append((field, path, enc, dec, comment_fn))
    return specs


SECTION_SPECIFIC_SPECS_BY_SEC: dict[str, list[FieldSpec]] = {
    sec: _section_specific_specs(sec) for sec in paramap.SECTION_NAMES
}

SECTION_ADDITIONAL_SPECS: list[FieldSpec] = [
    ("mono_poly", ("mono_poly",), *_enum_codec(MONO_POLY)),
    ("portamento_switch", ("portamento", "on"), _enc_bool, _dec_bool, None),
    ("portamento_time", ("portamento", "time"), _id, _id, None),
    ("portamento_mode", ("portamento", "mode"), *_enum_codec(PORTAMENTO_MODE)),
    ("portamento_time_mode", ("portamento", "time_mode"), *_enum_codec(PORTAMENTO_TIME_MODE)),
    ("pan", ("pan",), signed64, unsigned64, None),
]

# fields living in the `common` block but conceptually per-section
TOUCH_SPECS_TEMPLATE: list[FieldSpec] = [
    ("{sec}_touch_sensitivity_depth", ("touch_sensitivity", "depth"), _id, _id, None),
    ("{sec}_touch_sensitivity_offset", ("touch_sensitivity", "offset"), _id, _id, None),
    ("{sec}_pitch_modulation_speed", ("pitch_modulation_speed",), _id, _id, None),
]

# Fields that are always shown explicitly in the yaml, even when equal to
# their default ("off"): the physical switches for Delay and Reverb (the
# section on/off switches are handled separately, in _section_to_yaml).
ALWAYS_SHOW = {"delay_switch", "reverb_switch"}


# ---------------------------------------------------------------------------
# Top-level "common" group (remaining `common` + `additional` block fields)
# ---------------------------------------------------------------------------
COMMON_SPECS: list[tuple] = [
    ("common", "zone_mode_switch", ("zone_mode",), _enc_bool, _dec_bool, None),
    ("common", "advanced_zone_mode_switch", ("advanced_zone_mode",), _enc_bool, _dec_bool, None),
    ("common", "live_set_eq_mode_switch", ("live_set_eq_mode",), _enc_bool, _dec_bool, None),
    ("common", "modulation_lever_assign", ("modulation_lever", "assign"), *_enum_codec(CC_NAMES)),
    ("common", "modulation_lever_limit_low", ("modulation_lever", "limit_low"), _id, _id, None),
    ("common", "modulation_lever_limit_high", ("modulation_lever", "limit_high"), _id, _id, None),
    ("common", "tg_transpose", ("tg_transpose",), signed64, unsigned64, None),
    ("common", "split_point", ("split_point",), *_note_codec()),
    ("common", "fc1_assign", ("fc1", "assign"), *_enum_codec(CC_NAMES)),
    ("common", "fc1_limit_low", ("fc1", "limit_low"), _id, _id, None),
    ("common", "fc1_limit_high", ("fc1", "limit_high"), _id, _id, None),
    ("common", "fc2_assign", ("fc2", "assign"), *_enum_codec(CC_NAMES)),
    ("common", "fc2_limit_low", ("fc2", "limit_low"), _id, _id, None),
    ("common", "fc2_limit_high", ("fc2", "limit_high"), _id, _id, None),
    ("common", "depth_knob_section_select", ("depth_knob_section",), *_enum_codec(DEPTH_KNOB_SECTION)),
    ("common", "delay_switch", ("delay", "on"), _enc_bool, _dec_bool, None),
    ("common", "delay_type", ("delay", "type"), *_enum_codec(DELAY_TYPE)),
    ("common", "delay_feedback", ("delay", "feedback"), _id, _id, None),
    ("common", "delay_time", ("delay", "time"), _id, _id, None),
    # Tempo and the Tempo-Delay note length live under `delay`: they only
    # affect the Tempo Delay type, and the device groups them with the delay.
    ("additional", "tempo_raw", ("delay", "tempo"), _enc_tempo, _dec_tempo, None),
    ("additional", "tempo_delay_time", ("delay", "tempo_delay_time"), *_enum_codec(TEMPO_DELAY_TIME)),
    ("common", "reverb_switch", ("reverb", "on"), _enc_bool, _dec_bool, None),
    ("common", "reverb_time", ("reverb", "time"), _id, _id, None),
]

# ---------------------------------------------------------------------------
# master_eq group
# ---------------------------------------------------------------------------
MASTER_EQ_SPECS: list[FieldSpec] = [
    ("eq_gain1", ("low",), signed64, unsigned64, None),
    ("eq_gain3", ("mid",), signed64, unsigned64, None),
    ("eq_frequency3", ("mid_freq",), *_enum_codec(EQ_FREQ3)),
    ("eq_gain5", ("high",), signed64, unsigned64, None),
    ("eq_on_off", ("on",), _enc_bool, _dec_bool, None),
]

# ---------------------------------------------------------------------------
# zone field specs
# ---------------------------------------------------------------------------
ZONE_SPECS: list[FieldSpec] = [
    ("zone_switch", ("on",), _enc_bool, _dec_bool, None),
    ("transmit_channel", ("transmit_channel",), _enc_plus1, _dec_plus1, None),
    ("transpose_octave", ("transpose_octave",), signed64, unsigned64, None),
    ("transpose_semitone", ("transpose_semitone",), signed64, unsigned64, None),
    ("note_limit_low", ("note_limit", "low"), *_note_codec()),
    ("note_limit_high", ("note_limit", "high"), *_note_codec()),
    ("midi_volume", ("volume",), _id, _id, None),
    ("midi_pan", ("pan",), signed64, unsigned64, None),
    # Bank Select MSB/LSB are two independent 0-127 values on the device
    # (panel "Bank MSB"/"Bank LSB", and two separate bulk parameters), so they
    # are kept as two fields here rather than folded into one 14-bit number.
    ("midi_bank_msb", ("bank", "msb"), _id, _id, None),
    ("midi_bank_lsb", ("bank", "lsb"), _id, _id, None),
    ("midi_program_number", ("program",), _enc_plus1, _dec_plus1, None),
]

ZONE_TRANSMIT1_BITS = [
    ("bank_select", 0), ("program_change", 1), ("volume", 2), ("pan", 3), ("note", 4),
]
ZONE_TRANSMIT2_BITS = [
    ("pitch_bend", 0), ("modulation", 1), ("fc1", 2), ("fc2", 3), ("foot_switch", 4), ("sustain", 5),
]


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------
def _get_or_create(cm: CommentedMap, key: str) -> CommentedMap:
    if key not in cm:
        cm[key] = CommentedMap()
    return cm[key]


def _set_path(root: CommentedMap, path: tuple[str, ...], value, comment: str | None):
    cm = root
    for key in path[:-1]:
        cm = _get_or_create(cm, key)
    leaf = path[-1]
    cm[leaf] = value
    if comment:
        cm.yaml_add_eol_comment(comment, leaf)


def _get_path(root, path: tuple[str, ...]):
    cur = root
    for key in path:
        if not isinstance(cur, dict) or key not in cur:
            return None, False
        cur = cur[key]
    return cur, True


def _encode_specs_main(src, specs, defaults_prefix: str, out: CommentedMap, consumed: set):
    """Encode `specs` into `out`, returning a list of deferred "on" fields
    (ones at their default/off value) for `_finalize_on_fields`."""
    deferred_on = []
    for field, path, enc, _dec, comment_fn in specs:
        consumed.add(field)
        raw = getattr(src, field)
        default = FIELD_DEFAULTS[f"{defaults_prefix}.{field}"]
        if raw == default:
            if path[-1] == "on":
                deferred_on.append((path, enc, comment_fn, raw))
            continue
        comment = comment_fn(raw) if comment_fn else None
        _set_path(out, path, enc(raw), comment)
    return deferred_on


def _finalize_on_fields(out: CommentedMap, deferred_on: list):
    """An "on" field defaulting to off is still shown if its enclosing map
    ended up with other (non-default) entries."""
    for path, enc, comment_fn, raw in deferred_on:
        group_path = path[:-1]
        group, found = _get_path(out, group_path) if group_path else (out, True)
        if found and group:
            comment = comment_fn(raw) if comment_fn else None
            _set_path(out, path, enc(raw), comment)
            group.move_to_end("on", last=False)


def _encode_specs(src, specs, defaults_prefix: str, out: CommentedMap, consumed: set):
    deferred_on = _encode_specs_main(src, specs, defaults_prefix, out, consumed)
    _finalize_on_fields(out, deferred_on)


def _decode_specs(dst: dict, specs, defaults_prefix: str, src: CommentedMap):
    for field, path, _enc, dec, _comment_fn in specs:
        value, found = _get_path(src, path)
        if found:
            dst[field] = dec(value)
        else:
            dst[field] = FIELD_DEFAULTS[f"{defaults_prefix}.{field}"]


# ---------------------------------------------------------------------------
# Section conversion
# ---------------------------------------------------------------------------
SECTION_CATEGORY_BASE = {"piano": 0, "epiano": 4, "sub": 8}


ADVANCED_CATEGORY_NAME = "Advanced Mode"


def _section_to_yaml(sec: str, common: SectionCommon, specific: SectionSpecific,
                      additional: SectionAdditional) -> CommentedMap:
    out = CommentedMap()

    section_switch = common.section_switch
    on = section_switch != FIELD_DEFAULTS[f"section_{sec}_common.section_switch"]
    out["on"] = bool(on)

    consumed_common = {"section_switch", "current_category",
                        "advanced_sound_mode_switch", "advanced_sound_mode_voice_number",
                        "advanced_sound_mode_extra_voice_number",
                        "category1_voice_number", "category2_voice_number",
                        "category3_voice_number", "category4_voice_number"}

    advanced = (common.advanced_sound_mode_switch
                != FIELD_DEFAULTS[f"section_{sec}_common.advanced_sound_mode_switch"])

    base = SECTION_CATEGORY_BASE[sec]
    cat_idx_raw = common.current_category - base
    active_cat_idx = cat_idx_raw if 0 <= cat_idx_raw < 4 else 0

    advanced_number = advanced_raw_to_number(common.advanced_sound_mode_voice_number,
                                              common.advanced_sound_mode_extra_voice_number)
    advanced_default_number = advanced_raw_to_number(
        FIELD_DEFAULTS[f"section_{sec}_common.advanced_sound_mode_voice_number"],
        FIELD_DEFAULTS[f"section_{sec}_common.advanced_sound_mode_extra_voice_number"])

    def advanced_value_comment(number):
        # The Advanced Mode voice number is not shown anywhere on the device,
        # so (unlike the within-category instrument number) it carries no
        # eol comment.
        name = advanced_voice_name(number)
        if name is not None:
            return name, None
        return number, None

    if advanced:
        active_category = ADVANCED_CATEGORY_NAME
        active_value, active_comment = advanced_value_comment(advanced_number)
    else:
        active_category = category_name(sec, active_cat_idx)
        voices = SECTION_CATEGORIES[sec][active_cat_idx][1]
        voice_raw = getattr(common, f"category{active_cat_idx + 1}_voice_number")
        if 0 <= voice_raw < len(voices):
            active_value, active_comment = voices[voice_raw], f"{voice_raw + 1}"
        else:
            active_value, active_comment = voice_raw + 1, None

    out["category"] = active_category

    others = []
    for i in range(4):
        if i == active_cat_idx and not advanced:
            continue
        voice_raw = getattr(common, f"category{i + 1}_voice_number")
        if voice_raw == 0:
            continue
        cat_name, voices = SECTION_CATEGORIES[sec][i]
        if 0 <= voice_raw < len(voices):
            value, comment = voices[voice_raw], f"{voice_raw + 1}"
        else:
            value, comment = voice_raw + 1, None
        others.append((cat_name, value, comment))

    if not advanced and advanced_number != advanced_default_number:
        value, comment = advanced_value_comment(advanced_number)
        others.append((ADVANCED_CATEGORY_NAME, value, comment))

    if others:
        instrument_map = CommentedMap()
        instrument_map[active_category] = active_value
        if active_comment:
            instrument_map.yaml_add_eol_comment(active_comment, active_category)
        for cat_name, value, comment in others:
            instrument_map[cat_name] = value
            if comment:
                instrument_map.yaml_add_eol_comment(comment, cat_name)
        out["instrument"] = instrument_map
    else:
        out["instrument"] = active_value
        if active_comment:
            out.yaml_add_eol_comment(active_comment, "instrument")

    _encode_specs(common, SECTION_COMMON_SPECS, f"section_{sec}_common", out, consumed_common)

    consumed_specific = set()
    _encode_specs(specific, SECTION_SPECIFIC_SPECS_BY_SEC[sec], f"section_{sec}_specific",
                  out, consumed_specific)

    consumed_additional = set()
    _encode_specs(additional, SECTION_ADDITIONAL_SPECS, f"section_{sec}_additional", out, consumed_additional)

    return out, consumed_common, consumed_specific, consumed_additional


def _section_from_yaml(sec: str, src: CommentedMap) -> tuple[dict, dict, dict]:
    common: dict = {}
    specific: dict = {}
    additional: dict = {}

    on = bool(src.get("on", False))
    common["section_switch"] = 1 if on else FIELD_DEFAULTS[f"section_{sec}_common.section_switch"]

    base = SECTION_CATEGORY_BASE[sec]

    category, has_cat = _get_path(src, ("category",))
    if not has_cat:
        category = category_name(sec, 0)

    instrument, has_instr = _get_path(src, ("instrument",))
    if has_instr and isinstance(instrument, dict):
        slot_values = dict(instrument)
    elif has_instr:
        slot_values = {category: instrument}
    else:
        slot_values = {}

    advanced = category == ADVANCED_CATEGORY_NAME
    common["advanced_sound_mode_switch"] = (
        1 if advanced else FIELD_DEFAULTS[f"section_{sec}_common.advanced_sound_mode_switch"])

    if advanced:
        common["current_category"] = FIELD_DEFAULTS[f"section_{sec}_common.current_category"]
    else:
        cat_idx = category_index_from_name(sec, category)
        if cat_idx is None:
            raise ValueError(f"unknown category {category!r} for section {sec!r}")
        common["current_category"] = base + cat_idx

    for i in range(4):
        cat_name = category_name(sec, i)
        if cat_name in slot_values:
            value = slot_values[cat_name]
            voices = SECTION_CATEGORIES[sec][i][1]
            voice_raw = voices.index(value) if isinstance(value, str) else value - 1
        else:
            voice_raw = 0
        common[f"category{i + 1}_voice_number"] = voice_raw

    if ADVANCED_CATEGORY_NAME in slot_values:
        value = slot_values[ADVANCED_CATEGORY_NAME]
        number = advanced_voice_number(value) if isinstance(value, str) else value
        voice_raw, extra_raw = advanced_number_to_raw(number)
    else:
        voice_raw = FIELD_DEFAULTS[f"section_{sec}_common.advanced_sound_mode_voice_number"]
        extra_raw = FIELD_DEFAULTS[f"section_{sec}_common.advanced_sound_mode_extra_voice_number"]
    common["advanced_sound_mode_voice_number"] = voice_raw
    common["advanced_sound_mode_extra_voice_number"] = extra_raw

    _decode_specs(common, SECTION_COMMON_SPECS, f"section_{sec}_common", src)
    _decode_specs(specific, SECTION_SPECIFIC_SPECS_BY_SEC[sec], f"section_{sec}_specific", src)
    _decode_specs(additional, SECTION_ADDITIONAL_SPECS, f"section_{sec}_additional", src)

    return common, specific, additional


# ---------------------------------------------------------------------------
# Zone conversion
# ---------------------------------------------------------------------------
def _zone_to_yaml(zone: Zone, zz: int) -> tuple[CommentedMap, set]:
    out2 = CommentedMap()
    consumed = set()
    deferred_on = _encode_specs_main(zone, ZONE_SPECS, f"zone_{zz}", out2, consumed)

    transmit = CommentedMap()
    sw1 = zone.transmit_switches_1
    sw1_default = FIELD_DEFAULTS[f"zone_{zz}.transmit_switches_1"]
    for name, bit in ZONE_TRANSMIT1_BITS:
        bitval = (sw1 >> bit) & 1
        if bitval != ((sw1_default >> bit) & 1):
            transmit[name] = bool(bitval)
    sw2 = zone.transmit_switches_2
    sw2_default = FIELD_DEFAULTS[f"zone_{zz}.transmit_switches_2"]
    for name, bit in ZONE_TRANSMIT2_BITS:
        bitval = (sw2 >> bit) & 1
        if bitval != ((sw2_default >> bit) & 1):
            transmit[name] = bool(bitval)
    consumed.add("transmit_switches_1")
    consumed.add("transmit_switches_2")
    if transmit:
        out2["transmit"] = transmit

    _finalize_on_fields(out2, deferred_on)

    return out2, consumed


def _zone_from_yaml(src: CommentedMap, zz: int) -> dict:
    zone: dict = {}
    for field, path, _enc, dec, _comment_fn in ZONE_SPECS:
        value, found = _get_path(src, path)
        if found:
            zone[field] = dec(value)
        else:
            zone[field] = FIELD_DEFAULTS[f"zone_{zz}.{field}"]

    transmit, has_transmit = _get_path(src, ("transmit",))
    sw1 = FIELD_DEFAULTS[f"zone_{zz}.transmit_switches_1"]
    sw2 = FIELD_DEFAULTS[f"zone_{zz}.transmit_switches_2"]
    if has_transmit:
        for name, bit in ZONE_TRANSMIT1_BITS:
            if name in transmit:
                if transmit[name]:
                    sw1 |= (1 << bit)
                else:
                    sw1 &= ~(1 << bit)
        for name, bit in ZONE_TRANSMIT2_BITS:
            if name in transmit:
                if transmit[name]:
                    sw2 |= (1 << bit)
                else:
                    sw2 &= ~(1 << bit)
    zone["transmit_switches_1"] = sw1
    zone["transmit_switches_2"] = sw2
    return zone


# ---------------------------------------------------------------------------
# Top-level sound conversion
# ---------------------------------------------------------------------------
def sound_to_yaml(ls: LiveSetSound) -> CommentedMap:
    out = CommentedMap()
    # Common.name strips trailing NUL bytes (the Common._strip_trailing_nulls
    # validator), so a NUL-padded name comes back shorter than 15 while a
    # space-padded one keeps its trailing spaces. Re-extend with NULs before
    # trimming so the YAML "name" keeps any trailing NULs but drops trailing
    # spaces -- the mirror of JSON, which lets either padding round-trip
    # exactly (NULs survive via sound_from_yaml's space-pad + the validator's
    # NUL strip). Which padding a name uses is observed device behaviour (in
    # practice real instruments space-pad and the "Init Sound" NUL-pads), not
    # a documented rule.
    out["name"] = ls.common.name.ljust(15, "\x00").rstrip(" ")

    consumed_common = {"name"}
    consumed_additional = set()
    consumed_master_eq = set()

    for sec in paramap.SECTION_NAMES:
        sd = getattr(ls.sections, sec)
        sec_out, c_common, c_specific, c_additional = _section_to_yaml(
            sec, sd.common, sd.specific, sd.additional)

        touch_consumed = set()
        for field_t, path, enc, _dec, comment_fn in TOUCH_SPECS_TEMPLATE:
            field = field_t.format(sec=sec)
            touch_consumed.add(field)
            raw = getattr(ls.common, field)
            default = FIELD_DEFAULTS[f"common.{field}"]
            if raw == default:
                continue
            comment = comment_fn(raw) if comment_fn else None
            _set_path(sec_out, path, enc(raw), comment)
        consumed_common |= touch_consumed

        out[sec] = sec_out

        # leftover fields (not handled by any spec) -> raw fallback
        _raw_fallback(out, f"section_{sec}_common", sd.common, c_common)
        _raw_fallback(out, f"section_{sec}_specific", sd.specific, c_specific)
        _raw_fallback(out, f"section_{sec}_additional", sd.additional, c_additional)

    # top-level common/master_eq/additional groups
    common_out = CommentedMap()
    master_eq_out = CommentedMap()
    for block_key, field, path, enc, _dec, comment_fn in COMMON_SPECS:
        if block_key == "common":
            consumed_common.add(field)
        else:
            consumed_additional.add(field)
        src_block = ls.common if block_key == "common" else ls.additional
        raw = getattr(src_block, field)
        default = FIELD_DEFAULTS[f"{block_key}.{field}"]
        if raw == default and field not in ALWAYS_SHOW:
            continue
        comment = comment_fn(raw) if comment_fn else None
        _set_path(common_out, path, enc(raw), comment)
    if common_out:
        out["common"] = common_out

    _encode_specs(ls.master_eq, MASTER_EQ_SPECS, "master_eq", master_eq_out, consumed_master_eq)
    if master_eq_out:
        out["master_eq"] = master_eq_out

    _raw_fallback(out, "common", ls.common, consumed_common)
    _raw_fallback(out, "additional", ls.additional, consumed_additional)
    _raw_fallback(out, "master_eq", ls.master_eq, consumed_master_eq)
    _raw_fallback(out, "soundmondo", ls.soundmondo, set())

    zones_out = CommentedMap()
    for zz, zone in enumerate(ls.zones):
        zone_out, consumed = _zone_to_yaml(zone, zz)
        if zone_out:
            zones_out[zz + 1] = zone_out
        _raw_fallback(out, f"zone_{zz}", zone, consumed)
    if zones_out:
        out["zones"] = zones_out

    return out


def _fill_reserved(block: dict, fields, defaults_prefix: str):
    """Fill in any fields (mainly reserved_0xNN bytes, and "fixed" fields
    like bulk_format_version) missing from `block` with their default value,
    per the field list from paramap (so codec.py's _encode_block sees
    every field)."""
    for _offset, name, _size, _kind in fields:
        if name not in block:
            block[name] = FIELD_DEFAULTS.get(f"{defaults_prefix}.{name}", 0)


def sound_from_yaml(src: CommentedMap) -> LiveSetSound:
    name = str(src.get("name", "")).ljust(15, " ")
    raw_map = src.get("raw", {}) or {}

    d: dict = {}

    d["soundmondo"] = {
        "soundmondo_format_version_major": FIELD_DEFAULTS["soundmondo.soundmondo_format_version_major"],
        "soundmondo_format_version_minor": FIELD_DEFAULTS["soundmondo.soundmondo_format_version_minor"],
        "soundmondo_format_version_bugfix": FIELD_DEFAULTS["soundmondo.soundmondo_format_version_bugfix"],
    }
    _apply_raw_overrides(d["soundmondo"], raw_map, "soundmondo")
    _fill_reserved(d["soundmondo"], paramap.SOUNDMONDO_FIELDS, "soundmondo")

    d["master_eq"] = {f: FIELD_DEFAULTS[f"master_eq.{f}"] for f, _p, _e, _d, _c in MASTER_EQ_SPECS}
    me_src = src.get("master_eq", CommentedMap())
    for field, path, _enc, dec, _comment_fn in MASTER_EQ_SPECS:
        value, found = _get_path(me_src, path)
        if found:
            d["master_eq"][field] = dec(value)
    _apply_raw_overrides(d["master_eq"], raw_map, "master_eq")
    _fill_reserved(d["master_eq"], paramap.MASTER_EQ_FIELDS, "master_eq")

    d["common"] = {}
    d["additional"] = {}
    d["common"]["name"] = name
    common_src = src.get("common", CommentedMap())
    for block_key, field, path, _enc, dec, _comment_fn in COMMON_SPECS:
        target = d[block_key]
        value, found = _get_path(common_src, path)
        if found:
            target[field] = dec(value)
        else:
            target[field] = FIELD_DEFAULTS[f"{block_key}.{field}"]

    d["zones"] = []
    zones_src = src.get("zones", CommentedMap()) or {}
    for zz in range(paramap.ZONE_COUNT):
        zone_src = zones_src.get(zz + 1, CommentedMap())
        zone = _zone_from_yaml(zone_src, zz)
        _apply_raw_overrides(zone, raw_map, f"zone_{zz}")
        _fill_reserved(zone, paramap.ZONE_FIELDS, f"zone_{zz}")
        d["zones"].append(zone)

    d["sections"] = {}
    for sec in paramap.SECTION_NAMES:
        sec_src = src.get(sec, CommentedMap())
        common, specific, additional = _section_from_yaml(sec, sec_src)

        for field_t, path, _enc, dec, _comment_fn in TOUCH_SPECS_TEMPLATE:
            field = field_t.format(sec=sec)
            value, found = _get_path(sec_src, path)
            if found:
                d["common"][field] = dec(value)
            else:
                d["common"][field] = FIELD_DEFAULTS[f"common.{field}"]

        _apply_raw_overrides(common, raw_map, f"section_{sec}_common")
        _apply_raw_overrides(specific, raw_map, f"section_{sec}_specific")
        _apply_raw_overrides(additional, raw_map, f"section_{sec}_additional")
        _fill_reserved(common, paramap.SECTION_COMMON_FIELDS, f"section_{sec}_common")
        _fill_reserved(specific, paramap.SECTION_SPECIFIC_FIELDS, f"section_{sec}_specific")
        _fill_reserved(additional, paramap.SECTION_ADDITIONAL_FIELDS, f"section_{sec}_additional")

        d["sections"][sec] = {"common": common, "specific": specific, "additional": additional}

    _apply_raw_overrides(d["common"], raw_map, "common")
    _apply_raw_overrides(d["additional"], raw_map, "additional")
    _fill_reserved(d["common"], paramap.COMMON_FIELDS, "common")
    _fill_reserved(d["additional"], paramap.ADDITIONAL_FIELDS, "additional")

    sections = Sections(**{
        sec: Section(
            common=SectionCommon(**blocks["common"]),
            specific=SectionSpecific(**blocks["specific"]),
            additional=SectionAdditional(**blocks["additional"]),
        )
        for sec, blocks in d["sections"].items()
    })
    return LiveSetSound(
        soundmondo=SoundMondo(**d["soundmondo"]),
        master_eq=MasterEq(**d["master_eq"]),
        common=Common(**d["common"]),
        additional=Additional(**d["additional"]),
        zones=[Zone(**z) for z in d["zones"]],
        sections=sections,
    )


# ---------------------------------------------------------------------------
# raw fallback
# ---------------------------------------------------------------------------
def _raw_fallback(out: CommentedMap, block_key: str, block, consumed: set):
    for field in type(block).model_fields:
        if field in consumed:
            continue
        value = getattr(block, field)
        # "name" is always in `consumed` for the "common" block (it's the
        # top-level `name:` field), but guard explicitly: it must never end
        # up in the raw fallback.
        if field == "name":
            continue
        if isinstance(value, list):
            default = FIELD_DEFAULTS.get(f"{block_key}.{field}")
            if default is not None and list(value) == list(default):
                continue
            raw_out = _get_or_create(out, "raw")
            raw_out[f"{block_key}.{field}"] = list(value)
            continue
        default = FIELD_DEFAULTS.get(f"{block_key}.{field}")
        if default is None:
            default = 0
        if value == default:
            continue
        raw_out = _get_or_create(out, "raw")
        raw_out[f"{block_key}.{field}"] = value


def _apply_raw_overrides(block: dict, raw_map: dict, block_key: str):
    prefix = f"{block_key}."
    for key, value in raw_map.items():
        if key.startswith(prefix):
            field = key[len(prefix):]
            block[field] = value


