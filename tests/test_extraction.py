"""Tests for the defensive extraction layer."""

from __future__ import annotations

import zipfile

import pytest

from app.extraction import MAX_ENTRIES, UnsafeArchive, extract


def _extract(tmp_path, writer):
    archive = tmp_path / "upload.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        writer(zf)
    return extract(archive, tmp_path / "out", original_filename="upload.zip")


def test_path_traversal_is_rejected(tmp_path):
    with pytest.raises(UnsafeArchive, match="Unsafe path"):
        _extract(tmp_path, lambda zf: zf.writestr("../escaped.txt", "x"))


def test_absolute_path_is_rejected(tmp_path):
    with pytest.raises(UnsafeArchive, match="Unsafe path"):
        _extract(tmp_path, lambda zf: zf.writestr("/etc/passwd", "x"))


def test_zip_bomb_is_rejected(tmp_path):
    def writer(zf):
        zf.writestr("bomb.txt", "0" * (50 * 1024 * 1024))

    archive = tmp_path / "bomb.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        writer(zf)

    with pytest.raises(UnsafeArchive, match="compression ratio"):
        extract(archive, tmp_path / "out", original_filename="bomb.zip")


def test_too_many_entries_is_rejected(tmp_path):
    def writer(zf):
        for i in range(MAX_ENTRIES + 1):
            zf.writestr(f"f{i}.txt", "x")

    with pytest.raises(UnsafeArchive, match="entries"):
        _extract(tmp_path, writer)


def test_ordinary_archive_extracts(tmp_path):
    submission = _extract(tmp_path, lambda zf: zf.writestr("dir/file.txt", "hello"))
    assert [f.relpath for f in submission.files] == ["dir/file.txt"]
    assert submission.total_size == 5
    assert submission.main_directory == "dir"
