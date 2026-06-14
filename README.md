# cp-liveset

`cp-liveset` is a Python library and command-line tool for reading,
converting, and writing Yamaha CP88/CP73 **Live Set** data. It moves Live
Set Sounds losslessly between the device's own representations — SysEx Bulk
Dumps over MIDI, `.X9A`/`.X9L`/`.X9P`/`.X9S` files, and a live USB-MIDI
connection — and editable JSON and YAML, so you can back up, inspect, edit,
diff, and restore your sounds with ordinary tools.

## Features

- **Byte-exact round trips** between every supported format: each of the 19
  SysEx Bulk Dump messages that make up a Live Set Sound is decoded into
  named fields and re-encoded identically.
- **Editable JSON** and a **concise YAML** format that shows only
  the fields differing from the factory defaults.
- **Live MIDI I/O**: read, write, and switch Live Set Sounds on a connected
  CP88/CP73.
- **The device's file-menu formats**: read `.X9A` backups and read/write
  `.X9L`, `.X9P`, and `.X9S` files.
- A **fully typed public API** (`import cp_liveset`) with the `cp-liveset`
  command-line tool layered on top of it.

## Installation

```
pip install .
# optional live-MIDI backend (rtmidi: endpoints):
pip install ".[rtmidi]"
# editable install for development:
pip install -e .
```

This installs the `cp-liveset` console script and the importable
`cp_liveset` package, so `cp-liveset ...`, `python -m cp_liveset ...`, and
`import cp_liveset` all work.

### Requirements

- Python 3.9 or newer.
- [`mido`](https://mido.readthedocs.io/), [`pydantic`](https://docs.pydantic.dev)
  v2, and [`ruamel.yaml`](https://yaml.readthedocs.io/) (installed
  automatically).
- [`python-rtmidi`](https://pypi.org/project/python-rtmidi/) for `rtmidi:`
  endpoints (the `rtmidi` optional extra, above). On Windows this needs the
  MSVC build tools if no prebuilt wheel is available for your Python version.

## Quick start

Command line:

```
# Convert a Live Set Sound JSON file to the concise YAML format
cp-liveset convert -i myset.json -o myset.yaml

# Read page 1 from a connected CP88 and save it as JSON
cp-liveset convert -i rtmidi:CP88 1:* -o page1.json
```

Python:

```python
import mido, cp_liveset
from cp_liveset import LiveSetCollection

with mido.open_input("CP88/CP73-1 0") as inp, \
     mido.open_output("CP88/CP73-1 1") as out:
    group = cp_liveset.request_group(inp, out, [(1, 1), (1, 2)])

group[(2, 1)] = group.pop((1, 1))          # remap 1:1 -> 2:1
cp_liveset.send_group(out, group)          # write it back to the device
```

See [`docs/api.md`](https://github.com/michiel-dewilde/cp-liveset/blob/main/docs/api.md) for the full library reference, and the
[Commands](#commands) section below for the command-line tool.

## Data model

A Live Set Sound is addressed as **page** (1-40, "User Live Set Page") and
**set** (1-8, the Program Change number within the page). Each Live Set Sound is
made up of 19 SysEx Bulk Dump blocks: a header/footer pair, a `soundmondo`
(format version) block, a `master_eq` block, a `common` block, an
`additional` (tempo/delay) block, 4 `zones`, and 3 `sections` (`piano`,
`epiano`, `sub`), each with `common`/`specific`/`additional` sub-blocks.
`codec.py` decodes every byte of these blocks into named fields (see
`paramap.py`); unused/reserved bytes are kept as `reserved_0xNN` so a JSON
file can always be converted back into byte-identical SysEx. The Live Set Sound
`name` (a fixed 15-character field on the device) is decoded with trailing
NUL bytes stripped — any other padding, such as trailing spaces, is kept —
and re-padded to 15 bytes with NULs on write, so the round trip is
byte-exact whatever padding the field used. (Which padding it uses isn't
documented by Yamaha: in practice real instruments are space-padded, so
their names keep the full 15 characters, while the factory "Init Sound" of
an empty slot is NUL-padded and reads back shorter.)

See [`docs/json-format.md`](https://github.com/michiel-dewilde/cp-liveset/blob/main/docs/json-format.md) for the complete field
reference. The JSON file produced/consumed by this tool looks like:

```json
{
  "format": "cp88-cp73-liveset-v1",
  "pages": {
    "1": { "5": { "soundmondo": {...}, "master_eq": {...}, "common": {...},
                  "additional": {...}, "zones": [...], "sections": {...} } },
    "2": { "1": {...}, "2": {...} }
  }
}
```

See [`docs/implementation-notes.md`](https://github.com/michiel-dewilde/cp-liveset/blob/main/docs/implementation-notes.md) for notes
on SysEx Bulk Dump framing and other device behavior verified against a real
CP88.

## Python API

Everything the CLI does is built on the public `cp_liveset` package, which
you can use directly for plumbing Live Set data into your own code. The
central types are `LiveSetSound` (one Live Set Sound, a pydantic model) and
`LiveSetCollection` (a dict-like `(page, set) -> LiveSetSound` mapping with
conversions to/from plain JSON dicts, ruamel.yaml documents, mido SysEx
messages, and `.X9*` file bytes), plus live-MIDI functions
(`request_sound`/`request_group`, `send_sound`/`send_group`,
`select_sound`) that work on mido ports you open yourself:

```python
import cp_liveset
from cp_liveset import LiveSetCollection

# read a backup, keep only its page 2, save that as concise YAML
with open("CP BackUp.X9A", "rb") as f:
    group = LiveSetCollection.from_x9(f.read())
page2 = LiveSetCollection({k: v for k, v in group.items() if k[0] == 2})
with open("page2.yaml", "w", encoding="utf-8") as f:
    cp_liveset.make_yaml().dump(page2.to_yaml(), f)
```

`LiveSetCollection` is an ordinary `MutableMapping`, so selecting, merging,
and remapping sounds are plain dict operations; the live-MIDI functions work
on `mido` ports you open yourself. See [`docs/api.md`](https://github.com/michiel-dewilde/cp-liveset/blob/main/docs/api.md) for the
full reference.

## Commands

The command-line tool centers on `convert`, which moves Live Set data
between one or more input endpoints (`-i`/`--input`) and one or more output
endpoints
(`-o`/`--output`), each written as `FORMAT:LOCATION`:

| Format     | Location              | Description                                  |
|------------|-----------------------|-----------------------------------------------|
| `json`     | path to a `.json` file | the `cp88-cp73-liveset-v1` format above       |
| `yaml`     | path to a `.yaml` file | concise human-editable format, see below      |
| `midi`     | path to a `.mid` file  | a SysEx Bulk Dump recorded as a MIDI file     |
| `syx`      | path to a `.syx` file  | raw SysEx Bulk Dumps (bare `F0..F7` messages) |
| `rtmidi`   | `PORT[:DEVICE_ID]` or `IN:OUT[:DEVICE_ID]` | a connected CP88/CP73 (requires `python-rtmidi`) |
| `x9a`      | path to a `.X9A` file | "Back Up" file (read-only)                    |
| `x9l`      | path to a `.X9L` file | "Live Set All" file, 160 sets (read/write)    |
| `x9p`      | path to a `.X9P` file | "Live Set Page" file, 8 sets (read/write)     |
| `x9s`      | path to a `.X9S` file | "Live Set Sound" file, 1 set (read/write)           |

For `rtmidi` endpoints, `LOCATION` is one of:

- `IN:OUT[:DEVICE_ID]`, where `IN` and `OUT` are port *numbers* (the indexes
  shown by `list-midi-ports`) for the input port and output port to use,
  given separately - useful if the device exposes different port indexes for
  input and output. This form is used whenever `LOCATION` starts with a
  digit.
- `PORT[:DEVICE_ID]`, where `PORT` is a port *name* (or a unique prefix of
  one) as shown by `list-midi-ports`, **not starting with a digit**, used for
  *both* input and output. This form is used whenever `LOCATION` does not
  start with a digit.

In both forms, `DEVICE_ID` (0-15, the MIDI SysEx device number to address) is
optional and defaults to 0. Which of the input/output port(s) is actually
used depends on context: `convert -i` only opens the input, `convert -o` and
`select` only open the output; reading a Live Set Sound from a device (`convert -i
rtmidi:...`) needs both, since it sends the request on the output and
receives the reply on the input.

For the `PORT[:DEVICE_ID]` form, a trailing `:<digits>` is taken as
`DEVICE_ID` and stripped from the end - greedily, so only the *last*
`:<digits>` group is stripped. A port name can therefore itself contain or
end in `:<digits>`: if it does, append an extra `:<device_id>` to address
it (e.g. for a port literally named `Foo:1`, use `rtmidi:Foo:1:0` for device
ID 0, or `rtmidi:Foo:1:5` for device ID 5).

For example, `rtmidi:CP88` means port `CP88` for both input and output,
device ID 0; `rtmidi:CP88:5` means port `CP88`, device ID 5; and `rtmidi:1:2`
means input port number 1, output port number 2, device ID 0 (and
`rtmidi:1:2:5` adds device ID 5).

The `FORMAT:` prefix can be omitted for `json`, `yaml`, `midi`, `syx`, `x9a`,
`x9l`, `x9p`, and `x9s` endpoints, in which case the format is inferred from
the file's extension (`.json`, `.yaml`/`.yml`, `.mid`/`.midi`, `.syx`, `.x9a`,
`.x9l`, `.x9p`, `.x9s`, case-insensitive; a trailing `:<page>[:<set>]` override
suffix is ignored for this purpose), e.g. `cp-liveset convert -i
myset.json -o myset.yaml`. `rtmidi` always needs its explicit prefix.

`midi`/`syx` endpoints may have a trailing `:<device_id>` (0-15, default 0)
giving the MIDI SysEx device number to embed when writing. As with the
`rtmidi` `PORT[:DEVICE_ID]` form, the suffix is stripped greedily — only the
*last* `:<digits>` group is taken as `DEVICE_ID` — and the token must be all
digits, so a normal path (e.g. `myset.mid` or `C:\sounds\myset.mid`) is left
untouched; a path that itself ends in `:<digits>` needs an extra
`:<device_id>` appended to address it. When *reading* a `midi` or `syx` file,
any SysEx that is not a CP88/CP73 Live Set Bulk Dump (other manufacturers,
other Yamaha models) is ignored, so a file that interleaves unrelated SysEx is
fine.

For `json`, `yaml`, `midi`, and `syx` endpoints, `LOCATION` may be a literal `-` to
mean stdin (for an input) or stdout (for an output), e.g. `json:-` or
`yaml:-`. Since a format can't be inferred from `-`, the `FORMAT:` prefix is
required in this case (a bare `-` is rejected).

`convert` produces no output on success; it only prints to stderr and exits
non-zero on error. This makes it suitable for use in scripts/pipelines, e.g.
`cp-liveset convert -i json:myset.json -o yaml:- | less`.

A file output (`json`/`yaml`/`midi`/`x9a`/`x9l`/`x9p`/`x9s`) is rewritten from
scratch, replacing its entire previous contents. A `rtmidi` output only
updates the addressed Live Set Sound(s) on the device; everything else on the
device is left unchanged. If a file output already exists, `convert` prompts
for confirmation before overwriting it; pass `-y`/`--yes` to overwrite
without prompting (e.g. in scripts), or `-n`/`--no` to fail instead of
prompting if any output file already exists.

### The working Live Set group

`convert` works against one **working Live Set group**: a full, sparse,
addressable 40-page x 8-set space. Each `-i` reads its endpoint's *incoming*
group and merges it into the working group; each `-o` selects from the
working group into an *outgoing* group and writes it to its endpoint.

By default (no specs after the endpoint), the *whole* incoming/working group
is carried straight through, slot-for-slot. To select only some slots, or
remap them to different page/set numbers, follow `-i`/`-o ENDPOINT` with one
or more specs:

```
*                                  all present (page,set) pairs, identity
<pages>:<sets>                     select these pairs, identity mapping
<pages>:<sets>=<pages>:<sets>      select the left side, remap onto the right
```

`<pages>`/`<sets>` is `*` or a comma-separated list of numbers and/or `a-b`
ranges, e.g. `1`, `1,3,5`, `1-4`, `1,3,5-7`, `*`. On the left of `=` (or with
no `=`), `*` means "whatever is present"; on the right of `=`, `*` means the
full range (1-40 for pages, 1-8 for sets). The two sides of `=` must resolve
to the same number of `(page,set)` pairs, paired up in page-major order.
Multiple `-i`/`-o` (and multiple specs after one endpoint) are processed in
order; later specs overwrite earlier ones for the same destination slot.

A `rtmidi` device always holds all 320 Live Set Sounds, but each one requires its own
MIDI Bulk Dump Request. Regardless of the spec(s) given to a `rtmidi` input,
only the `(page,set)` pairs that the `-o` spec(s) actually end up needing are
downloaded — e.g. `-i rtmidi:CP88 -o json:myset.json 1:5 2:1-8` downloads
just `1:5` and `2:1-8`, and `-i rtmidi:CP88 * -o yaml:out.yaml 1:*=2:*` downloads
just `1:1-8` (since a `rtmidi` device always has all 8 sets of page 1
present), even though the input spec `*` nominally selects all 320. If the
`-o` spec(s) need every `(page,set)` pair (e.g. a bare `*`), all 320 are
downloaded.

Using the same endpoint (e.g. the same `rtmidi` device, or the same file) as
both an input and an output in one `convert` invocation is well-defined: all
inputs are read before any output is written, so the output sees the data as
it was before the command ran.

Writing to `x9p` fills any of the page's 8 sets not present in the output
with "Init Sound"; without a `:PAGE` override (see below), at least one Live
Set must be present, and all of them must belong to the same page. Writing to
`x9l` similarly fills any of its 160 sets (pages 1-20) not present with "Init
Sound". Writing to `x9s` requires at most one Live Set Sound; if the output is
empty, a `:PAGE:SET` override (see below) must be given, and "Init Sound" is
written at that identity.

```
# List the Live Set Sounds present in a JSON file (or x9*, rtmidi, etc.)
cp-liveset inspect json:myset.json
cp-liveset inspect x9a:CP_BackUp.X9A

# List only some Live Set Sounds, using the same '*'/<pages>:<sets> selection
# syntax as 'convert' (without '=' remapping)
cp-liveset inspect rtmidi:CP88 1:5 2:1-8

# Read Live Set Sound 1:5 and all of page 2 from a connected CP88 into JSON
cp-liveset convert -i rtmidi:CP88 1:5 2:1-8 -o json:myset.json

# Write a JSON file's Live Set Sounds back to a connected CP88
cp-liveset convert -i json:myset.json -o rtmidi:CP88

# Convert a Live Set Sound JSON file to a .mid file containing the SysEx Bulk Dump
# (play this file into the CP88's MIDI IN to restore those Live Set Sounds)
cp-liveset convert -i json:myset.json -o midi:myset.mid

# Convert a SysEx .mid file (e.g. captured from the CP88) back to JSON
cp-liveset convert -i midi:myset.mid -o json:myset.json

# Write/read a raw .syx SysEx file (bare F0..F7 dumps, no MIDI-file wrapper)
cp-liveset convert -i json:myset.json -o syx:myset.syx
cp-liveset convert -i syx:myset.syx -o json:myset.json

# Extract just page 1, set 5 from an existing JSON/MIDI file
cp-liveset convert -i json:myset.json 1:5 -o json:subset.json

# Read every Live Set Sound out of a Back Up file into JSON
cp-liveset convert -i x9a:CP_BackUp.X9A -o json:backup.json

# Write a single Live Set Sound to a .X9S file (loads into the device's
# "Live Set Sound" file slot for that page/set)
cp-liveset convert -i json:myset.json 1:5 -o x9s:myset.X9S

# Write a full page (8 sets) to a .X9P file
cp-liveset convert -i json:myset.json 1:1-8 -o x9p:mypage.X9P

# Copy a backup's page 1 onto device page 5
cp-liveset convert -i x9a:CP_BackUp.X9A 1:1-8=5:1-8 -o rtmidi:CP88

# Create blank "Init Sound" .X9P/.X9L/.X9S files (no -i needed)
cp-liveset convert -o x9p:blank.X9P:5
cp-liveset convert -o x9l:blank.X9L
cp-liveset convert -o x9s:blank.X9S:12:2

# Select Live Set page 7, set 3 (write a .mid file, or send it live)
cp-liveset select midi:switch.mid 7:3
cp-liveset select rtmidi:CP88 7:3

# List MIDI ports (requires python-rtmidi)
cp-liveset list-midi-ports
```

`inspect` prints YAML, mapping each page number to a mapping of set number to
Live Set Sound name, e.g.:

```yaml
1:
  5: Simple 78
2:
  1: CFX+DX Legend
  2: A.Bass/78Rd
  3: 80s El Grand
```

## Concise YAML format (`yaml`)

The `yaml` endpoint reads/writes the same data as `json`, but only encodes
values that differ from a "standard" default for that field (computed from a
factory-reset CP88's Live Set Sounds, see `yamldata.FIELD_DEFAULTS`). It uses
`cp88-cp73-liveset-yaml-v1` as its `format` value, and otherwise has the same
top-level `pages` structure as the JSON format. See
[`docs/yaml-format.md`](https://github.com/michiel-dewilde/cp-liveset/blob/main/docs/yaml-format.md) for the complete field
reference.

A few conventions:

- The three sections (`piano`/`epiano`/`sub`) are always written, each with
  at least `on`, `category`, and `instrument`. A section is **off**
  (`on: false`) unless its section switch is set.
- `category` is the section's active voice category and `instrument` its
  active voice **by name**, with the voice's within-category number as a
  `# N` comment — the one annotation the format emits, mirroring the number
  on the instrument's display. If other categories hold a non-default
  remembered voice, `instrument` becomes a `Category: voice` map instead;
  Advanced Sound Mode shows as `category: Advanced Mode`.
- Most discrete/enumerated values (effect types, note numbers, split mode,
  EQ frequency, the assignable-controller targets, etc.) are written by
  **name**, with no raw-number comment (either the name or the raw number is
  accepted on read; the number tables are in
  [`docs/yaml-format.md`](https://github.com/michiel-dewilde/cp-liveset/blob/main/docs/yaml-format.md)).
- Any field not otherwise represented, but which differs from its default, is
  preserved exactly via a `raw:` map keyed `block.field_name`
  (e.g. `raw: {section_piano_specific.bulk_format_version: 0}`), guaranteeing
  an exact `json -> yaml -> json` round trip.
- On read, repeating a default value or omitting comments is not an error.
  Re-writing a Live Set Sound as `yaml` always produces the same canonical
  formatting (`yaml -> json -> yaml` is byte-identical).

For example, a "Demo Piano" Live Set Sound looks like:

```yaml
format: cp88-cp73-liveset-yaml-v1
pages:
  1:
    1:
      name: Demo Piano
      piano:
        on: true
        category: Grand Piano
        instrument: Nashville C3  # 7
        delay_depth: 20
        reverb_depth: 21
        damper_resonance:
          on: true
        effect:
          on: false
          depth: 31
      epiano:
        on: true
        category: Wr
        instrument: Wr Warm  # 1
        tone: 56
        reverb_depth: 17
        effect1:
          on: false
          type: Comp
          rate: 41
        effect2:
          on: true
          type: Fla
          depth: 48
        drive:
          on: false
          depth: 0
      sub:
        on: true
        category: Pad/Strings
        instrument: Analog Pad  # 12
        split_mode: L
        octave_shift: 2
        volume: 58
        tone: 69
        pitch_modulation_depth: 5
        reverb_depth: 28
        effect:
          on: false
          depth: 49
          speed: 23
        envelope:
          attack: 50
          release: 34
      common:
        split_point: D#2
        depth_knob_section: Piano
        delay:
          on: false
          time: 54
        reverb:
          on: true
          time: 46
      master_eq:
        on: false
        mid_freq: 800Hz
```

```
# Convert a Live Set Sound JSON file to the concise yaml format
cp-liveset convert -i json:myset.json -o yaml:myset.yaml

# Edit myset.yaml by hand, then convert back
cp-liveset convert -i yaml:myset.yaml -o json:myset.json
```

## Back Up / Live Set files (.X9A / .X9L / .X9P / .X9S)

The CP88/CP73 can save/load "Back Up" (`.X9A`), "Live Set All" (`.X9L`),
"Live Set Page" (`.X9P`), and "Live Set Sound" (`.X9S`) files via its own file
menu. These are "YSFC" container files; their binary layout is not
documented in the manuals, so this support is based on reverse-engineering
real files exported from a CP88 (see `x9format.py` and `x9data.py`).

Only Live Set data is supported (the rest of `.X9A`'s contents — global
settings, etc. — is ignored):

- **Reading** is supported for all four formats (`x9a`, `x9l`, `x9p`,
  `x9s`). `.X9A`/`.X9L` contain up to 160 Live Set Sounds (pages 1-20 x 8 sets);
  `.X9P` contains one page (8 sets); `.X9S` contains a single Live Set Sound.
- **Writing** is supported for `x9l` (pages 1-20 x 8 sets), `x9p` (one
  page, 8 sets), and `x9s` (at most one Live Set Sound), by patching a
  template file. Any (page, set) slots within `x9l`/`x9p`'s range that
  aren't present in the output are filled with "Init Sound" (the same
  factory-default sound used for unused preset slots). For `x9p` without a
  `:PAGE` override (see below), the output must contain at least one Live
  Set, and all of them must belong to the same page (which becomes the page
  written); with a `:PAGE` override, the output may be empty or contain Live
  Sets from multiple source pages, as long as no two of them end up at the
  same set number on the target page. For `x9s`, if the output is empty, a
  `:PAGE:SET` override (see below) must be given, and "Init Sound" is
  written at that identity. `.X9A` is read-only — to change a backup,
  extract the Live Set Sounds you need with `x9a`, edit them as JSON, and write
  them back as `.X9L`/`.X9P`/`.X9S` files instead.

`.X9P`/`.X9S` files store their own page (and, for `.X9S`, set) number(s),
which is what determines where the device loads them from/to. To
assign/override that identity, append `:PAGE` (for `x9p`) or
`:PAGE[:SET]` (for `x9s`) to the endpoint, on either side of the
conversion, e.g.:

```
# Read "Natural CFX.X9S" as if it were page 3, set 7
cp-liveset convert -i "x9s:Natural CFX.X9S:3:7" -o json:myset.json

# Write Live Set Sound 1:5 to a .X9S file tagged as page 12, set 2
cp-liveset convert -i json:myset.json 1:5 -o x9s:myset.X9S:12:2
```

If `:SET` is omitted for `x9s`, only the page is overridden and the
stored/derived set number is kept.

### Field coverage caveat

Of the 244 non-reserved fields in a Live Set Sound, **189 are stored** as
parameters in the X9 blob (`x9data.FIELD_POSITIONS`, plus `x9data.BIT_POSITIONS`
for the per-zone transmit switches, which the device stores bit-expanded — one
blob byte per switch bit), and the Live Set Sound name is stored too (190 in
all). The remaining **54 fields are not present in the X9 format at all** —
mostly the per-instrument-type effect parameters for a section's *inactive*
instrument types (which the device force-constants), plus the format-version
stamps, the raw tempo value, and a few advanced-mode fields. The mapping was
reverse-engineered by sending sounds with controlled, distinctive values over
MIDI, exporting them from a CP88, and correlating every blob byte against the
device's read-back model (plus all 160 factory sounds); a generated `.X9P` is
**byte-identical** to the device's own export of the same page (the 8 trailing
blob bytes are a constant device chunk).

These 54 fields are real, addressable SysEx Bulk Dump parameters (they come
from the same MIDI Data Table as everything else in `paramap.py`, and round
trip correctly through `rtmidi:`/`midi:`/`syx:`) — Yamaha's own file save just
doesn't persist them. So:

- `x9a`/`x9l`/`x9p`/`x9s` **reads** decode these 54 fields as `0`, except the
  fixed format-version stamps (`soundmondo` major/minor/bugfix and each block's
  `bulk_format_version`), which are filled with their canonical constants
  (`x9data.FIXED_VERSION_FIELDS`) — they are deterministic for a given format
  version, so a read reconstructs them rather than leaving them `0`.
- `x9l`/`x9p`/`x9s` **writes** silently drop any values set for these 54
  fields in the input JSON.
- `rtmidi -> json -> x9*` and `x9* -> json -> x9*` round trips are each
  internally lossless; only the **cross** path loses these 54 fields.
- **Important**: writing an `.X9*`-derived Live Set Sound back to the device
  (`x9* -> json -> rtmidi`) will set the ~48 non-version fields among these to
  `0` on the device (the format-version stamps are sent at their canonical
  values, not zeroed), not leave their existing values unchanged — since the
  JSON decoded from an `.X9*` file has `0` for those, and a `rtmidi:` write
  sends a complete Bulk Dump. If you need to preserve these fields, capture the
  Live Set Sound via `rtmidi:`/`midi:`/`syx:` instead of `.X9*`.

## Sources

All formats this tool reads and writes are taken from Yamaha's official
documentation:

- the [CP88/CP73 Supplementary Manual](https://data.yamaha.com/files/download/other_assets/7/1243337/CP88_CP73_supplementary_manual_En_v200_H0.pdf)
  (`CP88_CP73_supplementary_manual_En_v200_H0.pdf`; its "MIDI Data Table" /
  "MIDI PARAMETER CHANGE TABLE (BULK CONTROL)" sections);
- the [CP88/CP73 Owner's Manual](https://data.yamaha.com/files/download/other_assets/7/1180527/CP88_owners_manual_En_F0.pdf)
  (`CP88_owners_manual_En_F0.pdf`); and
- the text extracted from Yamaha's CP88/CP73 **Data List** download
  (`cp88_cp73_en_om_d0_text/`, distributed as a `.zip`).

Those direct links are to Yamaha's download CDN; if they move, all of the
above are reachable from the official support/download pages
([Yamaha Europe](https://europe.yamaha.com/en/musical-instruments/keyboards/products/stagekeyboards/cp88-73/support.html),
[Yamaha USA](https://usa.yamaha.com/products/contents/music_production/downloads/manuals/index.html?l=en&c=music_production&k=CP88)).

The `.X9A`/`.X9L`/`.X9P`/`.X9S` container layout is not documented by Yamaha.
The *general* YSFC container framing — the 64-byte header, the tag+offset
catalogue, and the paired `Exxx`/`Dxxx` entry/data chunks shared across the
Motif/Montage/MODX YSFC family — follows the structure described by the
[ysfctools](https://github.com/SpotlightKid/ysfctools) project and the
[Yamaha YSFC file-format notes](https://gist.github.com/arachsys/2883877) it
builds on. The CP88/CP73-*specific* details — which chunks carry Live Set
data, the 367-byte Live Set Sound blob layout, and the device's file load
behavior — were reverse-engineered here from real files exported by a CP88
(see [`docs/implementation-notes.md`](https://github.com/michiel-dewilde/cp-liveset/blob/main/docs/implementation-notes.md)).

"CP88", "CP73", and the Voice, category, effect, and control names used to
label sounds and parameters (e.g. "CFX", "DX Legend", "Pedal Wah") are Yamaha's;
they appear here only as factual identifiers for interoperability, and no Yamaha
preset, firmware, or other creative content is included or redistributed.

## License

Released under the [MIT License](https://github.com/michiel-dewilde/cp-liveset/blob/main/LICENSE) — free to use, modify, and
distribute, provided the copyright and license notice are retained.

## Disclaimer / No warranty

This software is provided **"as is", without warranty of any kind**, express
or implied. To the maximum extent permitted by law, the authors and copyright
holders accept **no liability** for any claim, damages, data loss, or other
harm arising from its use, whether in contract, tort, or otherwise (see the
full disclaimer in [`LICENSE`](https://github.com/michiel-dewilde/cp-liveset/blob/main/LICENSE)).

This is an **independent, privately made** project, **not affiliated with,
authorized, sponsored, or endorsed by Yamaha** in any way. "Yamaha", "CP88",
"CP73", and related names are trademarks or product names of Yamaha Corporation,
used here only for identification and interoperability. The SysEx/YSFC formats
it uses are partly reverse-engineered (see
[`docs/implementation-notes.md`](https://github.com/michiel-dewilde/cp-liveset/blob/main/docs/implementation-notes.md)). It can
**write to your CP88/CP73 and overwrite files**: sending Live Set Sounds to a
device replaces what is stored there, writing a file rewrites it from scratch,
and (as noted above) an `.X9*`-derived Live Set Sound zeroes the ~48 non-version
fields the X9 format does not store. **Back up your data first and use at your own
risk** — verify results before relying on them, especially when writing to
hardware.
