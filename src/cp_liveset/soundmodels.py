"""
Pydantic models for the cp88-cp73-liveset-v1 Live Set Sound structure.

Generated from paramap.py's field tables -- do not edit by hand.
Regenerate with:

    python tools/gen_soundmodels.py > src/cp_liveset/soundmodels.py
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator



class SoundMondo(BaseModel):
    model_config = ConfigDict(validate_assignment=True, extra="forbid")
    soundmondo_format_version_major: Annotated[int, Field(ge=0, le=127)]
    soundmondo_format_version_minor: Annotated[int, Field(ge=0, le=127)]
    soundmondo_format_version_bugfix: Annotated[int, Field(ge=0, le=127)]
    reserved_0x03: Annotated[int, Field(ge=0, le=127)]


class MasterEq(BaseModel):
    model_config = ConfigDict(validate_assignment=True, extra="forbid")
    eq_gain1: Annotated[int, Field(ge=0, le=127)]
    reserved_0x01: Annotated[int, Field(ge=0, le=127)]
    reserved_0x02: Annotated[int, Field(ge=0, le=127)]
    reserved_0x03: Annotated[int, Field(ge=0, le=127)]
    reserved_0x04: Annotated[int, Field(ge=0, le=127)]
    reserved_0x05: Annotated[int, Field(ge=0, le=127)]
    reserved_0x06: Annotated[int, Field(ge=0, le=127)]
    reserved_0x07: Annotated[int, Field(ge=0, le=127)]
    eq_gain3: Annotated[int, Field(ge=0, le=127)]
    eq_frequency3: Annotated[int, Field(ge=0, le=127)]
    reserved_0x0a: Annotated[int, Field(ge=0, le=127)]
    reserved_0x0b: Annotated[int, Field(ge=0, le=127)]
    reserved_0x0c: Annotated[int, Field(ge=0, le=127)]
    reserved_0x0d: Annotated[int, Field(ge=0, le=127)]
    reserved_0x0e: Annotated[int, Field(ge=0, le=127)]
    reserved_0x0f: Annotated[int, Field(ge=0, le=127)]
    eq_gain5: Annotated[int, Field(ge=0, le=127)]
    reserved_0x11: Annotated[int, Field(ge=0, le=127)]
    reserved_0x12: Annotated[int, Field(ge=0, le=127)]
    eq_on_off: Annotated[int, Field(ge=0, le=127)]


class Common(BaseModel):
    model_config = ConfigDict(validate_assignment=True, extra="forbid")
    name: Annotated[str, StringConstraints(max_length=15, pattern=r"^[\x20-\x7f]*$")]
    bulk_format_version: Annotated[int, Field(ge=0, le=127)]
    reserved_0x10: Annotated[int, Field(ge=0, le=127)]
    zone_mode_switch: Annotated[int, Field(ge=0, le=127)]
    advanced_zone_mode_switch: Annotated[int, Field(ge=0, le=127)]
    live_set_eq_mode_switch: Annotated[int, Field(ge=0, le=127)]
    modulation_lever_assign: Annotated[int, Field(ge=0, le=127)]
    tg_transpose: Annotated[int, Field(ge=0, le=127)]
    split_point: Annotated[int, Field(ge=0, le=127)]
    modulation_lever_limit_low: Annotated[int, Field(ge=0, le=127)]
    modulation_lever_limit_high: Annotated[int, Field(ge=0, le=127)]
    fc1_assign: Annotated[int, Field(ge=0, le=127)]
    fc2_assign: Annotated[int, Field(ge=0, le=127)]
    fc1_limit_low: Annotated[int, Field(ge=0, le=127)]
    fc1_limit_high: Annotated[int, Field(ge=0, le=127)]
    fc2_limit_low: Annotated[int, Field(ge=0, le=127)]
    fc2_limit_high: Annotated[int, Field(ge=0, le=127)]
    reserved_0x1f: Annotated[int, Field(ge=0, le=127)]
    depth_knob_section_select: Annotated[int, Field(ge=0, le=127)]
    piano_touch_sensitivity_depth: Annotated[int, Field(ge=0, le=127)]
    epiano_touch_sensitivity_depth: Annotated[int, Field(ge=0, le=127)]
    sub_touch_sensitivity_depth: Annotated[int, Field(ge=0, le=127)]
    delay_switch: Annotated[int, Field(ge=0, le=127)]
    delay_type: Annotated[int, Field(ge=0, le=127)]
    delay_feedback: Annotated[int, Field(ge=0, le=127)]
    delay_time: Annotated[int, Field(ge=0, le=127)]
    reverb_switch: Annotated[int, Field(ge=0, le=127)]
    piano_touch_sensitivity_offset: Annotated[int, Field(ge=0, le=127)]
    epiano_touch_sensitivity_offset: Annotated[int, Field(ge=0, le=127)]
    reverb_time: Annotated[int, Field(ge=0, le=127)]
    sub_touch_sensitivity_offset: Annotated[int, Field(ge=0, le=127)]
    piano_pitch_modulation_speed: Annotated[int, Field(ge=0, le=127)]
    epiano_pitch_modulation_speed: Annotated[int, Field(ge=0, le=127)]
    sub_pitch_modulation_speed: Annotated[int, Field(ge=0, le=127)]

    # mode='before' so that NUL padding from raw device dumps is
    # stripped before the charset pattern constraint is checked.
    @field_validator("name", mode="before")
    @classmethod
    def _strip_trailing_nulls(cls, v):
        return v.rstrip("\x00") if isinstance(v, str) else v


class Additional(BaseModel):
    model_config = ConfigDict(validate_assignment=True, extra="forbid")
    reserved_0x00: Annotated[int, Field(ge=0, le=127)]
    tempo_delay_time: Annotated[int, Field(ge=0, le=127)]
    tempo_raw: Annotated[list[Annotated[int, Field(ge=0, le=127)]], Field(min_length=2, max_length=2)]
    reserved_0x04: Annotated[int, Field(ge=0, le=127)]
    reserved_0x05: Annotated[int, Field(ge=0, le=127)]
    reserved_0x06: Annotated[int, Field(ge=0, le=127)]
    reserved_0x07: Annotated[int, Field(ge=0, le=127)]
    reserved_0x08: Annotated[int, Field(ge=0, le=127)]
    reserved_0x09: Annotated[int, Field(ge=0, le=127)]
    reserved_0x0a: Annotated[int, Field(ge=0, le=127)]
    reserved_0x0b: Annotated[int, Field(ge=0, le=127)]
    reserved_0x0c: Annotated[int, Field(ge=0, le=127)]
    reserved_0x0d: Annotated[int, Field(ge=0, le=127)]
    reserved_0x0e: Annotated[int, Field(ge=0, le=127)]
    reserved_0x0f: Annotated[int, Field(ge=0, le=127)]


class Zone(BaseModel):
    model_config = ConfigDict(validate_assignment=True, extra="forbid")
    zone_switch: Annotated[int, Field(ge=0, le=127)]
    transmit_channel: Annotated[int, Field(ge=0, le=127)]
    transpose_octave: Annotated[int, Field(ge=0, le=127)]
    transpose_semitone: Annotated[int, Field(ge=0, le=127)]
    note_limit_low: Annotated[int, Field(ge=0, le=127)]
    note_limit_high: Annotated[int, Field(ge=0, le=127)]
    reserved_0x06: Annotated[int, Field(ge=0, le=127)]
    midi_volume: Annotated[int, Field(ge=0, le=127)]
    midi_pan: Annotated[int, Field(ge=0, le=127)]
    midi_bank_msb: Annotated[int, Field(ge=0, le=127)]
    midi_bank_lsb: Annotated[int, Field(ge=0, le=127)]
    midi_program_number: Annotated[int, Field(ge=0, le=127)]
    transmit_switches_1: Annotated[int, Field(ge=0, le=127)]
    transmit_switches_2: Annotated[int, Field(ge=0, le=127)]
    reserved_0x0e: Annotated[int, Field(ge=0, le=127)]
    reserved_0x0f: Annotated[int, Field(ge=0, le=127)]


class SectionCommon(BaseModel):
    model_config = ConfigDict(validate_assignment=True, extra="forbid")
    current_category: Annotated[int, Field(ge=0, le=127)]
    category1_voice_number: Annotated[int, Field(ge=0, le=127)]
    category2_voice_number: Annotated[int, Field(ge=0, le=127)]
    category3_voice_number: Annotated[int, Field(ge=0, le=127)]
    category4_voice_number: Annotated[int, Field(ge=0, le=127)]
    advanced_sound_mode_voice_number: Annotated[int, Field(ge=0, le=127)]
    advanced_sound_mode_switch: Annotated[int, Field(ge=0, le=127)]
    section_switch: Annotated[int, Field(ge=0, le=127)]
    split_mode: Annotated[int, Field(ge=0, le=127)]
    octave_shift: Annotated[int, Field(ge=0, le=127)]
    section_volume: Annotated[int, Field(ge=0, le=127)]
    tone: Annotated[int, Field(ge=0, le=127)]
    advanced_sound_mode_extra_voice_number: Annotated[int, Field(ge=0, le=127)]
    pitch_bend_range: Annotated[int, Field(ge=0, le=127)]
    reserved_0x0e: Annotated[int, Field(ge=0, le=127)]
    pitch_modulation_depth: Annotated[int, Field(ge=0, le=127)]
    reserved_0x10: Annotated[int, Field(ge=0, le=127)]
    receive_expression: Annotated[int, Field(ge=0, le=127)]
    receive_sustain: Annotated[int, Field(ge=0, le=127)]
    receive_sostenuto: Annotated[int, Field(ge=0, le=127)]
    receive_soft: Annotated[int, Field(ge=0, le=127)]
    reserved_0x15: Annotated[int, Field(ge=0, le=127)]
    delay_depth: Annotated[int, Field(ge=0, le=127)]
    reverb_depth: Annotated[int, Field(ge=0, le=127)]


class SectionSpecific(BaseModel):
    model_config = ConfigDict(validate_assignment=True, extra="forbid")
    piano_damper_resonance_switch: Annotated[int, Field(ge=0, le=127)]
    bulk_format_version: Annotated[int, Field(ge=0, le=127)]
    piano_damper_resonance_damper_control: Annotated[int, Field(ge=0, le=127)]
    piano_damper_resonance_dry_wet_balance: Annotated[int, Field(ge=0, le=127)]
    piano_effect_switch: Annotated[int, Field(ge=0, le=127)]
    piano_effect_type: Annotated[int, Field(ge=0, le=127)]
    piano_effect_depth: Annotated[int, Field(ge=0, le=127)]
    reserved_0x07: Annotated[int, Field(ge=0, le=127)]
    epiano_effect1_switch: Annotated[int, Field(ge=0, le=127)]
    epiano_effect1_type: Annotated[int, Field(ge=0, le=127)]
    epiano_effect1_depth: Annotated[int, Field(ge=0, le=127)]
    epiano_effect1_rate: Annotated[int, Field(ge=0, le=127)]
    epiano_effect2_switch: Annotated[int, Field(ge=0, le=127)]
    epiano_effect2_type: Annotated[int, Field(ge=0, le=127)]
    epiano_effect2_depth: Annotated[int, Field(ge=0, le=127)]
    epiano_effect2_speed: Annotated[int, Field(ge=0, le=127)]
    epiano_drive_switch: Annotated[int, Field(ge=0, le=127)]
    epiano_drive: Annotated[int, Field(ge=0, le=127)]
    reserved_0x12: Annotated[int, Field(ge=0, le=127)]
    reserved_0x13: Annotated[int, Field(ge=0, le=127)]
    sub_effect_switch: Annotated[int, Field(ge=0, le=127)]
    sub_effect_type: Annotated[int, Field(ge=0, le=127)]
    sub_effect_depth: Annotated[int, Field(ge=0, le=127)]
    sub_effect_speed: Annotated[int, Field(ge=0, le=127)]
    sub_attack: Annotated[int, Field(ge=0, le=127)]
    sub_release: Annotated[int, Field(ge=0, le=127)]
    reserved_0x1a: Annotated[int, Field(ge=0, le=127)]
    reserved_0x1b: Annotated[int, Field(ge=0, le=127)]


class SectionAdditional(BaseModel):
    model_config = ConfigDict(validate_assignment=True, extra="forbid")
    reserved_0x00: Annotated[int, Field(ge=0, le=127)]
    mono_poly: Annotated[int, Field(ge=0, le=127)]
    portamento_switch: Annotated[int, Field(ge=0, le=127)]
    portamento_time: Annotated[int, Field(ge=0, le=127)]
    portamento_mode: Annotated[int, Field(ge=0, le=127)]
    portamento_time_mode: Annotated[int, Field(ge=0, le=127)]
    reserved_0x06: Annotated[int, Field(ge=0, le=127)]
    reserved_0x07: Annotated[int, Field(ge=0, le=127)]
    pan: Annotated[int, Field(ge=0, le=127)]
    reserved_0x09: Annotated[int, Field(ge=0, le=127)]
    reserved_0x0a: Annotated[int, Field(ge=0, le=127)]
    reserved_0x0b: Annotated[int, Field(ge=0, le=127)]
    reserved_0x0c: Annotated[int, Field(ge=0, le=127)]
    reserved_0x0d: Annotated[int, Field(ge=0, le=127)]
    reserved_0x0e: Annotated[int, Field(ge=0, le=127)]
    reserved_0x0f: Annotated[int, Field(ge=0, le=127)]


class Section(BaseModel):
    model_config = ConfigDict(validate_assignment=True, extra="forbid")
    common: SectionCommon
    specific: SectionSpecific
    additional: SectionAdditional


class Sections(BaseModel):
    model_config = ConfigDict(validate_assignment=True, extra="forbid")
    piano: Section
    epiano: Section
    sub: Section


class LiveSetSound(BaseModel):
    model_config = ConfigDict(validate_assignment=True, extra="forbid")
    soundmondo: SoundMondo
    master_eq: MasterEq
    common: Common
    additional: Additional
    zones: Annotated[list[Zone], Field(min_length=4, max_length=4)]
    sections: Sections
