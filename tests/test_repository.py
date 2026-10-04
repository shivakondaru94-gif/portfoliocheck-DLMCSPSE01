"""Tests for RepositoryClient and rule R07 (repository matches code archive)."""

from __future__ import annotations

import io
import json
import subprocess
import urllib.error

import pytest

from app import checker
from app.models import Severity
from app.repository import (
    GitHubRepositoryClient,
    RepositoryNotFound,
    RepositoryUnavailable,
    blob_hash,
)

from .conftest import CODE_ARCHIVE, MAIN, OWNER, PROJECT_FILES, REPO, VALID_PHASE_3, zip_bytes


def r07(report):
    matches = [f for f in report.findings if f.rule_id == "R07"]
    assert len(matches) == 1, matches
    return matches[0]


def with_archive(files):
    submission = dict(VALID_PHASE_3)
    submission[CODE_ARCHIVE] = zip_bytes(files)
    return submission


# -- blob hash ----------------------------------------------------------------


def test_blob_hash_matches_git_for_known_content():
    # `printf 'hello\n' | git hash-object --stdin` -> ce0136250...
    assert blob_hash(b"hello\n") == "ce013625030ba8dba906f756967f9e9ca394464a"


def test_blob_hash_of_empty_file_matches_git():
    assert blob_hash(b"") == "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391"


@pytest.mark.skipif(
    subprocess.run(["git", "--version"], capture_output=True).returncode != 0,
    reason="git not installed",
)
def test_blob_hash_agrees_with_git_hash_object():
    content = b"def main():\n    return 42\n"
    git = subprocess.run(
        ["git", "hash-object", "--stdin"], input=content, capture_output=True, check=True
    )
    assert blob_hash(content) == git.stdout.decode().strip()


# -- R07 outcomes -------------------------------------------------------------


def test_identical_archive_and_repository_pass(make_submission, fake_repository):
    report = checker.run(make_submission(dict(VALID_PHASE_3)))
    finding = r07(report)
    assert finding.severity is Severity.PASS
    assert f"{OWNER}/{REPO}" in finding.message
    assert fake_repository.requests == [(OWNER, REPO)]


def test_file_missing_from_archive_fails_and_is_named(make_submission):
    files = {k: v for k, v in PROJECT_FILES.items() if k != "tests/test_main.py"}
    finding = r07(checker.run(make_submission(with_archive(files))))
    assert finding.severity is Severity.FAIL
    assert "1 only in the repository" in finding.message
    assert "tests/test_main.py" in finding.message


def test_extra_file_in_archive_fails(make_submission):
    files = dict(PROJECT_FILES, **{"notes/todo.txt": b"deploy on friday\n"})
    finding = r07(checker.run(make_submission(with_archive(files))))
    assert finding.severity is Severity.FAIL
    assert "1 only in the archive" in finding.message
    assert "notes/todo.txt" in finding.message


def test_changed_file_content_fails(make_submission):
    files = dict(PROJECT_FILES, **{"app/main.py": b"from fastapi import FastAPI\n\napp = FastAPI(debug=True)\n"})
    finding = r07(checker.run(make_submission(with_archive(files))))
    assert finding.severity is Severity.FAIL
    assert "1 with different content (app/main.py)" in finding.message


def test_windows_line_endings_count_as_identical(make_submission):
    files = {k: v.replace(b"\n", b"\r\n") for k, v in PROJECT_FILES.items()}
    finding = r07(checker.run(make_submission(with_archive(files))))
    assert finding.severity is Severity.PASS


def test_github_download_zip_wrapper_folder_is_ignored(make_submission):
    files = {f"pse_myproject-main/{k}": v for k, v in PROJECT_FILES.items()}
    finding = r07(checker.run(make_submission(with_archive(files))))
    assert finding.severity is Severity.PASS


def test_macos_metadata_and_git_folder_are_ignored(make_submission):
    files = dict(PROJECT_FILES)
    files["__MACOSX/._README.md"] = b"\x00\x05\x16\x07"
    files[".git/HEAD"] = b"ref: refs/heads/main\n"
    files["app/.DS_Store"] = b"\x00\x00\x00\x01Bud1"
    finding = r07(checker.run(make_submission(with_archive(files))))
    assert finding.severity is Severity.PASS


def test_private_or_missing_repository_fails(make_submission, fake_repository):
    fake_repository.error = RepositoryNotFound("/repos/x/y")
    finding = r07(checker.run(make_submission(dict(VALID_PHASE_3))))
    assert finding.severity is Severity.FAIL
    assert "not public" in finding.message


def test_unreachable_github_only_warns(make_submission, fake_repository):
    fake_repository.error = RepositoryUnavailable("timed out")
    finding = r07(checker.run(make_submission(dict(VALID_PHASE_3))))
    assert finding.severity is Severity.WARN
    assert "could not be reached" in finding.message


def test_truncated_tree_warns_even_when_files_match(make_submission, fake_repository):
    fake_repository.truncated = True
    finding = r07(checker.run(make_submission(dict(VALID_PHASE_3))))
    assert finding.severity is Severity.WARN


def test_missing_link_file_skips_comparison_with_warning(make_submission, fake_repository):
    files = {k: v for k, v in VALID_PHASE_3.items() if k != f"{MAIN}/links.txt"}
    finding = r07(checker.run(make_submission(files)))
    assert finding.severity is Severity.WARN
    assert "GitHub link" in finding.message
    assert fake_repository.requests == []


def test_corrupt_code_archive_fails(make_submission):
    files = dict(VALID_PHASE_3, **{CODE_ARCHIVE: b"PK\x03\x04 not really a zip"})
    finding = r07(checker.run(make_submission(files)))
    assert finding.severity is Severity.FAIL
    assert "could not be read" in finding.message


def test_nested_archive_with_path_traversal_is_rejected(make_submission):
    files = dict(VALID_PHASE_3, **{CODE_ARCHIVE: zip_bytes({"../escape.py": b"x"})})
    finding = r07(checker.run(make_submission(files)))
    assert finding.severity is Severity.FAIL
    assert "Unsafe path" in finding.message


def test_repository_url_with_git_suffix_is_understood(make_submission, fake_repository):
    files = dict(VALID_PHASE_3)
    files[f"{MAIN}/links.txt"] = (
        f"https://github.com/{OWNER}/{REPO}.git\nhttps://app.example.org\n".encode()
    )
    checker.run(make_submission(files))
    assert fake_repository.requests == [(OWNER, REPO)]


def test_comparison_not_run_for_phase_1(make_submission, fake_repository):
    report = checker.run(make_submission(dict(VALID_PHASE_3), phase=1))
    assert not [f for f in report.findings if f.rule_id == "R07"]
    assert fake_repository.requests == []


# -- GitHubRepositoryClient against a stubbed HTTP layer ------------------------


class _Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _stub_urlopen(monkeypatch, responses):
    """Serve ``responses`` (path suffix -> payload or exception) to the client."""
    seen = []

    def fake_urlopen(request, timeout):
        seen.append((request.full_url, dict(request.header_items()), timeout))
        for suffix, payload in responses.items():
            if request.full_url.endswith(suffix):
                if isinstance(payload, Exception):
                    raise payload
                return _Response(json.dumps(payload).encode())
        raise AssertionError(f"unexpected request {request.full_url}")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    return seen


def test_client_builds_inventory_from_default_branch_tree(monkeypatch):
    seen = _stub_urlopen(
        monkeypatch,
        {
            "/repos/alice/demo": {"default_branch": "trunk"},
            "/repos/alice/demo/git/trees/trunk?recursive=1": {
                "truncated": False,
                "tree": [
                    {"path": "src", "type": "tree", "sha": "t1"},
                    {"path": "src/app.py", "type": "blob", "sha": "b1"},
                    {"path": "vendor/lib", "type": "commit", "sha": "c1"},
                ],
            },
        },
    )
    inventory = GitHubRepositoryClient(token="").inventory("alice", "demo")

    assert inventory.ref == "trunk"
    assert inventory.blobs == {"src/app.py": "b1"}
    assert all(timeout == 2.5 for _, _, timeout in seen)


def test_client_sends_token_when_configured(monkeypatch):
    seen = _stub_urlopen(
        monkeypatch,
        {
            "/repos/alice/demo": {"default_branch": "main"},
            "/git/trees/main?recursive=1": {"tree": []},
        },
    )
    GitHubRepositoryClient(token="secret-token").inventory("alice", "demo")
    assert seen[0][1]["Authorization"] == "Bearer secret-token"


def test_client_maps_404_to_not_found(monkeypatch):
    error = urllib.error.HTTPError("u", 404, "Not Found", {}, None)
    _stub_urlopen(monkeypatch, {"/repos/alice/private": error})
    with pytest.raises(RepositoryNotFound):
        GitHubRepositoryClient(token="").inventory("alice", "private")


def test_client_maps_rate_limit_to_unavailable(monkeypatch):
    error = urllib.error.HTTPError("u", 403, "rate limit exceeded", {}, None)
    _stub_urlopen(monkeypatch, {"/repos/alice/demo": error})
    with pytest.raises(RepositoryUnavailable, match="403"):
        GitHubRepositoryClient(token="").inventory("alice", "demo")


def test_client_maps_network_failure_to_unavailable(monkeypatch):
    _stub_urlopen(monkeypatch, {"/repos/alice/demo": urllib.error.URLError("no route")})
    with pytest.raises(RepositoryUnavailable):
        GitHubRepositoryClient(token="").inventory("alice", "demo")
