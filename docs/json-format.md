# JSON Live Set format (`cp88-cp73-liveset-v1`)

This is the format used by the `json` endpoint (and internally by every
other endpoint - `yaml`, `midi`, `rtmidi`, `x9a`/`x9l`/`x9p`/`x9s` are all
converted to/from this shape). It is a 1:1, byte-exact representation of
the CP88/CP73 "Live Set Sound" SysEx Bulk Dump (19 messages: header, 17
data blocks, footer), as decoded by `codec.py` using the field map in
`paramap.py`.

## Top-level document

```json
{
  "format": "cp88-cp73-liveset-v1",
  "pages": {
    "1": { "5": { ... Live Set Sound ... } },
    "2": { "1": { ... }, "2": { ... } }
  }
}
```

- `format`: always `"cp88-cp73-liveset-v1"`.
- `pages`: a map from **page** ("User Live Set Page", `"1"`-`"40"`, as
  strings) to a map from **set** (the Program Change number within the
  page, `"1"`-`"8"`, as strings) to a **Live Set Sound** dict (below). Only the
  pages/sets actually present are included - a document doesn't need to be
  "complete". The `x9l`/`x9p` endpoints accept any subset and fill the
  remaining slots with "Init Sound" (`x9l` covers pages 1-20; `x9p` covers
  one page's 8 sets, and with no explicit page the document must be non-empty
  and entirely on a single page). Only `x9s` requires exactly one Live Set
  Sound.

The MIDI SysEx device number is **not** stored in the document; it is a
property of the `rtmidi`/`midi`/`syx` endpoint (a trailing `:<device_id>`,
default 0), since it concerns how the data is transmitted, not the Live Set
Sounds themselves.

## Live Set Sound dict

Each Live Set Sound dict has six top-level keys:

```json
{
  "soundmondo": { ... },
  "master_eq": { ... },
  "common": { ... },
  "additional": { ... },
  "zones": [ {...}, {...}, {...}, {...} ],
  "sections": { "piano": {...}, "epiano": {...}, "sub": {...} }
}
```

Every field of every block is present, including bytes that aren't
otherwise meaningful - those are named `reserved_0xNN` (`NN` = the byte's
hex offset within its block). Keeping `reserved_0xNN` bytes verbatim is
what makes `x9* -> json -> x9*`, `midi -> json -> midi`, and
`live -> json -> live` round trips byte-exact.

Every field holds a raw integer **0-127** (the value as transmitted in the
SysEx Bulk Dump), *except* `common.name`, which is a string (see below).
There is no scaling/offsetting applied anywhere in the JSON format - e.g.
a "pan" value of `64` means "center" (the device displays this as `0`);
see [`yaml-format.md`](yaml-format.md) for the human-friendly,
offset/decoded representation.

### `soundmondo` (4 bytes)

Format-version header included in every Live Set Sound bulk dump.

| field | offset | notes |
|---|---|---|
| `soundmondo_format_version_major` | 0x00 | fixed `1` |
| `soundmondo_format_version_minor` | 0x01 | fixed `4` |
| `soundmondo_format_version_bugfix` | 0x02 | fixed `0` |
| `reserved_0x03` | 0x03 | |

### `master_eq` (20 bytes)

| field | offset | notes |
|---|---|---|
| `eq_gain1` | 0x00 | Master EQ Low gain, 0-127 = -12dB..+12dB (64 = 0dB) |
| `eq_gain3` | 0x08 | Master EQ Mid gain, 0-127 = -12dB..+12dB (64 = 0dB) |
| `eq_frequency3` | 0x09 | Master EQ Mid frequency, 14-54 = 100Hz..10kHz |
| `eq_gain5` | 0x10 | Master EQ High gain, 0-127 = -12dB..+12dB (64 = 0dB) |
| `eq_on_off` | 0x13 | Master EQ on/off, 0/1 |
| `reserved_0xNN` | (everything else) | |

### `common` (48 bytes)

| field | offset | notes |
|---|---|---|
| `name` | 0x00-0x0E | Live Set Sound name, see [Name field](#name-field) |
| `bulk_format_version` | 0x0F | fixed `2` |
| `zone_mode_switch` | 0x11 | Zone Mode on/off |
| `advanced_zone_mode_switch` | 0x12 | Advanced Zone Mode on/off |
| `live_set_eq_mode_switch` | 0x13 | Live Set EQ Mode on/off |
| `modulation_lever_assign` | 0x14 | Control Change number assigned to the Modulation Lever |
| `tg_transpose` | 0x15 | Transpose, 0-127, 64 = 0 semitones |
| `split_point` | 0x16 | Split Point note number, 0-127 |
| `modulation_lever_limit_low` | 0x17 | |
| `modulation_lever_limit_high` | 0x18 | |
| `fc1_assign` | 0x19 | Control Change number assigned to Foot Controller 1 |
| `fc2_assign` | 0x1A | Control Change number assigned to Foot Controller 2 |
| `fc1_limit_low` | 0x1B | |
| `fc1_limit_high` | 0x1C | |
| `fc2_limit_low` | 0x1D | |
| `fc2_limit_high` | 0x1E | |
| `depth_knob_section_select` | 0x20 | which section the front-panel Depth knob controls: 0=All, 1=Piano, 2=E.Piano, 3=Sub |
| `piano_touch_sensitivity_depth` | 0x21 | |
| `epiano_touch_sensitivity_depth` | 0x22 | |
| `sub_touch_sensitivity_depth` | 0x23 | |
| `delay_switch` | 0x24 | Delay on/off |
| `delay_type` | 0x25 | 0=Analog, 1=Digital, 2=Tempo |
| `delay_feedback` | 0x26 | |
| `delay_time` | 0x27 | |
| `reverb_switch` | 0x28 | Reverb on/off |
| `piano_touch_sensitivity_offset` | 0x29 | |
| `epiano_touch_sensitivity_offset` | 0x2A | |
| `reverb_time` | 0x2B | |
| `sub_touch_sensitivity_offset` | 0x2C | |
| `piano_pitch_modulation_speed` | 0x2D | |
| `epiano_pitch_modulation_speed` | 0x2E | |
| `sub_pitch_modulation_speed` | 0x2F | |
| `reserved_0xNN` | (everything else) | |

### `additional` (16 bytes)

| field | offset | notes |
|---|---|---|
| `tempo_delay_time` | 0x01 | Delay time as a tempo-relative note value, 0-14 (see `yamldata.TEMPO_DELAY_TIME`) |
| `tempo_raw` | 0x02-0x03 | 2-byte tempo value (list of 2 ints, `msb*128+lsb`); BPM = value/10, default `[7, 4]` (900) = 90.0 BPM |
| `reserved_0xNN` | (everything else) | |

### `zones` (list of 4 dicts, 16 bytes each)

Index 0-3 corresponds to Zone 1-4.

| field | offset | notes |
|---|---|---|
| `zone_switch` | 0x00 | Zone on/off |
| `transmit_channel` | 0x01 | MIDI transmit channel, 0-15 (= channel 1-16) |
| `transpose_octave` | 0x02 | 0-127, 64 = 0 octaves |
| `transpose_semitone` | 0x03 | 0-127, 64 = 0 semitones |
| `note_limit_low` | 0x04 | lowest note transmitted, 0-127 |
| `note_limit_high` | 0x05 | highest note transmitted, 0-127 |
| `midi_volume` | 0x07 | |
| `midi_pan` | 0x08 | 0-127, 64 = center |
| `midi_bank_msb` | 0x09 | |
| `midi_bank_lsb` | 0x0A | |
| `midi_program_number` | 0x0B | 0-127 (= Program Change 1-128) |
| `transmit_switches_1` | 0x0C | bitmask: bit0 Bank Select, bit1 Program Change, bit2 Volume, bit3 Pan, bit4 Note |
| `transmit_switches_2` | 0x0D | bitmask: bit0 Pitch Bend, bit1 Modulation, bit2 FC1, bit3 FC2, bit4 Foot Switch, bit5 Sustain |
| `reserved_0x06`, `reserved_0x0E`, `reserved_0x0F` | | |

### `sections.{piano,epiano,sub}`

Each section has three sub-blocks: `common`, `specific`, `additional`.
All three sub-blocks are present and fully decoded for all three sections,
even if the section is off or its `specific` fields belong to a different
instrument type - this is required for byte-exact round trips.

#### `sections.<sec>.common` (24 bytes)

| field | offset | notes |
|---|---|---|
| `current_category` | 0x00 | which of the section's 4 instrument categories is active (section-relative index 0-3, offset by the section's base - see `yamlformat.SECTION_CATEGORY_BASE`) |
| `category1_voice_number` | 0x01 | voice number within category 1, 0-based |
| `category2_voice_number` | 0x02 | voice number within category 2, 0-based |
| `category3_voice_number` | 0x03 | voice number within category 3, 0-based |
| `category4_voice_number` | 0x04 | voice number within category 4, 0-based |
| `advanced_sound_mode_voice_number` | 0x05 | |
| `advanced_sound_mode_switch` | 0x06 | Advanced Sound Mode on/off |
| `section_switch` | 0x07 | section on/off |
| `split_mode` | 0x08 | 0=L&R, 1=L, 2=R |
| `octave_shift` | 0x09 | 0-127, 64 = 0 octaves |
| `section_volume` | 0x0A | |
| `tone` | 0x0B | |
| `advanced_sound_mode_extra_voice_number` | 0x0C | |
| `pitch_bend_range` | 0x0D | 0-127, 64 = 0 semitones |
| `pitch_modulation_depth` | 0x0F | |
| `receive_expression` | 0x11 | on/off |
| `receive_sustain` | 0x12 | on/off |
| `receive_sostenuto` | 0x13 | on/off |
| `receive_soft` | 0x14 | on/off |
| `delay_depth` | 0x16 | |
| `reverb_depth` | 0x17 | |
| `reserved_0x0E`, `reserved_0x10`, `reserved_0x15` | | |

#### `sections.<sec>.specific` (28 bytes)

These fields only have an effect for the section whose name they share
(`piano_*` for `sections.piano`, `epiano_*` for `sections.epiano`,
`sub_*` for `sections.sub`); for the other two sections they're inert but
still present and preserved.

| field | offset | notes |
|---|---|---|
| `piano_damper_resonance_switch` | 0x00 | |
| `bulk_format_version` | 0x01 | fixed `1` |
| `piano_damper_resonance_damper_control` | 0x02 | |
| `piano_damper_resonance_dry_wet_balance` | 0x03 | |
| `piano_effect_switch` | 0x04 | |
| `piano_effect_type` | 0x05 | 0=Comp, 1=Dist/OD, 2=Drive, 3=Chorus |
| `piano_effect_depth` | 0x06 | |
| `epiano_effect1_switch` | 0x08 | |
| `epiano_effect1_type` | 0x09 | 0=A.Pan, 1=Trem, 2=R.Mod, 3=T.Wah, 4=P.Wah, 5=Comp |
| `epiano_effect1_depth` | 0x0A | |
| `epiano_effect1_rate` | 0x0B | |
| `epiano_effect2_switch` | 0x0C | |
| `epiano_effect2_type` | 0x0D | 0=Cho1, 1=Cho2, 2=Fla, 3=Pha1, 4=Pha2, 5=Pha3 |
| `epiano_effect2_depth` | 0x0E | |
| `epiano_effect2_speed` | 0x0F | |
| `epiano_drive_switch` | 0x10 | |
| `epiano_drive` | 0x11 | |
| `sub_effect_switch` | 0x14 | |
| `sub_effect_type` | 0x15 | 0=Cho/Fla, 1=Rotary, 2=Trem, 3=Dist/OD |
| `sub_effect_depth` | 0x16 | |
| `sub_effect_speed` | 0x17 | |
| `sub_attack` | 0x18 | |
| `sub_release` | 0x19 | |
| `reserved_0xNN` | (everything else) | |

#### `sections.<sec>.additional` (16 bytes)

| field | offset | notes |
|---|---|---|
| `mono_poly` | 0x01 | 0=Mono, 1=Poly |
| `portamento_switch` | 0x02 | |
| `portamento_time` | 0x03 | |
| `portamento_mode` | 0x04 | 0=Fingered, 1=Full-time |
| `portamento_time_mode` | 0x05 | 0=Rate, 1=Time |
| `pan` | 0x08 | 0-127, 64 = center |
| `reserved_0xNN` | (everything else) | |

## Name field

On the wire (SysEx and `.X9*`) the name is a fixed **15-byte ASCII field**,
right-padded to length. In JSON, `common.name` is that field with trailing
**NUL** bytes stripped; any other padding (notably trailing **spaces**) is
kept verbatim. On write the string is re-padded to 15 bytes with NULs, which
reproduces the original bytes exactly — so the round trip is byte-exact
whatever padding the field happened to use. The concise YAML format does the
mirror image, stripping trailing spaces and keeping NULs (see
[`yaml-format.md`](yaml-format.md)).

How the field is padded is not something the device documents; two kinds are
seen in practice. Real instrument names appear space-padded — e.g.
`"Natural CFX    "`, which keeps its full 15 characters in JSON — while the
factory "Init Sound" used for empty slots appears NUL-padded — e.g.
`"Init Sound\x00\x00\x00\x00\x00"`, which reads back as `"Init Sound"`.
Neither is guaranteed; the tool just preserves whatever it finds.

Writing a name longer than 15 characters, or containing characters outside
the `0x20`-`0x7F` range, is an error.

## Field coverage in `.X9*` files

Of the 244 non-reserved fields above, 189 are stored as parameters in `.X9A` /
`.X9L` / `.X9P` / `.X9S` files (plus the name); the remaining 54 (mostly
per-instrument effect parameters for a section's *inactive* instrument types)
are decoded as `0` when reading those formats — except the fixed format-version
stamps, which are filled with their canonical constants — and silently dropped
when writing them. See
the "Field coverage caveat" section of [`README.md`](../README.md) for
details - this only affects the `x9a`/`x9l`/`x9p`/`x9s` endpoints, not
`json`/`yaml`/`midi`/`syx`/`rtmidi`.
