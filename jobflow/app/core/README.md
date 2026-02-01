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
