
# ResumeIQ – ATS Resume & Job Description Matcher

ResumeIQ is an NLP-powered resume analysis application designed to help job seekers evaluate how well their resumes align with specific job descriptions.

Users can upload their resumes and provide a target job description to receive an estimated compatibility score, identify relevant skills, discover missing technical keywords, and understand areas where their resumes could be improved.

The goal is to make resume optimization more data-driven, transparent, and accessible.

## Key Features

### Resume Analysis
- Upload resumes in PDF format.
- Extract text from resumes automatically.
- Process resume content using Natural Language Processing.

### Job Description Matching
- Compare resume content against a target job description.
- Calculate an estimated compatibility score using TF-IDF and Cosine Similarity.
- Identify relevant keywords and technical skills.

### Skill Gap Analysis
- Highlight skills found in both the resume and job description.
- Identify missing or underrepresented skills.
- Provide suggestions for improving resume alignment.

### Analysis History
- Store previous resume analyses.
- Retrieve individual analysis results.
- Delete previous analysis records.

*Note: Features are being developed and integrated in stages. The final feature set will depend on implementation and testing.*

## Technology Stack

| Component | Technology |
|---|---|
| Programming Language | Python |
| Backend Framework | Flask |
| Natural Language Processing | NLTK |
| Text Vectorization | TF-IDF |
| Similarity Algorithm | Cosine Similarity |
| Data Processing | NumPy, Pandas, Scikit-learn |
| PDF Text Extraction | PyMuPDF |
| Database | MySQL |
| ORM | Flask-SQLAlchemy |
| Database Connector | PyMySQL |
| Frontend | HTML, CSS, JavaScript |
| Data Visualization | Chart.js |

## Project Structure

```text
ResumeIQ/
│
├── backend/
│   ├── app.py
│   ├── config.py
│   │
│   ├── nlp_engine/
│   │   ├── __init__.py
│   │   ├── preprocessing.py
│   │   ├── similarity.py
│   │   ├── keyword_extraction.py
│   │   ├── skill_extraction.py
│   │   └── scoring.py
│   │
│   ├── routes/
│   │   └── analysis_routes.py
│   │
│   ├── database/
│   │   ├── db.py
│   │   └── models.py
│   │
│   ├── services/
│   │   └── pdf_extractor.py
│   │
│   ├── data/
│   │   ├── esco/
│   │   └── processed/
│   │
│   └── requirements.txt
│
├── datasets/
│   └── sample_data/
│
├── tests/
│   ├── test_nlp.py
│   └── test_backend.py
│
├── .env.example
├── .gitignore
└── README.md
```

## Getting Started

### Prerequisites

Make sure you have the following installed:

- Python 3.10 or later
- MySQL Server 8.0
- MySQL Workbench (recommended)
- Git

### 1. Clone the Repository

```bash
git clone https://github.com/YOUR-USERNAME/ResumeIQ.git
```

```bash
cd ResumeIQ
```

### 2. Create a Virtual Environment

```bash
python -m venv venv
```

Activate it on Windows:

```powershell
.\venv\Scripts\Activate.ps1
```

### 3. Install Dependencies

```bash
pip install -r backend/requirements.txt
```

### 4. Configure NLTK

```bash
python -m nltk.downloader stopwords wordnet
```

### 5. Configure MySQL

- Start your MySQL Server.
- Create a database named `resumeiq`.
- Configure the database credentials in your `.env` file using `.env.example` as a reference.

### 6. Run the Application

The application startup and database initialization instructions will be finalized as backend and frontend integration is completed.

## How It Works

ResumeIQ follows a multi-stage NLP pipeline:

1. **Text Extraction:** Extract textual content from uploaded PDF resumes.
2. **Preprocessing:** Clean and normalize the extracted text.
3. **Vectorization:** Convert resume and job description text into numerical representations using TF-IDF.
4. **Similarity Calculation:** Apply Cosine Similarity to estimate textual relevance.
5. **Keyword Extraction:** Identify important keywords from the job description.
6. **Skill Extraction:** Identify technical skills present in the resume and job description.
7. **Scoring:** Generate an estimated compatibility score and skill-gap insights.
8. **Results:** Present the analysis in an accessible dashboard.

## Important Note About the Match Score

The ResumeIQ match score is an estimated measure of resume-to-job-description compatibility based on the implemented NLP techniques.

It does **not** represent the probability of passing an actual company's ATS screening process or guarantee selection for an interview.

## Development Roadmap

- [x] Initial project structure
- [x] NLP preprocessing pipeline
- [x] TF-IDF vectorization and cosine similarity
- [x] Keyword extraction
- [x] Technical skill extraction
- [x] Resume scoring logic
- [x] Flask backend foundation
- [x] PDF extraction functionality
- [x] Database integration foundation
- [ ] Complete frontend UI
- [ ] Integrate frontend with backend APIs
- [ ] Complete end-to-end MySQL integration
- [ ] Comprehensive testing
- [ ] Deployment
- [ ] Documentation and screenshots

## Future Enhancements

- Support for additional job domains beyond technical roles.
- More advanced NLP techniques and contextual semantic matching.
- Improved skill extraction and classification.
- Resume improvement recommendations.
- Enhanced analysis visualizations.

## Contribution

Contributions, suggestions, and improvements are welcome.

For major changes, please open an issue first to discuss what you would like to change.

## License

This project is currently developed for educational and portfolio purposes. A formal open-source license can be added separately.

---

**ResumeIQ** – Make every application count.
