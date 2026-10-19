"""
ATS JOB DESCRIPTION KEYWORD EXTRACTION
========================================

Extracts and ranks job-description keywords for ATS resume matching.

Design rules:
- Pure and deterministic: no I/O, no clock, no randomness, no network.
- Existing CareerGap skill logic is reused, never rewritten:
  `extract_skills()` supplies canonical technology names and
  `determine_importance()` supplies Required/Preferred/Mentioned.
- This module only DESCRIBES the job description. It never asserts that a
  candidate has (or lacks) any capability, and never generates advice, so
  it cannot produce an untruthful or unsupported recommendation.
"""

from __future__ import annotations

import re

from career_gap import determine_importance, extract_skills


# ============================================================
# NORMALIZATION
# ============================================================

# Keeps characters that appear inside real technology tokens so that
# "c++", "c#", "node.js" and "ci/cd" survive normalization intact.
_DISALLOWED_PATTERN = re.compile(
    r"[^a-z0-9+#./-]+"
)

# Punctuation that is only ever a bullet marker or sentence delimiter.
# Internal occurrences are preserved ("node.js"); edge ones are noise.
_EDGE_PUNCTUATION = ".-/"

# Sentence and line breaks. The lookbehind is case-insensitive in effect
# (A-Za-z0-9) because segmenting runs on raw text: a lowercase-only
# lookbehind would never split "PostgreSQL." and would let phrases leak
# across clause boundaries.
_SEGMENT_BREAK = re.compile(
    r"(?<=[A-Za-z0-9])\.(?=\s|$)|[;!?\n]"
)

# Bullet markers and heading decoration stripped from segment starts.
_LEADING_MARKERS = re.compile(
    r"^[\s*\-•·>–—|#]+"
)

_MIN_TERM_LENGTH = 3

_MAX_PHRASE_WORDS = 3

# determine_importance() matches terms as plain substrings, so very short
# single words ("go", "r") can match inside unrelated words and produce
# misleading importance. Phrases and longer single words are safe.
_MIN_IMPORTANCE_LENGTH = 6


def normalize_text(text) -> str:
    """
    Lowercase, strip punctuation outside technology tokens, collapse space.
    """

    if not isinstance(text, str):

        return ""

    lowered = text.lower()

    replaced = _DISALLOWED_PATTERN.sub(
        " ", lowered
    )

    return " ".join(replaced.split())


def _tokenize(normalized_text: str) -> list[str]:
    """
    Split normalized text into tokens, dropping empty and bullet-only tokens.

    "- strong python" becomes ["strong", "python"], while "node.js" and
    "c++" are preserved intact.
    """

    tokens = []

    for raw_token in normalized_text.split():

        token = raw_token.strip(_EDGE_PUNCTUATION)

        if token:

            tokens.append(token)

    return tokens


# ============================================================
# STOPWORDS AND JOB BOILERPLATE
# ============================================================

STOPWORDS = frozenset({
    "a", "about", "above", "across", "after", "all", "also", "an", "and",
    "any", "are", "as", "at", "be", "been", "being", "but", "by", "can",
    "could", "did", "do", "does", "doing", "done", "each", "etc", "even",
    "every", "few", "for", "from", "further", "had", "has", "have",
    "having", "he", "her", "here", "hers", "herself", "him", "himself",
    "his", "how", "i", "if", "in", "into", "is", "it", "its", "itself",
    "just", "may", "me", "might", "more", "most", "must", "my", "myself",
    "no", "nor", "not", "now", "of", "off", "on", "once", "only", "or",
    "other", "our", "ours", "ourselves", "out", "over", "own", "per",
    "same", "shall", "she", "should", "so", "some", "such", "than", "that",
    "the", "their", "theirs", "them", "themselves", "then", "there",
    "these", "they", "this", "those", "through", "to", "too", "under",
    "until", "up", "upon", "us", "very", "was", "we", "were", "what",
    "when", "where", "whether", "which", "while", "who", "whom", "why",
    "will", "with", "within", "would", "you", "your", "yours",
    "yourself", "yourselves", "willing",
})

# Common job-posting scaffolding. These are not English stopwords, but
# they describe the posting structure rather than the role's content and
# must never rank as keywords.
JOB_BOILERPLATE = frozenset({
    "applicant", "applicants", "apply", "benefits", "candidate",
    "candidates", "company", "consideration", "day", "days",
    "degree", "demonstrated", "description", "duties", "employer",
    "environment", "equal", "experience", "experienced", "expertise",
    "flexible", "growth", "identity", "job", "join", "knowledge",
    "like", "looking", "minimum", "nice", "opportunities",
    "opportunity", "orientation", "plus", "position", "preferred",
    "professional", "qualifications", "related", "remote",
    "require", "required", "requires", "requirements",
    "responsibilities", "responsibility", "role", "salary", "skills",
    "solutions", "status", "team", "teams", "understanding",
    "understand", "veteran", "disability", "gender", "work",
    "working", "workplace", "years", "new", "existing", "key",
    "today", "tomorrow", "yesterday", "soon", "later", "now",
    "then", "week", "weeks", "month", "months", "year", "time",
    "times", "people", "person", "someone", "something",
    # Section header words that should never be keywords
    "required", "requirements", "must", "must-have", "must-haves",
    "must have", "must haves", "mandatory", "essential",
    "qualifications", "preferred", "preferred skills", "nice to have",
    "nice-to-have", "nice to haves", "nice-to-have",
    "desired", "bonus", "good to have",
    "preferred qualifications", "desired qualifications",
    "qualifications", "must have", "must haves", "must-have", "must-haves",
    "must-have", "must-haves", "mandatory", "essential",
    "preferred", "preferred skills", "nice to have", "nice-to-have",
    "nice to haves", "nice-to-haves", "desired", "bonus",
    "good to have", "preferred qualifications", "desired qualifications",
    "qualifications", "must have", "must haves", "must-have", "must-haves",
})


# Words describing the candidate's traits or resume verbs. These are
# requirements language, never keywords to place on a resume.
CANDIDATE_TRAITS = frozenset({
    "adaptable", "able", "architect", "architecture", "build",
    "building", "collaborate", "collaborating", "collaborative",
    "communicating", "coordinating", "creating", "debugging",
    "delivering", "deploying", "design", "designing", "detail",
    "detailed", "developing", "driven", "drive", "endpoint",
    "endpoints", "ensure", "ensures", "exceed", "exceeds",
    "excellent", "executing", "fast", "generating", "good",
    "great", "handling", "helping", "honest", "implement",
    "implementing", "improving", "include", "includes",
    "including", "innovative", "involve", "involves",
    "involving", "leading", "maintaining", "manage", "managing",
    "meet", "meets", "mentoring", "motivated", "need", "needed",
    "needs", "organized", "ownership", "passionate",
    "preparing", "presenting", "proactive", "produce", "produces",
    "producing", "provide", "provides", "responsible", "reviewing",
    "scaling", "seeking", "seeks", "self-starter", "strong",
    "successful", "supporting", "testing", "training", "used",
    "use", "using", "want", "wanted", "work", "working", "write",
    "writing",
})

SCAFFOLDING = frozenset(
    STOPWORDS | JOB_BOILERPLATE | CANDIDATE_TRAITS
)


# ============================================================
# PHRASE GENERATION
# ============================================================

def _trim_stopwords(window: list[str]) -> list[str]:
    """Strip leading and trailing stopwords from a candidate window."""

    start = 0
    end = len(window)

    while start < end and window[start] in STOPWORDS:

        start += 1

    while end > start and window[end - 1] in STOPWORDS:

        end -= 1

    return window[start:end]


def _segment(job_text: str) -> list[str]:
    """
    Split a job description into independent clause segments.

    N-grams are only built inside a segment, so a phrase can never span a
    sentence or list-item boundary. Without this, unrelated adjacent items
    merge into meaningless phrases such as "rest apis postgresql".

    Periods are only treated as breaks when they follow a word, so
    technology names like "node.js" stay intact.
    """

    segments = []

    for chunk in _SEGMENT_BREAK.split(job_text):

        for part in chunk.split(","):

            cleaned = _LEADING_MARKERS.sub(
                "", part
            ).strip()

            if cleaned:

                segments.append(cleaned)

    return segments


def _collect_candidate_phrases(
    job_text: str,
    max_words: int = _MAX_PHRASE_WORDS,
) -> list[str]:
    """
    Collect every distinct stopword-trimmed 1..max_words phrase that
    appears inside a single clause.

    Only membership matters here; frequencies are always measured by
    occurrence count so that a single mention is never counted once per
    window size.
    """

    phrases: set[str] = set()

    for segment in _segment(job_text):

        normalized_segment = normalize_text(segment)

        tokens = _tokenize(normalized_segment)

        for size in range(1, max_words + 1):

            for start in range(len(tokens) - size + 1):

                trimmed = _trim_stopwords(
                    tokens[start:start + size]
                )

                if trimmed:

                    phrases.add(" ".join(trimmed))

    return sorted(phrases)


def _is_subphrase(phrase: str, other: str) -> bool:
    """True when `phrase` appears as contiguous words inside `other`."""

    phrase_words = phrase.split()

    other_words = other.split()

    if len(phrase_words) >= len(other_words):

        return False

    for start in range(
        len(other_words) - len(phrase_words) + 1
    ):

        window = other_words[start:start + len(phrase_words)]

        if window == phrase_words:

            return True

    return False


def _keep_maximal_phrases(phrases: list[str]) -> list[str]:
    """
    Drop phrases fully contained in a longer phrase.

    "machine learning" is more useful than the overlapping "machine" or
    "learning", so only the most specific phrase survives. Longest phrases
    are considered first, and ties break alphabetically for determinism.
    """

    kept: list[str] = []

    ordered = sorted(
        phrases,
        key=lambda phrase: (
            -len(phrase.split()),
            phrase,
        ),
    )

    for phrase in ordered:

        if any(
            _is_subphrase(phrase, accepted)
            for accepted in kept
        ):

            continue

        kept.append(phrase)

    return kept


# ============================================================
# NOISE FILTERING
# ============================================================

def _contains_letter(phrase: str) -> bool:
    """True when the phrase has at least one alphabetic character."""

    return any(
        character.isalpha()
        for character in phrase
    )


def _is_noise(phrase: str, canonical_skills: dict[str, str]) -> bool:
    """
    Decide whether a candidate phrase is unsuitable as a keyword.

    A phrase is rejected when it carries no letters (pure digits or
    punctuation) or when ANY word is stopword, posting boilerplate, or
    candidate-trait language. Rejecting on a single scaffolding word is
    deliberate: it removes verb-led noise such as "building rest apis"
    while keeping noun phrases such as "rest apis".
    """

    if phrase in canonical_skills:

        return False

    if not _contains_letter(phrase):

        return True

    words = phrase.split()

    if len(words) == 1 and len(words[0]) < _MIN_TERM_LENGTH:

        return True

    # A run of several known technologies is a list, not a phrase.
    # Without this, "Docker PostgreSQL Python" would swallow each
    # individual skill into one unusable keyword.
    if len(words) > 1 and all(
        word in canonical_skills
        or f"{word}s" in canonical_skills
        for word in words
    ):

        return True

    return any(
        word in SCAFFOLDING
        for word in words
    )


def _count_occurrences(
    normalized_text: str,
    normalized_phrase: str,
) -> int:
    """Count word-boundary occurrences of a phrase in normalized text."""

    if not normalized_text or not normalized_phrase:

        return 0

    pattern = re.compile(
        r"(?<![a-z0-9+#./-])"
        + re.escape(normalized_phrase)
        + r"(?![a-z0-9+#./-])"
    )

    return len(pattern.findall(normalized_text))


# ============================================================
# CANONICAL SKILL RESOLUTION
# ============================================================

def _resolve_canonical(
    phrase: str,
    canonical_skills: dict[str, str],
) -> str | None:
    """
    Map a phrase onto a canonical CareerGap skill name.

    Tries the phrase itself, then a naive singular form, so that
    "rest apis" resolves to the canonical "REST API". Returns None when
    the phrase has no canonical equivalent.
    """

    if phrase in canonical_skills:

        return canonical_skills[phrase]

    if phrase.endswith("s") and len(phrase) > 3:

        singular = phrase[:-1]

        if singular in canonical_skills:

            return canonical_skills[singular]

    if not phrase.endswith("s") and len(phrase) >= 3:

        plural = f"{phrase}s"

        if plural in canonical_skills:

            return canonical_skills[plural]

    return None


# ============================================================
# IMPORTANCE
# ============================================================

IMPORTANCE_RANK = {
    "Required": 0,
    "Preferred": 1,
    "Mentioned": 2,
}

_MENTIONED = "Mentioned"


def _importance_for(
    job_text: str,
    term: str,
    is_canonical: bool = False,
) -> str:
    """
    Reuse CareerGap's determine_importance().

    That function matches terms as plain substrings, so very short single
    words ("go", "r") can match inside unrelated words and report a
    misleading importance. Short terms are therefore only trusted when
    they are a known canonical skill (where "aws" matching "laws" is a far
    smaller risk than demoting a real requirement).
    """

    words = term.split()

    if len(words) == 1:

        if is_canonical and len(term) >= 3:

            is_reliable = True

        else:

            is_reliable = len(term) >= _MIN_IMPORTANCE_LENGTH

    else:

        is_reliable = True

    if not is_reliable:

        return _MENTIONED

    try:

        importance = determine_importance(
            job_text,
            term,
        )

    except Exception:

        return _MENTIONED

    if importance not in IMPORTANCE_RANK:

        return _MENTIONED

    return importance


# ============================================================
# PUBLIC API
# ============================================================

def extract_job_keywords(
    job_text,
    limit: int = 25,
) -> list[dict]:
    """
    Extract and rank ATS keywords from a job description.

    Returns a list of dictionaries, most relevant first:
        {
            "term": str,          # display form, canonical when known
            "normalized": str,    # lowercased comparison key
            "frequency": int,
            "importance": str,    # Required | Preferred | Mentioned
            "word_count": int,
        }

    Ranking is deterministic: importance, then frequency, then longer
    phrases, then alphabetically. Duplicates that resolve to the same
    canonical skill are collapsed to the highest-ranked instance.

    Returns an empty list for empty or non-string input, for text with no
    usable keywords, and for a non-positive limit.
    """

    if not isinstance(job_text, str) or not job_text.strip():

        return []

    if isinstance(limit, bool) or not isinstance(limit, int):

        limit = 25

    if limit <= 0:

        return []

    normalized = normalize_text(job_text)

    if not normalized:

        return []

    # Reuse existing CareerGap skill extraction for canonical naming.
    # extract_skills() does not match plural forms ("REST API" is not
    # found in "REST APIs"), so a plural alias is registered here rather
    # than modifying the shared extraction logic.
    canonical_skills: dict[str, str] = {}

    for skill in extract_skills(job_text):

        key = normalize_text(skill)

        if not key or key in canonical_skills:

            continue

        canonical_skills[key] = skill

        if (
            not key.endswith("s")
            and len(key) >= 3
            and f"{key}s" not in canonical_skills
        ):

            canonical_skills[f"{key}s"] = skill

    tokens = _tokenize(normalized)

    if not tokens:

        return []

    # Counting runs on the re-joined token stream so that sentence
    # punctuation ("apis.", "aws.") cannot break word boundaries.
    countable = " ".join(tokens)

    # Canonical skills always get a chance, even if the phrase generator
    # did not surface them.
    candidates = set(
        _collect_candidate_phrases(job_text)
    )

    candidates.update(canonical_skills)

    # Noise is removed BEFORE the maximal reduction. Otherwise an
    # informative short phrase is discarded merely because some longer
    # phrase containing it happens to be discarded too.
    usable = {
        phrase
        for phrase in candidates
        if not _is_noise(
            phrase,
            canonical_skills,
        )
    }

    results = []

    for phrase in _keep_maximal_phrases(
        sorted(usable)
    ):

        frequency = _count_occurrences(
            countable,
            phrase,
        )

        if not frequency:

            continue

        canonical = _resolve_canonical(
            phrase,
            canonical_skills,
        )

        term = canonical or phrase

        results.append({
            "term": term,
            "normalized": phrase,
            "frequency": frequency,
            "importance": _importance_for(
                job_text,
                term,
                canonical is not None,
            ),
            "word_count": len(phrase.split()),
        })

    results.sort(
        key=lambda item: (
            IMPORTANCE_RANK.get(
                item["importance"],
                len(IMPORTANCE_RANK),
            ),
            -item["frequency"],
            -item["word_count"],
            item["normalized"],
        )
    )

    # Collapse phrases that resolve to the same canonical skill.
    deduplicated = []

    seen_keys = set()

    for item in results:

        key = normalize_text(item["term"])

        if key in seen_keys:

            continue

        seen_keys.add(key)

        deduplicated.append(item)

    return deduplicated[:limit]


# ============================================================
# ATS RESUME SCORECARD
# ============================================================
#
# The ATS scorecard provides a deterministic, explainable score (0-100)
# assessing resume readiness for applicant tracking systems.
#
# Scoring dimensions (weights total 100):
#   1. Resume Completeness      - 25 pts  | Recognizable sections, contact info
#   2. Keyword Alignment        - 35 pts  | Match with job description keywords
#   3. Project & Impact Evidence - 25 pts | Projects, accomplishments, metrics
#   4. Clarity & Signal Quality - 15 pts  | No stuffing, clear structure
#
# Design rules:
# - Pure and deterministic: no I/O, no clock, no randomness, no network.
# - Reuses existing CareerGap and ATS keyword extraction logic.
# - Never rewards length, repetition, or keyword stuffing.
# - Does not penalize students lacking professional employment when
#   relevant project evidence exists.
# - Does not infer visual PDF formatting from plain text.
# - Identical inputs always produce identical results.
# ============================================================

# Score band labels
ATS_SCORE_BANDS = [
    (90, "Excellent"),
    (75, "Strong"),
    (60, "Fair"),
    (40, "Needs Improvement"),
    (0, "Weak"),
]


def _score_label(score: int) -> str:
    """Map a numeric score to its descriptive label."""
    for threshold, label in ATS_SCORE_BANDS:
        if score >= threshold:
            return label
    return "Weak"


def _extract_resume_skills(resume_text: str) -> set[str]:
    """Extract canonical skills from resume text using existing logic."""
    if not isinstance(resume_text, str) or not resume_text.strip():
        return set()
    return set(extract_skills(resume_text))


def _extract_job_keywords_set(job_text: str) -> set[str]:
    """Extract canonical job keywords from job description."""
    if not isinstance(job_text, str) or not job_text.strip():
        return set()
    keywords = extract_job_keywords(job_text, limit=50)
    return {kw["term"] for kw in keywords}


def _count_resume_sections(resume_text: str) -> dict[str, bool]:
    """
    Detect recognizable resume sections in the text.
    Returns a dict of section names to presence boolean.
    """
    if not isinstance(resume_text, str) or not resume_text.strip():
        return {}

    text_lower = resume_text.lower()
    sections = {
        "contact": _has_contact_info(text_lower),
        "summary": _has_summary_section(text_lower),
        "skills": _has_skills_section(text_lower),
        "experience": _has_experience_section(text_lower),
        "education": _has_education_section(text_lower),
        "projects": _has_projects_section(text_lower),
        "certifications": _has_certifications_section(text_lower),
    }
    return sections


def _has_contact_info(text_lower: str) -> bool:
    """Check for actual contact information in the header area, not project text."""
    # Only check the first portion of the resume (first ~15 lines / ~500 chars) for contact info
    header_lines = text_lower.split('\n')[:15]
    header_text = '\n'.join(header_lines)

    # Look for email pattern
    if re.search(r"[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}", header_text):
        return True
    # Look for phone pattern
    if re.search(r"(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}", header_text):
        return True
    # Look for explicit LinkedIn/profile URLs (not just "github" in project text)
    if re.search(r"linkedin\.com/in/[a-z0-9\-_]+", header_text):
        return True
    if re.search(r"github\.com/[a-z0-9\-_]+(?:/(?=[\s.,;!?]|$)|(?=[\s.,;!?]|$))", header_text):
        return True
    if re.search(r"portfolio\.[a-z]{2,}", header_text):
        return True
    return False


def _has_summary_section(text_lower: str) -> bool:
    """Check for explicit summary section header."""
    lines = text_lower.split('\n')
    for line in lines:
        stripped = line.strip()
        if stripped in ("summary", "professional summary", "objective", "profile", "about me", "career summary",
                        "summary:", "professional summary:", "objective:", "profile:", "about me:", "career summary:"):
            return True
        if stripped.startswith(("summary ", "professional summary ", "objective ", "profile ", "about me ", "career summary ")):
            return True
    return False


def _has_skills_section(text_lower: str) -> bool:
    """Check for explicit skills section header."""
    lines = text_lower.split('\n')
    for line in lines:
        stripped = line.strip()
        if stripped in ("skills", "technical skills", "technologies", "tech stack", "tools", "languages", "frameworks",
                        "skills:", "technical skills:", "technologies:", "tech stack:", "tools:", "languages:", "frameworks:"):
            return True
        if stripped.startswith(("skills ", "technical skills ", "technologies ", "tech stack ", "tools ", "languages ", "frameworks ")):
            return True
    return False


def _has_experience_section(text_lower: str) -> bool:
    """Check for explicit experience section header."""
    lines = text_lower.split('\n')
    for line in lines:
        stripped = line.strip()
        if stripped in ("experience", "work experience", "professional experience", "work history", "employment",
                        "experience:", "work experience:", "professional experience:", "work history:", "employment:"):
            return True
        if stripped.startswith(("experience ", "work experience ", "professional experience ", "work history ", "employment ")):
            return True
    return False


def _has_education_section(text_lower: str) -> bool:
    """Check for explicit education section header (not just the word 'degree')."""
    lines = text_lower.split('\n')
    for line in lines:
        stripped = line.strip()
        # Check for exact matches or prefix with space/colon
        if stripped in ("education", "education & certifications", "education & training", "academic background",
                        "education:", "education & certifications:", "education & training:", "academic background:",
                        "university", "college", "university:", "college:"):
            return True
        if stripped.startswith(("education ", "education & certifications ", "education & training ", "academic background ",
                                "education:", "university ", "college ", "university:", "college:")):
            return True
    return False


def _has_projects_section(text_lower: str) -> bool:
    """Check for explicit projects section header."""
    lines = text_lower.split('\n')
    for line in lines:
        stripped = line.strip()
        if stripped in ("projects", "project", "personal projects", "selected projects", "key projects", "notable projects",
                        "projects:", "project:", "personal projects:", "selected projects:", "key projects:", "notable projects:",
                        "portfolio", "personal project", "side project",
                        "portfolio:", "personal project:", "side project:"):
            return True
        if stripped.startswith(("projects ", "project ", "personal projects ", "selected projects ", "key projects ", "notable projects ",
                                "portfolio ", "personal project ", "side project ",
                                "portfolio:", "personal project:", "side project:")):
            return True
    return False


def _has_certifications_section(text_lower: str) -> bool:
    """Check for explicit certifications section header."""
    lines = text_lower.split('\n')
    for line in lines:
        stripped = line.strip()
        if stripped in ("certifications", "certification", "certificates", "certified", "license", "certifications & licenses",
                        "certifications:", "certification:", "certificates:", "certified:", "license:", "certifications & licenses:"):
            return True
        if stripped.startswith(("certifications ", "certification ", "certificates ", "certified ", "license ", "certifications & licenses ")):
            return True
    return False


# Need access to the original text for section detection
resume_text_lower = ""

def _count_resume_sections(resume_text: str) -> dict[str, bool]:
    """
    Detect recognizable resume sections in the text.
    Returns a dict of section names to presence boolean.
    """
    if not isinstance(resume_text, str) or not resume_text.strip():
        return {}

    global _resume_text_lower
    _resume_text_lower = resume_text.lower()

    sections = {
        "contact": _has_contact_info(_resume_text_lower),
        "summary": _has_summary_section(_resume_text_lower),
        "skills": _has_skills_section(_resume_text_lower),
        "experience": _has_experience_section(_resume_text_lower),
        "education": _has_education_section(_resume_text_lower),
        "projects": _has_projects_section(_resume_text_lower),
        "certifications": _has_certifications_section(_resume_text_lower),
    }
    return sections


def _calculate_completeness_score(resume_text: str, projects: list[dict] | None = None) -> tuple[int, list[str], list[str]]:
    """
    Calculate resume completeness score (0-25).
    Returns (score, strengths, weaknesses).
    """
    if not isinstance(resume_text, str) or not resume_text.strip():
        return 0, [], ["Resume text is empty or missing"]

    sections = _count_resume_sections(resume_text)

    # If projects are provided (structured data), consider projects section as present
    has_projects = projects is not None and len(projects) > 0
    if has_projects:
        sections["projects"] = True

    # Weight essential sections higher (contact, skills, experience, education = 4 pts each)
    # Optional sections (summary, projects, certifications) = 3 pts each
    # But if projects provided, don't require experience section for students
    has_projects_section = sections.get("projects", False)

    essential = {"contact", "skills", "education"}
    # Experience is essential unless projects are present (student case)
    if not has_projects_section:
        essential.add("experience")
    optional = {"summary", "projects", "certifications"}

    essential_present = sum(1 for s in essential if sections.get(s))
    optional_present = sum(1 for s in optional if sections.get(s))

    score = essential_present * 4 + optional_present * 3

    strengths = [name for name, v in sections.items() if v]
    weaknesses = [name for name in essential if not sections.get(name)]

    return min(score, 25), strengths, weaknesses


def _calculate_keyword_alignment_score(
    resume_text: str,
    job_text: str,
    job_keywords: list[dict]
) -> tuple[int, list[str], list[str]]:
    """
    Calculate keyword alignment score (0-35).
    Returns (score, strengths, weaknesses).
    """
    if not job_keywords:
        return 0, [], ["No job keywords extracted"]

    resume_skills = _extract_resume_skills(resume_text)
    if not resume_skills:
        return 0, [], ["No skills detected in resume"]

    # Extract required/preferred keywords using both canonical importance
    # and inline markers (Required:/Preferred:)
    required_keywords = set()
    preferred_keywords = set()
    mentioned_keywords = set()

    for kw in job_keywords:
        term = kw["term"]
        importance = kw.get("importance", "Mentioned")
        if importance == "Required":
            required_keywords.add(term)
        elif importance == "Preferred":
            preferred_keywords.add(term)
        else:
            mentioned_keywords.add(term)

    # Also check for inline Required:/Preferred: markers in job text
    if job_text:
        job_lower = job_text.lower()
        # Build lowercase sets for matching
        mentioned_lower = {k.lower() for k in mentioned_keywords}
        for kw in job_keywords:
            term = kw["term"]
            term_lower = term.lower()
            if term_lower in mentioned_lower:
                # Check for inline "Required: term" or "Preferred: term" patterns
                required_pattern = rf"required\s*[:\-]\s*.*?\b{re.escape(term_lower)}\b"
                preferred_pattern = rf"preferred\s*[:\-]\s*.*?\b{re.escape(term_lower)}\b"
                if re.search(required_pattern, job_lower):
                    required_keywords.add(term)
                    mentioned_keywords.discard(term)
                elif re.search(preferred_pattern, job_lower):
                    preferred_keywords.add(term)
                    mentioned_keywords.discard(term)

    all_important = required_keywords | preferred_keywords
    if not all_important:
        # No extractable required/preferred keywords - cannot assess alignment
        return 0, [], ["No required or preferred keywords found in job description"]

    matched_required = resume_skills & required_keywords
    matched_preferred = resume_skills & preferred_keywords
    matched_all = resume_skills & all_important

    # Scoring: Required keywords worth more
    required_weight = 0.7
    preferred_weight = 0.3

    if required_keywords and preferred_keywords:
        required_score = len(matched_required) / len(required_keywords)
        preferred_score = len(matched_preferred) / len(preferred_keywords)
        combined = required_weight * required_score + preferred_weight * preferred_score
    elif required_keywords:
        combined = len(matched_required) / len(required_keywords)
    elif preferred_keywords:
        combined = len(matched_preferred) / len(preferred_keywords)
    else:
        combined = 0.0

    score = round(combined * 35)

    strengths = []
    weaknesses = []

    if matched_required:
        strengths.append(f"Covers {len(matched_required)}/{len(required_keywords)} required keywords")
    else:
        weaknesses.append("Missing all required keywords from job description")

    if matched_preferred:
        strengths.append(f"Covers {len(matched_preferred)}/{len(preferred_keywords)} preferred keywords")
    elif preferred_keywords:
        weaknesses.append(f"Missing {len(preferred_keywords)} preferred keywords")

    missing_critical = required_keywords - resume_skills
    if missing_critical:
        weaknesses.append(f"Missing critical required skills: {', '.join(sorted(missing_critical)[:5])}")

    return min(score, 35), strengths, weaknesses


def _calculate_impact_score(
    resume_text: str,
    projects: list[dict] | None
) -> tuple[int, list[str], list[str]]:
    """
    Calculate project & impact evidence score (0-25).
    Returns (score, strengths, weaknesses).
    """
    if not isinstance(resume_text, str) or not resume_text.strip():
        return 0, [], ["Resume text is empty"]

    strengths = []
    weaknesses = []

    # Check for projects in resume text
    has_projects_section = _has_projects_section(resume_text.lower())
    # Check for actual GitHub/portfolio URLs (not just "git" word)
    has_github = _has_github_link(resume_text.lower())

    # Check for measurable impact signals - only credible quantitative evidence
    metric_signals = [
        r"\d+%", r"\d+\s*percent", r"increased by \d+", "decreased by \d+", "reduced by \d+", "improved by \d+",
        r"\$\d+", r"\d+\s*k\b", r"\d+\s*m\b", r"\d+\s*x\b", "scaled", "optimized",
        "accelerated", "delivered", "launched", "built", "designed", "architected"
    ]
    text_lower = resume_text.lower()
    # Only count as metrics if there's a number/quantity involved
    metric_patterns = [
        r"\d+%", r"\d+\s*percent",
        r"increased by \d+", r"decreased by \d+", r"reduced by \d+", r"improved by \d+",
        r"\$\d+", r"\d+\s*k\b", r"\d+\s*m\b", r"\d+\s*x\b",
        r"scaled (?:to|by|from|up)", r"optimized (?:by|to) \d+",
    ]
    has_metrics = any(re.search(pattern, text_lower) for pattern in metric_patterns)

    # Projects from structured data
    project_count = len(projects) if projects else 0
    project_bullets = 0
    if projects:
        for p in projects:
            bullets = p.get("bullets", [])
            project_bullets += len(bullets) if bullets else 0

    # Check if resume demonstrates relevant technical skills (even without projects section)
    resume_skills = _extract_resume_skills(resume_text)
    has_technical_skills = len(resume_skills) >= 3

    score = 0

    # Base points for having projects
    if has_projects_section or project_count > 0:
        score += 8
        strengths.append("Projects section present")

    # Award GitHub/portfolio points only for actual links
    has_github_link = _has_github_link(resume_text.lower())
    if has_github_link:
        score += 4
        strengths.append("GitHub/portfolio link present")

    if project_count >= 2:
        score += 5
        strengths.append(f"{project_count} projects documented")
    elif project_count == 1:
        score += 3
        strengths.append("1 project documented")
    else:
        weaknesses.append("No projects documented")

    # Only award metrics points for credible quantitative evidence
    if has_metrics:
        score += 5
        strengths.append("Measurable impact metrics present")
    else:
        weaknesses.append("No measurable impact metrics (%, $, scale, time/cost improvements) found")

    if project_bullets >= 4:
        score += 3
        strengths.append(f"{project_bullets} project bullet points")
    elif project_bullets > 0:
        score += 1

    # Give some credit for demonstrated technical skills even without projects section
    if has_technical_skills and not (has_projects_section or project_count > 0):
        score += 5
        strengths.append("Demonstrated relevant technical skills")

    return min(score, 25), strengths, weaknesses


def _has_github_link(text_lower: str) -> bool:
    """Check for actual GitHub/portfolio profile URLs in the header area, not project URLs."""
    # Only check the header area (first ~15 lines)
    header_lines = text_lower.split('\n')[:15]
    header_text = '\n'.join(header_lines)

    # Match profile URLs: github.com/username (not github.com/username/project)
    if re.search(r"github\.com/[a-z0-9\-_]+(?:/(?=[\s.,;!?]|$)|(?=[\s.,;!?]|$))", header_text):
        return True
    if re.search(r"gitlab\.com/[a-z0-9\-_]+(?:/(?=[\s.,;!?]|$)|(?=[\s.,;!?]|$))", header_text):
        return True
    if re.search(r"portfolio\.[a-z]{2,}", header_text):
        return True
    return False


def _calculate_clarity_score(resume_text: str) -> tuple[int, list[str], list[str]]:
    """
    Calculate clarity & signal quality score (0-15).
    Penalizes keyword stuffing, rewards clear structure.
    Returns (score, strengths, weaknesses).
    """
    if not isinstance(resume_text, str) or not resume_text.strip():
        return 0, [], ["Resume text is empty"]

    strengths = []
    weaknesses = []
    score = 15  # Start with full points, deduct for issues

    text_lower = resume_text.lower()
    word_count = len(resume_text.split())

    # Check for keyword stuffing: repeated same skill excessively
    # Use word-boundary matching to avoid false positives like "Git" in "GitHub"
    # Common tech skills have higher threshold since they naturally appear often
    COMMON_TECH_SKILLS = {
        "python", "sql", "java", "javascript", "typescript", "c", "c++", "c#",
        "go", "rust", "ruby", "php", "swift", "kotlin", "scala", "r",
        "html", "css", "react", "vue", "angular", "node.js", "nodejs", "express",
        "sql", "postgresql", "mysql", "mongodb", "redis", "sqlite", "oracle",
        "aws", "azure", "gcp", "google cloud", "docker", "kubernetes", "k8s",
        "git", "github", "gitlab", "bitbucket", "jenkins", "gitlab ci", "github actions",
        "linux", "unix", "bash", "shell", "powershell",
        "git", "github", "gitlab", "jira", "confluence", "slack", "trello",
        "rest api", "graphql", "grpc", "api", "microservices", "ci/cd", "ci cd"
    }

    skill_mentions = {}
    for skill in extract_skills(resume_text):
        # Use word-boundary regex to count whole-word occurrences
        pattern = rf"(?<![a-z0-9+#./-]){re.escape(skill.lower())}(?![a-z0-9+#./-])"
        count = len(re.findall(pattern, text_lower))
        # Higher threshold for common tech skills (threshold = 6 instead of 3)
        threshold = 6 if skill.lower() in COMMON_TECH_SKILLS else 3
        if count > threshold:
            skill_mentions[skill] = count

    if skill_mentions:
        # Deduct for stuffing (max -5)
        stuffing_count = sum(v - (6 if skill.lower() in COMMON_TECH_SKILLS else 3)
                             for skill, v in skill_mentions.items())
        deduction = min(5, stuffing_count)
        score -= deduction
        if deduction > 0:
            weaknesses.append(f"Possible keyword stuffing: {', '.join(skill_mentions.keys())}")

    # Check for very short resume
    if word_count < 100:
        score -= 3
        weaknesses.append("Resume appears very short (<100 words)")

    # Check for excessive length (potential padding)
    if word_count > 1500:
        score -= 2
        weaknesses.append("Resume is very long (>1500 words), may contain padding")

    # Check for section structure - use the improved section detection
    sections = _count_resume_sections(resume_text)
    sections_found = sum(1 for v in sections.values() if v)
    if sections_found >= 4:
        strengths.append("Well-structured with multiple sections")
    elif sections_found < 3:  # Only penalize if fewer than 3 sections
        score -= 2
        weaknesses.append("Few recognizable sections")

    # Check for contact info - use improved detection
    if _has_contact_info(resume_text.lower()):
        strengths.append("Contact information present")
    else:
        score -= 2
        weaknesses.append("Missing contact information (email, phone, LinkedIn, portfolio)")

    return max(0, score), strengths, weaknesses


def _has_github_link(text_lower: str) -> bool:
    """Check for actual GitHub/portfolio profile URLs in the header area, not project URLs."""
    # Only check the header area (first ~15 lines)
    header_lines = text_lower.split('\n')[:15]
    header_text = '\n'.join(header_lines)

    # Match profile URLs: github.com/username (not github.com/username/project)
    if re.search(r"github\.com/[a-z0-9\-_]+(?:/(?=[\s.,;!?]|$)|(?=[\s.,;!?]|$))", header_text):
        return True
    if re.search(r"gitlab\.com/[a-z0-9\-_]+(?:/(?=[\s.,;!?]|$)|(?=[\s.,;!?]|$))", header_text):
        return True
    if re.search(r"portfolio\.[a-z]{2,}", header_text):
        return True
    return False


def calculate_ats_scorecard(
    resume_text: str,
    job_text: str,
    job_keywords: list[dict],
    projects: list[dict] | None = None
) -> dict:
    """
    Calculate the ATS Resume Scorecard.

    Returns a dict with:
    - score: int (0-100)
    - label: str (score band label)
    - breakdown: list of dimension dicts with awarded/max points
    - reasons: list of 2-4 evidence-based deduction reasons
    - improvements: list of up to 3 prioritized actionable improvements
    - disclaimer: str
    """
    # Calculate each dimension
    completeness_score, c_str, c_weak = _calculate_completeness_score(resume_text, projects)
    keyword_score, k_str, k_weak = _calculate_keyword_alignment_score(resume_text, job_text, job_keywords)
    impact_score, i_str, i_weak = _calculate_impact_score(resume_text, projects)
    clarity_score, cl_str, cl_weak = _calculate_clarity_score(resume_text)

    total_score = completeness_score + keyword_score + impact_score + clarity_score
    total_score = max(0, min(100, total_score))

    # Prioritize weaknesses: keyword alignment and clarity are most actionable
    # Order: keyword alignment > clarity > impact > completeness
    priority_weaknesses = k_weak + cl_weak + i_weak + c_weak
    reasons = priority_weaknesses[:4]  # Top 4 deductions

    # Generate improvements based on weaknesses
    improvements = []
    if any("required keyword" in w.lower() or "required skill" in w.lower() for w in priority_weaknesses):
        improvements.append("Add missing required skills from the job description to your skills section or experience bullets.")
    if any("preferred keyword" in w.lower() or "preferred skill" in w.lower() for w in priority_weaknesses):
        improvements.append("Incorporate preferred skills from the job description into your experience or projects.")
    if any("metric" in w.lower() or "impact" in w.lower() for w in priority_weaknesses):
        improvements.append("Add measurable outcomes to your projects and experience (%, $, scale, time saved).")
    if any("project" in w.lower() for w in priority_weaknesses):
        improvements.append("Document relevant projects with clear descriptions, your role, and technologies used.")
    if any("contact" in w.lower() for w in priority_weaknesses):
        improvements.append("Add email, phone, LinkedIn, and/or GitHub to your contact section.")
    if any("section" in w.lower() for w in priority_weaknesses):
        improvements.append("Organize resume into clear sections: Summary, Skills, Experience, Education, Projects.")
    if any("stuffing" in w.lower() for w in priority_weaknesses):
        improvements.append("Avoid repeating the same skill excessively; focus on varied, relevant keywords.")

    # Ensure we have at least 1 and at most 3 improvements
    improvements = improvements[:3] if improvements else ["Review the job description and tailor your resume to its required and preferred skills."]

    # Build breakdown
    breakdown = [
        {"dimension": "Resume Completeness", "awarded": completeness_score, "max": 25, "description": "Presence of standard resume sections (contact, summary, skills, experience, education, projects, certifications)"},
        {"dimension": "Keyword Alignment", "awarded": keyword_score, "max": 35, "description": "Match between resume skills and job description required/preferred keywords"},
        {"dimension": "Project & Impact Evidence", "awarded": impact_score, "max": 25, "description": "Projects documented with measurable outcomes and technical details"},
        {"dimension": "Clarity & Signal Quality", "awarded": clarity_score, "max": 15, "description": "Clear structure, no keyword stuffing, contact info present"},
    ]

    return {
        "score": total_score,
        "label": _score_label(total_score),
        "breakdown": breakdown,
        "reasons": reasons,
        "improvements": improvements,
        "disclaimer": "This is a heuristic assessment based on observable text signals, not an official ATS vendor score. A high score does not guarantee an interview."
    }


# ============================================================
# PDF RESUME ANALYSIS
# ============================================================
#
# Analyzes the actual PDF bytes of a resume using pypdf text extraction.
# Separates analysis into dimensions that can be meaningfully assessed
# from extracted text vs. those requiring visual rendering.
#
# Design rules:
# - Pure and deterministic: no I/O, no clock, no randomness, no network.
# - Reuses existing ATS scoring logic where applicable.
# - Never claims to assess colors, typography, spacing, or page breaks
#   from extracted text alone.
# - Reports concrete evidence for each finding.
# - Does not predict hiring decisions or selection probabilities.
# ============================================================

PDF_ANALYSIS_DIMENSIONS = [
    {
        "id": "pdf_parsing",
        "name": "PDF Parsing & Text Extraction",
        "max": 20,
        "description": "Whether the PDF yields clean, structured text that ATS systems can read."
    },
    {
        "id": "job_alignment",
        "name": "Job Alignment",
        "max": 30,
        "description": "Match between resume skills and job description required/preferred keywords (when job provided)."
    },
    {
        "id": "section_completeness",
        "name": "Section Completeness & Evidence",
        "max": 30,
        "description": "Presence of standard sections, contact info, projects, and measurable outcomes."
    },
    {
        "id": "visual_layout",
        "name": "Visual Layout Risks (Text-Based)",
        "max": 20,
        "description": "Text-based indicators of layout issues: column bleeding, missing sections, text density. Cannot assess colors, fonts, or exact page breaks from extracted text."
    },
]


def _analyze_pdf_parsing_quality(extracted_text: str, page_count: int) -> tuple[int, list[str], list[str]]:
    """
    Assess PDF text extraction quality.
    Returns (score, strengths, weaknesses).
    """
    if not extracted_text or not extracted_text.strip():
        return 0, [], ["No text could be extracted from PDF (possibly scanned/image-only)"]

    strengths = []
    weaknesses = []
    score = 20  # Start with full points

    text_lower = extracted_text.lower()
    word_count = len(extracted_text.split())
    line_count = len(extracted_text.split('\n'))

    # Check for common extraction issues
    # 1. Excessive whitespace/newlines indicating column bleeding
    consecutive_newlines = max(len(match.group()) for match in re.finditer(r'\n{3,}', extracted_text)) if re.search(r'\n{3,}', extracted_text) else 0
    if consecutive_newlines > 5:
        score -= 3
        weaknesses.append("Excessive blank lines suggest multi-column layout bleeding in extraction")

    # 2. Very short lines (possible column fragments)
    lines = extracted_text.split('\n')
    short_lines = sum(1 for line in lines if len(line.strip()) < 20)
    if short_lines > len(lines) * 0.4:
        score -= 2
        weaknesses.append("High proportion of very short lines suggests column layout issues")

    # 3. Check for garbled characters (common in scanned PDFs)
    garbled_chars = sum(1 for c in extracted_text if ord(c) > 127 and c not in 'àáâãäåæçèéêëìíîïðñòóôõöøùúûüýþÿÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖØÙÚÛÜÝÞß')
    if garbled_chars > word_count * 0.05:
        score -= 3
        weaknesses.append("High non-ASCII character count suggests encoding or OCR issues")

    # 4. Very low word count
    if word_count < 100:
        score -= 5
        weaknesses.append(f"Very low extracted word count ({word_count}) - may be image-based or mostly graphics")

    # 5. Page count vs text volume
    if page_count > 1 and word_count < 200:
        score -= 3
        weaknesses.append(f"Multi-page PDF ({page_count} pages) but low text volume ({word_count} words)")

    # 6. Check for readable structure (section-like patterns)
    has_headers = any(len(line.strip()) < 50 and line.strip().isupper() for line in lines)
    if has_headers:
        strengths.append("Detected uppercase section headers in extracted text")

    # 7. Reasonable text density
    if word_count >= 300 and line_count >= 20:
        strengths.append(f"Good text extraction: {word_count} words across {line_count} lines")

    # 8. No major issues
    if score >= 18:
        strengths.append("Clean text extraction suitable for ATS parsing")

    return max(0, score), strengths, weaknesses


def _analyze_job_alignment(extracted_text: str, job_text: str, job_keywords: list[dict]) -> tuple[int, list[str], list[str]]:
    """
    Assess job alignment using existing ATS keyword logic.
    Returns (score, strengths, weaknesses).
    """
    if not job_keywords:
        return 0, [], ["No job description provided or no keywords extracted"]

    # Reuse existing keyword alignment logic
    from ats_match import _calculate_keyword_alignment_score
    score, strengths, weaknesses = _calculate_keyword_alignment_score(extracted_text, job_text, job_keywords)

    # Scale from 35 to 30 max
    scaled_score = round(score * 30 / 35) if score > 0 else 0

    return min(scaled_score, 30), strengths, weaknesses


def _analyze_section_completeness(extracted_text: str, projects: list[dict] | None = None) -> tuple[int, list[str], list[str]]:
    """
    Assess section completeness and evidence quality.
    Returns (score, strengths, weaknesses).
    """
    if not extracted_text or not extracted_text.strip():
        return 0, [], ["No text extracted to analyze sections"]

    from ats_match import _calculate_completeness_score, _calculate_impact_score

    completeness_score, c_str, c_weak = _calculate_completeness_score(extracted_text, projects)
    impact_score, i_str, i_weak = _calculate_impact_score(extracted_text, projects)

    # Combine completeness (25) + impact (25) = 50, scale to 30
    total_raw = completeness_score + impact_score
    scaled_score = round(total_raw * 30 / 50) if total_raw > 0 else 0

    strengths = c_str + i_str
    weaknesses = c_weak + i_weak

    return min(scaled_score, 30), strengths, weaknesses


def _analyze_visual_layout_risks(extracted_text: str, page_count: int) -> tuple[int, list[str], list[str]]:
    """
    Assess visual layout risks based on extracted text patterns.
    Cannot assess actual visual design from text alone.
    Returns (score, strengths, weaknesses).
    """
    if not extracted_text or not extracted_text.strip():
        return 0, [], ["Cannot assess layout - no text extracted"]

    strengths = []
    weaknesses = []
    score = 20  # Start with full points

    text_lower = extracted_text.lower()
    lines = extracted_text.split('\n')

    # 1. Check for potential column layout bleeding (text from multiple columns interleaved)
    # Heuristic: look for abrupt topic shifts within same line area
    # Simple check: many short fragments
    avg_line_length = sum(len(line.strip()) for line in lines) / max(1, len(lines))
    if avg_line_length < 30 and len(lines) > 30:
        score -= 3
        weaknesses.append("Short average line length suggests possible multi-column layout")

    # 2. Check for missing section boundaries
    # Look for section headers
    section_keywords = ['experience', 'education', 'skills', 'projects', 'summary', 'certifications', 'contact']
    found_sections = sum(1 for kw in section_keywords if kw in text_lower)
    if found_sections < 3:
        score -= 4
        weaknesses.append(f"Only {found_sections}/7 standard sections detected in extracted text")
    elif found_sections >= 5:
        strengths.append(f"Good section structure: {found_sections}/7 standard sections found")

    # 3. Check for contact info clustering (should be at top)
    contact_patterns = [
        r'[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}',
        r'(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',
        r'linkedin\.com/in/[a-z0-9\-_]+',
        r'github\.com/[a-z0-9\-_]+',
    ]
    header_text = '\n'.join(lines[:15])
    has_contact_in_header = any(re.search(pattern, header_text) for pattern in contact_patterns)
    if has_contact_in_header:
        strengths.append("Contact information appears in header area (first 15 lines)")
    else:
        score -= 3
        weaknesses.append("Contact information not clearly in header area")

    # 4. Text density check
    word_count = len(extracted_text.split())
    if word_count > 1500:
        score -= 2
        weaknesses.append("Very high word count may indicate dense text or padding")
    elif 300 <= word_count <= 1000:
        strengths.append("Reasonable text density for single-page resume")

    # 5. Check for bullet points (structure indicator)
    bullet_count = sum(1 for line in lines if re.match(r'^\s*[•\-\*]\s', line.strip()))
    if bullet_count >= 5:
        strengths.append(f"Bullet points detected ({bullet_count}) - good structure")
    elif bullet_count == 0:
        score -= 2
        weaknesses.append("No bullet points detected - may lack scannable structure")

    # 6. Cannot-assess disclaimer for visual aspects
    weaknesses.append("Note: Cannot assess colors, fonts, spacing, margins, or page breaks from extracted text alone")

    return max(0, score), strengths, weaknesses


def analyze_resume_pdf(
    pdf_bytes: bytes,
    job_text: str | None = None,
    projects: list[dict] | None = None
) -> dict:
    """
    Analyze a resume PDF for ATS readiness.

    Args:
        pdf_bytes: Raw PDF file bytes
        job_text: Optional job description text for job-specific alignment
        projects: Optional structured projects data (from Resume Builder)

    Returns:
        Dict with dimension scores, evidence, and overall assessment.
    """
    import io
    from pypdf import PdfReader

    # Extract text and get page count
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        page_count = len(reader.pages)

        text_parts = []
        for page in reader.pages:
            text = page.extract_text() or ""
            text_parts.append(text)
        extracted_text = "\n".join(text_parts)
    except Exception as e:
        return {
            "error": f"Failed to parse PDF: {str(e)}",
            "dimensions": [],
            "overall_score": 0,
            "overall_label": "Error",
            "disclaimer": "PDF could not be processed. Ensure it is a valid, text-based PDF (not scanned/image-only)."
        }

    # Extract job keywords if job provided
    job_keywords = []
    if job_text:
        job_keywords = extract_job_keywords(job_text)

    # Analyze each dimension
    pdf_parsing_score, pdf_str, pdf_weak = _analyze_pdf_parsing_quality(extracted_text, page_count)
    job_align_score, ja_str, ja_weak = _analyze_job_alignment(extracted_text, job_text or "", job_keywords)
    section_score, sec_str, sec_weak = _analyze_section_completeness(extracted_text, projects)
    visual_score, vis_str, vis_weak = _analyze_visual_layout_risks(extracted_text, page_count)

    # Build dimension results
    dimensions = []
    total_max = 0
    for dim_def, score, strengths, weaknesses in [
        (PDF_ANALYSIS_DIMENSIONS[0], pdf_parsing_score, pdf_str, pdf_weak),
        (PDF_ANALYSIS_DIMENSIONS[1], job_align_score, ja_str, ja_weak),
        (PDF_ANALYSIS_DIMENSIONS[2], section_score, sec_str, sec_weak),
        (PDF_ANALYSIS_DIMENSIONS[3], visual_score, vis_str, vis_weak),
    ]:
        # Skip job_alignment from overall score if no job provided
        if dim_def["id"] == "job_alignment" and not job_text:
            # Include dimension but mark as not assessed
            dimensions.append({
                "id": dim_def["id"],
                "name": dim_def["name"],
                "awarded": None,
                "max": dim_def["max"],
                "description": dim_def["description"],
                "strengths": [],
                "weaknesses": ["Not assessed - no job description provided"],
                "not_assessed": True,
            })
            continue

        total_max += dim_def["max"]
        dimensions.append({
            "id": dim_def["id"],
            "name": dim_def["name"],
            "awarded": score,
            "max": dim_def["max"],
            "description": dim_def["description"],
            "strengths": strengths,
            "weaknesses": weaknesses,
        })

    overall_score = sum(d["awarded"] for d in dimensions if d.get("awarded") is not None)
    overall_score = max(0, min(total_max, overall_score))

    # Score bands (relative to total_max)
    score_pct = (overall_score / total_max) * 100 if total_max > 0 else 0
    if score_pct >= 90:
        label = "Excellent"
    elif score_pct >= 75:
        label = "Strong"
    elif score_pct >= 60:
        label = "Fair"
    elif score_pct >= 40:
        label = "Needs Improvement"
    else:
        label = "Weak"

    # Aggregate strengths and weaknesses
    all_strengths = []
    all_weaknesses = []
    for d in dimensions:
        all_strengths.extend(d["strengths"])
        all_weaknesses.extend(d["weaknesses"])

    # Generate improvements
    improvements = []
    if any("required" in w.lower() or "keyword" in w.lower() for w in all_weaknesses):
        improvements.append("Add missing required skills from the job description to your resume.")
    if any("metric" in w.lower() or "impact" in w.lower() for w in all_weaknesses):
        improvements.append("Add measurable outcomes (%, $, scale, time saved) to your experience and projects.")
    if any("project" in w.lower() for w in all_weaknesses):
        improvements.append("Document relevant projects with clear descriptions, technologies, and your role.")
    if any("contact" in w.lower() for w in all_weaknesses):
        improvements.append("Add email, phone, LinkedIn, and/or GitHub profile to your contact section.")
    if any("section" in w.lower() for w in all_weaknesses):
        improvements.append("Organize resume into clear sections: Summary, Skills, Experience, Education, Projects.")
    if any("column" in w.lower() or "layout" in w.lower() for w in all_weaknesses):
        improvements.append("Use a single-column layout for better ATS parsing; avoid complex multi-column designs.")
    if any("scanned" in w.lower() or "image" in w.lower() or "extracted" in w.lower() for w in all_weaknesses):
        improvements.append("Ensure PDF is text-based (not scanned/image-only); export from your editor rather than scanning.")

    improvements = improvements[:4] if improvements else ["Review the analysis dimensions above and address any flagged issues."]

    # Disclaimer based on whether job was provided
    if job_text:
        disclaimer = (
            "This assessment evaluates PDF text extraction quality, job alignment, and text-based layout indicators. "
            "It cannot assess visual design (colors, fonts, spacing, page breaks) from extracted text. "
            "A high score does not guarantee an interview or ATS passage."
        )
    else:
        disclaimer = (
            "This assessment evaluates PDF text extraction quality and general resume structure only. "
            "No job-specific alignment was analyzed. "
            "It cannot assess visual design (colors, fonts, spacing, page breaks) from extracted text. "
            "A high score does not guarantee an interview or ATS passage."
        )

    return {
        "overall_score": overall_score,
        "overall_label": label,
        "overall_max": total_max,
        "score_percentage": round(score_pct, 1),
        "dimensions": dimensions,
        "aggregated_strengths": all_strengths,
        "aggregated_weaknesses": all_weaknesses,
        "improvements": improvements,
        "disclaimer": disclaimer,
        "extracted_text_preview": extracted_text[:500] + "..." if len(extracted_text) > 500 else extracted_text,
        "page_count": page_count,
        "word_count": len(extracted_text.split()),
        "job_description_provided": job_text is not None,
    }


import re