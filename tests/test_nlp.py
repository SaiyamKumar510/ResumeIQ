"""Tests for the ResumeIQ NLP engine.

Run from the project root (the ResumeIQ folder):

    python -m unittest tests.test_nlp -v

(``python -m pytest tests/test_nlp.py`` also works if pytest is installed.)

The tests use the synthetic sample resume / job-description pairs in
``datasets/sample_data`` plus longer inline texts that contain special
technical terms such as C++, C#, .NET, Node.js and CI/CD.
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.nlp_engine import (  # noqa: E402
    keyword_extraction,
    preprocessing,
    scoring,
    similarity,
    skill_extraction,
)

SAMPLE_DIR = ROOT / "datasets" / "sample_data"
ROLES = [
    "python_developer",
    "java_backend_developer",
    "frontend_developer",
    "full_stack_developer",
    "data_analyst",
    "machine_learning_engineer",
]

# Skills each sample JD requires that its sample resume does NOT mention.
# The gaps were written into the synthetic data on purpose, so these are known answers.
EXPECTED_MISSING = {
    "python_developer": {"PostgreSQL", "Redis", "AWS", "CI/CD"},
    "java_backend_developer": {
        "Microservices", "PostgreSQL", "AWS", "Kubernetes", "CI/CD", "Jenkins", "Unit Testing",
    },
    "frontend_developer": {"TypeScript", "Redux", "Tailwind CSS", "Jest"},
    "full_stack_developer": {"TypeScript", "AWS", "CI/CD"},
    "data_analyst": {"PostgreSQL", "Tableau", "ETL", "A/B Testing"},
    "machine_learning_engineer": {"PyTorch", "AWS", "Docker", "Kubernetes"},
}


def load(role: str, kind: str) -> str:
    """kind is 'resume' or 'jd'."""
    return (SAMPLE_DIR / f"{role}_{kind}.txt").read_text(encoding="utf-8")


# A realistic resume / JD pair full of special-character technical terms.
DOTNET_RESUME = """Arjun Rao | arjun.rao@example.com | https://linkedin.com/in/arjun-example
Software Engineer with 4 years of experience in C#/.NET and C++.
Skills: C#, .NET Core, ASP.NET, C++, C, SQL Server, Node.js, JavaScript, Git, CI/CD, Docker
- Built ASP.NET Core Web APIs and migrated legacy C++ modules to C#.
- Set up CI/CD pipelines with Jenkins and Docker; worked closely with C-level stakeholders.
- Collaborated with the R&D team on a Node.js proof of concept."""

DOTNET_JD = """Backend Engineer (.NET)
Requirements: strong C# and .NET skills, experience with ASP.NET, SQL Server and CI/CD.
Knowledge of C++ is a plus. Familiarity with Node.js and Docker preferred."""


# --------------------------------------------------------------------------
# 1. Preprocessing
# --------------------------------------------------------------------------
class TestPreprocessing(unittest.TestCase):
    def test_special_technical_terms_are_preserved(self):
        tokens = preprocessing.tokenize(DOTNET_RESUME)
        for term in ["c#", ".net", "c++", "asp.net", "node.js", "ci/cd"]:
            with self.subTest(term=term):
                self.assertIn(term, tokens)

    def test_term_inside_sentence_with_punctuation(self):
        tokens = preprocessing.tokenize("Experienced in C++, C#, .NET, Node.js and CI/CD.")
        self.assertEqual(tokens, ["experienced", "in", "c++", "c#", ".net", "node.js", "and", "ci/cd"])

    def test_c_slash_cpp_gives_both_tokens(self):
        self.assertEqual(preprocessing.tokenize("C/C++ developer"), ["c", "c++", "developer"])

    def test_lowercase_conversion(self):
        self.assertEqual(preprocessing.normalize_text("PYTHON Developer"), "python developer")

    def test_urls_and_emails_removed(self):
        cleaned = preprocessing.normalize_text("Mail a.b@example.com or see https://github.com/x/y and www.site.org")
        self.assertNotIn("@", cleaned)
        self.assertNotIn("github", cleaned)
        self.assertNotIn("site.org", cleaned)

    def test_spelling_variants_are_unified(self):
        for raw, expected in [
            ("NodeJS", "node.js"),
            ("Node JS", "node.js"),
            ("ReactJS", "react"),
            ("Postgres", "postgresql"),
            ("sklearn", "scikit-learn"),
            ("Scikit Learn", "scikit-learn"),
            ("C Sharp", "c#"),
            ("CI-CD", "ci/cd"),
        ]:
            with self.subTest(raw=raw):
                self.assertEqual(preprocessing.normalize_text(raw), expected)

    def test_c_level_is_not_the_c_language(self):
        self.assertNotIn("c", preprocessing.tokenize("worked with C-level executives"))

    def test_numbers_and_single_letters_are_dropped_but_c_and_r_kept(self):
        tokens = preprocessing.tokenize("5 years of C and R, plus 3.9 x y")
        self.assertIn("c", tokens)
        self.assertIn("r", tokens)
        for junk in ["5", "3.9", "x", "y"]:
            self.assertNotIn(junk, tokens)

    def test_stopwords_removed(self):
        tokens = preprocessing.remove_stopwords(["the", "python", "and", "the", "django", "with"])
        self.assertEqual(tokens, ["python", "django"])

    def test_lemmatization_of_verbs_and_nouns(self):
        self.assertEqual(preprocessing.lemmatize_token("developed"), "develop")
        self.assertEqual(preprocessing.lemmatize_token("databases"), "database")
        self.assertEqual(preprocessing.lemmatize_token("learning", include_verbs=False), "learning")

    def test_lemmatization_does_not_damage_technical_terms(self):
        for term in ["pandas", "css", "ios", "keras", "statistics", "c++", "node.js", "html5", "ci/cd"]:
            with self.subTest(term=term):
                self.assertEqual(preprocessing.lemmatize_token(term), term)

    def test_full_pipeline_on_realistic_resume(self):
        cleaned = preprocessing.preprocess_text(load("python_developer", "resume"))
        for kept in ["python", "django", "flask", "pytest", "docker", "mysql"]:
            with self.subTest(kept=kept):
                self.assertIn(kept, cleaned.split())
        for removed in ["the", "and", "with", "of"]:
            self.assertNotIn(removed, cleaned.split())
        self.assertNotIn("rohan.verma@example.com", cleaned)

    def test_split_into_segments_breaks_at_commas_lines_and_slashes(self):
        segments = preprocessing.split_into_segments("Python, Django\nExperience with REST APIs. HTML/CSS and CI/CD")
        self.assertEqual(segments, ["python", "django", "experience with rest apis", "html", "css and ci/cd"])

    def test_empty_and_symbol_only_input(self):
        for text in ["", "   ", "\n\t", "!!! ### @@@", "12345"]:
            with self.subTest(text=text):
                self.assertEqual(preprocessing.preprocess_text(text), "")
                self.assertEqual(preprocessing.tokenize(text), [])

    def test_invalid_input_raises_type_error(self):
        for bad in [None, 42, 3.5, ["python"], b"python"]:
            with self.subTest(bad=bad):
                with self.assertRaises(TypeError):
                    preprocessing.preprocess_text(bad)
                with self.assertRaises(TypeError):
                    preprocessing.tokenize(bad)


# --------------------------------------------------------------------------
# 2. Similarity
# --------------------------------------------------------------------------
class TestSimilarity(unittest.TestCase):
    def test_identical_texts_score_100(self):
        text = load("python_developer", "jd")
        self.assertEqual(similarity.calculate_similarity(text, text), 100.0)

    def test_related_pair_scores_higher_than_unrelated_pair(self):
        jd = load("python_developer", "jd")
        related = similarity.calculate_similarity(load("python_developer", "resume"), jd)
        unrelated = similarity.calculate_similarity(load("data_analyst", "resume"), jd)
        self.assertGreater(related, unrelated)

    def test_completely_unrelated_text_scores_low(self):
        retail = "Retail store manager handling cashiers, inventory counts, customer complaints and weekend rosters."
        score = similarity.calculate_similarity(retail, load("machine_learning_engineer", "jd"))
        self.assertLess(score, 10)

    def test_result_is_a_percentage_with_two_decimals(self):
        for role in ROLES:
            with self.subTest(role=role):
                score = similarity.calculate_similarity(load(role, "resume"), load(role, "jd"))
                self.assertIsInstance(score, float)
                self.assertGreaterEqual(score, 0.0)
                self.assertLessEqual(score, 100.0)
                self.assertEqual(score, round(score, 2))

    def test_similarity_is_symmetric(self):
        a, b = load("frontend_developer", "resume"), load("full_stack_developer", "jd")
        self.assertEqual(similarity.calculate_similarity(a, b), similarity.calculate_similarity(b, a))

    def test_special_character_terms_are_kept_distinct(self):
        self.assertEqual(similarity.calculate_similarity("C++ developer", "C++ developer"), 100.0)
        self.assertEqual(similarity.calculate_similarity("C++", "C#"), 0.0)

    def test_empty_or_meaningless_text_gives_zero(self):
        jd = load("python_developer", "jd")
        for text in ["", "   ", "the and of with", "!!! ???"]:
            with self.subTest(text=text):
                self.assertEqual(similarity.calculate_similarity(text, jd), 0.0)
                self.assertEqual(similarity.calculate_similarity(jd, text), 0.0)

    def test_invalid_input_raises_type_error(self):
        with self.assertRaises(TypeError):
            similarity.calculate_similarity(None, "python")
        with self.assertRaises(TypeError):
            similarity.calculate_similarity("python", 123)

    def test_build_tfidf_vectors_is_reusable_and_keeps_technical_tokens(self):
        vectorizer, matrix = similarity.build_tfidf_vectors([DOTNET_RESUME, DOTNET_JD])
        self.assertEqual(matrix.shape[0], 2)
        for term in ["c++", "c#", ".net", "node.js", "ci/cd"]:
            with self.subTest(term=term):
                self.assertIn(term, vectorizer.vocabulary_)
        score = similarity.cosine_similarity_percent(matrix[0], matrix[1])
        self.assertTrue(0 < score <= 100)

    def test_optional_reference_corpus(self):
        corpus = [load(role, "jd") for role in ROLES]
        score = similarity.calculate_similarity(
            load("java_backend_developer", "resume"), load("java_backend_developer", "jd"), corpus=corpus
        )
        self.assertTrue(0 < score <= 100)


# --------------------------------------------------------------------------
# 4. Skill extraction (tested before keywords because keywords build on it)
# --------------------------------------------------------------------------
class TestSkillExtraction(unittest.TestCase):
    def test_case_insensitive_matching(self):
        for text in ["PYTHON", "python", "Python", "pYtHoN"]:
            with self.subTest(text=text):
                self.assertEqual(skill_extraction.extract_skills(text), ["Python"])

    def test_synonym_aware_matching(self):
        cases = {
            "ReactJS": "React",
            "NodeJS": "Node.js",
            "ExpressJS": "Express.js",
            "Postgres": "PostgreSQL",
            "mongo db": "MongoDB",
            "sklearn": "Scikit-learn",
            "k8s": "Kubernetes",
            "Amazon Web Services": "AWS",
            "Google Cloud Platform": "GCP",
            "JS": "JavaScript",
            "Python3": "Python",
            "HTML5": "HTML",
            "CSS3": "CSS",
            "springboot": "Spring Boot",
            "Spring-Boot": "Spring Boot",
            "RESTful services": "REST APIs",
            "REST API": "REST APIs",
            "natural language processing": "NLP",
            "object-oriented programming": "OOP",
            "database management systems": "DBMS",
            "powerbi": "Power BI",
            "continuous integration": "CI/CD",
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertIn(expected, skill_extraction.extract_skills(text))

    def test_single_letter_c_does_not_match_unrelated_words(self):
        text = (
            "Cloud computing with Docker and Cassandra; Computer science degree; "
            "C-level stakeholders; Vitamin supplements; R&D team; Scikit; Cache"
        )
        found = skill_extraction.extract_skills(text)
        self.assertNotIn("C", found)
        self.assertNotIn("R", found)
        self.assertEqual(found, ["Docker"])

    def test_c_c_plus_plus_and_c_sharp_are_separate_skills(self):
        self.assertEqual(skill_extraction.extract_skills("C"), ["C"])
        self.assertEqual(skill_extraction.extract_skills("C++"), ["C++"])
        self.assertEqual(skill_extraction.extract_skills("C#"), ["C#"])
        self.assertEqual(skill_extraction.extract_skills("C/C++ developer"), ["C", "C++"])
        self.assertEqual(skill_extraction.extract_skills("C, C++, C#"), ["C", "C++", "C#"])

    def test_java_is_not_matched_inside_javascript(self):
        self.assertEqual(skill_extraction.extract_skills("JavaScript"), ["JavaScript"])
        self.assertEqual(skill_extraction.extract_skills("Java"), ["Java"])

    def test_nodejs_does_not_imply_javascript(self):
        self.assertEqual(skill_extraction.extract_skills("Node.js"), ["Node.js"])

    def test_sql_not_matched_inside_mysql_or_postgresql(self):
        self.assertEqual(skill_extraction.extract_skills("MySQL"), ["MySQL"])
        self.assertEqual(skill_extraction.extract_skills("PostgreSQL"), ["PostgreSQL"])
        self.assertEqual(skill_extraction.extract_skills("SQLite"), ["SQLite"])

    def test_everyday_words_are_not_read_as_skills(self):
        text = (
            "Eager to express interest; able to react to change; will excel in a fast team; "
            "the rest of the group went to the OS of life; oops, a typo"
        )
        found = skill_extraction.extract_skills(text)
        for wrongly_found in ["Express.js", "React", "Excel", "REST APIs"]:
            self.assertNotIn(wrongly_found, found)

    def test_excel_and_react_still_match_in_skill_context(self):
        self.assertEqual(skill_extraction.extract_skills("Advanced Excel, pivot tables"), ["Excel"])
        self.assertEqual(skill_extraction.extract_skills("Frontend: React, Redux"), ["React", "Redux"])

    def test_special_character_skills_in_realistic_text(self):
        found = skill_extraction.extract_skills(DOTNET_RESUME)
        for skill in ["C#", ".NET", "C++", "C", "SQL Server", "Node.js", "JavaScript", "Git", "CI/CD", "Docker", "Jenkins"]:
            with self.subTest(skill=skill):
                self.assertIn(skill, found)

    def test_extract_skills_by_category(self):
        by_category = skill_extraction.extract_skills_by_category("Python, Django, MySQL, Docker, pytest, Agile")
        self.assertEqual(by_category["Programming Languages"], ["Python"])
        self.assertEqual(by_category["Backend"], ["Django"])
        self.assertEqual(by_category["Databases"], ["MySQL"])
        self.assertEqual(by_category["Cloud and DevOps"], ["Docker"])
        self.assertEqual(by_category["Testing and Practices"], ["pytest", "Agile"])

    def test_required_categories_exist(self):
        for category in [
            "Programming Languages", "Frontend", "Backend", "Databases",
            "Data Science and ML", "Cloud and DevOps", "Core CS",
        ]:
            self.assertIn(category, skill_extraction.SKILL_DICTIONARY)

    def test_get_skill_category(self):
        self.assertEqual(skill_extraction.get_skill_category("Docker"), "Cloud and DevOps")
        self.assertEqual(skill_extraction.get_skill_category("DBMS"), "Core CS")
        self.assertIsNone(skill_extraction.get_skill_category("Basket Weaving"))

    def test_dictionary_is_easy_to_extend(self):
        text = "Experienced in Tally and GST filing"
        self.assertEqual(skill_extraction.extract_skills(text), [])
        skill_extraction.register_skill("Accounting", "Tally", ["tally erp"])
        skill_extraction.register_skill("Accounting", "GST Filing", ["gst returns"])
        try:
            self.assertEqual(skill_extraction.extract_skills(text), ["Tally", "GST Filing"])
            self.assertEqual(skill_extraction.extract_skills("Used Tally ERP"), ["Tally"])
            self.assertEqual(skill_extraction.get_skill_category("Tally"), "Accounting")
        finally:
            skill_extraction.unregister_skill("Accounting", "Tally")
            skill_extraction.unregister_skill("Accounting", "GST Filing")
        self.assertEqual(skill_extraction.extract_skills(text), [])
        self.assertNotIn("Accounting", skill_extraction.SKILL_DICTIONARY)

    def test_empty_and_invalid_input(self):
        for text in ["", "   ", "\n"]:
            self.assertEqual(skill_extraction.extract_skills(text), [])
        for bad in [None, 5, ["Python"]]:
            with self.subTest(bad=bad):
                with self.assertRaises(TypeError):
                    skill_extraction.extract_skills(bad)

    def test_compare_skills_matched_missing_extra(self):
        result = skill_extraction.compare_skills(
            iter(["Python", "Git", "Flask"]), iter(["Python", "Django", "Git", "AWS"])
        )
        self.assertEqual(result["matched"], ["Python", "Git"])
        self.assertEqual(result["missing"], ["Django", "AWS"])
        self.assertEqual(result["extra"], ["Flask"])

    def test_matched_and_missing_skills_on_sample_pairs(self):
        for role in ROLES:
            with self.subTest(role=role):
                analysis = skill_extraction.analyze_skills(load(role, "resume"), load(role, "jd"))
                self.assertEqual(set(analysis["missing_skills"]), EXPECTED_MISSING[role])
                # matched + missing is exactly the set of JD skills, with no overlap
                self.assertEqual(
                    set(analysis["matched_skills"]) | set(analysis["missing_skills"]), set(analysis["jd_skills"])
                )
                self.assertFalse(set(analysis["matched_skills"]) & set(analysis["missing_skills"]))

    def test_category_wise_analysis(self):
        analysis = skill_extraction.analyze_skills(load("python_developer", "resume"), load("python_developer", "jd"))
        by_category = analysis["by_category"]
        self.assertEqual(by_category["Databases"]["required"], 2)  # PostgreSQL and Redis
        self.assertEqual(by_category["Databases"]["missing"], ["PostgreSQL", "Redis"])
        self.assertEqual(by_category["Databases"]["coverage"], 0.0)
        self.assertEqual(by_category["Backend"]["coverage"], 100.0)
        self.assertEqual(by_category["Cloud and DevOps"]["missing"], ["AWS", "CI/CD"])
        for category, data in by_category.items():
            with self.subTest(category=category):
                self.assertEqual(len(data["matched"]) + len(data["missing"]), data["required"])

    def test_skill_coverage_is_none_when_jd_has_no_known_skills(self):
        analysis = skill_extraction.analyze_skills("Python developer", "We need a friendly cashier for weekend shifts.")
        self.assertIsNone(analysis["skill_coverage"])
        self.assertEqual(analysis["jd_skills"], [])


# --------------------------------------------------------------------------
# 3. Keyword extraction
# --------------------------------------------------------------------------
class TestKeywordExtraction(unittest.TestCase):
    @staticmethod
    def by_keyword(records):
        return {r["keyword"]: r for r in records}

    def test_unigram_bigram_and_trigram_extraction(self):
        jd = "Python and machine learning experience. Knowledge of natural language processing. Repeated data pipelines; data pipelines."
        records = self.by_keyword(keyword_extraction.extract_keywords(jd))
        self.assertEqual(records["Python"]["ngram_size"], 1)
        self.assertEqual(records["Machine Learning"]["ngram_size"], 2)
        self.assertEqual(records["NLP"]["ngram_size"], 3)  # "natural language processing"
        self.assertEqual(records["data pipelines"]["ngram_size"], 2)  # repeated non-skill phrase

    def test_generic_words_are_not_keywords(self):
        jd = (
            "We are looking for a strong candidate with excellent communication skills and 3+ years of "
            "experience. Ability to work in a team and solve problems. Python required."
        )
        keywords = [r["keyword"] for r in keyword_extraction.extract_keywords(jd)]
        self.assertEqual(keywords, ["Python"])

    def test_technical_terms_outrank_generic_content(self):
        records = keyword_extraction.extract_keywords(load("python_developer", "jd"))
        self.assertTrue(records[0]["is_skill"])
        top_keywords = [r["keyword"] for r in records[:8]]
        for expected in ["Python", "Django", "REST APIs"]:
            self.assertIn(expected, top_keywords)

    def test_phrase_wrapping_a_skill_is_not_reported_separately(self):
        keywords = [r["keyword"] for r in keyword_extraction.extract_keywords(load("frontend_developer", "jd"))]
        self.assertIn("REST APIs", keywords)
        for noise in ["integrate rest", "integrate rest apis", "rest", "apis"]:
            self.assertNotIn(noise, keywords)

    def test_special_character_terms_become_keywords(self):
        keywords = [r["keyword"] for r in keyword_extraction.extract_keywords(DOTNET_JD)]
        for term in ["C#", ".NET", "SQL Server", "CI/CD", "C++", "Node.js", "Docker"]:
            with self.subTest(term=term):
                self.assertIn(term, keywords)

    def test_present_and_missing_keywords_with_synonyms(self):
        jd = "Requirements: Node.js, PostgreSQL, Docker, Kubernetes."
        resume = "Built services in NodeJS with Postgres and Docker."
        result = keyword_extraction.analyze_keywords(resume, jd)
        self.assertEqual(set(result["present"]), {"Node.js", "PostgreSQL", "Docker"})
        self.assertEqual(result["missing"], ["Kubernetes"])
        self.assertEqual(result["coverage"], 75.0)

    def test_missing_keywords_on_sample_pair(self):
        result = keyword_extraction.analyze_keywords(load("python_developer", "resume"), load("python_developer", "jd"))
        self.assertEqual(set(result["missing"]), {"PostgreSQL", "Redis", "AWS", "CI/CD"})
        for present in ["Python", "Django", "Flask", "Docker", "Git", "Linux", "pytest"]:
            self.assertIn(present, result["present"])

    def test_present_plus_missing_equals_keywords(self):
        for role in ROLES:
            with self.subTest(role=role):
                result = keyword_extraction.analyze_keywords(load(role, "resume"), load(role, "jd"))
                self.assertEqual(len(result["present"]) + len(result["missing"]), len(result["keywords"]))

    def test_top_n_limits_results(self):
        records = keyword_extraction.extract_keywords(load("full_stack_developer", "jd"), top_n=5)
        self.assertEqual(len(records), 5)
        scores = [r["score"] for r in records]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_empty_and_meaningless_input(self):
        for text in ["", "   ", "the and of with", "!!! ???"]:
            with self.subTest(text=text):
                self.assertEqual(keyword_extraction.extract_keywords(text), [])
        result = keyword_extraction.analyze_keywords("Python", "")
        self.assertEqual((result["keywords"], result["present"], result["missing"], result["coverage"]), ([], [], [], None))

    def test_invalid_input(self):
        with self.assertRaises(TypeError):
            keyword_extraction.extract_keywords(None)
        with self.assertRaises(TypeError):
            keyword_extraction.analyze_keywords(123, "python")
        with self.assertRaises(ValueError):
            keyword_extraction.extract_keywords("python", top_n=0)

    def test_extended_dictionary_is_used_for_keywords(self):
        jd = "We need Tally experience for bookkeeping."
        self.assertNotIn("Tally", [r["keyword"] for r in keyword_extraction.extract_keywords(jd)])
        skill_extraction.register_skill("Accounting", "Tally", ["tally erp"])
        try:
            self.assertIn("Tally", [r["keyword"] for r in keyword_extraction.extract_keywords(jd)])
        finally:
            skill_extraction.unregister_skill("Accounting", "Tally")


# --------------------------------------------------------------------------
# 5. Scoring
# --------------------------------------------------------------------------
class TestScoring(unittest.TestCase):
    EXPECTED_KEYS = {
        "overall_score", "text_similarity", "skill_coverage", "matched_skills",
        "missing_skills", "category_analysis", "weights", "explanation", "notes", "disclaimer",
    }

    def test_initial_weights_are_40_60(self):
        self.assertEqual(scoring.SIMILARITY_WEIGHT, 0.40)
        self.assertEqual(scoring.SKILL_WEIGHT, 0.60)

    def test_returns_all_required_fields(self):
        result = scoring.calculate_match_score(load("python_developer", "resume"), load("python_developer", "jd"))
        self.assertEqual(set(result), self.EXPECTED_KEYS)

    def test_overall_score_follows_the_40_60_formula(self):
        for role in ROLES:
            with self.subTest(role=role):
                resume, jd = load(role, "resume"), load(role, "jd")
                result = scoring.calculate_match_score(resume, jd)
                similarity_score = similarity.calculate_similarity(resume, jd)
                coverage = skill_extraction.analyze_skills(resume, jd)["skill_coverage"]
                self.assertEqual(result["text_similarity"], similarity_score)
                self.assertEqual(result["skill_coverage"], coverage)
                self.assertEqual(result["overall_score"], round(0.4 * similarity_score + 0.6 * coverage, 2))
                self.assertEqual(result["weights"], {"similarity": 0.4, "skills": 0.6})

    def test_skill_coverage_is_matched_over_required(self):
        jd = "Requirements: Python, Django, MySQL, Docker."
        resume = "I know Python and Django."
        result = scoring.calculate_match_score(resume, jd)
        self.assertEqual(result["matched_skills"], ["Python", "Django"])
        self.assertEqual(result["missing_skills"], ["MySQL", "Docker"])
        self.assertEqual(result["skill_coverage"], 50.0)

    def test_full_skill_coverage_gives_100_coverage(self):
        jd = "Requirements: Python, Django, MySQL."
        resume = "Python, Django and MySQL developer."
        result = scoring.calculate_match_score(resume, jd)
        self.assertEqual(result["skill_coverage"], 100.0)
        self.assertEqual(result["missing_skills"], [])
        self.assertGreaterEqual(result["overall_score"], 60.0)  # skill part alone is worth 60

    def test_no_skill_overlap_gives_zero_coverage(self):
        result = scoring.calculate_match_score("Retail manager and cashier trainer.", "Requirements: Python, Django.")
        self.assertEqual(result["skill_coverage"], 0.0)
        self.assertEqual(result["matched_skills"], [])
        self.assertEqual(result["overall_score"], round(0.4 * result["text_similarity"], 2))

    def test_scores_are_within_0_and_100(self):
        for role in ROLES:
            with self.subTest(role=role):
                result = scoring.calculate_match_score(load(role, "resume"), load(role, "jd"))
                for field in ["overall_score", "text_similarity", "skill_coverage"]:
                    self.assertGreaterEqual(result[field], 0.0)
                    self.assertLessEqual(result[field], 100.0)

    def test_better_resume_scores_higher_for_same_job(self):
        jd = load("java_backend_developer", "jd")
        good = scoring.calculate_match_score(load("java_backend_developer", "resume"), jd)["overall_score"]
        poor = scoring.calculate_match_score(load("frontend_developer", "resume"), jd)["overall_score"]
        self.assertGreater(good, poor)

    def test_special_character_skills_in_scoring(self):
        result = scoring.calculate_match_score(DOTNET_RESUME, DOTNET_JD)
        for skill in ["C#", ".NET", "SQL Server", "CI/CD", "C++", "Node.js", "Docker"]:
            with self.subTest(skill=skill):
                self.assertIn(skill, result["matched_skills"])
        self.assertEqual(result["missing_skills"], [])
        self.assertEqual(result["skill_coverage"], 100.0)

    def test_disclaimer_says_estimate_not_ats_probability(self):
        result = scoring.calculate_match_score("Python developer", "Requirements: Python.")
        text = result["disclaimer"].lower()
        self.assertIn("estimated", text)
        self.assertIn("not", text)
        self.assertIn("ats", text)
        self.assertIn("estimated compatibility score", scoring.__doc__)
        self.assertIn("NOT the probability", scoring.__doc__)

    def test_explanation_shows_the_calculation(self):
        result = scoring.calculate_match_score(load("data_analyst", "resume"), load("data_analyst", "jd"))
        self.assertIn("40%", result["explanation"])
        self.assertIn("60%", result["explanation"])
        self.assertIn(str(result["overall_score"]), result["explanation"])

    def test_jd_without_known_skills_falls_back_to_similarity_only(self):
        result = scoring.calculate_match_score(
            "Customer service associate with cash handling experience",
            "We need a friendly customer service associate for weekend shifts",
        )
        self.assertIsNone(result["skill_coverage"])
        self.assertEqual(result["weights"], {"similarity": 1.0, "skills": 0.0})
        self.assertEqual(result["overall_score"], result["text_similarity"])
        self.assertEqual(len(result["notes"]), 1)

    def test_custom_weights_are_applied_and_validated(self):
        resume, jd = load("python_developer", "resume"), load("python_developer", "jd")
        only_skills = scoring.calculate_match_score(resume, jd, similarity_weight=0.0, skill_weight=1.0)
        self.assertEqual(only_skills["overall_score"], only_skills["skill_coverage"])
        for similarity_weight, skill_weight in [(0.5, 0.6), (-0.1, 1.1), (0.2, 0.2)]:
            with self.subTest(weights=(similarity_weight, skill_weight)):
                with self.assertRaises(ValueError):
                    scoring.calculate_match_score(resume, jd, similarity_weight, skill_weight)

    def test_empty_input_raises_value_error(self):
        jd = load("python_developer", "jd")
        for blank in ["", "   ", "\n\t"]:
            with self.subTest(blank=blank):
                with self.assertRaises(ValueError):
                    scoring.calculate_match_score(blank, jd)
                with self.assertRaises(ValueError):
                    scoring.calculate_match_score(jd, blank)

    def test_invalid_input_raises_type_error(self):
        jd = load("python_developer", "jd")
        for bad in [None, 123, ["Python"], b"python"]:
            with self.subTest(bad=bad):
                with self.assertRaises(TypeError):
                    scoring.calculate_match_score(bad, jd)
                with self.assertRaises(TypeError):
                    scoring.calculate_match_score(jd, bad)

    def test_text_that_is_only_symbols_does_not_crash(self):
        result = scoring.calculate_match_score("!!! ??? ###", load("python_developer", "jd"))
        self.assertEqual(result["text_similarity"], 0.0)
        self.assertEqual(result["skill_coverage"], 0.0)
        self.assertEqual(result["overall_score"], 0.0)


# --------------------------------------------------------------------------
# Sample data and cross-module integration
# --------------------------------------------------------------------------
class TestSampleDataAndIntegration(unittest.TestCase):
    def test_all_sample_files_exist_and_are_realistic_length(self):
        for role in ROLES:
            for kind in ["resume", "jd"]:
                with self.subTest(role=role, kind=kind):
                    path = SAMPLE_DIR / f"{role}_{kind}.txt"
                    self.assertTrue(path.exists(), f"missing {path.name}")
                    self.assertGreater(len(path.read_text(encoding="utf-8").split()), 80)

    def test_full_pipeline_runs_on_every_sample_pair(self):
        for role in ROLES:
            with self.subTest(role=role):
                resume, jd = load(role, "resume"), load(role, "jd")
                self.assertTrue(preprocessing.preprocess_text(resume))
                self.assertTrue(keyword_extraction.extract_keywords(jd))
                result = scoring.calculate_match_score(resume, jd)
                # the scoring module and the keyword module agree on missing skills
                keyword_result = keyword_extraction.analyze_keywords(resume, jd, top_n=40)
                skill_keywords_missing = {
                    r["keyword"] for r in keyword_result["keywords"] if r["is_skill"]
                } & set(keyword_result["missing"])
                self.assertTrue(skill_keywords_missing <= set(result["missing_skills"]))

    def test_each_resume_matches_its_own_job_best(self):
        """Sanity check on the synthetic data: a resume should score higher for the
        job it was written for than for any of the other five jobs."""
        for resume_role in ROLES:
            with self.subTest(resume=resume_role):
                scores = {
                    jd_role: scoring.calculate_match_score(load(resume_role, "resume"), load(jd_role, "jd"))["overall_score"]
                    for jd_role in ROLES
                }
                self.assertEqual(max(scores, key=scores.get), resume_role, scores)


if __name__ == "__main__":
    unittest.main(verbosity=2)
