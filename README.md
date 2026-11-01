# Applicant Tracking System

An internal Django app where hiring staff track candidates, job openings, applications and a rule-governed hiring pipeline. Candidates never log in.

Requirements and plan: `prd/applicant-tracking-system.md` and `plans/applicant-tracking-system.md`.

## Requirements

- [uv](https://docs.astral.sh/uv/). It installs a matching Python (3.14+) if you don't have one.
- An internet connection on first run, to download the Tailwind CSS CLI (with DaisyUI) into `.django_tailwind_cli/`.

## Setup

```sh
uv sync
uv run python manage.py migrate
uv run python manage.py createsuperuser
```

The superuser is for Django admin only. Create employee accounts in admin at `/admin/` under **Users**. Leave **Staff status** and **Superuser status** unticked for hiring employees, so they can use every hiring page but not admin.

## Run

```sh
uv run python manage.py tailwind runserver
```

This starts the Django development server and rebuilds the CSS whenever templates change. Open <http://127.0.0.1:8000/> and sign in.

To build the CSS once without the server (for example before running `runserver` on its own):

```sh
uv run python manage.py tailwind build
```

## Checks

```sh
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run python manage.py makemigrations --check
```

## Troubleshooting

- **`UnicodeEncodeError` from a `tailwind` subcommand on Windows:** some django-tailwind-cli subcommands, such as `tailwind config`, print emoji that the default Windows console encoding can't handle. Set UTF-8 output first, then rerun. In PowerShell: `$env:PYTHONIOENCODING = "utf-8"`. `tailwind build` and `tailwind runserver` work without it.
- **CSRF error when saving a form, including admin:** signing in or out in the same browser replaces its CSRF token, so a form opened before that is refused. Reopen the form and save again.

## Project layout

- `config/`: Django project settings and root URLs.
- `hiring/`: the single app holding all hiring features, its templates and its tests (`hiring/tests/`).
- `templates/`: the base layout, top navigation and login page.
- `assets/css/source.css`: Tailwind and DaisyUI source (dark theme). It builds to `static/css/tailwind.css`, which isn't committed.
- `static/js/htmx.min.js`: vendored HTMX 2.0.4.
