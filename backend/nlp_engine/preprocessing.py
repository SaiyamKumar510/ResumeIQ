"""Text preprocessing for the ResumeIQ NLP engine.

Purpose
-------
Turn raw resume / job-description text into clean, comparable tokens
WITHOUT destroying technical terms such as ``C++``, ``C#``, ``.NET``,
``Node.js``, ``CI/CD`` or ``scikit-learn``.

Pipeline (each step is a separate, reusable function)
-----------------------------------------------------
1. ``normalize_text``     - unicode clean-up, lowercase, remove URLs/e-mails,
                            unify a few common spelling variants.
2. ``tokenize``           - regex tokenizer that keeps technical tokens whole.
3. ``remove_stopwords``   - NLTK English stop-words (+ a few extras).
4. ``lemmatize_tokens``   - WordNet lemmatizer that never touches technical
                            tokens (``pandas`` must not become ``panda``).
5. ``preprocess_tokens`` / ``preprocess_text`` - the whole pipeline.

``split_into_segments`` is a helper used by keyword extraction so that
phrases (n-grams) are never built across commas, bullets or line breaks.

NLTK data (``stopwords`` and ``wordnet``) is downloaded automatically the
first time it is needed.
"""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache
from typing import FrozenSet, List

import nltk
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer

# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------

# Extra stop-words that are noise in resumes / job descriptions.
EXTRA_STOP_WORDS = frozenset(
    {"e.g", "i.e", "etc", "eg", "ie", "vs", "versus", "also", "per", "via"}
)

# Single-letter tokens are normally noise, but C and R are programming languages.
KEEP_SINGLE_LETTER_TOKENS = frozenset({"c", "r"})

# Technical words that WordNet would wrongly change (found by testing the
# lemmatizer: pandas->panda, css->cs, ios->io, sas->sa, gis->gi, keras->kera,
# sass->sas, statistics->statistic).
NO_LEMMATIZE = frozenset(
    {"pandas", "css", "ios", "sas", "gis", "keras", "sass", "statistics", "analytics"}
)

# Spelling variants unified BEFORE tokenization so the same technology written
# in different ways produces the same token. (pattern, replacement)
_TERM_VARIANTS = [
    (re.compile(r"\bnode[\s\-]?\.?js\b"), "node.js"),
    (re.compile(r"\breact[\s\-]?\.?js\b"), "react"),
    (re.compile(r"\bvue[\s\-]?\.?js\b"), "vue"),
    (re.compile(r"\bangular[\s\-]?\.?js\b"), "angular"),
    (re.compile(r"\bexpress[\s\-]?\.?js\b"), "express.js"),
    (re.compile(r"\bscikit[\s\-]?learn\b|\bsklearn\b"), "scikit-learn"),
    (re.compile(r"\bpostgres(?:ql)?\b"), "postgresql"),
    (re.compile(r"\bc[\s\-]?sharp\b|\bcsharp\b"), "c#"),
    (re.compile(r"\bci\s*[-/\\]\s*cd\b"), "ci/cd"),
    (re.compile(r"\br\s*&\s*d\b"), "research development"),
    (re.compile(r"\bc-(?=level\b|suite\b)"), "c"),  # "C-level" is not the C language
]

_URL_RE = re.compile(r"https?://\S+|www\.\S+")
_EMAIL_RE = re.compile(r"\S+@\S+\.\S+")
_HORIZONTAL_SPACE_RE = re.compile(r"[ \t\r\f\v]+")
_BLANK_LINES_RE = re.compile(r"\n\s*\n+")

# Technical tokens that must stay in one piece. The first alternative handles
# the special-character terms; the second is a general word token that may
# contain dots (node.js, asp.net) but treats hyphens/slashes as separators.
_TOKEN_RE = re.compile(
    r"(?<![a-z0-9])(?:c\+\+|c#|f#|ci/cd|scikit-learn|\.net)(?![a-z#+])"
    r"|[a-z0-9]+(?:\.[a-z0-9]+)*"
)
_PURE_NUMBER_RE = re.compile(r"^[\d.]+$")
_TECHNICAL_CHARS_RE = re.compile(r"[^a-z]")  # digits, '.', '+', '#', '/', '-'

# Boundaries used when splitting text into phrase-safe segments.
# A "/" is a boundary except inside "ci/cd".
_SEGMENT_SPLIT_RE = re.compile(
    r"[\n,;:()\[\]{}|•·●▪◦►→!?\"“”]"
    r"|\.(?=\s|$)"
    r"|\s[-–—]\s"
    r"|(?<!ci)/(?!cd)"
)


# --------------------------------------------------------------------------
# NLTK resource loading (lazy, cached)
# --------------------------------------------------------------------------

def _load_nltk(package: str, loader):
    """Run ``loader``; if the NLTK data is missing, download it once and retry."""
    try:
        return loader()
    except LookupError:
        if not nltk.download(package, quiet=True):
            raise RuntimeError(
                f"NLTK data '{package}' is missing and could not be downloaded. "
                f"Run: python -m nltk.downloader {package}"
            )
        return loader()


@lru_cache(maxsize=1)
def get_stop_words() -> FrozenSet[str]:
    """Return the set of stop-words (NLTK English + a few extras)."""
    words = _load_nltk("stopwords", lambda: stopwords.words("english"))
    return frozenset(words) | EXTRA_STOP_WORDS


@lru_cache(maxsize=1)
def _get_lemmatizer() -> WordNetLemmatizer:
    lemmatizer = WordNetLemmatizer()
    _load_nltk("wordnet", lambda: lemmatizer.lemmatize("tests"))  # forces data load
    return lemmatizer


# --------------------------------------------------------------------------
# Pipeline steps
# --------------------------------------------------------------------------

def _require_text(text) -> str:
    if not isinstance(text, str):
        raise TypeError(f"text must be a string, got {type(text).__name__}")
    return text


def normalize_text(text: str) -> str:
    """Normalize raw text.

    Steps: unicode NFKC, lowercase, drop URLs and e-mail addresses, unify
    spelling variants of common technologies (``NodeJS`` -> ``node.js``),
    collapse spaces. Line breaks are kept because they mark phrase boundaries.
    """
    text = unicodedata.normalize("NFKC", _require_text(text)).lower()
    text = _URL_RE.sub(" ", text)
    text = _EMAIL_RE.sub(" ", text)
    for pattern, replacement in _TERM_VARIANTS:
        text = pattern.sub(replacement, text)
    text = _HORIZONTAL_SPACE_RE.sub(" ", text)
    text = _BLANK_LINES_RE.sub("\n", text)
    return text.strip()


def tokenize(text: str) -> List[str]:
    """Split text into lowercase tokens, keeping technical terms whole.

    ``"C++, C#, .NET and Node.js with CI/CD"`` ->
    ``['c++', 'c#', '.net', 'and', 'node.js', 'with', 'ci/cd']``.
    Pure numbers and single letters are dropped (except ``c`` and ``r``).
    """
    tokens = []
    for token in _TOKEN_RE.findall(normalize_text(text)):
        if _PURE_NUMBER_RE.match(token):
            continue
        if len(token) == 1 and token not in KEEP_SINGLE_LETTER_TOKENS:
            continue
        tokens.append(token)
    return tokens


def is_stop_word(token: str) -> bool:
    """True if ``token`` is a stop-word."""
    return token in get_stop_words()


def remove_stopwords(tokens: List[str]) -> List[str]:
    """Remove stop-words from a token list."""
    stop_words = get_stop_words()
    return [t for t in tokens if t not in stop_words]


@lru_cache(maxsize=50000)
def lemmatize_token(token: str, include_verbs: bool = True) -> str:
    """Lemmatize one token.

    Technical tokens (anything with digits or symbols, plus the words in
    ``NO_LEMMATIZE``) are returned unchanged. With ``include_verbs`` the verb
    form is tried first (``developed`` -> ``develop``), otherwise only the
    noun form is used (``databases`` -> ``database``, ``learning`` stays).
    """
    if token in NO_LEMMATIZE or _TECHNICAL_CHARS_RE.search(token):
        return token
    lemmatizer = _get_lemmatizer()
    if include_verbs:
        verb_form = lemmatizer.lemmatize(token, pos="v")
        if verb_form != token:
            return verb_form
    return lemmatizer.lemmatize(token, pos="n")


def lemmatize_tokens(tokens: List[str], include_verbs: bool = True) -> List[str]:
    """Lemmatize a list of tokens (see ``lemmatize_token``)."""
    return [lemmatize_token(t, include_verbs) for t in tokens]


def preprocess_tokens(text: str, lemmatize: bool = True, include_verbs: bool = True) -> List[str]:
    """Full pipeline returning a token list: normalize -> tokenize ->
    remove stop-words -> lemmatize (-> remove stop-words that appear after
    lemmatization, e.g. ``having`` -> ``have``)."""
    tokens = remove_stopwords(tokenize(text))
    if lemmatize:
        tokens = remove_stopwords(lemmatize_tokens(tokens, include_verbs))
    return tokens


def preprocess_text(text: str, lemmatize: bool = True, include_verbs: bool = True) -> str:
    """Full pipeline returning one cleaned, space-separated string.

    This is the text that goes into the TF-IDF vectorizer.
    """
    return " ".join(preprocess_tokens(text, lemmatize, include_verbs))


def split_into_segments(text: str) -> List[str]:
    """Split text at line breaks, commas, bullets, brackets, sentence ends and
    slashes so phrases are never built across them.

    ``"Python, Django\\nExperience with REST APIs."`` ->
    ``['python', 'django', 'experience with rest apis']``.
    """
    segments = _SEGMENT_SPLIT_RE.split(normalize_text(text))
    return [s.strip() for s in segments if s and s.strip()]
