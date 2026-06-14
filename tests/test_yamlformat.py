from __future__ import annotations

import io

from cp_liveset import LiveSetCollection, init_sound, make_yaml
from cp_liveset import yamlformat
from cp_liveset.soundmodels import LiveSetSound


def _as_sound(v):
    return v if isinstance(v, LiveSetSound) else LiveSetSound.model_validate(v)


def test_sound_yaml_roundtrip_exact(sound_1_1):
    yml = yamlformat.sound_to_yaml(sound_1_1)
    back = yamlformat.sound_from_yaml(yml)
    assert back == sound_1_1


def test_sound_yaml_canonical(sound_1_1):
    yml1 = yamlformat.sound_to_yaml(sound_1_1)
    back = yamlformat.sound_from_yaml(yml1)
    yml2 = yamlformat.sound_to_yaml(back)
    assert yml1 == yml2


def test_sample_group_yaml_roundtrip_exact(factory_doc):
    group = LiveSetCollection(
        {(int(p), int(s)): _as_sound(ls)
         for p, sets in factory_doc["pages"].items() for s, ls in sets.items()})
    back = LiveSetCollection.from_yaml(group.to_yaml())
    assert back == group


def test_group_yaml_file_roundtrip(tmp_path, factory_doc):
    # use a small subset to keep the test fast
    subset = LiveSetCollection(
        {(1, int(s)): _as_sound(ls) for s, ls in factory_doc["pages"]["1"].items()})
    path = tmp_path / "page1.yaml"
    yaml = make_yaml()
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(subset.to_yaml(), f)
    with open(path, "r", encoding="utf-8") as f:
        back = LiveSetCollection.from_yaml(yaml.load(f))
    assert back == subset


def test_yaml_text_is_canonical(sound_1_1):
    group = LiveSetCollection({(1, 1): sound_1_1})

    def dump(g):
        buf = io.StringIO()
        make_yaml().dump(g.to_yaml(), buf)
        return buf.getvalue()

    text1 = dump(group)
    back = LiveSetCollection.from_yaml(make_yaml().load(io.StringIO(text1)))
    assert dump(back) == text1


def test_yaml_name_is_stripped_of_trailing_spaces(sound_1_1):
    # Common.name is a fixed-length 15-char string (always trailing-space
    # padded), but the concise YAML "name" field is trimmed for display.
    assert sound_1_1.common.name.endswith(" ")
    yml = yamlformat.sound_to_yaml(sound_1_1)
    assert yml["name"] == sound_1_1.common.name.rstrip(" ")
    assert not yml["name"].endswith(" ")


def test_yaml_name_keeps_trailing_nulls():
    # The YAML format strips trailing spaces but, unlike JSON, keeps trailing
    # NULs, so a name reconstructs whatever padding it used. The factory
    # "Init Sound" happens to be NUL-padded, so it keeps its 5 trailing NULs
    # here and still round-trips exactly.
    init = init_sound()
    assert init.common.name == "Init Sound"                 # model: NULs stripped
    yml = yamlformat.sound_to_yaml(init)
    assert yml["name"] == "Init Sound" + "\x00" * 5         # yaml: NULs kept, spaces stripped
    assert yamlformat.sound_from_yaml(yml) == init
