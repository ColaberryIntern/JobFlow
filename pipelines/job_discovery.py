"""
Job Discovery Pipeline

High-level workflow for discovering, parsing, and storing job postings.

IMPORTANT: This is a DESCRIPTIVE definition only.
No execution logic, imports, or side effects belong here.
Actual work is done by execution scripts coordinated by workers.
"""

# Pipeline: Job Discovery and Parsing
# Purpose: Discover new job postings from various sources and parse them into structured data
#
# Steps:
#   1. fetch_job_sources
#      - Input: List of job board URLs or API endpoints
#      - Output: Raw job posting data (HTML, JSON, etc.)
#      - Execution: /execution/fetch_jobs.py
#      - Retry: 3 attempts with exponential backoff
#      - Failure: Log and continue to next source
#
#   2. parse_job_postings
#      - Input: Raw job posting data from step 1
#      - Output: Structured job data (title, company, description, requirements, etc.)
#      - Execution: /execution/parse_jobs.py
#      - Retry: 2 attempts
#      - Failure: Mark as unparseable, continue
#
#   3. deduplicate_jobs
#      - Input: Parsed job data from step 2
#      - Output: Deduplicated job list
#      - Execution: /execution/deduplicate_jobs.py
#      - Retry: 1 attempt
#      - Failure: Skip deduplication, continue
#
#   4. store_jobs
#      - Input: Deduplicated jobs from step 3
#      - Output: Job IDs in database
#      - Execution: /execution/store_jobs.py
#      - Retry: 3 attempts
#      - Failure: Alert on failure, halt pipeline
#
# Dependencies:
#   - Steps 1-4 run sequentially
#   - Step 2 can process multiple jobs in parallel
#   - Step 4 is critical path (must succeed)
#
# Schedule:
#   - Run every 6 hours
#   - Can be triggered manually via API
#
# Configuration:
#   - max_jobs_per_run: 1000
#   - timeout_per_step: 300 seconds
#   - parallel_parsing: True
#   - parallel_workers: 5


# Pipeline: Job Discovery (Placeholder)
# Not yet implemented. No operational code below.


def get_pipeline_definition():
    """
    Return pipeline definition structure.

    This is a placeholder for future pipeline configuration.
    Currently returns None - not yet operational.

    Returns:
        None (not implemented)
    """
    return None


# ==============================================================================
# Executable Pipeline Functions
# ==============================================================================


def run_job_discovery(candidate_or_query, sources: list) -> dict:
    """
    Execute job discovery pipeline for a candidate.

    Orchestrates the complete job discovery workflow:
    1. Build search query from candidate profile (or use provided query)
    2. Aggregate jobs from multiple sources
    3. Return structured results with jobs and errors

    This is a deterministic, pure function with no side effects.
    All I/O is delegated to the provided JobSource implementations.

    Args:
        candidate_or_query: One of:
            - CandidateProfile instance
            - dict with CandidateProfile fields (full_name, email, etc.)
            - dict with SearchQuery fields (titles, keywords, etc.) [legacy]
            - dict with old-style fields (desired_title, skills_years, etc.) [legacy]
        sources: List of JobSource implementations to aggregate from

    Returns:
        Dict containing:
        - status: "ok" (always successful, errors captured separately)
        - query: Search query dict built from candidate profile
        - jobs: List of serialized job dicts (using Job.to_dict())
        - errors: List of error dicts from aggregation
        - counts: Dict with "jobs" and "errors" counts

    Example (new style):
        >>> from jobflow.app.core.candidate_profile import CandidateProfile
        >>> candidate = CandidateProfile(
        ...     full_name="Jane Doe",
        ...     email="jane@example.com",
        ...     phone="555-1234",
        ...     location="SF",
        ...     desired_titles=["Software Engineer"],
        ...     skills=["Python", "AWS"]
        ... )
        >>> result = run_job_discovery(candidate, [source])

    Example (legacy):
        >>> candidate = {
        ...     "desired_title": "Software Engineer",
        ...     "skills_years": {"Python": 5, "AWS": 3}
        ... }
        >>> result = run_job_discovery(candidate, [source])
    """
    from jobflow.app.core.candidate_profile import CandidateProfile
    from jobflow.app.core.candidate_query_builder import build_search_query
    from jobflow.app.core.job_aggregator import JobAggregator
    from jobflow.app.core.search_query import build_job_query

    # Step 1: Build search query (handle multiple input formats)
    query = _build_query_from_input(candidate_or_query)

    # Step 2: Aggregate jobs from sources with error handling
    aggregator = JobAggregator(sources)
    jobs, errors = aggregator.aggregate_with_errors(query)

    # Step 3: Serialize jobs (convert JobPosting instances to dicts)
    serialized_jobs = [job.to_dict() for job in jobs]

    # Step 4: Build result structure
    result = {
        "status": "ok",
        "query": query,
        "jobs": serialized_jobs,
        "errors": errors,
        "counts": {
            "jobs": len(jobs),
            "errors": len(errors),
        },
    }

    return result


def _build_query_from_input(candidate_or_query) -> dict:
    """
    Build search query from various input formats.

    Handles:
    - CandidateProfile instance → build_search_query
    - dict with CandidateProfile fields → build_search_query
    - dict with SearchQuery fields (titles, keywords) → passthrough
    - dict with legacy fields (desired_title, skills_years) → build_job_query

    Args:
        candidate_or_query: Input in one of the supported formats

    Returns:
        Search query dict
    """
    from jobflow.app.core.candidate_profile import CandidateProfile
    from jobflow.app.core.candidate_query_builder import build_search_query
    from jobflow.app.core.search_query import build_job_query

    # Handle CandidateProfile instance
    if isinstance(candidate_or_query, CandidateProfile):
        return build_search_query(candidate_or_query)

    # Handle dict
    if isinstance(candidate_or_query, dict):
        # Check if it's already a SearchQuery (has titles/keywords/remote_ok)
        if "titles" in candidate_or_query and "keywords" in candidate_or_query:
            # Already a search query, use as-is
            return candidate_or_query

        # Check if it's CandidateProfile-style (has full_name, email, etc.)
        if "full_name" in candidate_or_query or "email" in candidate_or_query:
            # Convert to CandidateProfile and build query
            profile = CandidateProfile.from_dict(candidate_or_query)
            return build_search_query(profile)

        # Otherwise, assume legacy format (desired_title, skills_years, etc.)
        # Use old build_job_query
        return build_job_query(candidate_or_query)

    # Fallback: treat as legacy dict
    return build_job_query(candidate_or_query)
