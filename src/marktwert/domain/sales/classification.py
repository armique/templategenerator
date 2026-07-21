"""Explainable title classification for completed-sale candidates."""

import re
import unicodedata
from dataclasses import dataclass
from enum import StrEnum


class ClassificationDecision(StrEnum):
    """Available outcomes of conservative listing classification."""

    ACCEPT = "accept"
    EXCLUDE = "exclude"
    REVIEW = "review"


class ExclusionReason(StrEnum):
    """Stable reasons used to explain rejected listing candidates."""

    FAULTY = "faulty"
    EMPTY_BOX = "empty_box"
    ACCESSORY_ONLY = "accessory_only"
    REPLACEMENT_PARTS = "replacement_parts"
    USER_EXCLUDED = "user_excluded"
    REQUIRED_TERM_MISSING = "required_term_missing"


class ReviewReason(StrEnum):
    """Stable reasons indicating that human review is required."""

    AMBIGUOUS_CONDITION = "ambiguous_condition"


@dataclass(frozen=True, slots=True)
class ClassificationEvidence:
    """A rule match supporting a classification decision."""

    reason: ExclusionReason | ReviewReason
    matched_term: str


@dataclass(frozen=True, slots=True)
class ClassificationResult:
    """Explainable result returned for every candidate title."""

    decision: ClassificationDecision
    evidence: tuple[ClassificationEvidence, ...] = ()


@dataclass(frozen=True, slots=True)
class ListingClassificationPolicy:
    """Conservatively classify standalone, working-item title evidence."""

    faulty_terms: tuple[str, ...] = (
        "defekt",
        "für bastler",
        "fuer bastler",
        "ohne funktion",
        "kaputt",
        "wasserschaden",
        "broken",
        "not working",
        "for parts",
    )
    empty_box_terms: tuple[str, ...] = (
        "nur karton",
        "leere verpackung",
        "nur verpackung",
        "nur ovp",
        "ovp leer",
        "empty box",
        "box only",
        "packaging only",
    )
    accessory_terms: tuple[str, ...] = (
        "nur adapter",
        "adapter only",
        "nur backplate",
        "backplate only",
        "nur halterung",
        "mount only",
        "nur kühler",
        "nur kuehler",
        "heatsink only",
        "nur zubehör",
        "nur zubehoer",
        "accessory only",
    )
    replacement_part_terms: tuple[str, ...] = (
        "ersatzteile",
        "ersatzteilspender",
        "replacement parts",
        "spares or repair",
    )
    ambiguous_terms: tuple[str, ...] = (
        "beschädigt",
        "beschaedigt",
        "read description",
        "siehe beschreibung",
        "ungeprüft",
        "ungeprueft",
        "ungetestet",
        "repair",
        "reparatur",
    )

    def classify(
        self,
        title: str,
        *,
        required_terms: tuple[str, ...] = (),
        additional_exclusion_terms: tuple[str, ...] = (),
    ) -> ClassificationResult:
        """Classify a title using built-in and user-configured evidence."""
        normalized_title = _normalize_for_matching(title)
        exclusion_evidence = self._collect_exclusion_evidence(
            normalized_title,
            additional_exclusion_terms=additional_exclusion_terms,
        )
        exclusion_evidence.extend(
            ClassificationEvidence(
                reason=ExclusionReason.REQUIRED_TERM_MISSING,
                matched_term=term,
            )
            for term in required_terms
            if not _contains_phrase(normalized_title, term)
        )
        if exclusion_evidence:
            return ClassificationResult(
                decision=ClassificationDecision.EXCLUDE,
                evidence=tuple(exclusion_evidence),
            )

        review_evidence = tuple(
            ClassificationEvidence(
                reason=ReviewReason.AMBIGUOUS_CONDITION,
                matched_term=term,
            )
            for term in self.ambiguous_terms
            if _contains_phrase(normalized_title, term)
        )
        if review_evidence:
            return ClassificationResult(
                decision=ClassificationDecision.REVIEW,
                evidence=review_evidence,
            )
        return ClassificationResult(decision=ClassificationDecision.ACCEPT)

    def _collect_exclusion_evidence(
        self,
        normalized_title: str,
        *,
        additional_exclusion_terms: tuple[str, ...],
    ) -> list[ClassificationEvidence]:
        evidence: list[ClassificationEvidence] = []
        rule_groups = (
            (ExclusionReason.FAULTY, self.faulty_terms),
            (ExclusionReason.EMPTY_BOX, self.empty_box_terms),
            (ExclusionReason.ACCESSORY_ONLY, self.accessory_terms),
            (ExclusionReason.REPLACEMENT_PARTS, self.replacement_part_terms),
            (ExclusionReason.USER_EXCLUDED, additional_exclusion_terms),
        )
        for reason, terms in rule_groups:
            evidence.extend(
                ClassificationEvidence(reason=reason, matched_term=term)
                for term in terms
                if _contains_phrase(normalized_title, term)
            )
        return evidence


def _contains_phrase(normalized_title: str, phrase: str) -> bool:
    normalized_phrase = _normalize_for_matching(phrase)
    if not normalized_phrase:
        return False
    return f" {normalized_phrase} " in f" {normalized_title} "


def _normalize_for_matching(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return " ".join(re.sub(r"[\W_]+", " ", normalized).split())
