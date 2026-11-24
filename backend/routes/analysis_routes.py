"""Analysis API: health check, analyze, history, retrieve and delete."""

from flask import Blueprint, current_app, jsonify, request
from sqlalchemy import func, select

from ..database.db import check_database, db, ensure_schema
from ..database.models import JOB_DESCRIPTION_PREVIEW_CHARS, Analysis, format_timestamp
from ..nlp_engine import DISCLAIMER, analyze_keywords, calculate_match_score
from ..services.pdf_extractor import PDFExtractionError, extract_text_from_upload
from . import ApiError

analysis_bp = Blueprint("analysis", __name__, url_prefix="/api")

FORM_MIMETYPES = {"multipart/form-data", "application/x-www-form-urlencoded"}
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


# --------------------------------------------------------------------------
# Health
# --------------------------------------------------------------------------

@analysis_bp.get("/health")
def health():
    """Application and database status. HTTP 503 when the database is unreachable."""
    connected, message = check_database()
    body = {
        "status": "ok" if connected else "degraded",
        "app": "running",
        "database": {"status": "connected" if connected else "unavailable", "message": message},
    }
    return jsonify(body), (200 if connected else 503)


# --------------------------------------------------------------------------
# Input handling
# --------------------------------------------------------------------------

def _read_request():
    """Return ``(resume_text, job_description, pdf_upload)`` from a JSON or form request.

    JSON:  {"resume_text": "...", "job_description": "..."}
    Form:  resume_text and/or resume_file (a PDF), plus job_description
    """
    if request.is_json:
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            raise ApiError(400, "invalid_json", "The request body must be a valid JSON object.")
        resume, job_description, upload = data.get("resume_text"), data.get("job_description"), None
        wrong_types = {
            field: "must be a string"
            for field, value in (("resume_text", resume), ("job_description", job_description))
            if value is not None and not isinstance(value, str)
        }
        if wrong_types:
            raise ApiError(400, "invalid_field_type", "Text fields must be strings.", wrong_types)
    elif request.mimetype in FORM_MIMETYPES:
        resume = request.form.get("resume_text")
        job_description = request.form.get("job_description")
        upload = request.files.get("resume_file")
        if upload is not None and not upload.filename:
            upload = None  # browsers send an empty part when no file was chosen
    else:
        raise ApiError(
            415,
            "unsupported_media_type",
            "Send JSON (application/json) or a form (multipart/form-data).",
        )
    return resume, job_description, upload


def _validate_input(resume, job_description, upload):
    """Raise a 400 ApiError listing every input problem (the first one sets the code)."""
    issues = {}  # field -> (code, message)

    if upload is not None and resume is not None and resume.strip():
        issues["resume"] = (
            "conflicting_resume_input",
            "Provide either resume_text or a PDF in resume_file, not both.",
        )
    elif upload is None:
        if resume is None:
            issues["resume"] = (
                "missing_resume",
                "The resume is missing. Provide resume_text or upload a PDF as resume_file.",
            )
        elif not resume.strip():
            issues["resume"] = ("empty_resume", "resume_text must not be empty.")

    if job_description is None:
        issues["job_description"] = ("missing_job_description", "job_description is required.")
    elif not job_description.strip():
        issues["job_description"] = ("empty_job_description", "job_description must not be empty.")

    if issues:
        code, message = next(iter(issues.values()))
        details = {field: msg for field, (_, msg) in issues.items()}
        raise ApiError(400, code, message, details)


def _run_nlp(resume_text, job_description):
    """Run the existing NLP engine and return ``(score_result, keyword_result)``."""
    try:
        score = calculate_match_score(resume_text, job_description)
        keywords = analyze_keywords(resume_text, job_description)
    except (TypeError, ValueError) as exc:
        raise ApiError(422, "analysis_failed", f"The texts could not be analyzed: {exc}")
    except RuntimeError as exc:  # raised by the engine when NLTK data is unavailable
        current_app.logger.error("NLP resources unavailable: %s", exc)
        raise ApiError(503, "nlp_resources_unavailable", "Language resources for the analysis are unavailable.")
    return score, keywords


# --------------------------------------------------------------------------
# Analyze
# --------------------------------------------------------------------------

@analysis_bp.post("/analyze")
def analyze():
    """Analyze a resume (text or PDF) against a job description and save the result."""
    resume_text, job_description, upload = _read_request()
    _validate_input(resume_text, job_description, upload)

    filename = None
    if upload is not None:
        try:
            filename, resume_text = extract_text_from_upload(
                upload, current_app.config["MAX_UPLOAD_BYTES"]
            )
        except PDFExtractionError as exc:
            raise ApiError(exc.status_code, exc.code, str(exc))

    if not ensure_schema():  # fail fast, before doing the NLP work
        raise ApiError(503, "database_unavailable", "The database is not available. Please try again later.")

    score, keywords = _run_nlp(resume_text, job_description)

    analysis = Analysis(
        resume_filename=filename,
        resume_text=resume_text,
        job_description=job_description,
        overall_score=score["overall_score"],
        text_similarity=score["text_similarity"],
        skill_coverage=score["skill_coverage"],
        matched_skills=score["matched_skills"],
        missing_skills=score["missing_skills"],
        category_analysis=score["category_analysis"],
        extracted_keywords=keywords["keywords"],
        missing_keywords=keywords["missing"],
        scoring_explanation=score["explanation"],
        score_weights=score["weights"],
        scoring_notes=score["notes"],
    )
    db.session.add(analysis)
    db.session.commit()  # database errors are turned into JSON by the app-level handler
    return jsonify(analysis.to_dict(disclaimer=DISCLAIMER)), 201


# --------------------------------------------------------------------------
# History, retrieve, delete
# --------------------------------------------------------------------------

def _int_arg(name, default, minimum, maximum=None):
    raw = request.args.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        value = None
    if value is None or value < minimum or (maximum is not None and value > maximum):
        bound = f"between {minimum} and {maximum}" if maximum is not None else f"at least {minimum}"
        raise ApiError(400, "invalid_parameter", f"{name} must be an integer {bound}.")
    return value


@analysis_bp.get("/analyses")
def list_analyses():
    """Saved analyses, newest first. Summaries only: the full resume and job
    description are not returned here (use GET /api/analyses/<id>)."""
    limit = _int_arg("limit", DEFAULT_PAGE_SIZE, 1, MAX_PAGE_SIZE)
    offset = _int_arg("offset", 0, 0)
    ensure_schema()

    preview = func.substr(Analysis.job_description, 1, JOB_DESCRIPTION_PREVIEW_CHARS + 1)
    rows = db.session.execute(
        select(
            Analysis.id,
            Analysis.resume_filename,
            Analysis.overall_score,
            Analysis.text_similarity,
            Analysis.skill_coverage,
            Analysis.matched_skills,
            Analysis.missing_skills,
            Analysis.created_at,
            preview.label("job_description_preview"),
        )
        .order_by(Analysis.created_at.desc(), Analysis.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    total = db.session.scalar(select(func.count(Analysis.id)))

    analyses = []
    for row in rows:
        text = row.job_description_preview or ""
        if len(text) > JOB_DESCRIPTION_PREVIEW_CHARS:
            text = text[:JOB_DESCRIPTION_PREVIEW_CHARS] + "…"
        analyses.append(
            {
                "id": row.id,
                "resume_filename": row.resume_filename,
                "created_at": format_timestamp(row.created_at),
                "overall_score": row.overall_score,
                "text_similarity": row.text_similarity,
                "skill_coverage": row.skill_coverage,
                "matched_skills_count": len(row.matched_skills),
                "missing_skills_count": len(row.missing_skills),
                "job_description_preview": text,
            }
        )
    return jsonify({"total": total, "limit": limit, "offset": offset, "analyses": analyses})


def _get_or_404(analysis_id):
    ensure_schema()
    analysis = db.session.get(Analysis, analysis_id)
    if analysis is None:
        raise ApiError(404, "analysis_not_found", f"No analysis with id {analysis_id} exists.")
    return analysis


@analysis_bp.get("/analyses/<int:analysis_id>")
def get_analysis(analysis_id):
    """The complete saved analysis, including the resume and job description text."""
    return jsonify(_get_or_404(analysis_id).to_dict(disclaimer=DISCLAIMER))


@analysis_bp.delete("/analyses/<int:analysis_id>")
def delete_analysis(analysis_id):
    """Delete a saved analysis."""
    analysis = _get_or_404(analysis_id)
    db.session.delete(analysis)
    db.session.commit()
    return jsonify({"message": "Analysis deleted.", "id": analysis_id})
