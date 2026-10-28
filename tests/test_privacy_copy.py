"""Regression tests for the Item 5 privacy copy.

These assert user-facing wording only. They do not assert the storage
behavior itself; the data flows are covered by the backend and
database tests.
"""

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "frontend" / "index.html"
SETTINGS = ROOT / "frontend" / "settings.html"

ATS_DESCRIPTION = re.compile(
    r'<span class="ats-source-desc">(Analyze a PDF\..*?)</span>',
    re.S,
)

DELETE_MODAL = re.compile(
    r'<p id="delete-modal-text">(.*?)</p>',
    re.S,
)

DELETE_HINT = re.compile(
    r'<p class="account-row-label">\s*Delete account\s*</p>\s*'
    r'<p class="account-row-hint">(.*?)</p>',
    re.S,
)


def _read(path):
    return path.read_text(encoding="utf-8")


def _compact(source):
    return re.sub(r"\s+", " ", source).strip()


class TestAnalyzeDisclosure:

    def test_old_misleading_claim_is_removed(self):
        assert (
            "Your information is used only for this analysis."
            not in _read(INDEX)
        )

    def test_discloses_that_the_analysis_is_saved(self):
        text = _compact(_read(INDEX))

        assert (
            "Your resume, job description and results are saved to "
            "your account and appear in Saved Analyses."
            in text
        )

    def test_discloses_gemini_processing_of_derived_results(self):
        text = _compact(_read(INDEX))

        assert (
            "The derived results are also sent to Google Gemini to "
            "generate the AI advice."
            in text
        )


class TestAtsDisclosure:

    def test_ats_check_scopes_non_storage_to_file_text_and_result(self):
        match = ATS_DESCRIPTION.search(_read(INDEX))

        assert match is not None

        assert _compact(match.group(1)) == (
            "Analyze a PDF. This check does not save the file, its "
            "extracted text or the ATS result to your account."
        )

    def test_old_unqualified_claim_is_removed(self):
        assert (
            "Analyze a PDF file without saving it to your account."
            not in _read(INDEX)
        )


class TestDeleteModal:

    def test_states_only_account_deletion(self):
        match = DELETE_MODAL.search(_read(SETTINGS))

        assert match is not None

        assert _compact(match.group(1)) == (
            "This deletes your CareerGap account. You will be signed "
            "out, and this cannot be undone from your account."
        )

    def test_does_not_promise_associated_data_removal(self):
        match = DELETE_MODAL.search(_read(SETTINGS))

        assert match is not None

        text = _compact(match.group(1)).lower()

        for claim in (
            "profile",
            "resume",
            "saved analyses",
            "interview",
            "session",
        ):
            assert claim not in text


class TestDeleteHint:

    def test_makes_no_unverified_data_removal_promises(self):
        match = DELETE_HINT.search(_read(SETTINGS))

        assert match is not None

        text = _compact(match.group(1))

        assert text == (
            "Deletes your CareerGap account and signs you out."
        )

        for claim in (
            "profile",
            "resume",
            "analys",
            "interview",
            "session",
        ):
            assert claim not in text.lower()
