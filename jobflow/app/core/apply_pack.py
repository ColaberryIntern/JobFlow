"""
Apply pack builder for submission-ready job applications.

Transforms job discovery results into structured application packets
ready for candidate review and submission.
"""


def build_apply_pack(discovery_result: dict, top_n: int = 25) -> dict:
    """
    Build a submission-ready application pack from discovery results.

    This creates a structured export of top job matches with all information
    needed for application submission. Output is deterministic and stable.

    Args:
        discovery_result: Output from job_discovery pipeline (dict with candidate, jobs, matches)
        top_n: Maximum number of applications to include (default: 25)

    Returns:
        Dictionary with keys:
            - candidate: Safe subset of candidate info (name, email, phone, location, etc.)
            - top_n: Number of applications included
            - applications: List of application entries sorted by score (desc)
            - checklist: Pre-submission checklist with autofill data

    Notes:
        - Uses matches if present; falls back to jobs if no matching
        - Gracefully handles missing fields
        - Stable ordering for deterministic output
        - No timestamps (for reproducibility)
    """
    # Extract candidate info
    candidate_data = discovery_result.get("candidate", {})
    candidate_safe = {
        "name": candidate_data.get("name") or candidate_data.get("full_name", ""),
        "email": candidate_data.get("email", ""),
        "phone": candidate_data.get("phone", ""),
        "location": candidate_data.get("location", ""),
        "desired_titles": candidate_data.get("desired_titles", []),
        "skills": candidate_data.get("skills", []),
    }

    # Build applications list from matches or jobs
    applications = []

    if "matches" in discovery_result and discovery_result["matches"]:
        # Use matches (scored and ranked)
        matches = discovery_result["matches"]

        # Sort by score descending, then by job_title for stable tie-breaking
        sorted_matches = sorted(
            matches,
            key=lambda m: (-m.get("overall_score", 0), m.get("job_title", "")),
        )

        # Take top N
        top_matches = sorted_matches[:top_n]

        for rank, match in enumerate(top_matches, start=1):
            app = {
                "rank": rank,
                "job_title": match.get("job_title", ""),
                "company": match.get("job_company", ""),
                "location": match.get("job_location", ""),
                "apply_url": match.get("job_url", ""),
                "source": match.get("source", ""),
                "score": match.get("overall_score", 0),
                "decision": match.get("decision", ""),
                "reasons": match.get("reasons", []),
                "matched_keywords": match.get("matched_keywords", []),
                "missing_keywords": match.get("missing_keywords", []),
                "job_fingerprint": match.get("job_fingerprint", ""),
                "notes": "",  # Reserved for human annotation
            }
            applications.append(app)

    elif "jobs" in discovery_result and discovery_result["jobs"]:
        # Fall back to jobs (no scoring)
        jobs = discovery_result["jobs"]

        # Sort by title for stable ordering
        sorted_jobs = sorted(jobs, key=lambda j: j.get("title", ""))

        # Take top N
        top_jobs = sorted_jobs[:top_n]

        for rank, job in enumerate(top_jobs, start=1):
            app = {
                "rank": rank,
                "job_title": job.get("title", ""),
                "company": job.get("company", ""),
                "location": job.get("location", ""),
                "apply_url": job.get("url", ""),
                "source": job.get("source", ""),
                "score": 0,
                "decision": "",
                "reasons": [],
                "matched_keywords": [],
                "missing_keywords": [],
                "job_fingerprint": job.get("fingerprint", ""),
                "notes": "",
            }
            applications.append(app)

    # Build checklist
    has_email = bool(candidate_safe.get("email"))
    has_phone = bool(candidate_safe.get("phone"))

    # Infer resume availability from raw data if present
    raw_data = discovery_result.get("raw", {})
    has_resume = bool(raw_data.get("resume_path") or raw_data.get("resume_text_excerpt"))

    # Check if any top applications need manual review
    needs_manual_review = any(
        app.get("decision") != "strong_fit"
        for app in applications
    )

    checklist = {
        "has_email": has_email,
        "has_phone": has_phone,
        "has_resume": has_resume,
        "work_authorization": candidate_data.get("work_authorization", ""),
        "sponsorship_needed": candidate_data.get("sponsorship_needed"),
        "needs_manual_review": needs_manual_review,
    }

    # Build final pack
    pack = {
        "candidate": candidate_safe,
        "top_n": len(applications),
        "applications": applications,
        "checklist": checklist,
    }

    return pack
