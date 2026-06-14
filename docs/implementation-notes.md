# Device quirks and implementation notes

Notes on CP88/CP73 behavior that is undocumented, ambiguous, or inaccurate in
the manuals, verified against a real CP88.

## Bulk Dump framing

The [supplementary manual](https://data.yamaha.com/files/download/other_assets/7/1243337/CP88_CP73_supplementary_manual_En_v200_H0.pdf)'s
description of the Bulk Dump byte count and checksum is ambiguous/inaccurate;
the following was verified against a real CP88:

- Byte Count (`bh bl`, 7-bit big-endian) = `len(address) + len(data) + 1`
  = `len(data) + 4`.
- Checksum = the value that makes `Model ID + Address bytes + Data bytes +
  Checksum` sum to 0 mod 128 (the Byte Count bytes are *not* included, but
  the Model ID byte *is*).

## .X9P "Live Set Page" Load behavior

The [owner's manual](https://data.yamaha.com/files/download/other_assets/7/1180527/CP88_owners_manual_En_F0.pdf)
says a `.X9P` file "will be loaded to the currently selected Live Set Page," but doesn't say how the file's 8 entries map onto
that page's 8 sets. Verified against a real CP88 by loading hand-crafted
`.X9P` files (8 entries, each carrying its own embedded `(page, set)` ID) onto
a selected target page:

- The embedded **page** ID in each entry is ignored entirely. All 8 entries
  are written into whichever page is currently selected on the device,
  regardless of what page they claim to belong to. There is no merging of
  entries from a single `.X9P` across multiple device pages.
- Placement within the target page is driven by each entry's embedded **set**
  ID (1-8), not by the entry's position in the file. If two entries claim the
  same set ID, the one **later in the file wins**.
- The Load is effectively a full-page replace: any of the target page's 8 set
  slots that isn't claimed by some entry's set ID is reset to `Init Sound`,
  even though it had different content before the Load. There is no
  "incomplete update that leaves unmentioned sets untouched" mode.

In short: to update some sets of a page without disturbing the rest, a
`.X9P` Load is not sufficient — every entry not meant to change must still
explicitly carry that set's current content with the matching set ID, or that
set will end up as `Init Sound`.

## YSFC (.X9*) container structure

The `.X9A`/`.X9L`/`.X9P`/`.X9S` files are Yamaha's YSFC container (the
Motif/Montage/MODX lineage), here at version `6.0.0`. The general container
framing (header + tag/offset catalogue + paired `Exxx`/`Dxxx` chunks) is the
shared YSFC structure described by [ysfctools](https://github.com/SpotlightKid/ysfctools)
and the [arachsys YSFC notes](https://gist.github.com/arachsys/2883877); the
CP88/CP73-specific layout below is fully understood — it was mapped against
real device exports and confirmed by generating a complete `.X9L` from scratch
and loading it on a CP88. The
shipped `x9format.py` writer emits the whole framing from scratch (no template
file); the reader resolves sections **through the catalogue by tag**, not by a
fixed chunk order or position, so it also reads conformant files that order
their chunks differently or carry additional unrelated chunks.

- **Header (64 bytes):** `"YAMAHA-YSFC"` + version (`"6.0.0"`); a 32-bit
  big-endian *catalogue size* at `0x20` (`8 * number of catalogue entries`);
  library-info size `0` at `0x30`; `0xFFFFFFFF` (unset timestamp) at `0x34`.
- **Catalogue (at `0x40`):** one 8-byte entry per section — a 4-char tag plus
  the 32-bit big-endian absolute offset of that section; its total size is the
  32-bit value at `0x20`. This catalogue is the authoritative index: sections
  are located by tag, in any order. `.X9P`/`.X9S` have two entries (`ELST`,
  `DLST`); `.X9L`/`.X9A` add a second list pair (`ELSE`, `DLSE`). The reader
  loads `ELST` (the Live Set entry list) and `DLST` (its blob data) by tag, so
  the second init layer and any other system chunks (`.X9A` backups carry
  several) are simply ignored.
- **Entry lists (`ELST`/`ELSE`):** `tag` + 32-bit length + 32-bit count, then
  variable-length `Entr` records: item size (always 1024), data offset,
  `00 3F` type marker, 0-based page & set, then a **NUL-terminated** name
  (so a 15-char space-padded name takes 16 bytes, a short NUL-padded one
  fewer — which is why entry-list sizes vary between files).
- **Data lists (`DLST`/`DLSE`):** `tag` + length + count, then `Data` records
  of a fixed 1024-byte payload each (the 367-byte Live Set Sound blob, NUL
  name, `0xFF` padding). `DLST` is the Live Set the device loads from; the
  `DLSE` second layer holds an `Init Sound` per slot and is ignored on load.
- **No checksums.** A content-modified file with otherwise-unchanged framing
  loads fine, and the 8 trailing blob bytes (device-written save metadata)
  are ignored on load.

## X9 blob field mapping

The 367-byte per-Live-Set blob stores a *subset* of the SysEx parameters
(`x9data.FIELD_POSITIONS` for the direct single-byte fields,
`x9data.BIT_POSITIONS` for the bit-expanded ones, `x9data.REPACK_POSITIONS`
for the one cross-width field). The mapping was reverse-engineered by
**controlled experiment**: send sounds with unique, distinctive values for
every field over MIDI, read the device's actual stored model back (MIDI
receive clamps/forces many fields, so the read-back — not the sent values —
is the ground truth), export the page from the CP88, and correlate every blob
byte (and bit) against the read-back model across the controlled plus 160
factory sounds. The result is confirmed on hardware: a `.X9P` generated from a
known page is **byte-identical** to the device's own export of that page, and
the codec round-trips every captured sound idempotently. 189 of the 244
non-reserved fields are stored; the rest are genuinely absent (mostly a
section's *inactive*-instrument-type effect parameters, which the device
force-constants, plus format-version stamps). The absent fields decode as `0`,
except the fixed format-version stamps (`soundmondo` versions and each block's
`bulk_format_version`), which the reader fills with their canonical constants
(`x9data.FIXED_VERSION_FIELDS`) since they are deterministic for the format and
not stored anywhere in the YSFC blob — they would otherwise litter the concise
YAML's `raw:` map on every X9-derived sound. They are not in `FIELD_POSITIONS`,
so the writer still omits them and X9 round-trips stay byte-exact.

An earlier factory-correlation-only pass was less reliable: because a field
that never varies across factory presets can't be located that way, it had
mis-mapped the per-zone transmit switches, missed ~35 fields that are
default in every factory preset, and was fooled by two factory-file quirks
(below). The controlled experiment fixes all of that.

Notable encodings/quirks the hardware diff pinned down:

- The per-zone **transmit switches are stored bit-expanded** — each switch
  byte's bits occupy individual blob bytes (`0`/`1`). The layout is regular:
  each zone uses 11 consecutive blob bytes, `transmit_switches_1` bits
  `[4,0,1,2,3]` then `transmit_switches_2` bits `[0,1,2,3,4,5]` (e.g. zone 0 at
  blob bytes 84-94). Hence `BIT_POSITIONS`.
- **Tempo is repacked across the 7-bit/8-bit boundary**: the SysEx model
  carries it as two 7-bit bytes (`additional.tempo_raw = [msb, lsb]`,
  value `= msb*128 + lsb`), but the file stores it as a 16-bit
  little-endian value in two 8-bit bytes (blob `59` = low, `60` = high).
  This is the only such field (`REPACK_POSITIONS`); it was invisible until a
  tempo-varying experiment, because every factory and earlier-test sound
  shared one tempo (`900`, i.e. `132,3`).
- The per-section delay/reverb send depths live at blob bytes 55-57 / 67-69.
  Factory *file* exports happen to also carry a copy of them in the
  section-common area (203/204, 262/263, 321/322), but a freshly written
  sound has those bytes `0`, so they are not mapped — the depths are read and
  written only at 55-57 / 67-69.
- The blob's last 8 bytes are a trailing chunk: a 32-bit count (always `4`)
  followed by 4 panel-only bytes that are not present in the SysEx Bulk Dump
  (so they default to `0x40`). Current firmware writes this chunk
  (`00 00 00 04 40 40 40 40`) for every slot, including empty Init Sound
  slots; older factory files instead left empty slots `0xFF`-padded. The
  writer always emits the chunk, matching a fresh device export byte-for-byte
  (verified: a generated `.X9P` of a real sound plus seven Init Sound fills is
  identical to the CP88's export of the same page, all 8606 bytes).

### Completeness

Every blob bit that varies in a *fresh* device export is mapped to the model:
checking all 8 bits of all 367 bytes across the 16 controlled sounds (which
exercised essentially every MIDI-settable field) found **zero** varying bits
that are not accounted for by `FIELD_POSITIONS` / `BIT_POSITIONS`.

Widening the check to the 160 factory files surfaces varying-but-unmapped bits
at exactly 15 positions — `30`, `203/204`, `262/263`, `321/322`, and `359-366`
— and every one of them is **constant in fresh output** (it only ever varies
in legacy factory saves). Those are precisely the redundant duplicate copies
(`203/204` … echo the delay/reverb depths held at `55-57`/`67-69`; `30` echoes
`fc2_assign` at `38`) and the panel-only trailing chunk (`359-366`), none of
which is part of the SysEx model. So nothing this tool can produce or
round-trip — and nothing in a current device export — is unaccounted for.
