"""Deterministic ATS-readiness heuristics for CareerGap normalized resumes.

This is an architectural/readability assessment, not a prediction of any employer's
ATS result. Job-description matching is intentionally separate.
"""
from __future__ import annotations

import re
from collections import Counter
from typing import Any

MAX_SCORES = {
    "contact_completeness": 15,
    "resume_structure": 20,
    "content_quality": 15,
    "skills_quality_organization": 20,
    "ats_formatting_parseability": 15,
    "length_readability": 15,
}

# Deliberately small local taxonomy; do not import career_gap.py here.
CANONICAL_SKILLS = frozenset("""
python c c++ c# java javascript typescript go rust r sql pandas numpy scikit-learn
machine learning deep learning tensorflow pytorch keras matplotlib seaborn power bi
tableau excel fastapi flask django rest api graphql postgresql mysql mongodb sqlite
redis docker kubernetes aws azure google cloud git github linux html css react node.js
data structures algorithms object-oriented programming oop github actions pytest scipy
jupyter bash powershell pydantic natural language processing nlp computer vision llm
generative ai json vite
""".split())
# Preserve multiword skills separately because splitting a string would split them.
CANONICAL_SKILLS = frozenset(CANONICAL_SKILLS | {
    "machine learning", "deep learning", "power bi", "scikit-learn", "google cloud",
    "data structures", "object-oriented programming", "natural language processing",
    "computer vision", "generative ai", "rest api", "node.js", "github actions",
})
ALIASES = {
    "sklearn": "scikit-learn", "scikit learn": "scikit-learn", "ml": "machine learning",
    "np": "numpy", "pd": "pandas", "fast api": "fastapi", "restful api": "rest api",
    "postgres": "postgresql", "mongo": "mongodb", "amazon web services": "aws",
    "google cloud platform": "google cloud", "gcp": "google cloud", "dsa": "data structures",
    "object oriented programming": "object-oriented programming",
}
SKILL_GROUPS = {
    "Languages": {"python", "c", "c++", "c#", "java", "javascript", "typescript", "go", "rust", "r", "sql", "bash", "powershell"},
    "Backend": {"fastapi", "flask", "django", "rest api", "graphql", "node.js", "pydantic"},
    "Frontend": {"html", "css", "react", "javascript", "typescript", "vite"},
    "Data & ML": {"pandas", "numpy", "scikit-learn", "machine learning", "deep learning", "tensorflow", "pytorch", "keras", "matplotlib", "seaborn", "scipy", "jupyter", "nlp", "natural language processing", "computer vision", "llm", "generative ai"},
    "Databases": {"sql", "postgresql", "mysql", "mongodb", "sqlite", "redis"},
    "Cloud & DevOps": {"docker", "kubernetes", "aws", "azure", "google cloud", "linux", "git", "github", "github actions"},
    "Tools": {"excel", "power bi", "tableau", "pytest", "json"},
}
ACTION_VERBS = set("""
built created developed implemented designed engineered automated integrated deployed
optimized improved reduced increased delivered launched configured migrated maintained
tested debugged refactored analyzed evaluated trained tuned secured documented led owned
shipped generated processed transformed orchestrated monitored established streamlined
resolved enabled validated collaborated authored wrote programmed
""".split())
TECH_TERMS = set("""
api backend frontend database service system application model pipeline data algorithm
python java javascript typescript sql query endpoint authentication authorization deployment
cloud docker kubernetes server client framework library test testing architecture performance
latency throughput cache security automation workflow integration infrastructure machine
learning neural network classification regression dashboard analytics feature index schema
function module component react fastapi flask django pandas numpy postgresql mongodb redis
aws azure git github linux ci cd rest graphql vector embedding llm prompt inference training
evaluation monitoring logging
""".split())
FLUFF = re.compile(r"\b(responsible for|assisted with|helped with|worked on|participated in|team player|hard-working)\b", re.I)
IMPACT = re.compile(r"\b(improv\w*|reduc\w*|increas\w*|accelerat\w*|enabl\w*|streamlin\w*|simplif\w*|strengthen\w*|secur\w*|deliver\w*|support\w*|prevent\w*|resolv\w*|achiev\w*|result\w*|cut|boost\w*|lower\w*|reliable|reliability|scalable|scalability|maintainable|successfully)\b", re.I)
METRIC = re.compile(r"\b\d+(?:\.\d+)?\s*(?:%|percent|x\b|\$|users?\b|customers?\b|ms\b|milliseconds?\b|seconds?\b|minutes?\b|hours?\b|gb\b|tb\b|req/s\b|rps\b|requests?\b|records?\b|developers?\b|days?\b|weeks?\b)", re.I)
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MONTH_DATE = re.compile(r"^(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{4}$", re.I)
MONTHS = {"jan":"Jan","january":"Jan","feb":"Feb","february":"Feb","mar":"Mar","march":"Mar","apr":"Apr","april":"Apr","may":"May","jun":"Jun","june":"Jun","jul":"Jul","july":"Jul","aug":"Aug","august":"Aug","sep":"Sep","sept":"Sep","september":"Sep","oct":"Oct","october":"Oct","nov":"Nov","november":"Nov","dec":"Dec","december":"Dec"}


def _s(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _list(value: Any) -> list:
    return value if isinstance(value, list) else []


def _sections(document: dict) -> list[dict]:
    return [x for x in _list(document.get("sections")) if isinstance(x, dict)]


def _kind(section: dict) -> str:
    raw = _s(section.get("type") or section.get("heading")).lower()
    return {
        "work experience": "experience", "professional experience": "experience",
        "employment": "experience", "internships": "experience", "internship": "experience",
        "technical skills": "skills", "certificates": "certifications",
        "academic projects": "projects",
    }.get(raw, raw)


def _items(section: dict) -> list:
    return _list(section.get("items"))


def _date(value: Any) -> str:
    raw = _s(value)
    if raw.lower() in {"present", "current"}:
        return "Present"
    if re.fullmatch(r"\d{4}", raw):
        return raw
    match = MONTH_DATE.fullmatch(raw)
    if match:
        month, year = raw.split()
        return f"{MONTHS.get(month.lower(), month.title())} {year}"
    # Existing normalizer intentionally passes unknown forms through.
    return raw


def _skill_key(value: str) -> str:
    key = re.sub(r"\s+", " ", value.strip().lower())
    return ALIASES.get(key, key)


def _skill_groups(skills: list[str]) -> set[str]:
    groups = set()
    for skill in skills:
        key = _skill_key(skill)
        for group, terms in SKILL_GROUPS.items():
            if key in terms:
                groups.add(group)
    return groups


def _result(score: int, maximum: int, issues: list[str], fixes: list[str], note: str | None = None) -> dict:
    item = {"score": max(0, min(maximum, int(score))), "max_score": maximum,
            "issues": issues, "fixes": fixes}
    if note:
        item["note"] = note
    return item


def _contact(document: dict) -> dict:
    contact = document.get("contact") if isinstance(document.get("contact"), dict) else {}
    score, issues, fixes = 0, [], []
    checks = [
        (bool(_s(contact.get("full_name"))), 3, "Full name is missing.", "Add your full name to the resume header."),
        (bool(EMAIL.fullmatch(_s(contact.get("email")))), 3, "A valid email address is missing.", "Add a professional email address."),
        (len(re.sub(r"\D", "", _s(contact.get("phone")))) >= 7, 2, "A usable phone number is missing.", "Add a reachable phone number if you want phone contact."),
        (bool(_s(contact.get("location"))), 2, "Location is missing.", "Add your city or preferred work location if appropriate."),
    ]
    for passed, points, issue, fix in checks:
        if passed:
            score += points
        else:
            issues.append(issue); fixes.append(fix)
    links = [x for x in _list(contact.get("links")) if isinstance(x, dict) and _s(x.get("url"))]
    if links:
        score += 3
    else:
        issues.append("No professional link is provided.")
        fixes.append("Add a relevant professional profile or portfolio link when available.")
    if links and all(_s(x.get("label")) and _s(x.get("url")) for x in links):
        score += 2
    else:
        issues.append("Professional links need clear labels and URLs.")
        fixes.append("Give each professional link a descriptive label and complete URL.")
    return _result(score, 15, issues, fixes)


def _structure(document: dict) -> dict:
    by_type: dict[str, list] = {}
    for section in _sections(document):
        by_type.setdefault(_kind(section), []).extend(_items(section))
    experience = [x for x in by_type.get("experience", []) if isinstance(x, dict)]
    education = [x for x in by_type.get("education", []) if isinstance(x, dict)]
    projects = [x for x in by_type.get("projects", []) if isinstance(x, dict)]
    skills = [_s(x) for x in by_type.get("skills", []) if _s(x)]
    score, issues, fixes = 0, [], []

    exp_best = 0
    for item in experience:
        title, org = _s(item.get("title")), _s(item.get("organization"))
        dates = bool(_date(item.get("start")) and _date(item.get("end")))
        bullets = [x for x in _list(item.get("bullets")) if _s(x)]
        points = 8 if title and org and dates and len(bullets) >= 3 else 4 if title and org and dates and bullets else 2 if title or org else 0
        exp_best = max(exp_best, points)
    score += exp_best
    if not exp_best:
        issues.append("Experience entries are missing or incomplete.")
        fixes.append("If applicable, add role, organization, dates, and specific bullets. Students can demonstrate readiness through projects.")

    edu_best = 0
    for item in education:
        degree, school = _s(item.get("title")), _s(item.get("organization"))
        year_present = bool(re.search(r"\b(?:19|20)\d{2}\b", " ".join((_s(item.get("text")), _s(item.get("start")), _s(item.get("end"))))))
        points = 5 if degree and school and year_present else 3 if degree and school else 1 if degree or school else 0
        edu_best = max(edu_best, points)
    score += edu_best
    if not edu_best:
        issues.append("Education details are missing or incomplete.")
        fixes.append("Add your qualification and institution; include a graduation year when known.")

    if skills:
        score += 4 if _skill_groups(skills) else 2
    else:
        issues.append("No skills section is populated.")
        fixes.append("Add a concise skills section with skills you can demonstrate.")

    project_best, strong_projects = 0, 0
    projects_with_technical_bullets = 0
    for item in projects:
        title = _s(item.get("title"))
        description = _s(item.get("text") or item.get("summary"))
        bullets = " ".join(_s(x) for x in _list(item.get("bullets")))
        evidence = f"{description} {bullets}"
        tech = bool(_s(item.get("organization")) or re.search(r"\b(?:python|javascript|typescript|react|fastapi|sql|docker|api|using|built with)\b", evidence, re.I))
        technical_bullets = [
            bullet for bullet in _list(item.get("bullets"))
            if _s(bullet) and re.search(
                r"\b(?:python|javascript|typescript|react|fastapi|flask|django|sql|docker|api|database|algorithm|model|pipeline|testing|pytest|cloud|deployment)\b",
                bullet,
                re.I,
            )
        ]
        if technical_bullets:
            projects_with_technical_bullets += 1
        outcome = bool(IMPACT.search(evidence) or METRIC.search(evidence))
        if title and description and tech and outcome:
            project_best = max(project_best, 3); strong_projects += 1
        elif title and description and (tech or outcome):
            project_best = max(project_best, 1)
    if not projects:
        issues.append("No projects section is populated.")
        fixes.append("Add relevant projects that demonstrate applied skills, especially early in your career.")
    elif project_best == 0:
        issues.append("Projects need clearer technical details or outcomes.")
        fixes.append("Describe the project, the technologies used, and a truthful result or capability.")
    if exp_best == 0 and projects_with_technical_bullets >= 2:
        project_best = min(7, project_best + 4)
    score += project_best
    return _result(score, 20, issues, fixes)


def _content(document: dict) -> dict:
    bullets, descriptions = [], []
    for section in _sections(document):
        if _kind(section) not in {"experience", "projects", "custom"}:
            continue
        for item in _items(section):
            if not isinstance(item, dict):
                continue
            bullets.extend(_s(x) for x in _list(item.get("bullets")) if _s(x))
            desc = _s(item.get("text") or item.get("summary"))
            if desc:
                descriptions.append(desc)
    evidence = bullets or descriptions
    if not evidence:
        return _result(0, 15, ["No accomplishment text is available to assess."],
                       ["Add specific, truthful bullets about work completed or project capabilities."])
    total = len(evidence)
    action = sum(bool(re.match(r"^[\W_]*([A-Za-z]+)", b) and re.match(r"^[\W_]*([A-Za-z]+)", b).group(1).lower() in ACTION_VERBS) for b in evidence)
    impact = sum(bool(METRIC.search(b) or IMPACT.search(b)) for b in evidence)
    specific = sum(len(re.findall(r"\b\w+\b", b)) >= 12 and bool(set(re.findall(r"[a-zA-Z][a-zA-Z0-9+#.-]*", b.lower())) & TECH_TERMS) for b in evidence)
    fluff = sum(bool(FLUFF.search(b)) for b in evidence)
    score = (5 if action / total >= .8 else 3 if action / total >= .5 else 0)
    score += (5 if impact / total >= .6 else 3 if impact / total >= .3 else 0)
    score += (3 if specific / total >= .7 else 2 if specific / total >= .4 else 0)
    score += 2 if fluff == 0 else 0
    issues, fixes = [], []
    if action / total < .8:
        issues.append("Some bullets do not begin with clear action verbs.")
        fixes.append("Start bullets with accurate verbs such as built, implemented, automated, or tested.")
    if impact / total < .6:
        issues.append("Some bullets do not explain an outcome or capability.")
        fixes.append("Explain the truthful result or capability enabled; use numbers only when verifiable.")
    if specific / total < .7:
        issues.append("Some bullets lack technical detail or sufficient context.")
        fixes.append("Name the technology, system, method, or engineering task where accurate.")
    if fluff:
        issues.append("Generic phrases weaken some bullets.")
        fixes.append("Replace vague wording with the specific work you performed.")
    return _result(score, 15, issues, fixes)


def _skills(document: dict) -> dict:
    values = []
    for section in _sections(document):
        if _kind(section) == "skills":
            values.extend(_s(x) for x in _items(section) if _s(x))
    if not values:
        return _result(0, 20, ["Skills section is empty."], ["Add a focused list of skills you can demonstrate."])
    keys = [_skill_key(x) for x in values]
    counts = Counter(keys)
    duplicates = sum(n - 1 for n in counts.values() if n > 1)
    groups = _skill_groups(values)
    recognized = sum(key in CANONICAL_SKILLS for key in keys)
    score = 3
    score += 4 if len(groups) >= 2 else 2 if groups else 0
    score += max(0, 3 - duplicates)
    score += round(5 * recognized / len(values))
    score += max(0, 5 - max(0, len(values) - 25))
    issues, fixes = [], []
    if duplicates:
        issues.append(f"{duplicates} duplicate skill entries found.")
        fixes.append("Remove duplicate skills and use one consistent name for each technology.")
    if len(groups) < 2:
        issues.append("Skills are not grouped across multiple recognizable categories.")
        fixes.append("Group skills where useful; do not add skills solely to create categories.")
    if recognized < len(values):
        issues.append("Some skills are outside the scorer's limited canonical taxonomy; this does not mean they are invalid.")
        fixes.append("Check spelling and use conventional technology names where appropriate.")
    if len(values) > 25:
        issues.append("The skills list is unusually long.")
        fixes.append("Prioritize skills you can substantiate instead of listing everything.")
    return _result(score, 20, issues, fixes)


def _format() -> dict:
    return _result(15, 15, [], [], note="Architectural assessment based on CareerGap's known single-column, selectable-text renderer and structured resume schema. This is not a universal ATS compatibility guarantee.")


def _length(document: dict) -> dict:
    parts = [_s(document.get("summary"))]
    contact = document.get("contact") if isinstance(document.get("contact"), dict) else {}
    parts.extend(_s(contact.get(k)) for k in ("full_name", "email", "phone", "location"))
    for section in _sections(document):
        parts.extend((_s(section.get("heading")), _s(section.get("text"))))
        for item in _items(section):
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                parts.extend((_s(item.get("title")), _s(item.get("organization")), _s(item.get("text") or item.get("summary"))))
                parts.extend(_s(x) for x in _list(item.get("bullets")))
    count = len(re.findall(r"\b[\w+#.-]+\b", " ".join(x for x in parts if x)))
    score, issues, fixes = 15, [], []
    if count < 100:
        score -= 7; issues.append("Resume content is extremely sparse.")
        fixes.append("Add useful evidence about education, projects, experience, and skills without padding.")
    elif count < 200:
        score -= 5; issues.append("Resume content may be too sparse.")
        fixes.append("Add truthful specifics where important evidence is missing.")
    elif count < 300:
        score -= 2; issues.append("Check that the concise resume still includes essential evidence.")
        fixes.append("Ensure relevant projects and roles explain the work and its outcome.")
    elif count > 1200:
        score -= 7; issues.append("Resume contains a very large amount of text.")
        fixes.append("Remove repetition and prioritize relevant evidence.")
    elif count > 800:
        score -= 4; issues.append("Resume may be longer than necessary.")
        fixes.append("Trim repetitive bullets and keep details focused.")
    bullets = [ _s(b) for section in _sections(document) for item in _items(section) if isinstance(item, dict) for b in _list(item.get("bullets")) if _s(b)]
    long_bullets = sum(len(re.findall(r"\b\w+\b", b)) > 45 for b in bullets)
    if long_bullets:
        score -= min(3, long_bullets); issues.append(f"{long_bullets} bullet(s) are unusually long.")
        fixes.append("Shorten long bullets while preserving technical work and outcomes.")
    if len(re.findall(r"\b\w+\b", _s(document.get("summary")))) > 100:
        score -= 2; issues.append("Summary is unusually long.")
        fixes.append("Condense the summary and remove repetition.")
    return _result(score, 15, issues, fixes, note=f"Heuristic readability assessment based on approximately {count} words; thresholds are not ATS standards or page-count equivalents.")


def score_ats_readiness(document: dict) -> dict:
    """Score a normalized resume; JD matching is deliberately excluded."""
    if not isinstance(document, dict):
        document = {}
    categories = {
        "contact_completeness": _contact(document),
        "resume_structure": _structure(document),
        "content_quality": _content(document),
        "skills_quality_organization": _skills(document),
        "ats_formatting_parseability": _format(),
        "length_readability": _length(document),
    }
    score = max(0, min(100, sum(x["score"] for x in categories.values())))
    issues = [message for category in categories.values() for message in category["issues"]]
    fixes = list(dict.fromkeys(message for category in categories.values() for message in category["fixes"]))
    grade = "Excellent" if score >= 90 else "Strong" if score >= 80 else "Good" if score >= 70 else "Needs Improvement" if score >= 60 else "Weak"
    return {"score": score, "max_score": 100, "grade": grade, "categories": categories,
            "issues": issues, "fixes": fixes, "jd_match": None,
            "jd_match_note": "JD Match is separate and is not included in ATS Readiness."}
