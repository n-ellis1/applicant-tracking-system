# CLAUDE.md

Internal Django applicant tracking system where hiring staff track candidates, job openings, applications and a rule-governed hiring pipeline. Candidates never log in.

## Stack
- Python, Django, SQLite. uv for project and dependency management.
- Tailwind CSS + DaisyUI via django-tailwind-cli. HTMX for partial page updates.
- Ruff for linting and formatting. pytest + pytest-django for tests.

## Approved architecture decisions
- Use one Django project package (`config`) and one app (`hiring`), with Django's built-in `User` model and auth views. No custom user model or accounts app.
- Require an authenticated, active user on every hiring page. Give all employees equal hiring access; keep Django admin access separate and off by default.
- Keep stage rules in a pure stage-rules module, with no database access, that returns allowed or blocked plus a human-readable reason.
- Use shared service operations for application creation, stage changes, and job closing/reopening. Save application stage changes and their history together in a transaction.
- Derive past workflow facts from stage history rather than duplicating them in application fields.
- Keep views thin: read the request, call a service or query, and return a full page or an HTMX partial.
- Apply the PRD's record-protection rules consistently across app, ORM, and admin deletion paths.
- Use HTMX only in the pipeline workspace; use standard Django pages elsewhere.
- Enable timezone support: store UTC, display `America/Chicago`, and use `timezone.localdate()` for local dates.

## References
- PRD (requirements, stage rules, acceptance criteria): `prd/applicant-tracking-system.md`
- Phased implementation plan: `plans/applicant-tracking-system.md`
- Stage rule decisions: `prototypes/stage-rules-decisions.md`
- Pipeline UI decisions: `prototypes/pipeline-ui-decisions.md`
