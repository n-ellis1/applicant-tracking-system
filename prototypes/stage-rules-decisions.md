# Stage Rules: Decisions from the Logic Prototype

Prototype: [`stage-rules.html`](stage-rules.html) (throwaway, not production code)
Decided: 2026-11-01, after working through all eight guided scenarios.

Stages: Applied, Screening, Interview, Final Review, Offer, Hired, Rejected, Withdrawn.
- **Active stages:** Applied, Screening, Interview, Final Review, Offer
- **Final outcomes:** Hired, Rejected, Withdrawn

## Decisions

| # | Rule | Why |
|---|------|-----|
| 1 | New applications start at **Applied**. | Every application has one clear starting point. |
| 2 | On an open job, staff can **skip forward** to any later active stage, or to Hired, unless rule 7 applies. | Real hiring sometimes fast-tracks people, such as a strong referral going straight to Interview. |
| 3 | On an open job, staff can **move back to any earlier active stage**. | Someone may need another screening or interview. It also lets staff fix accidental forward moves. |
| 4 | Staff can move an application to **Rejected or Withdrawn from any active stage**. | A candidate can be turned down or drop out at any point in the process. |
| 5 | **No direct moves between final outcomes**, such as Rejected → Withdrawn or Hired → Rejected. Staff must reopen the application first. | Every change to an outcome goes through an explicit reopen, so it follows the reopen rules. |
| 6 | **Hired** and **Rejected** can be reopened **only to the stage they were in right before that outcome**. | This lets staff fix a mis-click, like Rejected instead of Hired, without making final outcomes easy to undo by accident. |
| 7 | **Withdrawn is the exception:** reopening returns the *existing* application to **Applied**. From then on, that application can **never skip forward**: it must take every stage one step at a time. Backward moves and moves to Rejected or Withdrawn are still allowed. | A candidate who withdrew and comes back is starting over, so the team should re-evaluate them step by step. |
| 8 | The no-skip restriction from rule 7 **stays with the application permanently**, even if it's later Hired or Rejected and reopened again. If it withdraws again and reopens, it **returns to Applied again**. | Otherwise, reopening could be used to get around the requirement to repeat every stage. |
| 9 | **Offer → Hired is allowed** for a restricted application, because it's the next step. | Rule 7 blocks skips, not ordinary single steps. |
| 10 | **Reopening any finished application** (Hired, Rejected or Withdrawn) **requires the job to be open**. | Closed jobs don't progress. Staff reopen the job first. |
| 11 | Closing a job **leaves applications in their current stages** and **blocks all movement except to Rejected or Withdrawn**. | Closed jobs stop progressing, but staff can still tidy up the leftover candidates. |
| 12 | A closed job **can't accept new applications** and **can't have applications moved to Hired**. | Hiring for a closed job would contradict its status. |
| 13 | Reopening a job **clears `closed_at`** and lets **active** applications move again. It does **not** automatically reopen finished applications. | Reopening the job and reopening a candidate are separate decisions. Staff reopen individual applications under rules 6–8 when they mean to. |
| 14 | **Duplicate applications are always blocked:** one application per candidate per opening, whatever stage the existing one is in. | This is a requirement. A returning candidate is handled by reopening their existing application, not by creating a second one. |
| 15 | A candidate can apply to a **different open job** using the same candidate record and a separate application. | This is a requirement. Candidate data lives in one place, and each job tracks its own application. |

How the application remembers that it was reopened from Withdrawn is **not decided yet**. That's an implementation choice for later design.

## ⚠️ Needs verification: the Withdrawn reopen rules (rules 7–9)

The prototype didn't model the Withdrawn exception, so it hasn't been tried hands-on. These rules must be written into the PRD as explicit rules and covered by implementation tests.

Test expectations:

**Reopening from Withdrawn**
- Reopening a Withdrawn application moves it to **Applied**, regardless of the stage it withdrew from.
- It reuses the **same application record**, with no duplicate created.

**After a Withdrawn reopen (restricted application)**
- A forward **skip is blocked**, for example Applied → Interview.
- A **single forward step** is allowed, for example Applied → Screening.
- **Offer → Hired** is allowed.
- **Backward moves** to any earlier active stage are allowed.
- Moving to **Rejected or Withdrawn** from any active stage is allowed.

**The restriction is permanent**
- If a restricted application is Rejected and then reopened to its previous stage, a forward skip is **still blocked**.
- If a restricted application is Hired and then reopened to Offer, the restriction **still applies**.
- If a restricted application withdraws again and reopens, it **returns to Applied** and is still restricted.

**Applications never reopened from Withdrawn**
- Reopening Hired or Rejected goes **only to the previous stage**, and forward skips are allowed afterward.

**Final outcomes and closed jobs**
- Direct moves between final outcomes (Rejected ↔ Withdrawn, Hired → Rejected, and so on) are **blocked**.
- Reopening a Hired, Rejected or Withdrawn application on a **closed** job is **blocked**.
- On a closed job, moves to Rejected or Withdrawn from active stages are allowed, and all other moves are blocked, including → Hired.
- A new application for a closed job is blocked.
- Reopening a job clears `closed_at`, allows active applications to move again, and leaves finished applications unchanged.
- A duplicate application for the same candidate and opening is blocked, even when the existing one is Rejected or Withdrawn.

## Options considered and not chosen

- **"One stage at a time" for every application:** it got in the way of fast-tracking candidates. It's kept only for applications reopened from Withdrawn (rule 7).
- **"Only one stage back" and "no backward moves":** these backward-movement restrictions blocked corrections and stopped candidates from returning to an earlier stage, such as Final Review → Screening.
- **"Reopen to any active stage":** too easy to undo outcomes carelessly.
- **"Freeze everything when the job closes":** this stopped staff from rejecting leftover candidates.
- **"Closing leaves applications fully movable":** this let a closed job keep hiring.
