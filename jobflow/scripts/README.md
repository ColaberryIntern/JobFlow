# JobFlow Scripts

Command-line utilities for batch processing and automation.

## batch_run.py

Batch process multiple candidate folders for job discovery and matching.

### Usage

```bash
python -m jobflow.scripts.batch_run \
  --candidates-dir ./candidates \
  --jobs ./jobs.json \
  --out ./results
```

### Arguments

- `--candidates-dir` (required): Directory containing candidate folders
  - Each subfolder should contain:
    - One `.xlsx` file with application info (key-value pairs)
    - One resume file (`.txt`, `.md`, or `.docx`)

- `--jobs` (required): Path to JSON file with job postings
  - Used as FileJobSource for job aggregation
  - Format: list of job dicts or `{"jobs": [...]}`

- `--out` (required): Output directory for results
  - Will be created if it doesn't exist
  - Contains:
    - `summary.csv`: Summary of all candidates
    - `errors.json`: Any processing errors
    - `results/<candidate_id>/results.json`: Per-candidate detailed results

- `--no-match` (optional): Disable job matching
  - By default, matching is enabled
  - When disabled, only job aggregation is performed (no scoring)

### Output Structure

```
results/
├── summary.csv                    # Summary table
├── errors.json                    # Processing errors
└── results/
    ├── anusha_kayam/
    │   └── results.json           # Full results for Anusha
    └── john_doe/
        └── results.json           # Full results for John
```

### summary.csv Format

| candidate_id | folder | num_jobs | num_matches | top_score | num_errors | status |
|--------------|--------|----------|-------------|-----------|------------|--------|
| anusha@example.com | anusha | 8 | 5 | 85.5 | 0 | success |
| john@example.com | john | 8 | 3 | 72.0 | 0 | success |

### Per-Candidate results.json

Contains complete job discovery pipeline output:
```json
{
  "status": "ok",
  "candidate": {
    "name": "Anusha Kayam",
    "email": "anusha@example.com",
    "location": "Remote",
    "desired_titles": ["Power BI Developer", "Data Analyst"],
    "skills": ["Power BI", "SQL", "DAX", "Excel", "Azure", ...]
  },
  "query": {
    "titles": ["Power BI Developer", "Data Analyst"],
    "keywords": ["powerbi", "sql", "dax", "excel", "azure", ...],
    "locations": ["Remote"],
    "remote_ok": true
  },
  "jobs": [...],
  "matches": [
    {
      "candidate_id": "anusha@example.com",
      "job_fingerprint": "abc123...",
      "overall_score": 85.5,
      "decision": "strong_fit",
      "dimension_scores": {
        "skills_overlap": 90.0,
        "title_alignment": 85.0,
        "location_alignment": 100.0,
        "seniority_alignment": 80.0
      },
      "reasons": [
        "Strong skills overlap: 90%",
        "Strong title alignment: 85%",
        "Matched skills: powerbi, sql, dax"
      ],
      "matched_keywords": ["powerbi", "sql", "dax", ...],
      "missing_keywords": ["python", "aws"],
      "job_title": "Power BI Developer",
      "job_company": "Tech Corp",
      "job_location": "Remote",
      "job_url": "https://example.com/job/123"
    }
  ],
  "counts": {
    "jobs": 8,
    "errors": 0,
    "matches": 5
  }
}
```

### Exit Codes

- `0`: Success (at least one candidate processed)
- `1`: Error (invalid inputs, processing failure)
- `2`: No candidates found in directory

### Examples

#### Basic Usage

```bash
# Process all candidates with matching
python -m jobflow.scripts.batch_run \
  --candidates-dir ./data/candidates \
  --jobs ./data/jobs.json \
  --out ./output
```

#### Without Matching

```bash
# Only aggregate jobs, no scoring
python -m jobflow.scripts.batch_run \
  --candidates-dir ./data/candidates \
  --jobs ./data/jobs.json \
  --out ./output \
  --no-match
```

#### Pipeline Integration

```bash
# Run and capture JSON output
python -m jobflow.scripts.batch_run \
  --candidates-dir ./candidates \
  --jobs ./jobs.json \
  --out ./results > batch_summary.json

# Check exit code
if [ $? -eq 0 ]; then
  echo "Batch processing completed successfully"
  cat batch_summary.json | jq '.succeeded'
elif [ $? -eq 2 ]; then
  echo "No candidates found"
else
  echo "Batch processing failed"
fi
```

### Approval-Gated Batch Execution

For production use, batch processing should go through the approval framework to ensure proper oversight and auditability.

#### 3-Command Flow

**1. Review the Plan**

```bash
# Review the batch_run directive and generate an execution plan
python -m jobflow.scripts.review_directive batch_run \
  --auto-approve

# Or review manually without auto-approval
python -m jobflow.scripts.review_directive batch_run
```

This generates:
- Execution plan based on the `directives/batch_run.md` specification
- Risk assessment
- Approval artifact (if auto-approved or approved via policy)

**2. Approve the Plan** (if not auto-approved)

```bash
# Approve the plan manually
python -m jobflow.scripts.approve_plan \
  --plan-file ./plan.json \
  --approved-by "alice@example.com"
```

**3. Execute with Approval**

```bash
# Execute the approved plan with payload
python -m jobflow.scripts.execute \
  --directive batch_run \
  --approval approval.json \
  --payload payload.json
```

Where `payload.json` contains:
```json
{
  "candidates_dir": "./data/candidates",
  "jobs": "./data/jobs.json",
  "out": "./results/batch_2026_02_01",
  "match_jobs": true
}
```

#### Why Use Approval-Gated Execution?

- **Auditability**: Every execution is cryptographically tied to an approval artifact
- **Oversight**: Plans are reviewed before execution
- **Safety**: Prevents unauthorized batch processing of candidate data
- **Compliance**: Ensures proper authorization for processing PII
- **Traceability**: Approval artifacts include who approved, when, and what scope

#### Approval Scopes

- `single-run` (default): Approval intended for one execution
- `session`: Approval valid for multiple executions in the same session

Note: Single-run enforcement (blocking reuse) is not yet implemented. Both scopes currently allow reuse.

#### Direct CLI vs Approval-Gated

| Feature | Direct CLI | Approval-Gated |
|---------|-----------|----------------|
| Convenience | High - one command | Medium - 3 commands |
| Auditability | None | Full audit trail |
| Authorization | None | Required |
| Production Use | Development only | Recommended |
| Compliance | No | Yes |

### Submission-Ready Outputs (Apply Packs)

By default, batch processing generates **apply packs** - submission-ready exports for each candidate.

#### What Are Apply Packs?

Apply packs transform job discovery results into actionable application packets containing:
- Top N job matches (default: 25)
- Candidate information
- Match scores and decisions
- Pre-submission checklist

#### Output Structure

```
output/
├── apply_packs/
│   ├── anusha_kayam/
│   │   ├── applications_ready.json    # Full apply pack
│   │   └── applications_ready.csv     # Spreadsheet format
│   └── john_doe/
│       ├── applications_ready.json
│       └── applications_ready.csv
├── results/                            # Detailed discovery results
├── summary.csv                         # Batch summary with fit counts
└── errors.json
```

#### CSV Format

The `applications_ready.csv` file contains:

| Column | Description |
|--------|-------------|
| rank | Application ranking (1-N) |
| score | Match score (0-100) |
| decision | strong_fit / possible_fit / weak_fit |
| company | Company name |
| job_title | Job title |
| location | Job location |
| apply_url | Application URL |
| source | Job source identifier |
| reasons | Match reasons (semicolon-separated) |
| matched_keywords | Matched skills/keywords (semicolon-separated) |
| missing_keywords | Missing skills/keywords (semicolon-separated) |

#### Usage

```bash
# Default: apply packs enabled, top 25 jobs
python -m jobflow.scripts.batch_run \
  --candidates-dir ./candidates \
  --jobs ./jobs.json \
  --out ./results

# Custom top N
python -m jobflow.scripts.batch_run \
  --candidates-dir ./candidates \
  --jobs ./jobs.json \
  --out ./results \
  --top-n 50

# Disable apply packs
python -m jobflow.scripts.batch_run \
  --candidates-dir ./candidates \
  --jobs ./jobs.json \
  --out ./results \
  --no-apply-pack
```

#### Workflow

1. Review `applications_ready.csv` in Excel/Sheets
2. Filter by `decision == "strong_fit"`
3. Check `apply_url` for each application
4. Add notes in spreadsheet
5. Submit applications

The CSV format allows easy sorting, filtering, and tracking in spreadsheet software.

### Application Queue

Each candidate's apply pack includes an **application queue** (`application_queue.csv`) with merge-safe status tracking.

#### What Is the Application Queue?

The queue is a CSV file that preserves your application status and notes across reruns:
- First run: creates queue with `status="queued"` and empty notes
- You edit the CSV to track progress (applied, interview, etc.)
- Subsequent runs: **preserve your status/notes** while updating job data

#### Queue Columns

| Column | Description | Preserved on Rerun |
|--------|-------------|-------------------|
| job_fingerprint | Unique job identifier | - |
| rank | Application ranking (1-N) | No (updated) |
| score | Match score | No (updated) |
| decision | strong_fit / possible_fit / weak_fit | No (updated) |
| company | Company name | No (updated) |
| job_title | Job title | No (updated) |
| location | Job location | No (updated) |
| apply_url | Application URL | No (updated) |
| source | Job source | No (updated) |
| **status** | Application status | **Yes** |
| **notes** | Your notes | **Yes** |
| matched_keywords | Matched skills | No (updated) |
| missing_keywords | Missing skills | No (updated) |

#### Status Values

Track your progress using these status values:
- `queued` - Default, not yet applied
- `applied` - Application submitted
- `rejected` - Application rejected
- `interview` - Interview scheduled/completed
- `offer` - Offer received
- `withdrawn` - Application withdrawn

You can use custom status values as needed.

#### Rerun Behavior

When you rerun batch processing:

1. **Existing jobs**: Status and notes preserved, other fields updated from new results
2. **New jobs**: Added with `status="queued"` and empty notes
3. **Removed jobs**: Kept in queue to preserve your tracking

This allows you to:
- Re-run when new jobs are posted
- Update match scores as candidate profile improves
- Never lose your application tracking data

#### Example Workflow

```bash
# First run - creates queues
python -m jobflow.scripts.batch_run \
  --candidates-dir ./candidates \
  --jobs ./jobs.json \
  --out ./results

# Open results/apply_packs/candidate_name/application_queue.csv
# Update status column: "applied", "interview", etc.
# Add notes: "Submitted via LinkedIn", "Phone screen scheduled", etc.

# Rerun with updated jobs file
python -m jobflow.scripts.batch_run \
  --candidates-dir ./candidates \
  --jobs ./jobs_updated.json \
  --out ./results

# Your status and notes are preserved!
# New jobs appear with status="queued"
```

#### Best Practices

- Use the queue CSV as your primary tracking tool
- Update status immediately after actions (applying, interviewing, etc.)
- Add detailed notes for follow-up context
- Re-run periodically to catch new jobs
- Sort by status in Excel to focus on queued applications

### Notes

- Processing is deterministic: same inputs always produce same outputs
- All file I/O is restricted to the output directory
- No network or database calls
- Safe for parallel execution with different output directories
- Candidate folders are discovered automatically (must contain `.xlsx` or resume files)
- Candidate ID is derived from email (preferred), name, or folder name
- Results are sorted alphabetically by candidate folder name
