"""Technical skill extraction and comparison.

Purpose
-------
Find which technical skills a resume or job description mentions, and compare
the two (matched skills, missing skills, category-wise analysis).

Approach
--------
* ``SKILL_DICTIONARY`` maps ``category -> canonical skill -> [extra synonyms]``.
  The canonical name is always matched too, so only synonyms need listing.
  To support new fields (e.g. non-technical jobs) add categories/skills with
  ``register_skill`` or by editing the dictionary - no other code changes.
* Every alias is compiled into a regular expression that is
  - case-insensitive (``PYTHON``, ``python``, ``Python``),
  - boundary-aware, so ``Java`` does not match ``JavaScript``, ``C`` does not
    match ``Cloud`` / ``C++`` / ``C#`` / ``C-level`` / ``R&D``, and ``JS`` does
    not match inside ``Node.js``,
  - tolerant of spacing/hyphen variants (``spring boot``, ``Spring-Boot``,
    ``springboot``), and of a plural ``s`` (``REST API`` / ``REST APIs``).
* A few aliases are matched case-sensitively (``C``, ``R``, ``OS``, ...) because
  their lowercase form is an ordinary word, and a few common English words
  (``react``, ``excel``) carry a "guard" so ``react to change`` or
  ``excel in a team`` are not read as skills.

Known limitations
-----------------
* Matching is dictionary based: a skill that is not in the dictionary is not
  found (add it with ``register_skill``).
* Plain ``Express`` (without ``.js``) is deliberately not matched because it is
  also an everyday verb; ``Express.js`` / ``ExpressJS`` are.
* An uppercase single ``C`` is matched as the language wherever it stands alone,
  so something like "Vitamin C" would be a false match.
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Dict, Iterable, List, Optional, Tuple

# --------------------------------------------------------------------------
# Skill dictionary: category -> canonical skill -> extra synonyms/aliases
# --------------------------------------------------------------------------

SKILL_DICTIONARY: Dict[str, Dict[str, List[str]]] = {
    "Programming Languages": {
        "Python": ["python3"],
        "Java": [],
        "C": ["C"],
        "C++": ["cpp", "c plus plus"],
        "C#": ["csharp", "c sharp"],
        "JavaScript": ["js", "ecmascript", "es6"],
        "TypeScript": [],
        "R": ["R"],
    },
    "Frontend": {
        "HTML": ["html5"],
        "CSS": ["css3"],
        "React": ["react.js", "react js"],
        "Angular": ["angular.js", "angular js"],
        "Vue.js": ["vue", "vue js"],
        "Redux": [],
        "Bootstrap": [],
        "Tailwind CSS": ["tailwind"],
        "Responsive Design": ["responsive web design", "responsive layout"],
    },
    "Backend": {
        "Flask": [],
        "Django": [],
        "FastAPI": [],
        "Spring Boot": [],
        "Hibernate": [],
        "Node.js": ["node js"],
        "Express.js": ["express js"],
        "REST APIs": ["rest api", "restful", "restful api", "REST"],
        "Microservices": ["microservice architecture"],
        ".NET": ["dotnet", "asp.net", "asp.net core", ".net core"],
    },
    "Databases": {
        "SQL": [],
        "MySQL": [],
        "PostgreSQL": ["postgres"],
        "MongoDB": ["mongo db", "mongo"],
        "SQLite": [],
        "SQL Server": ["mssql", "ms sql", "microsoft sql server"],
        "Redis": [],
        "NoSQL": ["no sql"],
    },
    "Data Science and ML": {
        "NumPy": [],
        "Pandas": [],
        "Scikit-learn": ["sklearn", "scikit learn"],
        "TensorFlow": [],
        "PyTorch": [],
        "Keras": [],
        "Matplotlib": [],
        "Seaborn": [],
        "Machine Learning": ["ML"],
        "Deep Learning": ["neural network"],
        "NLP": ["natural language processing"],
        "Computer Vision": [],
        "OpenCV": [],
        "Statistics": ["statistical analysis", "statistical modeling", "statistical modelling"],
        "Data Visualization": ["data visualisation", "data viz"],
        "Feature Engineering": [],
        "Jupyter": ["jupyter notebook"],
    },
    "Data Analysis and BI": {
        "Excel": ["ms excel", "microsoft excel", "advanced excel"],
        "Tableau": [],
        "Power BI": ["powerbi"],
        "ETL": [],
        "Data Analysis": ["data analytics"],
        "Data Cleaning": ["data cleansing", "data wrangling"],
        "A/B Testing": ["ab testing", "split testing"],
    },
    "Cloud and DevOps": {
        "AWS": ["amazon web services"],
        "Azure": ["microsoft azure"],
        "GCP": ["google cloud", "google cloud platform"],
        "Docker": [],
        "Kubernetes": ["k8s"],
        "Git": [],
        "GitHub": [],
        "GitLab": [],
        "CI/CD": ["ci-cd", "continuous integration", "continuous delivery"],
        "Jenkins": [],
        "Terraform": [],
        "Linux": [],
    },
    "Core CS": {
        "Data Structures": ["data structure", "DSA"],
        "Algorithms": ["DSA"],
        "OOP": ["oops", "object oriented"],
        "DBMS": ["database management system"],
        "Operating Systems": ["operating system", "OS"],
        "Computer Networks": ["computer network", "computer networking", "CN"],
    },
    "Testing and Practices": {
        "Unit Testing": ["unit tests"],
        "pytest": [],
        "JUnit": [],
        "Jest": [],
        "Agile": [],
        "Scrum": [],
    },
}

# Aliases matched case-sensitively, exactly as written in the dictionary.
# Their lowercase forms are ordinary words ("c", "r", "os", "rest", "ml").
CASE_SENSITIVE_ALIASES = frozenset({"C", "R", "OS", "CN", "ML", "REST"})

# Everyday English words that are also skill names: the skill is NOT matched
# when the word is followed by one of these (e.g. "react to change",
# "excel in a team"). Key = lowercase alias, value = regex lookahead.
AMBIGUOUS_ALIAS_GUARDS = {
    "react": r"(?!\s+(?:to|quickly|fast|well|swiftly|promptly)\b)",
    "excel": r"(?!\s+(?:in|at|as|under)\b)",
}

# --------------------------------------------------------------------------
# Regex building
# --------------------------------------------------------------------------

# Not preceded by a letter/digit/underscore/dot (so "JS" is not found in "Node.js").
_LOOKBEHIND = r"(?<![A-Za-z0-9_.])"
# Not followed by a letter/underscore, "++" or "#" (so "C" is not found in "C++",
# "Java" not in "JavaScript"). Digits are allowed: "Python3", "HTML5", "Java8".
_LOOKAHEAD = r"(?![A-Za-z_]|\+\+|#)"
# Stricter rules for one-letter aliases such as "C" and "R".
_STRICT_LOOKBEHIND = r"(?<![A-Za-z0-9_.&\-])"
_STRICT_LOOKAHEAD = r"(?![A-Za-z0-9_&+#]|-\w|\.\w)"


def _alias_pattern(alias: str) -> "re.Pattern[str]":
    """Compile one alias into a boundary-aware regular expression."""
    parts = [re.escape(p) for p in re.split(r"[\s\-]+", alias.strip()) if p]
    body = r"[\s\-]*".join(parts)  # "spring boot" also matches "spring-boot"
    flags = 0 if alias in CASE_SENSITIVE_ALIASES else re.IGNORECASE

    if len(alias) == 1:  # "C", "R"
        pattern = _STRICT_LOOKBEHIND + body + _STRICT_LOOKAHEAD
    else:
        plural = r"s?" if alias[-1].isalpha() and alias not in CASE_SENSITIVE_ALIASES else ""
        guard = AMBIGUOUS_ALIAS_GUARDS.get(alias.lower(), "")
        pattern = _LOOKBEHIND + body + plural + _LOOKAHEAD + guard
    return re.compile(pattern, flags)


@lru_cache(maxsize=1)
def _skill_index() -> Tuple[Tuple[str, str, Tuple["re.Pattern[str]", ...]], ...]:
    """Compile the dictionary once: ((category, skill, (patterns...)), ...)."""
    index = []
    for category, skills in SKILL_DICTIONARY.items():
        for skill, synonyms in skills.items():
            aliases = list(dict.fromkeys([skill, *synonyms]))
            index.append((category, skill, tuple(_alias_pattern(a) for a in aliases)))
    return tuple(index)


def _reset_cache() -> None:
    _skill_index.cache_clear()
    skill_for_term.cache_clear()


# --------------------------------------------------------------------------
# Extending the dictionary
# --------------------------------------------------------------------------

def register_skill(category: str, skill: str, aliases: Iterable[str] = ()) -> None:
    """Add (or extend) a skill. Creates the category if it does not exist."""
    if not category.strip() or not skill.strip():
        raise ValueError("category and skill must be non-empty")
    entry = SKILL_DICTIONARY.setdefault(category, {}).setdefault(skill, [])
    entry.extend(a for a in aliases if a not in entry)
    _reset_cache()


def unregister_skill(category: str, skill: str) -> None:
    """Remove a skill (and the category if it becomes empty). Missing names are ignored."""
    SKILL_DICTIONARY.get(category, {}).pop(skill, None)
    if category in SKILL_DICTIONARY and not SKILL_DICTIONARY[category]:
        del SKILL_DICTIONARY[category]
    _reset_cache()


# --------------------------------------------------------------------------
# Extraction
# --------------------------------------------------------------------------

def _require_text(text) -> str:
    if not isinstance(text, str):
        raise TypeError(f"text must be a string, got {type(text).__name__}")
    return text


def extract_skills(text: str) -> List[str]:
    """Return the canonical names of all skills found in ``text``.

    The result follows dictionary order (category by category) and has no
    duplicates. Empty text gives an empty list.
    """
    _require_text(text)
    if not text.strip():
        return []
    return [
        skill
        for _, skill, patterns in _skill_index()
        if any(p.search(text) for p in patterns)
    ]


def extract_skills_by_category(text: str) -> Dict[str, List[str]]:
    """Return ``{category: [skills]}`` for the skills found in ``text``
    (categories with no skills are omitted)."""
    found = set(extract_skills(text))
    result: Dict[str, List[str]] = {}
    for category, skill, _ in _skill_index():
        if skill in found:
            result.setdefault(category, []).append(skill)
    return result


def get_skill_category(skill: str) -> Optional[str]:
    """Return the category of a canonical skill name (``None`` if unknown)."""
    for category, skills in SKILL_DICTIONARY.items():
        if skill in skills:
            return category
    return None


@lru_cache(maxsize=20000)
def skill_for_term(term: str) -> Optional[str]:
    """If the WHOLE ``term`` is a skill name or synonym, return its canonical
    name, else ``None`` (``"rest apis"`` -> ``"REST APIs"``,
    ``"python developer"`` -> ``None``). Used by keyword extraction."""
    term = term.strip()
    for _, skill, patterns in _skill_index():
        if any(p.fullmatch(term) for p in patterns):
            return skill
    return None


# --------------------------------------------------------------------------
# Comparison
# --------------------------------------------------------------------------

def compare_skills(resume_skills: Iterable[str], jd_skills: Iterable[str]) -> Dict[str, List[str]]:
    """Compare two skill lists.

    Returns ``matched`` (required and present), ``missing`` (required but
    absent) and ``extra`` (in the resume only). Order follows the inputs.
    """
    resume_list, jd_list = list(resume_skills), list(jd_skills)
    resume_set, jd_set = set(resume_list), set(jd_list)
    return {
        "matched": [s for s in jd_list if s in resume_set],
        "missing": [s for s in jd_list if s not in resume_set],
        "extra": [s for s in resume_list if s not in jd_set],
    }


def analyze_skills(resume_text: str, job_description: str) -> Dict:
    """Full skill analysis of a resume against a job description.

    Returns a dict with:
      resume_skills, jd_skills, matched_skills, missing_skills, extra_skills,
      skill_coverage  - % of the JD's skills found in the resume
                        (``None`` when the JD mentions no known skill),
      by_category     - per category: required / matched / missing / coverage.
    """
    resume_skills = extract_skills(resume_text)
    jd_skills = extract_skills(job_description)
    comparison = compare_skills(resume_skills, jd_skills)

    coverage = (
        round(len(comparison["matched"]) / len(jd_skills) * 100, 2) if jd_skills else None
    )

    by_category: Dict[str, Dict] = {}
    for category, skills in extract_skills_by_category(job_description).items():
        matched = [s for s in skills if s in comparison["matched"]]
        by_category[category] = {
            "required": len(skills),
            "matched": matched,
            "missing": [s for s in skills if s not in matched],
            "coverage": round(len(matched) / len(skills) * 100, 2),
        }

    return {
        "resume_skills": resume_skills,
        "jd_skills": jd_skills,
        "matched_skills": comparison["matched"],
        "missing_skills": comparison["missing"],
        "extra_skills": comparison["extra"],
        "skill_coverage": coverage,
        "by_category": by_category,
    }
