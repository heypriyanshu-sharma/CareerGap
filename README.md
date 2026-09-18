# CareerGap

> An Evidence-Based Career Readiness Engine

CareerGap analyzes a candidate's resume against a job description to identify skill gaps, prioritize missing skills using available market evidence, find relevant learning resources, and determine how existing projects can be strengthened to demonstrate missing skills.

## What CareerGap Does

CareerGap is built around four core capabilities:

1. **Skill Gap Analysis**
   - Extracts skills from resumes and job descriptions
   - Identifies matched and missing skills
   - Calculates a skill-match score

2. **Market Evidence**
   - Uses recorded market-demand data to provide additional context when available
   - Keeps missing market evidence separate from zero demand

3. **Resource Intelligence**
   - Searches GitHub for relevant repositories and learning resources
   - Filters results for actual skill relevance

4. **Project Upgrade Intelligence**
   - Examines the candidate's existing projects
   - Determines whether missing skills genuinely fit those projects
   - Suggests meaningful upgrades when appropriate
   - Explicitly avoids forcing unrelated skills into projects

## Architecture

```text
Resume ──────────────┐
                     │
                     ▼
               Skill Gap Analysis
                     │
                     ▼
               Market Evidence
                     │
              Missing Skills
                     │
          ┌──────────┴──────────┐
          ▼                     ▼
 Resource Intelligence   Project Upgrade
          │                     │
          └──────────┬──────────┘
                     ▼
              Career Guidance
```

## Tech Stack

- **Python** — Core analysis engine
- **FastAPI** — Backend API
- **Pydantic** — Request validation
- **GitHub REST API** — Resource discovery
- **Google Gemini** — AI career advice
- **HTML, CSS, JavaScript** — Frontend
- **Pytest** — Automated testing
- **uv** — Python project and dependency management

## Project Structure

```text
CareerGap/
├── backend.py
├── career_gap.py
├── github_search.py
├── ai_advisor.py
├── ai_test.py
├── market_data.csv
├── resume.txt
├── job_description.txt
├── projects.json
├── pyproject.toml
├── uv.lock
│
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── script.js
│
└── tests/
    ├── test_career_gap.py
    └── test_backend.py
```

## Running Locally

### 1. Clone the repository

```bash
git clone https://github.com/heypriyanshu-sharma/CareerGap.git
cd CareerGap
```

### 2. Install dependencies

CareerGap uses `uv` for Python project and dependency management.

Install the project dependencies:

```bash
uv sync
```

### 3. Configure environment variables

Create a `.env` file in the project root:

```text
GEMINI_API_KEY=your_gemini_api_key
GITHUB_TOKEN=your_github_token
```

Never commit `.env` or expose API keys publicly.

### 4. Start the backend

```bash
python -m uvicorn backend:app --reload
```

The API will run at:

```text
http://127.0.0.1:8000
```

Interactive API documentation is available at:

```text
http://127.0.0.1:8000/docs
```

### 5. Start the frontend

Open another terminal:

```bash
cd frontend
python -m http.server 5500
```

Then open:

```text
http://localhost:5500
```

## Testing

Run the complete test suite:

```bash
python -m pytest -q
```
