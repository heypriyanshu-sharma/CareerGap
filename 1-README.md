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
- **Groq** - AI career advice and Interview Studio
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
├── ai_advisor.py             # Groq-based AI career advice
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
GROQ_API_KEY=your_groq_api_key
GITHUB_TOKEN=your_github_token
```

Notes:

- **`SUPABASE_URL` and `SUPABASE_PUBLISHABLE_KEY` are required** — the backend refuses to start without them.
- **`SUPABASE_SERVICE_KEY`** enables submitting interview answers and account deletion (server-side privileged operations). The server starts without it, but those features return an error.
- **`GROQ_MODEL`** is optional; a sensible default is used when it is not set.
- **`GROQ_API_KEY`** and **`GITHUB_TOKEN`** enable AI advice and GitHub resource search, respectively.

**Secrets-file precedence:** `backend.py`, `auth.py`, and `ai_advisor.py` load an optional external secrets file only when the `CAREERGAP_SECRETS_PATH` environment variable is set; there is no built-in default path. When it is unset (or points at a missing file), the project-root `.env` documented above is loaded. Set `CAREERGAP_SECRETS_PATH` if you keep secrets outside the repository — no personal filesystem paths are compiled into the code.

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

The interactive docs are disabled in production: Render sets
`RENDER=true`, which turns off `/docs`, `/redoc` and `/openapi.json`
there. Local development keeps them enabled.

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
- **Rate limiting** — Endpoints are rate-limited with slowapi (HTTP 429 when exceeded):
  - `/upload` and `/interview/generate` — 5/minute
  - `/analyze`, `/ats/analyze-resume`, `/interview/{id}/answer`, `/interview/{id}` (DELETE), `/auth/profile` — 10/minute
  - `/auth/delete-account` — 3/minute
  - `/resumes` (POST/PUT), `/interview/{id}` (GET) — 30/minute

  - **Verified locally (pytest):** `get_client_key` logic (9 unit tests), limiter wiring (`limiter._key_func == get_client_key`), per-client isolation via `CF-Connecting-IP` (integration test). All 807 tests pass.
  - **Deferred live verification:** Production Cloudflare/Render header handling has not been end-to-end tested. The following are **assumptions, not confirmed facts**:
    1. Cloudflare overwrites `CF-Connecting-IP` with the true client IP (Render's DDoS protection).
    2. `X-Forwarded-For` is not trusted as a rate-limit key (Render appends without clearing client-supplied values).
    3. Render is configured for one instance with autoscaling off; runtime single-instance behavior is unverified.
    4. Fixed-window reset behaves as expected across deploys.

  A live spoof test requires an authenticated production request; no automated token path exists without browser automation or a debug endpoint. Documented here to track the gap.

- **Request size limits** — Uploaded files are capped at 5 MB with extracted text capped at 50,000 characters; resume-write endpoints additionally enforce a 256 KB body limit via middleware.
- **CORS** — A fixed allowlist only: the local development origins (`http://localhost:5500`, `http://127.0.0.1:5500`) and the production origin `https://careergap.pages.dev`.
- **Security headers** — `frontend/_headers` sets them for Cloudflare Pages: a report-only Content-Security-Policy, `X-Frame-Options: DENY`, a `Permissions-Policy` that denies camera/microphone/geolocation and similar features, and HSTS (`max-age=31536000; includeSubDomains`). `frame-ancestors` is ignored in report-only mode, so `X-Frame-Options` is the clickjacking control until the CSP is enforced in a follow-up. The inline theme bootstrap in `index.html` is allowed by SHA-256 hash, not `'unsafe-inline'`.
- **Migrations are manual** — SQL files under `supabase/migrations/` are proposals intended to be reviewed and applied manually (dashboard SQL editor or `supabase db push`); nothing in the repo applies them automatically. The `career_analyses` table is managed directly in the dashboard and is deliberately excluded from repo migrations (guarded by automated tests).

## Testing

Run the complete test suite:

```bash
python -m pytest -q
```

### Groq provider migration

The server uses Groq's official Python client with `openai/gpt-oss-120b` as
its default. `GROQ_MODEL` can override that model, but must support low
reasoning effort and JSON object mode for Interview Studio. There is no
Gemini fallback. Keep `GROQ_API_KEY` server-side only.

The adapter fixes the API destination, disables redirects and retries,
limits responses to 1 MiB, refuses compression, and uses 25-second socket
timeouts plus a body deadline check. This is not a hard process-wide
25-second deadline. Existing Interview Studio request timeouts remain.
`GROQ_CUSTOM_HEADERS` is refused. Do not enable Groq SDK body debug logging.

Questions must match quick/full category counts exactly. Feedback is
validated before persistence; malformed or out-of-range output fails
without saving a partial result. API response field names are unchanged,
but malformed upstream output is rejected more strictly. Provider failures
use fixed safe messages, with 429 for rate limits, 503 for missing key or
access/connection problems, 504 for timeouts and 502 for other upstream
failures. Career advice remains optional and does not fail core analysis.

Before deployment, verify the final callers against the provider using
fictional inputs in an isolated environment. Offline tests do not establish
provider access or production readiness.
