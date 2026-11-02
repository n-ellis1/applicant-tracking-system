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

## Commands
- Setup: `uv sync`, then `uv run python manage.py migrate`
- Run (dev server + Tailwind watch): `uv run python manage.py tailwind runserver`
- Build CSS once: `uv run python manage.py tailwind build`
- Tests: `uv run pytest`
- Lint / format: `uv run ruff check .` and `uv run ruff format --check .` (apply with `uv run ruff format .`)
- Migrations check: `uv run python manage.py makemigrations --check`

## Project layout
- `config/`: settings and root URLs (`/admin/`, `/accounts/` auth views, then `hiring.urls`).
- `hiring/`: the only app. URL namespace `hiring`; templates in `hiring/templates/hiring/`; tests in `hiring/tests/test_*.py`, with shared fixtures in `hiring/tests/conftest.py` and data builders in `hiring/tests/helpers.py`.
- `hiring/stages.py`: the stage list, the active and final groups, and `check_move()`, which returns a `MoveCheck(allowed, reason)`. No database access.
- `hiring/services.py`: application creation, stage moves (`move_application`) and job close/reopen operations. Views use these shared operations.
- `hiring/templates/hiring/pipeline.html`: the pipeline workspace (jobs sidebar, application list, detail panel), with partials `_sidebar_job.html` and `_application_panel.html`. One `_workspace` view helper renders it for `/`, job URLs and application URLs.
- `templates/`: `base.html`, nav partials `_nav.html` / `_nav_links.html`, `registration/login.html`.
- `assets/css/source.css`: Tailwind + DaisyUI source. It scans the template folders and `hiring/forms.py` (for widget classes). Builds to `static/css/tailwind.css` (gitignored).
- `static/js/htmx.min.js`: vendored HTMX 2.0.4.

## Conventions
- `LoginRequiredMiddleware` protects every page site-wide. Don't add per-view login decorators; mark a view `login_not_required` only if it must be public.
- Keep Django's default `ModelBackend`: it's what refuses inactive users' existing sessions.
- Pages extend `base.html` and pass `active_nav` (`pipeline`, `candidates`, `jobs`, `skills`) to highlight the nav link.
- Use DaisyUI's `dark` theme only (`data-theme="dark"` on `<html>`); style with DaisyUI component classes.
- Forms live in `hiring/forms.py`; normalize user input in forms rather than model `save()` overrides.
- Where case-insensitive uniqueness is required, pair a database constraint with friendly form validation that excludes the current record on edit.
- App and admin forms should share validation behavior.
- Confirmation pages (delete, close) use GET for display and POST for the action. Actions without a confirmation page (reopen) are POST-only via `@require_POST`.
- A `next` return address is followed only if `url_has_allowed_host_and_scheme` accepts it for `request.get_host()`; otherwise use the page's safe default. Confirmation pages carry a valid `next` in a hidden field and use it for Cancel.
- Where built-in PROTECT is insufficient, enforce deletion rules on both model and QuerySet paths. App and admin deletion pages must explain blocking records instead of returning an error page.
- Service operations report expected business-rule refusals with `ValidationError`. Views display the message in the relevant form or panel.
- Validate service operations against current database state. Translate only identified constraint failures into friendly errors; let unrelated database errors propagate.
- Where a service checks eligibility, `EligibleChoiceField` displays eligible records while allowing existing submitted records to reach that validation. Never rely on picker filtering alone.
- Both application entry points build on `ApplicationForm` (applied-on date) and add their own `EligibleChoiceField` picker.
- "Active" or "in progress" means a stage in `ACTIVE_STAGES`. Count it with `JobOpening.objects.with_in_progress_count()` rather than recounting.
- After aggregate annotations, specify ordering explicitly where the page requires it; don't rely on `Meta.ordering`.
- Workspace pages take the displayed job and application from the URL path, never from the sidebar filter. Every sidebar job link, application link and filter link carries `jobs=open|closed|all` explicitly.
- Workspace POST forms preserve a valid `jobs` filter through their action URLs and redirects.
- Allowed and blocked moves and their explanations come from `check_move()`; templates don't decide transition rules.
- Never edit or regenerate a migration that has been applied or committed; add a new migration.
- List pages read search and filter from GET, show 25 per page, and fall back to the default filter for unknown values. Page links carry the cleaned search and filter values.
- Tests use pytest functions with pytest-django's `client` and `db` fixtures, not `TestCase` classes.
- On Windows, `uv run python manage.py tailwind config` needs `PYTHONIOENCODING=utf-8` (it crashes printing emoji otherwise).

## References
- PRD (requirements, stage rules, acceptance criteria): `prd/applicant-tracking-system.md`
- Phased implementation plan: `plans/applicant-tracking-system.md`
- Stage rule decisions: `prototypes/stage-rules-decisions.md`
- Pipeline UI decisions: `prototypes/pipeline-ui-decisions.md`
