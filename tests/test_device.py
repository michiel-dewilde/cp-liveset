from __future__ import annotations

import mido
import pytest

import cp_liveset
from cp_liveset import DeviceTimeoutError, LiveSetSound, LiveSetCollection


# --------------------------------------------------------------------------- fake ports

class _FakeInput:
    """A mido-input-alike whose queue is filled by a paired _FakeOutput."""

    def __init__(self):
        self.queue: list[mido.Message] = []

    def poll(self):
        return self.queue.pop(0) if self.queue else None


class _FakeOutput:
    """A mido-output-alike that records sent messages and (optionally)
    delivers a canned reply to a paired _FakeInput on each send."""

    def __init__(self, inport=None, reply=()):
        self.inport = inport
        self.reply = list(reply)
        self.sent: list[mido.Message] = []

    def send(self, msg):
        self.sent.append(msg)
        if self.inport is not None:
            self.inport.queue.extend(self.reply)


def _reply_messages(sound, page, set_no, device_id=0):
    return LiveSetCollection({(page, set_no): sound}).to_sysex(device_id=device_id)


def test_request_sound_fake_roundtrip(sound_1_1):
    inport = _FakeInput()
    outport = _FakeOutput(inport, _reply_messages(sound_1_1, 2, 3))
    result = cp_liveset.request_sound(inport, outport, 2, 3)
    assert result == sound_1_1
    # exactly one Bulk Dump Request was sent
    assert len(outport.sent) == 1
    assert outport.sent[0].type == "sysex"


def test_request_sound_discards_stale_input(sound_1_1):
    inport = _FakeInput()
    # stale leftovers from an earlier dump of a different Live Set
    inport.queue.extend(_reply_messages(sound_1_1, 9, 1))
    outport = _FakeOutput(inport, _reply_messages(sound_1_1, 2, 3))
    assert cp_liveset.request_sound(inport, outport, 2, 3) == sound_1_1


def test_request_sound_ignores_unrelated_messages(sound_1_1):
    inport = _FakeInput()
    reply = _reply_messages(sound_1_1, 2, 3)
    reply.insert(0, mido.Message("note_on", note=60))
    reply.insert(1, mido.Message("sysex", data=(0x7E, 0x7F, 0x06, 0x01)))  # other sysex
    outport = _FakeOutput(inport, reply)
    assert cp_liveset.request_sound(inport, outport, 2, 3) == sound_1_1


def test_request_sound_timeout():
    inport = _FakeInput()
    outport = _FakeOutput()  # no reply ever arrives
    with pytest.raises(DeviceTimeoutError):
        cp_liveset.request_sound(inport, outport, 1, 1, timeout=0.05)


def test_request_sound_validates_arguments():
    inport, outport = _FakeInput(), _FakeOutput()
    with pytest.raises(ValueError):
        cp_liveset.request_sound(inport, outport, 41, 1)
    with pytest.raises(ValueError):
        cp_liveset.request_sound(inport, outport, 1, 1, device_id=16)


def test_request_group_fake(sound_1_1):
    inport = _FakeInput()
    # the same canned reply satisfies only (2, 3); request_group asks per pair
    outport = _FakeOutput(inport, _reply_messages(sound_1_1, 2, 3))
    group = cp_liveset.request_group(inport, outport, [(2, 3)])
    assert group == {(2, 3): sound_1_1}


def test_send_sound_fake(sound_1_1):
    outport = _FakeOutput()
    cp_liveset.send_sound(outport, 4, 7, sound_1_1, gap=0)
    assert len(outport.sent) == 19
    back = LiveSetCollection.from_sysex(outport.sent)
    assert back == {(4, 7): sound_1_1}


def test_send_group_fake(factory_doc):
    group = LiveSetCollection({
        (1, 1): LiveSetSound.model_validate(factory_doc["pages"]["1"]["1"]),
        (2, 5): LiveSetSound.model_validate(factory_doc["pages"]["2"]["5"]),
    })
    outport = _FakeOutput()
    cp_liveset.send_group(outport, group, gap=0)
    assert len(outport.sent) == 38
    assert LiveSetCollection.from_sysex(outport.sent) == group


def test_select_messages():
    msgs = cp_liveset.select_messages(7, 3, channel=2)
    assert [m.type for m in msgs] == ["control_change", "control_change", "program_change"]
    assert msgs[0].control == 0 and msgs[0].value == 0x3F
    assert msgs[1].control == 32 and msgs[1].value == 6
    assert msgs[2].program == 2
    assert all(m.channel == 1 for m in msgs)


def test_select_messages_validates_arguments():
    with pytest.raises(ValueError):
        cp_liveset.select_messages(41, 1)
    with pytest.raises(ValueError):
        cp_liveset.select_messages(1, 1, channel=17)


def test_select_sound_fake():
    outport = _FakeOutput()
    cp_liveset.select_sound(outport, 7, 3)
    assert [m.type for m in outport.sent] == [
        "control_change", "control_change", "program_change"]


# --------------------------------------------------------------------------- live hardware
# These run only with a CP88/CP73 connected. They only ever write back data
# that was just read from the device, so its state is preserved.

def test_live_request_sound(device_ports):
    inport, outport = device_ports
    sound = cp_liveset.request_sound(inport, outport, 1, 1, timeout=5.0)
    assert isinstance(sound, LiveSetSound)
    assert sound.common.name.strip()


def test_live_request_group(device_ports):
    inport, outport = device_ports
    group = cp_liveset.request_group(inport, outport, [(1, 1), (1, 2)], timeout=5.0)
    assert set(group) == {(1, 1), (1, 2)}
    assert all(isinstance(ls, LiveSetSound) for ls in group.values())


def test_live_send_and_request_roundtrip(device_ports):
    inport, outport = device_ports
    original = cp_liveset.request_sound(inport, outport, 1, 1, timeout=5.0)
    cp_liveset.send_sound(outport, 1, 1, original)
    back = cp_liveset.request_sound(inport, outport, 1, 1, timeout=5.0)
    assert back == original


def test_live_select_sound(device_ports):
    _inport, outport = device_ports
    cp_liveset.select_sound(outport, 1, 1)
