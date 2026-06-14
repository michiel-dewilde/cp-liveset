from __future__ import annotations

import pytest

from cp_liveset import selectspec


def test_bare_star_identity_over_present():
    present = {(1, 1), (1, 2), (3, 5)}
    pairs = sorted(selectspec.resolve("*", present))
    assert pairs == [((1, 1), (1, 1)), ((1, 2), (1, 2)), ((3, 5), (3, 5))]


def test_single_slot_no_remap():
    assert selectspec.resolve("3:5", set()) == [((3, 5), (3, 5))]


def test_single_slot_remap():
    assert selectspec.resolve("1:5=2:3", set()) == [((1, 5), (2, 3))]


def test_range_block_remap():
    pairs = selectspec.resolve("1-2:1-2=9-10:1-2", set())
    assert pairs == [
        ((1, 1), (9, 1)), ((1, 2), (9, 2)),
        ((2, 1), (10, 1)), ((2, 2), (10, 2)),
    ]


def test_comma_list_pages():
    assert selectspec.resolve("1,3:5", set()) == [((1, 5), (1, 5)), ((3, 5), (3, 5))]


def test_left_star_sets_means_present_for_page():
    present = {(1, 1), (1, 2), (2, 5)}
    pairs = selectspec.resolve("1:*", present)
    assert pairs == [((1, 1), (1, 1)), ((1, 2), (1, 2))]


def test_left_star_sets_remapped_to_full_range():
    present = {(1, s) for s in range(1, 9)}
    pairs = selectspec.resolve("1:*=5:*", present)
    assert pairs == [((1, s), (5, s)) for s in range(1, 9)]


def test_left_star_pages_means_present_pages():
    present = {(1, 5), (3, 5), (3, 1)}
    pairs = selectspec.resolve("*:5", present)
    assert pairs == [((1, 5), (1, 5)), ((3, 5), (3, 5))]


def test_cardinality_mismatch_raises():
    present = {(1, 1), (1, 2)}  # only 2 sets present for page 1
    with pytest.raises(selectspec.SpecError):
        selectspec.resolve("1:*=5:*", present)


def test_out_of_range_page_raises():
    with pytest.raises(selectspec.SpecError):
        selectspec.resolve("41:1", set())


def test_out_of_range_set_raises():
    with pytest.raises(selectspec.SpecError):
        selectspec.resolve("1:9", set())


def test_invalid_range_missing_colon_raises():
    with pytest.raises(selectspec.SpecError):
        selectspec.resolve("*=*", set())


def test_static_left_pairs_bare_star_is_none():
    assert selectspec.static_left_pairs("*") is None


def test_static_left_pairs_left_star_is_none():
    assert selectspec.static_left_pairs("1:*") is None
    assert selectspec.static_left_pairs("*:5") is None
    assert selectspec.static_left_pairs("1:*=5:*") is None


def test_static_left_pairs_explicit():
    assert selectspec.static_left_pairs("1:5") == [(1, 5)]
    assert selectspec.static_left_pairs("1-2:1-2") == [
        (1, 1), (1, 2), (2, 1), (2, 2)]
    assert selectspec.static_left_pairs("1:1-8=5:1-8") == [(1, s) for s in range(1, 9)]


def test_later_pairs_can_overwrite_logic_is_caller_responsibility():
    # resolve() itself just produces pairs; overwrite semantics are applied
    # by the caller (cmd_convert) when writing into the working group.
    pairs = selectspec.resolve("1:1-2=5:1-2", set())
    assert pairs == [((1, 1), (5, 1)), ((1, 2), (5, 2))]
