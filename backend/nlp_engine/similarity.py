"""TF-IDF + cosine similarity between a resume and a job description.

Purpose
-------
Measure how similar two texts are in vocabulary, as a percentage (0-100).

Approach
--------
1. Clean both texts with ``preprocessing.preprocess_text``.
2. Convert them to TF-IDF vectors (scikit-learn ``TfidfVectorizer``,
   unigrams + bigrams, sublinear term frequency).
3. Take the cosine similarity of the two vectors and return it as a percentage.

Notes / limitations
-------------------
* No training happens here. TF-IDF is fitted on the texts it is given.
* With only two documents the IDF part has little effect (every shared word
  gets the same weight). If you have a reference collection (for example many
  job descriptions), pass it as ``corpus`` so IDF can down-weight words that
  are common everywhere.
* Similarity measures shared wording only; it does not understand meaning.

The three public functions can be used independently:
``build_tfidf_vectors`` -> ``cosine_similarity_percent`` -> ``calculate_similarity``.
"""

from __future__ import annotations

from typing import Iterable, Optional, Tuple

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .preprocessing import preprocess_text

DEFAULT_NGRAM_RANGE = (1, 2)


def _require_text(value, name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string, got {type(value).__name__}")
    return value


def build_tfidf_vectors(
    texts: Iterable[str],
    ngram_range: Tuple[int, int] = DEFAULT_NGRAM_RANGE,
    corpus: Optional[Iterable[str]] = None,
):
    """Convert texts into TF-IDF vectors.

    Parameters
    ----------
    texts:
        The raw texts to vectorize (they are preprocessed here).
    ngram_range:
        Word n-gram range, default unigrams and bigrams.
    corpus:
        Optional extra raw texts used only to fit the vocabulary / IDF.

    Returns
    -------
    (vectorizer, matrix)
        The fitted ``TfidfVectorizer`` and a sparse matrix with one row per
        text in ``texts`` (same order).

    Raises
    ------
    TypeError  if any text is not a string.
    ValueError if, after cleaning, there is nothing left to vectorize.
    """
    texts = [_require_text(t, "text") for t in texts]
    corpus = [_require_text(t, "corpus text") for t in (corpus or [])]

    cleaned_texts = [preprocess_text(t) for t in texts]
    cleaned_corpus = [preprocess_text(t) for t in corpus]

    # Tokens are already cleaned and space-separated, so split on whitespace
    # only. This keeps "c++", "c#", ".net", "node.js" and "ci/cd" intact.
    vectorizer = TfidfVectorizer(
        token_pattern=r"\S+",
        lowercase=False,
        ngram_range=ngram_range,
        sublinear_tf=True,
    )
    vectorizer.fit(cleaned_texts + cleaned_corpus)
    return vectorizer, vectorizer.transform(cleaned_texts)


def cosine_similarity_percent(vector_a, vector_b) -> float:
    """Cosine similarity of two TF-IDF vectors as a percentage (0-100, 2 decimals)."""
    score = float(cosine_similarity(vector_a, vector_b)[0][0])
    return round(max(0.0, min(1.0, score)) * 100, 2)


def calculate_similarity(
    resume_text: str,
    job_description: str,
    ngram_range: Tuple[int, int] = DEFAULT_NGRAM_RANGE,
    corpus: Optional[Iterable[str]] = None,
) -> float:
    """Return the TF-IDF cosine similarity of two texts as a percentage (0-100).

    Returns ``0.0`` if either text is empty or has no usable words after
    cleaning. Raises ``TypeError`` if an argument is not a string.
    """
    _require_text(resume_text, "resume_text")
    _require_text(job_description, "job_description")

    if not preprocess_text(resume_text) or not preprocess_text(job_description):
        return 0.0

    _, matrix = build_tfidf_vectors([resume_text, job_description], ngram_range, corpus)
    return cosine_similarity_percent(matrix[0], matrix[1])
