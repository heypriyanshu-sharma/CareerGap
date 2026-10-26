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
- **Supabase** — Postgres database (with Row Level Security) and hosted authentication
- **GitHub REST API** — Resource discovery
- **Google Gemini** — AI career advice
- **slowapi** — Per-endpoint API rate limiting
- **HTML, CSS, JavaScript** — Frontend
- **Pytest** — Automated testing
- **uv** — Python project and dependency management

## Project Structure

```text
CareerGap/
├── backend.py                # FastAPI app: routes, CORS, rate limits, size limits
├── auth.py                   # Supabase JWT verification for data endpoints
├── database.py               # PostgREST access (resumes, analyses, interviews)
├── career_gap.py             # Skill-gap analysis engine
├── ats_match.py              # ATS keyword matching
├── ats_readiness.py          # ATS readiness scoring
├── github_search.py          # GitHub resource discovery
├── ai_advisor.py             # Gemini-based AI career advice
├── resume_builder.py         # Resume builder engine
├── resume_pdf.py             # Resume PDF generation
├── resume_serialize.py       # Resume load/save helpers
├── file_upload.py            # Upload validation and text extraction
├── conftest.py               # Shared pytest configuration
├── market_data.csv           # Recorded market-demand data
├── projects.json             # Starter project catalog
├── pyproject.toml, uv.lock, requirements.txt
│
├── frontend/
│   ├── index.html, style.css, script.js     # Main application
│   ├── login.html, signup.html, login.js, signup.js   # Supabase Auth pages
│   ├── auth-guard.js, supabase-config.js    # Client-side auth helpers
│   ├── profile.html, settings.html, reset-password.html (+ their JS/CSS)
│
├── supabase/
│   └── migrations/           # SQL schema proposals (applied manually)
│
└── tests/
    └── (25 pytest suites covering backend, database,
         analysis, ATS, resume builder, and frontend behavior)
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
SUPABASE_URL=your_supabase_project_url
SUPABASE_PUBLISHABLE_KEY=your_supabase_publishable_key
SUPABASE_SERVICE_KEY=your_supabase_service_role_key
GEMINI_API_KEY=your_gemini_api_key
GITHUB_TOKEN=your_github_token
```

Notes:

- **`SUPABASE_URL` and `SUPABASE_PUBLISHABLE_KEY` are required** — the backend refuses to start without them.
- **`SUPABASE_SERVICE_KEY`** enables submitting interview answers and account deletion (server-side privileged operations). The server starts without it, but those features return an error.
- **`GEMINI_MODEL`** is optional; a sensible default is used when it is not set.
- **`GEMINI_API_KEY`** and **`GITHUB_TOKEN`** enable AI advice and GitHub resource search, respectively.

**Secrets-file precedence:** the backend modules first load an optional developer-local secrets file (found via `SECRETS_PATH` in `backend.py` and `auth.py`, overridable with the `CAREERGAP_SECRETS_PATH` environment variable) and then this root `.env`. On machines where that external file does not exist, the root `.env` documented above is what gets loaded. If you edit the root `.env` on the developer machine and nothing changes, check whether the external secrets file is shadowing it.

Never commit `.env` or expose API keys publicly.

### 4. Start the backend

```bash
python -m uvicorn backend:app --reload
```

The API will run at:

```text
http://127.0.0.1:8000
```

On Render, the start command must bind to `0.0.0.0` on the port from
the `$PORT` environment variable (default `10000`); if Render cannot
detect your bound port, the deploy fails:

```bash
python -m uvicorn backend:app --host 0.0.0.0 --port $PORT
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

## Security

- **Authentication** — Every data endpoint requires a Supabase Auth JWT (`HTTPBearer`). Identity is always derived server-side from the verified token's claims; user IDs sent in a client payload are never trusted.
- **Data isolation** — PostgreSQL Row Level Security (owner-only policies) is the enforcement authority for all user tables. On top of RLS, application-level PostgREST queries also scope every request with an explicit `user_id=eq.<token-subject>` filter.
- **Service-role key discipline** — `SUPABASE_SERVICE_KEY` bypasses RLS. It is used server-side only, and only for privileged operations: the `SECURITY DEFINER` interview RPC `submit_interview_answers` (execute granted solely to `service_role`) and account deletion. It must never be embedded in or shipped to the frontend.
- **Rate limiting** — Endpoints are rate-limited with slowapi (HTTP 429 when exceeded), e.g. `/upload` and `/interview/generate` at 5/minute, `/analyze` and other analysis, ATS, and interview endpoints at 10/minute, `/auth/delete-account` at 3/minute, and resume create/update routes at 30/minute.
- **Request size limits** — Uploaded files are capped at 5 MB with extracted text capped at 50,000 characters; resume-write endpoints additionally enforce a 256 KB body limit via middleware.
- **CORS** — A fixed allowlist only: the local development origins (`http://localhost:5500`, `http://127.0.0.1:5500`) and the production origin `https://careergap.pages.dev`.
- **Migrations are manual** — SQL files under `supabase/migrations/` are proposals intended to be reviewed and applied manually (dashboard SQL editor or `supabase db push`); nothing in the repo applies them automatically. The `career_analyses` table is managed directly in the dashboard and is deliberately excluded from repo migrations (guarded by automated tests).

## Testing

Run the complete test suite:

```bash
python -m pytest -q
```
