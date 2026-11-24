"""ResumeIQ NLP engine.

Modules
-------
preprocessing       text normalization, tokenization, stop-words, lemmatization
similarity          TF-IDF vectors and cosine similarity (percentage)
keyword_extraction  JD keywords (1-3 word phrases), present / missing in resume
skill_extraction    skill dictionary, extraction, matched / missing skills
scoring             explainable estimated match score (NOT an ATS acceptance probability)
"""

from .keyword_extraction import analyze_keywords, extract_keywords
from .preprocessing import preprocess_text, preprocess_tokens
from .scoring import DISCLAIMER, calculate_match_score
from .similarity import calculate_similarity
from .skill_extraction import analyze_skills, extract_skills, register_skill

__all__ = [
    "DISCLAIMER",
    "analyze_keywords",
    "analyze_skills",
    "calculate_match_score",
    "calculate_similarity",
    "extract_keywords",
    "extract_skills",
    "preprocess_text",
    "preprocess_tokens",
    "register_skill",
]
