"""
cp-liveset - manage Yamaha CP88/CP73 Live Set data.

Subcommands:
  inspect                list the Live Set Sounds present at an endpoint
  convert                convert Live Set data between json / midi / rtmidi endpoints
  select                 select a Live Set Sound on the CP88/CP73, via a .mid file or rtmidi
  list-midi-ports        list available MIDI port names

This module is a thin shell over the public `cp_liveset` API (LiveSetCollection
and the device I/O functions): everything CLI-specific - endpoint/spec
parsing, MIDI port discovery, .mid file packaging, the x9p/x9s identity
overrides, and the demand-driven device download in `convert` - lives here.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import sys

import mido
from ruamel.yaml.comments import CommentedMap, CommentedSeq

import cp_liveset
from cp_liveset import LiveSetCollection

from . import selectspec

ENDPOINT_FORMATS = ("json", "yaml", "midi", "syx", "rtmidi", "x9a", "x9l", "x9p", "x9s")

DEFAULT_TICKS_PER_BEAT = 480
DEFAULT_GAP_TICKS = 20  # ~20ms gap at 120 BPM, enough for the CP88 to digest each block

# Trailing ":<page>" / ":<page>:<set>" suffix on a x9p:/x9s: location, used
# to assign/override the Live Set page (and, for x9s, set) identity.
_X9P_SUFFIX_RE = re.compile(r"^(.*):(\d+)$")
_X9S_SUFFIX_RE2 = re.compile(r"^(.*):(\d+):(\d+)$")
_X9S_SUFFIX_RE1 = re.compile(r"^(.*):(\d+)$")

# Trailing ":<device_id>" suffix on a rtmidi:/midi: location, used to set the
# MIDI SysEx device number (0-15).
_DEVICE_ID_SUFFIX_RE = re.compile(r"^(.*):(\d+)$")


class _AppendIO(argparse.Action):
    """Like 'append', but -i/-o share a single dest, storing (kind, values)
    tuples in the order the options appear on the command line (kind is
    'i' or 'o', taken from `const`)."""

    def __call__(self, parser, namespace, values, option_string=None):
        items = getattr(namespace, self.dest, None)
        items = list(items) if items else []
        items.append((self.const, values))
        setattr(namespace, self.dest, items)


def _split_device_id(location: str, spec: str) -> tuple[str, int]:
    """Split an optional trailing ":<device_id>" (0-15) off `location`.

    Returns (location, device_id), with device_id 0 if no suffix is present.
    """
    m = _DEVICE_ID_SUFFIX_RE.match(location)
    if not m:
        return location, 0
    device_id = int(m.group(2))
    if not (0 <= device_id <= 15):
        raise argparse.ArgumentTypeError(
            f"invalid device id {device_id} in '{spec}', must be 0-15")
    return m.group(1), device_id


def _parse_rtmidi_location(location: str, spec: str) -> tuple[str, str, int]:
    """Parse a rtmidi LOCATION.

    If LOCATION starts with a digit, it is "IN:OUT[:DEVICE_ID]", where IN and
    OUT are port *numbers* (given separately, since a single number can't
    necessarily address "the same" device in both the input and output port
    lists). Otherwise, it is "PORT[:DEVICE_ID]", where PORT is a port *name*
    (or a unique prefix of one, not starting with a digit), used for both
    input and output. A trailing ":<device_id>" is stripped greedily (only
    the last ":<digits>" group), so a port name that itself ends in
    ":<digits>" needs an extra ":<device_id>" appended to address it.

    Returns (in_port, out_port, device_id), with device_id 0 if no
    ":<device_id>" suffix is present.
    """
    if location[:1].isdigit():
        parts = location.split(":")
        if len(parts) == 2 and all(p.isdigit() for p in parts):
            in_port, out_port, device_id = parts[0], parts[1], 0
        elif len(parts) == 3 and all(p.isdigit() for p in parts):
            in_port, out_port, device_id = parts[0], parts[1], int(parts[2])
        else:
            raise argparse.ArgumentTypeError(
                f"invalid rtmidi location '{location}' in '{spec}', "
                f"expected 'IN:OUT[:DEVICE_ID]' (port numbers)")
        if not (0 <= device_id <= 15):
            raise argparse.ArgumentTypeError(
                f"invalid device id {device_id} in '{spec}', must be 0-15")
    else:
        port, device_id = _split_device_id(location, spec)
        in_port = out_port = port
    return in_port, out_port, device_id

# File extension -> format, used to infer FORMAT when an endpoint is given as
# a bare path with no "FORMAT:" prefix (e.g. "myset.json", "page9.X9P:9").
_EXT_FORMAT_RE = re.compile(r"\.(json|yaml|yml|midi|mid|syx|x9[apls])(:\d+(?::\d+)?)?$",
                            re.IGNORECASE)
_EXT_TO_FORMAT = {
    "json": "json",
    "yaml": "yaml", "yml": "yaml",
    "midi": "midi", "mid": "midi",
    "syx": "syx",
    "x9a": "x9a", "x9l": "x9l", "x9p": "x9p", "x9s": "x9s",
}


def _infer_format(spec: str):
    """Infer FORMAT from `spec`'s file extension (case-insensitive; .yml
    counts as .yaml), or None if it has no recognized extension."""
    m = _EXT_FORMAT_RE.search(spec)
    if not m:
        return None
    return _EXT_TO_FORMAT[m.group(1).lower()]


def parse_endpoint(spec: str):
    """Parse "FORMAT:LOCATION" -> (format, location).

    For format "rtmidi", LOCATION is either:
    - "IN:OUT[:DEVICE_ID]", where IN and OUT are port *numbers* (the indexes
      shown by 'list-midi-ports') for the input port and output port to use,
      given separately; or
    - "PORT[:DEVICE_ID]", where PORT is a port *name* (or a unique prefix of
      one) as shown by 'list-midi-ports', not starting with a digit, used
      for both input and output.
    Which form applies is determined by whether LOCATION starts with a
    digit. DEVICE_ID (0-15, default 0) is the MIDI SysEx device number.
    location is always (in_port, out_port, device_id).

    For formats "midi" and "syx", LOCATION may have a trailing ":<device_id>"
    (0-15, default 0) giving the MIDI SysEx device number to embed when
    writing; location is (path, device_id).

    For formats "x9p"/"x9s", LOCATION may have a trailing ":<page>" (x9p) or
    ":<page>[:<set>]" (x9s) suffix to assign/override the Live Set page/set
    identity; if the suffix is omitted, location is (path, None) / (path,
    None, None) and the identity stored in/derived from the file is used
    unchanged. If only <page> is given for x9s, the stored/derived <set> is
    kept and only the page is overridden.

    The "FORMAT:" prefix may be omitted for "json", "yaml" (".yaml"/".yml"),
    "midi" (".mid"/".midi"), "syx" (".syx"), "x9a", "x9l", "x9p", and "x9s"
    endpoints, in which case FORMAT is inferred from LOCATION's file extension
    (a trailing ":<page>[:<set>]" or ":<device_id>" suffix is ignored for
    this purpose).
    """
    fmt, location = (None, spec)
    if ":" in spec:
        prefix, rest = spec.split(":", 1)
        if prefix in ENDPOINT_FORMATS:
            fmt, location = prefix, rest
    if fmt is None:
        fmt = _infer_format(spec)
        if fmt is None:
            raise argparse.ArgumentTypeError(
                f"invalid endpoint '{spec}', expected FORMAT:LOCATION "
                f"(FORMAT is one of {', '.join(ENDPOINT_FORMATS)}), or a path "
                f"ending in .json, .yaml/.yml, .mid/.midi, .syx, .x9a, .x9l, .x9p, or .x9s")
        location = spec
    if fmt == "rtmidi":
        location = _parse_rtmidi_location(location, spec)
    elif fmt in ("midi", "syx"):
        location, device_id = _split_device_id(location, spec)
        location = (location, device_id)
    elif fmt == "x9p":
        m = _X9P_SUFFIX_RE.match(location)
        if m:
            path, page = m.group(1), int(m.group(2))
            if not (1 <= page <= cp_liveset.PAGE_COUNT):
                raise argparse.ArgumentTypeError(
                    f"invalid page {page} in '{spec}', must be 1-{cp_liveset.PAGE_COUNT}")
            location = (path, page)
        else:
            location = (location, None)
    elif fmt == "x9s":
        m = _X9S_SUFFIX_RE2.match(location) or _X9S_SUFFIX_RE1.match(location)
        if m:
            path = m.group(1)
            page = int(m.group(2))
            set_no = int(m.group(3)) if len(m.groups()) > 2 and m.group(3) is not None else None
            if not (1 <= page <= cp_liveset.PAGE_COUNT):
                raise argparse.ArgumentTypeError(
                    f"invalid page {page} in '{spec}', must be 1-{cp_liveset.PAGE_COUNT}")
            if set_no is not None and not (1 <= set_no <= cp_liveset.SETS_PER_PAGE):
                raise argparse.ArgumentTypeError(
                    f"invalid set {set_no} in '{spec}', must be 1-{cp_liveset.SETS_PER_PAGE}")
            location = (path, page, set_no)
        else:
            location = (location, None, None)
    return fmt, location


def parse_sound_id(s: str):
    """Parse "PAGE:SET" -> (page, set_no), for the 'select' command."""
    if ":" not in s:
        raise argparse.ArgumentTypeError(f"invalid Live Set Sound '{s}', expected PAGE:SET")
    page_s, set_s = s.split(":", 1)
    try:
        page, set_no = int(page_s), int(set_s)
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid Live Set Sound '{s}', expected PAGE:SET (integers)")
    if not (1 <= page <= cp_liveset.PAGE_COUNT):
        raise argparse.ArgumentTypeError(
            f"invalid page {page} in '{s}', must be 1-{cp_liveset.PAGE_COUNT}")
    if not (1 <= set_no <= cp_liveset.SETS_PER_PAGE):
        raise argparse.ArgumentTypeError(
            f"invalid set {set_no} in '{s}', must be 1-{cp_liveset.SETS_PER_PAGE}")
    return page, set_no


def parse_select_endpoint(spec: str):
    """Parse a 'select' destination endpoint: "midi:PATH" or "rtmidi:PORT"."""
    fmt, loc = parse_endpoint(spec)
    if fmt not in ("midi", "rtmidi"):
        raise argparse.ArgumentTypeError(
            f"'select' endpoint must be 'midi:PATH' or 'rtmidi:PORT', got '{spec}'")
    return fmt, loc


def _output_path(fmt, loc):
    """Return the file path a 'convert' output endpoint would write to, or
    None if it isn't file-based ('rtmidi') or is stdout ('-')."""
    if fmt == "rtmidi":
        return None
    path = loc if fmt in ("json", "yaml", "x9a", "x9l") else loc[0]
    return None if path == "-" else path


def _check_overwrite(path, args):
    """Confirm overwriting an existing output file, per --yes/--no/prompt."""
    if not os.path.exists(path):
        return
    if args.no:
        raise ValueError(f"output file '{path}' already exists (use --yes to overwrite)")
    if args.yes:
        return
    answer = input(f"Overwrite existing file '{path}'? [y/N] ")
    if answer.strip().lower() not in ("y", "yes"):
        raise ValueError(f"not overwriting existing file '{path}'")


# --------------------------------------------------------------------------- MIDI ports

def _midi_port_names() -> tuple[list[str], list[str]]:
    """Return (input_names, output_names), or fail with a hint if mido has
    no working backend (python-rtmidi is an optional dependency)."""
    try:
        return mido.get_input_names(), mido.get_output_names()
    except Exception as exc:
        raise ValueError(
            "No working MIDI backend found. Install python-rtmidi "
            "(pip install python-rtmidi) to use live MIDI I/O.") from exc


def _resolve_port(spec: str, names: list[str], kind: str) -> str:
    """Resolve a PORT spec (a port number, or a port name or unique prefix of
    one) to an actual port name from `names`."""
    if spec.isdigit():
        index = int(spec)
        if not (0 <= index < len(names)):
            raise ValueError(f"no {kind} port number {index} (have {len(names)} {kind} port(s))")
        return names[index]
    if spec in names:
        return spec
    matches = [name for name in names if name.startswith(spec)]
    if not matches:
        raise ValueError(f"no {kind} port matching '{spec}'")
    if len(matches) > 1:
        raise ValueError(f"ambiguous {kind} port prefix '{spec}', matches {matches!r}")
    return matches[0]


def _open_input(spec: str):
    inputs, _outputs = _midi_port_names()
    return mido.open_input(_resolve_port(spec, inputs, "input"))


def _open_output(spec: str):
    _inputs, outputs = _midi_port_names()
    return mido.open_output(_resolve_port(spec, outputs, "output"))


# --------------------------------------------------------------------------- MIDI files

def _midifile_to_messages(path) -> list[mido.Message]:
    """Read all SysEx messages from a .mid file ('-' = stdin)."""
    mid = mido.MidiFile(file=sys.stdin.buffer) if path == "-" else mido.MidiFile(path)
    return [msg for track in mid.tracks for msg in track if msg.type == "sysex"]


def _messages_to_midifile(messages: list[mido.Message], path, gap_ticks: int):
    """Write SysEx messages to a type-0 .mid file ('-' = stdout), with a
    `gap_ticks` delay between consecutive messages."""
    mid = mido.MidiFile(type=0, ticks_per_beat=DEFAULT_TICKS_PER_BEAT)
    track = mido.MidiTrack()
    mid.tracks.append(track)
    track.append(mido.MetaMessage("set_tempo", tempo=500000, time=0))
    for i, msg in enumerate(messages):
        track.append(msg.copy(time=gap_ticks if i > 0 else 0))
    track.append(mido.MetaMessage("end_of_track", time=0))
    if path == "-":
        mid.save(file=sys.stdout.buffer)
    else:
        mid.save(path)


def _syxfile_to_messages(path) -> list[mido.Message]:
    """Read all SysEx messages from a .syx file ('-' = stdin)."""
    if path == "-":
        return [m for m in mido.parse_all(sys.stdin.buffer.read()) if m.type == "sysex"]
    return [m for m in mido.read_syx_file(path) if m.type == "sysex"]


def _messages_to_syxfile(messages: list[mido.Message], path):
    """Write SysEx messages to a .syx file ('-' = stdout)."""
    if path == "-":
        sys.stdout.buffer.write(b"".join(msg.bin() for msg in messages))
    else:
        mido.write_syx_file(path, messages)


def _switch_midifile(page: int, set_no: int, path, channel: int):
    """Write a .mid file that selects the given Live Set Sound."""
    mid = mido.MidiFile(type=0, ticks_per_beat=DEFAULT_TICKS_PER_BEAT)
    track = mido.MidiTrack()
    mid.tracks.append(track)
    for msg in cp_liveset.select_messages(page, set_no, channel=channel):
        track.append(msg)
    track.append(mido.MetaMessage("end_of_track", time=0))
    mid.save(path)


# --------------------------------------------------------------------------- x9p/x9s identity overrides

def _remap_page(group: LiveSetCollection, page: int) -> LiveSetCollection:
    """Return a copy of `group` with all Live Set Sounds reassigned to `page`,
    keeping their set numbers (the x9p:PATH:<page> override). Raises if two
    Live Set Sounds from different source pages would end up at the same set."""
    out = LiveSetCollection()
    for (_page, set_no), sound in group.items():
        if (page, set_no) in out:
            raise ValueError(
                f"cannot remap to page {page}: multiple Live Set Sounds map to set {set_no}")
        out[(page, set_no)] = sound
    return out


def _remap_single(group: LiveSetCollection, page: int, set_no: int) -> LiveSetCollection:
    """Return a group containing exactly `group`'s single Live Set Sound,
    reassigned to (page, set_no) (the x9s:PATH:<page>:<set> override)."""
    if len(group) != 1:
        raise ValueError(f"expected exactly one Live Set Sound, got {len(group)}")
    (sound,) = group.values()
    return LiveSetCollection({(page, set_no): sound})


# --------------------------------------------------------------------------- endpoint read/write

def _read_endpoint(fmt, loc) -> LiveSetCollection:
    """Read a non-rtmidi endpoint into a LiveSetCollection ('rtmidi' is handled
    separately by _read_rtmidi, since it needs an explicit pair list)."""
    if fmt == "json":
        if loc == "-":
            doc = json.load(sys.stdin)
        else:
            with open(loc, "r", encoding="utf-8") as f:
                doc = json.load(f)
        return LiveSetCollection.from_json(doc)
    if fmt == "yaml":
        yaml = cp_liveset.make_yaml()
        if loc == "-":
            node = yaml.load(sys.stdin)
        else:
            with open(loc, "r", encoding="utf-8") as f:
                node = yaml.load(f)
        return LiveSetCollection.from_yaml(node)
    if fmt in ("midi", "syx"):
        path, _device_id = loc
        reader = _midifile_to_messages if fmt == "midi" else _syxfile_to_messages
        group = LiveSetCollection.from_sysex(reader(path), ignore_unknown=True)
        if not group:
            raise ValueError("no complete Live Set Sound found in input file")
        return group
    if fmt in ("x9a", "x9l"):
        with open(loc, "rb") as f:
            return LiveSetCollection.from_x9(f.read())
    if fmt == "x9p":
        path, page = loc
        with open(path, "rb") as f:
            group = LiveSetCollection.from_x9(f.read())
        return _remap_page(group, page) if page is not None else group
    if fmt == "x9s":
        path, page, set_no = loc
        with open(path, "rb") as f:
            group = LiveSetCollection.from_x9(f.read())
        if page is not None:
            group = (_remap_single(group, page, set_no) if set_no is not None
                     else _remap_page(group, page))
        return group
    raise ValueError(f"cannot read endpoint format '{fmt}'")


def _read_rtmidi(loc, pairs, timeout: float) -> LiveSetCollection:
    """Read the given (page, set) pairs from a connected device."""
    in_spec, out_spec, device_id = loc
    with contextlib.ExitStack() as stack:
        inport = stack.enter_context(_open_input(in_spec))
        outport = stack.enter_context(_open_output(out_spec))
        return cp_liveset.request_group(
            inport, outport, sorted(pairs), device_id=device_id, timeout=timeout)


def _write_endpoint(fmt, loc, group: LiveSetCollection, gap_ticks: int):
    """Write a LiveSetCollection to an output endpoint."""
    if fmt == "json":
        doc = group.to_json()
        if loc == "-":
            json.dump(doc, sys.stdout, indent=2)
            sys.stdout.write("\n")
        else:
            with open(loc, "w", encoding="utf-8") as f:
                json.dump(doc, f, indent=2)
                f.write("\n")
        return
    if fmt == "yaml":
        yaml = cp_liveset.make_yaml()
        node = group.to_yaml()
        if loc == "-":
            yaml.dump(node, sys.stdout)
        else:
            with open(loc, "w", encoding="utf-8") as f:
                yaml.dump(node, f)
        return
    if fmt in ("midi", "syx"):
        path, device_id = loc
        messages = group.to_sysex(device_id=device_id)
        if not messages:
            raise ValueError("document contains no Live Set Sounds")
        if fmt == "midi":
            _messages_to_midifile(messages, path, gap_ticks)
        else:
            _messages_to_syxfile(messages, path)
        return
    if fmt == "x9a":
        raise NotImplementedError(
            "Writing .X9A files is not supported (only reading); "
            "write 'x9l:PATH' (all 160 sets), 'x9p:PATH' (one page, 8 sets), "
            "or 'x9s:PATH' (one Live Set Sound) instead.")
    if fmt == "x9l":
        with open(loc, "wb") as f:
            f.write(group.to_x9l())
        return
    if fmt == "x9p":
        path, page = loc
        if page is not None:
            group = _remap_page(group, page)
        with open(path, "wb") as f:
            f.write(group.to_x9p(page))
        return
    if fmt == "x9s":
        path, page, set_no = loc
        if page is not None:
            if set_no is not None:
                group = (_remap_single(group, page, set_no) if group
                         else LiveSetCollection({(page, set_no): cp_liveset.init_sound()}))
            else:
                group = _remap_page(group, page)
        if not group:
            raise ValueError(
                "writing .X9S with no Live Set Sound requires both the page and set "
                "to be specified (e.g. 'x9s:PATH:PAGE:SET')")
        with open(path, "wb") as f:
            f.write(group.to_x9s())
        return
    if fmt == "rtmidi":
        _in_spec, out_spec, device_id = loc
        with _open_output(out_spec) as outport:
            cp_liveset.send_group(outport, group, device_id=device_id)
        return
    raise ValueError(f"cannot write endpoint format '{fmt}'")


# --------------------------------------------------------------------------- commands

def cmd_list_midi_ports(args):
    inputs, outputs = _midi_port_names()
    doc = CommentedMap()
    for key, names in (("in", inputs), ("out", outputs)):
        seq = CommentedSeq(names)
        for i in range(len(names)):
            seq.yaml_add_eol_comment(str(i), i)
        doc[key] = seq
    cp_liveset.make_yaml().dump(doc, sys.stdout)


def cmd_convert(args):
    io_items = args.io
    inputs = [tokens for kind, tokens in io_items if kind == "i"]
    outputs = [tokens for kind, tokens in io_items if kind == "o"]

    # Confirm overwriting any existing output files up front, before doing
    # any (potentially slow) reads.
    for tokens in outputs:
        endpoint, *_specs = tokens
        fmt, loc = parse_endpoint(endpoint)
        path = _output_path(fmt, loc)
        if path is not None:
            _check_overwrite(path, args)

    # convert runs in three phases:
    #   1. read all inputs (below)
    #   2. process -i/-o left to right, merging each input into a "working
    #      set" and taking a snapshot of it for each output (cmd_convert's
    #      final loop below)
    #   3. write all output snapshots
    # Phase 1 happening fully before phase 3 makes using the same endpoint as
    # both an input and an output well-defined (a write sees the endpoint's
    # contents from before this command ran). Phase 2's left-to-right order
    # makes "-i Ai 1:1 -o Ao -i Bi 1:1 -o Bo" well-defined too: Ao gets Ai's
    # 1:1 and Bo gets Bi's 1:1, even though both inputs target the same
    # working-set slot (1:1) -- Bi's merge happens after Ao's snapshot is
    # taken. Don't introduce streaming/incremental I/O that collapses these
    # phases without re-examining this.

    # Pass 1: read each input (eagerly for non-rtmidi; 'rtmidi' inputs are
    # read in pass 3, since each Live Set Sound requires its own MIDI Bulk Dump
    # Request and we want to fetch only what's actually used), and resolve
    # its specs against its own "present" set into a list of (src, dst)
    # pairs.
    incoming: list[LiveSetCollection | None] = []
    mappings: list[list[tuple[tuple[int, int], tuple[int, int]]]] = []
    for tokens in inputs:
        endpoint, *specs = tokens
        fmt, loc = parse_endpoint(endpoint)
        if fmt == "rtmidi":
            incoming.append(None)
            present = selectspec.ALL_PAIRS
        else:
            group = _read_endpoint(fmt, loc)
            incoming.append(group)
            present = set(group.keys())
        mapping = []
        for spec in (specs or ["*"]):
            mapping.extend(selectspec.resolve(spec, present))
        mappings.append(mapping)

    # Pass 2: for 'rtmidi' inputs, determine which source pairs feed into any
    # output's destination slots, so only those are downloaded. This ignores
    # -i/-o ordering (a conservative superset), which is safe: it may fetch a
    # few pairs that end up unused, but never misses one that's needed.
    all_dsts = {dst for mapping in mappings for _src, dst in mapping}
    read_dsts: set[tuple[int, int]] = set()
    for tokens in outputs:
        endpoint, *specs = tokens
        for spec in (specs or ["*"]):
            for src, _dst in selectspec.resolve(spec, all_dsts):
                read_dsts.add(src)
    needed: list[set] = [set() for _ in inputs]
    for idx, mapping in enumerate(mappings):
        if incoming[idx] is None:
            for src, dst in mapping:
                if dst in read_dsts:
                    needed[idx].add(src)

    # Pass 3: fetch 'rtmidi' inputs, downloading only the needed pairs.
    for idx, tokens in enumerate(inputs):
        if incoming[idx] is not None:
            continue
        endpoint, *specs = tokens
        fmt, loc = parse_endpoint(endpoint)
        pairs = sorted(needed[idx])
        incoming[idx] = _read_rtmidi(loc, pairs, args.timeout) if pairs else LiveSetCollection()

    # Phase 2: walk -i/-o left to right, merging each input into `working`
    # and taking an output snapshot at each -o's position.
    working = LiveSetCollection()
    snapshots = []
    in_idx = 0
    for kind, tokens in io_items:
        if kind == "i":
            for src, dst in mappings[in_idx]:
                if src in incoming[in_idx]:
                    working[dst] = incoming[in_idx][src]
            in_idx += 1
        else:
            endpoint, *specs = tokens
            fmt, loc = parse_endpoint(endpoint)
            present = set(working.keys())
            outgoing = LiveSetCollection()
            for spec in (specs or ["*"]):
                for src, dst in selectspec.resolve(spec, present):
                    if src in working:
                        outgoing[dst] = working[src]
            snapshots.append((fmt, loc, outgoing))

    # Phase 3: write all output snapshots.
    for fmt, loc, outgoing in snapshots:
        _write_endpoint(fmt, loc, outgoing, args.gap_ticks)


def cmd_inspect(args):
    fmt, loc = parse_endpoint(args.endpoint)
    for spec in args.specs:
        if "=" in spec:
            raise ValueError(f"'show' does not support remapping ('=') in spec '{spec}'")

    if fmt == "rtmidi":
        if args.specs:
            pairs = set()
            for spec in args.specs:
                for src, _dst in selectspec.resolve(spec, selectspec.ALL_PAIRS):
                    pairs.add(src)
        else:
            pairs = selectspec.ALL_PAIRS
        group = _read_rtmidi(loc, pairs, args.timeout)
    else:
        group = _read_endpoint(fmt, loc)
        if args.specs:
            present = set(group.keys())
            wanted = set()
            for spec in args.specs:
                for src, _dst in selectspec.resolve(spec, present):
                    wanted.add(src)
            group = LiveSetCollection(
                {pair: sound for pair, sound in group.items() if pair in wanted})

    doc = CommentedMap()
    for page, set_no in sorted(group):
        name = group[(page, set_no)].common.name.ljust(15, "\x00").rstrip(" ")
        doc.setdefault(page, CommentedMap())[set_no] = name
    cp_liveset.make_yaml().dump(doc, sys.stdout)


def cmd_select(args):
    fmt, loc = args.endpoint
    page, set_no = args.sound
    if fmt == "midi":
        path = loc[0]
        _switch_midifile(page, set_no, path, channel=args.channel)
    else:  # rtmidi
        with _open_output(loc[1]) as outport:
            cp_liveset.select_sound(outport, page, set_no, channel=args.channel)


# --------------------------------------------------------------------------- main

def _package_version() -> str:
    from importlib.metadata import PackageNotFoundError, version
    try:
        return version("cp-liveset")
    except PackageNotFoundError:
        return "unknown"


def build_parser():
    parser = argparse.ArgumentParser(prog="cp-liveset", description=__doc__,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--version", action="version",
                        version=f"%(prog)s {_package_version()}")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser(
        "inspect",
        help="list the Live Set Sounds present at an endpoint",
        description=(
            "Print, as YAML, the name of every Live Set Sound present at an endpoint,\n"
            "mapping each page number to a mapping of set number to name.\n\n"
            "ENDPOINT is FORMAT:LOCATION, where FORMAT is one of: json, yaml,\n"
            "midi, syx, rtmidi, x9a, x9l, x9p, x9s.\n\n"
            "  json:PATH / yaml:PATH    Live Set Sound JSON/YAML file\n"
            "  midi:PATH                .mid file containing SysEx Bulk Dumps\n"
            "  syx:PATH                 .syx file (raw SysEx Bulk Dumps)\n"
            "  rtmidi:PORT[:DEVICE_ID]  CP88/CP73 MIDI port, see 'list-midi-ports'\n"
            "  x9a:PATH / x9l:PATH      .X9A 'Back Up' / .X9L 'Live Set All' file\n"
            "  x9p:PATH[:PAGE]          .X9P 'Live Set Page' file\n"
            "  x9s:PATH[:PAGE[:SET]]    .X9S 'Live Set Sound' file\n\n"
            "The 'FORMAT:' prefix may be omitted for json/yaml/midi/syx/x9a/x9l/x9p/x9s,\n"
            "in which case FORMAT is inferred from LOCATION's file extension.\n\n"
            "By default, every Live Set Sound present is listed. To list only some, follow\n"
            "ENDPOINT with one or more selection specs, using the same '*' /\n"
            "<pages>:<sets> syntax as 'convert' (remapping with '=' is not supported).\n"
            "For 'rtmidi', specs also determine which Live Set Sounds are downloaded\n"
            "(each requires its own MIDI Bulk Dump Request); with no specs, all\n"
            "320 are downloaded.\n\n"
            "Examples:\n"
            "  cp-liveset inspect json:myset.json\n"
            "  cp-liveset inspect x9a:CP_BackUp.X9A 1:5 2:1-8\n"
            "  cp-liveset inspect rtmidi:CP88 1:1-8\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("endpoint", help="endpoint to inspect, FORMAT:LOCATION")
    p.add_argument("specs", nargs="*", metavar="SPEC",
                    help="selection spec(s), e.g. '1:5' or '1,3:1-8' (default: all present)")
    p.add_argument("--timeout", type=float, default=3.0,
                    help="seconds to wait when reading from a live device (default %(default)s)")
    p.set_defaults(func=cmd_inspect)

    p = sub.add_parser(
        "convert",
        help="convert Live Set data between json / midi / rtmidi / x9* endpoints",
        description=(
            "Convert Live Set data between one or more input endpoints and one or\n"
            "more output endpoints. Each endpoint is FORMAT:LOCATION, where FORMAT\n"
            "is one of: json, yaml, midi, syx, rtmidi, x9a, x9l, x9p, x9s.\n\n"
            "  json:PATH            Live Set Sound JSON file (cp88-cp73-liveset-v1)\n"
            "  yaml:PATH            Concise YAML file (only non-default values)\n"
            "  midi:PATH[:DEVICE_ID]  .mid file containing SysEx Bulk Dumps\n"
            "  syx:PATH[:DEVICE_ID]   .syx file (raw SysEx Bulk Dumps)\n"
            "  rtmidi:IN:OUT[:DEVICE_ID]  CP88/CP73 MIDI input/output port\n"
            "                       numbers, see 'list-midi-ports' (given\n"
            "                       separately as numbers, since the same\n"
            "                       device may have different in/out indexes)\n"
            "  rtmidi:PORT[:DEVICE_ID]  CP88/CP73 MIDI port name (or a unique\n"
            "                       prefix, not starting with a digit), used for\n"
            "                       both input and output, see 'list-midi-ports'\n"
            "  x9a:PATH             .X9A 'Back Up' file (read-only)\n"
            "  x9l:PATH             .X9L 'Live Set All' file (read/write, 160 sets)\n"
            "  x9p:PATH[:PAGE]      .X9P 'Live Set Page' file (read/write, 8 sets)\n"
            "  x9s:PATH[:PAGE[:SET]]  .X9S 'Live Set Sound' file (read/write, 1 set)\n\n"
            "The 'FORMAT:' prefix may be omitted for json/yaml/midi/syx/x9a/x9l/x9p/x9s,\n"
            "in which case FORMAT is inferred from LOCATION's file extension\n"
            "(.json, .yaml/.yml, .mid/.midi, .syx, .x9a, .x9l, .x9p, .x9s, case-\n"
            "insensitive; a trailing :PAGE[:SET] suffix is ignored for this).\n"
            "'rtmidi' always needs its explicit prefix.\n\n"
            "rtmidi/midi/syx endpoints may have a trailing :DEVICE_ID (0-15, default 0)\n"
            "giving the MIDI SysEx device number to address (rtmidi) or embed\n"
            "(midi/syx) when writing.\n\n"
            "x9p/x9s files store their own page (and, for x9s, set) number;\n"
            "the optional :PAGE / :PAGE:SET suffix overrides that identity on\n"
            "both read and write (if SET is omitted for x9s, only the page is\n"
            "overridden and the stored/derived set number is kept). Writing to\n"
            "x9p/x9l fills any (page,set) slots not present in the output with\n"
            "\"Init Sound\"; for x9p with no :PAGE override, the output must have\n"
            "at least one Live Set Sound, all on the same page. Writing to x9s requires\n"
            "at most one Live Set Sound; if the output is empty, :PAGE:SET must be\n"
            "given, and \"Init Sound\" is written at that identity.\n\n"
            "Each -i/-o is followed by zero or more selection/remapping specs:\n\n"
            "  *                    all present (page,set) pairs, identity\n"
            "  <pages>:<sets>       select these pairs, identity mapping\n"
            "  <pages>:<sets>=<pages>:<sets>   select the left, remap onto the right\n\n"
            "<pages>/<sets> is '*' or a comma-separated list of numbers and/or\n"
            "'a-b' ranges. On the left of '=' (or with no '='), '*' means \"whatever\n"
            "is present\"; on the right of '=', '*' means the full range\n"
            f"(1-{cp_liveset.PAGE_COUNT} for pages, 1-{cp_liveset.SETS_PER_PAGE} for sets). The two sides of\n"
            "'=' must resolve to the same number of pairs. With no specs at all,\n"
            "'*' is assumed (carry everything present straight through).\n\n"
            "A 'rtmidi' device always holds all 320 Live Set Sounds, but each one\n"
            "requires its own MIDI Bulk Dump Request. So a 'rtmidi' input with\n"
            "explicit specs only downloads those; with no spec at all, only the\n"
            "page:set pairs that the -o spec(s) actually need are downloaded\n"
            "(this requires those -o specs to not use '*' on their left side).\n\n"
            "-i and -o are processed left to right (in their order on the command\n"
            "line, interleaved with each other): each -i merges its Live Set Sounds into\n"
            "a working set, overwriting any existing entry for the same\n"
            "destination slot, and each -o captures a snapshot of the working set\n"
            "as it stands at that point. So e.g. \"-i Ai 1:1 -o Ao -i Bi 1:1 -o Bo\"\n"
            "writes Ai's 1:1 to Ao and Bi's 1:1 to Bo, even though both inputs\n"
            "target the same working-set slot (1:1). All inputs are read, and all\n"
            "outputs written, before/after this left-to-right pass respectively, so\n"
            "using the same endpoint as both an input and an output is also\n"
            "well-defined (a write sees the endpoint's contents from before this\n"
            "command ran).\n\n"
            "A file output (json/yaml/midi/x9a/x9l/x9p/x9s) is rewritten from\n"
            "scratch, replacing its entire previous contents. A 'rtmidi' output\n"
            "only updates the addressed Live Set Sound(s) on the device; everything else\n"
            "on the device is left unchanged. If a file output already exists, you\n"
            "are prompted to confirm overwriting it; -y/--yes overwrites without\n"
            "prompting, -n/--no fails instead of prompting.\n\n"
            "-i/-o may be omitted or repeated. With no -i (or a -o before the first\n"
            "-i), the working set is empty at that point, so e.g. 'x9p:PATH:PAGE' /\n"
            "'x9l:PATH' outputs are written entirely as \"Init Sound\", and other\n"
            "outputs are written empty. With no -o, inputs are still read (so e.g.\n"
            "an invalid file is still reported), but nothing is written.\n\n"
            "Examples:\n"
            "  cp-liveset convert -i rtmidi:CP88 1:5 2:* -o json:myset.json\n"
            "  cp-liveset convert -i json:myset.json -o midi:myset.mid\n"
            "  cp-liveset convert -i midi:myset.mid -o rtmidi:CP88\n"
            "  cp-liveset convert -i x9a:CP_BackUp.X9A -o json:backup.json\n"
            "  cp-liveset convert -i json:myset.json 1:5=12:2 -o x9s:myset.X9S\n"
            "  cp-liveset convert -i x9a:CP_BackUp.X9A 1:1-8=9:1-8 -o x9p:page9.X9P\n"
            "  cp-liveset convert -i myset.json -o dump.syx  # raw SysEx file\n"
            "  cp-liveset convert -o x9p:blank.X9P:5 -o x9l:blank.X9L  # all \"Init Sound\"\n"
            "  cp-liveset convert -o x9s:blank.X9S:12:2  # \"Init Sound\" at 12:2\n"
            "  cp-liveset convert -i x9a:CP_BackUp.X9A  # validate the file only\n"
            "  cp-liveset convert -i a.json 1:1 -o a_copy.json -i b.json 1:1 -o b_copy.json\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("-i", "--input", action=_AppendIO, const="i", dest="io", nargs="+", default=[],
                    metavar="ENDPOINT",
                    help="input endpoint, optionally followed by selection/remap specs "
                         "(may be repeated; default: none, i.e. nothing to carry through)")
    p.add_argument("-o", "--output", action=_AppendIO, const="o", dest="io", nargs="+", default=[],
                    metavar="ENDPOINT",
                    help="output endpoint, optionally followed by selection/remap specs "
                         "(may be repeated; default: none, i.e. nothing is written)")
    p.add_argument("--timeout", type=float, default=3.0,
                    help="seconds to wait for each Live Set Sound when reading from a "
                         "live device (default %(default)s)")
    p.add_argument("--gap-ticks", type=int, default=DEFAULT_GAP_TICKS,
                    help="ticks between SysEx messages in a .mid output file "
                         "(default %(default)s)")
    overwrite = p.add_mutually_exclusive_group()
    overwrite.add_argument("-y", "--yes", action="store_true",
                            help="overwrite existing output files without prompting")
    overwrite.add_argument("-n", "--no", action="store_true",
                            help="fail if an output file already exists, instead of prompting")
    p.set_defaults(func=cmd_convert)

    p = sub.add_parser(
        "select",
        help="select a Live Set Sound on the CP88/CP73 (write a .mid file, or send via rtmidi)",
        description=(
            "Select a Live Set Sound on the CP88/CP73 via Bank Select MSB/LSB + Program\n"
            "Change, either by writing a .mid file or sending it live to a connected\n"
            "device.\n\n"
            "ENDPOINT is one of:\n\n"
            "  midi:PATH[:DEVICE_ID]    write a .mid file containing the SysEx\n"
            "  rtmidi:PORT[:DEVICE_ID]  send live to a CP88/CP73 MIDI port (or a\n"
            "                           unique prefix, not starting with a digit),\n"
            "                           see 'list-midi-ports'\n\n"
            "DEVICE_ID is the MIDI SysEx device number (0-15, default 0).\n\n"
            "Examples:\n"
            "  cp-liveset select midi:switch.mid 7:3\n"
            "  cp-liveset select rtmidi:CP88 7:3\n"
            "  cp-liveset select rtmidi:CP88:5 7:3 -c 2\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("endpoint", type=parse_select_endpoint, metavar="ENDPOINT",
                    help="destination endpoint, 'midi:PATH' or 'rtmidi:PORT'")
    p.add_argument("sound", type=parse_sound_id, metavar="PAGE:SET",
                    help=f"Live Set Sound to select, PAGE:SET (PAGE 1-{cp_liveset.PAGE_COUNT}, "
                         f"SET 1-{cp_liveset.SETS_PER_PAGE})")
    p.add_argument("-c", "--channel", type=int, default=1, help="MIDI channel 1-16 (default 1)")
    p.set_defaults(func=cmd_select)

    p = sub.add_parser("list-midi-ports", help="list available MIDI port names")
    p.set_defaults(func=cmd_list_midi_ports)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except (ValueError, OSError, NotImplementedError) as exc:
        raise SystemExit(f"error: {exc}")
    except argparse.ArgumentTypeError as exc:
        raise SystemExit(f"error: {exc}")


if __name__ == "__main__":
    main()
