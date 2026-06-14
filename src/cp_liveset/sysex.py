"""
Low-level CP88/CP73 SysEx message helpers.

Message formats (Group Number = 7F 1C, Model ID = 08), from
CP88_CP73_supplementary_manual_En_v200_H0.pdf section (3-5)
(https://data.yamaha.com/files/download/other_assets/7/1243337/CP88_CP73_supplementary_manual_En_v200_H0.pdf):

    Bulk Dump:          F0 43 0n 7F 1C bh bl 08 ah am al dd...dd cc F7
    Bulk Dump Request:  F0 43 2n 7F 1C 08 ah am al F7
    Parameter Change:   F0 43 1n 7F 1C 08 ah am al dd...dd F7
    Parameter Request:  F0 43 3n 7F 1C 08 ah am al F7

Byte Count (bh, bl, 7 bits each, big-endian) covers everything from the
address through the checksum inclusive, i.e. byte_count = len(address) +
len(data) + 1 = len(data) + 4. (Confirmed against live CP88 Bulk Dump
responses; the manual's wording "byte count contained in each block" is
ambiguous about whether address/checksum are included.)

Checksum: the value that makes the lower 7 bits of
(Model ID + Address + Data + Checksum) sum to 0. (Also confirmed against
live CP88 responses - the manual's description ("Byte Count, Start Address,
Data and Checksum") does not match the device's actual checksum, which
does not include the Byte Count bytes but does include the Model ID byte.)
"""

from __future__ import annotations

YAMAHA_ID = 0x43
GROUP_HIGH = 0x7F
GROUP_LOW = 0x1C
MODEL_ID = 0x08

ADDRESS_LEN = 3
FIXED_PREFIX_LEN = 8  # F0 43 0n 7F 1C bh bl 08


def _split_count(n: int):
    return (n >> 7) & 0x7F, n & 0x7F


def checksum(address, data):
    total = MODEL_ID + sum(address) + sum(data)
    return (-total) & 0x7F


def build_bulk_dump(device_no: int, address, data: bytes) -> bytes:
    """Build a complete Bulk Dump SysEx message (including F0/F7)."""
    bh, bl = _split_count(len(data) + ADDRESS_LEN + 1)
    body = [bh, bl, MODEL_ID, *address, *data]
    cc = checksum(address, data)
    return bytes([0xF0, YAMAHA_ID, 0x00 | (device_no & 0x0F), GROUP_HIGH, GROUP_LOW,
                   *body, cc, 0xF7])


def build_bulk_dump_request(device_no: int, address) -> bytes:
    """Build a Bulk Dump Request SysEx message (including F0/F7)."""
    return bytes([0xF0, YAMAHA_ID, 0x20 | (device_no & 0x0F), GROUP_HIGH, GROUP_LOW,
                   MODEL_ID, *address, 0xF7])


class SysexError(ValueError):
    pass


def parse_bulk_dump(msg: bytes):
    """Parse a Bulk Dump SysEx message (including F0/F7).

    Returns (device_no, address_tuple, data_bytes).
    Raises SysexError if the message is malformed or the checksum is wrong.
    """
    if len(msg) < FIXED_PREFIX_LEN + ADDRESS_LEN + 2 or msg[0] != 0xF0 or msg[-1] != 0xF7:
        raise SysexError("not a SysEx message")
    if msg[1] != YAMAHA_ID or (msg[2] & 0xF0) != 0x00:
        raise SysexError("not a Yamaha Bulk Dump message")
    if tuple(msg[3:5]) != (GROUP_HIGH, GROUP_LOW) or msg[7] != MODEL_ID:
        raise SysexError("unexpected group/model ID")
    device_no = msg[2] & 0x0F
    bh, bl = msg[5], msg[6]
    byte_count = (bh << 7) | bl
    n_data = byte_count - (ADDRESS_LEN + 1)
    if n_data < 0:
        raise SysexError("byte count too small")
    address = tuple(msg[8:8 + ADDRESS_LEN])
    data_start = 8 + ADDRESS_LEN
    if len(msg) != data_start + n_data + 2:
        raise SysexError("byte count does not match message length")
    data = bytes(msg[data_start:data_start + n_data])
    cc = msg[data_start + n_data]
    expected_cc = checksum(address, data)
    if cc != expected_cc:
        raise SysexError(
            f"checksum mismatch at address {address}: got {cc:#x}, expected {expected_cc:#x}")
    return device_no, address, data
