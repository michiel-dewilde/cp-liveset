"""
cp_liveset - manage Yamaha CP88/CP73 Live Set data from Python.

The two central types are:

- ``LiveSetSound``: one Live Set Sound, a pydantic model decoding every byte of
  the device's 17 SysEx Bulk Dump data blocks into named fields (e.g.
  ``sound.common.name``, ``sound.sections.piano.common.section_volume``).
  Its JSON shape is the pydantic one: ``LiveSetSound.model_validate(data)`` /
  ``sound.model_dump(mode="json")``.
- ``LiveSetCollection``: a dict-like mapping of ``(page, set)`` (page 1-40,
  set 1-8) to ``LiveSetSound`` over the device's sparse Live Set space, with
  conversions to/from plain JSON dicts, ruamel.yaml documents, mido SysEx
  messages, and ``.X9*`` container file bytes.

Selecting, merging, and remapping Live Set Sounds is ordinary dict manipulation
on a ``LiveSetCollection``; there is deliberately no selection mini-language at
this level (the ``cp-liveset`` CLI builds one on top).

Live MIDI I/O (``request_sound``/``request_group``,
``send_sound``/``send_group``, ``select_sound``) works on mido ports
the caller has already opened; port discovery and opening stay with the
caller (``mido.get_input_names()``, ``mido.open_input()``, ...).

Example - read two Live Set Sounds from a connected CP88, save as YAML::

    import json, mido, cp_liveset

    with mido.open_input("CP88/CP73-1 0") as inp, \\
         mido.open_output("CP88/CP73-1 1") as out:
        group = cp_liveset.request_group(inp, out, [(1, 1), (1, 2)])

    print(group)                       # LiveSetCollection({(1, 1): 'Natural CFX', ...})
    group[(2, 1)] = group.pop((1, 1))  # remap 1:1 -> 2:1

    with open("mysets.yaml", "w", encoding="utf-8") as f:
        cp_liveset.make_yaml().dump(group.to_yaml(), f)

See docs/api.md for the full reference.
"""

from .device import (
    DEFAULT_SEND_GAP,
    DEFAULT_TIMEOUT,
    DeviceTimeoutError,
    request_group,
    request_sound,
    select_sound,
    select_messages,
    send_group,
    send_sound,
)
from .group import (
    JSON_FORMAT,
    X9L_PAGE_COUNT,
    YAML_FORMAT,
    LiveSetCollection,
    Pair,
    init_sound,
)
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
from .paramap import PAGE_COUNT, SETS_PER_PAGE
from .sysex import SysexError
from .yamlformat import make_yaml

__all__ = [
    # data model
    "LiveSetSound",
    "LiveSetCollection",
    "Pair",
    "init_sound",
    # LiveSetSound sub-models
    "SoundMondo",
    "MasterEq",
    "Common",
    "Additional",
    "Zone",
    "Section",
    "Sections",
    "SectionCommon",
    "SectionSpecific",
    "SectionAdditional",
    # live MIDI I/O
    "request_sound",
    "request_group",
    "send_sound",
    "send_group",
    "select_sound",
    "select_messages",
    "DEFAULT_TIMEOUT",
    "DEFAULT_SEND_GAP",
    # YAML helper
    "make_yaml",
    # errors
    "DeviceTimeoutError",
    "SysexError",
    # constants
    "PAGE_COUNT",
    "SETS_PER_PAGE",
    "X9L_PAGE_COUNT",
    "JSON_FORMAT",
    "YAML_FORMAT",
]
