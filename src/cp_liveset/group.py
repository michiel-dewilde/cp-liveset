"""
LiveSetCollection: a sparse, addressable collection of CP88/CP73 Live Set Sounds.

A LiveSetCollection is a MutableMapping from a (page, set) pair (page 1-40,
set 1-8) to a LiveSetSound, with conversions to and from every supported
representation. It is the unit the rest of the public API works in.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping, MutableMapping
from typing import Any, Optional, Tuple, Union

import mido
from ruamel.yaml.comments import CommentedMap

from . import codec, paramap, x9format, yamlformat
from .soundmodels import LiveSetSound

Pair = Tuple[int, int]
"""A Live Set Sound address: (page, set), page 1-40, set 1-8 (both 1-based)."""

JSON_FORMAT = codec.JSON_FORMAT
YAML_FORMAT = yamlformat.YAML_FORMAT
X9L_PAGE_COUNT = x9format.X9L_PAGE_COUNT

_REPR_LIMIT = 8


def init_sound() -> LiveSetSound:
    """Return a fresh "Init Sound" LiveSetSound (the device's empty-slot
    default, used for unused slots). Each call returns a new, independent
    instance."""
    return codec.init_sound()


def _check_pair(key: object) -> Pair:
    try:
        page, set_no = key  # type: ignore[misc]
        page = int(page)
        set_no = int(set_no)
    except (TypeError, ValueError):
        raise TypeError(f"LiveSetCollection keys must be (page, set) integer pairs, got {key!r}")
    paramap.check_page_set(page, set_no)
    return page, set_no


class LiveSetCollection(MutableMapping[Pair, LiveSetSound]):
    """A mapping of (page, set) -> LiveSetSound over the device's sparse
    40-page x 8-set Live Set space.

    Behaves like a dict keyed by (page, set) tuples (page 1-40, set 1-8),
    with key/value validation on insertion, and iterates in (page, set)
    order. All conversions are non-streaming; a full group (320 Live Set Sounds)
    is small.

    Conversions (each pair documents its boundary type):

    - JSON:  ``from_json`` / ``to_json``  (plain JSON-able dicts)
    - YAML:  ``from_yaml`` / ``to_yaml``  (ruamel.yaml CommentedMap)
    - SysEx: ``from_sysex`` / ``to_sysex``  (mido sysex Messages)
    - X9:    ``from_x9`` / ``to_x9l`` / ``to_x9p`` / ``to_x9s``  (bytes of a
      whole .X9A/.X9L/.X9P/.X9S container file)

    For a single LiveSetSound, use pydantic's ``LiveSetSound.model_validate(...)`` /
    ``sound.model_dump(mode="json")`` for the JSON shape, or a one-entry
    LiveSetCollection for any of the other representations.
    """

    __slots__ = ("_items",)

    def __init__(self, items: Union[Mapping[Pair, LiveSetSound],
                                     Iterable[Tuple[Pair, LiveSetSound]]] = ()) -> None:
        self._items: dict[Pair, LiveSetSound] = {}
        self.update(items)

    # ------------------------------------------------------------- mapping

    def __setitem__(self, key: Pair, value: LiveSetSound) -> None:
        pair = _check_pair(key)
        if not isinstance(value, LiveSetSound):
            raise TypeError(f"LiveSetCollection values must be LiveSetSound instances, "
                            f"got {type(value).__name__}")
        self._items[pair] = value

    def __getitem__(self, key: Pair) -> LiveSetSound:
        return self._items[key]

    def __delitem__(self, key: Pair) -> None:
        del self._items[key]

    def __iter__(self) -> Iterator[Pair]:
        return iter(sorted(self._items))

    def __len__(self) -> int:
        return len(self._items)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, LiveSetCollection):
            return self._items == other._items
        if isinstance(other, Mapping):
            return self._items == dict(other)
        return NotImplemented

    def __repr__(self) -> str:
        pairs = sorted(self._items)
        shown = ", ".join(
            f"({page}, {set_no}): {self._items[(page, set_no)].common.name.rstrip(' ')!r}"
            for page, set_no in pairs[:_REPR_LIMIT])
        if len(pairs) > _REPR_LIMIT:
            shown += f", ... {len(pairs) - _REPR_LIMIT} more"
        return f"{type(self).__name__}({{{shown}}})"

    # ---------------------------------------------------------------- JSON

    @classmethod
    def from_json(cls, doc: Mapping[str, Any]) -> "LiveSetCollection":
        """Build a group from a cp88-cp73-liveset-v1 document (the plain,
        JSON-able dict shape produced by ``to_json``, e.g. straight out of
        ``json.load``). Raises ValueError if ``doc["format"]`` is not
        ``JSON_FORMAT``."""
        if not isinstance(doc, Mapping) or doc.get("format") != JSON_FORMAT:
            fmt = doc.get("format") if isinstance(doc, Mapping) else doc
            raise ValueError(f"unrecognized file format: {fmt!r}")
        group = cls()
        for page_str, sets in (doc.get("pages") or {}).items():
            for set_str, sound in sets.items():
                group[(int(page_str), int(set_str))] = LiveSetSound.model_validate(sound)
        return group

    def to_json(self) -> dict[str, Any]:
        """Return the group as a cp88-cp73-liveset-v1 document: a plain,
        JSON-able dict (pass it to ``json.dump`` yourself)."""
        pages: dict[str, dict[str, Any]] = {}
        for page, set_no in self:
            pages.setdefault(str(page), {})[str(set_no)] = \
                self._items[(page, set_no)].model_dump(mode="json")
        return {"format": JSON_FORMAT, "pages": pages}

    # ---------------------------------------------------------------- YAML

    @classmethod
    def from_yaml(cls, node: Mapping[Any, Any]) -> "LiveSetCollection":
        """Build a group from a cp88-cp73-liveset-yaml-v1 document (the
        ruamel.yaml mapping shape produced by ``to_yaml``, e.g. straight out
        of ``ruamel.yaml.YAML().load``). Raises ValueError if
        ``node["format"]`` is not ``YAML_FORMAT``."""
        if not isinstance(node, Mapping) or node.get("format") != YAML_FORMAT:
            fmt = node.get("format") if isinstance(node, Mapping) else node
            raise ValueError(f"unrecognized file format: {fmt!r}")
        group = cls()
        for page, sets in (node.get("pages") or {}).items():
            for set_no, sound_node in sets.items():
                group[(int(page), int(set_no))] = yamlformat.sound_from_yaml(sound_node)
        return group

    def to_yaml(self) -> CommentedMap:
        """Return the group as a cp88-cp73-liveset-yaml-v1 document: a
        ruamel.yaml CommentedMap (with the instrument voice number as the one
        eol comment) that only encodes values differing from their factory
        defaults. Dump it with a ``make_yaml()`` instance to get the canonical
        formatting."""
        out = CommentedMap()
        out["format"] = YAML_FORMAT
        pages = CommentedMap()
        for page, set_no in self:
            pages.setdefault(page, CommentedMap())[set_no] = \
                yamlformat.sound_to_yaml(self._items[(page, set_no)])
        out["pages"] = pages
        return out

    # --------------------------------------------------------------- SysEx

    @classmethod
    def from_sysex(cls, messages: Iterable[Union[mido.Message, bytes]], *,
                   ignore_unknown: bool = False) -> "LiveSetCollection":
        """Build a group from a stream of Bulk Dump SysEx messages (each a
        mido Message or raw F0..F7 bytes), e.g. all messages of a
        ``mido.MidiFile`` recorded from the device. Non-sysex mido messages,
        and messages outside a Bulk Header/Footer bracket, are ignored; an
        incomplete Live Set Sound (e.g. a missing Bulk Footer or data block), a bad
        checksum, or sysex that is not a CP88/CP73 Bulk Dump raises
        SysexError/ValueError. If the same (page, set) occurs more than
        once, the last one wins. The result may be empty.

        Pass ``ignore_unknown=True`` to skip (rather than reject) any SysEx
        that is not a well-formed CP88/CP73 Bulk Dump, e.g. when reading a
        file that interleaves other SysEx data."""
        raw: list[bytes] = []
        for msg in messages:
            if isinstance(msg, (bytes, bytearray, memoryview)):
                raw.append(bytes(msg))
            elif isinstance(msg, mido.messages.BaseMessage):  # incl. MetaMessage
                if msg.type == "sysex":
                    raw.append(bytes([0xF0, *msg.data, 0xF7]))
            else:
                raise TypeError(
                    f"expected mido messages or raw bytes, got {type(msg).__name__}")
        group = cls()
        for parsed in codec.iter_sounds_from_messages(raw, ignore_unknown=ignore_unknown):
            group[(parsed.page, parsed.set_no)] = parsed.sound
        return group

    def to_sysex(self, *, device_id: int = 0) -> list[mido.Message]:
        """Return the group as Bulk Dump SysEx messages: 19 mido sysex
        Messages per Live Set Sound (header + 17 data blocks + footer), in
        (page, set) order, all with ``time=0``. Playing/sending these to the
        device stores the Live Set Sounds at their (page, set) addresses.
        ``device_id`` (0-15) is the MIDI SysEx device number to embed."""
        _check_device_id(device_id)
        out: list[mido.Message] = []
        for page, set_no in self:
            for raw in codec.sound_to_messages(device_id, page, set_no,
                                                  self._items[(page, set_no)]):
                out.append(mido.Message("sysex", data=raw[1:-1]))
        return out

    # ------------------------------------------------------------ X9 files

    @classmethod
    def from_x9(cls, data: bytes) -> "LiveSetCollection":
        """Build a group from the contents of any .X9A/.X9L/.X9P/.X9S file.
        Raises ValueError if `data` is not a YSFC container or holds no Live
        Sets. Note the X9 file format only stores 189 of the 244 fields; the
        rest read back as 0 (see the README's field coverage caveat)."""
        return cls(x9format.parse_container(data))

    def to_x9l(self) -> bytes:
        """Return the group as the contents of a .X9L ("Live Set All",
        pages 1-20 x 8 sets) file. All keys must be within pages 1-20;
        missing (page, set) slots are filled with "Init Sound". Fields not
        representable in the X9 format are silently dropped."""
        return x9format.build_x9l(self._items, fill=init_sound())

    def to_x9p(self, page: Optional[int] = None) -> bytes:
        """Return the group as the contents of a .X9P ("Live Set Page",
        8 sets) file for `page`. With ``page=None`` the page is inferred:
        the group must be non-empty and entirely on one page. With an
        explicit `page`, every entry must already be keyed on that page
        (remap first if needed); missing sets are filled with "Init Sound".
        Fields not representable in the X9 format are silently dropped."""
        if page is None:
            pages = {p for p, _s in self._items}
            if not pages:
                raise ValueError(
                    "writing .X9P without an explicit page requires at least one Live Set Sound")
            if len(pages) != 1:
                raise ValueError(
                    f"writing .X9P without an explicit page requires Live Set Sounds from "
                    f"exactly one page, got pages {sorted(pages)}")
            page = pages.pop()
        else:
            paramap.check_page_set(page, 1)
            wrong = sorted({p for p, _s in self._items if p != page})
            if wrong:
                raise ValueError(
                    f"writing .X9P for page {page}: group contains Live Set Sounds on "
                    f"page(s) {wrong} (remap them to page {page} first)")
        return x9format.build_x9p(self._items, page, fill=init_sound())

    def to_x9s(self) -> bytes:
        """Return the group as the contents of a .X9S ("Live Set Sound", single
        set) file. The group must contain exactly one Live Set Sound; its
        (page, set) key is the identity stored in the file (which is where
        the device loads it to). Fields not representable in the X9 format
        are silently dropped."""
        if len(self._items) != 1:
            raise ValueError(
                f"writing .X9S requires exactly one Live Set Sound, got {len(self._items)}")
        ((page, set_no), sound), = self._items.items()
        return x9format.build_x9s(page, set_no, sound)


def _check_device_id(device_id: int) -> None:
    if not (0 <= device_id <= 15):
        raise ValueError(f"device_id must be 0-15, got {device_id}")
