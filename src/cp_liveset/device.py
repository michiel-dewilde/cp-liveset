"""
Live MIDI I/O with a connected CP88/CP73.

All functions here operate on *already-open* mido ports; discovering,
opening, and closing ports is left to the caller, e.g.::

    import mido, cp_liveset

    with mido.open_input("CP88/CP73-1 0") as inport, \\
         mido.open_output("CP88/CP73-1 1") as outport:
        sound = cp_liveset.request_sound(inport, outport, 1, 1)

A Bulk Dump Request only ever fetches one Live Set Sound, so reading is
per-(page, set): ``request_sound`` for one, ``request_group`` for an
explicit list of pairs (the device holds all 320, but each costs its own
request/response round trip, roughly 0.4 s). Writing (``send_sound`` /
``send_group``) updates only the addressed slot(s) on the device.
"""

from __future__ import annotations

import time
from collections.abc import Iterable, Mapping

import mido

from . import codec, paramap, sysex
from .group import LiveSetCollection, Pair, _check_device_id
from .soundmodels import LiveSetSound

DEFAULT_TIMEOUT = 3.0
DEFAULT_SEND_GAP = 0.02  # seconds between Bulk Dump messages, enough for the device to digest each
_POLL_INTERVAL = 0.005


class DeviceTimeoutError(TimeoutError):
    """The device did not send a complete reply within the timeout."""


def request_sound(inport: "mido.ports.BaseInput", outport: "mido.ports.BaseOutput",
                     page: int, set_no: int, *, device_id: int = 0,
                     timeout: float = DEFAULT_TIMEOUT) -> LiveSetSound:
    """Read one Live Set Sound from the device: send a Bulk Dump Request for
    (page, set_no) on `outport` and collect the 19-message reply from
    `inport`.

    Any messages already pending on `inport` are discarded first; non-sysex
    messages and unrelated sysex received while waiting are ignored. Raises
    DeviceTimeoutError if the complete reply does not arrive within
    `timeout` seconds. ``device_id`` (0-15) is the MIDI SysEx device number
    to address.
    """
    paramap.check_page_set(page, set_no)
    _check_device_id(device_id)
    pp, n = page - 1, set_no - 1
    request = sysex.build_bulk_dump_request(device_id, paramap.header_addr(pp, n))

    while inport.poll() is not None:  # discard stale input
        pass
    outport.send(mido.Message("sysex", data=request[1:-1]))

    messages: list[bytes] = []
    started = False
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        msg = inport.poll()
        if msg is None:
            time.sleep(_POLL_INTERVAL)
            continue
        if msg.type != "sysex":
            continue
        raw = bytes([0xF0, *msg.data, 0xF7])
        try:
            _dev, address, _data = sysex.parse_bulk_dump(raw)
        except sysex.SysexError:
            continue
        if not started:
            if address != paramap.header_addr(pp, n):
                continue
            started = True
        messages.append(raw)
        if address == paramap.footer_addr(pp, n):
            return codec.sound_from_messages(messages).sound
    raise DeviceTimeoutError(
        f"timed out waiting for Live Set Sound {page}:{set_no} "
        f"(received {len(messages)} messages)")


def request_group(inport: "mido.ports.BaseInput", outport: "mido.ports.BaseOutput",
                   pairs: Iterable[Pair], *, device_id: int = 0,
                   timeout: float = DEFAULT_TIMEOUT) -> LiveSetCollection:
    """Read the given (page, set) pairs from the device, one Bulk Dump
    Request each (`timeout` applies per Live Set Sound). Returns them as a
    LiveSetCollection."""
    group = LiveSetCollection()
    for page, set_no in pairs:
        group[(page, set_no)] = request_sound(
            inport, outport, page, set_no, device_id=device_id, timeout=timeout)
    return group


def send_sound(outport: "mido.ports.BaseOutput", page: int, set_no: int,
                  sound: LiveSetSound, *, device_id: int = 0,
                  gap: float = DEFAULT_SEND_GAP) -> None:
    """Store one Live Set Sound on the device at (page, set_no), by sending its
    19 Bulk Dump messages on `outport`, sleeping `gap` seconds after each
    so the device can keep up. Everything else on the device is left
    unchanged."""
    paramap.check_page_set(page, set_no)
    _check_device_id(device_id)
    for raw in codec.sound_to_messages(device_id, page, set_no, sound):
        outport.send(mido.Message("sysex", data=raw[1:-1]))
        time.sleep(gap)


def send_group(outport: "mido.ports.BaseOutput", group: Mapping[Pair, LiveSetSound],
                *, device_id: int = 0, gap: float = DEFAULT_SEND_GAP) -> None:
    """Store every Live Set Sound in `group` (a LiveSetCollection or any
    {(page, set): LiveSetSound} mapping) on the device, in (page, set) order.
    Slots not present in `group` are left unchanged."""
    for page, set_no in sorted(group):
        send_sound(outport, page, set_no, group[(page, set_no)],
                      device_id=device_id, gap=gap)


def select_messages(page: int, set_no: int, *, channel: int = 1) -> list[mido.Message]:
    """Return the three messages (Bank Select MSB 63 / Bank Select LSB
    page-1 / Program Change set-1) that switch the device to the given Live
    Set, on the given MIDI channel (1-16), all with ``time=0``. Use
    ``select_sound`` to send them, or put them in a MIDI file."""
    paramap.check_page_set(page, set_no)
    if not (1 <= channel <= 16):
        raise ValueError(f"channel must be 1-16, got {channel}")
    ch = channel - 1
    return [
        mido.Message("control_change", channel=ch, control=0,
                      value=paramap.LIVE_SET_BANK_MSB, time=0),
        mido.Message("control_change", channel=ch, control=32,
                      value=page - 1, time=0),
        mido.Message("program_change", channel=ch, program=set_no - 1, time=0),
    ]


def select_sound(outport: "mido.ports.BaseOutput", page: int, set_no: int,
                    *, channel: int = 1) -> None:
    """Switch the device to the given Live Set Sound (page 1-40, set 1-8) by
    sending Bank Select + Program Change on the given channel (1-16)."""
    for msg in select_messages(page, set_no, channel=channel):
        outport.send(msg)
