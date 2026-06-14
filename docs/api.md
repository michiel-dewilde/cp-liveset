# `cp_liveset` Python API

The `cp_liveset` package is a Python library for working with Yamaha
CP88/CP73 **Live Set** data; the `cp-liveset` command line tool is a thin
shell over it. The API sits one level below the CLI: it deals in Python
objects (no endpoint strings, no `FORMAT:LOCATION` parsing, no selection
mini-language) and uses the natural type for each representation:

| Representation | Boundary type |
|---|---|
| JSON document | plain JSON-able `dict` (use `json.load`/`json.dump` yourself) |
| Concise YAML document | `ruamel.yaml` `CommentedMap` (use a `make_yaml()` instance) |
| SysEx Bulk Dump | `list[mido.Message]` (sysex messages) |
| `.X9A`/`.X9L`/`.X9P`/`.X9S` file | `bytes` (the whole container file) |
| Live device | open `mido` input/output ports (you open them) |

Everything is non-streaming: even a full device's 320 Live Set Sounds are small
(~2 MB as JSON).

All public names are importable from the top-level `cp_liveset` package,
which is fully typed (`py.typed`).

```python
import cp_liveset
from cp_liveset import LiveSetSound, LiveSetCollection
```

## The data model: `LiveSetSound`

A `LiveSetSound` is one Live Set Sound: a [pydantic](https://docs.pydantic.dev)
model decoding every byte of the device's 17 SysEx Bulk Dump data blocks
into named integer/string fields (see [json-format.md](json-format.md) for
the complete field reference):

```python
ls = cp_liveset.init_sound()
ls.common.name                                   # 'Init Sound'
ls.sections.piano.common.section_volume          # 100
ls.zones[0].transmit_channel                     # 0
ls.common.reverb_switch = 1                      # validated on assignment
```

Structure: `soundmondo`, `master_eq`, `common`, `additional`, `zones`
(list of 4 `Zone`), and `sections` with `piano`/`epiano`/`sub`, each a
`Section` of `common`/`specific`/`additional`. All sub-models
(`Common`, `Zone`, `Section`, ...) are exported too. Unused bytes are kept
as `reserved_0xNN` fields so every conversion is byte-exact; `name` is the
device's fixed 15-character field with trailing NULs stripped (names padded
with spaces keep their 15 characters; names padded with NULs read shorter).

A single LiveSetSound's JSON shape is pydantic's:

```python
data = ls.model_dump(mode="json")     # plain dict, JSON-able
ls2 = LiveSetSound.model_validate(data)
```

For any other representation of a single Live Set Sound, use a one-entry
`LiveSetCollection` (a Live Set Sound only has a page/set address, a device id, or an
X9 identity as part of a group).

## The container: `LiveSetCollection`

A `LiveSetCollection` maps `(page, set)` → `LiveSetSound` over the device's sparse
40-page × 8-set space (page 1–40, set 1–8, both 1-based). It is a
`MutableMapping`, so selection, merging, and remapping are ordinary dict
operations:

```python
group = LiveSetCollection()                     # empty
group[(1, 5)] = ls                         # keys/values validated
group[(2, 1)] = group.pop((1, 5))          # remap 1:5 -> 2:1
group.update(other_group)                  # merge (later wins)
subset = LiveSetCollection({k: v for k, v in group.items() if k[0] == 2})
```

Iteration is always in `(page, set)` order. Out-of-range or malformed keys
raise `ValueError`/`TypeError` on insertion; values must be `LiveSetSound`
instances. Equality works against any mapping with the same contents.

### JSON: `from_json` / `to_json`

The `cp88-cp73-liveset-v1` document format (the CLI's `json` endpoint),
as plain dicts; serialization is yours:

```python
import json

with open("mysets.json") as f:
    group = LiveSetCollection.from_json(json.load(f))

with open("out.json", "w") as f:
    json.dump(group.to_json(), f, indent=2)
```

`from_json` raises `ValueError` unless `doc["format"] ==
cp_liveset.JSON_FORMAT`.

### YAML: `from_yaml` / `to_yaml` and `make_yaml()`

The concise `cp88-cp73-liveset-yaml-v1` format (the CLI's `yaml`
endpoint): only values differing from the factory defaults are encoded, as
readable names/offsets, with the instrument voice number as the one
end-of-line comment (see [yaml-format.md](yaml-format.md)). The boundary type is a `ruamel.yaml`
`CommentedMap`; `make_yaml()` returns a `ruamel.yaml.YAML` instance
configured for the format's canonical output style:

```python
yaml = cp_liveset.make_yaml()

with open("mysets.yaml") as f:
    group = LiveSetCollection.from_yaml(yaml.load(f))

with open("out.yaml", "w") as f:
    yaml.dump(group.to_yaml(), f)
```

Re-dumping a loaded document through `from_yaml`/`to_yaml` with a
`make_yaml()` instance is byte-identical (canonical), and
`to_yaml -> from_yaml` round-trips exactly. `from_yaml` raises
`ValueError` unless `node["format"] == cp_liveset.YAML_FORMAT`.

### SysEx: `from_sysex` / `to_sysex`

Bulk Dump SysEx as `mido.Message` lists — 19 messages per Live Set Sound (Bulk
Header, 17 data blocks, Bulk Footer). This is the representation to use
with MIDI files (the CLI's `midi` endpoint) or your own MIDI transport:

```python
import mido

# read every Live Set Sound out of a recorded .mid file
mid = mido.MidiFile("dump.mid")
group = LiveSetCollection.from_sysex(msg for track in mid.tracks for msg in track)

# write a .mid file the device can play back from a USB stick / sequencer
out = mido.MidiFile(type=0)
track = mido.MidiTrack()
out.tracks.append(track)
for i, msg in enumerate(group.to_sysex()):
    track.append(msg.copy(time=20 if i > 0 else 0))   # give the device time to digest
out.save("restore.mid")
```

`from_sysex` accepts mido messages and/or raw `bytes` (`F0 ... F7`);
non-sysex mido messages and messages outside a Bulk Header/Footer bracket
are ignored, so you can feed it a whole file's message stream. Incomplete
Live Set Sounds, bad checksums, or non-CP88/CP73 sysex raise
`SysexError`/`ValueError` — unless you pass `ignore_unknown=True`, which
skips any SysEx that is not a well-formed CP88/CP73 Bulk Dump (handy for a
file that interleaves other SysEx). `to_sysex(device_id=0)` embeds the MIDI
SysEx device number (0–15) and emits messages with `time=0`; pacing (the CLI
uses ~20 ms gaps in `.mid` files) is up to you.

For raw `.syx` files (bare concatenated `F0..F7` dumps, the CLI's `syx`
endpoint), pair `from_sysex`/`to_sysex` with `mido.read_syx_file` /
`mido.write_syx_file`.

### X9 files: `from_x9` / `to_x9l` / `to_x9p` / `to_x9s`

The device's own "file menu" formats, as `bytes` of the whole container:

```python
group = LiveSetCollection.from_x9(open("CP BackUp.X9A", "rb").read())   # any .X9A/.X9L/.X9P/.X9S

open("all.X9L", "wb").write(group.to_x9l())          # pages 1-20 x 8 sets
open("page3.X9P", "wb").write(group.to_x9p())        # one page (8 sets)
open("one.X9S", "wb").write(one_entry_group.to_x9s())  # exactly one Live Set Sound
```

- `to_x9l()`: every key must be within pages 1–20 (`X9L_PAGE_COUNT`);
  missing slots are filled with "Init Sound".
- `to_x9p(page=None)`: with `page=None` the page is inferred (the group
  must be non-empty, all on one page); with an explicit `page`, all keys
  must already be on that page — remap first if they aren't. Missing sets
  are filled with "Init Sound".
- `to_x9s()`: the group must hold exactly one Live Set Sound; its key is the
  identity stored in the file (which determines where the device loads
  it). To make a blank file, use
  `LiveSetCollection({(page, set): cp_liveset.init_sound()}).to_x9s()`.
- `.X9A` is read-only (`from_x9` works; there is no `to_x9a`).

**Field coverage caveat**: the X9 blob format stores 189 of the 244
non-reserved fields as parameters (plus the name); the other 54 decode as `0`
on read (bar the fixed format-version stamps, which are filled with their
canonical constants) and are silently dropped on write. `rtmidi`/SysEx round
trips are complete; see the README for details. In particular, sending an
X9-derived Live Set Sound to the device zeroes the ~48 non-version fields among
those.

### Presets

- `cp_liveset.init_sound()` — the "Init Sound" `LiveSetSound` (the device's
  empty-slot default, generated in code) used to fill unused slots. Returns a
  fresh, independent instance on every call.

## Live MIDI I/O

All device functions take *already-open* mido ports; discovering, opening,
and closing ports is left to you — it's one `mido` call and you may want to
hold ports open across many operations:

```python
import mido, cp_liveset

print(mido.get_input_names(), mido.get_output_names())

with mido.open_input("CP88/CP73-1 0") as inp, \
     mido.open_output("CP88/CP73-1 1") as out:
    # read (one Bulk Dump Request per Live Set Sound, ~0.4 s each)
    ls = cp_liveset.request_sound(inp, out, 1, 1)
    group = cp_liveset.request_group(inp, out, [(1, s) for s in range(1, 9)])

    # write (only the addressed slots change on the device)
    cp_liveset.send_sound(out, 2, 1, ls)
    cp_liveset.send_group(out, group)

    # switch the front panel to a Live Set Sound
    cp_liveset.select_sound(out, 2, 1)
```

- `request_sound(inport, outport, page, set_no, *, device_id=0,
  timeout=3.0) -> LiveSetSound` — sends one Bulk Dump Request and collects the
  19-message reply. Pending input is drained first; unrelated traffic is
  ignored. Raises `DeviceTimeoutError` (a `TimeoutError`) if the complete
  reply doesn't arrive within `timeout` seconds.
- `request_group(inport, outport, pairs, *, device_id=0, timeout=3.0) ->
  LiveSetCollection` — `request_sound` for each `(page, set)` in `pairs`
  (`timeout` is per Live Set Sound). The device holds all 320 Live Set Sounds; you
  decide which ones are worth the round trips, so there is no implicit
  "fetch everything" and no lazy proxy object.
- `send_sound(outport, page, set_no, sound, *, device_id=0,
  gap=0.02)` / `send_group(outport, group, *, device_id=0, gap=0.02)` —
  store Live Set Sounds on the device (a complete Bulk Dump per set; `gap`
  seconds between messages so the device keeps up). `send_group` accepts a
  `LiveSetCollection` or any `{(page, set): LiveSetSound}` mapping.
- `select_sound(outport, page, set_no, *, channel=1)` — Bank Select +
  Program Change to switch the panel to a Live Set Sound.
  `select_messages(page, set_no, *, channel=1)` returns the same three
  messages without sending them (e.g. to put in a MIDI file).

`device_id` is the MIDI SysEx device number (0–15) configured on the
instrument (default 0).

## Errors

- `SysexError` (subclass of `ValueError`) — malformed/unexpected SysEx
  data (bad framing, checksum mismatch, missing blocks, ...).
- `DeviceTimeoutError` (subclass of `TimeoutError`) — the device didn't
  answer a Bulk Dump Request in time.
- Plain `ValueError`/`TypeError` — invalid arguments, wrong document
  `format` values, unsatisfiable X9 identity rules, etc.
- pydantic's `ValidationError` — invalid `LiveSetSound` field data.

## Constants

| Name | Value | Meaning |
|---|---|---|
| `PAGE_COUNT` | 40 | User Live Set pages on the device |
| `SETS_PER_PAGE` | 8 | Sets (Program Changes) per page |
| `X9L_PAGE_COUNT` | 20 | Pages storable in `.X9L`/`.X9A` files |
| `JSON_FORMAT` | `"cp88-cp73-liveset-v1"` | `format` value of JSON documents |
| `YAML_FORMAT` | `"cp88-cp73-liveset-yaml-v1"` | `format` value of YAML documents |
| `DEFAULT_TIMEOUT` | 3.0 | Default per-Live-Set request timeout (s) |
| `DEFAULT_SEND_GAP` | 0.02 | Default gap between sent Bulk Dump messages (s) |

`Pair` is the type alias `tuple[int, int]` used for `(page, set)` keys.

## Recipes

Copy a backup's page 1 onto device page 5:

```python
backup = LiveSetCollection.from_x9(open("CP BackUp.X9A", "rb").read())
page5 = LiveSetCollection({(5, s): backup[(1, s)] for s in range(1, 9)})
with mido.open_output("CP88/CP73-1 1") as out:
    cp_liveset.send_group(out, page5)
```

Turn a `.X9A` backup into editable YAML:

```python
group = LiveSetCollection.from_x9(open("CP BackUp.X9A", "rb").read())
with open("backup.yaml", "w", encoding="utf-8") as f:
    cp_liveset.make_yaml().dump(group.to_yaml(), f)
```

Tweak one field on the device without touching anything else:

```python
with mido.open_input(inp_name) as inp, mido.open_output(out_name) as out:
    ls = cp_liveset.request_sound(inp, out, 1, 1)
    ls.common.reverb_time = 50
    cp_liveset.send_sound(out, 1, 1, ls)
```

## Scope notes

Deliberately *not* part of the API (the CLI layers them on top):

- MIDI **port discovery/opening** — plain `mido` already does it
  (`mido.get_input_names()`, `mido.open_input()`, ...).
- **`.mid` file packaging** — `mido.MidiFile` plus
  `from_sysex`/`to_sysex` covers it (see the SysEx section).
- The `convert` command's **selection/remapping spec language** and its
  **demand-driven device download** — in Python these are dict
  comprehensions and an explicit `pairs` list to `request_group`.
