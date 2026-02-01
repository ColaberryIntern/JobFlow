# Core Business Logic

Core business logic and domain rules.

Responsible for:
- Business rule enforcement
- Domain logic
- Application-specific algorithms
- Cross-cutting concerns

## Modules

### candidate_intake.py
Converts candidate-provided application sheets (Excel) into normalized profiles for matching/submission. Parses personal information and skills from the "Application Info.xlsx" template with resilience to blank rows and section headers.

### job_model.py
Canonical job posting domain model used across aggregation, matching, approvals, and execution pipelines. Normalizes messy job data from various sources into consistent structure with deterministic fingerprinting.

### job_source.py
Protocol interface for pluggable job feed sources. Defines contract for fetching raw job dicts that are normalized elsewhere.

### job_aggregator.py
Multi-source job aggregator with fingerprint-based deduplication. Orchestrates fetching from multiple JobSource implementations, normalizes raw data, and maintains stable ordering.

### file_job_source.py
File-based JobSource implementation for local fixtures and exports. Reads job postings from JSON files for testing and offline scenarios.

### search_query.py
Search query builder that transforms candidate profiles into structured job search queries. Maps candidate preferences and skills to search criteria.
