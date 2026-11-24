"""Keyword extraction from job descriptions and resume keyword coverage.

Purpose
-------
Find the important keywords of a job description (unigrams, bigrams and
trigrams), then report which of them appear in a resume and which are missing.

Approach
--------
1. Split the text into segments (lines, commas, bullets, sentences).
2. Inside each segment, stop-words and *generic* words ("experience", "team",
   "strong", "develop", ...) act as phrase breakers, so n-grams such as
   "machine learning" or "rest apis" are built only from consecutive
   meaningful words and never across "with", "and", etc.
3. Candidate 1-3 word phrases are counted and scored:
        score = count x weight
   weight 3.0  the phrase is a known skill (``skill_extraction`` dictionary)
          2.0  it contains a technical-looking token: an acronym (ETL), a
               camelCase name (PostgreSQL), or a token with digits/symbols
          1.0  anything else
4. A phrase is kept if it is a known skill, technical-looking, or repeated
   (2+ times for phrases, 3+ times for single words). Low-value single words
   ("developer", "software"), generic phrases ("problem solving") and
   non-technical phrases that merely wrap a known skill ("python developer",
   "integrate rest apis") are dropped, and a shorter phrase is removed when it
   only ever appears inside a longer kept phrase.
5. Skill keywords are merged under their canonical name (``nodejs`` and
   ``Node.js`` -> ``Node.js``).

Limitations
-----------
* A tool that is neither in the skill dictionary nor technical-looking
  (e.g. a plain capitalised name mentioned once) is not picked up; add it to
  the dictionary with ``skill_extraction.register_skill``.
* The single letters ``C`` and ``R`` are handled by skill extraction, not here.
* Presence in the resume is checked on lemmatized words and, for skills, on
  the canonical skill; it does not understand meaning (no synonyms beyond the
  skill dictionary).
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Dict, List, Set, Tuple

from .preprocessing import (
    is_stop_word,
    lemmatize_token,
    split_into_segments,
    tokenize,
)
from .skill_extraction import SKILL_DICTIONARY, extract_skills, skill_for_term

MAX_NGRAM = 3
DEFAULT_TOP_N = 25
MIN_COUNT_PHRASE = 2    # repeats needed for a non-technical phrase
MIN_COUNT_UNIGRAM = 3   # repeats needed for a non-technical single word

# Words that carry no technical information. They break phrases (like
# stop-words do). Stored as base forms; plural / past forms are matched via
# lemmatization.
GENERIC_TERMS = frozenset(
    """
    experience year work team ability able strong knowledge skill requirement
    require required responsibility responsible role candidate job position
    company looking look good great excellent understanding understand
    including include preferred prefer plus bonus nice must should will new
    need use used using like well high level least minimum proven demonstrated
    relevant similar join opportunity environment degree bachelor master
    qualification benefit overview summary education description about
    develop build design implement maintain write create collaborate ensure
    support provide perform participate contribute deliver manage lead help
    improve optimize deploy test review document analyze apply learn
    familiarity proficiency proficient hands exposure basic advanced senior
    junior fresher intern internship full time part month
    communication teamwork collaboration solving problem passion passionate
    motivated driven self fast paced deadline stakeholder
    """.split()
)

# Single words that are too generic to be a keyword on their own, but are fine
# inside a phrase ("backend developer", "software development").
LOW_VALUE_UNIGRAMS = frozenset(
    """
    development developer engineer engineering software application system
    solution project product business technology technical service feature
    code coding quality process tool platform industry client customer
    task goal result impact value idea data model design testing analysis learning stack
    """.split()
)

# Generic multi-word phrases to ignore.
GENERIC_PHRASES = frozenset({"problem solving", "problem solve"})

_ACRONYM_RE = re.compile(r"\b[A-Z]{2,6}\b")
_CAMEL_CASE_RE = re.compile(r"\b[A-Za-z]*[a-z][A-Z][A-Za-z0-9]*\b")
_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9+#.]*")
_SPECIAL_TOKEN_RE = re.compile(r"[0-9.+#/\-]")


# --------------------------------------------------------------------------
# Internals
# --------------------------------------------------------------------------

def _require_text(text, name: str) -> str:
    if not isinstance(text, str):
        raise TypeError(f"{name} must be a string, got {type(text).__name__}")
    return text


def _skill_vocabulary() -> Set[str]:
    """Every word used in a skill name or synonym ("learning", "testing",
    "design", ...). These words are never treated as generic, otherwise
    "machine learning" or "unit testing" would be cut apart."""
    words: Set[str] = set()
    for skills in SKILL_DICTIONARY.values():
        for skill, synonyms in skills.items():
            for alias in (skill, *synonyms):
                words.update(tokenize(alias))
    return words


def _is_generic(token: str, skill_words: Set[str]) -> bool:
    if token in skill_words:
        return False
    return token in GENERIC_TERMS or lemmatize_token(token, True) in GENERIC_TERMS


def _build_chunks(text: str, skill_words: Set[str]) -> List[List[Tuple[str, str]]]:
    """Split text into chunks of consecutive meaningful words.

    Each chunk is a list of ``(surface_token, noun_lemma)`` pairs.
    """
    chunks: List[List[Tuple[str, str]]] = []
    for segment in split_into_segments(text):
        current: List[Tuple[str, str]] = []
        for token in tokenize(segment):
            if is_stop_word(token) or _is_generic(token, skill_words):
                if current:
                    chunks.append(current)
                    current = []
                continue
            current.append((token, lemmatize_token(token, False)))
        if current:
            chunks.append(current)
    return chunks


def _technical_looking_words(text: str) -> Set[str]:
    """Lowercase words that look technical in the ORIGINAL text: acronyms
    (``ETL``), camelCase (``PostgreSQL``, ``TensorFlow``)."""
    words = {w.lower() for w in _ACRONYM_RE.findall(text)}
    words |= {w.lower() for w in _CAMEL_CASE_RE.findall(text)}
    return words


def _ngram_counts(chunks) -> Tuple[Counter, Dict[Tuple[str, ...], str]]:
    """Count lemma n-grams (n = 1..MAX_NGRAM) inside chunks and remember the
    first surface form of each."""
    counts: Counter = Counter()
    surface: Dict[Tuple[str, ...], str] = {}
    for chunk in chunks:
        for n in range(1, MAX_NGRAM + 1):
            for i in range(len(chunk) - n + 1):
                window = chunk[i : i + n]
                key = tuple(lemma for _, lemma in window)
                counts[key] += 1
                surface.setdefault(key, " ".join(tok for tok, _ in window))
    return counts, surface


def _is_contained(short: Tuple[str, ...], long: Tuple[str, ...]) -> bool:
    n = len(short)
    return len(long) > n and any(long[i : i + n] == short for i in range(len(long) - n + 1))


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------

def extract_keywords(
    job_description: str, top_n: int = DEFAULT_TOP_N, max_ngram: int = MAX_NGRAM
) -> List[Dict]:
    """Extract the most important keywords (1-3 word phrases) of a job description.

    Returns a list of dicts, best first::

        {"keyword": "REST APIs", "ngram_size": 2, "count": 3,
         "score": 9.0, "is_skill": True, "lemmas": ["rest", "api"]}

    Skill keywords use their canonical name; other keywords are shown as
    written in the text (lowercase). Empty text gives an empty list.
    """
    _require_text(job_description, "job_description")
    if top_n < 1:
        raise ValueError("top_n must be at least 1")

    skill_words = _skill_vocabulary()
    chunks = _build_chunks(job_description, skill_words)
    counts, surface = _ngram_counts(chunks)
    technical_words = _technical_looking_words(job_description)

    skills: Dict[str, Dict] = {}   # canonical skill -> record (merged)
    others: Dict[Tuple[str, ...], Dict] = {}
    wrappers: List[Tuple[Tuple[str, ...], int]] = []

    for key, count in counts.items():
        n = len(key)
        if n > max_ngram:
            continue
        text = surface[key]
        if n == 1 and len(text) < 2:
            continue  # single letters (C, R) are handled by skill extraction

        skill = skill_for_term(text)
        if skill:
            record = skills.setdefault(
                skill,
                {"keyword": skill, "ngram_size": n, "count": 0, "score": 0.0,
                 "is_skill": True, "lemmas": list(key), "_keys": []},
            )
            record["count"] += count
            record["_keys"].append(key)
            continue

        if n == 1 and key[0] in LOW_VALUE_UNIGRAMS:
            continue
        if " ".join(key) in GENERIC_PHRASES:
            continue

        # Tokens covered by a skill inside this phrase (e.g. "rest apis" in
        # "integrate rest apis") do not make it technical: the skill is
        # already reported on its own.
        tokens = text.split()
        covered: Set[int] = set()
        for i in range(n):
            for j in range(i + 1, n + 1):
                if skill_for_term(" ".join(tokens[i:j])):
                    covered.update(range(i, j))
        technical = any(
            i not in covered and (tok in technical_words or _SPECIAL_TOKEN_RE.search(tok))
            for i, tok in enumerate(tokens)
        )
        if covered and not technical:
            # Wraps a skill in other words ("python developer"): not reported
            # itself, but it still hides shorter phrases inside it.
            wrappers.append((key, count))
            continue
        min_count = MIN_COUNT_UNIGRAM if n == 1 else MIN_COUNT_PHRASE
        if not (technical or count >= min_count):
            continue
        others[key] = {
            "keyword": text, "ngram_size": n, "count": count, "score": 0.0,
            "is_skill": False, "lemmas": list(key), "_technical": technical,
        }

    # Drop phrases that only ever occur inside a longer kept phrase.
    kept = [(key, counts[key]) for key in others] + wrappers
    for record in skills.values():
        kept += [(key, record["count"]) for key in record["_keys"]]
    for key in list(others):
        if any(_is_contained(key, other) and other_count >= counts[key] for other, other_count in kept):
            del others[key]

    for record in skills.values():
        record.pop("_keys")
        record["score"] = round(record["count"] * 3.0, 2)
    for record in others.values():
        weight = 2.0 if record.pop("_technical") else 1.0
        record["score"] = round(record["count"] * weight, 2)

    ranked = sorted(
        [*skills.values(), *others.values()],
        key=lambda r: (-r["score"], -r["ngram_size"], r["keyword"]),
    )
    return ranked[:top_n]


def match_keywords(keywords: List[Dict], resume_text: str) -> Tuple[List[str], List[str]]:
    """Split ``keywords`` (output of ``extract_keywords``) into those present
    in the resume and those missing. Returns ``(present, missing)`` as lists
    of keyword strings in ranking order."""
    _require_text(resume_text, "resume_text")
    resume_skills = set(extract_skills(resume_text))
    resume_ngrams, _ = _ngram_counts(_build_chunks(resume_text, _skill_vocabulary()))

    present: List[str] = []
    missing: List[str] = []
    for record in keywords:
        if record["is_skill"]:
            found = record["keyword"] in resume_skills or tuple(record["lemmas"]) in resume_ngrams
        else:
            found = tuple(record["lemmas"]) in resume_ngrams
        (present if found else missing).append(record["keyword"])
    return present, missing


def analyze_keywords(
    resume_text: str, job_description: str, top_n: int = DEFAULT_TOP_N
) -> Dict:
    """Extract the JD's keywords and check them against the resume.

    Returns ``{"keywords": [...], "present": [...], "missing": [...],
    "coverage": percent or None}``.
    """
    _require_text(resume_text, "resume_text")
    keywords = extract_keywords(job_description, top_n)
    present, missing = match_keywords(keywords, resume_text)
    coverage = round(len(present) / len(keywords) * 100, 2) if keywords else None
    return {"keywords": keywords, "present": present, "missing": missing, "coverage": coverage}
