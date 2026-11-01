# PRD: Applicant Tracking System

Status: Approved · 2026-11-01
Sources: design interview (grill-me), `prototypes/stage-rules-decisions.md`, `prototypes/pipeline-ui-decisions.md`

## Problem Statement

A company's hiring team has no shared place to track job openings, the candidates who apply, and where each application is in the hiring process. Candidates come from several channels: the company website, job boards, referrals and others. The same person may apply for more than one opening. Staff need to record applications, move them through a fixed set of hiring stages, and correct mistakes without losing track of what actually happened. They also need to close and sometimes reopen openings without corrupting the records of the people who applied. Today there's no consistent rule for what can move where, no history of who moved an application or when, and nothing preventing duplicate applications or the loss of hiring records.

## Solution

An internal Django web application used only by employees involved in hiring. Candidates never log in. Staff sign in with accounts created by an administrator. Every active employee has the same hiring access.

Staff manage candidates, job openings (Open or Closed) and a shared list of skills attached to openings. They record applications, and each candidate may have at most one application per opening. The main screen is a dark-themed **list-and-detail pipeline workspace**:
- a sidebar of job openings,
- the selected job's applications grouped by stage,
- a detail panel with a stage progress indicator, stage actions, notes and a full stage history.

Staff move applications between stages without reloading the whole page. Every move follows an approved set of stage rules, and every move is recorded in the stage history with the employee and time. Records that carry hiring history are protected from deletion.

## User Stories

### Access
1. As a hiring employee, I want to sign in with an account an administrator created for me, so that only authorized staff can use the system.
2. As an administrator, I want to create employee accounts in Django admin, so that there's no public sign-up.
3. As a hiring employee, I want every hiring page to require login with an active employee account, so that candidate information isn't exposed and deactivated accounts lose access.
4. As a hiring employee, I want the same hiring access as every other employee, so that I can do any hiring task without waiting for someone with special permissions. Equal hiring access doesn't include Django admin access.
5. As a hiring employee, I want to land on the pipeline workspace after signing in, so that I can start working right away.
6. As a hiring employee, I want to sign out from the navigation, so that I can end my session on a shared computer.

### Candidates
7. As a hiring employee, I want to record and later edit a candidate's first name, last name and email, so that I can identify them and keep their information current.
8. As a hiring employee, I want to optionally record and edit a candidate's phone, location, profile URL and general notes, so that I have useful contact and background details.
9. As a hiring employee, I want each email to be unique regardless of capitalization and extra spaces, checked the same way when a candidate is created or edited, so that the same person can't be entered twice.
10. As a hiring employee, I want to record how a candidate first came to the company (Company Website, Job Board, Referral or Other) with optional details, so that we know our sources.
11. As a hiring employee, I want the candidate's source to stay as originally recorded when they apply for other openings, so that it reflects how they first came to us.
12. As a hiring employee, I want to search candidates by name or email, so that I can find someone quickly.
13. As a hiring employee, I want the candidate list sorted by last name, then first name, and paginated, so that it stays easy to browse.
14. As a hiring employee, I want a candidate's detail page to list their applications with links to each one in the workspace, so that I can jump to the right application.
15. As a hiring employee, I want to delete a candidate entered by mistake, after confirmation, only if they have no applications, so that I can clean up errors without losing hiring history.

### Job openings
16. As a hiring employee, I want to create a job opening with title, department, employment type and description (required) and location (optional), so that openings are clearly described.
17. As a hiring employee, I want new openings to start as Open, so that they can receive applications immediately.
18. As a hiring employee, I want to attach existing skills to an opening, so that its requirements are clear.
19. As a hiring employee, I want to search jobs by title and filter by Open, Closed or All (default Open), so that I can find the opening I need.
20. As a hiring employee, I want to close an opening after a confirmation page that explains the effects on its applications, so that I don't close it by accident.
21. As a hiring employee, I want to reopen a closed opening with one action, so that I can resume hiring if a hire falls through.
22. As a hiring employee, I want to see when a job was closed and when it was last updated, so that I understand its recent history.
23. As a hiring employee, I want to edit a closed opening's details and skills without reopening it, so that I can fix mistakes without changing its status or closed date.
24. As a hiring employee, I want to delete an opening created by mistake, after confirmation, only if it has no applications, so that real hiring history is protected.

### Skills
25. As a hiring employee, I want a simple alphabetical Skills page where I can create skills, so that I don't need admin access to add one.
26. As a hiring employee, I want skill names to be unique regardless of capitalization and extra spaces, so that duplicates like "Python" and "python" can't exist.
27. As a hiring employee, I want to rename a skill and have the new name appear on every opening that uses it, so that I can fix typos.
28. As a hiring employee, I want deleting a skill to be blocked while any open or closed opening uses it, so that job records stay accurate.

### Applications
29. As a hiring employee, I want to record an application from the selected job in the workspace, choosing only candidates who haven't applied to that job, so that duplicates are prevented up front.
30. As a hiring employee, I want to record an application from a candidate's detail page, choosing only open jobs they haven't applied to, so that I can handle a candidate applying elsewhere.
31. As a hiring employee, I want new applications to start at Applied, so that every application has the same starting point.
32. As a hiring employee, I want an applied-on date that defaults to today and that I can edit later in the workspace detail panel, never to a future date, so that I can record when the candidate actually applied.
33. As a hiring employee, I want job-specific notes on each application that I can edit in the workspace detail panel, so that feedback about one job doesn't mix with other jobs.
34. As a hiring employee, I want the system to block a second application for the same candidate and opening, whatever stage the first one is in, so that each candidate has one record per job.
35. As a hiring employee, I want to be blocked from recording an application for a closed job, so that closed openings stay closed.
36. As a hiring employee, I want to be taken to the workspace with the new application selected after saving, so that I can continue working on it.
37. As a hiring employee, I want to delete an application recorded by mistake, after confirmation, only if it has never changed stages, so that real history is protected.
38. As a hiring employee, I want an application's candidate and job to be fixed once created, so that its history always describes the right candidate and job.

### Stage movement
39. As a hiring employee, I want to move an application forward one stage, so that I can advance a candidate through the normal process.
40. As a hiring employee, I want to skip forward past stages on an open job, so that I can fast-track strong candidates.
41. As a hiring employee, I want to move an application back to any earlier active stage, so that a candidate can get another screening or interview and mistakes can be corrected.
42. As a hiring employee, I want to reject or withdraw an application from any active stage, so that I can record its outcome at any point.
43. As a hiring employee, I want Reject and Mark withdrawn to always ask me to confirm in the panel, with an optional reason, so that I don't end an application by accident.
44. As a hiring employee, I want the reason saved on that history entry and shown in the timeline, so that I can later see why it ended.
45. As a hiring employee, I want to reopen a Hired or Rejected application to the stage it was in right before that outcome, so that I can fix a mistaken outcome.
46. As a hiring employee, I want reopening a Withdrawn application to return it to Applied, so that a returning candidate is re-evaluated from the start.
47. As a hiring employee, I want an application that was ever reopened from Withdrawn to be permanently unable to skip forward, so that a returning candidate truly repeats every stage.
48. As a hiring employee, I want direct moves between final outcomes to be blocked, so that every outcome change goes through an explicit reopen.
49. As a hiring employee, I want applications on a closed job to keep their stages and only be markable as Rejected or Withdrawn, so that a closed job stops progressing while I tidy up.
50. As a hiring employee, I want reopening a finished application to require its job to be open, so that closed jobs don't progress.
51. As a hiring employee, I want reopening a job to let its active applications move again without reopening finished ones, so that reopening a candidate stays a deliberate choice.
52. As a hiring employee, I want a clear error if a move is no longer allowed when I submit it, so that a stale page never leaves an application in a broken state.

### Stage history
53. As a hiring employee, I want each application to show a history of every stage change, including the initial Applied entry and reopens, with old stage, new stage, date and time, and the employee, so that I can follow the whole process.
54. As a hiring employee, I want stage history to be something staff can't edit or delete on its own, so that the record of what happened can be trusted. The only exception is deleting an eligible never-moved application, which also removes its initial history entry.

### Pipeline workspace
55. As a hiring employee, I want a sidebar of job openings, including closed ones, with in-progress counts, so that I can switch between jobs.
56. As a hiring employee, I want the selected job's applications grouped by stage in pipeline order, newest stage change first within each group, so that I can scan a busy opening.
57. As a hiring employee, I want Active, Finished and All tabs with counts, so that I can focus on people in progress or find Hired, Rejected and Withdrawn applications.
58. As a hiring employee, I want to search the job's applications by name or email, so that I can find a candidate in a busy pipeline.
59. As a hiring employee, I want selecting an application to show its details beside the list without reloading the page, so that I can work through candidates quickly.
60. As a hiring employee, I want a stage progress indicator in the detail panel, so that I can see where the application is at a glance.
61. As a hiring employee, I want primary actions (advance to the next stage, reopen, reject, mark withdrawn), buttons for other allowed moves, and a collapsed explanation of blocked moves, so that I know what I can do and why some moves aren't available.
62. As a hiring employee, I want visible alerts when a job is closed or an application can't skip stages, so that restrictions aren't a surprise.
63. As a hiring employee, I want to edit and save an application's notes and applied-on date in the detail panel without a full page reload, so that I can record feedback and corrections as I go.
64. As a hiring employee, I want stage changes to update the detail panel, the list and the counts together, so that everything on screen stays consistent.
65. As a hiring employee, I want an application that no longer matches my current tab or search after a move to stay visible with an explanation, so that I don't lose my place.
66. As a hiring employee, I want the URL to reflect the selected application, tab and search, so that refresh, bookmarks, links and Back and Forward bring me to the same view.
67. As a hiring employee, I want Close job and Reopen job in the workspace header and on the job detail page, returning me to where I was, so that I can manage a job while reviewing its pipeline.
68. As a hiring employee, I want a clear empty state with a link to create a job when there are no open jobs, so that I know what to do next.
69. As a hiring employee, I want a dark interface with readable text and clearly contrasted buttons, stage labels and blocked actions, so that long sessions are comfortable.
70. As a hiring employee, I want the workspace to stack its columns and bring the detail panel into view on narrow screens, so that it stays usable in smaller windows.

### Development and demos
71. As a developer, I want a demo seed command that creates fictional data covering the important stage and reopening scenarios through the real services, so that I can demo and manually test the rules quickly.
72. As a developer, I want the seed command to refuse to run if hiring data already exists, so that it can never mix with or erase real records.

## Implementation Decisions

### Fixed technology requirements (assignment)
- Python, Django, SQLite, uv for project and dependency management.
- Tailwind CSS with DaisyUI through django-tailwind-cli. HTMX for partial page updates.
- Ruff for linting and formatting.
- Automated tests with **pytest and pytest-django**. Stage-rule cases use parametrized tests where they fit.

### Project structure
- One Django project configuration package (`config`) and **one app (`hiring`)** containing all hiring models and features.
- Django's built-in `User` model and built-in login and logout views. No custom user model and no accounts app.

### Access
- Accounts are created by an administrator in Django admin. There's no public sign-up.
- Every hiring page requires an authenticated, **active** employee account. Inactive accounts can't sign in or reach hiring pages.
- All active employees have identical **hiring** access, with no roles or per-job permissions.
- Equal hiring access is separate from **Django admin access**. Employee accounts aren't staff or superusers by default. Admin access is granted only to administrators who manage accounts.

### Models
- **Candidate:** first name, last name, email (required). Phone, location, profile URL, notes (optional). Source (fixed choices: Company Website, Job Board, Referral, Other) with optional source details. Created and updated timestamps. Email is trimmed and normalized, and unique case-insensitively, backed by a database constraint on the lowercased value. Source isn't changed by later applications. Candidates can be edited after creation, using the same validation, normalization and case-insensitive unique-email rule as creation. An edit keeping the candidate's own email isn't treated as a duplicate. There are no resume uploads.
- **JobOpening:** title, department, employment type (Full-time, Part-time, Contract, Internship) and description (required). Location (optional plain text, may be "Remote"). Department is plain text. Status (Open or Closed, default Open), `closed_at`, and created and updated timestamps. Skills through a plain many-to-many relationship.
- **Skill:** name, trimmed and unique case-insensitively, backed by a database constraint.
- **Application:** candidate and job (fixed after creation), applied-on date (defaults to the local date, can't be in the future when created or edited), optional notes, and created and updated timestamps. A database unique constraint on (candidate, job). After creation, only the applied-on date and notes are editable, in the workspace detail panel. Editing them doesn't create stage history.
- **Stage history entry:** belongs to an application. It records old stage (empty for the initial entry), new stage, timestamp, the employee who made the change, and an optional reason, offered only for moves to Rejected or Withdrawn.
- **Stages:** Applied, Screening, Interview, Final Review, Offer (active), and Hired, Rejected, Withdrawn (final outcomes).

### Approved stage rules
Applies to all stage moves and reopens. Full rationale is in `prototypes/stage-rules-decisions.md`.
1. New applications start at **Applied**.
2. On an open job, staff can **skip forward** to any later active stage or to Hired, unless rule 7 applies.
3. On an open job, staff can **move back to any earlier active stage**.
4. Staff can move to **Rejected or Withdrawn from any active stage**.
5. There are **no direct moves between final outcomes**. Staff must reopen first.
6. **Hired and Rejected reopen only to the stage they were in immediately before that outcome.**
7. **Reopening Withdrawn returns the same application to Applied.** From then on, that application can **never skip forward**: every forward move must be exactly one stage, including Offer → Hired. Backward moves and moves to Rejected or Withdrawn remain allowed.
8. The no-forward-skip restriction is **permanent**. It persists through later Hired or Rejected outcomes and their reopens. If the application withdraws and reopens again, it returns to Applied again and stays restricted.
9. Offer → Hired is allowed for a restricted application, because it's a single step.
10. **Reopening any finished application requires its job to be open.**
11. **Closing a job** leaves applications in their current stages and **blocks all moves except active → Rejected or Withdrawn**.
12. A closed job **can't accept new applications** and **can't have applications moved to Hired**.
13. **Reopening a job** clears `closed_at` and lets active applications move again. It doesn't reopen finished applications.
14. **Duplicate applications** (same candidate and opening) are always blocked, whatever stage the existing one is in.
15. A candidate may apply to **different open jobs** using the same candidate record with separate applications.

### Where rules live
- **Database constraints** (unique constraints enforced by SQLite itself): unique (candidate, job), case-insensitive unique candidate email, and case-insensitive unique skill name.
- **Protections enforced through Django's deletion handling** (`on_delete=PROTECT`): Django refuses to delete a candidate or job that has applications, or an application that has stage history entries. This applies to Django model deletes, QuerySet deletes and admin deletes. It's Django behavior, not a SQLite constraint, so it doesn't cover raw SQL or other code that bypasses Django's ORM.
- **Rules enforced through supported app and admin operations** (these aren't impossible to bypass, for example with raw SQL or a shell; they're enforced on every supported path):
  - A **stage-rules module** holds the stage list and a pure decision function: given the current stage, the target stage, whether the job is open, the stage before the current Hired or Rejected outcome, and whether the application was ever reopened from Withdrawn, it returns allowed or blocked plus a human-readable reason. It doesn't access the database.
  - A small **services module** performs every data-changing hiring operation: create application, move or reopen, close job, reopen job. Each operation derives the needed facts from stage history, asks the stage-rules module, and writes the change plus its history entry in one database transaction. Every submitted move is re-checked. A blocked move changes nothing and writes no history.
  - **Facts derived from stage history:** the stage before the current Hired or Rejected outcome is the old stage on the history entry that moved the application into that outcome. "Ever reopened from Withdrawn" means some history entry goes from Withdrawn to Applied, which is unambiguous because no direct moves out of a final outcome exist. No duplicate fields store these facts on the application. How the current stage is stored is left to implementation planning.
  - **Forms and model validation:** trimming and normalization, and no future applied-on date.
  - **Views** stay straightforward: they read the request, call a service or query, and return a full page or an HTMX partial.
- **Deletion protection beyond database constraints** is enforced in both the model's single-object delete *and* a custom QuerySet delete, so Django admin's single and bulk delete paths follow the same rules:
  - An **application** can be deleted only if its history contains just the initial Applied entry. Editing notes or the applied-on date doesn't affect this. Once any stage move has happened, deletion is blocked permanently, even if the application later returns to Applied. The supported delete path removes the single initial history entry and then the application, in one transaction.
  - A **skill** can't be deleted while any open or closed job uses it. This is an app-level rule, because the plain many-to-many link table would otherwise cascade.
  - **Candidates and jobs** with applications can't be deleted, through the app or admin, with no admin exception.
- **Stage history protection:** staff can't add, edit or delete history entries on their own, in the app or in admin. History entries are only created by service operations. The single exception is deleting an eligible never-moved application, which removes its initial history entry as part of that supported delete. This protection is enforced through supported app, admin and ORM delete paths. It isn't a claim that no code path could ever delete history.
- **Django admin:** application stage and stage history are read-only. History has no add, edit or delete actions there. Any stage change goes through the same service operations. Deleting an eligible application in admin follows the same never-moved rule and removes its initial history entry.

### Record lifecycle
- **Candidates:** deletable after a confirmation page only when they have no applications. No archiving.
- **Jobs:** deletable after a confirmation page only when they have no applications. Closing is the normal way to retire an opening.
- **Closed jobs:** editable (details and skills) without reopening. Editing never changes status or `closed_at`, and never changes applications or their history.
- **Skills:** renameable everywhere, including closed openings. Deletable after confirmation only when unused.
- **Applications:** deletable after confirmation only when they've never moved. Candidate and job can't be changed. A mistaken application is deleted (if eligible) and recreated correctly.

### Navigation and pages
- After login, staff land on the pipeline workspace.
- A top navigation bar on every page: Pipeline, Candidates, Jobs, Skills, the username, and Log out. It collapses into a menu on narrow screens.
- **Candidates, Jobs and Skills** use regular Django pages and forms: list, detail where relevant, create, edit, and delete confirmation.
  - **Candidates list:** GET search by name or email, sorted by last name then first name. Columns: name, email, source, number of applications.
  - **Jobs list:** GET title search and Open, Closed or All filter (default Open), sorted alphabetically by title. Columns: title, department, location, type, status, closed date, number of active applications.
  - Both lists show 25 per page and keep search and filter values when changing pages. Searches submit with a button or Enter, with no live search.
  - **Skills:** an alphabetical list with create, rename and protected delete.
  - **Candidate detail** lists the candidate's applications, each linking to that application selected in the workspace, and has an "Add application" action.
- **Recording applications:** from the workspace's selected job (the picker lists only candidates without an application for that job) or from a candidate's detail page (the picker lists only open jobs the candidate hasn't applied to). Both use shared form logic and the same service, with server-side validation and the database constraint as backstops. After saving, the workspace opens with the new application selected. A new candidate is created first, then the application is added from their detail page. There's no inline candidate creation.
- **Closing and reopening jobs:** available in the workspace header and on the job detail page, through the same views and services, submitted with POST.
  - Close goes to a separate confirmation page showing how many applications are active. It explains that their stages stay unchanged, that only Reject and Withdraw remain available, and that new applications will be blocked.
  - Reopen has no confirmation.
  - Both return to the page staff came from, keeping the selected application and filters when that's the workspace. The return address is validated so it can only redirect within this site, with a safe default otherwise.

### Pipeline workspace
The workspace follows the direction chosen in the UI prototype: Variant C, list-and-detail, with a dark theme.
- **Layout:** jobs sidebar (open and closed jobs, with in-progress counts), the selected job's application list, and a detail panel. The jobs sidebar appears only in the workspace.
- **Application list:**
  - Active (default), Finished and All tabs, each with a count.
  - Groups by stage in pipeline order, with the most recent stage change first within each group.
  - A name or email search.
  - The tab and search are kept in the URL.
  - Tab counts reflect the selected job and search, before the tab is applied.
- **Detail panel:**
  - Candidate summary, job, applied-on date, current stage, and a **stage progress indicator**.
  - Alerts for a closed job and for a no-skip (reopened-from-Withdrawn) application.
  - Primary actions: advance to the next stage, reopen (to the allowed target), **Reject…** and **Mark withdrawn…**.
  - Buttons for other allowed moves. These don't include Rejected or Withdrawn, which are only reachable through the confirm flow.
  - A collapsed section explaining each blocked move, using the stage-rules module's reasons.
  - An application details form for editing the **applied-on date** and **notes**. Candidate and job are shown but not editable. A future applied-on date is rejected with an inline error.
  - The stage history timeline, including reasons.
- **Reject and withdraw:** always open an inline confirmation box with an optional reason. Confirmation is required even when the reason is blank, and no other control bypasses it.
- **HTMX and URL behavior:**
  - **Selecting an application** swaps the detail panel (and selection highlight) through HTMX and pushes the application's URL, including tab and search, to browser history.
  - **Every workspace URL** also renders the full page on a normal request.
  - **Stage actions** update the detail panel, the application list and affected counts together without a full reload. **Saving the applied-on date and notes** uses HTMX.
  - **Switching jobs** in the sidebar is a normal full-page link.
  - Views return a partial for HTMX requests and the full page otherwise, including HTMX history-restore requests, which must receive the full page.
- **Filter mismatch:** if a stage move leaves the selected application outside the current tab or search, its updated details stay visible with a note that it no longer matches the list. The tab and search don't change automatically.
- **Stale moves:** if a submitted move is no longer allowed, the panel shows a clear error and refreshed actions. The stage doesn't change and no history entry is written.
- **Empty state:** with no open jobs, the workspace shows a clear message and a link to create a job. Closed jobs remain accessible.
- **Theme:** dark gray backgrounds, readable text, and clear contrast for buttons, stage labels and blocked actions, across panels, forms, dropdowns, notes and history.
- **Responsive:** three columns side by side on wide screens, stacked on narrow screens. Selecting an application on a narrow screen brings the detail panel into view. Forms, buttons and long text must not cause horizontal page scrolling. This is a design choice for usability, not an assignment requirement.

### Dates and time
- Timezone support is enabled: timestamps are stored in UTC and displayed in `America/Chicago`.
- The applied-on default and the no-future-date validation both use Django's local date (`timezone.localdate()`).

### Demo data
- A management command (`seed_demo`) creates fictional skills, candidates, open and closed jobs, non-admin demo employee accounts, and applications covering the important stage and reopening scenarios:
  - a no-skip application reopened from Withdrawn,
  - reopenable Hired and Rejected applications,
  - a closed job with in-progress applications,
  - candidates with several applications.
- Applications and history are created **through the real services**.
- It **refuses to run if any hiring data exists**. There's no reset option.
- Demo accounts use a known **development-only** password printed in the terminal.
- How to run it gets documented once it's implemented and verified.

## Acceptance Criteria

### Stage rules and Withdrawn reopening
- Each of the 15 approved stage rules has automated tests, using parametrized cases for the stage-rules module where they fit.
- Reopening a Withdrawn application moves it to Applied from any prior stage, reusing the same application record.
- After a Withdrawn reopen:
  - Applied → Interview is blocked.
  - Applied → Screening is allowed.
  - Offer → Hired is allowed.
  - Backward moves are allowed.
  - Rejected or Withdrawn from any active stage are allowed.
- A restricted application that's Rejected and reopened to its previous stage still can't skip forward.
- A restricted application that's Hired and reopened to Offer is still restricted.
- A restricted application that withdraws and reopens again returns to Applied and is still restricted.
- An application never reopened from Withdrawn reopens from Hired or Rejected only to its previous stage and may skip forward afterward.
- Tests cover repeated reopen and withdraw sequences and confirm the history-derived facts are correct after each step.
- Direct final-to-final moves are blocked.
- Reopening a finished application on a closed job is blocked.
- On a closed job, only active → Rejected or Withdrawn succeeds, and → Hired is blocked. A new application is blocked.
- Reopening a job clears `closed_at`, re-enables active applications, and leaves finished ones unchanged.
- A duplicate application is blocked even when the existing one is Rejected or Withdrawn.
- Every successful move writes exactly one history entry in the same transaction. A blocked move changes nothing and writes no history.

### Deletion protection
- A candidate or job with applications can't be deleted through app views, admin single delete, admin bulk delete, or QuerySet delete.
- An application that has ever moved can't be deleted through any of those paths, even after returning to Applied. A never-moved application can be deleted, along with its initial history entry.
- A used skill can't be deleted through any of those paths. An unused skill can.
- Staff can't add, edit or delete stage history entries on their own in the app or admin. Deleting an eligible never-moved application removes its initial history entry in the same transaction. Deleting a moved application is refused, and its history stays intact.

### Access and editing
- An anonymous visitor or an inactive account is redirected to login, or refused, on every hiring page.
- A regular employee account (not staff or superuser) can use every hiring page but can't access Django admin.
- Editing a candidate applies the same trimming, normalization and case-insensitive unique-email rule as creation. Changing to another candidate's email in different capitalization or with extra spaces is rejected, and saving with the candidate's own email is accepted.
- An application's candidate and job can't be changed after creation. Only the applied-on date and notes are editable.

### HTMX updates
- Selecting an application in the workspace updates the detail panel and selection highlight without a full page reload.
- A stage action updates the detail panel, application list and affected counts in one response, without a full reload.
- Saving the applied-on date and notes updates the panel without a full reload. A future applied-on date is rejected with an inline error and isn't saved.
- A stage move rejected by the service shows an error in the panel with refreshed actions, and the stage and history are unchanged.

### Direct application links and refresh
- Opening an application's workspace URL directly (bookmark, typed URL, or link from a candidate page) renders the full workspace with that job, application, tab and search selected.
- Refreshing the browser on any workspace URL renders the same job, selection, tab and search.
- A view called with an HTMX request returns the partial. Called without one, or with an HTMX history-restore request, it returns the full page.

### Back and Forward
- After selecting several applications in turn, Back and Forward restore the matching application in the detail panel and the matching highlight in the list.
- The URL updates on each selection to include the application, tab and search.

### Filters
- The tab and search are reflected in the URL and survive refresh and Back and Forward.
- Tab counts reflect the selected job and current search, independent of which tab is active.
- Within each stage group, applications are ordered by most recent stage change first. Groups appear in pipeline order.

### Selected application no longer matching the list
- If a move makes the selected application fall outside the current tab or search, its updated details remain visible in the panel with a message saying it no longer matches the list.
- The active tab and search text don't change automatically.

### Manual browser check list
These are verified by hand in a real browser unless browser tests are added later:
- Back and Forward across several selections, including after a stage move.
- Restoring history after the HTMX history cache is cleared or missed.
- The narrow-screen layout: stacked columns, the detail panel brought into view, and no horizontal page scroll.
- Dark theme contrast for buttons, stage labels, blocked actions, dropdowns and alerts.

## Out of Scope

- Candidate logins, a candidate portal, or public job postings and application forms.
- Public sign-up, roles, permission levels, or per-job access restrictions.
- A custom user model or accounts app.
- Resume or file uploads, work history, education, or candidate skills.
- A managed Source model, or a per-application source.
- Required vs. preferred skills, or creating skills inline on the job form.
- Additional job statuses (Draft, On Hold, Filled, Cancelled), or a history of job closures.
- Archiving candidates.
- A full audit log of candidate or job edits.
- A comments thread on applications.
- Reasons for stage moves other than Rejected or Withdrawn, and required reasons.
- Changing an application's candidate or job after creation.
- Inline candidate creation while recording an application.
- The per-job board view with stage columns and drag-and-drop, and the cross-job application table view.
- A separate summary dashboard.
- Live-as-you-type search on the Candidates and Jobs pages, and extra filters (by source, department or employment type).
- Per-employee time zones.
- A reset option for the demo seed command.
- Any admin exception to the deletion protections.

## Further Notes

### What the prototypes tested vs. what still needs verification

**Tested hands-on in the logic prototype** (`prototypes/stage-rules.html`, all eight scenarios):
- Skipping forward, backward moves to any earlier stage, and reject or withdraw from any active stage.
- Reopening Hired or Rejected to the previous stage.
- Closing a job, leaving applications unchanged except for Reject or Withdraw.
- Blocking new applications on a closed job, and reopening a job.
- Blocking duplicates, including for rejected applications, and applying to a different job.

**Implemented in the UI prototype but not formally verified** (`prototypes/pipeline-ui.html`):
- Withdrawn → Applied reopening and the permanent no-skip restriction, demonstrated with sample applications.
- Reopen requiring an open job, and no direct final-to-final moves.
- History-derived rule facts.

The logic prototype didn't model the Withdrawn exception. The UI prototype implemented it for demonstration only. **The Withdrawn reopening rules (rules 7–9) therefore still need verification** through the acceptance tests above.

**Chosen through the UI prototype:**
- The list-and-detail workspace, the stage progress indicator, and actions, notes and history beside the list.
- The dark theme.
- Inline Reject and Withdraw confirmation with an optional reason.

**Not prototyped; verify during implementation:**
- The real HTMX and URL behavior: full vs. partial responses, push-url, history restore and Back/Forward. The prototype used client-side JavaScript only.
- All deletion protections, including admin bulk delete and QuerySet delete.
- Admin read-only behavior, the responsive layout in Django templates, and the seed command.

### Deferred to implementation planning (not yet settled)
- Whether service operations accept an optional timestamp so seeded history can carry realistic past dates. Without one, seeded history uses the time the command ran.
- How the application's current stage is stored, consistent with history being the source for rule facts.
- Exact `pyproject.toml` configuration for Ruff, pytest and pytest-django.
- django-tailwind-cli and DaisyUI setup details, including which dark theme to configure.
- Whether automated browser tests are added for Back and Forward and responsive checks. Until then they're on the manual check list.

### Explaining the design
- **Protection principle:** nothing that carries hiring history can be deleted. Jobs close, candidates stay, moved applications stay, and used skills stay.
- **Rule placement:** the database guarantees what must never break, the stage-rules module decides which moves are legal, services perform changes and write history together, and views just connect pages to them.
- **HTMX:** used where the requirement asks for it, moving and inspecting applications without a full reload. Everything else is standard Django pages.
