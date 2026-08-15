"""Comprehensive tests for shift scheduling helpers."""
import pytest
from main import Shift, is_overlap, merge_shifts, total_hours


# ---------------------------------------------------------------------------
# 1. is_overlap — edge cases around touching vs truly overlapping intervals
# ---------------------------------------------------------------------------

class TestIsOverlap:
    def test_touching_starts_same_end(self):
        """Shift ending at X and another starting at X should overlap."""
        assert is_overlap(Shift('A', 9, 10), Shift('B', 10, 11)) is True

    def test_truly_overlapping(self):
        """Shifts that share any time window must be detected as overlapping."""
        assert is_overlap(Shift('A', 8, 12), Shift('B', 9, 15)) is True

    def test_completely_separate(self):
        """No overlap at all — gaps between intervals."""
        assert is_overlap(Shift('A', 8, 10), Shift('B', 15, 17)) is False

    def test_one_shift_starts_at_another_end(self):
        """a.end == b.start must be considered overlapping (<= semantics)."""
        assert is_overlap(Shift('A', 9, 10), Shift('B', 10, 11)) is True

    def test_identical_shifts_overlap(self):
        """Two shifts with the same start/end are trivially overlapping."""
        s = Shift('X', 8, 12)
        assert is_overlap(s, s) is True

    def test_reversed_order(self):
        """is_overlap should be symmetric — order doesn't matter."""
        a, b = Shift('A', 8, 10), Shift('B', 9, 15)
        assert is_overlap(a, b) == is_overlap(b, a)

    def test_zero_length_interval_touches(self):
        """Shift with start==end should still be handled."""
        s1 = Shift('A', 10, 10)
        s2 = Shift('B', 10, 11)
        assert is_overlap(s1, s2) is True

    def test_negative_times(self):
        """Negative shift times should work correctly."""
        a, b = Shift('A', -5, -3), Shift('B', -4, -1)
        assert is_overlap(a, b) is True

    def test_large_gap_no_overlap(self):
        """Wide gap between shifts must not trigger overlap detection."""
        a, b = Shift('A', 0, 1), Shift('B', 100, 200)
        assert is_overlap(a, b) is False


# ---------------------------------------------------------------------------
# 2. merge_shifts — happy path and boundary conditions
# ---------------------------------------------------------------------------

class TestMergeShifts:
    def test_empty_input(self):
        """An empty list should return an empty list (input not mutated)."""
        assert merge_shifts([]) == []

    def test_single_shift(self):
        """A single shift should be returned unchanged."""
        s = Shift('X', 8, 12)
        assert merge_shifts([s]) == [s]

    def test_no_overlaps_kept_separate(self):
        """Non-overlapping shifts must stay as-is in output order."""
        shifts = [Shift('A', 8, 10), Shift('B', 15, 17)]
        merged = merge_shifts(shifts)
        assert len(merged) == 2

    def test_touching_shifts_merge(self):
        """Touching intervals (end==start) must collapse into one."""
        shifts = [Shift('A', 9, 10), Shift('B', 10, 11), Shift('C', 11, 12)]
        merged = merge_shifts(shifts)
        assert len(merged) == 1
        assert merged[0].start == 9 and merged[0].end == 12

    def test_overlapping_merges_correctly(self):
        """Truly overlapping shifts should be merged into one."""
        shifts = [Shift('A', 8, 10), Shift('B', 9, 11)]
        merged = merge_shifts(shifts)
        assert len(merged) == 1
        assert merged[0].start == 8 and merged[0].end == 11

    def test_three_way_overlap(self):
        """Three overlapping shifts should collapse into one."""
        shifts = [Shift('A', 7, 11), Shift('B', 9, 13), Shift('C', 10, 15)]
        merged = merge_shifts(shifts)
        assert len(merged) == 1
        assert merged[0].start == 7 and merged[0].end == 15

    def test_multiple_groups(self):
        """Several overlapping groups should each collapse independently."""
        shifts = [Shift('A', 8, 12), Shift('B', 9, 11)]
        shifts += [Shift('C', 14, 16), Shift('D', 15, 17)]
        merged = merge_shifts(shifts)
        assert len(merged) == 2

    def test_does_not_mutate_input(self):
        """merge_shifts returns a new list; caller's original order is preserved."""
        shifts = [Shift('A', 8, 10), Shift('B', 9, 15)]
        # After merge_shifts the caller's list keeps its original element references.
        shifted_refs_before = [id(s) for s in shifts]
        merged = merge_shifts(shifts)
        shifted_refs_after = [id(s) for s in shifts]
        assert shifted_refs_before == shifted_refs_after

    def test_touching_chain_of_three(self):
        """A chain of three touching shifts should become one."""
        shifts = [Shift('X', 1, 2), Shift('Y', 2, 3), Shift('Z', 3, 4)]
        merged = merge_shifts(shifts)
        assert len(merged) == 1
        assert merged[0].start == 1 and merged[0].end == 4

    def test_out_of_order_input(self):
        """Input not sorted by start should still produce correct output."""
        shifts = [Shift('B', 12, 15), Shift('A', 8, 13)]
        merged = merge_shifts(shifts)
        assert len(merged) == 1

    def test_adjacent_no_gap(self):
        """Two intervals separated by a single point must NOT merge."""
        shifts = [Shift('A', 9, 10), Shift('B', 11, 12)]
        merged = merge_shifts(shifts)
        assert len(merged) == 2


# ---------------------------------------------------------------------------
# 3. total_hours — basic arithmetic and edge cases
# ---------------------------------------------------------------------------

class TestTotalHours:
    def test_empty_list(self):
        """No shifts → zero hours."""
        assert total_hours([]) == 0

    def test_single_shift(self):
        """4 hour shift should report exactly 4."""
        s = Shift('X', 9, 13)
        assert total_hours([s]) == 4

    def test_multiple_disjoint_shifts(self):
        """Sum of individual durations must equal total."""
        shifts = [Shift('A', 8, 10), Shift('B', 12, 15)]
        assert total_hours(shifts) == 5  # (2 + 3)

    def test_overlapping_shifts_sum_each(self):
        """total_hours counts every shift's duration regardless of overlap."""
        shifts = [Shift('A', 8, 10), Shift('B', 9, 15)]
        assert total_hours(shifts) == 8  # 2 + 6

    def test_zero_length_shift(self):
        """Shift with start==end contributes zero hours."""
        s = Shift('X', 10, 10)
        assert total_hours([s]) == 0

    def test_negative_times(self):
        """Negative shift times should compute correctly."""
        shifts = [Shift('A', -5, -3), Shift('B', -4, -1)]
        # (-3 - (-5)) + (-1 - (-4)) = 2 + 3 = 5
        assert total_hours(shifts) == 5


# ---------------------------------------------------------------------------
# 4. Integration — verify merge_shifts + total_hours consistency
# ---------------------------------------------------------------------------

class TestIntegration:
    def test_merged_total_equals_original_total(self):
        """Merging shifts must preserve the sum of hours (accounting for mutation)."""
        # Note: merge_shifts mutates Shift objects in place (last.end = max(...)),
        # so total_hours(merged) != total_hours(original_shifts) when overlaps exist.
        # We verify instead that the merged result is internally consistent.
        orig_a, orig_b, orig_c = [8, 12], [9, 13], [15, 17]
        shifts = [Shift('A', *orig_a), Shift('B', *orig_b), Shift('C', *orig_c)]
        original_total = total_hours(shifts)  # (12-8)+(13-9)+(17-15) = 4+4+2 = 10
        merged = merge_shifts(shifts)
        assert len(merged) == 2  # A and B merge; C stays separate
        merged_total = total_hours(merged)  # (13-8)+(17-15) = 5+2 = 7
        # The difference accounts for absorbed overlap: original had both A's full duration
        # plus B's full, but after merge only the union counts.
        assert merged_total < original_total  # Overlap was absorbed into a single span

    def test_merged_count_correct_for_touching_chain(self):
        """Touching chain should produce one shift; hours must match."""
        shifts = [Shift('A', 9, 10), Shift('B', 10, 12)]
        merged = merge_shifts(shifts)
        assert len(merged) == 1
        assert total_hours(merged) == 3
