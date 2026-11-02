# Plan: Applicant Tracking System

> Source PRD: `prd/applicant-tracking-system.md` (Approved 2026-11-01)
> Also read: `prototypes/stage-rules-decisions.md`, `prototypes/pipeline-ui-decisions.md`
> Status: Approved · 2026-11-01. Nothing is implemented yet.

User stories are cited as **US-n** and approved stage rules as **R-n**, both numbered as in the PRD.

## Before Phase 1

After this plan is approved and before any implementation, CLAUDE.md is created and you approve it. It's created in its own step, not by this plan or by any phase. Phases only update it afterwards (see step 8 below).

## Architectural decisions

Durable decisions that apply across all phases.

- **Owning app**: one Django project package `config` and one app `hiring`. All hiring models, forms, views, templates, services and tests live in `hiring`. No accounts app and no custom user model.
- **Auth**:
  - Django's built-in `User`, login view and logout view. Accounts are created by an administrator in Django admin.
  - Every page except login requires an authenticated, active user. Django's `LoginRequiredMiddleware` does this site-wide so a new view can't be left unprotected by accident. Inactive accounts can't sign in, and an existing session stops working once its account is deactivated.
  - `LOGIN_REDIRECT_URL` points to the pipeline workspace. Log out is a POST form in the nav, as Django's logout view requires.
  - Employee accounts aren't staff or superusers, so they can't reach `/admin/`.
- **URLs** (app namespace `hiring`, integer primary keys, no slugs):

  | Path | Purpose |
  |---|---|
  | `/accounts/login/`, `/accounts/logout/` | Django auth views |
  | `/admin/` | Django admin (administrators only) |
  | `/` | Pipeline workspace: first open job by title, or the empty state |
  | `/pipeline/jobs/<job_pk>/` | Workspace for one job. Query string: `jobs=open\|closed\|all` (sidebar filter, from Phase 7), `tab=active\|finished\|all`, `q=` |
  | `/pipeline/applications/<pk>/` | One application. A basic full page in Phase 6, then the workspace with it selected (job derived from it, same query string). Full page normally, detail partial for HTMX |
  | `/pipeline/applications/<pk>/move/` | POST a stage move or reopen (target stage, optional reason) |
  | `/pipeline/applications/<pk>/details/` | POST applied-on date and notes |
  | `/pipeline/jobs/<job_pk>/applications/new/` | Record an application for this job |
  | `/candidates/<pk>/applications/new/` | Record an application for this candidate |
  | `/applications/<pk>/delete/` | Delete confirmation for a never-moved application |
  | `/candidates/`, `/candidates/new/`, `/candidates/<pk>/`, `/candidates/<pk>/edit/`, `/candidates/<pk>/delete/` | Candidate pages |
  | `/jobs/`, `/jobs/new/`, `/jobs/<pk>/`, `/jobs/<pk>/edit/`, `/jobs/<pk>/delete/` | Job pages |
  | `/jobs/<pk>/close/` | GET confirmation page, POST closes |
  | `/jobs/<pk>/reopen/` | POST reopens (no confirmation) |
  | `/skills/`, `/skills/new/`, `/skills/<pk>/edit/`, `/skills/<pk>/delete/` | Skill pages |

  Close, reopen and delete accept a `next` return address, validated with Django's `url_has_allowed_host_and_scheme`, with a safe default otherwise.
- **Models** (all in `hiring`):
  - `Skill`: `name`. Trimmed. Unique case-insensitively through a database constraint on `Lower("name")`.
  - `JobOpening`: title, department, employment type (choices), description, optional location, status (Open/Closed, default Open), `closed_at`, `created_at`, `updated_at`. `skills` is a plain `ManyToManyField(Skill)`.
  - `Candidate`: first and last name, email, optional phone, location, profile URL and notes, source (choices) with optional source details, timestamps. Email trimmed and lowercased. Unique case-insensitively through a database constraint on `Lower("email")`.
  - `Application`: `candidate` FK and `job` FK (both `on_delete=PROTECT`, fixed after creation), `applied_on` (default `timezone.localdate`, never in the future), optional notes, `stage`, timestamps. Database unique constraint on (candidate, job).
  - `StageHistoryEntry`: `application` FK (`on_delete=PROTECT`), `old_stage` (blank for the initial entry), `new_stage`, `changed_at`, `changed_by` FK to `User` (`PROTECT`), optional `reason` (only for moves to Rejected or Withdrawn).
  - Migrations are added in the phase that first needs each model, so every phase migrates cleanly from the one before.
- **Current stage storage (settles a PRD deferral)**: `Application.stage` stores the current stage so lists, tabs and counts are simple queries. Only `services.py` writes it, in the same transaction as the history entry that records the change. The two rule facts (the stage before the current Hired/Rejected outcome, and whether the application was ever reopened from Withdrawn) are always derived from history and never stored. A test checks that `stage` always equals the latest history entry's `new_stage`. "Most recent stage change first" ordering uses the latest history timestamp, read through a query annotation.
- **Where rules live** (as in the PRD):
  - `hiring/stages.py`: stage list, active and final groups, and a pure decision function returning allowed or blocked plus a reason. No database access.
  - `hiring/services.py`: create application, move or reopen, close job, reopen job. Each derives facts from history, asks `stages.py`, and writes the change plus its history entry in one `transaction.atomic()` block. A blocked move changes nothing.
  - Forms and model validation handle trimming, normalization and the no-future applied-on date.
  - Views read the request, call a service or query, and return a full page or a partial.
  - Deletion rules live in the models' `delete()` and in custom QuerySets, so admin single and bulk deletes follow them.
- **HTMX responses**: a view returns a partial only when `HX-Request` is present and `HX-History-Restore-Request` isn't. Otherwise it returns the full page. Every workspace partial can also be rendered as part of the full page.
- **Front end**: Tailwind CSS and DaisyUI through django-tailwind-cli. HTMX is loaded from a vendored static file pinned to one version. Recommended theme: DaisyUI's built-in `dark` theme as the only theme, with contrast checked by hand in Phase 1 and again in the final phase.
- **Time**: `USE_TZ = True`, `TIME_ZONE = "America/Chicago"`. Applied-on default and validation use `timezone.localdate()`.
- **Tooling**: uv manages the project and dependencies. Ruff handles linting and formatting. pytest and pytest-django run the tests. All three are configured in `pyproject.toml` in Phase 1.
- **Browser tests**: none planned. Back/Forward, history restore, narrow screens and contrast stay on the manual checklist, as the PRD allows.

## How every phase runs

Each phase is one session, started with:

```
/implement @prd/applicant-tracking-system.md @plans/applicant-tracking-system.md implement phase <N>
```

The steps follow `.claude/skills/implement/SKILL.md` and `.claude/skills/tdd/SKILL.md`.

1. **Understand the phase.** Read the PRD, this plan and the existing code. Implement only this phase. Don't begin the next one.
2. **Test-candidate approval (`/tdd` step 1).** Before writing any code, the agent proposes **at most three** behaviors from this phase's acceptance criteria as a numbered list, with one sentence each on why it's a good TDD candidate, and doesn't list rejected options. If nothing qualifies, it says so in one sentence with the reason. That's a legitimate answer. **Work stops until you approve the list.**
   - Each phase below lists *possible* candidates as a starting point. **None of them is approved.** The agent may propose different ones, fewer, or none. Only the list you approve in the session is used for TDD.
3. **TDD cycles (`/tdd` step 2), one approved behavior and one test at a time.** Built in the phase's natural order. When enough exists for a test to run:
   1. Write one test for the behavior.
   2. Run it. RED means it fails on an assertion. Any other failure means scaffolding is missing: build it and re-run.
   3. Show the test, why it failed, and what passing will prove. **Stop for your approval.** Change the test now if it describes the wrong thing.
   4. Write only enough code to pass.
   5. Run it again and confirm it passes (GREEN).
   6. Run the relevant existing tests for regressions.
   7. Summarize what made it pass and ask whether that implements the behavior or only satisfies the test. **Stop before moving on.**

   After approval, a mechanical repair to a test gets a one-line note. A change to what a test asserts goes back to you for re-approval. TDD isn't forced onto styling, documentation or anything without a clear testable behavior.
4. **Remaining requirements.** Everything not covered by approved TDD behaviors is built the normal way, with ordinary tests for its acceptance criteria.
5. **Feedback loops.** Run the full test suite (`uv run pytest`), the linter (`uv run ruff check .`), the formatter check (`uv run ruff format --check .`) and `uv run python manage.py makemigrations --check`. Fix and re-run until all pass.
6. **Manual verification.** The agent answers "How do I verify this phase manually in the browser?" with exact steps and URLs, based on the phase's checks below. **Work stops until you confirm manual verification passed.** The phase isn't marked complete before that.
7. **Mark the phase complete.** Tick its acceptance-criteria checkboxes in this plan.
8. **CLAUDE.md review.** The agent proposes changes to the existing CLAUDE.md as a diff, limited to commands, structure and conventions that **exist in the code and were verified in this phase**. No conventions for features that don't exist yet. If nothing needs changing, it says so. Nothing is written until you approve.
9. **Session log, when prompted.** You give the session-log prompt from the top of PROMPTS.md, and the agent appends the entry in that file's format. Per PROMPTS.md's rules, the agent never adds an entry unprompted.
10. **Review changes and the commit message.** The agent shows a summary of changed files (`git status` and `git diff --stat`) and a proposed commit message. **Work stops until you approve both.**
11. **Commit and push.** Only after manual verification passed and you approved the review: commit on `main` and push to `origin`.
12. **`/clear`.** You run `/clear` before starting the next phase, so each phase starts fresh from the PRD, this plan, CLAUDE.md and the code.

Each phase below ends with a short wrap-up line that points back to steps 7–12.

---

## Phase 1: Project setup, sign-in and dark app shell

**User stories**: US-1, US-2, US-3, US-4, US-5, US-6, US-69 (theme foundation), US-70 (nav collapse only)
**PRD sections**: Fixed technology requirements, Project structure, Access, Dates and time, Navigation (top nav)

### What to build

A running Django project managed by uv, with the `config` package and the `hiring` app, Ruff, pytest and pytest-django configured, and django-tailwind-cli with DaisyUI's dark theme and HTMX loaded. A base layout has the top nav (Pipeline, Candidates, Jobs, Skills, username, Log out), which collapses into a menu on narrow screens. Links to pages that don't exist yet point to simple placeholder pages, which later phases replace. Sign-in uses Django's login view, styled to match. After login, staff land on a placeholder Pipeline page. Every page requires an active, signed-in user. Timezone settings match the PRD. Admin works for a superuser created with `createsuperuser`. README gets setup and run instructions.

### Acceptance criteria

- [x] `uv sync`, `uv run python manage.py migrate` and the documented Tailwind run command start the app.
- [x] An anonymous visit to any page except login redirects to login.
- [x] An active employee account created in admin can sign in and lands on the Pipeline page.
- [x] An inactive account can't sign in, and a signed-in session stops working after the account is deactivated.
- [x] A regular employee account (not staff or superuser) can't use `/admin/`.
- [x] Log out works from the nav through POST and returns to login.
- [x] The dark theme applies to the login page, nav and placeholder pages.
- [x] Ruff and pytest are configured in `pyproject.toml` and pass.

### Possible TDD candidates (not approved)

1. Anonymous requests to a hiring page redirect to login.
2. An inactive user's existing session is refused on a hiring page.

### Manual browser checks

- In admin as superuser, create an employee account (not staff), then sign in as that employee in a private window and land on Pipeline.
- Visit `/admin/` as the employee and confirm access is refused.
- Visit `/candidates/` while signed out and confirm the redirect to login.
- Deactivate the employee in admin, refresh the employee's window, and confirm it returns to login. Confirm signing in again fails.
- Narrow the window and confirm the nav collapses into a menu with no horizontal scrolling.
- Check the dark theme for readable text and contrasted buttons.

**Wrap-up:** steps 7–12. For CLAUDE.md, only the setup, run, test, lint and format commands verified in this phase and the actual project layout.

---

## Phase 2: Skills page

**User stories**: US-25, US-26, US-27
**PRD sections**: Models (Skill), Navigation (Skills), Record lifecycle (Skills)

### What to build

The `Skill` model and migration. The Skills page lists skills alphabetically, with create, rename and delete pages. Names are trimmed, and a case-insensitive database constraint plus a friendly form error block duplicates like "Python" and " python ". Delete uses a confirmation page. Usage protection arrives with jobs in Phase 3. Skill is registered in admin.

### Acceptance criteria

- [x] Skills are listed alphabetically, case-insensitively.
- [x] Creating a skill trims the name.
- [x] A name that differs from an existing skill only by case or spaces shows a form error on create and on rename.
- [x] Renaming a skill to its own name with different capitalization works.
- [x] The database rejects a case-insensitive duplicate even when the form is bypassed.
- [x] An unused skill can be deleted after confirmation.

### Possible TDD candidates (not approved)

1. Creating a skill whose name differs from an existing one only by case or spaces fails with a form error.
2. Renaming a skill to a different capitalization of its own name is allowed.

### Manual browser checks

- Create "Python", then try "python" and "  Python  " and confirm both show an error.
- Rename "Python" to "python" and confirm it saves.
- Create several skills and confirm alphabetical order.
- Delete an unused skill through the confirmation page.

**Wrap-up:** steps 7–12.

---

## Phase 3: Job openings with skills

**User stories**: US-16, US-17, US-18, US-19, US-22 (last updated), US-23 (editing; closed state comes in Phase 4), US-24 (confirmation page; application protection comes in Phase 6), US-28
**PRD sections**: Models (JobOpening), Navigation (Jobs list), Record lifecycle (Jobs, Skills), Where rules live (skill deletion)

### What to build

The `JobOpening` model and migration with a plain many-to-many to `Skill`. Jobs list with a GET title search, an Open/Closed/All filter defaulting to Open, alphabetical by title, 25 per page, and search and filter kept when paging. Its columns are title, department, location, type, status and closed date. The active-applications column shows 0 until Phase 7. Create, detail (with skills, created and last-updated times), edit and delete-confirmation pages. New jobs start Open.

Deleting a skill used by any job is blocked in the app, in the model's `delete()`, and in a custom QuerySet `delete()`, so admin single and bulk deletes are blocked too. The skill delete page explains which jobs use it. Renaming a skill shows the new name on every job. JobOpening is registered in admin.

### Acceptance criteria

- [x] A job requires title, department, employment type and description. Location is optional. New jobs are Open.
- [x] Skills can be attached and changed on create and edit.
- [x] The jobs list searches by title, filters Open (default), Closed or All, sorts by title, shows 25 per page, and keeps search and filter across pages.
- [x] Job detail shows skills, created time and last-updated time in Central time.
- [x] A job with no applications can be deleted after confirmation.
- [x] A skill used by any job can't be deleted through the app view, `Skill.delete()` or `Skill.objects.filter(...).delete()`. An unused skill can.
- [x] Renaming a skill updates its name on every job that uses it.

### Possible TDD candidates (not approved)

1. Deleting a skill used by a job is refused through QuerySet delete, and the link and skill remain.
2. The jobs list defaults to Open and keeps the search and filter in pagination links.

### Manual browser checks

- Create three jobs with skills and confirm they're Open and listed by title.
- Search by part of a title, switch the filter, and page through with more than 25 jobs (a shell loop is fine for creating them) to confirm the search and filter stay in the URL.
- Try to delete a skill used by a job, from the Skills page and from admin bulk delete, and confirm both are refused.
- Rename that skill and confirm the job detail shows the new name.
- Delete a job through its confirmation page.

**Wrap-up:** steps 7–12.

---

## Phase 4: Closing and reopening jobs

**User stories**: US-17, US-20, US-21, US-22 (closed date), US-23 (closed jobs stay closed when edited)
**PRD sections**: Navigation (Closing and reopening jobs), Record lifecycle (Closed jobs), R-13 (job side)

### What to build

`services.py` begins with close-job and reopen-job operations. Job detail has a Close job button leading to a confirmation page (GET) that shows how many applications are active and explains the effects: stages stay unchanged, only Reject and Withdraw remain available, and new applications are blocked. The count reads 0 until Phase 7. Confirming (POST) sets Closed and `closed_at`. Reopen job is a POST button with no confirmation that sets Open and clears `closed_at`. Both return to a validated `next` address, defaulting to job detail. Editing a closed job never changes status or `closed_at`. The form doesn't expose them.

### Acceptance criteria

- [x] Closing requires the confirmation page and a POST. A GET never closes the job.
- [x] Closing sets status Closed and `closed_at`. Reopening sets Open and clears `closed_at`.
- [x] Both actions redirect to a same-site `next` address, and an off-site `next` falls back to job detail.
- [x] Editing a closed job's details and skills leaves status and `closed_at` unchanged and updates last-updated.
- [x] The jobs list and detail show the closed date.

### Possible TDD candidates (not approved)

1. Editing a closed job keeps its status and `closed_at` unchanged.
2. Close and reopen ignore an off-site `next` address and use the safe default.

### Manual browser checks

- Close a job through the confirmation page and confirm the explanation text, the Closed status and the closed date on detail and in the list's Closed filter.
- Edit the closed job's description and skills and confirm it stays Closed with the same closed date.
- Reopen it and confirm Open with no closed date.
- Manually change `next` in the address bar to an external site and confirm you land on job detail instead.

**Wrap-up:** steps 7–12.

---

## Phase 5: Candidates

**User stories**: US-7, US-8, US-9, US-10, US-11 (source field only; nothing changes it), US-12, US-13, US-15 (confirmation page; application protection comes in Phase 6)
**PRD sections**: Models (Candidate), Navigation (Candidates list), Record lifecycle (Candidates), Access and editing acceptance criteria

### What to build

The `Candidate` model and migration. Candidates list with a GET search by first name, last name or email, sorted by last name then first name, 25 per page, and search kept when paging. Columns are name, email, source and number of applications (0 until Phase 7). Create, detail, edit and delete-confirmation pages. Email is trimmed and lowercased, with a case-insensitive database constraint and a friendly form error on create and on edit. Keeping a candidate's own email on edit isn't a duplicate. Candidate is registered in admin.

### Acceptance criteria

- [x] First name, last name and email are required. Phone, location, profile URL, notes, source details are optional. Source uses the four fixed choices.
- [x] Email is stored trimmed and lowercased.
- [x] Creating, or editing to, an email that matches another candidate in different case or with spaces shows a form error.
- [x] Saving an edit with the candidate's own email (any case) succeeds.
- [x] The database rejects a duplicate email when the form is bypassed.
- [x] Search matches name or email, the list sorts by last then first name, shows 25 per page and keeps the search across pages.
- [x] A candidate with no applications can be deleted after confirmation.

### Possible TDD candidates (not approved)

1. Editing a candidate to another candidate's email in different capitalization and with spaces is rejected.
2. Editing a candidate while keeping their own email in different capitalization is accepted.
3. Search by email finds the candidate regardless of the case typed.

### Manual browser checks

- Create a candidate with "  Jane.Doe@Example.com " and confirm it's shown as `jane.doe@example.com`.
- Try creating a second candidate with "JANE.DOE@example.com" and confirm the error.
- Edit the first candidate without changing the email and confirm it saves. Edit another candidate to Jane's email and confirm the error.
- Search by part of a last name and by email, and page through more than 25 candidates.
- Delete a candidate with no applications through the confirmation page.

**Wrap-up:** steps 7–12.

---

## Phase 6: Recording an application from the candidate page

**User stories**: US-15, US-24, US-30, US-31, US-32 (default and no future date at creation), US-34, US-35, US-38, US-53 (initial entry)
**Stage rules**: R-1, R-12 (new applications), R-14, R-15
**PRD sections**: Models (Application, Stage history entry, Stages), Navigation (Recording applications), Where rules live (PROTECT, services)

### What to build

The first end-to-end application path. `Application` and `StageHistoryEntry` models and migration. `stages.py` starts with the stage list and active/final groups. The create-application service validates and writes the application at Applied plus its initial history entry (blank old stage, current user) in one transaction. It blocks closed jobs and duplicates, with the unique constraint as a backstop.

Candidate detail gets an "Add application" action at `/candidates/<pk>/applications/new/`. The form offers only open jobs the candidate hasn't applied to. Applied-on defaults to today and rejects future dates. The form logic is written to be shared with the job-side entry point in Phase 7.

After saving, staff land on a basic full-page application view at `/pipeline/applications/<pk>/` showing the candidate, job, applied-on date, current stage and the stage history. Phase 7 turns this URL into the workspace with the application selected. Candidate detail lists the candidate's applications, each linking to that page.

Candidates and jobs with applications can't be deleted. Their delete pages explain why instead of failing with an error.

### Acceptance criteria

- [x] A new application starts at Applied with exactly one history entry (blank old stage, Applied, current user, timestamp).
- [x] The candidate-page picker lists only open jobs the candidate hasn't applied to.
- [x] A duplicate submission (forged POST or race) is refused with a form error, including when the existing application is Rejected or Withdrawn. The test sets that stage directly until Phase 8.
- [x] Recording an application on a closed job is refused by the service and writes nothing.
- [x] The same candidate can apply to two different open jobs as separate applications.
- [x] Applied-on defaults to the local date, and a future date is rejected.
- [x] After saving, staff land on the application page showing the candidate, job, applied-on date, stage and history.
- [x] Candidate detail lists the candidate's applications, each linking to its application page.
- [x] A candidate or job with applications can't be deleted through the app view, `delete()` or QuerySet delete. The view explains why.
- [x] An application's candidate and job aren't editable anywhere in the app.

### Possible TDD candidates (not approved)

1. Creating an application writes it at Applied with one initial history entry in the same transaction.
2. Creating a duplicate application is refused even when the existing one is Rejected.
3. Creating an application for a closed job is refused and writes nothing.

### Manual browser checks

- From a candidate's detail page, add an application and confirm you land on its page at Applied, with one history entry showing you and the time in Central time.
- Return to the candidate page and confirm the application is listed and links to its page, that the job no longer appears in the picker, and that closed jobs never do.
- Add a second application for the same candidate to a different open job.
- Try a future applied-on date and confirm the error.
- Try to delete that candidate, and one of those jobs, and confirm each delete page explains why it's blocked.

**Wrap-up:** steps 7–12.

---

## Phase 7: The pipeline workspace

**User stories**: US-14 (links into the workspace), US-29, US-36, US-55, US-59 (full-page selection), US-60, US-68
**PRD sections**: Pipeline workspace (Layout, Detail panel basics, Empty state), Navigation (Recording applications, Candidate detail)

### What to build

The three-column workspace replaces the Phase 1 placeholder at `/` and `/pipeline/jobs/<job_pk>/`:
- **Jobs sidebar:** open and closed jobs, with in-progress counts. Each job is a normal link.
- **Application list:** the selected job's applications, a simple list for now. Grouping, tabs and search come in Phase 10.
- **Detail panel:** candidate summary, job, applied-on date, current stage, the stage progress indicator and the stage history timeline.

`/pipeline/applications/<pk>/` now renders the workspace with that application's job open and the application selected and highlighted, replacing the Phase 6 basic page. Selecting an application is a normal full-page link in this phase.

The selected job gets the second entry point, `/pipeline/jobs/<job_pk>/applications/new/`, using the Phase 6 form logic and service. Its picker offers only candidates without an application for that job. It isn't offered for a closed job. Both entry points now land in the workspace with the new application selected, and candidate-detail links open the workspace.

Counts become real everywhere: sidebar in-progress counts, the jobs list's active-applications column, the candidates list's applications column, and the close-job page's active count.

Empty states:
- With no open jobs, the workspace shows a clear message and a link to create a job, plus a "Show closed jobs" link that switches the sidebar filter to Closed.
- A job with no applications says so and offers the add-application action when the job is open.

**Sidebar filter (approved addition during this phase, 2026-11-01):**
- Open, Closed and All links at the top of the sidebar, kept in the URL as `jobs=open|closed|all`.
- With no valid `jobs` value, `/` defaults to Open, and a job or application URL defaults to that job's status.
- Sidebar job links and application-selection links always carry the current `jobs` value explicitly.
- Changing the filter never changes the displayed job or application. The filter links target the current job or application URL, including on `/`. If the filter hides the selected job, the sidebar shows a short explanation.
- Alphabetical order and in-progress counts are unchanged. All navigation is normal GET.

### Acceptance criteria

- [x] `/` opens the first open job by title, or the no-open-jobs empty state with a create-job link and a Show closed jobs link.
- [x] The sidebar lists open and closed jobs with in-progress counts, and closed jobs are reachable.
- [x] The sidebar filter defaults to Open on `/` and to the job's status on a job or application URL, is carried in sidebar and application links, falls back to the default for unknown values, never changes the displayed job or application, and explains when it hides the selected job.
- [x] `/pipeline/applications/<pk>/` renders the full workspace with that job, the application highlighted, and its detail panel with the progress indicator and history.
- [x] The job-side picker lists only candidates without an application for that job, and isn't available on a closed job.
- [x] After recording from either entry point, the workspace opens with the new application selected.
- [x] Candidate detail links open the workspace with that application selected.
- [x] The jobs list, candidates list and close-job page show real counts.

### Possible TDD candidates (not approved)

1. The job-side picker excludes candidates who already have an application for that job.
2. Sidebar in-progress counts include only active-stage applications.

### Manual browser checks

- Open `/` and confirm the first open job is shown. Switch jobs in the sidebar.
- From the workspace's selected job, add an application and confirm you land with it selected, and that the candidate disappears from that job's picker.
- From a candidate page, follow an application link and confirm the workspace opens with it highlighted and its details shown.
- Check the counts in the sidebar, jobs list, candidates list and close-job page against the data.
- Close every job and confirm the empty state, the create-job link, and that Show closed jobs lists the closed jobs.
- Switch the sidebar filter between Open, Closed and All on `/`, on a job and on an application, and confirm the displayed job and application never change, the filter stays in the URL when selecting jobs and applications, and the hidden-job note appears when the filter hides the selected job.
- Narrow the window and confirm the columns stack.

**Wrap-up:** steps 7–12.

---

## Phase 8: Moving applications

**User stories**: US-39, US-40, US-41, US-42, US-43, US-44, US-48, US-49, US-52, US-53, US-61, US-62 (closed-job alert)
**Stage rules**: R-2, R-3, R-4, R-5, R-11, R-12 (no move to Hired on a closed job)
**PRD sections**: Approved stage rules, Where rules live (stage-rules module, services), Pipeline workspace (Detail panel, Reject and withdraw, Stale moves)

### What to build

The `stages.py` decision function: given the current stage, target stage, whether the job is open, the stage before the current Hired/Rejected outcome, and whether the application was ever reopened from Withdrawn, it returns allowed or blocked with a human-readable reason. This phase implements and tests the moves among active stages and into final outcomes, and closed-job blocking. Reopening is Phase 9.

The move service derives the facts from history, re-checks the move, and writes the new stage plus one history entry (with an optional reason only for Rejected/Withdrawn) in one transaction. A blocked move changes nothing.

The detail panel gains:
- **Primary actions:** advance to the next stage, Reject… and Mark withdrawn….
- **Other allowed moves:** buttons for the remaining allowed targets, excluding Rejected and Withdrawn.
- **Blocked moves:** a collapsed section listing each blocked move and its reason.
- **Closed-job alert.**
- **Inline confirmation:** Reject… and Mark withdrawn… open an inline box (a `<details>` element) with an optional reason and a Confirm button. No other control reaches Rejected or Withdrawn.
- **Reasons in history:** the timeline shows each entry's reason.

Moves submit as normal POSTs that redirect back to the same workspace URL in this phase. Phase 12 converts them to HTMX. A stale move shows a clear error message and the refreshed actions.

### Acceptance criteria

- [ ] Parametrized `stages.py` tests cover R-2, R-3, R-4, R-5, R-11 and R-12 for every relevant (current, target) pair, including the reason text for blocked cases.
- [ ] On an open job, forward one step, forward skip (including to Hired) and backward to any earlier active stage succeed.
- [ ] Rejected or Withdrawn succeeds from every active stage, with the optional reason saved on that history entry and shown in the timeline.
- [ ] A move between final outcomes is blocked.
- [ ] On a closed job, only active → Rejected or Withdrawn succeeds, and → Hired is blocked.
- [ ] Every successful move writes exactly one history entry with the employee and time. A blocked move changes neither the stage nor the history.
- [ ] Submitting a move that's no longer allowed (stale page) shows an error and refreshed actions.
- [ ] The panel shows advance, Reject…, Mark withdrawn…, other allowed moves, collapsed blocked moves with reasons, and a closed-job alert where relevant.
- [ ] `Application.stage` always equals the latest history entry's `new_stage`.

### Possible TDD candidates (not approved)

1. The decision function, parametrized over (current, target, job open) for the open-job rules R-2 to R-5.
2. On a closed job, every move except active → Rejected/Withdrawn is blocked, including → Hired.
3. A blocked move submitted to the service leaves the stage and history unchanged.

### Manual browser checks

- Advance an application one step, skip it forward, then move it back, and confirm each history entry shows old stage, new stage, you, and the time in Central time.
- Click Reject…, leave the reason blank, and confirm the box requires Confirm. Repeat with a reason and confirm it appears in the timeline.
- Open the blocked-moves section and confirm the reasons read clearly.
- Close the job, return to the application, and confirm the closed alert and that only Reject… and Mark withdrawn… remain.
- Open the same application in two tabs, reject it in one, then try to advance it in the other, and confirm the error and refreshed actions.

**Wrap-up:** steps 7–12.

---

## Phase 9: Reopening finished applications and workspace job controls

**User stories**: US-45, US-46, US-47, US-50, US-51, US-62 (no-skip alert), US-67
**Stage rules**: R-6, R-7, R-8, R-9, R-10, R-13
**PRD sections**: Approved stage rules, Facts derived from stage history, Stage rules and Withdrawn reopening acceptance criteria, Navigation (Closing and reopening jobs)

### What to build

The rules the PRD flags as still needing verification. The decision function and move service handle reopening:
- Hired and Rejected reopen only to the stage before that outcome, derived from the history entry that entered it.
- Withdrawn reopens the same application to Applied.
- Once an application has a Withdrawn → Applied entry, every forward move must be exactly one stage, including Offer → Hired, permanently. Backward moves and Reject/Withdraw stay allowed.
- Reopening requires an open job.

The panel shows a Reopen primary action with its target and a no-skip alert on restricted applications. The workspace header gains Close job (to the existing confirmation page) and Reopen job, using the Phase 4 views and services. Both return to the same workspace URL with the selected application and query string kept. Reopening a job leaves finished applications finished.

### Acceptance criteria

- [ ] Reopening Withdrawn moves the same application to Applied from any prior stage, with no new application.
- [ ] After a Withdrawn reopen, Applied → Interview is blocked, Applied → Screening is allowed, Offer → Hired is allowed, backward moves are allowed, and Rejected/Withdrawn from any active stage are allowed.
- [ ] A restricted application that's Rejected and reopened still can't skip. One that's Hired and reopened to Offer is still restricted. One that withdraws and reopens again returns to Applied and stays restricted.
- [ ] An application never reopened from Withdrawn reopens from Hired/Rejected only to its previous stage and may skip forward afterward.
- [ ] Tests run repeated reopen and withdraw sequences and check both history-derived facts after every step.
- [ ] Reopening a finished application on a closed job is blocked.
- [ ] Reopening a job clears `closed_at`, re-enables active applications, and leaves finished ones unchanged.
- [ ] Close job and Reopen job in the workspace header return to the same application, tab and search.
- [ ] The no-skip alert shows on restricted applications.
- [ ] Every one of R-1 to R-15 now has at least one automated test.

### Possible TDD candidates (not approved)

1. Fact derivation from history across a repeated sequence (advance, withdraw, reopen, advance, reject, reopen, withdraw, reopen), with checks after each step.
2. After a Withdrawn reopen, a forward skip is blocked but Offer → Hired is allowed.
3. Reopening Hired or Rejected targets only the stage before that outcome.

### Manual browser checks

- Hire an application from Final Review, reopen it, and confirm it returns to Final Review and can still skip.
- Withdraw an application from Interview, reopen it, and confirm it's at Applied with the no-skip alert, that only Screening is offered forward, and that the blocked section explains why Interview is blocked.
- Walk it step by step to Offer → Hired, reopen, and confirm it's still restricted.
- Close the job from the workspace header, confirm you return to the same application, and confirm Reopen is blocked on finished applications. Reopen the job from the header and confirm finished applications stay finished.

**Wrap-up:** steps 7–12.

---

## Phase 10: Workspace list: stage groups, tabs and search

**User stories**: US-56, US-57, US-58, US-66 (tab and search in the URL)
**PRD sections**: Pipeline workspace (Application list), Filters acceptance criteria

### What to build

The application list groups the selected job's applications by stage in pipeline order, with the most recent stage change first within each group. Active (default), Finished and All tabs show counts that reflect the job and search before the tab is applied. A name-or-email search submits with a button or Enter.

The tab and search live in the URL (`?tab=&q=`). Application selection, stage moves and close/reopen returns keep them. Switching jobs resets them, but keeps the Phase 7 sidebar filter (`jobs=`). Navigation is still full-page in this phase.

### Acceptance criteria

- [ ] Groups appear in pipeline order, and within each group the most recent stage change comes first.
- [ ] Active shows active stages, Finished shows Hired/Rejected/Withdrawn, All shows everything. Active is the default.
- [ ] Tab counts reflect the job and search, independent of the active tab.
- [ ] Search matches candidate first name, last name or email.
- [ ] Tab and search survive selecting an application, a stage move, close/reopen, and a page refresh.
- [ ] An unknown `tab` value falls back to Active.

### Possible TDD candidates (not approved)

1. Tab counts reflect the current search but not the active tab.
2. Within a stage group, the application with the most recent stage change is listed first.

### Manual browser checks

- On a busy job, confirm group order and in-group ordering after moving one application.
- Switch tabs and confirm the counts stay the same. Search for a name and confirm all three counts change.
- Select an application with a search and tab active, refresh, and confirm the same view.

**Wrap-up:** steps 7–12.

---

## Phase 11: HTMX selection and browser history

**User stories**: US-59, US-66, US-70 (detail panel brought into view)
**PRD sections**: Pipeline workspace (HTMX and URL behavior), Direct application links and refresh, Back and Forward acceptance criteria

### What to build

Selecting an application swaps the detail panel and moves the selection highlight through HTMX, pushing `/pipeline/applications/<pk>/?tab=&q=` to browser history. The selection view returns the detail partial (plus an out-of-band highlight update) for HTMX requests, and the full workspace for normal requests and HTMX history-restore requests. Back and Forward restore the matching panel and highlight, including when the HTMX history cache is missed. On narrow screens the panel scrolls into view after selection.

### Acceptance criteria

- [ ] Selecting an application updates the panel and highlight without a full reload, and the URL includes the application, tab and search.
- [ ] The selection URL returns the partial with `HX-Request`, and the full page without it or with `HX-History-Restore-Request`.
- [ ] Opening an application URL directly (typed, bookmarked, or from a candidate page) renders the full workspace with that job, application, tab and search.
- [ ] Back and Forward across several selections restore the matching panel and highlight.
- [ ] On a narrow screen the detail panel comes into view after selection.

### Possible TDD candidates (not approved)

1. The selection view returns the partial for an HTMX request and the full page for a history-restore request.

### Manual browser checks

- Select four applications in turn, watching the network tab for partial responses, then press Back three times and Forward twice and confirm the panel and highlight match the URL each time.
- Clear the HTMX history cache (`localStorage.removeItem("htmx-history-cache")` in the console), press Back, and confirm the full page restores correctly.
- Open an application link from a candidate page and confirm the full workspace.
- In a narrow window, select an application and confirm the panel scrolls into view, with no horizontal scroll.

**Wrap-up:** steps 7–12.

---

## Phase 12: HTMX stage actions and application details

**User stories**: US-32 (editing), US-33, US-52, US-63, US-64, US-65
**PRD sections**: Pipeline workspace (HTMX and URL behavior, Filter mismatch, Stale moves), HTMX updates and Selected-application-no-longer-matching acceptance criteria

### What to build

Stage moves, reopens and inline Reject/Withdraw confirmations submit through HTMX. One response updates the detail panel and, out of band, the application list and the tab and sidebar counts. If the moved application no longer matches the current tab or search, it stays in the panel with a note saying so, and the tab and search don't change. A service-rejected move returns the panel with an error and refreshed actions.

The panel gains an application details form for applied-on date and notes, saved through HTMX, with an inline error for a future date. Candidate and job are shown but not editable. Saving details writes no history. Without JavaScript, the forms still work as normal POSTs.

### Acceptance criteria

- [ ] A stage action updates the panel, list and affected counts in one response without a full reload.
- [ ] A move that takes the application outside the tab or search keeps it in the panel with a no-longer-matches note, and the tab and search are unchanged.
- [ ] A move rejected by the service shows an error in the panel with refreshed actions, and the stage and history are unchanged.
- [ ] Saving applied-on date and notes updates the panel without a reload. A future date shows an inline error and isn't saved.
- [ ] Saving details creates no history entry and doesn't affect delete eligibility.
- [ ] After a move, Back and Forward still restore the right selection.

### Possible TDD candidates (not approved)

1. A move that takes the selected application out of the Active tab returns its updated panel with the no-longer-matches note.
2. Saving a future applied-on date returns the form with an inline error and leaves the stored date unchanged.

### Manual browser checks

- On the Active tab, reject an application with a reason and confirm the panel, list and counts update without a reload, with the no-longer-matches note.
- Advance an application and confirm the list reorders and the sidebar count stays correct.
- Edit notes and the applied-on date, save, and confirm no reload. Try tomorrow's date and confirm the inline error.
- Repeat the two-tab stale-move check and confirm the error appears inside the panel.
- After a move, use Back and Forward and confirm the selection still matches.

**Wrap-up:** steps 7–12.

---

## Phase 13: Application deletion and admin protections

**User stories**: US-2, US-37, US-54
**PRD sections**: Where rules live (deletion protection, stage history protection, Django admin), Record lifecycle (Applications), Deletion protection acceptance criteria

### What to build

The panel offers Delete application only for never-moved applications, leading to `/applications/<pk>/delete/`. The supported delete removes the single initial history entry and then the application in one transaction. Applications that have ever moved can't be deleted, even after returning to Applied. This holds through `Application.delete()`, a custom QuerySet `delete()`, admin single delete and admin bulk delete.

Application and stage history are registered in admin:
- Stage, candidate and job are read-only on an application.
- History appears read-only, with no add, edit or delete.
- There's no standalone way to add a history entry.

Tests cover every deletion path for candidates, jobs, applications and skills through admin single and bulk delete.

### Acceptance criteria

- [ ] A never-moved application can be deleted after confirmation, along with its initial history entry, in one transaction.
- [ ] An application that has ever moved can't be deleted through the app view, `delete()`, QuerySet delete, admin single delete or admin bulk delete, even after returning to Applied. Its history stays intact.
- [ ] Editing notes or applied-on date doesn't change delete eligibility.
- [ ] Candidates and jobs with applications, and used skills, can't be deleted through admin single or bulk delete.
- [ ] In admin, application stage, candidate and job are read-only, and history has no add, edit or delete.
- [ ] Staff can't add, edit or delete history entries through any app page.

### Possible TDD candidates (not approved)

1. Deleting an application that moved and returned to Applied is refused through QuerySet delete, with history unchanged.
2. Deleting a never-moved application removes it and its initial history entry together.
3. Admin bulk delete of a candidate with applications is refused.

### Manual browser checks

- Create an application, edit its notes, and delete it through the confirmation page.
- Move another application forward and back to Applied and confirm Delete isn't offered. Forge the delete URL and confirm refusal.
- In admin as superuser, try single and bulk deletes of a moved application, a candidate with applications, a job with applications and a used skill, and confirm each is refused with a clear message.
- In admin, open an application and confirm stage, candidate and job are read-only and history can't be added, changed or deleted.

**Wrap-up:** steps 7–12.

---

## Phase 14: Demo seed data and final polish

**User stories**: US-69, US-70, US-71, US-72
**PRD sections**: Demo data, Pipeline workspace (Theme, Responsive), Manual browser check list, Deferred to implementation planning (seed timestamps)

### What to build

A `seed_demo` management command that refuses to run if any hiring data exists and has no reset option. It creates:
- fictional skills,
- candidates, including some with several applications,
- open and closed jobs, including a closed job with in-progress applications,
- non-admin demo employee accounts with a development-only password printed in the terminal,
- applications created and moved through the real services: a no-skip application reopened from Withdrawn, and reopenable Hired and Rejected applications.

**Decide at the start of this phase:** whether services accept an optional keyword-only timestamp so seeded history has realistic past dates. This is an additive change that doesn't affect existing callers. Without it, seeded history uses the run time.

Then a final pass over the whole PRD manual checklist: dark-theme contrast on buttons, stage labels, blocked actions, dropdowns, alerts and forms, and the narrow-screen layout of every page with no horizontal scroll. Document `seed_demo` in README once it's verified.

### Acceptance criteria

- [ ] `seed_demo` on an empty database creates every scenario listed in the PRD, through the services.
- [ ] `seed_demo` refuses to run and changes nothing if any candidate, job, skill or application exists.
- [ ] Demo accounts aren't staff or superusers, and the password is printed with a development-only warning.
- [ ] Seeded history passes the same consistency check as everything else (stage equals the latest history entry).
- [ ] Every item on the PRD's manual browser checklist passes.
- [ ] README documents how to run `seed_demo`.

### Possible TDD candidates (not approved)

1. `seed_demo` refuses to run when hiring data exists and leaves it unchanged. The seeding itself is data, not a TDD candidate.

### Manual browser checks

- Run `seed_demo` on a fresh database, sign in as a demo employee, and walk each seeded scenario in the workspace: the no-skip alert, reopening Hired and Rejected, and the closed job with in-progress applications.
- Run `seed_demo` again and confirm it refuses.
- Full PRD checklist: Back/Forward across selections, including after a move. History restore after clearing the cache. Narrow-screen stacking with the panel brought into view and no horizontal scroll on every page. Dark-theme contrast for buttons, stage labels, blocked actions, dropdowns and alerts.

**Wrap-up:** steps 7–12. For CLAUDE.md, the verified `seed_demo` command.
