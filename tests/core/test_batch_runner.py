"""
Unit tests for batch_runner.py

Tests batch candidate processing functionality.
"""

import csv
import json
from pathlib import Path

import pytest

from jobflow.app.core.batch_runner import (
    discover_candidate_folders,
    run_batch,
    safe_slug,
)


def test_safe_slug_basic():
    """Test basic slug sanitization."""
    assert safe_slug("John Doe") == "john_doe"
    assert safe_slug("jane@example.com") == "janeexamplecom"
    assert safe_slug("Test User 123") == "test_user_123"


def test_safe_slug_special_chars():
    """Test slug with special characters."""
    assert safe_slug("user@domain.com") == "userdomaincom"
    assert safe_slug("first.last+tag@example.com") == "firstlasttagexamplecom"
    assert safe_slug("user-name_test") == "user_name_test"  # Consecutive separators collapsed


def test_safe_slug_consecutive_separators():
    """Test slug collapses consecutive separators."""
    assert safe_slug("test   user") == "test_user"
    assert safe_slug("test---user") == "test_user"
    assert safe_slug("test___user") == "test_user"


def test_safe_slug_max_length():
    """Test slug is truncated to 80 chars."""
    long_text = "a" * 100
    slug = safe_slug(long_text)
    assert len(slug) == 80


def test_safe_slug_empty():
    """Test slug with empty input."""
    assert safe_slug("") == "unknown"
    assert safe_slug("   ") == "unknown"
    assert safe_slug("!!!") == "unknown"


def test_discover_candidate_folders_anusha():
    """Test discovering Anusha's candidate folder."""
    fixtures_dir = Path(__file__).parent.parent / "fixtures" / "candidates"

    folders = discover_candidate_folders(str(fixtures_dir))

    # Should find at least anusha
    assert len(folders) >= 1
    assert any("anusha" in f for f in folders)

    # Should be sorted
    assert folders == sorted(folders)


def test_discover_candidate_folders_empty(tmp_path):
    """Test discovering with no candidate folders."""
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()

    folders = discover_candidate_folders(str(empty_dir))

    assert folders == []


def test_discover_candidate_folders_nonexistent():
    """Test discovering with nonexistent directory."""
    folders = discover_candidate_folders("nonexistent_dir")

    assert folders == []


def test_discover_candidate_folders_filters_non_candidates(tmp_path):
    """Test that non-candidate folders are filtered out."""
    candidates_dir = tmp_path / "candidates"
    candidates_dir.mkdir()

    # Create valid candidate folder
    valid = candidates_dir / "valid"
    valid.mkdir()
    (valid / "resume.txt").write_text("Resume")

    # Create invalid folder (no resume or xlsx, just other files)
    invalid = candidates_dir / "invalid"
    invalid.mkdir()
    (invalid / "readme.pdf").write_text("Other")  # .pdf not recognized as resume

    folders = discover_candidate_folders(str(candidates_dir))

    # Should only find valid
    assert len(folders) == 1
    assert "valid" in folders[0]


def test_run_batch_single_candidate(tmp_path):
    """Test batch run with single candidate (Anusha)."""
    from jobflow.app.core.file_job_source import FileJobSource

    # Use Anusha fixture
    candidates_dir = Path(__file__).parent.parent / "fixtures" / "candidates"
    jobs_file = Path(__file__).parent.parent / "fixtures" / "jobs_sample.json"

    # Output to tmp
    out_dir = tmp_path / "output"

    source = FileJobSource("jobs", str(jobs_file))

    result = run_batch(
        candidates_dir=str(candidates_dir),
        job_sources=[source],
        out_dir=str(out_dir),
        match_jobs=True,
    )

    # Verify result structure
    assert result["processed"] >= 1
    assert result["succeeded"] >= 1
    assert result["failed"] == 0

    # Verify output files exist
    assert Path(result["summary_path"]).exists()
    assert Path(result["errors_path"]).exists()
    assert Path(result["results_dir"]).exists()

    # Verify summary CSV
    with open(result["summary_path"], "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    assert len(rows) >= 1
    assert rows[0]["status"] == "success"
    assert rows[0]["candidate_id"] == "anusha@example.com"
    assert int(rows[0]["num_jobs"]) > 0

    # Verify errors JSON
    with open(result["errors_path"], "r", encoding="utf-8") as f:
        errors = json.load(f)

    assert errors == []  # No errors expected

    # Verify per-candidate results exist
    results_dir = Path(result["results_dir"])
    candidate_results = list(results_dir.glob("*/results.json"))
    assert len(candidate_results) >= 1

    # Verify results JSON structure
    with open(candidate_results[0], "r", encoding="utf-8") as f:
        candidate_result = json.load(f)

    assert "candidate" in candidate_result
    assert "jobs" in candidate_result
    assert "matches" in candidate_result
    assert candidate_result["candidate"]["name"] == "Anusha Kayam"


def test_run_batch_no_matching(tmp_path):
    """Test batch run without matching."""
    from jobflow.app.core.file_job_source import FileJobSource

    candidates_dir = Path(__file__).parent.parent / "fixtures" / "candidates"
    jobs_file = Path(__file__).parent.parent / "fixtures" / "jobs_sample.json"

    out_dir = tmp_path / "output"

    source = FileJobSource("jobs", str(jobs_file))

    result = run_batch(
        candidates_dir=str(candidates_dir),
        job_sources=[source],
        out_dir=str(out_dir),
        match_jobs=False,  # No matching
    )

    # Verify summary has no match data
    with open(result["summary_path"], "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    assert len(rows) >= 1
    assert rows[0]["num_matches"] == "0"
    assert rows[0]["top_score"] == ""

    # Verify results don't have matches
    results_dir = Path(result["results_dir"])
    candidate_results = list(results_dir.glob("*/results.json"))

    with open(candidate_results[0], "r", encoding="utf-8") as f:
        candidate_result = json.load(f)

    assert "matches" not in candidate_result


def test_run_batch_empty_candidates(tmp_path):
    """Test batch run with no candidates."""
    from jobflow.app.core.file_job_source import FileJobSource

    empty_dir = tmp_path / "empty_candidates"
    empty_dir.mkdir()

    jobs_file = Path(__file__).parent.parent / "fixtures" / "jobs_sample.json"
    out_dir = tmp_path / "output"

    source = FileJobSource("jobs", str(jobs_file))

    result = run_batch(
        candidates_dir=str(empty_dir),
        job_sources=[source],
        out_dir=str(out_dir),
        match_jobs=True,
    )

    # Should process 0 candidates
    assert result["processed"] == 0
    assert result["succeeded"] == 0
    assert result["failed"] == 0

    # Files should still be created (empty)
    assert Path(result["summary_path"]).exists()
    assert Path(result["errors_path"]).exists()

    # Summary should have only header
    with open(result["summary_path"], "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    assert len(rows) == 0


def test_run_batch_creates_output_dirs(tmp_path):
    """Test that batch run creates output directories."""
    from jobflow.app.core.file_job_source import FileJobSource

    candidates_dir = Path(__file__).parent.parent / "fixtures" / "candidates"
    jobs_file = Path(__file__).parent.parent / "fixtures" / "jobs_sample.json"

    # Output to nested path that doesn't exist
    out_dir = tmp_path / "nested" / "output" / "dir"

    source = FileJobSource("jobs", str(jobs_file))

    result = run_batch(
        candidates_dir=str(candidates_dir),
        job_sources=[source],
        out_dir=str(out_dir),
        match_jobs=True,
    )

    # Should create all directories
    assert out_dir.exists()
    assert (out_dir / "results").exists()
    assert Path(result["summary_path"]).exists()


def test_run_batch_handles_errors(tmp_path):
    """Test batch run handles candidate errors gracefully."""
    from jobflow.app.core.file_job_source import FileJobSource
    from scripts.generate_xlsx_fixture import generate_application_xlsx

    # Create candidates directory
    candidates_dir = tmp_path / "candidates"
    candidates_dir.mkdir()

    # Create valid candidate
    valid = candidates_dir / "valid"
    valid.mkdir()
    generate_application_xlsx(
        str(valid / "application.xlsx"),
        {"Name": "Valid", "Email": "valid@example.com", "Phone": "555-0000", "Location": "NYC"}
    )
    (valid / "resume.txt").write_text("Resume with Python and SQL")

    # Create invalid candidate (missing required fields)
    invalid = candidates_dir / "invalid"
    invalid.mkdir()
    generate_application_xlsx(str(invalid / "application.xlsx"), {})
    # No resume - will fail

    jobs_file = Path(__file__).parent.parent / "fixtures" / "jobs_sample.json"
    out_dir = tmp_path / "output"

    source = FileJobSource("jobs", str(jobs_file))

    result = run_batch(
        candidates_dir=str(candidates_dir),
        job_sources=[source],
        out_dir=str(out_dir),
        match_jobs=True,
    )

    # Should have processed both, but one failed
    assert result["processed"] == 2
    assert result["succeeded"] == 1
    assert result["failed"] == 1

    # Verify errors recorded
    with open(result["errors_path"], "r", encoding="utf-8") as f:
        errors = json.load(f)

    assert len(errors) == 1
    assert "invalid" in errors[0]["folder"]

    # Summary should show both
    with open(result["summary_path"], "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    assert len(rows) == 2
    statuses = {r["status"] for r in rows}
    assert "success" in statuses
    assert "failed" in statuses


def test_run_batch_deterministic(tmp_path):
    """Test that batch run is deterministic."""
    from jobflow.app.core.file_job_source import FileJobSource

    candidates_dir = Path(__file__).parent.parent / "fixtures" / "candidates"
    jobs_file = Path(__file__).parent.parent / "fixtures" / "jobs_sample.json"

    out_dir1 = tmp_path / "output1"
    out_dir2 = tmp_path / "output2"

    source1 = FileJobSource("jobs", str(jobs_file))
    source2 = FileJobSource("jobs", str(jobs_file))

    # Run twice
    result1 = run_batch(
        candidates_dir=str(candidates_dir),
        job_sources=[source1],
        out_dir=str(out_dir1),
        match_jobs=True,
    )

    result2 = run_batch(
        candidates_dir=str(candidates_dir),
        job_sources=[source2],
        out_dir=str(out_dir2),
        match_jobs=True,
    )

    # Results should be identical (excluding paths)
    assert result1["processed"] == result2["processed"]
    assert result1["succeeded"] == result2["succeeded"]
    assert result1["failed"] == result2["failed"]

    # Summary CSVs should have same content
    with open(result1["summary_path"], "r", encoding="utf-8") as f:
        rows1 = list(csv.DictReader(f))

    with open(result2["summary_path"], "r", encoding="utf-8") as f:
        rows2 = list(csv.DictReader(f))

    assert len(rows1) == len(rows2)
    for r1, r2 in zip(rows1, rows2):
        assert r1["candidate_id"] == r2["candidate_id"]
        assert r1["num_jobs"] == r2["num_jobs"]
        assert r1["num_matches"] == r2["num_matches"]
