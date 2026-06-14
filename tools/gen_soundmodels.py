"""
Generate src/cp_liveset/soundmodels.py from paramap.py's field tables.

Usage:
    python tools/gen_soundmodels.py > src/cp_liveset/soundmodels.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cp_liveset import paramap  # noqa: E402

HEADER = '''"""
Pydantic models for the cp88-cp73-liveset-v1 Live Set structure.

Generated from paramap.py's field tables -- do not edit by hand.
Regenerate with:

    python tools/gen_soundmodels.py > src/cp_liveset/soundmodels.py
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator
'''

MODEL_CONFIG = "    model_config = ConfigDict(validate_assignment=True, extra=\"forbid\")"


def _field_type(fsize: int, kind: str) -> str:
    if kind == "ascii":
        # Charset per the manual: ASCII 0x20-0x7F. Enforced here so that
        # encoding back to SysEx bytes can never fail or corrupt a block.
        return (f'Annotated[str, StringConstraints(max_length={fsize}, '
                f'pattern=r"^[\\x20-\\x7f]*$")]')
    if kind == "byte":
        return "Annotated[int, Field(ge=0, le=127)]"
    assert kind == "bytes", kind
    return (
        f"Annotated[list[Annotated[int, Field(ge=0, le=127)]], "
        f"Field(min_length={fsize}, max_length={fsize})]"
    )


def _emit_block_class(name: str, fields) -> str:
    lines = [f"class {name}(BaseModel):", MODEL_CONFIG]
    for _offset, field_name, fsize, kind in fields:
        lines.append(f"    {field_name}: {_field_type(fsize, kind)}")
    if name == "Common":
        lines.append("")
        lines.append("    # mode='before' so that NUL padding from raw device dumps is")
        lines.append("    # stripped before the charset pattern constraint is checked.")
        lines.append('    @field_validator("name", mode="before")')
        lines.append("    @classmethod")
        lines.append("    def _strip_trailing_nulls(cls, v):")
        lines.append('        return v.rstrip("\\x00") if isinstance(v, str) else v')
    return "\n".join(lines)


def generate() -> str:
    parts = [HEADER]

    parts.append(_emit_block_class("SoundMondo", paramap.SOUNDMONDO_FIELDS))
    parts.append(_emit_block_class("MasterEq", paramap.MASTER_EQ_FIELDS))
    parts.append(_emit_block_class("Common", paramap.COMMON_FIELDS))
    parts.append(_emit_block_class("Additional", paramap.ADDITIONAL_FIELDS))
    parts.append(_emit_block_class("Zone", paramap.ZONE_FIELDS))
    parts.append(_emit_block_class("SectionCommon", paramap.SECTION_COMMON_FIELDS))
    parts.append(_emit_block_class("SectionSpecific", paramap.SECTION_SPECIFIC_FIELDS))
    parts.append(_emit_block_class("SectionAdditional", paramap.SECTION_ADDITIONAL_FIELDS))

    parts.append(
        "class Section(BaseModel):\n"
        f"{MODEL_CONFIG}\n"
        "    common: SectionCommon\n"
        "    specific: SectionSpecific\n"
        "    additional: SectionAdditional"
    )

    section_fields = "\n".join(f"    {sec}: Section" for sec in paramap.SECTION_NAMES)
    parts.append(
        "class Sections(BaseModel):\n"
        f"{MODEL_CONFIG}\n"
        f"{section_fields}"
    )

    parts.append(
        "class LiveSetSound(BaseModel):\n"
        f"{MODEL_CONFIG}\n"
        "    soundmondo: SoundMondo\n"
        "    master_eq: MasterEq\n"
        "    common: Common\n"
        "    additional: Additional\n"
        "    zones: Annotated[list[Zone], "
        f"Field(min_length={paramap.ZONE_COUNT}, max_length={paramap.ZONE_COUNT})]\n"
        "    sections: Sections"
    )

    return "\n\n\n".join(parts) + "\n"


if __name__ == "__main__":
    sys.stdout.write(generate())
