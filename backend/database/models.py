"""Database models."""

from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, Double, Integer, String, Text
from sqlalchemy.dialects.mysql import MEDIUMTEXT

from .db import db

# TEXT holds only 64 KB on MySQL; resumes extracted from PDFs can be longer.
LongText = Text().with_variant(MEDIUMTEXT(), "mysql")

JOB_DESCRIPTION_PREVIEW_CHARS = 100


def _utc_now() -> datetime:
    """Current UTC time as a naive datetime (MySQL DATETIME has no time zone)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def format_timestamp(value: datetime):
    """ISO-8601 string in UTC, e.g. ``2026-11-20T10:15:30Z``."""
    return value.replace(microsecond=0).isoformat() + "Z" if value else None


class Analysis(db.Model):
    """One saved resume <-> job description analysis.

    The structured columns store exactly what the NLP engine returned:
    ``calculate_match_score`` for the score fields and ``analyze_keywords``
    for the keyword fields.
    """

    __tablename__ = "analyses"
    __table_args__ = {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"}

    id = Column(Integer, primary_key=True)
    resume_filename = Column(String(255), nullable=True)  # NULL when text was pasted
    resume_text = Column(LongText, nullable=False)
    job_description = Column(LongText, nullable=False)

    overall_score = Column(Double, nullable=False)
    text_similarity = Column(Double, nullable=False)
    skill_coverage = Column(Double, nullable=True)  # NULL if the JD has no known skills

    matched_skills = Column(JSON, nullable=False)
    missing_skills = Column(JSON, nullable=False)
    category_analysis = Column(JSON, nullable=False)
    extracted_keywords = Column(JSON, nullable=False)
    missing_keywords = Column(JSON, nullable=False)

    scoring_explanation = Column(Text, nullable=False)
    score_weights = Column(JSON, nullable=False)
    scoring_notes = Column(JSON, nullable=False)

    created_at = Column(DateTime, nullable=False, default=_utc_now, index=True)

    def to_dict(self, disclaimer: str = None) -> dict:
        """Full representation, including the resume and job description text."""
        data = {
            "id": self.id,
            "resume_filename": self.resume_filename,
            "created_at": format_timestamp(self.created_at),
            "overall_score": self.overall_score,
            "text_similarity": self.text_similarity,
            "skill_coverage": self.skill_coverage,
            "matched_skills": self.matched_skills,
            "missing_skills": self.missing_skills,
            "category_analysis": self.category_analysis,
            "extracted_keywords": self.extracted_keywords,
            "missing_keywords": self.missing_keywords,
            "scoring_explanation": self.scoring_explanation,
            "weights": self.score_weights,
            "notes": self.scoring_notes,
            "resume_text": self.resume_text,
            "job_description": self.job_description,
        }
        if disclaimer is not None:
            data["disclaimer"] = disclaimer
        return data
