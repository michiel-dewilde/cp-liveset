"""
Read/write support for the YSFC ".X9*" container files used by the
CP88/CP73 file menu:

  .X9A  "Back Up"        - read-only, full device backup (many chunks;
                            we only extract the Live Set data)
  .X9L  "Live Set All"   - read-only, all 160 Live Set Sounds (pages 1-20 x 8 sets)
  .X9P  "Live Set Page"  - read/write, one page (8 sets)
  .X9S  "Live Set Sound"       - read/write, a single Live Set Sound

This module works purely on bytes (whole container files) and
{(page, set): LiveSetSound} dicts; identity-override and page-inference rules
live with the callers (group.py / cli.py).

Per-Live-Set data is stored as a fixed-size 367-byte "blob" inside a
"DLST" chunk; see x9data.py for the byte-position mapping (189/244
non-reserved fields are stored; the rest are confirmed absent and read
back as 0 / dropped on write).
"""

from __future__ import annotations

import struct
from typing import Mapping

from . import codec, paramap, x9data
from .soundmodels import LiveSetSound

MAGIC = b"YAMAHA-YSFC"

DATA_CHUNK_SIZE = 1024

# .X9L ("Live Set All") files only hold pages 1-20 (not paramap.PAGE_COUNT=40),
# even though page numbers up to 40 are otherwise valid for the device.
X9L_PAGE_COUNT = 20


# --------------------------------------------------------------------------- field <-> blob

FIELD_OFFSETS = {
    (block_key, name): (offset, fsize, kind)
    for block_key, _addr, _size, fields in paramap.DATA_BLOCKS
    for offset, name, fsize, kind in fields
}


def _field_offset(block_key, field_name):
    return FIELD_OFFSETS[(block_key, field_name)][0]


def blob_to_sound(blob: bytes) -> LiveSetSound:
    """Convert a 367-byte X9 Live Set Sound blob to a LiveSetSound.

    Fields not stored in the X9 format are decoded as 0, except the fixed
    format-version stamps, which are filled with their canonical constants
    (x9data.FIXED_VERSION_FIELDS). Most fields are stored as a single byte
    (FIELD_POSITIONS); a few (the per-zone transmit switches) are stored
    bit-expanded, one blob byte per bit (BIT_POSITIONS).
    """
    if len(blob) < x9data.BLOB_SIZE:
        raise ValueError(f"X9 Live Set Sound blob too short: expected at least "
                          f"{x9data.BLOB_SIZE} bytes, got {len(blob)}")
    block_data = {key: bytearray(size) for key, _addr, size, _fields in paramap.DATA_BLOCKS}
    for block_key, field_name, sub, pos in x9data.FIELD_POSITIONS:
        block_data[block_key][_field_offset(block_key, field_name) + sub] = blob[pos]
    for block_key, field_name, sub, bit, pos in x9data.BIT_POSITIONS:
        block_data[block_key][_field_offset(block_key, field_name) + sub] |= (blob[pos] & 1) << bit
    for block_key, field_name, lo, hi in x9data.REPACK_POSITIONS:
        off = _field_offset(block_key, field_name)
        value = (blob[hi] << 8) | blob[lo]           # 16-bit little-endian in the file
        block_data[block_key][off] = value >> 7      # back to two 7-bit SysEx bytes
        block_data[block_key][off + 1] = value & 0x7F
    # The YSFC blob carries its own structural framing but not the SysEx
    # "soundmondo"/bulk format-version stamps; fill those fixed constants so an
    # X9-derived sound matches its MIDI form (see x9data.FIXED_VERSION_FIELDS).
    for block_key, field_name, value in x9data.FIXED_VERSION_FIELDS:
        block_data[block_key][_field_offset(block_key, field_name)] = value
    ls = codec.sound_from_blocks({k: bytes(v) for k, v in block_data.items()})
    ls.common.name = blob[4:4 + 15].decode("ascii")
    return ls


def sound_to_blob(ls: LiveSetSound) -> bytes:
    """Convert a LiveSetSound to a 367-byte X9 blob.

    Values for fields not stored in the X9 format are silently dropped. The
    per-zone transmit switches are written bit-expanded (BIT_POSITIONS).
    """
    block_data = codec.sound_to_blocks(ls)
    name = ls.common.name
    blob = bytearray(x9data.BASELINE_BLOB)
    blob[4:4 + 15] = name.encode("ascii").ljust(15, b"\x00")
    for block_key, field_name, sub, pos in x9data.FIELD_POSITIONS:
        blob[pos] = block_data[block_key][_field_offset(block_key, field_name) + sub]
    for block_key, field_name, sub, bit, pos in x9data.BIT_POSITIONS:
        blob[pos] = (block_data[block_key][_field_offset(block_key, field_name) + sub] >> bit) & 1
    for block_key, field_name, lo, hi in x9data.REPACK_POSITIONS:
        off = _field_offset(block_key, field_name)
        value = (block_data[block_key][off] << 7) | block_data[block_key][off + 1]
        blob[lo] = value & 0xFF
        blob[hi] = (value >> 8) & 0xFF
    return bytes(blob)


# --------------------------------------------------------------------------- container parsing

def _read_u32(data: bytes, off: int) -> int:
    if off + 4 > len(data):
        raise ValueError("unrecognized X9 container: truncated (u32 past end of file)")
    return struct.unpack(">I", data[off:off + 4])[0]


# Header field offsets (see docs/implementation-notes.md "YSFC container structure").
_CATALOGUE_OFF = 0x40         # catalogue starts right after the 64-byte header
_CATALOGUE_SIZE_OFF = 0x20    # u32: 8 * number of catalogue entries


def _parse_catalogue(data: bytes) -> dict[bytes, int]:
    """Build the YSFC catalogue: a {4-char tag: absolute section offset} map.

    The catalogue (not a fixed section order) is the authoritative index into a
    YSFC file, so sections are located by tag. This is what lets us read files
    whose chunk order differs from what this module writes, as long as they are
    valid containers of the same family.
    """
    if data[0:len(MAGIC)] != MAGIC:
        raise ValueError("not a YSFC (.X9*) file")

    cat_size = _read_u32(data, _CATALOGUE_SIZE_OFF)
    if cat_size % 8 or _CATALOGUE_OFF + cat_size > len(data):
        raise ValueError("unrecognized X9 container: bad catalogue size")

    catalogue: dict[bytes, int] = {}
    for off in range(_CATALOGUE_OFF, _CATALOGUE_OFF + cat_size, 8):
        tag = bytes(data[off:off + 4])
        catalogue[tag] = _read_u32(data, off + 4)
    return catalogue


def _entry_list_records(data: bytes, list_off: int, tag: bytes):
    """Yield (payload_off, payload_len) for each 'Entr' record in the entry-list
    chunk at `list_off` (which must carry `tag`)."""
    if data[list_off:list_off + 4] != tag:
        raise ValueError(f"unrecognized X9 container: expected {tag!r} chunk at "
                         f"catalogue offset {list_off}")
    count = _read_u32(data, list_off + 8)        # tag(4) + chunk-len(4) + count(4)
    pos = list_off + 12
    for _ in range(count):
        if data[pos:pos + 4] != b"Entr":
            raise ValueError(f"unrecognized X9 container: malformed {tag!r} entry")
        elen = _read_u32(data, pos + 4)
        yield pos + 8, elen
        pos += 8 + elen


def _locate_entries(data: bytes):
    """Return a list of dicts describing each Live Set Sound entry in the file's
    main entry list: id_off, name_off, blob_off, page, set_no.

    Sections are resolved through the catalogue by tag, so the ELST/DLST pair is
    found regardless of where (or in what order) those chunks sit in the file,
    and regardless of any other chunks present (e.g. the ELSE/DLSE init layer in
    .X9L/.X9A, or unrelated system chunks in .X9A).
    """
    catalogue = _parse_catalogue(data)
    if b"ELST" not in catalogue:
        raise ValueError("unrecognized X9 container: no ELST (Live Set) chunk in catalogue")
    if b"DLST" not in catalogue:
        raise ValueError("unrecognized X9 container: no DLST (Live Set data) chunk in catalogue")

    dlst_off = catalogue[b"DLST"]
    if data[dlst_off:dlst_off + 4] != b"DLST":
        raise ValueError("unrecognized X9 container: DLST catalogue offset is wrong")
    dcontent_start = dlst_off + 8     # skip "DLST" tag + chunk-length u32

    entries = []
    for payload_off, _elen in _entry_list_records(data, catalogue[b"ELST"], b"ELST"):
        if tuple(data[payload_off + 8:payload_off + 10]) != (0x00, 0x3F):
            continue  # not a Live Set Sound entry
        data_offset = _read_u32(data, payload_off + 4)
        page = data[payload_off + 10] + 1
        set_no = data[payload_off + 11] + 1
        if not (1 <= page <= paramap.PAGE_COUNT and 1 <= set_no <= paramap.SETS_PER_PAGE):
            continue
        blob_off = dcontent_start + data_offset
        # The entry's data offset points at a "Data" record inside DLST; validate
        # the tag so a mis-sized/foreign offset fails loudly instead of decoding
        # garbage.
        if data[blob_off - 8:blob_off - 4] != b"Data":
            raise ValueError("unrecognized X9 container: DLST data offset does not "
                             "point at a 'Data' record")
        entries.append({
            "id_off": payload_off + 8,
            "name_off": payload_off + 12,
            "blob_off": blob_off,
            "page": page,
            "set_no": set_no,
        })
    return entries


def parse_container(data: bytes) -> dict[tuple[int, int], LiveSetSound]:
    """Parse the contents of a .X9A/.X9L/.X9P/.X9S file into a
    {(page, set_no): LiveSetSound} dict.
    """
    entries = _locate_entries(data)
    if not entries:
        raise ValueError("no Live Set Sounds found in .X9* container")

    out: dict[tuple[int, int], LiveSetSound] = {}
    for entry in entries:
        blob = data[entry["blob_off"]:entry["blob_off"] + x9data.BLOB_SIZE]
        out[(entry["page"], entry["set_no"])] = blob_to_sound(blob)
    return out


# --------------------------------------------------------------------------- container writing
#
# These build complete YSFC containers from scratch (no template file). The
# layout is documented in docs/implementation-notes.md and was confirmed by
# generating files that load on a real CP88.

VERSION = b"6.0.0"
_STRIDE = 8 + DATA_CHUNK_SIZE     # one DLST "Data" record: tag+size header + payload


def _pack_u32(n: int) -> bytes:
    return struct.pack(">I", n)


def _entry(data_offset: int, idbytes: bytes, name: str) -> bytes:
    """One ELST/ELSE 'Entr' record (variable length: NUL-terminated name)."""
    payload = (_pack_u32(DATA_CHUNK_SIZE) + _pack_u32(data_offset) + idbytes
               + name.encode("ascii") + b"\x00")
    return b"Entr" + _pack_u32(len(payload)) + payload


def _entry_list(tag: bytes, entries: list[tuple[bytes, str]]) -> bytes:
    """An Exxx entry-list chunk from (idbytes, name) records."""
    body = b"".join(_entry(12 + i * _STRIDE, idbytes, name)
                    for i, (idbytes, name) in enumerate(entries))
    chunk = _pack_u32(len(entries)) + body
    return tag + _pack_u32(len(chunk)) + chunk


def _data_list(tag: bytes, blobs: list[bytes]) -> bytes:
    """A Dxxx data-list chunk; each blob is padded to DATA_CHUNK_SIZE."""
    body = b"".join(
        b"Data" + _pack_u32(DATA_CHUNK_SIZE) + bytes(blob).ljust(DATA_CHUNK_SIZE, b"\xff")
        for blob in blobs)
    chunk = _pack_u32(len(blobs)) + body
    return tag + _pack_u32(len(chunk)) + chunk


def _container(sections: list[tuple[bytes, bytes]]) -> bytes:
    """Assemble a YSFC container: 64-byte header + catalogue of
    (tag, absolute offset) entries + the section chunks."""
    header = bytearray(0x40)
    header[0:len(MAGIC)] = MAGIC
    header[0x10:0x10 + len(VERSION)] = VERSION
    header[0x20:0x24] = _pack_u32(8 * len(sections))    # catalogue size
    header[0x24:0x30] = b"\xff" * 12
    header[0x30:0x34] = _pack_u32(0)                     # library-info size
    header[0x34:0x40] = b"\xff" * 12                     # unset timestamp + padding
    out = bytearray(header) + bytearray(8 * len(sections))
    offsets = []
    for _tag, chunk in sections:
        offsets.append(len(out))
        out += chunk
    for i, (tag, _chunk) in enumerate(sections):
        o = 0x40 + 8 * i
        out[o:o + 4] = tag
        out[o + 4:o + 8] = _pack_u32(offsets[i])
    return bytes(out)


def _live_layer(items: list[tuple[int, int, LiveSetSound]]):
    """ELST entries + DLST blobs for an ordered list of (page, set, sound)."""
    entries = [(bytes([0x00, 0x3F, page - 1, set_no - 1]), sound.common.name)
               for page, set_no, sound in items]
    blobs = [sound_to_blob(sound) for _p, _s, sound in items]
    return entries, blobs


def build_x9s(page: int, set_no: int, sound: LiveSetSound) -> bytes:
    """Build the contents of a .X9S (single Live Set Sound) file, holding
    `sound` at identity (page, set_no)."""
    paramap.check_page_set(page, set_no)
    entries, blobs = _live_layer([(page, set_no, sound)])
    return _container([(b"ELST", _entry_list(b"ELST", entries)),
                       (b"DLST", _data_list(b"DLST", blobs))])


def build_x9p(sounds: Mapping[tuple[int, int], LiveSetSound], page: int,
               fill: LiveSetSound) -> bytes:
    """Build the contents of a .X9P (Live Set Page, 8 sets) file for `page`.

    Entries in `sounds` for other pages are ignored; sets of `page` not
    present in `sounds` are filled with `fill`."""
    paramap.check_page_set(page, 1)
    items = [(page, s, sounds.get((page, s), fill))
             for s in range(1, paramap.SETS_PER_PAGE + 1)]
    entries, blobs = _live_layer(items)
    return _container([(b"ELST", _entry_list(b"ELST", entries)),
                       (b"DLST", _data_list(b"DLST", blobs))])


def build_x9l(sounds: Mapping[tuple[int, int], LiveSetSound], fill: LiveSetSound) -> bytes:
    """Build the contents of a .X9L (Live Set All, 160 sets) file.

    (page, set) pairs not present in `sounds` are filled with `fill`."""
    extra_pages = {p for p, _s in sounds if p > X9L_PAGE_COUNT}
    if extra_pages:
        raise ValueError(f".X9L only supports pages 1-{X9L_PAGE_COUNT}, "
                          f"got Live Set Sound(s) for page(s) {sorted(extra_pages)}")
    pages = range(1, X9L_PAGE_COUNT + 1)
    sets = range(1, paramap.SETS_PER_PAGE + 1)
    items = [(p, s, sounds.get((p, s), fill)) for p in pages for s in sets]
    entries, blobs = _live_layer(items)
    # Second ("init") layer: the device stores an Init Sound per slot in
    # ELSE/DLSE and ignores it on load. Its entries tag the page as 0x13+page.
    init_blob = sound_to_blob(codec.init_sound())
    else_entries = [(bytes([0x00, 0x3F, 0x13 + p, s - 1]), "Init Sound")
                    for p in pages for s in sets]
    dlse_blobs = [init_blob] * (X9L_PAGE_COUNT * paramap.SETS_PER_PAGE)
    return _container([(b"ELST", _entry_list(b"ELST", entries)),
                       (b"ELSE", _entry_list(b"ELSE", else_entries)),
                       (b"DLST", _data_list(b"DLST", blobs)),
                       (b"DLSE", _data_list(b"DLSE", dlse_blobs))])
