"""
Codec between LiveSetSound structures (soundmodels.py) and the raw SysEx
Bulk Dump messages described in paramap.py / sysex.py.
"""

from __future__ import annotations

from typing import Iterable, Iterator, NamedTuple

from . import paramap, sysex, yamldata
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

JSON_FORMAT = "cp88-cp73-liveset-v1"

# Pydantic model class for each data block key in paramap.DATA_BLOCKS.
_BLOCK_MODELS = {
    "soundmondo": SoundMondo,
    "master_eq": MasterEq,
    "common": Common,
    "additional": Additional,
    **{f"zone_{zz}": Zone for zz in range(paramap.ZONE_COUNT)},
}
for _sec in paramap.SECTION_NAMES:
    _BLOCK_MODELS[f"section_{_sec}_common"] = SectionCommon
    _BLOCK_MODELS[f"section_{_sec}_specific"] = SectionSpecific
    _BLOCK_MODELS[f"section_{_sec}_additional"] = SectionAdditional


def _decode_block(data: bytes, fields, size: int, model_cls):
    if len(data) != size:
        raise ValueError(f"expected {size} bytes, got {len(data)}")
    kwargs = {}
    for offset, name, fsize, kind in fields:
        chunk = data[offset:offset + fsize]
        if kind == "ascii":
            kwargs[name] = bytes(chunk).decode("ascii")
        elif kind == "byte":
            kwargs[name] = chunk[0]
        else:  # "bytes"
            kwargs[name] = list(chunk)
    return model_cls(**kwargs)


def _encode_block(obj, fields, size: int) -> bytes:
    buf = bytearray(size)
    for offset, name, fsize, kind in fields:
        val = getattr(obj, name)
        if kind == "ascii":
            raw = val.encode("ascii")
            if len(raw) > fsize:
                raise ValueError(f"field '{name}': {val!r} exceeds {fsize} bytes")
            buf[offset:offset + fsize] = raw.ljust(fsize, b"\x00")
        elif kind == "byte":
            buf[offset] = val
        else:  # "bytes"
            if len(val) != fsize:
                raise ValueError(f"field '{name}': expected {fsize} bytes, got {len(val)}")
            buf[offset:offset + fsize] = bytes(val)
    return bytes(buf)


def _block_objects(ls: LiveSetSound) -> dict:
    """The sub-model holding each data block key's fields."""
    objs = {
        "soundmondo": ls.soundmondo,
        "master_eq": ls.master_eq,
        "common": ls.common,
        "additional": ls.additional,
        **{f"zone_{zz}": zone for zz, zone in enumerate(ls.zones)},
    }
    for sec in paramap.SECTION_NAMES:
        section = getattr(ls.sections, sec)
        objs[f"section_{sec}_common"] = section.common
        objs[f"section_{sec}_specific"] = section.specific
        objs[f"section_{sec}_additional"] = section.additional
    return objs


def sound_from_blocks(block_data: dict[str, bytes]) -> LiveSetSound:
    """block_data: data block key -> raw bytes, for all 17 data blocks."""
    decoded = {
        key: _decode_block(block_data[key], fields, size, _BLOCK_MODELS[key])
        for key, _addr, size, fields in paramap.DATA_BLOCKS
    }
    return LiveSetSound(
        soundmondo=decoded["soundmondo"],
        master_eq=decoded["master_eq"],
        common=decoded["common"],
        additional=decoded["additional"],
        zones=[decoded[f"zone_{zz}"] for zz in range(paramap.ZONE_COUNT)],
        sections=Sections(**{
            sec: Section(
                common=decoded[f"section_{sec}_common"],
                specific=decoded[f"section_{sec}_specific"],
                additional=decoded[f"section_{sec}_additional"],
            )
            for sec in paramap.SECTION_NAMES
        }),
    )


def sound_to_blocks(ls: LiveSetSound) -> dict[str, bytes]:
    """Returns data block key -> raw bytes, for all 17 data blocks."""
    objs = _block_objects(ls)
    return {
        key: _encode_block(objs[key], fields, size)
        for key, _addr, size, fields in paramap.DATA_BLOCKS
    }


def sound_to_messages(device_no: int, page: int, set_no: int, ls: LiveSetSound) -> list[bytes]:
    """Build the 19 Bulk Dump SysEx messages (header + 17 data blocks +
    footer) for one Live Set Sound.

    page: 1-40, set_no: 1-8 (user-facing, 1-based).
    """
    paramap.check_page_set(page, set_no)
    block_data = sound_to_blocks(ls)
    messages = []
    for key, address, size, _fields in paramap.sound_blocks(page - 1, set_no - 1):
        data = b"" if size == 0 else block_data[key]
        messages.append(sysex.build_bulk_dump(device_no, address, data))
    return messages


class ParsedSound(NamedTuple):
    page: int
    set_no: int
    device_no: int
    sound: LiveSetSound


def _sound_from_parsed(parsed: list[tuple]) -> ParsedSound:
    """Assemble one Live Set Sound from parsed (device_no, address, data) tuples."""
    by_addr = {}
    devices = set()
    page = set_no = footer_page_set = None
    for dev, address, data in parsed:
        devices.add(dev)
        if address[0] == paramap.HEADER_HIGH:
            if page is not None:
                raise ValueError("multiple Bulk Header messages in one Live Set Sound")
            page, set_no = address[1] + 1, address[2] + 1
            continue
        if address[0] == paramap.FOOTER_HIGH:
            footer_page_set = (address[1] + 1, address[2] + 1)
            continue
        if address in by_addr:
            raise ValueError(f"duplicate data block at address {address}")
        by_addr[address] = data

    if page is None:
        raise ValueError("no Bulk Header message found")
    if footer_page_set is not None and footer_page_set != (page, set_no):
        raise ValueError(
            f"Bulk Footer for page {footer_page_set[0]} set {footer_page_set[1]} "
            f"does not match Bulk Header for page {page} set {set_no}")
    if len(devices) > 1:
        raise ValueError(f"messages from multiple device numbers: {sorted(devices)}")
    device_no = devices.pop()

    block_data = {}
    for key, address, size, _fields in paramap.DATA_BLOCKS:
        if address not in by_addr:
            raise ValueError(f"missing block '{key}' (address {address}) for page {page} set {set_no}")
        data = by_addr[address]
        if len(data) != size:
            raise ValueError(f"block '{key}': expected {size} bytes, got {len(data)}")
        block_data[key] = data

    return ParsedSound(page, set_no, device_no, sound_from_blocks(block_data))


def sound_from_messages(messages: Iterable[bytes]) -> ParsedSound:
    """Parse the Bulk Dump messages belonging to one Live Set Sound.

    `messages` may contain the blocks in any order (per the manual), but
    must contain exactly one Bulk Header, all 17 data blocks for a single
    (page, set), and at most one Bulk Footer (which must match the header).
    All messages must carry the same device number.
    """
    return _sound_from_parsed([sysex.parse_bulk_dump(msg) for msg in messages])


# Canonical "Init Sound": the device's empty-slot default Live Set Sound.
# Rather than shipping its captured bytes, it is rebuilt in code from the
# factory modal field defaults (yamldata.FIELD_DEFAULTS) with the few named
# deviations below; every reserved/un-defaulted byte stays 0. Verified against
# the device: the result matches the CP88's own Init Sound byte-for-byte.
_INIT_SOUND_NAME = "Init Sound"
_INIT_SOUND_OVERRIDES: dict[tuple[str, str], int] = {
    ("common", "reverb_switch"): 1,
    ("section_piano_common", "section_switch"): 1,
    ("section_piano_common", "section_volume"): 127,
    ("section_sub_common", "section_volume"): 127,
}


def _init_block_data() -> dict[str, bytes]:
    """The Init Sound's 17 data blocks as raw bytes, assembled from the field
    defaults plus _INIT_SOUND_OVERRIDES (reserved and un-defaulted bytes 0)."""
    blocks: dict[str, bytes] = {}
    for key, _addr, size, fields in paramap.DATA_BLOCKS:
        buf = bytearray(size)
        for offset, name, fsize, kind in fields:
            if kind == "ascii":
                buf[offset:offset + fsize] = \
                    _INIT_SOUND_NAME.encode("ascii").ljust(fsize, b"\x00")
                continue
            value = _INIT_SOUND_OVERRIDES.get((key, name))
            if value is None:
                value = yamldata.FIELD_DEFAULTS.get(f"{key}.{name}")
            if value is None:
                continue  # reserved or un-defaulted field -> stays 0
            if kind == "byte":
                buf[offset] = value
            else:  # "bytes" (e.g. additional.tempo_raw)
                buf[offset:offset + fsize] = bytes(value)
        blocks[key] = bytes(buf)
    return blocks


def init_sound() -> LiveSetSound:
    """Return a fresh "Init Sound" LiveSetSound: the device's empty-slot
    default, used to fill unused Live Set slots. Each call returns a new,
    independent instance."""
    return sound_from_blocks(_init_block_data())


def iter_sounds_from_messages(messages: Iterable[bytes], *,
                              ignore_unknown: bool = False) -> Iterator[ParsedSound]:
    """Parse a flat stream of Bulk Dump messages into per-Live-Set results.

    Only the Bulk Header/Footer messages carry the (page, set) address;
    the data blocks in between are addressed generically, so the stream is
    split at the Header/Footer brackets (in stream order). Messages outside
    a header/footer bracket are ignored, but a header inside an open
    bracket, or a bracket left open at the end of the stream, is an error.

    If ``ignore_unknown`` is set, any message that is not a well-formed
    CP88/CP73 Bulk Dump (foreign-manufacturer SysEx, wrong model, bad
    checksum, ...) is silently skipped instead of raising - useful when
    reading a file that may interleave other SysEx data.
    """
    group = None
    for msg in messages:
        try:
            parsed = sysex.parse_bulk_dump(msg)
        except sysex.SysexError:
            if ignore_unknown:
                continue
            raise
        _dev, address, _data = parsed
        if address[0] == paramap.HEADER_HIGH:
            if group is not None:
                raise ValueError("Bulk Header inside an unterminated Live Set Sound group")
            group = [parsed]
            continue
        if group is None:
            continue  # ignore stray messages outside a header/footer bracket
        group.append(parsed)
        if address[0] == paramap.FOOTER_HIGH:
            yield _sound_from_parsed(group)
            group = None
    if group is not None:
        raise ValueError("unterminated Live Set Sound group (missing Bulk Footer)")
