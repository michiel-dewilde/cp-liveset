# Concise YAML Live Set format (`cp88-cp73-liveset-yaml-v1`)

This is the format used by the `yaml` endpoint. It carries exactly the
same information as the [JSON format](json-format.md) (every
`yaml -> json -> yaml` round trip is canonical, and `json -> yaml -> json`
is exact), but:

- only writes fields whose value differs from a computed "standard
  default" (`yamldata.FIELD_DEFAULTS`, derived from a factory-reset
  CP88's 160 Live Set Sounds) — see [Defaults](#defaults) for the actual
  values, so you can tell what an omitted field means;
- decodes raw 0-127 values into human-friendly forms (booleans, signed
  `-64..+63` offsets, named enum/note values); and
- groups related fields under nested keys (`piano.effect.depth`
  instead of a flat `piano_effect_depth`).

Any field not covered by the conventions below - including any field that
is simply not represented in this format yet - is preserved exactly via a
`raw:` map, so nothing is ever lost.

Because the document only contains the values that differ from the defaults,
decoded into readable forms and grouped, it is meant to be **edited by hand**. Small tweaks
— renaming a Live Set Sound, nudging a level, changing a voice, toggling an
effect — are easy to make in any text editor: open the `.yaml`, change the
value (names or raw numbers both work for the enum/note fields), save, and
convert it back (`cp-liveset convert -i myset.yaml -o myset.json`, or straight
to a device/`.X9*`/`.mid` endpoint). Comments are ignored on read, so you do
not need to keep them in sync.

## Top-level document

```yaml
format: cp88-cp73-liveset-yaml-v1
pages:
  1:
    1:
      name: Demo Piano
      ...
    5:
      ...
  2:
    1:
      ...
```

`format` and the `pages: {page: {set: <Live Set Sound>}}` nesting mirror the
JSON format exactly (page/set keys are written as YAML integers here, vs.
strings in JSON). As in JSON, the MIDI SysEx device number is not stored in
the document — it is a property of the `rtmidi`/`midi`/`syx` endpoint.

## Live Set Sound structure

A Live Set Sound is a YAML mapping with these top-level keys, all optional except
`name`:

| key | corresponds to |
|---|---|
| `name` | `common.name` |
| `piano`, `epiano`, `sub` | each section's `common`/`specific`/`additional` blocks, plus the section's touch-sensitivity/pitch-modulation-speed fields from `common` |
| `common` | remaining `common`/`additional` fields not tied to a section |
| `master_eq` | the `master_eq` block |
| `zones` | the 4-element `zones` list, keyed `1`-`4` |
| `raw` | fallback for any field not covered above whose value differs from its default |

### General conventions

- **Booleans**: on/off (`_switch`) fields are written as `true`/`false`,
  almost always under an `on:` key — the section on/off, each effect block's
  `on`, `delay.on`/`reverb.on`, `master_eq.on`, and each zone's `on`.
- **Signed offsets**: fields that are stored as `0-127` with `64` = center
  (pan, transpose, octave shift, pitch bend range, EQ gain, etc.) are
  written as a signed integer `-64..+63` (raw value minus 64).
- **1-based numbers**: `transmit_channel` and `midi_program_number` are
  stored 0-based and written 1-based (channel 1-16, program 1-128).
- **Named enums**: most discrete/enumerated fields (effect types, split
  mode, delay type, mono/poly, portamento modes, depth-knob section, EQ mid
  frequency, delay-time tempo division, and the assignable-controller targets
  `modulation_lever`/`fc1`/`fc2` `assign`) are written as their **name** — e.g.
  `type: Comp`, `mid_freq: 800Hz`, `assign: Modulation`. On read, either the
  name or the raw number is accepted; a value with no known name (e.g. an
  unassignable CC number) is written as the bare number. The full option set
  for every such field is listed under [Enumerations](#enumerations).
- **Note numbers** (`split_point`, zone `note_limit.low/high`) are likewise
  written as the **note name** — e.g. `split_point: D#2`. Either form is
  accepted on read (see [Enumerations](#enumerations) for the note-name
  scheme).
- **Comments**: the only annotation the writer emits is the within-category
  instrument voice number — e.g. `instrument: Nashville C3  # 7` — which
  mirrors the number shown on the instrument's own display. Enum, note, and
  CC values are written as plain names with no `# N` (the raw numbers are in
  [Enumerations](#enumerations) if you want them). Any `# ...` comment is
  informational only and never read back.
- A value equal to its default is normally omitted entirely. A handful of
  fields are written anyway, for readability: the Live Set Sound `name`; each
  section's `on`, `category`, and `instrument` (always shown — even for an
  *off* section sitting on its default voice); and the `common.delay.on` /
  `common.reverb.on` master switches. This redundancy is purely for clarity —
  it is **not** required for a file to be valid: on read, any of these (and any
  other field) may be omitted, and the default is substituted. Re-reading a
  file with a missing field, or a stale/incorrect comment, is never an error.

### `name`

```yaml
name: Natural CFX
```

A plain string, max 15 characters, with trailing **spaces** stripped — the
mirror of the JSON format, which strips trailing NULs instead (see
[`json-format.md`](json-format.md#name-field)). The 15-byte field is
reconstructed on write, so the round trip is byte-exact whatever padding it
used. A name padded with NULs rather than spaces keeps its trailing NUL
bytes here — e.g. the factory "Init Sound" shows as
`Init Sound\x00\x00\x00\x00\x00` — but which padding a name uses is observed
device behavior, not a documented rule.

### Sections (`piano` / `epiano` / `sub`)

```yaml
piano:
  on: true
  category: Grand Piano
  instrument: Nashville C3  # 7  # within-category voice number (mirrors the device display)
  split_mode: L&R
  octave_shift: 0
  volume: 100
  tone: 64
  pitch_bend_range: 2
  pitch_modulation_depth: 5
  receive:
    expression: true
    sustain: true
    sostenuto: true
    soft: true
  delay_depth: 20
  reverb_depth: 21
  touch_sensitivity:
    depth: 64
    offset: 64
  pitch_modulation_speed: 64
  # specific (a section shows only its own specific block; since it is already
  # nested under the section key, the redundant section prefix is dropped)
  damper_resonance:             # piano only
    on: true
    control: 64
    balance: 64
  effect:                       # piano's insert effect
    on: false
    type: Comp
    depth: 31
  # additional
  mono_poly: Poly
  portamento:
    on: false
    time: 64
    mode: Fingered
    time_mode: Rate
  pan: 0
```

The `epiano` and `sub` sections carry their own `specific` blocks under the
same de-prefixed keys:

```yaml
epiano:
  # ...
  effect1:                      # epiano's insert effect 1
    on: true
    type: T.Wah
    depth: 64
    rate: 41
  effect2:                      # epiano's insert effect 2
    on: false
    type: Cho1
    depth: 48
    speed: 64
  drive:                        # epiano's drive
    on: false
    depth: 0
sub:
  # ...
  effect:                       # sub's insert effect
    on: false
    type: Cho/Fla
    depth: 49
    speed: 23
  envelope:                     # sub's amp envelope
    attack: 50
    release: 34
```

Because every section's `specific` block physically stores all three
sections' effect parameters, only the *active* section's prefix is dropped. An
inert copy of another section's effect — which appears only if a file
explicitly sets one — keeps its full prefixed name, so e.g. a stray E.Piano
effect sitting in the `piano` block stays `epiano_effect1`, distinct from
piano's own `effect`.

Every section is always written, with at least `on`, `category`, and
`instrument`. Field reference (JSON field -> YAML path; the effect/envelope
paths below are relative to the section that owns them):

| JSON field (block) | YAML path | encoding |
|---|---|---|
| `section_switch` (`common`) | `on` | bool; section is "off" by default |
| `current_category`, `category{1-4}_voice_number`, `advanced_sound_mode_*` (`common`) | `category`, `instrument` | see [Instrument / voice numbers](#instrument--voice-numbers) |
| `split_mode` (`common`) | `split_mode` | name + raw comment (`yamldata.SPLIT_MODE`) |
| `octave_shift` (`common`) | `octave_shift` | signed -64..+63 |
| `section_volume` (`common`) | `volume` | raw |
| `tone` (`common`) | `tone` | raw |
| `pitch_bend_range` (`common`) | `pitch_bend_range` | signed -64..+63 |
| `pitch_modulation_depth` (`common`) | `pitch_modulation_depth` | raw |
| `receive_expression/sustain/sostenuto/soft` (`common`) | `receive.expression/sustain/sostenuto/soft` | bool |
| `delay_depth` (`common`) | `delay_depth` | raw |
| `reverb_depth` (`common`) | `reverb_depth` | raw |
| `{sec}_touch_sensitivity_depth` (top-level `common`) | `touch_sensitivity.depth` | raw |
| `{sec}_touch_sensitivity_offset` (top-level `common`) | `touch_sensitivity.offset` | raw |
| `{sec}_pitch_modulation_speed` (top-level `common`) | `pitch_modulation_speed` | raw |
| `piano_damper_resonance_switch/damper_control/dry_wet_balance` (`specific`) | `damper_resonance.on/control/balance` | bool / raw |
| `piano_effect_switch/type/depth` (`specific`) | `effect.on/type/depth` (under `piano`) | bool / name / raw |
| `epiano_effect1_switch/type/depth/rate` (`specific`) | `effect1.on/type/depth/rate` (under `epiano`) | bool / name / raw / raw |
| `epiano_effect2_switch/type/depth/speed` (`specific`) | `effect2.on/type/depth/speed` (under `epiano`) | bool / name / raw / raw |
| `epiano_drive_switch`, `epiano_drive` (`specific`) | `drive.on/depth` (under `epiano`) | bool / raw |
| `sub_effect_switch/type/depth/speed` (`specific`) | `effect.on/type/depth/speed` (under `sub`) | bool / name / raw / raw |
| `sub_attack`, `sub_release` (`specific`) | `envelope.attack/release` (under `sub`) | raw |
| `mono_poly` (`additional`) | `mono_poly` | name (`yamldata.MONO_POLY`) |
| `portamento_switch/time/mode/time_mode` (`additional`) | `portamento.on/time/mode/time_mode` | bool / raw / name / name |
| `pan` (`additional`) | `pan` | signed -64..+63 |

#### Instrument / voice numbers

Each section has 4 instrument *categories* (e.g. for `piano`: Grand Piano,
Upright Piano, CP, Layered Piano), each with several voices. The JSON
fields `category1_voice_number`..`category4_voice_number` each hold a
0-based voice index *within that category*, and `current_category`
selects which category is "active" (`current_category - <section base>`,
section bases from `yamlformat.SECTION_CATEGORY_BASE`); see
`yamldata.SECTION_CATEGORIES` for the per-category voice lists.

The YAML format renders this as two keys:

- `category:` — the **name** of the active category (e.g. `Grand Piano`),
  exactly as printed on the panel. If the section is in Advanced Sound Mode
  (`advanced_sound_mode_switch` on), this is the literal `Advanced Mode`
  instead.
- `instrument:` — the active category's voice, written as the voice **name**
  with its 1-based within-category number as a `# N` comment (e.g.
  `Nashville C3  # 7`). This is the **only** comment the writer emits — it
  mirrors the voice number shown on the instrument's own display. If *other*
  categories also have a non-default (non-zero) remembered voice — or, when not
  in Advanced Mode, a non-default Advanced Mode voice — `instrument` becomes a
  **map** of `Category: voice` instead, the active category first, then the
  others (and an `Advanced Mode:` entry for the remembered advanced voice). In
  Advanced Mode, the voice is taken from the global Advanced voice list
  (`yamldata.ADVANCED_VOICES`, No. 1-130) and is written as a plain name with
  **no** number comment (the Advanced voice number is not shown on the device).

Both `category` and `instrument` are always written (an off section keeps the
voice it would play if switched on). On read, a voice may be given by name or
by its raw number, and a missing `category`/`instrument` falls back to the
section's first category and voice.

### `common` (top-level group)

```yaml
common:
  zone_mode: false
  advanced_zone_mode: false
  live_set_eq_mode: false
  modulation_lever:
    assign: Modulation
    limit_low: 0
    limit_high: 127
  tg_transpose: 0
  split_point: C3
  fc1:
    assign: Pedal Wah
    limit_low: 0
    limit_high: 127
  fc2:
    assign: Delay Time
    limit_low: 0
    limit_high: 127
  depth_knob_section: Piano
  delay:
    on: false
    type: Analog
    feedback: 64
    time: 54
    tempo: 100.0                 # one-decimal BPM; see Tempo below
    tempo_delay_time: 1/8
  reverb:
    on: false
    time: 46
```

| JSON field (block) | YAML path | encoding |
|---|---|---|
| `zone_mode_switch` (`common`) | `common.zone_mode` | bool |
| `advanced_zone_mode_switch` (`common`) | `common.advanced_zone_mode` | bool |
| `live_set_eq_mode_switch` (`common`) | `common.live_set_eq_mode` | bool |
| `modulation_lever_assign` (`common`) | `common.modulation_lever.assign` | CC name |
| `modulation_lever_limit_low/high` (`common`) | `common.modulation_lever.limit_low/high` | raw |
| `tg_transpose` (`common`) | `common.tg_transpose` | signed -64..+63 |
| `split_point` (`common`) | `common.split_point` | note name |
| `fc1_assign`, `fc1_limit_low/high` (`common`) | `common.fc1.assign/limit_low/limit_high` | CC name / raw |
| `fc2_assign`, `fc2_limit_low/high` (`common`) | `common.fc2.assign/limit_low/limit_high` | CC name / raw |
| `depth_knob_section_select` (`common`) | `common.depth_knob_section` | name |
| `delay_switch` (`common`) | `common.delay.on` | bool |
| `delay_type` (`common`) | `common.delay.type` | name |
| `delay_feedback` (`common`) | `common.delay.feedback` | raw |
| `delay_time` (`common`) | `common.delay.time` | raw |
| `reverb_switch` (`common`) | `common.reverb.on` | bool |
| `reverb_time` (`common`) | `common.reverb.time` | raw |
| `tempo_raw` (`additional`) | `common.delay.tempo` | BPM as a one-decimal number (raw `[msb, lsb]` list if out of the 42.0–240.0 range) |
| `tempo_delay_time` (`additional`) | `common.delay.tempo_delay_time` | name |

### `master_eq`

```yaml
master_eq:
  low: 0
  mid: 0
  mid_freq: 500Hz
  high: 0
  on: false
```

| JSON field | YAML path | encoding |
|---|---|---|
| `eq_gain1` | `master_eq.low` | signed -64..+63 |
| `eq_gain3` | `master_eq.mid` | signed -64..+63 |
| `eq_frequency3` | `master_eq.mid_freq` | name |
| `eq_gain5` | `master_eq.high` | signed -64..+63 |
| `eq_on_off` | `master_eq.on` | bool |

### `zones`

```yaml
zones:
  1:
    on: true
    transmit_channel: 1
    transpose_octave: 0
    transpose_semitone: 0
    note_limit:
      low: C-2
      high: G8
    volume: 100
    pan: 0
    bank:
      msb: 0
      lsb: 0
    program: 1
    transmit:
      bank_select: true
      program_change: false
      volume: true
      pan: true
      note: true
      pitch_bend: true
      modulation: true
      fc1: true
      fc2: true
      foot_switch: true
      sustain: true
```

`zones` is a map keyed `1`-`4` (only zones with non-default content are
written). Field reference (JSON `zone_*` field -> YAML path):

| JSON field | YAML path | encoding |
|---|---|---|
| `zone_switch` | `on` | bool |
| `transmit_channel` | `transmit_channel` | 1-based (raw + 1) |
| `transpose_octave` | `transpose_octave` | signed -64..+63 |
| `transpose_semitone` | `transpose_semitone` | signed -64..+63 |
| `note_limit_low/high` | `note_limit.low/high` | note name |
| `midi_volume` | `volume` | raw |
| `midi_pan` | `pan` | signed -64..+63 |
| `midi_bank_msb`, `midi_bank_lsb` | `bank.msb`, `bank.lsb` | raw 0-127 each (the device's two separate Bank Select MSB/LSB values), each written only if non-default |
| `midi_program_number` | `program` | 1-based (raw + 1) |
| `transmit_switches_1` bits 0-4 | `transmit.bank_select/program_change/volume/pan/note` | bool, only written if it differs from the default bit |
| `transmit_switches_2` bits 0-5 | `transmit.pitch_bend/modulation/fc1/fc2/foot_switch/sustain` | bool, only written if it differs from the default bit |

### `raw:` fallback

Any field whose value differs from its default but isn't covered by a
mapping above (including `reserved_0xNN` bytes and fixed
`bulk_format_version`/format-version fields if they're ever non-standard) is
written under `raw:`, keyed `block_key.field_name` (the value is a list for
multi-byte fields like `tempo_raw`). The voice/category fields are always
handled by `category`/`instrument` — including out-of-range voice indices,
which are written as their bare 1-based number with no name — so they never
fall through to `raw:`.

```yaml
raw:
  section_piano_specific.bulk_format_version: 0
  zone_0.reserved_0x0e: 5
```

On read, `raw:` entries are applied *after* all other fields are decoded,
so they take precedence (this is how out-of-band/unexpected values are
preserved exactly).

## Tempo

`additional.tempo_raw` (`yaml: common.delay.tempo`) holds the song tempo as a
14-bit value `V = msb*128 + lsb`; the device's BPM is `V / 10` (verified on a
real CP88). The yaml writes it as the **BPM, a one-decimal number** — e.g.
`tempo: 90.0` for the factory default `[7, 4]` (`V = 900`) — across the
device's `42.0`–`240.0` BPM range (`V` `420`–`2400`). A value outside that
range (only reachable from synthetic/corrupt data, never from the device) is
written as the raw `[msb, lsb]` list instead, so it still round-trips exactly.
On read, `common.delay.tempo` accepts either a number (BPM) or a `[msb, lsb]`
list; like every field it is omitted when equal to the `90.0` default. It is
nested under `delay` because the tempo only affects the Tempo Delay effect.

## Defaults

A field is omitted from a YAML document exactly when it equals its default,
so to read a file fully you need to know those defaults. They are authoritative
in `cp_liveset/data/field_defaults.json` (loaded as `yamldata.FIELD_DEFAULTS`)
as **raw 0-127** values; they were computed as the statistical mode (most
common value) of each field across a factory-reset CP88's 160 Live Set Sounds,
with two deliberate overrides — every **section defaults to off**, and the
**category voice numbers default to 0** (instrument 1). The tables below give
the same defaults in their **decoded YAML form** (enum/note names with the raw
number in parentheses where relevant).

A blanket rule covers the "neutral" cases, so the tables only spell out the
rest: unless listed below, an on/off key defaults to `false`, a signed-offset
field (`octave_shift`, `transpose_*`, `pan`, `tg_transpose`) and the
send-depth fields (`delay_depth`, `reverb_depth`) default to `0`, a named enum
defaults to its first option, and `note_limit` defaults to the full `C-2`..`G8`
span.

### `common` and `master_eq`

| YAML path | default |
|---|---|
| `common.modulation_lever.assign` | `Modulation` (1) |
| `common.modulation_lever.limit_low` / `limit_high` | `0` / `127` |
| `common.split_point` | `G2` (55) |
| `common.fc1.assign` | `Expression` (11) |
| `common.fc1.limit_low` / `limit_high` | `0` / `127` |
| `common.fc2.assign` | `Pedal Wah` (4) |
| `common.fc2.limit_low` / `limit_high` | `0` / `127` |
| `common.depth_knob_section` | `All` (0) |
| `common.delay.type` | `Analog` (0) |
| `common.delay.feedback` | `64` |
| `common.delay.time` | `64` |
| `common.delay.tempo` | `90.0` (BPM) |
| `common.delay.tempo_delay_time` | `1/4` (11) |
| `common.reverb.time` | `64` |
| `master_eq.low` / `mid` / `high` | `0` |
| `master_eq.mid_freq` | `500Hz` (28) |

(`common.zone_mode`, `advanced_zone_mode`, `live_set_eq_mode`, `delay.on`,
`reverb.on`, and `master_eq.on` all default to `false`.)

### Sections (`piano` / `epiano` / `sub`)

Shared across all three sections unless a column differs:

| YAML path | piano | epiano | sub |
|---|---|---|---|
| `category` | `Grand Piano` | `Rd` | `Pad/Strings` |
| `instrument` (first voice) | `CFX` | `78Rd` | `Mellow Pad` |
| `volume` | `100` | `127` | `100` |
| `tone` | `64` | `64` | `64` |
| `pitch_bend_range` | `2` | `2` | `2` |
| `pitch_modulation_depth` | `0` | `0` | `10` |
| `receive.*` | `true` | `true` | `true` |
| `touch_sensitivity.depth` / `offset` | `64` / `64` | `64` / `64` | `64` / `64` |
| `pitch_modulation_speed` | `64` | `64` | `64` |
| `mono_poly` | `Poly` (1) | `Poly` (1) | `Poly` (1) |
| `portamento.time` | `64` | `64` | `64` |
| `portamento.mode` | `Full-time` (1) | `Full-time` (1) | `Full-time` (1) |
| `portamento.time_mode` | `Rate` (0) | `Rate` (0) | `Rate` (0) |

Each section's own effect block (`split_mode`, `octave_shift`, `delay_depth`,
`reverb_depth`, `portamento.on`, `pan` all follow the blanket rule):

- **piano**: `damper_resonance` `{on: false, control: 0, balance: 25}`;
  `effect` `{on: false, type: Comp, depth: 64}`
- **epiano**: `effect1` `{on: false, type: A.Pan, depth: 64, rate: 64}`;
  `effect2` `{on: false, type: Cho1, depth: 64, speed: 64}`;
  `drive` `{on: false, depth: 64}`
- **sub**: `effect` `{on: false, type: Cho/Fla, depth: 64, speed: 64}`;
  `envelope` `{attack: 64, release: 64}`

(A section's `specific` block also physically carries the *other* sections'
effect fields; those are inert for it and default to `0`, so they normally
stay omitted — they only surface, via `raw:` or their named path, if a file
happens to set one.)

### Zones (`1`-`4`)

| YAML path | default |
|---|---|
| `on` | `true` for zone 1, `false` for zones 2-4 |
| `transmit_channel` | the zone number (1, 2, 3, 4) |
| `volume` | `100` |
| `program` | `1` |
| `bank.msb` / `bank.lsb` | `0` / `0` |
| `transmit.*` (all 11 switches) | `true` |

## Enumerations

Every field written as a **name** (see [General conventions](#general-conventions))
draws from one of the fixed option sets below — the raw number the SysEx/JSON
format stores, and the name the yaml shows (as the value). The yaml does not
annotate these with the raw number, so this is the reference for it: on read
either the name **or** the raw number is accepted, and a value with no listed
name is written as the bare number. These tables are generated from the
authoritative ones in `cp_liveset/yamldata.py`.

### Switches / modes

| YAML path | options (`raw` = name) |
|---|---|
| `<section>.split_mode` | `0` L&R, `1` L, `2` R |
| `common.delay.type` | `0` Analog, `1` Digital, `2` Tempo |
| `common.depth_knob_section` | `0` All, `1` Piano, `2` E.Piano, `3` Sub |
| `<section>.mono_poly` | `0` Mono, `1` Poly |
| `<section>.portamento.mode` | `0` Fingered, `1` Full-time |
| `<section>.portamento.time_mode` | `0` Rate, `1` Time |

### Effect types

| YAML path | options (`raw` = name) |
|---|---|
| `piano.effect.type` | `0` Comp, `1` Dist/OD, `2` Drive, `3` Chorus |
| `epiano.effect1.type` | `0` A.Pan, `1` Trem, `2` R.Mod, `3` T.Wah, `4` P.Wah, `5` Comp |
| `epiano.effect2.type` | `0` Cho1, `1` Cho2, `2` Fla, `3` Pha1, `4` Pha2, `5` Pha3 |
| `sub.effect.type` | `0` Cho/Fla, `1` Rotary, `2` Trem, `3` Dist/OD |

### Tempo Delay Time (`common.delay.tempo_delay_time`)

Raw `0`–`14`: `0` 1/32 Tri., `1` 1/64 Dot., `2` 1/32, `3` 1/16 Tri., `4` 1/32 Dot., `5` 1/16, `6` 1/8 Tri., `7` 1/16 Dot., `8` 1/8, `9` 1/4 Tri., `10` 1/8 Dot., `11` 1/4, `12` 1/2 Tri., `13` 1/4 Dot., `14` 1/2.

### Master EQ mid frequency (`master_eq.mid_freq`)

Raw `14`–`54`: `14` 100Hz, `15` 110Hz, `16` 125Hz, `17` 140Hz, `18` 160Hz, `19` 180Hz, `20` 200Hz, `21` 225Hz, `22` 250Hz, `23` 280Hz, `24` 315Hz, `25` 355Hz, `26` 400Hz, `27` 450Hz, `28` 500Hz, `29` 560Hz, `30` 630Hz, `31` 700Hz, `32` 800Hz, `33` 900Hz, `34` 1.0kHz, `35` 1.1kHz, `36` 1.2kHz, `37` 1.4kHz, `38` 1.6kHz, `39` 1.8kHz, `40` 2.0kHz, `41` 2.2kHz, `42` 2.5kHz, `43` 2.8kHz, `44` 3.2kHz, `45` 3.6kHz, `46` 4.0kHz, `47` 4.5kHz, `48` 5.0kHz, `49` 5.6kHz, `50` 6.3kHz, `51` 7.0kHz, `52` 8.0kHz, `53` 9.0kHz, `54` 10kHz.

### Note names (`common.split_point`, zone `note_limit.low`/`high`)

Not a fixed list: the raw MIDI note number `0`–`127` is shown as a note name
from `C-2` (0) to `G8` (127), Yamaha numbering (middle C = `C3` = 60, i.e.
octave = number/12 − 2). On read either the name or the number is accepted.

### Assignable controllers (`common.modulation_lever`/`fc1`/`fc2` `.assign`)

The selectable Control Change targets (raw CC number = name). The device
allows `0`–`63`, `65`, `67`–`119`; CC `64` (Sustain) and `66` (Sostenuto)
cannot be assigned.

| raw | name | raw | name | raw | name |
|---|---|---|---|---|---|
| `0` | Bank Select MSB | `32` | Bank Select LSB | `94` | Effect 4 Depth |
| `1` | Modulation | `38` | Data Entry LSB | `95` | Effect 5 Depth |
| `4` | Pedal Wah | `65` | Portamento | `96` | Data Increment |
| `5` | Portamento Time | `67` | Soft | `97` | Data Decrement |
| `6` | Data Entry MSB | `68` | S: Effect SW | `98` | NRPN LSB |
| `7` | All Volume | `71` | Resonance | `99` | NRPN MSB |
| `10` | Pan | `72` | S: Release | `100` | RPN LSB |
| `11` | Expression | `73` | S: Attack | `101` | RPN MSB |
| `12` | P: Select | `74` | Cutoff | `102` | P: SW |
| `13` | P: Volume | `75` | S: Effect Depth | `103` | P: Split |
| `14` | P: Tone | `76` | S: Effect Speed | `104` | P: Octave |
| `15` | P: Damper Reso | `77` | P: Delay Depth | `105` | P: Effect Type |
| `16` | P: Effect SW | `78` | E: Delay Depth | `106` | E: SW |
| `17` | P: Effect Depth | `79` | S: Delay Depth | `107` | E: Split |
| `18` | E: Select | `80` | Delay Time | `108` | E: Octave |
| `19` | E: Volume | `81` | P: Reverb Depth | `109` | E: Effect 1 Type |
| `20` | E: Tone | `82` | E: Reverb Depth | `110` | E: Effect 2 Type |
| `21` | E: Drive SW | `83` | S: Reverb Depth | `111` | S: SW |
| `22` | E: Drive Depth | `84` | Portamento Ctrl | `112` | S: Split |
| `23` | E: Effect 1 SW | `85` | Reverb Time | `113` | S: Octave |
| `24` | E: Effect 1 Depth | `86` | Master EQ SW | `114` | S: Effect Type |
| `25` | E: Effect 1 Rate | `87` | Master EQ High | `115` | Delay SW |
| `26` | E: Effect 2 SW | `88` | Master EQ Mid | `116` | Delay Effect Type |
| `27` | E: Effect 2 Depth | `89` | Master EQ Freq | `117` | Reverb SW |
| `28` | E: Effect 2 Speed | `90` | Master EQ Low | `118` | Depth Knob Select |
| `29` | S: Select | `91` | All Reverb Depth | `119` | USB Audio Volume |
| `30` | S: Volume | `92` | Delay Feedback |  |  |
| `31` | S: Tone | `93` | All Delay Depth |  |  |

### Voice categories and voices (`<section>.category` / `instrument`)

Each section has 4 categories; `category` is the category name and
`instrument` the voice name. The `# N` after a voice is its 1-based position
in the category's list below (the order shown).

**piano**

- `Grand Piano`: CFX, Imperial, S700, Digi Piano, C7, CF3, Nashville C3, Live CF3, Hamburg Grand, CFX2, Imperial+
- `Upright Piano`: U1, SU7, Felt Piano
- `CP`: CP80 1, CP80 2
- `Layered Piano`: Piano Strings, Piano Synth

**epiano**

- `Rd`: 78Rd, 75Rd Funky, 73Rd, 67Rd Dark, 67Rd Bright, 73Rd Studio, 74Rd Stage
- `Wr`: Wr Warm, Wr Bright, Wr Wide
- `Clv`: Clavi B, Clavi S, Harpsichord
- `DX`: DX Legend, DX Woody, DX FTine, DX 7 II, DX Mellow, DX Crisp

**sub**

- `Pad/Strings`: Mellow Pad, Spectrum, Back Pad, Air Choir, Natural Str, Warm Strings, OB Strings, Section Str, Fat Saw Pad, Noble Pad, Pop Pad, Analog Pad, Itopia, Marcato Str, Slow Str, Tape Str, Oct Syn Str, Angel Pad, Mystic Pad, JP Strings, Pop Syn Str, Fast Strings, Pizzicato, Dark Light, Digi Pad, Lite Strings, Unison Str, Violin, Cello
- `Organ`: Bright Bars, Click Organ, Draw Organ 1, All Bars Out, Draw Organ 2, 60s Combo, Compact, Panther, Pipe Organ 1, Pipe Organ 2, Accordion, Musette
- `Chromatic Perc.`: Glocken, Vibraphone, Xylophone, Marimba, Brightness, Nice Bell, Stack Bell, Jazz Vibes, Marimba 2, Kalimba, Heaven Bell
- `Others`: Syn Lead 1, Syn Lead 2, Syn Bass, E.Bass, A.Bass, Steel Gt, Clean Gt, Syn Brass, Sine Lead, Sync Saw, Dirty Hook, Classic Mini, Funky Mini, Nu Mini, 80s Pop Bass, Sub Bass, Unison Bass, Finger Bass, Brass, Syn Brass 2, OB Brass 1, OB Brass 2, Jazz Flute, Tape Flute, Harmonica, Classic Gt, Steel Gt 2, Sf. Brass, 12Strings Gt, Clean Gt 2, Syn Brass 3, Horn, Sax Section, Soprano Sax, Alto Sax, Tenor Sax, Baritone Sax, Soft Square, Calliope Lead, 1o1 Bass

### Advanced Mode voices (`<section>.category: Advanced Mode`)

When a section is in Advanced Sound Mode, `instrument` is taken from a single
global voice list (the `# N` is the Advanced voice number):

| No. | voice | No. | voice | No. | voice | No. | voice |
|---|---|---|---|---|---|---|---|
| `1` | CFX | `34` | Click Organ | `67` | Marcato Str | `100` | Pop Syn Str |
| `2` | Imperial | `35` | Draw Organ 1 | `68` | Slow Str | `101` | Fast Strings |
| `3` | S700 | `36` | All Bars Out | `69` | Tape Str | `102` | Pizzicato |
| `4` | Digi Piano | `37` | Draw Organ 2 | `70` | Oct Syn Str | `103` | Accordion |
| `5` | U1 | `38` | 60s Combo | `71` | Jazz Vibes | `104` | Classic Gt |
| `6` | SU7 | `39` | Compact | `72` | Marimba 2 | `105` | Steel Gt 2 |
| `7` | CP80 1 | `40` | Panther | `73` | Kalimba | `106` | Sf. Brass |
| `8` | CP80 2 | `41` | Pipe Organ 1 | `74` | Heaven Bell | `107` | Hamburg Grand |
| `9` | Piano Strings | `42` | Pipe Organ 2 | `75` | Sine Lead | `108` | Felt Piano |
| `10` | Piano Synth | `43` | Glocken | `76` | Sync Saw | `109` | Dark Light |
| `11` | 78Rd | `44` | Vibraphone | `77` | Dirty Hook | `110` | Digi Pad |
| `12` | 75Rd Funky | `45` | Xylophone | `78` | Classic Mini | `111` | Lite Strings |
| `13` | 73Rd | `46` | Marimba | `79` | Funky Mini | `112` | Unison Str |
| `14` | Wr Warm | `47` | Brightness | `80` | Nu Mini | `113` | Violin |
| `15` | Wr Bright | `48` | Nice Bell | `81` | 80s Pop Bass | `114` | Cello |
| `16` | Clavi B | `49` | Stack Bell | `82` | Sub Bass | `115` | Musette |
| `17` | Clavi S | `50` | Syn Lead 1 | `83` | Unison Bass | `116` | 12Strings Gt |
| `18` | Harpsichord | `51` | Syn Lead 2 | `84` | Finger Bass | `117` | Clean Gt 2 |
| `19` | DX Legend | `52` | Syn Bass | `85` | Brass | `118` | Syn Brass 3 |
| `20` | DX Woody | `53` | E.Bass | `86` | Syn Brass 2 | `119` | Horn |
| `21` | DX FTine | `54` | A.Bass | `87` | OB Brass 1 | `120` | Sax Section |
| `22` | DX 7 II | `55` | Steel Gt | `88` | OB Brass 2 | `121` | Soprano Sax |
| `23` | DX Mellow | `56` | Clean Gt | `89` | Jazz Flute | `122` | Alto Sax |
| `24` | DX Crisp | `57` | Syn Brass | `90` | Tape Flute | `123` | Tenor Sax |
| `25` | Mellow Pad | `58` | C7 | `91` | Harmonica | `124` | Baritone Sax |
| `26` | Spectrum | `59` | 67Rd Dark | `92` | CF3 | `125` | Soft Square |
| `27` | Back Pad | `60` | 67Rd Bright | `93` | 73Rd Studio | `126` | Calliope Lead |
| `28` | Air Choir | `61` | Wr Wide | `94` | 74Rd Stage | `127` | 1o1 Bass |
| `29` | Natural Str | `62` | Fat Saw Pad | `95` | Nashville C3 | `128` | CFX2 |
| `30` | Warm Strings | `63` | Noble Pad | `96` | Live CF3 | `129` | Imperial+ |
| `31` | OB Strings | `64` | Pop Pad | `97` | Angel Pad |  |  |
| `32` | Section Str | `65` | Analog Pad | `98` | Mystic Pad |  |  |
| `33` | Bright Bars | `66` | Itopia | `99` | JP Strings |  |  |

