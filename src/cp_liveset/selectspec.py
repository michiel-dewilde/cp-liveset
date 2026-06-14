"""
Parser/resolver for the `convert` command's input/output selection and
remapping specs.

A spec is one of:

  *                          all present (page,set) pairs, identity mapping
  <range>                    select <range>, identity mapping
  <range>=<range>            select the left range, remap onto the right

<range> is "<pages>:<sets>", where <pages>/<sets> is each either "*" or a
comma-separated list of integers and/or "a-b" ranges, e.g. "1", "1,3,5",
"1-4", "1,3,5-7", "*".

"*" on the left side of "=" (or the only side, for a spec with no "="):
  - as <pages>: all pages that occur in the source's present pairs
    (filtered by <sets> if it is not also "*")
  - as <sets>: for each selected page, all sets present for that page

"*" on the right side of "=":
  - as <pages>: all pages 1-PAGE_COUNT
  - as <sets>: all sets 1-SETS_PER_PAGE

For a spec with "=", the left and right sides must resolve to the same
number of (page,set) pairs; they are then paired up in order.
"""

from __future__ import annotations

from . import paramap

PAGE_COUNT = paramap.PAGE_COUNT
SETS_PER_PAGE = paramap.SETS_PER_PAGE


class SpecError(ValueError):
    pass


ALL_PAIRS = {(p, s) for p in range(1, PAGE_COUNT + 1) for s in range(1, SETS_PER_PAGE + 1)}


def _expand_items(s: str, lo: int, hi: int):
    """Parse a comma/range list of integers, or "*"."""
    s = s.strip()
    if s == "*":
        return "*"
    items: list[int] = []
    for part in s.split(","):
        part = part.strip()
        if not part:
            raise SpecError(f"empty item in '{s}'")
        if "-" in part:
            a_str, b_str = part.split("-", 1)
            try:
                a, b = int(a_str), int(b_str)
            except ValueError:
                raise SpecError(f"invalid range '{part}'")
            values = range(a, b + 1)
        else:
            try:
                values = [int(part)]
            except ValueError:
                raise SpecError(f"invalid number '{part}'")
        for v in values:
            if not (lo <= v <= hi):
                raise SpecError(f"value {v} out of range {lo}-{hi} in '{s}'")
            items.append(v)
    if not items:
        raise SpecError(f"empty selection '{s}'")
    return items


def _parse_range(s: str):
    if ":" not in s:
        raise SpecError(f"invalid range '{s}', expected PAGES:SETS")
    page_s, set_s = s.split(":", 1)
    return _expand_items(page_s, 1, PAGE_COUNT), _expand_items(set_s, 1, SETS_PER_PAGE)


def _expand_side(dims, present, is_dst: bool):
    page_items, set_items = dims

    if page_items == "*":
        if is_dst:
            pages = list(range(1, PAGE_COUNT + 1))
        elif set_items == "*":
            pages = sorted({p for p, _s in present})
        else:
            wanted_sets = set(set_items)
            pages = sorted({p for p, s in present if s in wanted_sets})
    else:
        pages = page_items

    pairs = []
    for p in pages:
        if set_items == "*":
            if is_dst:
                sets = list(range(1, SETS_PER_PAGE + 1))
            else:
                sets = sorted(s for pp, s in present if pp == p)
        else:
            sets = set_items
        for s in sets:
            pairs.append((p, s))
    return pairs


def static_left_pairs(spec: str):
    """Return the left-hand-side (source) pairs of `spec`, if they can be
    computed without knowing what's `present` (i.e. neither dimension of the
    left side is "*"), or None if the left side depends on `present`
    (including a bare "*" spec).
    """
    spec = spec.strip()
    if spec == "*":
        return None
    left_s = spec.split("=", 1)[0]
    page_items, set_items = _parse_range(left_s)
    if page_items == "*" or set_items == "*":
        return None
    return [(p, s) for p in page_items for s in set_items]


def resolve(spec: str, present: set[tuple[int, int]]):
    """Resolve `spec` against `present` (the source group's (page,set) keys).

    Returns a list of ((src_page,src_set), (dst_page,dst_set)) pairs.
    """
    spec = spec.strip()
    if spec == "*":
        pairs = sorted(present)
        return [(pr, pr) for pr in pairs]

    if "=" in spec:
        left_s, right_s = spec.split("=", 1)
    else:
        left_s, right_s = spec, None

    left_dims = _parse_range(left_s)
    src = _expand_side(left_dims, present, is_dst=False)

    if right_s is None:
        dst = src
    else:
        right_dims = _parse_range(right_s)
        dst = _expand_side(right_dims, present, is_dst=True)

    if len(src) != len(dst):
        raise SpecError(
            f"selection '{spec}': left side resolves to {len(src)} slot(s), "
            f"right side to {len(dst)}; counts must match")

    return list(zip(src, dst))
