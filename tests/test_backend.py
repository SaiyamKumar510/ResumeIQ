"""Tests for the ResumeIQ Flask backend.

Run from the project root (the ResumeIQ folder):

    python -m unittest tests.test_backend -v

By default every test uses an in-memory SQLite database (``TestingConfig``),
so MySQL is NOT needed and nothing real is touched. Database failures are
simulated with mocks. One extra test class talks to a real MySQL server; it is
skipped unless you opt in (see ``TestMySQLIntegration``).
"""

import io
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

import pymupdf
from sqlalchemy.exc import OperationalError, SQLAlchemyError

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend import config as backend_config  # noqa: E402
from backend.app import create_app  # noqa: E402
from backend.config import Config, TestingConfig  # noqa: E402
from backend.database.db import db  # noqa: E402
from backend.database.models import Analysis  # noqa: E402
from backend.nlp_engine import DISCLAIMER, analyze_keywords, calculate_match_score  # noqa: E402
from backend.services import pdf_extractor  # noqa: E402
from backend.services.pdf_extractor import PDFExtractionError  # noqa: E402

SAMPLE_DIR = ROOT / "datasets" / "sample_data"
ROLES = [
    "python_developer",
    "java_backend_developer",
    "frontend_developer",
    "full_stack_developer",
    "data_analyst",
    "machine_learning_engineer",
]

RESUME = "Python developer. Built REST APIs with Django and Flask on MySQL. Used Git, GitHub and Docker."
JOB = "We need Python, Django, PostgreSQL, Docker and AWS. Experience with REST APIs is a plus."


def load(role, kind):
    return (SAMPLE_DIR / f"{role}_{kind}.txt").read_text(encoding="utf-8")


# --------------------------------------------------------------------------
# PDF helpers (PDFs are generated, no binary fixtures are stored)
# --------------------------------------------------------------------------

def make_pdf(pages, **save_options):
    """Return the bytes of a PDF with one page per string in ``pages``."""
    document = pymupdf.open()
    for text in pages:
        page = document.new_page()
        if text:
            page.insert_text((72, 72), text, fontsize=11)
    data = document.tobytes(**save_options)
    document.close()
    return data


def pdf_upload(data, filename="resume.pdf"):
    return (io.BytesIO(data), filename)


# --------------------------------------------------------------------------
# Base class
# --------------------------------------------------------------------------

class BackendTestCase(unittest.TestCase):
    config_class = TestingConfig

    def setUp(self):
        self.app = create_app(self.config_class)
        self.client = self.app.test_client()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.engine.dispose()

    # helpers ---------------------------------------------------------------
    def analyze(self, resume=RESUME, job=JOB):
        return self.client.post("/api/analyze", json={"resume_text": resume, "job_description": job})

    def count_rows(self):
        with self.app.app_context():
            return db.session.query(Analysis).count()

    def assert_error(self, response, status, code):
        self.assertEqual(response.status_code, status, response.get_data(as_text=True))
        self.assertEqual(response.mimetype, "application/json")
        body = response.get_json()
        self.assertEqual(set(body), {"error"})
        self.assertEqual(body["error"]["code"], code)
        self.assertTrue(body["error"]["message"])
        return body["error"]


# --------------------------------------------------------------------------
# Health
# --------------------------------------------------------------------------

class TestHealth(BackendTestCase):
    def test_health_reports_app_and_database_ok(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["status"], "ok")
        self.assertEqual(body["app"], "running")
        self.assertEqual(body["database"]["status"], "connected")

    def test_health_reports_database_failure_with_503(self):
        error = OperationalError("SELECT 1", {}, Exception("secret-host-name refused"))
        with mock.patch.object(db.session, "execute", side_effect=error):
            response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 503)
        body = response.get_json()
        self.assertEqual(body["status"], "degraded")
        self.assertEqual(body["app"], "running")
        self.assertEqual(body["database"]["status"], "unavailable")
        self.assertNotIn("secret-host-name", response.get_data(as_text=True))  # no internals leaked

    def test_app_starts_and_degrades_gracefully_when_mysql_is_unreachable(self):
        """Real connection attempt to a closed port (no mocks)."""

        class Unreachable(Config):
            TESTING = True
            SQLALCHEMY_DATABASE_URI = "mysql+pymysql://user:pw@127.0.0.1:1/none?charset=utf8mb4"
            SQLALCHEMY_ENGINE_OPTIONS = {"connect_args": {"connect_timeout": 1}}

        app = create_app(Unreachable)  # must not raise
        client = app.test_client()
        health = client.get("/api/health")
        self.assertEqual(health.status_code, 503)
        self.assertEqual(health.get_json()["database"]["status"], "unavailable")
        response = client.post("/api/analyze", json={"resume_text": RESUME, "job_description": JOB})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json()["error"]["code"], "database_unavailable")
        self.assertEqual(client.get("/api/analyses").status_code, 503)


# --------------------------------------------------------------------------
# Analyze with text
# --------------------------------------------------------------------------

class TestAnalyzeText(BackendTestCase):
    REQUIRED_FIELDS = {
        "id", "created_at", "overall_score", "text_similarity", "skill_coverage",
        "matched_skills", "missing_skills", "category_analysis", "extracted_keywords",
        "missing_keywords", "scoring_explanation", "disclaimer",
    }

    def test_text_analysis_returns_all_fields(self):
        response = self.analyze()
        self.assertEqual(response.status_code, 201, response.get_data(as_text=True))
        body = response.get_json()
        self.assertTrue(self.REQUIRED_FIELDS <= set(body), self.REQUIRED_FIELDS - set(body))
        self.assertIsNone(body["resume_filename"])
        self.assertEqual(body["disclaimer"], DISCLAIMER)
        self.assertIn("NOT", body["disclaimer"])

    def test_response_matches_the_nlp_engine_output_exactly(self):
        body = self.analyze().get_json()
        score = calculate_match_score(RESUME, JOB)
        keywords = analyze_keywords(RESUME, JOB)
        self.assertEqual(body["overall_score"], score["overall_score"])
        self.assertEqual(body["text_similarity"], score["text_similarity"])
        self.assertEqual(body["skill_coverage"], score["skill_coverage"])
        self.assertEqual(body["matched_skills"], score["matched_skills"])
        self.assertEqual(body["missing_skills"], score["missing_skills"])
        self.assertEqual(body["category_analysis"], score["category_analysis"])
        self.assertEqual(body["scoring_explanation"], score["explanation"])
        self.assertEqual(body["weights"], score["weights"])
        self.assertEqual(body["notes"], score["notes"])
        self.assertEqual(body["extracted_keywords"], keywords["keywords"])
        self.assertEqual(body["missing_keywords"], keywords["missing"])

    def test_known_skills_are_reported(self):
        body = self.analyze().get_json()
        self.assertEqual(set(body["missing_skills"]), {"PostgreSQL", "AWS"})
        self.assertIn("Python", body["matched_skills"])
        self.assertIn("PostgreSQL", body["missing_keywords"])
        self.assertEqual(body["weights"], {"similarity": 0.4, "skills": 0.6})

    def test_analysis_is_saved_to_the_database(self):
        body = self.analyze().get_json()
        self.assertEqual(self.count_rows(), 1)
        with self.app.app_context():
            row = db.session.get(Analysis, body["id"])
            self.assertEqual(row.resume_text, RESUME)
            self.assertEqual(row.job_description, JOB)
            self.assertEqual(row.overall_score, body["overall_score"])
            self.assertEqual(row.missing_skills, body["missing_skills"])
            self.assertIsNotNone(row.created_at)

    def test_every_sample_pair_can_be_analyzed(self):
        for role in ROLES:
            with self.subTest(role=role):
                response = self.analyze(load(role, "resume"), load(role, "jd"))
                self.assertEqual(response.status_code, 201)
                body = response.get_json()
                self.assertTrue(0 <= body["overall_score"] <= 100)
                self.assertTrue(body["extracted_keywords"])

    def test_jd_without_known_skills_stores_null_coverage(self):
        body = self.analyze("Friendly cashier with cash handling experience.", "We need a cashier for weekend shifts.").get_json()
        self.assertIsNone(body["skill_coverage"])
        self.assertEqual(body["weights"], {"similarity": 1.0, "skills": 0.0})
        self.assertEqual(len(body["notes"]), 1)
        with self.app.app_context():
            self.assertIsNone(db.session.get(Analysis, body["id"]).skill_coverage)

    def test_form_encoded_text_is_accepted(self):
        response = self.client.post("/api/analyze", data={"resume_text": RESUME, "job_description": JOB})
        self.assertEqual(response.status_code, 201)

    def test_unicode_text_is_stored_intact(self):
        resume = "Développeur Python – expérience Django, café ☕, 日本語"
        body = self.analyze(resume, JOB).get_json()
        self.assertEqual(body["resume_text"], resume)

    def test_long_text_is_not_truncated(self):
        resume = (RESUME + " ") * 3000  # about 270 KB, larger than a MySQL TEXT column
        body = self.analyze(resume, JOB).get_json()
        self.assertEqual(body["resume_text"], resume)


# --------------------------------------------------------------------------
# PDF extractor (service)
# --------------------------------------------------------------------------

class TestPdfExtractor(unittest.TestCase):
    def test_extracts_text_from_multiple_pages(self):
        text = pdf_extractor.extract_text_from_pdf(
            make_pdf(["Page one: Python and Django", "Page two: Docker and Git", "Page three: pytest"])
        )
        for expected in ["Python and Django", "Docker and Git", "pytest"]:
            self.assertIn(expected, text)
        self.assertLess(text.index("Python"), text.index("Docker"))
        self.assertLess(text.index("Docker"), text.index("pytest"))

    def test_empty_bytes_rejected(self):
        with self.assertRaises(PDFExtractionError) as ctx:
            pdf_extractor.extract_text_from_pdf(b"")
        self.assertEqual((ctx.exception.code, ctx.exception.status_code), ("invalid_pdf", 400))

    def test_non_pdf_bytes_rejected(self):
        with self.assertRaises(PDFExtractionError) as ctx:
            pdf_extractor.extract_text_from_pdf(b"This is just a plain text file.")
        self.assertEqual(ctx.exception.code, "invalid_pdf")

    def test_corrupt_pdf_rejected(self):
        corrupt = b"%PDF-1.7\n" + b"garbage" * 50
        with self.assertRaises(PDFExtractionError) as ctx:
            pdf_extractor.extract_text_from_pdf(corrupt)
        self.assertIn(ctx.exception.code, {"invalid_pdf", "no_extractable_text"})

    def test_truncated_pdf_never_crashes(self):
        data = make_pdf(["Python developer with Django"])
        try:
            pdf_extractor.extract_text_from_pdf(data[: len(data) // 2])
        except PDFExtractionError:
            pass  # a clean, typed error is the expected outcome

    def test_pdf_without_text_reports_no_extractable_text(self):
        with self.assertRaises(PDFExtractionError) as ctx:
            pdf_extractor.extract_text_from_pdf(make_pdf(["", ""]))  # blank pages, like a scan
        self.assertEqual((ctx.exception.code, ctx.exception.status_code), ("no_extractable_text", 422))
        self.assertIn("OCR", str(ctx.exception))

    def test_password_protected_pdf_rejected(self):
        data = make_pdf(["Secret resume text"], encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw="user", owner_pw="owner")
        with self.assertRaises(PDFExtractionError) as ctx:
            pdf_extractor.extract_text_from_pdf(data)
        self.assertEqual(ctx.exception.code, "encrypted_pdf")

    def test_too_many_pages_rejected(self):
        with mock.patch.object(pdf_extractor, "MAX_PAGES", 2):
            with self.assertRaises(PDFExtractionError) as ctx:
                pdf_extractor.extract_text_from_pdf(make_pdf(["a", "b", "c"]))
        self.assertEqual(ctx.exception.code, "too_many_pages")

    def test_non_bytes_input_is_a_type_error(self):
        with self.assertRaises(TypeError):
            pdf_extractor.extract_text_from_pdf("not bytes")


# --------------------------------------------------------------------------
# Analyze with a PDF upload
# --------------------------------------------------------------------------

class TestAnalyzePdf(BackendTestCase):
    def post_pdf(self, data, filename="resume.pdf", job=JOB, **extra_fields):
        fields = {"resume_file": pdf_upload(data, filename), "job_description": job, **extra_fields}
        return self.client.post("/api/analyze", data=fields, content_type="multipart/form-data")

    def test_pdf_resume_is_analyzed_and_saved(self):
        pdf = make_pdf(["Python developer. Built REST APIs with Django.", "Skills: Docker, Git, MySQL, pytest"])
        response = self.post_pdf(pdf, "My Resume (final).pdf")
        self.assertEqual(response.status_code, 201, response.get_data(as_text=True))
        body = response.get_json()
        self.assertEqual(body["resume_filename"], "My_Resume_final.pdf")  # sanitized
        self.assertIn("Built REST APIs with Django", body["resume_text"])
        self.assertIn("Skills: Docker, Git", body["resume_text"])  # second page
        for skill in ["Python", "Django", "Docker"]:
            self.assertIn(skill, body["matched_skills"])
        self.assertEqual(self.count_rows(), 1)

    def test_pdf_result_equals_text_result_for_the_same_content(self):
        text = "Python developer. Built REST APIs with Django."
        from_pdf = self.post_pdf(make_pdf([text])).get_json()
        from_text = self.analyze(from_pdf["resume_text"], JOB).get_json()
        for field in ["overall_score", "text_similarity", "skill_coverage", "matched_skills", "missing_skills"]:
            self.assertEqual(from_pdf[field], from_text[field], field)

    def test_uppercase_pdf_extension_is_accepted(self):
        self.assertEqual(self.post_pdf(make_pdf(["Python Django"]), "RESUME.PDF").status_code, 201)

    def test_invalid_pdf_content_returns_400(self):
        response = self.post_pdf(b"definitely not a pdf")
        self.assert_error(response, 400, "invalid_pdf")
        self.assertEqual(self.count_rows(), 0)

    def test_empty_file_returns_400(self):
        self.assert_error(self.post_pdf(b""), 400, "invalid_pdf")

    def test_scanned_pdf_returns_422_with_clear_message(self):
        error = self.assert_error(self.post_pdf(make_pdf([""])), 422, "no_extractable_text")
        self.assertIn("scanned", error["message"])

    def test_encrypted_pdf_returns_422(self):
        data = make_pdf(["secret"], encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw="u", owner_pw="o")
        self.assert_error(self.post_pdf(data), 422, "encrypted_pdf")

    def test_unsupported_file_formats_return_415(self):
        for filename in ["resume.docx", "resume.txt", "resume.png", "resume", "resume.pdf.exe"]:
            with self.subTest(filename=filename):
                response = self.post_pdf(make_pdf(["Python"]), filename)
                self.assert_error(response, 415, "unsupported_file_type")
        self.assertEqual(self.count_rows(), 0)

    def test_a_renamed_text_file_is_rejected(self):
        self.assert_error(self.post_pdf(b"Python developer\nDjango", "resume.pdf"), 400, "invalid_pdf")

    def test_file_over_the_limit_returns_413(self):
        class SmallLimit(TestingConfig):
            MAX_UPLOAD_BYTES = 20_000
            MAX_CONTENT_LENGTH = 60_000

        app = create_app(SmallLimit)
        pdf = make_pdf(["Python developer"]) + b"0" * 30_000  # still a readable PDF, but 30 KB
        response = app.test_client().post(
            "/api/analyze",
            data={"resume_file": pdf_upload(pdf), "job_description": JOB},
            content_type="multipart/form-data",
        )
        self.assert_error(response, 413, "file_too_large")

    def test_request_over_the_hard_limit_returns_json_413(self):
        class TinyRequestLimit(TestingConfig):
            MAX_CONTENT_LENGTH = 20_000

        app = create_app(TinyRequestLimit)
        response = app.test_client().post(
            "/api/analyze",
            data={"resume_file": pdf_upload(b"x" * 100_000), "job_description": JOB},
            content_type="multipart/form-data",
        )
        self.assert_error(response, 413, "file_too_large")

    def test_default_upload_limit_is_5_mb(self):
        self.assertEqual(Config.MAX_UPLOAD_BYTES, 5 * 1024 * 1024)

    def test_both_text_and_pdf_is_rejected(self):
        response = self.post_pdf(make_pdf(["Python"]), resume_text="Also pasted text")
        self.assert_error(response, 400, "conflicting_resume_input")

    def test_empty_resume_text_field_is_ignored_when_a_pdf_is_present(self):
        self.assertEqual(self.post_pdf(make_pdf(["Python Django"]), resume_text="").status_code, 201)

    def test_empty_file_part_without_text_counts_as_missing_resume(self):
        response = self.client.post(
            "/api/analyze",
            data={"resume_file": (io.BytesIO(b""), ""), "job_description": JOB},
            content_type="multipart/form-data",
        )
        self.assert_error(response, 400, "missing_resume")


# --------------------------------------------------------------------------
# Input validation
# --------------------------------------------------------------------------

class TestValidation(BackendTestCase):
    def test_missing_resume(self):
        error = self.assert_error(self.client.post("/api/analyze", json={"job_description": JOB}), 400, "missing_resume")
        self.assertIn("resume", error["details"])

    def test_missing_job_description(self):
        error = self.assert_error(
            self.client.post("/api/analyze", json={"resume_text": RESUME}), 400, "missing_job_description"
        )
        self.assertIn("job_description", error["details"])

    def test_missing_both_lists_both_problems(self):
        error = self.assert_error(self.client.post("/api/analyze", json={}), 400, "missing_resume")
        self.assertEqual(set(error["details"]), {"resume", "job_description"})

    def test_empty_and_blank_resume_text(self):
        for blank in ["", "   ", "\n\t  \n"]:
            with self.subTest(blank=blank):
                response = self.client.post("/api/analyze", json={"resume_text": blank, "job_description": JOB})
                self.assert_error(response, 400, "empty_resume")

    def test_empty_and_blank_job_description(self):
        for blank in ["", "   ", "\n"]:
            with self.subTest(blank=blank):
                response = self.client.post("/api/analyze", json={"resume_text": RESUME, "job_description": blank})
                self.assert_error(response, 400, "empty_job_description")

    def test_invalid_json_body(self):
        response = self.client.post("/api/analyze", data="{not json", content_type="application/json")
        self.assert_error(response, 400, "invalid_json")

    def test_json_body_must_be_an_object(self):
        response = self.client.post("/api/analyze", json=["resume", "job"])
        self.assert_error(response, 400, "invalid_json")

    def test_non_string_fields(self):
        response = self.client.post("/api/analyze", json={"resume_text": 123, "job_description": ["x"]})
        error = self.assert_error(response, 400, "invalid_field_type")
        self.assertEqual(set(error["details"]), {"resume_text", "job_description"})

    def test_unsupported_content_type(self):
        response = self.client.post("/api/analyze", data="plain text", content_type="text/plain")
        self.assert_error(response, 415, "unsupported_media_type")

    def test_request_without_body(self):
        self.assert_error(self.client.post("/api/analyze"), 415, "unsupported_media_type")

    def test_nothing_is_saved_when_validation_fails(self):
        self.client.post("/api/analyze", json={})
        self.client.post("/api/analyze", json={"resume_text": RESUME, "job_description": " "})
        self.assertEqual(self.count_rows(), 0)

    def test_unknown_routes_and_methods_return_json_errors(self):
        self.assert_error(self.client.get("/api/nope"), 404, "not_found")
        self.assert_error(self.client.put("/api/analyses"), 405, "method_not_allowed")
        self.assert_error(self.client.get("/api/analyses/abc"), 404, "not_found")


# --------------------------------------------------------------------------
# History, retrieval, deletion
# --------------------------------------------------------------------------

class TestHistoryRetrievalDeletion(BackendTestCase):
    def create(self, resume=RESUME, job=JOB):
        return self.analyze(resume, job).get_json()["id"]

    def test_history_starts_empty(self):
        body = self.client.get("/api/analyses").get_json()
        self.assertEqual((body["total"], body["analyses"]), (0, []))

    def test_history_is_newest_first(self):
        first, second, third = self.create(), self.create(), self.create()
        ids = [a["id"] for a in self.client.get("/api/analyses").get_json()["analyses"]]
        self.assertEqual(ids, [third, second, first])

    def test_history_order_follows_created_at_not_id(self):
        from datetime import datetime

        first, second, third = self.create(), self.create(), self.create()
        with self.app.app_context():
            db.session.get(Analysis, first).created_at = datetime(2030, 1, 1)  # newest by time
            db.session.get(Analysis, second).created_at = datetime(2020, 1, 1)
            db.session.get(Analysis, third).created_at = datetime(2025, 1, 1)
            db.session.commit()
        ids = [a["id"] for a in self.client.get("/api/analyses").get_json()["analyses"]]
        self.assertEqual(ids, [first, third, second])

    def test_history_items_are_summaries_without_full_texts(self):
        long_job = "Python Django developer needed. " * 50
        self.create(job=long_job)
        item = self.client.get("/api/analyses").get_json()["analyses"][0]
        for hidden in ["resume_text", "job_description", "category_analysis", "extracted_keywords"]:
            self.assertNotIn(hidden, item)
        for shown in ["id", "created_at", "overall_score", "text_similarity", "skill_coverage",
                      "matched_skills_count", "missing_skills_count", "job_description_preview", "resume_filename"]:
            self.assertIn(shown, item)
        self.assertLessEqual(len(item["job_description_preview"]), 101)
        self.assertTrue(item["job_description_preview"].endswith("…"))
        self.assertNotIn(RESUME, str(item))

    def test_short_job_description_preview_is_complete(self):
        self.create()
        item = self.client.get("/api/analyses").get_json()["analyses"][0]
        self.assertEqual(item["job_description_preview"], JOB)

    def test_history_counts_match_the_full_record(self):
        analysis_id = self.create()
        item = self.client.get("/api/analyses").get_json()["analyses"][0]
        full = self.client.get(f"/api/analyses/{analysis_id}").get_json()
        self.assertEqual(item["matched_skills_count"], len(full["matched_skills"]))
        self.assertEqual(item["missing_skills_count"], len(full["missing_skills"]))

    def test_history_pagination(self):
        ids = [self.create() for _ in range(5)]
        page = self.client.get("/api/analyses?limit=2&offset=1").get_json()
        self.assertEqual(page["total"], 5)
        self.assertEqual((page["limit"], page["offset"]), (2, 1))
        self.assertEqual([a["id"] for a in page["analyses"]], [ids[3], ids[2]])

    def test_history_rejects_invalid_pagination(self):
        for query in ["limit=0", "limit=abc", "limit=101", "offset=-1", "offset=x"]:
            with self.subTest(query=query):
                self.assert_error(self.client.get(f"/api/analyses?{query}"), 400, "invalid_parameter")

    def test_get_analysis_returns_the_complete_record(self):
        analysis_id = self.create()
        response = self.client.get(f"/api/analyses/{analysis_id}")
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["id"], analysis_id)
        self.assertEqual(body["resume_text"], RESUME)
        self.assertEqual(body["job_description"], JOB)
        self.assertEqual(body["disclaimer"], DISCLAIMER)
        for field in ["category_analysis", "extracted_keywords", "missing_keywords", "scoring_explanation"]:
            self.assertIn(field, body)

    def test_get_matches_what_analyze_returned(self):
        created = self.analyze().get_json()
        fetched = self.client.get(f"/api/analyses/{created['id']}").get_json()
        self.assertEqual(created, fetched)

    def test_get_unknown_id_returns_404(self):
        self.assert_error(self.client.get("/api/analyses/9999"), 404, "analysis_not_found")

    def test_delete_removes_the_analysis(self):
        keep, remove = self.create(), self.create()
        response = self.client.delete(f"/api/analyses/{remove}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["id"], remove)
        self.assert_error(self.client.get(f"/api/analyses/{remove}"), 404, "analysis_not_found")
        listing = self.client.get("/api/analyses").get_json()
        self.assertEqual(listing["total"], 1)
        self.assertEqual(listing["analyses"][0]["id"], keep)
        self.assertEqual(self.count_rows(), 1)

    def test_delete_unknown_id_returns_404(self):
        self.assert_error(self.client.delete("/api/analyses/9999"), 404, "analysis_not_found")

    def test_delete_twice_returns_404_the_second_time(self):
        analysis_id = self.create()
        self.assertEqual(self.client.delete(f"/api/analyses/{analysis_id}").status_code, 200)
        self.assert_error(self.client.delete(f"/api/analyses/{analysis_id}"), 404, "analysis_not_found")


# --------------------------------------------------------------------------
# Database and internal errors (simulated)
# --------------------------------------------------------------------------

class TestDatabaseErrors(BackendTestCase):
    def test_connection_error_while_saving_returns_503(self):
        error = OperationalError("INSERT", {}, Exception("secret-host-name down"))
        with mock.patch.object(db.session, "commit", side_effect=error):
            response = self.analyze()
        self.assert_error(response, 503, "database_unavailable")
        self.assertNotIn("secret-host-name", response.get_data(as_text=True))
        self.assertEqual(self.count_rows(), 0)

    def test_other_database_error_while_saving_returns_500(self):
        with mock.patch.object(db.session, "commit", side_effect=SQLAlchemyError("secret details")):
            response = self.analyze()
        self.assert_error(response, 500, "database_error")
        self.assertNotIn("secret details", response.get_data(as_text=True))
        self.assertEqual(self.count_rows(), 0)

    def test_schema_not_ready_returns_503_before_any_work(self):
        with mock.patch("backend.routes.analysis_routes.ensure_schema", return_value=False):
            with mock.patch("backend.routes.analysis_routes.calculate_match_score") as nlp:
                response = self.analyze()
        self.assert_error(response, 503, "database_unavailable")
        nlp.assert_not_called()

    def test_database_errors_on_read_and_delete_return_json(self):
        analysis_id = self.analyze().get_json()["id"]
        error = OperationalError("SELECT", {}, Exception("down"))
        with mock.patch.object(db.session, "execute", side_effect=error):
            self.assert_error(self.client.get("/api/analyses"), 503, "database_unavailable")
        with mock.patch.object(db.session, "get", side_effect=error):
            self.assert_error(self.client.get(f"/api/analyses/{analysis_id}"), 503, "database_unavailable")
            self.assert_error(self.client.delete(f"/api/analyses/{analysis_id}"), 503, "database_unavailable")

    def test_failed_save_does_not_break_the_next_request(self):
        error = OperationalError("INSERT", {}, Exception("down"))
        with mock.patch.object(db.session, "commit", side_effect=error):
            self.assertEqual(self.analyze().status_code, 503)
        self.assertEqual(self.analyze().status_code, 201)
        self.assertEqual(self.count_rows(), 1)

    def test_unexpected_errors_return_generic_json_500(self):
        with mock.patch("backend.routes.analysis_routes.calculate_match_score", side_effect=Exception("secret internals")):
            response = self.analyze()
        self.assert_error(response, 500, "internal_error")
        self.assertNotIn("secret internals", response.get_data(as_text=True))

    def test_missing_nlp_resources_return_503(self):
        with mock.patch("backend.routes.analysis_routes.calculate_match_score", side_effect=RuntimeError("NLTK data missing")):
            self.assert_error(self.analyze(), 503, "nlp_resources_unavailable")


# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

class TestConfiguration(unittest.TestCase):
    def test_database_url_is_built_from_environment_variables(self):
        env = {"DB_USER": "alice", "DB_PASSWORD": "p@ss/word:1", "DB_HOST": "db.example", "DB_PORT": "3307", "DB_NAME": "mydb"}
        with mock.patch.dict(os.environ, env):
            url = backend_config.build_mysql_url()
        self.assertEqual(url.drivername, "mysql+pymysql")
        self.assertEqual((url.username, url.host, url.port, url.database), ("alice", "db.example", 3307, "mydb"))
        self.assertEqual(url.password, "p@ss/word:1")  # special characters are handled
        self.assertEqual(url.query["charset"], "utf8mb4")
        self.assertNotIn("p@ss", url.render_as_string())  # password is hidden when printed

    def test_no_default_credentials(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            url = backend_config.build_mysql_url()
        self.assertEqual((url.username, url.password), ("", ""))

    def test_default_app_config_uses_mysql_and_tests_use_sqlite(self):
        self.assertEqual(Config.SQLALCHEMY_DATABASE_URI.drivername, "mysql+pymysql")
        self.assertEqual(TestingConfig.SQLALCHEMY_DATABASE_URI, "sqlite://")

    def test_env_example_exists_and_env_is_git_ignored(self):
        example = (ROOT / ".env.example").read_text(encoding="utf-8")
        for key in ["DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"]:
            self.assertIn(key + "=", example)
        ignored = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        self.assertIn(".env", ignored)
        self.assertIn("!.env.example", ignored)  # the template itself must stay in Git


# --------------------------------------------------------------------------
# Optional: real MySQL
# --------------------------------------------------------------------------

@unittest.skipUnless(
    os.environ.get("RESUMEIQ_TEST_MYSQL") == "1",
    "opt-in: set RESUMEIQ_TEST_MYSQL=1 and the DB_* variables for a THROWAWAY MySQL database",
)
class TestMySQLIntegration(unittest.TestCase):
    """Runs the main flow against the real MySQL database configured in DB_*.

    It creates the ``analyses`` table if needed and deletes the rows it creates.
    Use a test database, never one that holds data you care about.
    """

    def setUp(self):
        self.app = create_app(Config)
        self.client = self.app.test_client()
        self.created = []

    def tearDown(self):
        for analysis_id in self.created:
            self.client.delete(f"/api/analyses/{analysis_id}")
        with self.app.app_context():
            db.session.remove()
            db.engine.dispose()

    def test_full_flow_on_mysql(self):
        self.assertEqual(self.client.get("/api/health").get_json()["database"]["status"], "connected")

        big_resume = (RESUME + " Développeur ☕ ") * 3000  # > 64 KB: needs MEDIUMTEXT
        created = self.client.post("/api/analyze", json={"resume_text": big_resume, "job_description": JOB})
        self.assertEqual(created.status_code, 201, created.get_data(as_text=True))
        body = created.get_json()
        self.created.append(body["id"])

        fetched = self.client.get(f"/api/analyses/{body['id']}").get_json()
        self.assertEqual(fetched["resume_text"], big_resume)
        self.assertEqual(fetched["overall_score"], calculate_match_score(big_resume, JOB)["overall_score"])
        self.assertEqual(fetched["matched_skills"], body["matched_skills"])
        self.assertEqual(fetched["extracted_keywords"], body["extracted_keywords"])

        listing = self.client.get("/api/analyses?limit=100").get_json()
        self.assertIn(body["id"], [a["id"] for a in listing["analyses"]])

        self.assertEqual(self.client.delete(f"/api/analyses/{body['id']}").status_code, 200)
        self.created.clear()
        self.assertEqual(self.client.get(f"/api/analyses/{body['id']}").status_code, 404)


if __name__ == "__main__":
    unittest.main(verbosity=2)
