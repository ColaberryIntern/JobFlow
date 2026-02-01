"""
Batch candidate processing runner.

Processes multiple candidate folders and generates aggregated results.
"""

import csv
import json
import re
import traceback
from pathlib import Path
from typing import Any


def discover_candidate_folders(candidates_dir: str) -> list[str]:
    """
    Discover candidate folders in directory.

    Returns sorted list of immediate subdirectories that appear to be
    candidate folders (contain either .xlsx or resume files).

    Args:
        candidates_dir: Path to directory containing candidate folders

    Returns:
        Sorted list of absolute paths to candidate folders
    """
    candidates_path = Path(candidates_dir)

    if not candidates_path.exists() or not candidates_path.is_dir():
        return []

    candidate_folders = []

    for item in candidates_path.iterdir():
        if not item.is_dir():
            continue

        # Check if it looks like a candidate folder
        # Must have either .xlsx OR resume files (.txt, .md, .docx)
        has_xlsx = any(item.glob("*.xlsx"))
        has_resume = any(item.glob("*.txt")) or any(item.glob("*.md")) or any(item.glob("*.docx"))

        if has_xlsx or has_resume:
            candidate_folders.append(str(item.absolute()))

    return sorted(candidate_folders)


def run_batch(
    candidates_dir: str,
    job_sources: list,
    out_dir: str,
    match_jobs: bool = True
) -> dict:
    """
    Run batch candidate processing.

    Processes all candidate folders and generates:
    - Per-candidate results JSON files
    - Summary CSV with key metrics
    - Errors JSON with any failures

    Args:
        candidates_dir: Directory containing candidate folders
        job_sources: List of JobSource instances for job aggregation
        out_dir: Output directory for results
        match_jobs: Whether to compute match scores (default True)

    Returns:
        Dict with:
        - processed: number of candidates processed
        - succeeded: number of successful candidates
        - failed: number of failed candidates
        - summary_path: path to summary.csv
        - errors_path: path to errors.json
        - results_dir: path to results directory
    """
    from pipelines.job_discovery import run_job_discovery

    # Create output directories
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    results_dir = out_path / "results"
    results_dir.mkdir(exist_ok=True)

    # Discover candidate folders
    candidate_folders = discover_candidate_folders(candidates_dir)

    if not candidate_folders:
        # No candidates found - still write empty files
        _write_summary_csv(str(out_path / "summary.csv"), [])
        _write_errors_json(str(out_path / "errors.json"), [])
        return {
            "processed": 0,
            "succeeded": 0,
            "failed": 0,
            "summary_path": str(out_path / "summary.csv"),
            "errors_path": str(out_path / "errors.json"),
            "results_dir": str(results_dir),
        }

    # Process each candidate
    summary_rows = []
    errors = []
    succeeded = 0
    failed = 0

    for folder in candidate_folders:
        folder_name = Path(folder).name

        try:
            # Run job discovery for this candidate
            result = run_job_discovery(
                sources=job_sources,
                candidate_folder=folder,
                match_jobs=match_jobs
            )

            # Extract candidate ID
            candidate_id = _extract_candidate_id(result, folder_name)
            safe_id = safe_slug(candidate_id)

            # Write per-candidate results
            candidate_results_dir = results_dir / safe_id
            candidate_results_dir.mkdir(exist_ok=True)

            results_file = candidate_results_dir / "results.json"
            with open(results_file, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, sort_keys=True)

            # Build summary row
            num_jobs = result["counts"]["jobs"]
            num_errors = result["counts"]["errors"]
            num_matches = result["counts"].get("matches", 0)

            top_score = None
            if match_jobs and result.get("matches"):
                top_score = result["matches"][0]["overall_score"]

            summary_row = {
                "candidate_id": candidate_id,
                "folder": folder_name,
                "num_jobs": num_jobs,
                "num_matches": num_matches,
                "top_score": top_score if top_score is not None else "",
                "num_errors": num_errors,
                "status": "success",
            }
            summary_rows.append(summary_row)
            succeeded += 1

        except Exception as e:
            # Capture error
            error_entry = {
                "folder": folder_name,
                "error_type": type(e).__name__,
                "error_message": str(e),
                "traceback": _truncate_traceback(traceback.format_exc(), max_lines=20),
            }
            errors.append(error_entry)

            # Add failed row to summary
            summary_row = {
                "candidate_id": folder_name,
                "folder": folder_name,
                "num_jobs": 0,
                "num_matches": 0,
                "top_score": "",
                "num_errors": 0,
                "status": "failed",
            }
            summary_rows.append(summary_row)
            failed += 1

    # Write summary CSV
    summary_path = str(out_path / "summary.csv")
    _write_summary_csv(summary_path, summary_rows)

    # Write errors JSON
    errors_path = str(out_path / "errors.json")
    _write_errors_json(errors_path, errors)

    return {
        "processed": len(candidate_folders),
        "succeeded": succeeded,
        "failed": failed,
        "summary_path": summary_path,
        "errors_path": errors_path,
        "results_dir": str(results_dir),
    }


def safe_slug(text: str) -> str:
    """
    Create safe filesystem slug from text.

    Rules:
    - Lowercase
    - Replace spaces with underscores
    - Keep only alphanumeric, underscore, dash
    - Max length 80 characters

    Args:
        text: Input text

    Returns:
        Sanitized slug
    """
    if not text:
        return "unknown"

    # Lowercase
    slug = text.lower()

    # Replace spaces with underscores
    slug = slug.replace(" ", "_")

    # Keep only alphanumeric, underscore, dash
    slug = re.sub(r"[^a-z0-9_-]", "", slug)

    # Remove consecutive underscores/dashes
    slug = re.sub(r"[_-]+", "_", slug)

    # Strip leading/trailing underscores/dashes
    slug = slug.strip("_-")

    # Truncate to 80 chars
    if len(slug) > 80:
        slug = slug[:80].rstrip("_-")

    # Fallback if empty
    if not slug:
        return "unknown"

    return slug


def _extract_candidate_id(result: dict, fallback: str) -> str:
    """
    Extract candidate ID from result dict.

    Priority:
    1. candidate.email
    2. candidate.name
    3. fallback (folder name)

    Args:
        result: Job discovery result dict
        fallback: Fallback ID if no candidate info

    Returns:
        Candidate ID string
    """
    if "candidate" in result:
        candidate = result["candidate"]
        if candidate.get("email"):
            return candidate["email"]
        if candidate.get("name"):
            return candidate["name"]

    return fallback


def _write_summary_csv(path: str, rows: list[dict]):
    """
    Write summary CSV file.

    Args:
        path: Output CSV file path
        rows: List of summary row dicts
    """
    fieldnames = [
        "candidate_id",
        "folder",
        "num_jobs",
        "num_matches",
        "top_score",
        "num_errors",
        "status",
    ]

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_errors_json(path: str, errors: list[dict]):
    """
    Write errors JSON file.

    Args:
        path: Output JSON file path
        errors: List of error dicts
    """
    with open(path, "w", encoding="utf-8") as f:
        json.dump(errors, f, indent=2, sort_keys=True)


def _truncate_traceback(tb: str, max_lines: int = 20) -> str:
    """
    Truncate traceback to max lines.

    Args:
        tb: Traceback string
        max_lines: Maximum number of lines

    Returns:
        Truncated traceback
    """
    lines = tb.split("\n")
    if len(lines) <= max_lines:
        return tb

    return "\n".join(lines[:max_lines]) + f"\n... ({len(lines) - max_lines} more lines)"
