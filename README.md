# ResumeIQ – ATS Resume & Job Description Matcher

ResumeIQ compares a resume with a job description and reports an **estimated
compatibility score**, the skills that match, and the skills that are missing.

> **Important:** the score is an *estimate based on text similarity and
> technical-skill coverage*. It is **not** the probability that a real ATS
> (Applicant Tracking System) will accept or reject a resume. Real ATS products
> use their own undisclosed rules, and nothing in this project has been trained
> or validated against real ATS outcomes.

## Current scope

| Phase | Included |
|---|---|
| 1 – NLP engine | Text preprocessing, TF-IDF + cosine similarity, keyword extraction, skill extraction, explainable scoring |
| 2 – Backend | Flask REST API, PDF resume upload (PyMuPDF), MySQL storage (Flask-SQLAlchemy + PyMySQL), analysis history |

Frontend (Phase 3) is now included in `frontend/` (see below). Not built yet: authentication / user accounts, OCR for scanned
PDFs, non-technical job support.

Not used, by design: supervised ML training, deep learning, LLM or paid APIs.
**No model is trained anywhere in this project**; TF-IDF is fitted on the texts
it is given. All packages are free and open source.

## Frontend (React + Vite)

A React 18 single-page app in `frontend/` (JSX, custom CSS, React Router, Lucide icons; no TypeScript, Tailwind or UI kits).

| Page | Route | Data source |
|---|---|---|
| Dashboard | `/` | `GET /api/analyses` (stats are computed from your saved analyses) |
| New analysis | `/analyze` | `POST /api/analyze` (PDF as multipart, or pasted text as JSON) |
| Results | `/results/:id` | the analyze response, or `GET /api/analyses/:id` on reload |
| History | `/history` | `GET /api/analyses`, `DELETE /api/analyses/:id` |
| Analysis details | `/history/:id` | `GET /api/analyses/:id` |

Behaviour worth knowing:

- The backend has no search endpoint, so History loads all summaries (100 per request) and **searches and paginates in the browser**.
- Dashboard averages are computed from those same summaries; nothing is hard-coded.
- The sidebar health indicator reads `GET /api/health`.
- `skill_coverage` can be `null` (no known skills in the job description); the UI shows this instead of a number.
- The PDF size limit in the browser (`VITE_MAX_UPLOAD_MB`) should match `MAX_UPLOAD_MB` in the backend.

### Run backend and frontend together

Terminal 1, from the project root (see Installation and MySQL setup above):

```bash
source venv/bin/activate        # Windows: venv\Scripts\activate
python -m backend.app           # http://127.0.0.1:5000
```

Terminal 2:

```bash
cd frontend
cp .env.example .env            # Windows: copy .env.example .env
npm install
npm run dev                     # http://localhost:5173
```

In development the Vite dev server proxies `/api` to Flask (`VITE_PROXY_TARGET`), so no CORS setup is needed and `VITE_API_URL` stays empty.

### Production build

```bash
cd frontend
npm run build                   # output in frontend/dist
npm run preview
```

If you host `dist/` on a different origin from the API, set `VITE_API_URL` to the backend URL before building, and set `CORS_ORIGINS` (comma-separated origins) in the backend `.env`. If both are served from one domain behind a reverse proxy that forwards `/api` to Flask, leave `VITE_API_URL` empty.

### Frontend structure

```
frontend/
├── index.html, vite.config.js, package.json, .env.example
└── src/
    ├── main.jsx, App.jsx, hooks.js
    ├── services/api.js          reusable API client (errors normalised from {"error": {...}})
    ├── components/              Layout, Toast, ui (cards, ring, modal, states), AnalysisView
    ├── pages/                   Dashboard, Analyze, Results, History, AnalysisDetails, NotFound
    ├── styles/index.css         design system (CSS variables) and responsive rules
    └── utils/format.js
```


## NLP architecture

```
resume text ─┐                       ┌─ text similarity (TF-IDF + cosine, %) ──┐
             ├─ preprocessing ───────┤                                         ├─ scoring ─▶ overall score
job desc. ───┘                       └─ skill extraction ─ matched / missing ──┘            + matched/missing skills
                                      └─ keyword extraction ─ present / missing keywords
```

| Module (`backend/nlp_engine/`) | What it does |
|---|---|
| `preprocessing.py` | Lowercase, URL/e-mail removal, tokenization, stop-word removal, lemmatization. Keeps `C++`, `C#`, `.NET`, `Node.js`, `CI/CD`, `scikit-learn`; never lemmatizes technical words (`pandas` stays `pandas`). |
| `similarity.py` | TF-IDF (unigrams + bigrams) with scikit-learn, cosine similarity returned as a percentage. Optional `corpus` argument for a better IDF. |
| `keyword_extraction.py` | Extracts important JD keywords (unigram, bigram, trigram), prioritising known skills and technical-looking terms over generic words; reports which are present in / missing from the resume. |
| `skill_extraction.py` | Category-based skill dictionary, case-insensitive and synonym-aware matching with boundary rules (so `C` does not match `Cloud`, `Java` does not match `JavaScript`). Matched / missing skills and category-wise analysis. |
| `scoring.py` | Combines the two signals into one explainable score. |

### How the score is calculated

```
overall = 0.40 × text_similarity + 0.60 × skill_coverage
skill_coverage = (JD skills found in the resume) / (all JD skills) × 100
```

`calculate_match_score` returns `overall_score`, `text_similarity`,
`skill_coverage`, `matched_skills`, `missing_skills`, plus `category_analysis`,
the `weights` used, a one-line `explanation`, `notes` and the `disclaimer`.
If a job description contains no skill from the dictionary, coverage cannot be
computed; the score then uses text similarity only and says so in `notes`.

The 40/60 weights are an initial hand-chosen setting, not a tuned value.

### Extending the skill dictionary

Skills live in `SKILL_DICTIONARY` (`category → skill → synonyms`). Add to it
without touching any other code, for example for a non-technical field:

```python
from backend.nlp_engine import register_skill
register_skill("Accounting", "Tally", ["tally erp"])
```

## Backend architecture

```
 client ──HTTP/JSON──▶ routes/analysis_routes.py ──▶ services/pdf_extractor.py (PyMuPDF)
                              │                  └──▶ nlp_engine/  (Phase 1, unchanged)
                              └──▶ database/models.py + db.py ──▶ MySQL
```

| Module (`backend/`) | Responsibility |
|---|---|
| `app.py` | Application factory `create_app()`: loads config, initialises the database, registers the blueprint, turns every error into JSON. |
| `config.py` | Configuration from environment variables (`.env`). `Config` = MySQL, `TestingConfig` = in-memory SQLite for automated tests. |
| `routes/analysis_routes.py` | The five endpoints, request validation, calls the PDF extractor and the NLP engine, saves and reads analyses. |
| `routes/__init__.py` | `ApiError` and the standard error body. |
| `services/pdf_extractor.py` | PDF validation and text extraction; raises `PDFExtractionError` with a code and HTTP status. |
| `database/db.py` | The `SQLAlchemy` instance, schema creation and the connection check. The app **starts even if MySQL is down**; `/api/health` reports it and the tables are created as soon as MySQL is reachable. |
| `database/models.py` | The `Analysis` model. |
| `nlp_engine/` | The Phase 1 engine, used as is: `calculate_match_score()` for the scores and `analyze_keywords()` for the keywords. |

Every `/api/analyze` request runs: validate input → (extract PDF text) → check the
database is ready → NLP engine → save to MySQL → return the saved record.

## Folder structure

```
ResumeIQ/
├── .env.example                 template for your local .env (never commit .env)
├── .gitignore
├── README.md
├── backend/
│   ├── app.py                   Flask application factory
│   ├── config.py                configuration from environment variables
│   ├── requirements.txt
│   ├── routes/
│   │   ├── __init__.py          ApiError + error body
│   │   └── analysis_routes.py   /api endpoints
│   ├── services/
│   │   ├── __init__.py
│   │   └── pdf_extractor.py     PyMuPDF text extraction
│   ├── database/
│   │   ├── __init__.py
│   │   ├── db.py                SQLAlchemy instance, schema, health check
│   │   └── models.py            Analysis model
│   ├── nlp_engine/              Phase 1 (unchanged)
│   │   ├── __init__.py
│   │   ├── preprocessing.py
│   │   ├── similarity.py
│   │   ├── keyword_extraction.py
│   │   ├── skill_extraction.py
│   │   └── scoring.py
│   └── data/
│       ├── esco/                (empty; reserved for ESCO exports later)
│       └── processed/           (empty)
├── datasets/
│   └── sample_data/             6 synthetic resume / job-description pairs
└── tests/
    ├── test_nlp.py              NLP engine tests (Phase 1)
    └── test_backend.py          backend tests (Phase 2)
```

(`.gitkeep` files keep the empty `data/` folders in Git.)

## Sample data

`datasets/sample_data/` holds six resume / job-description pairs: Python
Developer, Java Backend Developer, Frontend Developer, Full Stack Developer,
Data Analyst and Machine Learning Engineer.

They are **synthetic**: written by hand for testing, with fictional people and
`example.com` addresses. They are not real resumes or real job postings, and
each resume intentionally lacks a few skills its job description asks for, so the
tests have known "missing skills" to check against.

**ESCO:** it is the preferred source for structured skill/occupation data, but
nothing from ESCO has been downloaded or used yet. The `backend/data/esco/`
folder is ready for it, e.g. to grow the skill dictionary later.

## Installation

Developed and tested only on Python 3.12 (scikit-learn 1.9.1, nltk 3.10.4, Flask 3.1.3,
Flask-SQLAlchemy 3.1.1, SQLAlchemy 2.1.9, PyMySQL 1.2.4, PyMuPDF 2.1) against MySQL 8.0.
Other versions, and the lower bounds in `requirements.txt`, have not been tested.

```bash
cd ResumeIQ
python -m venv venv
# Windows:  venv\Scripts\activate        macOS/Linux:  source venv/bin/activate
pip install -r backend/requirements.txt
```

Besides the Phase 1 packages this installs Flask, Flask-SQLAlchemy, PyMySQL,
PyMuPDF and python-dotenv, plus `cryptography`, which PyMySQL needs to log in to
MySQL 8 (the default `caching_sha2_password` authentication).

The two NLTK datasets (`stopwords`, `wordnet`) are downloaded automatically on
first use. To fetch them manually: `python -m nltk.downloader stopwords wordnet`.

## MySQL setup

1. Install MySQL 8.x (MySQL Installer on Windows, `brew install mysql` on macOS,
   `sudo apt install mysql-server` on Ubuntu) and make sure the server is running.
2. Create the database and a dedicated user. In the `mysql` client as an admin user:

```sql
CREATE DATABASE resumeiq CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'resumeiq_user'@'localhost' IDENTIFIED BY 'choose_a_strong_password';
GRANT ALL PRIVILEGES ON resumeiq.* TO 'resumeiq_user'@'localhost';
FLUSH PRIVILEGES;
```

3. Put the same user, password and database name in your `.env` (next section).

You do **not** create the table yourself: the `analyses` table is created
automatically by SQLAlchemy the first time the app can reach the database. There
are no migrations yet; if you later change the model, update the table manually.

## Environment variables

Copy the template and edit it. The real `.env` is ignored by Git.

```bash
cp .env.example .env        # Windows: copy .env.example .env
```

| Variable | Default | Meaning |
|---|---|---|
| `DB_HOST` | `localhost` | MySQL host |
| `DB_PORT` | `3306` | MySQL port |
| `DB_NAME` | `resumeiq` | Database name |
| `DB_USER` | *(none)* | MySQL user |
| `DB_PASSWORD` | *(none)* | MySQL password (special characters are fine) |
| `MAX_UPLOAD_MB` | `5` | Largest accepted PDF, in MB |
| `FLASK_HOST` / `FLASK_PORT` | `127.0.0.1` / `5000` | Where the dev server listens |
| `FLASK_DEBUG` | `0` | `1` enables Flask debug mode (development only) |

There are no default credentials: with `DB_USER` / `DB_PASSWORD` unset the app
still starts, logs a warning, and `/api/health` reports the database as unavailable.

## Running the backend

From the project root (the folder that contains `backend/`), with the virtual
environment active and `.env` filled in:

```bash
python -m backend.app
# or
flask --app backend.app run
```

The API is then at `http://127.0.0.1:5000`. Check it:

```bash
curl http://127.0.0.1:5000/api/health
```

(`python backend/app.py` does not work because the code uses package imports.)
The built-in server is for development; do not expose it to the internet. There is
**no authentication yet**, so anyone who can reach the server can read and delete
analyses, and CORS is off unless `CORS_ORIGINS` is set (see Frontend).

## API documentation

All responses are JSON. Success responses return the data directly. **Every error**
has the same shape:

```json
{"error": {"code": "missing_job_description", "message": "job_description is required.",
           "details": {"job_description": "job_description is required."}}}
```

(`details` appears only when there is more to say, e.g. several invalid fields.)

### GET /api/health

Application and database status. `200` when the database works, `503` otherwise.

```json
{"status": "ok", "app": "running",
 "database": {"status": "connected", "message": "Database connection is working."}}
```

When MySQL is unreachable: HTTP `503`, `"status": "degraded"`, `"database": {"status": "unavailable", ...}`.

### POST /api/analyze

Analyze a resume against a job description and save the result (HTTP `201`).

| Field | Type | Notes |
|---|---|---|
| `resume_text` | string | The resume as text. |
| `resume_file` | file (PDF) | Alternative to `resume_text`; `multipart/form-data` only. Max 5 MB, max 50 pages. |
| `job_description` | string | Required. |

Send **either** `resume_text` **or** `resume_file`, not both. Two ways to call it:

```bash
# JSON with pasted text
curl -X POST http://127.0.0.1:5000/api/analyze -H "Content-Type: application/json" \
  -d '{"resume_text": "Python developer. Built REST APIs with Django and Flask on MySQL. Used Git, GitHub and Docker.",
       "job_description": "We need Python, Django, PostgreSQL, Docker and AWS. Experience with REST APIs is a plus."}'

# PDF upload
curl -X POST http://127.0.0.1:5000/api/analyze \
  -F "resume_file=@my_resume.pdf" -F "job_description=<job description text>"
```

Real response of the first call (long fields shortened with `...`):

```json
{
  "id": 3,
  "resume_filename": null,
  "created_at": "2026-11-20T06:10:27Z",
  "overall_score": 46.78,
  "text_similarity": 16.94,
  "skill_coverage": 66.67,
  "matched_skills": ["Python", "Django", "REST APIs", "Docker"],
  "missing_skills": ["PostgreSQL", "AWS"],
  "category_analysis": {
    "Backend": {"required": 2, "matched": ["Django", "REST APIs"], "missing": [], "coverage": 100.0},
    "Databases": {"required": 1, "matched": [], "missing": ["PostgreSQL"], "coverage": 0.0},
    "Cloud and DevOps": {"required": 2, "matched": ["Docker"], "missing": ["AWS"], "coverage": 50.0},
    "Programming Languages": {"required": 1, "matched": ["Python"], "missing": [], "coverage": 100.0}
  },
  "extracted_keywords": [
    {"keyword": "REST APIs", "ngram_size": 2, "count": 1, "score": 3.0, "is_skill": true, "lemmas": ["rest", "apis"]},
    "..."
  ],
  "missing_keywords": ["AWS", "PostgreSQL"],
  "scoring_explanation": "overall = 40% x text similarity (16.94) + 60% x skill coverage (66.67) = 46.78",
  "weights": {"similarity": 0.4, "skills": 0.6},
  "notes": [],
  "resume_text": "Python developer. Built REST APIs ...",
  "job_description": "We need Python, Django, ...",
  "disclaimer": "This is an estimated compatibility score based on text similarity and technical-skill coverage. It is NOT the actual probability that an ATS will accept or reject a resume."
}
```

All fields come straight from the NLP engine (`calculate_match_score` and
`analyze_keywords`). `skill_coverage` is `null` when the job description mentions
no skill from the dictionary; `notes` then explains that only text similarity was used.
For a PDF, `resume_filename` is the sanitized upload name and `resume_text` is the
extracted text.

### GET /api/analyses

Saved analyses, newest first, as **summaries** (no full resume or job description
text; only a 100-character preview of the job description). Query parameters:
`limit` (1–100, default 20) and `offset` (default 0).

```json
{"total": 2, "limit": 1, "offset": 0,
 "analyses": [{"id": 3, "resume_filename": null, "created_at": "2026-11-20T06:10:27Z",
               "overall_score": 46.78, "text_similarity": 16.94, "skill_coverage": 66.67,
               "matched_skills_count": 4, "missing_skills_count": 2,
               "job_description_preview": "We need Python, Django, PostgreSQL, Docker and AWS. Experience with REST APIs is a plus."}]}
```

### GET /api/analyses/&lt;id&gt;

The complete saved analysis: the same object `POST /api/analyze` returned, including
`resume_text` and `job_description`. `404 analysis_not_found` if the id does not exist.

### DELETE /api/analyses/&lt;id&gt;

Deletes a saved analysis: `200 {"message": "Analysis deleted.", "id": 3}`, or `404`.

### Error codes

| HTTP | `code` | When |
|---|---|---|
| 400 | `missing_resume`, `empty_resume` | No resume given / resume text is blank |
| 400 | `missing_job_description`, `empty_job_description` | No job description / blank |
| 400 | `conflicting_resume_input` | Both `resume_text` and a PDF were sent |
| 400 | `invalid_json`, `invalid_field_type` | Body is not a JSON object / a text field is not a string |
| 400 | `invalid_pdf` | Empty, corrupt, or not really a PDF |
| 400 | `invalid_parameter` | Bad `limit` / `offset` |
| 404 | `analysis_not_found`, `not_found` | Unknown analysis id / unknown URL |
| 405 | `method_not_allowed` | Wrong HTTP method |
| 413 | `file_too_large` | Upload over the limit |
| 415 | `unsupported_file_type` | File is not a `.pdf` |
| 415 | `unsupported_media_type` | Request is neither JSON nor a form |
| 422 | `no_extractable_text` | PDF has no text layer (e.g. a scan; OCR is not supported) |
| 422 | `encrypted_pdf`, `too_many_pages` | Password-protected / more than 50 pages |
| 422 | `analysis_failed` | The NLP engine rejected the texts |
| 500 | `database_error`, `internal_error` | Unexpected failure (details are logged, not returned) |
| 503 | `database_unavailable` | MySQL cannot be reached |
| 503 | `nlp_resources_unavailable` | NLTK data missing and could not be downloaded |

## NLP engine quick example

```python
from backend.nlp_engine import calculate_match_score

result = calculate_match_score(resume_text, job_description_text)
print(result["overall_score"], result["matched_skills"], result["missing_skills"])
```

Run it from the `ResumeIQ` folder so `backend` is importable.

## Running the tests

From the project root:

```bash
# everything (NLP engine + backend)
python -m unittest discover -s tests -v

# only one part
python -m unittest tests.test_nlp -v
python -m unittest tests.test_backend -v
```

(`python -m pytest tests` also works if you install pytest.)

The backend tests use an **in-memory SQLite database**, so MySQL is not needed and
no real data is touched; database failures are simulated with mocks. PDFs are
generated on the fly with PyMuPDF. One extra test class runs the main flow against
a **real MySQL** server and is skipped by default. To run it, point the `DB_*`
variables at a throwaway database (it creates the table if needed and deletes the
rows it creates):

```bash
RESUMEIQ_TEST_MYSQL=1 DB_NAME=resumeiq_test python -m unittest tests.test_backend.TestMySQLIntegration -v
# Windows PowerShell:  $env:RESUMEIQ_TEST_MYSQL=1; python -m unittest tests.test_backend.TestMySQLIntegration -v
```

## Known limitations

- **Dictionary-based skills.** A skill that is not in the dictionary is not
  found. Skills are not inferred: a resume that says "Django" but never
  "Python" is reported as missing Python, and "JUnit" does not count as "Unit
  Testing".
- **Text similarity is lexical.** It compares shared wording, not meaning, and
  with only two documents the IDF part adds little.
- **Keyword extraction** finds unknown tools only if they are repeated or look
  technical (acronyms, camelCase, digits/symbols). A plain tool name mentioned
  once and missing from the dictionary is not picked up.
- A standalone capital `C` is read as the C language, so something like
  "Vitamin C" would be a false match. `Express` without `.js` is deliberately
  not matched.
- English text only. Resumes can be pasted text or a text-based PDF; DOCX and other formats are not supported.
- The score is an estimate and has not been validated against real hiring or
  ATS outcomes.
- **PDF input is text-based only.** Scanned or image-only PDFs are rejected (no
  OCR). For multi-column or heavily designed layouts the extracted text order may
  differ from the visual order, which can affect the text-similarity part.
- **MySQL `JSON` columns do not keep key order**, so the order of categories inside
  `category_analysis` (and of the keys in `weights` and in each keyword object) can
  differ from the NLP engine's. The content is identical.
- **No authentication and no migrations** yet. Resumes are stored as plain text
  in the database; treat the database accordingly.
