from __future__ import annotations

import pytest

from cp_liveset import LiveSetSound

from _samples import make_sample_doc


@pytest.fixture(scope="session")
def factory_doc():
    """A document of synthetic sample Live Set Sounds (pages 1-5, sets 1-8)."""
    return make_sample_doc()


@pytest.fixture
def sound_1_1(factory_doc):
    """A single sample LiveSetSound (page 1, set 1, name "Test 1-1")."""
    return LiveSetSound.model_validate(factory_doc["pages"]["1"]["1"])


def _cp_port_names():
    """(input_name, output_name) of a connected CP88/CP73, or None.

    Matched separately per direction: on Windows, rtmidi appends the port
    index to the name, so the same physical port has different input and
    output names (e.g. 'CP88/CP73-1 0' vs 'CP88/CP73-1 1')."""
    try:
        import mido
        inputs, outputs = mido.get_input_names(), mido.get_output_names()
    except Exception:
        return None
    in_names = [n for n in inputs if "CP88" in n or "CP73" in n]
    out_names = [n for n in outputs if "CP88" in n or "CP73" in n]
    if not in_names or not out_names:
        return None
    return in_names[0], out_names[0]


@pytest.fixture(scope="session")
def cp_port_names():
    """(input_name, output_name) for a connected CP88/CP73, or None."""
    return _cp_port_names()


@pytest.fixture
def require_device(cp_port_names):
    """(input_name, output_name), skipping if no CP88/CP73 is connected."""
    if cp_port_names is None:
        pytest.skip("no CP88/CP73 MIDI device connected")
    return cp_port_names


@pytest.fixture
def device_port_spec(require_device):
    """A single PORT spec (name or unique prefix) usable for both input and
    output in the CLI's 'rtmidi:PORT' form, e.g. 'CP88/CP73-1' when the
    actual port names are 'CP88/CP73-1 0' (in) and 'CP88/CP73-1 1' (out)."""
    import os.path

    in_name, out_name = require_device
    return os.path.commonprefix([in_name, out_name]) or in_name


@pytest.fixture
def device_ports(require_device):
    """(inport, outport): open mido ports to a connected CP88/CP73."""
    import mido

    in_name, out_name = require_device
    with mido.open_input(in_name) as inport, mido.open_output(out_name) as outport:
        yield inport, outport
