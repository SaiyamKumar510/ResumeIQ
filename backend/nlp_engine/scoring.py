"""Explainable resume <-> job description match score.

IMPORTANT - what this score is (and is not)
-------------------------------------------
The result is an *estimated compatibility score* computed from wording
similarity and technical-skill overlap. It is NOT the probability that a real
ATS (Applicant Tracking System) will accept, rank or reject the resume. Real
ATS products use their own, mostly undisclosed, rules and the decision also
involves recruiters. Nothing here has been trained or validated against real
ATS outcomes, and the weights below are an initial, hand-chosen setting.

How the score is calculated
---------------------------
    overall = 0.40 x text_similarity + 0.60 x skill_coverage

* text_similarity : TF-IDF cosine similarity of the two texts, in percent
                    (``similarity.calculate_similarity``).
* skill_coverage  : percent of the skills required by the job description that
                    are also found in the resume
                    (``skill_extraction.analyze_skills``):
                    ``matched JD skills / all JD skills x 100``.

Special case: if the job description mentions no skill from the skill
dictionary, coverage cannot be computed. The score then uses text similarity
only (weights 100% / 0%), ``skill_coverage`` is ``None`` and a note says so.
"""

from __future__ import annotations

from typing import Dict, Iterable, Optional

from .similarity import calculate_similarity
from .skill_extraction import analyze_skills

SIMILARITY_WEIGHT = 0.40
SKILL_WEIGHT = 0.60

DISCLAIMER = (
    "This is an estimated compatibility score based on text similarity and "
    "technical-skill coverage. It is NOT the actual probability that an ATS "
    "will accept or reject a resume."
)


def _validate_text(value, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string, got {type(value).__name__}")
    if not value.strip():
        raise ValueError(f"{name} must not be empty")


def _validate_weights(similarity_weight: float, skill_weight: float) -> None:
    if similarity_weight < 0 or skill_weight < 0:
        raise ValueError("weights must not be negative")
    if abs(similarity_weight + skill_weight - 1.0) > 1e-9:
        raise ValueError("similarity_weight and skill_weight must add up to 1.0")


def calculate_match_score(
    resume_text: str,
    job_description: str,
    similarity_weight: float = SIMILARITY_WEIGHT,
    skill_weight: float = SKILL_WEIGHT,
    corpus: Optional[Iterable[str]] = None,
) -> Dict:
    """Estimate how well a resume matches a job description.

    Parameters
    ----------
    resume_text, job_description:
        Raw texts. Both must be non-empty strings.
    similarity_weight, skill_weight:
        Weights of the two components (must add up to 1). Defaults: 0.4 / 0.6.
    corpus:
        Optional reference texts passed to the TF-IDF step (see ``similarity``).

    Returns
    -------
    dict with
        overall_score     estimated match score, 0-100
        text_similarity   0-100
        skill_coverage    0-100, or ``None`` if the JD has no known skills
        matched_skills    JD skills found in the resume
        missing_skills    JD skills not found in the resume
        category_analysis per-category required / matched / missing / coverage
        weights           the weights actually used
        explanation       one-line description of how the score was computed
        notes             list of warnings (empty when nothing special happened)
        disclaimer        reminder that this is not an ATS acceptance probability

    Raises
    ------
    TypeError  if an input is not a string.
    ValueError if a text is empty/blank or the weights are invalid.
    """
    _validate_text(resume_text, "resume_text")
    _validate_text(job_description, "job_description")
    _validate_weights(similarity_weight, skill_weight)

    similarity = calculate_similarity(resume_text, job_description, corpus=corpus)
    skills = analyze_skills(resume_text, job_description)
    coverage = skills["skill_coverage"]

    notes = []
    if coverage is None:
        weights = {"similarity": 1.0, "skills": 0.0}
        overall = similarity
        notes.append(
            "The job description mentions no skill from the skill dictionary, so "
            "the score is based on text similarity only."
        )
        explanation = f"overall = 100% x text similarity ({similarity}) = {overall}"
    else:
        weights = {"similarity": similarity_weight, "skills": skill_weight}
        overall = round(similarity_weight * similarity + skill_weight * coverage, 2)
        explanation = (
            f"overall = {similarity_weight:.0%} x text similarity ({similarity}) "
            f"+ {skill_weight:.0%} x skill coverage ({coverage}) = {overall}"
        )

    return {
        "overall_score": overall,
        "text_similarity": similarity,
        "skill_coverage": coverage,
        "matched_skills": skills["matched_skills"],
        "missing_skills": skills["missing_skills"],
        "category_analysis": skills["by_category"],
        "weights": weights,
        "explanation": explanation,
        "notes": notes,
        "disclaimer": DISCLAIMER,
    }
