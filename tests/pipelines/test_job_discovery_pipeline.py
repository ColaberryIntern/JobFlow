"""
Unit tests for job_discovery pipeline.

Tests the executable job discovery workflow orchestration.
"""

import json

import pytest

from pipelines.job_discovery import run_job_discovery


def test_run_job_discovery_basic(tmp_path):
    """Test basic job discovery pipeline with simple candidate and jobs."""
    from jobflow.app.core.file_job_source import FileJobSource

    # Create candidate profile
    candidate = {
        "desired_title": "Software Engineer",
        "skills_years": {"Python": 5, "AWS": 3},
        "desired_locations": ["San Francisco"],
        "remote_ok": True,
    }

    # Create test jobs fixture
    jobs_data = [
        {
            "title": "Software Engineer",
            "company": "Tech Corp",
            "location": "San Francisco",
            "description": "Build great software",
            "requirements": ["Python", "AWS"],
        },
        {
            "title": "Backend Engineer",
            "company": "Startup Inc",
            "location": "Remote",
            "description": "Work on backend systems",
            "requirements": ["Python", "Docker"],
        },
    ]

    jobs_file = tmp_path / "jobs.json"
    jobs_file.write_text(json.dumps(jobs_data))

    # Create source
    source = FileJobSource("test_source", str(jobs_file))

    # Run pipeline
    result = run_job_discovery(candidate, [source])

    # Verify result structure
    assert "status" in result
    assert "query" in result
    assert "jobs" in result
    assert "errors" in result
    assert "counts" in result

    # Verify status
    assert result["status"] == "ok"

    # Verify query was built
    assert result["query"]["titles"] == ["Software Engineer"]
    assert result["query"]["keywords"] == ["Python", "AWS"]
    assert result["query"]["remote_ok"] is True

    # Verify jobs were aggregated
    assert len(result["jobs"]) == 2
    assert result["counts"]["jobs"] == 2
    assert result["counts"]["errors"] == 0


def test_run_job_discovery_empty_sources():
    """Test pipeline with no sources."""
    candidate = {
        "desired_title": "Engineer",
        "skills_years": {"Python": 3},
    }

    result = run_job_discovery(candidate, [])

    assert result["status"] == "ok"
    assert result["jobs"] == []
    assert result["counts"]["jobs"] == 0
    assert result["counts"]["errors"] == 0


def test_run_job_discovery_minimal_candidate():
    """Test pipeline with minimal candidate profile."""
    candidate = {}  # Empty candidate

    result = run_job_discovery(candidate, [])

    assert result["status"] == "ok"
    assert result["query"]["titles"] == []
    assert result["query"]["keywords"] == []
    assert result["query"]["remote_ok"] is False


def test_run_job_discovery_deduplicates_jobs(tmp_path):
    """Test that pipeline deduplicates jobs by fingerprint."""
    from jobflow.app.core.file_job_source import FileJobSource

    candidate = {"desired_title": "Engineer"}

    # Create jobs with duplicates
    jobs_data = [
        {
            "title": "Engineer",
            "company": "Corp",
            "location": "SF",
            "description": "Work",
        },
        {
            "title": "Engineer",
            "company": "Corp",
            "location": "SF",
            "description": "Work",
            # Same content, should dedupe
        },
        {
            "title": "Scientist",
            "company": "Lab",
            "location": "NYC",
            "description": "Research",
        },
    ]

    jobs_file = tmp_path / "jobs.json"
    jobs_file.write_text(json.dumps(jobs_data))

    source = FileJobSource("test", str(jobs_file))
    result = run_job_discovery(candidate, [source])

    # Should deduplicate to 2 unique jobs
    assert result["counts"]["jobs"] == 2
    assert len(result["jobs"]) == 2


def test_run_job_discovery_captures_errors(tmp_path):
    """Test that pipeline captures errors from sources."""
    from jobflow.app.core.file_job_source import FileJobSource

    candidate = {"desired_title": "Engineer"}

    # Create jobs with invalid entries
    jobs_data = [
        {
            "title": "Valid Job",
            "company": "Corp",
            "location": "SF",
            "description": "Work",
        },
        "invalid entry",  # Will cause error
        {
            "title": "Another Valid",
            "company": "Corp2",
            "location": "NYC",
            "description": "Work",
        },
    ]

    jobs_file = tmp_path / "jobs.json"
    jobs_file.write_text(json.dumps(jobs_data))

    source = FileJobSource("test", str(jobs_file))
    result = run_job_discovery(candidate, [source])

    # Should have 2 valid jobs and 1 error
    assert result["counts"]["jobs"] == 2
    assert result["counts"]["errors"] == 1
    assert len(result["errors"]) == 1
    assert result["errors"][0]["source"] == "test"


def test_run_job_discovery_multiple_sources(tmp_path):
    """Test pipeline with multiple job sources."""
    from jobflow.app.core.file_job_source import FileJobSource

    candidate = {"desired_title": "Engineer"}

    # Create first source
    jobs1 = [
        {
            "title": "Job1",
            "company": "Corp1",
            "location": "SF",
            "description": "Work1",
        }
    ]
    jobs_file1 = tmp_path / "jobs1.json"
    jobs_file1.write_text(json.dumps(jobs1))
    source1 = FileJobSource("source1", str(jobs_file1))

    # Create second source
    jobs2 = [
        {
            "title": "Job2",
            "company": "Corp2",
            "location": "NYC",
            "description": "Work2",
        }
    ]
    jobs_file2 = tmp_path / "jobs2.json"
    jobs_file2.write_text(json.dumps(jobs2))
    source2 = FileJobSource("source2", str(jobs_file2))

    # Run pipeline with both sources
    result = run_job_discovery(candidate, [source1, source2])

    # Should have jobs from both sources
    assert result["counts"]["jobs"] == 2
    titles = [job["title"] for job in result["jobs"]]
    assert "Job1" in titles
    assert "Job2" in titles


def test_run_job_discovery_jobs_are_serialized(tmp_path):
    """Test that jobs are serialized to dicts."""
    from jobflow.app.core.file_job_source import FileJobSource

    candidate = {"desired_title": "Engineer"}

    jobs_data = [
        {
            "title": "Engineer",
            "company": "Corp",
            "location": "SF",
            "description": "Work",
            "requirements": ["Python"],
            "salary_min": 100000,
            "salary_max": 150000,
            "currency": "USD",
        }
    ]

    jobs_file = tmp_path / "jobs.json"
    jobs_file.write_text(json.dumps(jobs_data))

    source = FileJobSource("test", str(jobs_file))
    result = run_job_discovery(candidate, [source])

    # Verify jobs are dicts, not JobPosting objects
    assert len(result["jobs"]) == 1
    job = result["jobs"][0]
    assert isinstance(job, dict)

    # Verify all expected fields are present
    assert job["title"] == "Engineer"
    assert job["company"] == "Corp"
    assert job["location"] == "SF"
    assert job["description"] == "Work"
    assert job["requirements"] == ["Python"]
    assert job["salary_min"] == 100000.0
    assert job["salary_max"] == 150000.0
    assert job["currency"] == "USD"


def test_run_job_discovery_query_includes_all_fields():
    """Test that query includes all expected fields."""
    candidate = {
        "desired_title": "Senior Engineer",
        "alternate_titles": ["Engineer", "Developer"],
        "desired_locations": ["SF", "NYC"],
        "remote_ok": True,
        "skills_years": {"Python": 5, "AWS": 3},
        "employment_type": "full-time",
    }

    result = run_job_discovery(candidate, [])

    query = result["query"]
    assert "titles" in query
    assert "locations" in query
    assert "remote_ok" in query
    assert "keywords" in query
    assert "employment_type" in query

    assert query["titles"] == ["Senior Engineer", "Engineer", "Developer"]
    assert query["locations"] == ["SF", "NYC"]
    assert query["remote_ok"] is True
    assert query["keywords"] == ["Python", "AWS"]
    assert query["employment_type"] == "full-time"


def test_run_job_discovery_deterministic(tmp_path):
    """Test that pipeline is deterministic (same input → same output)."""
    from jobflow.app.core.file_job_source import FileJobSource

    candidate = {
        "desired_title": "Engineer",
        "skills_years": {"Python": 5},
    }

    jobs_data = [
        {
            "title": "Job1",
            "company": "Corp",
            "location": "SF",
            "description": "Work",
        }
    ]

    jobs_file = tmp_path / "jobs.json"
    jobs_file.write_text(json.dumps(jobs_data))

    source = FileJobSource("test", str(jobs_file))

    # Run pipeline twice
    result1 = run_job_discovery(candidate, [source])
    result2 = run_job_discovery(candidate, [source])

    # Results should be identical
    assert result1["status"] == result2["status"]
    assert result1["query"] == result2["query"]
    assert result1["counts"] == result2["counts"]
    assert len(result1["jobs"]) == len(result2["jobs"])


def test_run_job_discovery_with_realistic_fixture(tmp_path):
    """Test pipeline with realistic candidate and job fixture."""
    from jobflow.app.core.file_job_source import FileJobSource
    from pathlib import Path

    # Realistic candidate from candidate_intake
    candidate = {
        "first_name": "Jane",
        "last_name": "Doe",
        "email": "jane@example.com",
        "skills_years": {
            "Python": 5,
            "AWS": 3,
            "Docker": 2,
            "Kubernetes": 2,
        },
        "desired_title": "Backend Engineer",
        "alternate_titles": ["Software Engineer", "Python Developer"],
        "desired_locations": ["San Francisco", "Remote"],
        "remote_ok": True,
        "employment_type": "full-time",
    }

    # Use the existing jobs_sample.json fixture
    fixture_path = Path(__file__).parent.parent / "fixtures" / "jobs_sample.json"

    # Create source
    source = FileJobSource("fixtures", str(fixture_path))

    # Run pipeline
    result = run_job_discovery(candidate, [source])

    # Verify successful execution
    assert result["status"] == "ok"

    # Verify query was built correctly
    assert "Backend Engineer" in result["query"]["titles"]
    assert "python" in result["query"]["keywords"]  # Keywords are lowercase
    assert result["query"]["remote_ok"] is True

    # Verify jobs were aggregated (8 unique from 10 total)
    assert result["counts"]["jobs"] == 8
    assert len(result["jobs"]) == 8

    # Verify no errors
    assert result["counts"]["errors"] == 0

    # Verify jobs are properly serialized
    for job in result["jobs"]:
        assert isinstance(job, dict)
        assert "title" in job
        assert "company" in job
        assert "requirements" in job
        assert isinstance(job["requirements"], list)


def test_run_job_discovery_result_structure():
    """Test that result has correct structure."""
    candidate = {}
    result = run_job_discovery(candidate, [])

    # Verify top-level keys
    assert set(result.keys()) == {"status", "query", "jobs", "errors", "counts"}

    # Verify types
    assert isinstance(result["status"], str)
    assert isinstance(result["query"], dict)
    assert isinstance(result["jobs"], list)
    assert isinstance(result["errors"], list)
    assert isinstance(result["counts"], dict)

    # Verify counts structure
    assert set(result["counts"].keys()) == {"jobs", "errors"}
    assert isinstance(result["counts"]["jobs"], int)
    assert isinstance(result["counts"]["errors"], int)


def test_run_job_discovery_preserves_job_data(tmp_path):
    """Test that job data is preserved through pipeline."""
    from jobflow.app.core.file_job_source import FileJobSource

    candidate = {"desired_title": "Engineer"}

    jobs_data = [
        {
            "title": "Software Engineer",
            "company": "Tech Corp",
            "location": "San Francisco",
            "description": "Build scalable systems",
            "requirements": ["Python", "AWS", "Docker"],
            "salary_min": 120000,
            "salary_max": 160000,
            "currency": "USD",
            "employment_type": "full-time",
            "remote": True,
            "url": "https://example.com/job/123",
            "source": "linkedin",
        }
    ]

    jobs_file = tmp_path / "jobs.json"
    jobs_file.write_text(json.dumps(jobs_data))

    source = FileJobSource("test", str(jobs_file))
    result = run_job_discovery(candidate, [source])

    # Verify all data preserved
    job = result["jobs"][0]
    assert job["title"] == "Software Engineer"
    assert job["company"] == "Tech Corp"
    assert job["location"] == "San Francisco"
    assert job["description"] == "Build scalable systems"
    assert job["requirements"] == ["Python", "AWS", "Docker"]
    assert job["salary_min"] == 120000.0
    assert job["salary_max"] == 160000.0
    assert job["currency"] == "USD"
    assert job["employment_type"] == "full-time"
    assert job["remote"] is True
    assert job["url"] == "https://example.com/job/123"
    assert job["source"] == "linkedin"
