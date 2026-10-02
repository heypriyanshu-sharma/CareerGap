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