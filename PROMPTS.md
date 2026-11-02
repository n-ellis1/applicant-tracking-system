# PROMPTS.md — AI Usage Log

This file is the record of AI use on this codebase. At the end of every
agent session, direct the agent to write the session log with this prompt:

> Append a session log to PROMPTS.md at the repo root, under today's date,
> newest entry at the top. Record every prompt I gave you this session, in
> order, including any corrections. End the entry with a short summary:
> the outcome, any places where I deviated from a recommended answer or
> asked follow-up questions, and anything that went sideways.

Two rules:

- Entries are added only by that prompt, never unprompted.
- New entries go at the top. Never rewrite or delete an old entry — the
  log is part of your work, and an honest log of a session that went
  sideways is worth more than a tidy one.

Each entry has this shape:

    ## YYYY-MM-DD — <one-line summary>

    ### Prompts
    1. ...

    ### Summary
    - **Outcome:** what was built and what was kept
    - **Deviations:** recommendations overridden, follow-up questions asked
    - **Sideways:** failures, wrong turns, and how they were caught

## 2026-11-01 — Phase 6: Recording an application from the candidate page

### Prompts

1. **Start Phase 6 (`/implement`).**
   > /implement @prd/applicant-tracking-system.md @plans/applicant-tracking-system.md implement Phase 6 only
   >
   > Read CLAUDE.md and follow the implement and tdd skills. Propose the TDD candidates, explain each in beginner-friendly language, and wait for my approval before writing code.
   >
   > After automated checks pass, give me browser verification steps and wait for my confirmation. Don't mark the phase complete, commit, push, or start Phase 7 yet.

2. **Approve all three candidates and add rollback and constraint tests.**
   > I approve all three candidates.
   >
   > Also include ordinary tests proving:
   > - If writing the initial history entry fails, the application creation rolls back too.
   > - The database rejects a duplicate candidate/job pair when the form is bypassed.
   >
   > Start with candidate 1. Show me the test and RED result, then stop for approval before implementing the behavior. Keep scaffolding limited, and report honestly if any behavior already passes.

3. **Approve test 1, with a migration condition.**
   > I approve this test. Implement application creation and its initial history entry in one transaction. Show me the GREEN result and regression results, then stop before candidate 2.
   >
   > Only regenerate migration 0005 if it hasn't been applied to the local database or shared. If it has, add a new migration for the constraint instead.

4. **Confirm cycle 1 and start test 2.**
   > Yes, I agree. Proceed to candidate 2: a duplicate application should show a friendly form error even when the existing application is Rejected.
   >
   > Show me the test and RED result, then stop for approval before implementing duplicate protection. Keep the separate database-constraint and rollback tests on the checklist.

5. **Approve test 2, with picker and error-handling requirements.**
   > I approve this test and the friendly error wording. Implement the service check, database unique constraint, and form error handling.
   >
   > Keep the displayed picker limited to eligible jobs, with server-side validation for every submission. Catch only the duplicate-constraint failure as a duplicate error; don't turn unrelated database errors into that message.
   >
   > Show me the GREEN result and full regression results, then stop before candidate 3.

6. **Add the race and unrelated-error tests, then start test 3.**
   > Yes, this implements the duplicate behavior. Add both proposed ordinary tests: the missed pre-check still produces the friendly duplicate error, and an unrelated IntegrityError propagates unchanged. Keep the rollback and direct database-constraint tests too.
   >
   > Describe the patched test as exercising the race-recovery path, not proving real concurrent requests work.
   >
   > Proceed to candidate 3. Show me the closed-job test and RED result, then stop for approval before implementing that check.

7. **Approve test 3 and keep a forged-POST page test.**
   > I approve this test and its wording. Add the closed-job check in create_application so it refuses before writing anything.
   >
   > Show me the GREEN result and full regression results, then stop before building the remaining Phase 6 work. Keep an ordinary forged-POST test to verify the refusal also appears correctly on the page.

8. **Continue with the rest of Phase 6, reading job status fresh.**
   > Yes, continue with the remaining Phase 6 work and ordinary tests as listed.
   >
   > Have create_application refresh the job's status from the database before checking it, so it doesn't rely on a potentially stale object supplied by another caller. Add a regression test for that case. This doesn't need to claim full concurrency protection.
   >
   > Run all planned checks, then give me browser verification steps. Wait for my confirmation before marking Phase 6 complete, committing, pushing, or starting Phase 7.

9. **Browser checks passed; mark complete and propose CLAUDE.md.**
   > All Phase 6 browser checks passed, including recording applications, picker exclusions, applying to a second job, future-date rejection, candidate and job deletion protection, deleting an unused candidate, and the narrow-window layout.
   >
   > Mark Phase 6 complete. Show me any proposed CLAUDE.md updates, limited to concise, durable conventions established and verified in this phase. If nothing needs adding, say so.
   >
   > Migration 0005 is now applied locally, so future model changes must use new migrations.
   >
   > Don't commit or start Phase 7 yet.

10. **Correction: approve CLAUDE.md with my wording, and write this log.**
    > Approve the updates with these adjustments:
    >
    > - Services layout line: "hiring/services.py: application creation and job close/reopen operations. Views use these shared operations."
    > - Service errors: "Service operations report expected business-rule refusals with ValidationError. Views display the message in the relevant form or panel."
    > - Current-state checks: "Validate service operations against current database state. Translate only identified constraint failures into friendly errors; let unrelated database errors propagate."
    > - Picker guidance: "Where a service checks eligibility, EligibleChoiceField displays eligible records while allowing existing submitted records to reach that validation. Never rely on picker filtering alone."
    > - Keep the stages.py and migration guidance.
    >
    > Apply these concise updates, then report CLAUDE.md's line count. Keep it within our final target of about 70-80 lines by trimming duplication if needed.
    >
    > Write this session log to PROMPTS.md according to its instructions, including the three RED-to-GREEN tests, rollback and constraint checks, stale-job check, and browser verification.
    >
    > Show me the changed-file summary and proposed commit message before committing. Don't start Phase 7.

### Summary

- **Outcome:**
  - **Models:** `Application` (candidate and job FKs with `PROTECT`, `applied_on` defaulting to `timezone.localdate` with a shared `validate_not_future` validator, notes, `stage`, timestamps) and `StageHistoryEntry` (application FK with `PROTECT`, blank-able `old_stage`, `new_stage`, `changed_at`, `changed_by` FK to `User` with `PROTECT`, optional reason). A `UniqueConstraint(fields=["candidate", "job"], name="unique_application_candidate_job")`. Migration `0005_application_stagehistoryentry`.
  - **Stages:** new `hiring/stages.py` with the eight stages and the active and final groups, in pipeline order.
  - **Service:** `create_application(*, candidate, job, applied_on, changed_by)` in `hiring/services.py`:
    - reads the job's status from the database and refuses a closed job with "This job is closed and can't accept new applications."
    - refuses any existing application for the pair, whatever its stage, with "This candidate has already applied to this job."
    - writes the application at Applied and its initial history entry inside one `transaction.atomic()` block
    - turns an `IntegrityError` into the duplicate error only if the pair now exists, and re-raises any other database error unchanged
    - raises `ValidationError` for refusals, before writing anything
  - **Form:** `CandidateApplicationForm(candidate=...)` with a job picker and an applied-on date. The picker uses a new `EligibleChoiceField`: it lists only open jobs the candidate hasn't applied to, but accepts any existing job so a stale or forged choice reaches the service and gets its friendly reason.
  - **Pages:**
    - `/candidates/<pk>/applications/new/` records an application. The view attaches service refusals to the job field. If no eligible jobs are left, the page says so.
    - `/pipeline/applications/<pk>/` is a basic GET-only page with the candidate, job, applied-on date, stage and stage history (Central time and username). Phase 7 replaces it with the workspace.
    - Candidate detail gained "Add application" and a list of the candidate's applications linking to their pages.
    - The candidate and job delete pages now say why a record with applications can't be deleted, list those applications, and offer no Delete button. A POST shows the same explanation.
  - **TDD test 1** (a new application starts at Applied with one initial history entry): RED with `assert 0 == 1` after scaffolding the stage list, the models and migration, and an empty `create_application` that returned `None`. `Application.stage` was given no default, so the scaffolding didn't contain the behavior. Creating both records in one atomic block made it GREEN. The agent noted this test alone didn't prove the transaction.
  - **TDD test 2** (a duplicate shows a friendly form error even when the existing application is Rejected): the test sets Rejected directly until Phase 8 and sends a forged POST. RED with `assert 2 == 1` after scaffolding the form, add view, URL and basic application page, because the duplicate was saved. The service pre-check, the unique constraint and view error handling made it GREEN. The agent noted this test exercised only the pre-check.
  - **TDD test 3** (a closed job is refused by the service and writes nothing): RED with `Failed: DID NOT RAISE ValidationError`. That's pytest's `raises` expectation failing, not missing scaffolding. A closed-job check before any write made it GREEN.
  - **All three were genuine RED-to-GREEN cycles.**
  - **Rollback and constraint tests (ordinary, passed on first run):**
    - the database rejects a duplicate candidate/job pair created directly through the ORM
    - a forced `DatabaseError` on the history write leaves no application behind
    - **race-recovery path:** with the pre-check patched to miss an existing application, the unique constraint fires and the service still returns the friendly duplicate error, re-checking once and writing nothing. This exercises the recovery code; it doesn't prove real concurrent requests work.
    - an unrelated `IntegrityError` from the history write is re-raised as the same exception object, and nothing is saved
  - **Stale-job regression test:** the job is closed in the database behind a job object that still says Open, and the service refuses it. It's a regression test for a stale object, not a concurrency guarantee.
  - **Other ordinary tests:** 14 more test functions (16 cases), covering the forged closed-job POST showing the error under the job field, picker exclusions, the applied-on default, future dates rejected by the form and by model validation, saving and landing on the application page, applying to two jobs, candidate detail links, a submitted `candidate` value being ignored, the application page having no edit fields and refusing POST with 405, and candidate and job deletion protection through `delete()`, QuerySet delete and both delete pages on GET and POST.
  - **Automated checks:** 169 tests passed. `ruff check`, `ruff format --check` and `makemigrations --check` were clean.
  - **Browser checks (by me):** all passed. They covered recording applications, picker exclusions, applying to a second job, future-date rejection, candidate and job deletion protection, deleting an unused candidate, and the narrow-window layout.
  - **Docs:** Phase 6's acceptance criteria are ticked in the plan. CLAUDE.md's Project layout gained the `stages.py` line and my `services.py` wording. Conventions gained service refusals through `ValidationError`, checking current database state with only identified constraint failures translated, `EligibleChoiceField`, and the migration rule.
- **Deviations:**
  - **Extra ordinary tests:** I added the rollback and direct database-constraint tests up front, then accepted the agent's proposed race-recovery and unrelated-`IntegrityError` tests, and required the patched test to be described as exercising the recovery path rather than real concurrency.
  - **Duplicate handling:** I required only the duplicate-constraint failure to become the duplicate message, with unrelated database errors propagating.
  - **Picker:** I required the displayed picker to stay limited to eligible jobs, with server-side validation on every submission.
  - **Stale job:** the agent pointed out that the closed-job check trusted the job object passed in. I required the service to read the status from the database, with a regression test that doesn't claim full concurrency protection.
  - **Migration 0005:** I allowed regenerating it only while it was unapplied and unshared. The agent checked `showmigrations` and `git status` before each regeneration. Now that it's applied locally, later model changes need new migrations.
  - **CLAUDE.md wording:** I replaced the agent's services line and three convention lines with my own wording.
- **Sideways:**
  - **Stub choice:** a `NotImplementedError` stub would have made test 1 error instead of failing on an assertion, so the agent used a stub that returned `None` and said so.
  - **Ordinary tests not run RED:** the rollback, constraint, race-recovery and unrelated-error tests covered code that already existed, so they passed on their first run. The agent reasoned that they would fail without the code they guard, but didn't break the code to show it.
  - **Failing test assertions:** in the final batch, a "no `<form>` on the page" check failed because the nav's Log out form is on every page. The delete-page checks also looked for `Can&#x27;t`, but static template text isn't HTML-escaped. That was the same mistake as in Phase 3. Both were mechanical repairs: the tests now look for the specific form fields and Delete button, and for a plain `Can't`.
  - **Ambiguous edit:** adding the fresh status read first failed because the target line matched twice. It was redone with more context.
  - **Formatter and linter:** `ruff format` reformatted two files, and `ruff check` flagged a blank line after the imports in `services.py`. `ruff check --fix` fixed it.
  - **Line endings:** git warned that LF will be replaced by CRLF in several files. It's informational, and nothing was changed for it.
  - **Skill lookup:** `/implement` isn't one of the session's registered skills, so the agent read `.claude/skills/implement/SKILL.md` directly.

## 2026-11-01 — Phase 5: Candidates

### Prompts

1. **Start Phase 5 (`/implement`).**
   > /implement @prd/applicant-tracking-system.md @plans/applicant-tracking-system.md implement Phase 5 only
   >
   > Read CLAUDE.md and follow the implement and tdd skills. Propose the TDD candidates, explain each in beginner-friendly language, and wait for my approval before writing code.
   >
   > After automated checks pass, give me browser verification steps and wait for my confirmation. Don't mark the phase complete, commit, push, or start Phase 6 yet.

2. **Approve both candidates, splitting the search tests.**
   > I approve both candidates. For candidate 2, use separate tests for matching first name, last name, and email, and for last-name/first-name ordering, so failures are clear.
   >
   > Start with the email normalization test. Show me the test and RED result, then stop for approval before implementing the change.
   >
   > Keep all the ordinary tests you listed, including duplicate checks on create and edit, self-email edits, and the database constraint.

3. **Approve test 1 (email normalization).**
   > I approve this test. Add email lowercasing in CandidateForm.clean_email, then show me the GREEN result and full regression results. Stop before starting the search tests.

4. **Confirm cycle 1 and start the first-name search test.**
   > Yes, this implements the intended create-form behavior. Proceed with the first search test, showing the test and RED result before implementing its query logic. Keep edit and admin normalization covered by the ordinary tests later in this phase.

5. **Approve test 2 (first-name search).**
   > I approve this test. Add the first-name search behavior, then show me the GREEN result and regression results. Stop before starting the last-name search test.

6. **Start test 3 (last-name search).**
   > Yes, proceed with the last-name search test. Use data where the search text doesn't also match the first name or email. Show me the test and RED result, then stop for approval before changing the query.

7. **Approve test 3.**
   > I approve this test. Extend the query to match first name OR last name using Q objects. Show me the GREEN result and regression results, then stop before the email search test.

8. **Start test 4 (email search).**
   > Yes, proceed with the email search test. Use search text found only in the email, not either name. Show me the test and RED result, then stop for approval before changing the query.

9. **Approve test 4.**
   > I approve this test. Add email__icontains as the third OR condition. Show me the GREEN result and regression results, then stop before the ordering test.

10. **Ordering: keep the working code, write a regression test.**
    > Go with option 2. Keep the existing ordering and write the test as a regression test. Check last-name ordering and first-name ordering when two candidates share a last name. Show me the result.
    >
    > Record honestly that ordering was added during scaffolding, so this wasn't a RED-to-GREEN cycle. Don't remove working behavior to manufacture a failure.

11. **Continue with the rest of Phase 5, with logging instructions.**
    > Yes, continue with the remaining Phase 5 work and ordinary tests as listed.
    >
    > For the session log, record four RED-to-GREEN tests: email normalization, first-name search, last-name search, and email search. Record ordering separately as a regression test that passed immediately.
    >
    > Run all planned checks, then give me browser verification steps. Wait for my confirmation before marking Phase 5 complete, committing, pushing, or starting Phase 6.

12. **Browser checks passed; mark complete and propose CLAUDE.md.**
    > Phase 5 manual verification passed: email normalization, duplicate checks on create and edit, keeping a candidate's own email, optional fields and sources, search and ordering, pagination preserving search, delete confirmation and cancel, admin duplicate validation, and dark narrow-screen layouts.
    >
    > Mark Phase 5 complete. Show me any proposed CLAUDE.md updates, limited to concise, durable conventions established and verified in this phase. If nothing needs adding, say so.
    >
    > Don't commit or start Phase 6 yet.

13. **Leave CLAUDE.md unchanged and write this log.**
    > Agreed, leave CLAUDE.md unchanged.
    >
    > Write this session log to PROMPTS.md according to its instructions. Record the four RED-to-GREEN tests, the ordering regression test that passed immediately, and the completed browser checks.
    >
    > Then show me the changed-file summary and proposed Phase 5 commit message before committing. Don't start Phase 6.

### Summary

- **Outcome:**
  - **Model:** `Candidate` with first and last name, email, optional phone, location, profile URL and notes, a source (Company Website, Job Board, Referral, Other) with optional source details, and timestamps. Ordered by `Lower("last_name")`, `Lower("first_name")`. A `UniqueConstraint(Lower("email"), name="unique_candidate_email_ci")` backs up the form. Migration `0004_candidate`.
  - **Form:** `CandidateForm` in `hiring/forms.py`. Django's email field trims the spaces, and `clean_email` lowercases the email, then rejects a match against other candidates (skipping the one being edited) with "A candidate with this email already exists." There's no model `save()` override.
  - **Pages:**
    - The Candidates placeholder became a real list: GET search, 25 per page, page links that keep the cleaned `q`, and columns for name, email, source and applications (0 until Phase 7).
    - Create and edit share `candidate_form.html`.
    - The detail page shows every field, the source with its details, and Central-time created and last-updated times, with a "No applications yet" section ready for Phase 6.
    - `/candidates/<pk>/delete/` shows a confirmation on GET and deletes on POST. Application protection comes in Phase 6, as planned.
  - **Admin:** `Candidate` is registered with `CandidateAdminForm`, a subclass of `CandidateForm` with `widgets = {}`, so admin trims, lowercases and checks duplicates like the app.
  - **TDD test 1** (creating a candidate stores the email trimmed and lowercased): RED with `assert ['Jane.Doe@Example.com'] == ['jane.doe@example.com']` after scaffolding the model, form, create view and a stub detail page. The spaces were already trimmed by Django's form field. Lowercasing in `clean_email` made it GREEN.
  - **TDD test 2** (search matches first name, ignoring case): RED with `assert ['Jane Doe', 'Sam Rivera'] == ['Jane Doe']` after scaffolding an unfiltered list view. Emails were initials only, so only the first name could match. A `first_name__icontains` filter made it GREEN.
  - **TDD test 3** (search matches last name): `" RIV "` appears in no first name or email. RED with `assert [] == ['Sam Rivera']`. Changing the filter to `Q(first_name__icontains=q) | Q(last_name__icontains=q)` made it GREEN.
  - **TDD test 4** (search matches email): `" ACME "` appears only in `jd@acme.test`. RED with `assert [] == ['Jane Doe']`. Adding `| Q(email__icontains=q)` made it GREEN.
  - **Four genuine RED-to-GREEN cycles** across the two approved candidates. Candidate 2 was split into separate tests, as I asked.
  - **Ordering regression test** (last name, then first name, with two candidates sharing a last name and a lowercase last name sorting correctly): **passed on its first run. It was not a RED-to-GREEN cycle**, because `Meta.ordering` was added with the model during scaffolding for test 1. A comment above the test says so.
  - **Ordinary tests:** 27 more test functions (39 cases), covering:
    - every field saving, the required fields, optional fields left blank, the four source choices, an unknown source being rejected, and an invalid email or profile URL
    - duplicate email on create with case and spacing variations, and the database constraint when the form is skipped
    - editing to another candidate's email being rejected, keeping your own email in any case, a changed email being lowercased, the prefilled edit form, and the source staying unchanged
    - list columns and links, 25 per page, the next-page link with and without a search, and "No candidates match."
    - the detail page, the delete confirmation not deleting on GET, deleting on POST, 404s, and the signed-out redirect on every candidate page
    - admin add and change: trimming and lowercasing, duplicates rejected, and a candidate's own email in different case allowed
  - **Automated checks:** 145 tests passed. `ruff check`, `ruff format --check` and `makemigrations --check` were clean.
  - **Browser checks (by me):** all passed. They covered email normalization, duplicate checks on create and edit, keeping a candidate's own email, optional fields and sources, search and ordering, pagination keeping the search, delete confirmation and cancel, admin duplicate validation, and the dark narrow-screen layouts.
  - **Docs:** Phase 5's acceptance criteria are ticked in the plan. CLAUDE.md is unchanged, because the phase's patterns were already covered by existing conventions.
- **Deviations:**
  - **Search split:** I required separate tests for first name, last name and email matching, plus a separate ordering test, so failures would be clear.
  - **Test data:** I required each search test's text to match only the field it tests.
  - **Ordering:** the agent recommended temporarily removing `Meta.ordering` so the ordering test could go RED first. I chose to keep the working code and record the test as a regression test instead.
  - **Ordinary coverage:** I explicitly kept the duplicate checks on create and edit, self-email edits, the database constraint, and edit and admin normalization as ordinary tests.
- **Sideways:**
  - **Built ahead of TDD:** the agent added `Meta.ordering` while scaffolding for test 1, copying the Skill and JobOpening models, so the approved ordering test couldn't fail first. The agent flagged this before writing the test rather than after. It also saved a memory note to keep scaffolding free of behavior that an approved test is meant to check.
  - **Duplicate check not run RED:** the duplicate-email check was added together with its tests, as ordinary work following the Skills pattern, so those tests weren't seen failing first.
  - **Admin test cleanup:** the first draft of the "admin change rejects another candidate's email" test made an unneeded extra save first. The agent simplified it before running anything.
  - **Formatter:** `ruff format` rewrapped long lines in `test_candidates.py` once, with no change to what the tests assert.
  - **Skill lookup:** `/implement` isn't one of the session's registered skills, so the agent read `.claude/skills/implement/SKILL.md` directly.

## 2026-11-01 — Phase 4: Closing and reopening jobs

### Prompts

1. **Start Phase 4 (`/implement`).**
   > /implement @prd/applicant-tracking-system.md @plans/applicant-tracking-system.md implement Phase 4 only
   >
   > Read CLAUDE.md and follow the implement and tdd skills. Propose the TDD candidates, explain them in beginner-friendly language, and wait for my approval before writing code.
   >
   > After automated checks pass, give me browser verification steps and wait for my confirmation. Don't mark the phase complete, commit, push, or start Phase 5 yet.

2. **Approve all three candidates and add a GET-reopen test.**
   > I approve all three candidates. Also include an ordinary test confirming that a GET request cannot reopen a job, since reopening must use POST too.
   >
   > Start with candidate 1. Show me the test and its RED result, then stop for approval before implementing the behavior. If anything already passes, report that honestly rather than manufacturing a failure.

3. **Approve test 1 (closing needs the confirmation page and a POST).**
   > I approve this test. Implement close_job in services.py and call it from the POST path, keeping GET read-only. Show me the GREEN result and regression results, then stop before candidate 2.

4. **Close-again no-op, then start test 2.**
   > Yes, the closing behavior looks correct. Make closing an already-closed job a no-op that preserves closed_at and updated_at, and cover that with an ordinary test.
   >
   > Proceed to candidate 2 for reopening. Show me its test and RED result, then stop for approval before implementing it.

5. **Approve test 2 (reopening), with a reopen-again no-op.**
   > I approve candidate 2's test. Implement reopen_job in services.py and call it from the POST-only view.
   >
   > Also make reopening an already-open job preserve updated_at, covered by an ordinary test. Show me the GREEN result and regression results, then stop before candidate 3.

6. **Start test 3 (`next` return address).**
   > Yes, proceed to candidate 3 for the next return address. Show me the test and RED result, then stop for approval before implementing the redirect handling.

7. **Approve test 3.**
   > I approve candidate 3's test. Use Django's url_has_allowed_host_and_scheme with the current request host to validate next, falling back to job detail.
   >
   > Show me the GREEN result and full regression results, then stop before continuing with the remaining Phase 4 work.

8. **Continue with the rest of Phase 4.**
   > Yes, continue with the remaining Phase 4 work as listed. Validate the Cancel return address too, and test that next survives the confirmation-page GET through the form POST.
   >
   > Run all planned checks, then give me the browser verification steps. Wait for my confirmation before marking Phase 4 complete, committing, pushing, or starting Phase 5.

9. **Browser checks passed; mark complete and propose CLAUDE.md.**
   > Phase 4 manual verification passed: closing requires confirmation and POST, closed-list behavior, editing while closed preserves the closed date, reopening clears it, external next addresses are rejected, local next is preserved, GET cannot reopen, and the dark narrow-screen layout works.
   >
   > Mark Phase 4 complete. Show me any proposed CLAUDE.md updates, limited to concise, durable conventions established and verified in this phase. If nothing needs adding, say so.
   >
   > Don't commit or start Phase 5 yet.

10. **Correction: approve CLAUDE.md with my services line, and write this log.**
    > I approve these changes with one adjustment. Use this services line:
    >
    > - hiring/services.py: shared hiring operations; the close and reopen views use it for job status changes.
    >
    > Keep the confirmation and next-address guidance as proposed.
    >
    > Apply the updates, then write this session log to PROMPTS.md according to its instructions. Include the three RED-to-GREEN tests, no-op behavior for repeated actions, and completed browser checks.
    >
    > Show me the changed-file summary and proposed commit message before committing. Don't start Phase 5.

### Summary

- **Outcome:**
  - **Services:** new `hiring/services.py` with `close_job(job)` (sets Closed and `closed_at = timezone.now()`) and `reopen_job(job)` (sets Open and clears `closed_at`). Both save only `status`, `closed_at` and `updated_at`. No migration was needed: the fields came in Phase 3.
  - **No-op repeats:** closing an already-Closed job changes nothing, keeping the original `closed_at` and `updated_at`. Reopening an already-Open job changes nothing, keeping `updated_at`. This covers stale pages and double submits. Each has an ordinary test.
  - **Views and URLs:**
    - `/jobs/<pk>/close/` shows a confirmation page on GET and closes on POST.
    - `/jobs/<pk>/reopen/` is POST-only (`@require_POST`), so a GET gets a 405 response.
    - Both redirect through a `_next_or()` helper. It follows `next` only when `url_has_allowed_host_and_scheme` accepts it for `request.get_host()`, with HTTPS required only when the request is HTTPS. Otherwise it falls back to job detail.
  - **Confirmation page:**
    - Shows the active-applications count (0 until Phase 7).
    - Explains that stages stay unchanged, only Reject and Mark withdrawn remain available, and new applications are blocked.
    - Carries a validated `?next=` in a hidden field, and sends Cancel to the same validated address or to job detail.
  - **Job detail:** shows Close job for Open jobs and a Reopen job POST form for Closed jobs. The closed date was already shown on detail and in the list from Phase 3, and is now tested in Central time.
  - **TDD test 1** (closing needs the confirmation page and a POST): RED with `assert 'open' == JobOpening.Status.CLOSED` after scaffolding a display-only view. The GET checks in the same test passed from the start, only because the scaffold changed nothing. The agent reported this rather than claiming them as RED. Adding `close_job` and calling it on POST made it GREEN.
  - **TDD test 2** (reopening sets Open and clears `closed_at`): RED with `assert 'closed' == JobOpening.Status.OPEN` after scaffolding a POST-only view that only redirected. Adding `reopen_job` made it GREEN.
  - **TDD test 3** (close and reopen follow only a same-site `next`): parametrized over both actions and three addresses (`/jobs/?status=closed`, `https://evil.example.com/`, `//evil.example.com/`). RED in the two same-site cases with `assert '/jobs/1/' == '/jobs/?status=closed'`. The four off-site cases passed from the start because the views ignored `next`, which the agent reported. Adding `_next_or()` made all six GREEN, with the off-site cases now passing because the address is checked.
  - **All three were genuine RED-to-GREEN cycles.**
  - **Ordinary tests:** 13 more test functions (15 cases), covering:
    - close-again and reopen-again no-ops
    - a GET to reopen returning 405 and leaving the job Closed
    - the confirmation page's explanation text
    - `next` surviving from the confirmation page's GET, through its hidden field, to the POST redirect
    - Cancel following a same-site `next`, and a missing or off-site `next` being dropped from both the hidden field and Cancel
    - which button job detail shows for each status
    - editing a closed job's details and skills keeping status and `closed_at` while updating last-updated
    - the closed date in Central time on detail and in the Closed list
  - **Automated checks:** 101 tests passed. `ruff check`, `ruff format --check` and `makemigrations --check` were clean. `tailwind build` succeeded.
  - **Browser checks (by me):** all passed. They covered closing through confirmation and POST, closed-list behavior, editing while closed keeping the closed date, reopening clearing it, external `next` addresses being rejected, a local `next` being preserved, GET not being able to reopen, and the dark narrow-screen layout.
  - **Docs:** Phase 4's acceptance criteria are ticked in the plan. CLAUDE.md's Project layout gained the `services.py` line. Conventions now cover confirmation pages (delete, close) with POST-only actions (reopen), and the validated `next` rule, including the hidden field and Cancel.
- **Deviations:**
  - **GET-reopen test:** I added an ordinary test that a GET can't reopen a job.
  - **No-op scope:** the agent suggested making a repeat close keep `closed_at`. I also required it to keep `updated_at`, and asked for the same on reopening an already-open job.
  - **Cancel and `next` carry-through:** I required Cancel to use the validated address too, and a test that `next` survives from the confirmation page's GET through the form POST.
  - **CLAUDE.md wording:** I replaced the agent's `services.py` line with my own. The agent's proposal said views *and admin* call the services, which goes beyond what exists so far.
- **Sideways:**
  - **Early passes:** parts of tests 1 and 3 passed before the behavior existed, as described above. They were reported, not hidden, and become real guards once the code exists.
  - **No-op tests not run RED:** the no-op checks were added together with their tests, as ordinary work, so those tests weren't seen failing first. The agent said so.
  - **Nonexistent method:** while implementing test 3, the agent first wrote `job.get_absolute_url()`, which `JobOpening` doesn't define. It caught this before running anything and used `reverse("hiring:job_detail", ...)` instead.
  - **Ambiguous edit:** one test-file edit failed because its target text appeared three times. It was redone with more context. Mechanical, no effect on the tests.
  - **Formatter:** `ruff format --check` flagged one line in test 3 that fit on one line. `ruff format` rewrapped it, with no change to what it asserts.
  - **Skill lookup:** `/implement` isn't one of the session's registered skills, so the agent read `.claude/skills/implement/SKILL.md` directly.

## 2026-11-01 — Phase 3 follow-up: commit retry and push

### Prompts

1. **Commit and push Phase 3.**
   > I approve the file list and commit message. Commit Phase 3 on main and push to origin. Report whether the push succeeded and the working tree is clean. Don't start Phase 4.

2. **Log the retry and commit this update.**
   > Append a short follow-up session entry to PROMPTS.md according to its instructions. Record the failed PowerShell commit attempt, the successful retry using a scratch message file, and the successful Phase 3 push. Preserve existing entries.
   >
   > Commit and push this documentation update with the message "Document Phase 3 commit retry". Don't start Phase 4.

### Summary

- **Outcome:**
  - **Phase 3 commit:** `e124a3b` "Phase 3: Job openings with skills" on `main`, with the 20 approved files and the approved message.
  - **Push:** succeeded (`e9d9c1d..e124a3b main -> main`), and the working tree was clean afterwards.
  - **This entry:** committed and pushed separately as "Document Phase 3 commit retry".
- **Deviations:**
  - None. I asked for this follow-up entry because the main Phase 3 entry was written before the commit.
- **Sideways:**
  - **Failed commit attempt:** the agent piped a PowerShell here-string to `git commit -F -`. Windows PowerShell 5.1 passed the message as a pathspec instead, and git failed with "did not match any file(s) known to git". Nothing was committed, and `git push` reported "Everything up-to-date". The files were left staged with no partial commit.
  - **Retry:** the agent wrote the approved message to a file in its session scratchpad and committed with `git commit -F <file>`, which succeeded.
  - **Phase 3 log timing:** the failure wasn't in the main Phase 3 entry, because that entry was written before committing. The agent flagged this and waited for my prompt instead of editing the log unprompted.

## 2026-11-01 — Phase 3: Job openings with skills

### Prompts

1. **Start Phase 3 (`/implement`).**
   > /implement @prd/applicant-tracking-system.md @plans/applicant-tracking-system.md implement Phase 3 only
   >
   > Read CLAUDE.md and follow the implement and tdd skills. Propose the TDD candidates, explain each in beginner-friendly language, and wait for my approval before writing code.
   >
   > After implementation and automated checks, give me the browser verification steps and wait for my confirmation. Don't mark the phase complete, commit, push, or start Phase 4 yet.

2. **Approve both candidates, with a split and an admin requirement.**
   > I approve both candidates. For candidate 2, use separate tests for the default Open filter and preserving search/filter values in pagination links, so failures are easy to understand.
   >
   > Keep the planned admin bulk-delete check too; don't assume the QuerySet test alone proves the admin behavior.
   >
   > Start with candidate 1. Show me its test and RED result, then stop for approval before implementing the protection.

3. **Approve test 1 (QuerySet delete protection).**
   > I approve this test. Implement the QuerySet deletion protection, then show me the GREEN result and regression results before moving on.
   >
   > The protection must count usage by both open and closed jobs. Keep the separate tests for single-object deletion, the app delete page, and admin bulk deletion.

4. **Start test 2 (default Open filter).**
   > Yes, move on to candidate 2, starting with the default Open filter test. Show me the test and its RED result, then stop for approval before making it pass.
   >
   > Keep the remaining deletion-path tests and protections on the Phase 3 checklist.

5. **Approve test 2.**
   > I approve this test. Add the default Open filter, then show me the GREEN result and regression results. Stop before starting the pagination test.

6. **Start test 3 (pagination links).**
   > Yes, start the pagination test. Show that it checks search and filter values are preserved in the actual next-page link. Show me the test and RED result, then stop for approval before implementing the change.

7. **Approve test 3.**
   > I approve this test. Make pagination links preserve the search and filter values, then show me the GREEN result and regression results before continuing.

8. **Continue with the rest of Phase 3, with a logging correction.**
   > Yes, continue with the rest of Phase 3 as listed, including the remaining skill-deletion protections and their separate tests.
   >
   > One logging correction: we completed three RED-to-GREEN tests in this phase: QuerySet deletion protection, the default Open filter, and pagination preserving search/filter values.
   >
   > Run all planned checks, then give me the browser verification steps. Wait for my confirmation before marking Phase 3 complete, committing, pushing, or starting Phase 4.

9. **Browser checks passed; mark complete and propose CLAUDE.md.**
   > Phase 3 manual verification passed: job creation and required fields, list ordering, editing and skills, search/filter/pagination, invalid-filter fallback, skill protection for open and closed jobs, admin single and bulk deletion protection, shared skill renaming, job deletion, and narrow-screen layout.
   >
   > Mark Phase 3 complete. Show me any proposed CLAUDE.md updates, limited to concise, durable conventions established and verified in this phase. If nothing needs adding, say so.
   >
   > Don't commit or start Phase 4 yet.

10. **Correction: approve CLAUDE.md with adjustments, and write this log.**
    > Approve the updates with these adjustments:
    >
    > - Record shared fixtures in hiring/tests/conftest.py and data builders in hiring/tests/helpers.py, without listing individual function names.
    > - Keep the Tailwind source-scanning note.
    > - Use this deletion guidance: "Where built-in PROTECT is insufficient, enforce deletion rules on both model and QuerySet paths. App and admin deletion pages must explain blocking records instead of returning an error page."
    > - Keep the list-page convention.
    >
    > Apply the updates and write this session log to PROMPTS.md according to its instructions. Record the three RED-to-GREEN tests and completed browser checks.
    >
    > Show me the changed-file summary and proposed commit message before committing. Don't start Phase 4.

### Summary

- **Outcome:**
  - **Model:** `JobOpening` with title, department, employment type (Full-time, Part-time, Contract, Internship), description, optional location, status (Open/Closed, default Open), `closed_at`, timestamps, and a plain `skills = ManyToManyField(Skill, blank=True, related_name="jobs")`. Ordered by `Lower("title")`. Migration `0003_jobopening`.
  - **Skill delete protection:** a `refuse_if_used()` helper raises `ProtectedError` when any job uses the skill, open or closed. Both `SkillQuerySet.delete()` and `Skill.delete()` call it. A bulk delete that includes even one used skill refuses everything. The app's delete page catches `ProtectedError` and lists the jobs using the skill, with no Delete button. `SkillAdmin.get_deleted_objects` adds those jobs as protected objects, so admin single and bulk delete show Django's "cannot delete" page.
  - **Jobs list:** GET title search (case- and space-insensitive), Open/Closed/All filter defaulting to Open with unknown values falling back to Open, sorted by title, 25 per page, Next/Previous links carrying the cleaned `q` and `status`, and all seven columns (Active applications shows 0 until Phase 7).
  - **Job pages:** create and edit share `JobOpeningForm` (no status or closed-date fields, skills as checkboxes), detail with skills and Central-time created/updated/closed times, and a GET/POST delete confirmation.
  - **Admin:** `JobOpening` is registered with `JobOpeningAdminForm` (the app form with admin widgets) and `filter_horizontal` skills. Status, closed date and timestamps are read-only.
  - **TDD test 1** (QuerySet delete of a used skill is refused, and the skill and its link remain): RED with `Failed: DID NOT RAISE ProtectedError`, because Django deleted the skill and silently dropped its job link. Adding `SkillQuerySet.delete()` made it GREEN.
  - **TDD test 2** (the jobs list shows only Open jobs by default): RED with `assert ['Closed Role', 'Open Role'] == ['Open Role']` after scaffolding an unfiltered list. Filtering on Open made it GREEN. The agent noted this only satisfied the test until the filter was read from the URL.
  - **TDD test 3** (the rendered next-page link keeps search and filter): the test parses the actual `rel="next"` href and expects exactly `q=data`, `status=all`, `page=2`. It used `status=all` so the value could only come from the URL. RED with `assert {'page': ['2']} == {...}` after scaffolding plain `?page=N` links. Adding `page_query` made it GREEN.
  - **All three were genuine RED-to-GREEN cycles**, across the two approved candidates (candidate 2 was split into tests 2 and 3, as I asked).
  - **Ordinary tests:** 42 more, covering:
    - single `Skill.delete()`, a closed job protecting a skill, all-or-nothing bulk delete, unused skills deleting through every path
    - the skill delete page explaining blocking jobs, and a forged POST refused
    - admin bulk delete refused for open and for closed jobs, admin single delete refused, and unused skills deleting in admin
    - jobs list filters (including the fallback), search, search plus filter, title order, 25 per page with page 2 filtered, the Previous link, columns and links
    - job create (Open, trimmed, skills, optional location and skills, required fields, status ignored), edit (details, skills, last-updated, prefilled form), detail in CST and CDT, skill rename shown on open and closed jobs, a 404, and delete confirmation
    - admin job add and change sharing the form, with status and closed date not editable
    - the new job create page redirecting signed-out visitors
  - **Automated checks:** 80 tests passed. `ruff check`, `ruff format --check` and `makemigrations --check` were clean. `tailwind build` succeeded.
  - **Browser checks (by me):** all passed. They covered job creation and required fields, list ordering, editing and skills, search/filter/pagination, the invalid-filter fallback, skill protection for open and closed jobs, admin single and bulk delete protection, shared skill renaming, job deletion, and the narrow-screen layout.
  - **Docs:** Phase 3's acceptance criteria are ticked in the plan. CLAUDE.md's Project layout now records the shared test fixture and helper files and the Tailwind `forms.py` scan. Conventions gained the deletion guidance and the list-page convention.
- **Deviations:**
  - **Candidate 2 split:** I required separate tests for the default Open filter and for pagination links, so failures would be easier to read.
  - **Admin proof:** I required a separate admin bulk-delete test instead of relying on the QuerySet test, plus separate tests for single delete and the app delete page.
  - **Closed jobs:** I required the protection to count closed jobs as well as open ones. It's tested in the model, in admin, and in my browser check.
  - **CLAUDE.md wording:** I replaced the agent's deletion convention with my own wording and removed individual function names from the test-layout line.
- **Sideways:**
  - **Miscounted cycles:** after test 3 the agent said "both approved TDD cycles are complete". I corrected the log to three RED-to-GREEN tests across the two candidates.
  - **Shell append failed:** the agent's first attempt to append the ordinary job tests through a Bash heredoc failed with a quoting error and wrote nothing. It added them with the edit tool instead.
  - **Apostrophe test repair:** one new test looked for `can&#x27;t` but the apostrophe is literal template text, which Django doesn't escape. It was a mechanical repair to `can't`.
  - **Missing CSS classes:** before giving the browser steps, the agent noticed that Tailwind only scanned template folders, so the `textarea` and `checkbox` classes set in `forms.py` would be missing. It added `forms.py` as a Tailwind source and confirmed both classes in the built CSS.
  - **Test refactor:** `make_job` moved to `hiring/tests/helpers.py` and `employee_client` to `hiring/tests/conftest.py` during cycle 2. The approved test 1 asserted the same things afterwards.
  - **Admin wording:** Django's "cannot delete" page says deleting would require "deleting the following protected related objects", which isn't quite accurate for a skill link. It's Django's standard text and was left as is.
  - **Not done here:** the job delete page always returns to the jobs list. Handling a `next` return address comes with close and reopen in Phase 4.

## 2026-11-01 — Phase 2: Skills page

### Prompts

1. **Start Phase 2 (`/implement`).**
   > /implement @prd/applicant-tracking-system.md @plans/applicant-tracking-system.md implement Phase 2 only
   >
   > Read CLAUDE.md and follow the implement and tdd skills.
   >
   > Propose the TDD candidates and wait for my approval before writing code. Explain each in beginner-friendly language.
   >
   > Don't start Phase 3. After automated checks pass, give me the browser verification steps and wait for my confirmation before marking the phase complete.

2. **Approve the TDD candidates.**
   > I approve all three candidates. Implement Phase 2 only, following the TDD approval stops one test at a time.
   >
   > If a later test already passes because an earlier change provides that behavior, report it honestly as a regression test. Don't remove working protection just to manufacture a RED result.
   >
   > Show me the first test and its assertion failure, then wait for my approval before making it pass.

3. **Approve test 1 and its error wording.**
   > I approve this test and the error wording. Add the form validation, then show me the GREEN result and relevant regression results. Stop for my review before starting the next test.

4. **Confirm cycle 1 and start test 2.**
   > Yes, I'm happy with this result. Start test 2 for renaming a skill to its own name with different capitalization. Show me the test and its RED result, then stop for approval before changing the validation.

5. **Approve test 2.**
   > I approve test 2. Update the duplicate lookup to exclude the skill being edited. Run both skill tests and the regression suite, then show me the GREEN results before moving to test 3.

6. **Start test 3.**
   > Yes, proceed to test 3. Show me the database-constraint test and its RED assertion result before adding the constraint or migration. Then wait for my approval.

7. **Approve test 3.**
   > I approve test 3. Add the case-insensitive unique constraint and generate its migration. Run all skill tests and the full regression suite, then show me the GREEN results before continuing.

8. **Continue with the rest of Phase 2.**
   > Yes, continue with the remaining Phase 2 work and ordinary tests. Keep trimming in the form; don't add a model save override.
   >
   > Make sure creating and renaming through both the app and Django admin trim surrounding spaces and reject duplicates with a friendly error.
   >
   > Run all planned checks, then give me the browser verification steps. Wait for my confirmation before marking Phase 2 complete, committing, pushing, or starting Phase 3.

9. **Browser checks passed; mark complete and propose CLAUDE.md.**
   > All Phase 2 browser checks passed, including duplicate validation, trimming, renaming, alphabetical order, delete confirmation and cancel, admin behavior, and the narrow-screen dark layout.
   >
   > Mark Phase 2 complete. Show me any proposed CLAUDE.md updates, limited to useful conventions established and verified in this phase. If nothing needs adding, say so.
   >
   > Don't commit or start Phase 3 yet.

10. **Correction: approve CLAUDE.md with shorter lines, and write this log.**
    > Approve the updates with these shorter lines:
    >
    > - Forms live in hiring/forms.py; normalize user input in forms rather than model save() overrides.
    > - Where case-insensitive uniqueness is required, pair a database constraint with friendly form validation that excludes the current record on edit.
    > - App and admin forms should share validation behavior.
    > - Delete confirmation pages use GET for display and POST for deletion.
    >
    > Leave the Commands and Project layout sections unchanged.
    >
    > Apply these updates, then write this session log to PROMPTS.md according to its instructions. Include the three RED-to-GREEN tests and browser verification.
    >
    > Show me the changed-file summary and proposed commit message before committing. Don't start Phase 3.

### Summary

- **Outcome:**
  - **Model:** `Skill` with a `name`, ordered by `Lower("name")`, and a `UniqueConstraint(Lower("name"), name="unique_skill_name_ci")`. Migrations `0001_initial` (model) and `0002_skill_unique_skill_name_ci` (constraint).
  - **Pages:** the Skills placeholder became a real alphabetical list with New skill, Rename and Delete buttons. `/skills/new/` and `/skills/<pk>/edit/` share `SkillForm` and `skill_form.html`. `/skills/<pk>/delete/` shows a confirmation on GET and deletes only on POST. Usage protection waits for Phase 3, as planned.
  - **Form:** `hiring/forms.py` `SkillForm`. Django's form field trims the name, and `clean_name` rejects a case-insensitive match against other skills with "A skill with this name already exists." There's no model `save()` override.
  - **Admin:** `Skill` is registered with `SkillAdminForm`, a subclass of `SkillForm` with `widgets = {}`, so admin trims and validates like the app while keeping admin's own widgets.
  - **TDD test 1** (create with a case or space duplicate shows a form error): parametrized over `python`, `  Python  ` and ` PYTHON`. RED with `assert 302 == 200` in all three cases, because the form saved the duplicate and redirected. Adding `clean_name` with a `name__iexact` lookup made it GREEN.
  - **TDD test 2** (rename to its own name in different case saves): RED with `assert 200 == 302`, because `clean_name` matched the skill's own row. This was the gap the agent had flagged after test 1. Adding `exclude(pk=self.instance.pk)` made it GREEN.
  - **TDD test 3** (database rejects a case-insensitive duplicate without the form): RED with `Failed: DID NOT RAISE IntegrityError`. That's pytest's `raises` expectation failing, not missing scaffolding. Adding the constraint and its migration made it GREEN. Tests 1 and 2 were unaffected.
  - **All three were genuine RED-to-GREEN cycles.** None passed early, so no test had to be reported as a regression test.
  - **Ordinary tests:** 14 more, covering:
    - alphabetical order ignoring case, and the list's links
    - trimming on create and rename, and a blank name being rejected
    - renaming onto another skill's name being rejected
    - the rename page prefilled with the current name
    - the delete confirmation not deleting on GET, and deleting on POST
    - a 404 for a missing skill
    - admin add and change: trimming, rejecting duplicates, and allowing a skill's own name in different case
  - **Automated checks:** 35 tests passed. `ruff check`, `ruff format --check` and `makemigrations --check` were clean. `migrate` and `tailwind build` succeeded.
  - **Browser checks (by me):** all passed. They covered duplicate validation, trimming, renaming, alphabetical order, delete confirmation and cancel, admin behavior, and the narrow-screen dark layout.
  - **Docs:** Phase 2's acceptance criteria are ticked in the plan. CLAUDE.md's Conventions gained four lines (forms and normalization, case-insensitive uniqueness, shared app/admin validation, GET/POST delete confirmation). Commands and Project layout are unchanged.
- **Deviations:**
  - **Trimming location:** the agent noted that the database constraint covers capitalization but not spaces, and offered model-level trimming. I kept trimming in the form only, with no `save()` override.
  - **Admin parity:** I explicitly required admin create and rename to trim and reject duplicates like the app, which led to `SkillAdminForm` and the four admin tests.
  - **CLAUDE.md wording:** I replaced the agent's four proposed convention lines with shorter, more general wording.
- **Sideways:**
  - **Formatter:** `ruff format --check` flagged one over-long line in a new test. It was rewritten and the checks re-ran clean.
  - **Two migrations:** the constraint arrived in its own migration (`0002`) because the TDD order added it after the model. They were left as two migrations, not squashed.
  - **What the admin tests prove:** Django's admin form strips text by default, and model validation also reports the constraint's `violation_error_message`. So the admin trimming and duplicate tests would likely pass even without `SkillAdminForm`. They prove the admin *behavior*, not that the shared form is what produces it. The shared form keeps the two paths using the same code.
  - **Local database:** the agent ran `migrate` against the local `db.sqlite3` during the checks.

## 2026-11-01 — Phase 1: project setup, sign-in and dark app shell

### Prompts

1. **Start Phase 1 (`/implement`).**
   > /implement @prd/applicant-tracking-system.md @plans/applicant-tracking-system.md implement Phase 1 only
   >
   > Read CLAUDE.md and follow the approved plan and our implement and tdd skills.
   >
   > Before writing code, propose the TDD test candidates and wait for my approval. Explain what each test checks in beginner-friendly language.
   >
   > Don't start Phase 2. After implementation and automated checks, give me the browser verification steps and wait for me to test them before marking Phase 1 complete.

2. **Approve the TDD candidates.**
   > I approve both TDD candidates. Start Phase 1 only.
   >
   > For each candidate, show me the test and its RED result, explain why it failed and what passing will prove, then stop for my approval before writing the code that makes it pass.

3. **Approve test 1 and ask for GREEN.**
   > I approve this test as written. Add the planned login protection, run the test, and show me the GREEN result before moving on.
   >
   > If the inactive-session test already passes afterward, report that honestly as a regression test of existing behavior rather than claiming another RED-to-GREEN cycle.

4. **Confirm cycle 1 and move to candidate 2.**
   > Yes, I agree this implements the intended behavior. Move on to candidate 2. Show me the test and its result, and report whether it passes immediately without any additional code changes.

5. **Continue with the rest of Phase 1.**
   > Yes, continue with the remaining Phase 1 work as listed. Keep the normal authentication backend unchanged.
   >
   > Run the planned automated checks, then give me the exact steps to start the app and verify Phase 1 in the browser. Wait for my browser checks before marking the phase complete, committing, pushing, or starting Phase 2.

   *(A "Tool loaded." message arrived while the agent was stopping its smoke-test server. It carried no instruction.)*

6. **Browser checks passed; mark complete and propose CLAUDE.md.**
   > Phase 1 browser checks passed: login protection, employee access, navigation, admin refusal, logout, deactivation of an existing session, inactive login refusal, narrow-screen menu, and dark theme.
   >
   > During testing, an admin save returned a CSRF error. Opening the admin form fresh and retrying worked; no code change was needed.
   >
   > Mark Phase 1 complete and show me the proposed CLAUDE.md updates. Add only verified commands, actual project structure, and useful conventions established in Phase 1. Keep it concise.
   >
   > Don't commit or start Phase 2 yet.

7. **Correction: approve CLAUDE.md with a narrower Windows note, and write this log.**
   > I approve the diff, with one wording change: make the Windows encoding note specific to the command you actually observed needing PYTHONIOENCODING=utf-8. Leave broader troubleshooting details in README.
   >
   > Apply the updates, then write this session log to PROMPTS.md according to its instructions. Include the TDD results, browser checks, and the CSRF error resolved by reopening the form.
   >
   > Show me the changed-file summary and proposed Phase 1 commit message before committing. Don't start Phase 2.

### Summary

- **Outcome:**
  - **Project:** uv project (Python 3.14, Django 6.1.2) with the `config` package and the single `hiring` app. Ruff and pytest/pytest-django are configured in `pyproject.toml`. Central-time settings, and Django's login/logout views under `/accounts/`. After sign-in, staff land on a Pipeline placeholder. Placeholder Candidates, Jobs and Skills pages are there for the nav.
  - **Front end:** django-tailwind-cli pinned to tailwind-cli-extra 2.10.34 (Tailwind 4.3.3, DaisyUI 5.7.50), with DaisyUI's `dark` as the only theme. HTMX 2.0.4 is vendored. The base layout's top nav collapses into a ☰ menu on narrow screens, and Log out is a POST form. The login page is styled to match.
  - **TDD candidate 1** (signed-out visitor redirected to login): RED with `assert 200 == 302`, because no login requirement existed yet. Adding `LoginRequiredMiddleware` in settings made it GREEN. I agreed this implements the behavior site-wide, not just for the tested URL.
  - **TDD candidate 2** (deactivated user's existing session refused): passed on its first run with no new code, because Django's default `ModelBackend` already treats inactive users as signed out on every request. It's recorded as a **regression test of existing behavior, not a RED-to-GREEN cycle**. To show the test can fail, the agent ran it once from a scratch file outside the repo with `AllowAllUsersModelBackend` swapped in, and it failed with `assert 200 == 302`. The project's auth backend wasn't changed.
  - **Ordinary tests:** 14 more, covering:
    - every page redirecting signed-out visitors, and the login page staying public
    - landing on Pipeline after sign-in, and returning to the requested page
    - an inactive account not being able to sign in
    - a non-staff employee being refused at `/admin/`, while a superuser gets in
    - logout working by POST and being rejected by GET
    - the nav contents and the dark theme
  - **Automated checks:** 16 tests passed. `ruff check`, `ruff format --check`, `makemigrations --check` and `manage.py check` were all clean.
  - **Browser checks (by me):** all passed. They covered login protection, employee sign-in and access, navigation, admin refusal, logout, deactivation ending an existing session, inactive sign-in refusal, the narrow-screen menu, and the dark theme.
  - **Docs:** Phase 1's acceptance criteria are ticked in the plan. CLAUDE.md gained Commands, Project layout and Conventions sections. README has setup, run, checks, troubleshooting and layout.
- **Deviations:**
  - **Honest reporting:** I asked up front that candidate 2 be reported as a regression test if it passed immediately, and it was. The agent had flagged that likely outcome before writing it.
  - **Auth backend:** I explicitly asked to keep Django's normal authentication backend unchanged.
  - **CLAUDE.md wording:** I narrowed the Windows encoding note to the one command observed failing (`tailwind config`). The broader troubleshooting went in README instead.
- **Sideways:**
  - **Windows encoding:** `tailwind config` crashed with `UnicodeEncodeError` printing emoji to the cp1252 console. Setting `PYTHONIOENCODING=utf-8` fixed it. The agent then confirmed that `tailwind runserver` works from PowerShell without it.
  - **Scratch check settings:** the first scratch run of the failure check didn't pick up the Django settings because the file was outside the repo. Rerunning with `--ds=config.settings` fixed it.
  - **CSRF error:** during my browser checks, an admin save returned a CSRF error. Reopening the admin form and saving again worked. It was a stale token, not a code bug, and no change was needed.
  - **Line length:** Ruff flagged long lines in Django's generated password-validator settings. E501 was turned off in favor of the formatter's line length.

## 2026-11-01 — Initial CLAUDE.md for the Applicant Tracking System

### Prompts

1. **Draft the initial CLAUDE.md.**
   > Create the initial CLAUDE.md for this project using:
   > - @prd/applicant-tracking-system.md
   > - @plans/applicant-tracking-system.md
   > - @prototypes/stage-rules-decisions.md
   > - @prototypes/pipeline-ui-decisions.md
   >
   > Keep it to 20-30 lines. Include only:
   > 1. A one-line project description.
   > 2. The approved technology stack and package manager.
   > 3. Durable, project-wide architecture decisions already established in the PRD.
   > 4. Short pointers to the PRD, plan, and prototypes instead of repeating their details.
   >
   > Don't add commands yet because the tooling hasn't been installed or verified.
   > Don't predict project structure, paths, template conventions, URL conventions, or testing commands that don't exist yet.
   > Describe approved architecture as decisions, not as code that already exists.
   > Don't copy business requirements, user stories, phases, rejected alternatives, or detailed stage rules into CLAUDE.md.
   > Don't invent new conventions or pad the file just to reach the line count.
   >
   > Show me the draft and its line count for review. Don't start implementation.

2. **Correction: draft revisions.**
   > This is close. Please revise the draft before saving it:
   >
   > - Describe architecture as approved decisions rather than existing code.
   > - Replace the services line with: "Use shared service operations for application creation, stage changes, and job closing/reopening. Save application stage changes and their history together in a transaction."
   > - Shorten the history-facts line to: "Derive past workflow facts from stage history rather than duplicating them in application fields."
   > - Replace the deletion line with: "Apply the PRD's record-protection rules consistently across app, ORM, and admin deletion paths."
   > - Keep the rest concise and within 20-30 lines.
   >
   > Show me the revised draft and line count. Don't start implementation.

3. **Approve, save and write this log.**
   > I approve this version. Save it as CLAUDE.md at the repository root.
   >
   > Write this session log to PROMPTS.md according to its instructions, including the draft review and revisions. Don't start implementation yet.

### Summary

- **Outcome:**
  - **CLAUDE.md:** saved at the repo root, 25 lines. It has a one-line project description, the stack (Python, Django, SQLite, uv, Tailwind + DaisyUI via django-tailwind-cli, HTMX, Ruff, pytest + pytest-django), nine approved architecture decisions, and pointers to the PRD, plan and both prototype decision files.
  - **Left out on purpose:** commands, URLs, templates, test layout, user stories, phases, detailed stage rules, and plan-only details (`LoginRequiredMiddleware`, storing `Application.stage`, the `stages.py`/`services.py` file names). The stage-rules and services modules are described the way the PRD describes them.
  - **Not started:** no production code and no tooling installed.
- **Deviations:**
  - **Framing:** the first draft's "Architecture decisions" section read partly like existing code. I had it reframed as approved decisions. The heading became "Approved architecture decisions" and every bullet is now an instruction.
  - **My wording:** I replaced the agent's services, history-facts and deletion lines with my own shorter wording. The deletion line now points to the PRD's protection rules instead of naming model and QuerySet `delete()`.
- **Sideways:**
  - **Draft before saving:** the first prompt said both "create" and "show me the draft for review". The agent showed the draft in chat and didn't write the file until I approved the revised version.
  - Nothing else went wrong.

## 2026-11-01 — Phased implementation plan for the Applicant Tracking System

### Prompts

1. **Create the plan (`/prd-to-plan`).**
   > /prd-to-plan @prd/applicant-tracking-system.md
   >
   > Create a phased implementation plan from the approved PRD. Also read both prototype decision files in prototypes/.
   >
   > Keep each phase small enough to complete in one session. Each phase should deliver a working behavior I can test in the browser, including the models, forms, views, templates, and tests it needs. Don't split phases into database-only or UI-only layers.
   >
   > For each phase, explain what it delivers, which requirements it covers, and the manual browser checks I'll perform. Include test-candidate approval, TDD where applicable, session logging, a review of CLAUDE.md updates, and a commit and push after verification.
   >
   > Don't implement anything yet or create CLAUDE.md. Save the plan and give me its filename so I can review it first.

   *(I rejected the agent's first write of `plans/applicant-tracking-system.md` and interrupted the request before sending the next prompt.)*

2. **Correction: plan revisions.**
   > The plan looks good overall, but please revise these points:
   >
   > 1. CLAUDE.md must be created and approved before implementation, after planning. Remove instructions to create it during Phase 1. Phase 1 should only update the existing file with commands and structure that have actually been verified. Don't record conventions for later features before they exist.
   >
   > 2. Split Phase 6 into two smaller working phases:
   > - Record an application from the candidate detail page, including models, initial history, validation, duplicate protection, candidate/job deletion protection, and a basic full-page application view.
   > - Build the three-column workspace, add the job-side application entry point, connect application links, and show counts and empty states.
   >
   > Keep both phases usable and manually testable. Renumber later phases and update their references.
   >
   > 3. Make sure the TDD workflow follows our actual tdd and implement skills. All test candidates used for TDD need my approval; don't treat the suggested candidates as already approved.
   >
   > 4. Each phase should end with updating the session log when prompted, reviewing changes and the commit message, committing and pushing after verification, and then /clear before the next phase.
   >
   > Keep the approved product decisions unchanged. Don't implement anything yet.

3. **Approve the plan and write this log.**
   > The phase sizes look good. Keep all 14 phases as written.
   >
   > I approve storing the current stage on Application, updated by the services together with its history entry. Keep deriving the past rule facts from history. We can decide demo timestamps in Phase 14.
   >
   > Mark the plan Approved. Don't implement anything or create CLAUDE.md yet.
   >
   > Write this session log to PROMPTS.md according to its instructions, including the plan review, revisions, and approval.

### Summary

- **Outcome:**
  - **Plan:** `plans/applicant-tracking-system.md`, marked **Approved**. It has 14 vertical-slice phases, each one session long and testable in the browser:
    1. Project setup, sign-in and dark app shell
    2. Skills
    3. Job openings with skills
    4. Closing and reopening jobs
    5. Candidates
    6. Recording an application from the candidate page
    7. The pipeline workspace
    8. Moving applications
    9. Reopening finished applications and workspace job controls
    10. Workspace list: stage groups, tabs and search
    11. HTMX selection and browser history
    12. HTMX stage actions and application details
    13. Application deletion and admin protections
    14. Demo seed data and final polish
  - **Each phase lists:** covered user stories and stage rules, what it builds, acceptance criteria, possible TDD candidates (marked not approved), and manual browser checks.
  - **Plan header:** durable decisions covering the owning app, auth approach, a URL table, models and relationships, where rules live, HTMX full vs. partial responses, front end, time and tooling.
  - **"How every phase runs":** the `/implement` and `/tdd` steps with their approval stops. Each phase ends with marking it complete, a CLAUDE.md review, the session log when I prompt for it, reviewing changes and the commit message, commit and push, then `/clear`.
  - **Decisions settled at approval:** `Application.stage` stores the current stage, written only by the services together with its history entry. The past rule facts stay derived from history. Demo history timestamps are deferred to Phase 14.
  - **Not started:** no CLAUDE.md and no production code.
- **Deviations:**
  - **CLAUDE.md timing:** the agent's draft created CLAUDE.md in Phase 1. I moved its creation to a separate step after planning and before implementation. Phases only update it with verified commands, structure and conventions.
  - **Phase 6 split:** I split the draft's large "record applications and basic workspace" phase in two: a candidate-page application path with a basic full-page view (Phase 6), then the three-column workspace with the job-side entry point, links, counts and empty states (Phase 7). That took the plan from 13 phases to 14.
  - **TDD approval:** I required the TDD steps to follow the real `/tdd` and `/implement` skills, with every candidate needing my approval in the session.
  - **Phase ending:** I added reviewing changes and the commit message, the session log only when prompted, and `/clear` before the next phase.
- **Sideways:**
  - **Rejected first write:** I rejected the agent's first plan write for the four issues above, before it was saved.
  - **Skipped quiz step:** the `/prd-to-plan` skill says to present the phase breakdown and iterate before writing the file. The agent wrote the file straight away because I'd asked for a saved plan to review. It listed the phases and asked the granularity questions after the revision instead.
  - **Skill conflict:** the `/implement` skill says to update PROMPTS.md when finishing a phase, while PROMPTS.md says entries are added only when prompted. The revised plan follows PROMPTS.md: the log is written only when I prompt for it.
  - **Memory note:** the agent saved a memory note recording these workflow preferences for later sessions.

## 2026-11-01 — Design interview, two prototypes, and approved PRD for the Applicant Tracking System

### Prompts

1. **Start the design interview (`/grill-me`).**
   > /grill-me
   >
   > I'm starting a new Django project called Applicant Tracking System. It's for a company's hiring team to keep track of job openings, candidates, and where each application is in the hiring process.
   >
   > I've already created the new repo, copied over my skills, added the prototype skill, and created PROMPTS.md. There isn't any Django code yet.
   >
   > For this assignment, we have to use:
   > - Python
   > - Django
   > - SQLite
   > - uv
   > - Tailwind CSS with DaisyUI using django-tailwind-cli
   > - HTMX
   > - Ruff
   > - Automated tests, either Django's built-in tests or pytest. We can talk through which one to use.
   >
   > Here are the requirements from the hiring department:
   > - This is only for employees involved in hiring. Candidates won't log in.
   > - Staff need to keep track of candidates and their basic information. They might come from the company website, job boards, referrals, or other places.
   > - Staff need to create and edit job openings. Openings can be open or closed.
   > - Staff need to record when a candidate applies for an opening.
   > - A candidate can apply for multiple jobs, but they can't have more than one application for the same opening.
   > - The hiring stages have to include Applied, Screening, Interview, Final Review, Offer, Hired, Rejected, and Withdrawn.
   > - Staff need an easy way to see what stage applications are in and move them without reloading the whole page.
   > - Job openings need to have skills associated with them, and the same skill can be used for multiple openings.
   >
   > We still need to figure out what information to store for candidates and jobs, how employee access works, and what happens to candidate records over time. We also need to decide what happens when a job closes, whether it can reopen, and how existing applications are handled.
   >
   > I'd also like help deciding how to organize the Django app and where the rules should go. Keep it fairly simple and explain the choices so I understand what I'm agreeing to and can explain them later.
   >
   > Ask me one question at a time, and wait for my answer before deciding anything.
   >
   > For the assignment, I need to use /prototype twice during this conversation:
   > - Once to try out the rules for moving applications between hiring stages.
   > - Once to compare different ways the hiring dashboard or pipeline could work.
   >
   > When we get to either of those topics, let me know and pause so I can run /prototype myself before making those decisions.
   >
   > My professor showed an example with a job list, a board with columns for hiring stages, and a table view. Those are just ideas, so don't assume I want all of those features. I want to work through the options and make my own choices.
   >
   > For now, we're just working through the design. Don't start building the Django app yet.

2. **Q1, employee access.**
   > Let's go with A. An admin will create employee accounts through Django's admin site, and there won't be a public signup. All employees using the system will have the same access, and all hiring pages should require login. We can decide whether records can be deleted or archived when we get to that question.

3. **Q2, candidate fields.**
   > Let's go with B. First name, last name, and email will be required, and the other fields can be optional. Email should be unique regardless of capitalization, with extra spaces trimmed.
   >
   > A general notes field on the candidate sounds good. We can discuss notes about a specific job when we get to applications. Let's leave resume uploads out.

4. **Q3, candidate source.**
   > Let's go with A. We'll store how the candidate first came to the company using Company Website, Job Board, Referral, or Other, with an optional source details field for things like the job board name or who referred them. It won't change automatically when they apply for another opening.

5. **Q4, job opening fields.**
   > Let's go with B. Title, department, employment type, and description should be required. Location can be optional, and staff can enter Remote there when appropriate. Plain text for department and location is fine. Include the automatic timestamps, and we can settle the closing rules in the later question.

6. **Q5, skills.**
   > Let's go with A and (i). Use a simple Skill model with names that are unique regardless of capitalization, and trim extra spaces. Job openings can share skills through a plain ManyToManyField.
   >
   > Staff should have a simple Skills list/create page inside the app, then choose existing skills on the job form. Let's leave required versus preferred skills and creating skills directly on the job form out of this project.

7. **Q6, job status and reopening, then pause for the logic prototype.**
   > Let's go with A, and new openings should start as Open. Closing records closed_at, and reopening clears it. We don't need a full history of job closures.
   >
   > Before approving how closing affects existing applications, I'd like to explore that behavior along with the application-stage rules in the required logic prototype.

8. **Logic prototype (`/prototype`).**
   > /prototype
   >
   > Let's prototype the application-stage rules and what happens to applications when a job closes.
   >
   > Use the stages and open questions from our grill conversation. These rules aren't approved yet, so make any suggested defaults clear and let me compare alternatives. I'd like to try allowing or blocking skipped stages, backward moves, and reopening completed applications. Also let me compare what happens when closing a job leaves applications unchanged versus freezing their movement.
   >
   > Keep the job status decision we already made: openings start Open, can close, and can reopen.
   >
   > Make a standalone HTML file in prototypes/ that I can open directly in my browser. Don't build any production Django code.
   >
   > Include readable current-state information, free-play controls, and guided scenarios for:
   > - The normal path from Applied to Hired.
   > - Skipping a stage and moving backward.
   > - Rejecting or withdrawing, then trying to reopen.
   > - Correcting an accidental stage change.
   > - Closing a job with applications still in progress.
   > - Trying to add an application to a closed job.
   > - Reopening the job and checking its applications.
   > - Trying to add a duplicate application for the same candidate and opening.
   >
   > Keep it focused on testing the rules, rather than designing the final dashboard. Explain how to open and use it, then wait for my feedback before treating any rules as approved.

9. **Logic prototype feedback and stage-rule decisions.**
   > I've gone through all eight scenarios. Here's what I want:
   >
   > - New applications start at Applied.
   > - Normally, staff can skip forward and move back to any earlier active stage. Moving backward is useful when someone needs another screening or interview.
   > - Staff can reject or withdraw an application from any active stage.
   > - Hired and Rejected applications can reopen only to the stage they were in before that outcome, which lets staff correct mistakes.
   > - Withdrawn is different: reopening it returns the existing application to Applied, and it must go through every stage again without forward skips. Backward moves are still allowed. This exception wasn't supported by the prototype, so I haven't tested it yet.
   > - Closing a job leaves applications in their current stages and blocks movement except to Rejected or Withdrawn.
   > - Closed jobs cannot accept new applications or have applications moved to Hired.
   > - Reopening a job clears closed_at and allows active applications to move again. It doesn't automatically reopen completed applications.
   > - Duplicate applications for the same candidate and opening are always blocked, regardless of stage.
   > - A candidate can still apply to a different open job using the same candidate record and a separate application.
   >
   > Please record these choices and why we chose them alongside the prototype. Note that the Withdrawn exception still needs verification, and carry it into the PRD and implementation tests.
   >
   > Then continue /grill-me one question at a time. Don't start production code yet, and remember we still need the separate UI prototype.

   *(I rejected the agent's first write of `prototypes/stage-rules-decisions.md` and interrupted the request before sending the next prompt.)*

10. **Correction: settle the Withdrawn open details before recording.**
    > These rules look good overall. Let's settle the open details now:
    >
    > - Once a Withdrawn application reopens, the no-forward-skipping rule stays with that application, including if it is later Rejected or Hired and reopened again. Otherwise, reopening it could bypass the requirement to repeat every stage.
    > - If it withdraws again and reopens, it returns to Applied again.
    > - Offer to Hired is allowed because it is the next step.
    > - Reopening any finished application requires the job to be open.
    > - No direct moves between final outcomes. Staff must reopen the application first.
    >
    > Please update the decisions and test expectations to match. Don't treat a particular implementation, such as a flag, as an approved architecture decision yet.
    >
    > Also, please describe the rejected one-stage-at-a-time option as limiting fast-tracking. Backward-movement restrictions were what blocked corrections; those are separate rules.
    >
    > Then continue the interview.

11. **Q7, stage history.**
    > Let's go with B. Each application should have a simple stage history showing the old stage, new stage, date and time, and which employee made the change. Include the initial application and reopening events so staff can follow the whole process.
    >
    > We don't need a full audit log for candidate or job edits. We can decide how the history is stored and used by the rules when we discuss the architecture.

12. **Q8, application fields.**
    > Let's go with B. Applied on should default to today but be editable so staff can record the actual application date. Include an optional notes field for feedback specific to that job, plus automatic created and updated timestamps.
    >
    > We don't need a separate comments thread. Let's revisit optional rejection and withdrawal reasons during the UI prototype, but don't make them a requirement yet.

13. **Q9, candidate deletion (plus confirming no future applied-on dates).**
    > Let's go with D. Staff can delete a candidate only if they have no applications, with a confirmation page. If they have any applications, keep the candidate and their hiring history protected. We don't need archiving for now.
    >
    > Don't make Django admin an automatic exception to that protection. Any special cleanup can be handled separately.
    >
    > And yes, applied-on dates should not be in the future.

14. **Q10, job deletion.**
    > Let's go with A. Staff can delete a job opening only if it has no applications, with a confirmation page. If any applications exist, deletion should be blocked, including through Django admin. Closing is the normal way to retire an opening while keeping its hiring history.

15. **Q11, application deletion and reassignment.**
    > Let's go with B. An application can be deleted after confirmation only if its history contains just the initial Applied entry and it has never changed stages. Editing notes or the applied-on date doesn't affect that eligibility.
    >
    > Once any stage movement has happened, deletion is blocked, including through Django admin, even if the application later returns to Applied. The candidate and job can't be changed after creation. If those were entered incorrectly, staff must delete the unused application and create the correct one.

16. **Q12, skill rename and delete.**
    > Let's go with A. Staff can rename skills, keeping the trimmed, case-insensitive uniqueness rule. Renaming updates the name everywhere it's used, including closed openings.
    >
    > Deleting requires confirmation and is blocked if any open or closed job uses the skill. Staff must remove those links first. Apply the same deletion protection in Django admin.

17. **Q13, editing closed jobs.**
    > Let's go with C. Staff can edit a closed job's details and skills without reopening it. Show Last updated alongside the closed date.
    >
    > Editing must leave its status and closed_at unchanged. Reopening should remain a separate action, and edits shouldn't change existing applications or their stage history.

18. **Q14, app structure and user model.**
    > Let's go with A: a config project folder and one hiring app containing the hiring models and features.
    >
    > Keep Django's built-in User model as we decided earlier. We don't need custom account fields or behavior, so I'd rather keep authentication straightforward. Use Django's built-in login and logout views, with no separate accounts app.

19. **Q15, where rules live.**
    > Let's go with C and a small services.py. Keep the stage decisions in stages.py, and have services perform changes and write their history together in a transaction. Views should stay straightforward.
    >
    > Make sure the admin follows the same rules. Don't allow direct editing of application stages or history there; stage changes should use the same approved operations.
    >
    > Also account for bulk deletion in admin and QuerySet.delete(), since overriding a model's delete() alone doesn't cover those paths. Protect used skills while keeping the plain ManyToManyField we chose.
    >
    > Please distinguish database guarantees from rules enforced through our supported app and admin operations. Don't describe services as impossible to bypass. Keep the implementation focused rather than adding a general-purpose framework.

20. **Q16, where rule facts come from.**
    > Let's go with A. We already keep stage history, so I'd rather use that than store the same facts in extra Application fields.
    >
    > The service should get the stage before the current Hired or Rejected outcome from its history entry, and check whether the application has ever reopened from Withdrawn. Then pass those facts into stages.py.
    >
    > Keep history protected from editing and deletion through the app and admin, except when deleting an application that qualifies under our unused-application rule. Include tests for repeated reopening and withdrawal sequences so we know the history gives the right answers.

21. **Q17, testing framework.**
    > Let's go with B, pytest with pytest-django. Use parametrized tests for the stage-rule cases where it makes sense, and explain fixtures when we get to implementation so I understand the setup.

22. **UI prototype (`/prototype`).**
    > /prototype
    >
    > Let's compare different ways staff could view and manage the hiring pipeline.
    >
    > Use our approved requirements and stage rules. Build a standalone HTML prototype in prototypes/ using a lightweight Tailwind CSS and DaisyUI setup, without creating the production Django app or installing a separate toolchain.
    >
    > I'd like three structurally different options:
    > - A per-job board with applications grouped into stage columns.
    > - A compact application table with search, filters, and stage controls.
    > - A list-and-detail workspace where selecting an application shows its details and actions beside the list.
    >
    > Use the same realistic sample data across the options so I can compare them fairly. Include enough applications to see how each layout handles a busy opening.
    >
    > Let me try:
    > - Choosing a job and viewing its applications.
    > - Moving an application using our approved rules.
    > - Viewing notes and stage history.
    > - Reopening a finished application.
    > - Viewing a closed job and understanding which actions are blocked.
    > - Finding Hired, Rejected, and Withdrawn applications.
    > - Entering an optional rejection or withdrawal reason so I can decide whether to include that feature.
    >
    > Make the permanent no-skip restriction on applications reopened from Withdrawn visible and enforce it in the demo. Don't copy the old prototype's behavior where it differs from our approved decisions.
    >
    > Keep interactions in memory with no real data changes. Include an easy variant switcher, and explain how to open and compare the options.
    >
    > These are alternatives to evaluate, not approved features. Don't assume we'll build all three views. Wait for my feedback before choosing a direction.

23. **UI prototype feedback: dark theme.**
    > I've tested most of the prototype and it looks good so far. Can you change all three variants to a dark theme? The white background strains my eyes after a while.
    >
    > Use dark gray backgrounds with readable text and clear contrast for buttons, stage labels, and blocked actions. Keep the layouts and behavior the same for now so I can keep comparing them. Include the detail panels, modals, dropdowns, notes, and history in the dark theme too.
    >
    > Don't treat this as choosing a layout yet. My preference is a dark UI, but we still need to settle which interface to build.

24. **UI direction chosen.**
    > I like option C, the list-and-detail workspace, best. Let's use that direction with the dark theme.
    >
    > I especially like the stage progress indicator and having the actions, notes, and history beside the application list. It feels easier to work with someone without opening and closing different pages.
    >
    > We don't need the separate board and table views. Please record this choice and why, then continue /grill-me one question at a time to settle the remaining UI details, including whether to keep optional rejection and withdrawal reasons.

25. **Q18, rejection and withdrawal reasons.**
    > Let's go with A. Reject and Mark withdrawn should open an inline confirmation box with an optional reason. Save the reason on that stage history entry and display it in the timeline.
    >
    > For now, reasons should only be offered for moves to Rejected or Withdrawn. We don't need them for other stage moves or reopening. Keep the confirmation step even when the reason is left blank.

26. **Q19, navigation.**
    > Let's go with A. After login, staff should land on the Pipeline workspace. Keep the top navigation on every page, with Pipeline, Candidates, Jobs, Skills, the username, and Log out. The jobs sidebar should appear only in the workspace.
    >
    > Use regular Django pages and forms for managing candidates, jobs, and skills. Candidate detail pages should list their applications and link to the selected application in the workspace.
    >
    > If there are no open jobs, show a clear empty state with a link to create a job. Closed jobs should still be accessible from the workspace. We don't need a separate summary dashboard.

27. **Q20, recording applications.**
    > Let's go with C, without inline candidate creation. Staff can add an application from the selected job in the workspace or from a candidate's detail page, using shared form logic and the same service.
    >
    > From the workspace, only show candidates who haven't already applied to that job. From the candidate page, only show open jobs they haven't applied to. Keep server-side validation and the database duplicate constraint too.
    >
    > After saving, open the workspace with the new application selected. For a new candidate, staff should create their candidate record first, then add the application from their detail page.

28. **Q21, HTMX and URLs.**
    > Let's go with B. Selecting an application should update its detail panel without reloading the whole page, and the URL should follow the selection.
    >
    > Each application URL must also work as a normal full-page link for bookmarks, refresh, and links from candidate pages. Back and Forward should restore the correct selection and highlight.
    >
    > Stage changes should update the detail panel, application list, and any affected counts together without a full reload. Saving notes should use HTMX too. Switching jobs can stay a normal full-page link.
    >
    > Keep the full-page and partial responses straightforward, and include checks for refresh, direct links, and browser history.

29. **Q22, workspace list filtering.**
    > Let's go with A. Use Active, Finished, and All tabs with counts, stage groups in pipeline order, and a name or email search. Within each stage, show the most recent stage changes first.
    >
    > Keep the tab and search in the URL so refresh and browser history preserve them. Tab counts should reflect the selected job and search, before applying the Active or Finished tab.
    >
    > If a stage move puts the selected application outside the current filter, keep its updated details visible and explain that it no longer matches the list. Don't automatically switch tabs or clear my search.

30. **Q23, detail panel actions.**
    > Let's go with A. Keep the primary actions, buttons for other allowed moves, and a collapsed section explaining blocked moves. Keep the closed-job and no-skip alerts too.
    >
    > Reject and Withdraw must always open the inline confirmation box with the optional reason. No alternate button should bypass that step.
    >
    > The service should re-check every submitted move. If it's no longer allowed, show a clear error in the panel and refresh the available actions without changing the stage or adding a history entry.

31. **Q24, closing and reopening jobs.**
    > Let's go with B. Put Close job and Reopen job in the workspace header and on the job detail page, using the same views and services.
    >
    > Closing should use a separate confirmation page showing how many applications are still active and explaining that their stages stay unchanged, but only Reject and Withdraw remain available. Also explain that new applications will be blocked.
    >
    > Reopening can be a button without confirmation. Both actions should submit through POST. Afterward, return to the page staff came from, preserving the selected application and filters when returning to the workspace.

32. **Q25, Candidates and Jobs list pages.**
    > Let's go with A, using regular GET forms submitted with a button or Enter. No live search is needed on these pages.
    >
    > Candidates should be searchable by name or email and sorted by last name, then first name. Jobs should also have a title search, with Open, Closed, and All filters, defaulting to Open, and be sorted alphabetically by title.
    >
    > Use 25 records per page and preserve search and filter values when changing pages. The proposed columns sound good. Keep Skills as a simple alphabetical list with the create, rename, and protected-delete actions we already chose.

33. **Q26, smaller screens (with a correction).**
    > Let's go with A. Keep the three columns side by side on wide screens and stack them on narrow screens. Collapse the top navigation into a menu when needed.
    >
    > After selecting an application on a narrow screen, bring its detail panel into view. Make sure forms, buttons, and long text fit without causing horizontal page scrolling.
    >
    > I haven't provided a specific 16px-gutter requirement, so don't record that as an assignment requirement. This is our choice to make the app usable in smaller windows.

34. **Q27, demo seed data.**
    > Let's go with A. Include fictional candidates, skills, open and closed jobs, and applications covering the important stage and reopening scenarios. Create applications and stage history through our real services.
    >
    > Refuse to run if hiring data already exists. Leave out --reset for now so the command can't erase existing records.
    >
    > Local demo employee accounts are fine, with a known development-only password printed in the terminal. They don't need admin privileges. Document how to run the command once it's implemented and verified.

35. **Q28, time zone.**
    > Let's go with A and America/Chicago. Store timestamps in UTC with timezone support enabled, and display them in Central time. Use Django's timezone.localdate() for the applied-on default and future-date validation so they follow the same local date.

36. **Write the PRD (`/to-prd`).**
    > /to-prd
    >
    > Turn our completed grill conversation and both prototype decision files into the project PRD.
    >
    > Include all approved decisions from the conversation, including those not yet saved in files. Carry forward the fixed technology and business requirements, the stage rules, deletion protections, and the dark list-and-detail workspace.
    >
    > Make the Withdrawn reopening rules explicit, including the permanent no-forward-skipping restriction. Distinguish what we tested in the prototypes from what still needs verification.
    >
    > Include acceptance criteria for HTMX updates, direct application links, refresh, Back and Forward, filters, and selected applications that no longer match the list.
    >
    > Don't add rejected features or treat deferred tooling details as settled. Save the PRD and give me its exact filename. Don't create the implementation plan or production code yet. I want to review the PRD first.

37. **PRD corrections.**
    > The PRD looks good overall. Please make these corrections before I approve it:
    >
    > 1. Correct the database-guarantees section. Django's on_delete=PROTECT is enforced by Django's deletion handling, not a SQLite PROTECT constraint. Separate actual database constraints from protections enforced through Django. Don't claim stage history is impossible to delete through any code path.
    >
    > 2. Explicitly include editing candidate information, with the same validation and unique-email rules used during creation.
    >
    > 3. Explain where staff edit an application's applied-on date and notes. Both remain editable, but candidate and job stay fixed. Applied-on date edits must still reject future dates.
    >
    > 4. Clarify that only active, authenticated employee accounts can access hiring pages. Equal hiring access doesn't mean every employee gets Django admin access.
    >
    > 5. Make the stage-history protection wording consistent: staff cannot independently edit or delete history, but deleting an eligible never-moved application also removes its initial history entry.
    >
    > 6. Use the plain spelling resume instead of accented characters.
    >
    > Keep the other approved decisions unchanged. Show me the revised sections before marking the PRD approved.

38. **Approve the PRD and write this log.**
    > Editing the applied-on date and notes together in the workspace detail panel sounds good. I approve that choice and the revised PRD. Update its status to Approved.
    >
    > Write this session log to PROMPTS.md according to its instructions, including my design decisions, prototype feedback, corrections, and PRD revisions. Don't start planning or implementation yet.

39. **Post-approval wording correction.**
    > Change that sentence to "Every active employee has the same hiring access." Keep the PRD approved.
    >
    > Update this session's log to include this correction and approval accurately. Don't change older session entries.

### Summary

- **Outcome:**
  - **Design interview:** 28 one-at-a-time questions covering access, data model, record lifecycle and deletion protection, architecture, testing, UI details, demo data and time zone.
  - **Logic prototype:** `prototypes/stage-rules.html`, with rule toggles and eight guided scenarios. Decisions are in `prototypes/stage-rules-decisions.md` (15 stage rules plus test expectations; the Withdrawn reopen rules are flagged as needing verification).
  - **UI prototype:** `prototypes/pipeline-ui.html`, with three variants (per-job board, application table, list-and-detail workspace), later switched to a dark theme. Variant C, list-and-detail with a dark theme, was chosen and recorded in `prototypes/pipeline-ui-decisions.md`, along with the rejection and withdrawal reason decision.
  - **PRD:** `prd/applicant-tracking-system.md`, revised once with six corrections and marked **Approved**. After approval, one sentence in the Solution section was corrected to "Every active employee has the same hiring access." The PRD stays **Approved**.
  - **Not started:** no implementation plan and no production Django code.
- **Key design decisions:**
  - **Access:** built-in `User`, admin-created accounts, equal hiring access for active employees, no admin access by default.
  - **Data:** a `config` project with one `hiring` app. Candidates have a case-insensitive unique email and a fixed source list. Jobs are Open or Closed and can reopen. Skills are a plain many-to-many with protected delete. Applications have an applied-on date and notes, edited in the workspace detail panel, with candidate and job fixed.
  - **Stage history:** records who and when, with optional reasons only for Rejected and Withdrawn, and is the source of the facts the rules need.
  - **Stage rules:** forward skips and backward moves allowed. Hired and Rejected reopen to the previous stage. Withdrawn reopens to Applied, with a permanent no-skip restriction. Closed jobs allow only Reject or Withdraw. No direct moves between final outcomes.
  - **Where rules live:** database unique constraints, Django `PROTECT`, a pure stage-rules module, transactional services, and admin and QuerySet delete paths following the same rules.
  - **UI and supporting decisions:** pytest with pytest-django, HTMX selection with URL push and full-page fallbacks, a `seed_demo` command without reset, and `America/Chicago` time.
- **Deviations:**
  - **Q9:** I refused the admin-only deletion exception the agent described. Admin follows the same protections.
  - **Q14:** I declined the agent's recommendation to set up a custom user model at project start, and kept Django's built-in `User`.
  - **Q16:** I overrode the agent's recommendation (store rule facts as Application fields, plus consistency tests). The rules derive facts from stage history instead.
  - **Q25:** jobs are sorted alphabetically by title, and I added a title search, instead of the agent's "title or newest" suggestion.
  - **Q27:** I rejected the proposed `--reset` flag for the seed command, so it can never erase records.
  - **Logic prototype follow-up:** I added a rule the prototype didn't model (Withdrawn → Applied with a permanent no-skip restriction), then settled its open details myself.
  - **Recommendations extended rather than just accepted:** application deletion stays blocked even after returning to Applied (Q11); closed-job edits never touch status or `closed_at` (Q13); explicit Back/Forward and filter-mismatch behavior (Q21, Q22); no control may bypass the Reject/Withdraw confirmation (Q23); tab-count semantics (Q22).
  - **UI prototype:** I asked for a dark theme across all variants before choosing a layout.
  - **Follow-up question:** where applied-on date edits happen, raised during PRD review and approved as the workspace detail panel.
- **Sideways:**
  - **Rejected first write:** I rejected the agent's first write of the stage-rules decisions file and settled the open Withdrawn details first. I also corrected two things in it: implementation details like a "flag" must not read as approved architecture, and the rejected one-stage-at-a-time option limited fast-tracking, while the *backward-movement* restrictions were what blocked corrections.
  - **Overclaimed guarantees:** in Q15 the agent initially implied services "can't be bypassed". I required database guarantees to be kept separate from rules enforced by supported operations.
  - **Admin bulk delete:** the agent's first architecture framing relied on overriding `Model.delete()`. I pointed out that admin bulk delete and `QuerySet.delete()` bypass that.
  - **Invented requirement:** the agent wrote a "16px gutter" requirement into a Q26 option that I never gave. I corrected it.
  - **PRD draft errors, caught in my review and fixed before approval:**
    - It described `on_delete=PROTECT` as a SQLite constraint and implied stage history was undeletable by any path.
    - It omitted candidate editing, where the applied-on date is edited, and the active-account vs. Django-admin distinction.
    - It used the accented spelling of "resume".
  - **Missed inconsistency:** the six revisions missed the Solution section's "Every signed-in employee has the same access," which contradicted the corrected Access decisions. The agent noticed it only after the PRD was approved and while writing the log. It flagged it without editing the approved text. I then had it changed to "Every active employee has the same hiring access" and kept the PRD approved.
  - **Self-caught conflicts:** a conflict between `PROTECT` on history and deleting eligible unused applications, resolved by deleting the initial entry and then the application in one transaction. A UI-prototype mismatch where the move list included Reject/Withdraw buttons that skipped the inline confirm, excluded in the PRD.
  - **Unverified prototypes:** neither HTML prototype was run by the agent. Node wasn't installed, and the agent had no browser, so the code was reviewed by hand. The agent renamed `close`/`reopen` helpers to avoid clashing with `window.close`, and removed a leftover template line and opacity-suffixed color classes before handover.
  - **Session setup:** `/login` was interrupted three times before succeeding.
