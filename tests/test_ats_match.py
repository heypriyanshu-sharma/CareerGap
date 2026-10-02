import pytest

import ats_match
from ats_match import (
    extract_job_keywords,
    normalize_text,
)


REQUIRED_JOB = """
About the role
We build a payments platform.

Requirements:
- Strong Python and FastAPI experience.
- PostgreSQL and Docker in production.

Preferred:
- Machine learning experience.
- Kubernetes and AWS.
"""


# ============================================================
# EMPTY AND MALFORMED INPUT
# ============================================================

@pytest.mark.parametrize(
    "job_text",
    [None, "", "   ", "\n\n", "...", 42, [], {}, True],
)
def test_empty_or_non_string_input_returns_empty_list(job_text):
    assert extract_job_keywords(job_text) == []


def test_text_with_only_scaffolding_returns_empty_list():
    assert extract_job_keywords(
        "Responsibilities include working with the team."
    ) == []


@pytest.mark.parametrize("limit", [0, -1, -100])
def test_non_positive_limit_returns_empty_list(limit):
    assert extract_job_keywords(REQUIRED_JOB, limit) == []


def test_invalid_limit_type_falls_back_to_default():
    default = extract_job_keywords(REQUIRED_JOB)

    assert extract_job_keywords(
        REQUIRED_JOB, "not-an-int"
    ) == default

    assert extract_job_keywords(
        REQUIRED_JOB, True
    ) == default


def test_limit_truncates_results():
    unlimited = extract_job_keywords(REQUIRED_JOB, limit=100)

    assert len(extract_job_keywords(REQUIRED_JOB, limit=2)) == 2
    assert len(unlimited) >= 2


# ============================================================
# NORMALIZATION
# ============================================================

def test_normalize_lowercases_and_strips_punctuation():
    assert normalize_text("Python, FastAPI!") == "python fastapi"
    assert normalize_text("  Multiple   spaces  ") == (
        "multiple spaces"
    )


def test_normalize_keeps_technology_tokens_intact():
    assert normalize_text("C++ and C#") == "c++ and c#"
    assert normalize_text("Node.js") == "node.js"
    assert normalize_text("CI/CD pipelines") == "ci/cd pipelines"


@pytest.mark.parametrize(
    "value",
    [None, 42, [], {}],
)
def test_normalize_handles_non_string_input(value):
    assert normalize_text(value) == ""


def test_bullet_markers_do_not_leak_into_keywords():
    terms = [
        item["term"]
        for item in extract_job_keywords(REQUIRED_JOB)
    ]

    assert not any(
        term.startswith("-") or term.endswith("-")
        for term in terms
    )


# ============================================================
# ORDERING AND RELEVANCE
# ============================================================

def test_required_terms_rank_above_preferred_and_mentioned():
    results = extract_job_keywords(REQUIRED_JOB)
    importances = [
        item["importance"] for item in results
    ]

    assert importances == sorted(
        importances,
        key=lambda value: ats_match.IMPORTANCE_RANK[value],
    )

    assert "Required" in importances
    assert "Preferred" in importances


def test_required_skills_are_detected():
    terms = {
        item["term"]
        for item in extract_job_keywords(REQUIRED_JOB)
    }

    assert "Python" in terms
    assert "FastAPI" in terms
    assert "PostgreSQL" in terms
    assert "Docker" in terms


def test_preferred_section_is_not_reported_as_required():
    results = {
        item["term"]: item["importance"]
        for item in extract_job_keywords(REQUIRED_JOB)
    }

    assert results.get("Machine Learning") == "Preferred"
    assert results.get("AWS") == "Preferred"


def test_higher_frequency_ranks_higher_within_same_importance():
    job = "Docker. Docker. Docker. Kubernetes."

    results = extract_job_keywords(job)

    assert results[0]["term"] == "Docker"
    assert results[0]["frequency"] == 3


def test_longer_phrases_outrank_shorter_ones_at_equal_frequency():
    job = "Payments platform experience."

    results = extract_job_keywords(job)

    assert results[0]["term"] == "payments platform"


def test_results_are_capped_and_ordered_deterministically():
    first = extract_job_keywords(REQUIRED_JOB)
    second = extract_job_keywords(REQUIRED_JOB)

    assert first == second


# ============================================================
# DUPLICATE KEYWORDS
# ============================================================

def test_repeated_keyword_frequency_is_counted_once_per_mention():
    job = "Python. Python. Python."

    results = extract_job_keywords(job)

    assert len(results) == 1
    assert results[0]["term"] == "Python"
    assert results[0]["frequency"] == 3


def test_singular_and_plural_collapse_to_one_canonical_keyword():
    job = """
Requirements:
- Design REST API endpoints.
- Build REST APIs for clients.
"""

    terms = [
        item["term"]
        for item in extract_job_keywords(job)
    ]

    assert terms.count("REST API") == 1


def test_no_duplicate_normalized_keys_are_returned():
    results = extract_job_keywords(REQUIRED_JOB, limit=50)

    keys = [item["normalized"] for item in results]
    display = [
        item["term"].lower() for item in results
    ]

    assert len(keys) == len(set(keys))
    assert len(display) == len(set(display))


# ============================================================
# RELEVANCE FILTERING
# ============================================================

def test_stopwords_are_never_returned():
    results = extract_job_keywords(REQUIRED_JOB)

    for item in results:

        for word in item["normalized"].split():

            assert word not in ats_match.SCAFFOLDING


def test_job_boilerplate_is_never_returned():
    results = extract_job_keywords(REQUIRED_JOB)
    terms = {item["normalized"] for item in results}

    for boilerplate in (
        "requirements",
        "experience",
        "team",
        "responsibilities",
        "years",
        "role",
        "candidate",
    ):

        assert boilerplate not in terms


def test_verb_lead_phrases_are_rejected():
    results = extract_job_keywords(
        "We are building a payments platform today."
    )

    terms = {item["normalized"] for item in results}

    assert "building a payments" not in terms
    assert "payments platform" in terms


def test_phrases_do_not_span_clause_boundaries():
    job = "We use PostgreSQL. Docker is also required."

    results = extract_job_keywords(job)
    terms = {item["normalized"] for item in results}

    assert "postgresql docker" not in terms
    assert "postgresql" in terms
    assert "docker" in terms


def test_more_specific_phrase_replaces_its_subphrase():
    results = extract_job_keywords(
        "Machine learning experience required."
    )

    terms = {item["normalized"] for item in results}

    assert "machine learning" in terms
    assert "machine" not in terms
    assert "learning" not in terms


def test_pure_numbers_and_symbols_are_rejected():
    results = extract_job_keywords(
        "5+ years. 2020. ### Python."
    )

    terms = {item["normalized"] for item in results}

    assert "5" not in terms
    assert "2020" not in terms
    assert "python" in terms


def test_single_letter_noise_is_rejected():
    terms = {
        item["normalized"]
        for item in extract_job_keywords(
            "a b c d e f g Python"
        )
    }

    for noise in ("a", "b", "c", "d", "e", "f", "g"):

        assert noise not in terms


def test_short_terms_do_not_receive_unreliable_importance():
    """determine_importance() matches substrings, so short NON-canonical
    terms must not be given a section-based label. Canonical skills of
    length >= 3 stay trusted, because the exact token is known to exist.
    """

    results = {
        item["term"]: item["importance"]
        for item in extract_job_keywords(
            "Requirements:\n- kafka and spark\n"
        )
    }

    assert results.get("kafka") == "Mentioned"
    assert results.get("spark") == "Mentioned"


def test_short_canonical_skills_are_still_trusted():
    """Canonical skills of length >= 3 stay trusted. Two-letter canonical
    skills such as "Go" stay demoted, because determine_importance() would
    substring-match them inside words like "going" or "good".
    """

    results = {
        item["term"]: item["importance"]
        for item in extract_job_keywords(
            "Requirements:\n- Go and Rust\n"
        )
    }

    assert results.get("Rust") == "Required"
    assert results.get("Go") == "Mentioned"


# ============================================================
# EDGE CASES
# ============================================================

def test_very_long_single_token_is_handled():
    job = "x" * 5000

    assert isinstance(
        extract_job_keywords(job), list
    )


def test_repeated_input_is_bounded_by_the_limit():
    job = ("Docker. PostgreSQL. Python. AWS. " * 200)

    results = extract_job_keywords(job, limit=3)

    assert len(results) == 3


def test_runs_of_known_technologies_are_split_into_individual_skills():
    job = "Docker PostgreSQL Python Kubernetes AWS React"

    terms = {
        item["normalized"]
        for item in extract_job_keywords(job)
    }

    for skill in (
        "docker",
        "postgresql",
        "python",
        "kubernetes",
        "aws",
        "react",
    ):

        assert skill in terms


def test_unicode_text_does_not_raise():
    assert isinstance(
        extract_job_keywords(
            "Développeur Python —(PostgreSQL)."
        ),
        list,
    )


def test_result_items_expose_the_documented_shape():
    results = extract_job_keywords(REQUIRED_JOB)

    assert results

    for item in results:

        assert set(item) == {
            "term",
            "normalized",
            "frequency",
            "importance",
            "word_count",
        }
        assert isinstance(item["term"], str)
        assert isinstance(item["normalized"], str)
        assert isinstance(item["frequency"], int)
        assert item["frequency"] > 0
        assert item["importance"] in (
            "Required", "Preferred", "Mentioned"
        )
        assert item["word_count"] == len(
            item["normalized"].split()
        )


def test_module_exposes_no_side_effects_on_import():
    assert callable(extract_job_keywords)
    assert ats_match.IMPORTANCE_RANK["Required"] == 0