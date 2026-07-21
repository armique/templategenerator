"""Tests for explainable standalone-item title classification."""

import pytest

from marktwert.domain.sales import (
    ClassificationDecision,
    ExclusionReason,
    ListingClassificationPolicy,
    ReviewReason,
)


@pytest.fixture
def policy() -> ListingClassificationPolicy:
    return ListingClassificationPolicy()


def test_working_item_with_original_packaging_is_accepted(
    policy: ListingClassificationPolicy,
) -> None:
    result = policy.classify("Gigabyte RTX 3070 Gaming OC 8 GB mit OVP")

    assert result.decision is ClassificationDecision.ACCEPT
    assert result.evidence == ()


@pytest.mark.parametrize(
    ("title", "expected_reason"),
    [
        ("RTX 3070 DEFEKT - für Bastler", ExclusionReason.FAULTY),
        ("Gigabyte RTX 3070 - nur OVP", ExclusionReason.EMPTY_BOX),
        ("RTX 3070 Backplate only", ExclusionReason.ACCESSORY_ONLY),
        ("RTX 3070 Ersatzteile", ExclusionReason.REPLACEMENT_PARTS),
    ],
)
def test_clear_non_working_or_non_standalone_titles_are_excluded(
    policy: ListingClassificationPolicy,
    title: str,
    expected_reason: ExclusionReason,
) -> None:
    result = policy.classify(title)

    assert result.decision is ClassificationDecision.EXCLUDE
    assert expected_reason in {item.reason for item in result.evidence}


def test_ambiguous_condition_is_sent_to_review(
    policy: ListingClassificationPolicy,
) -> None:
    result = policy.classify("RTX 3070 ungeprüft, siehe Beschreibung")

    assert result.decision is ClassificationDecision.REVIEW
    assert {item.reason for item in result.evidence} == {
        ReviewReason.AMBIGUOUS_CONDITION
    }


def test_user_exclusion_terms_are_explainable(
    policy: ListingClassificationPolicy,
) -> None:
    result = policy.classify(
        "RTX 3070 with water block",
        additional_exclusion_terms=("water block",),
    )

    assert result.decision is ClassificationDecision.EXCLUDE
    assert result.evidence[0].reason is ExclusionReason.USER_EXCLUDED
    assert result.evidence[0].matched_term == "water block"


def test_missing_required_term_is_excluded(
    policy: ListingClassificationPolicy,
) -> None:
    result = policy.classify(
        "Gigabyte RTX 3070 Gaming OC",
        required_terms=("8 GB",),
    )

    assert result.decision is ClassificationDecision.EXCLUDE
    assert result.evidence[0].reason is ExclusionReason.REQUIRED_TERM_MISSING
    assert result.evidence[0].matched_term == "8 GB"


def test_phrase_matching_does_not_match_partial_words(
    policy: ListingClassificationPolicy,
) -> None:
    result = policy.classify("Professionally repaired RTX 3070, fully working")

    assert result.decision is ClassificationDecision.ACCEPT
