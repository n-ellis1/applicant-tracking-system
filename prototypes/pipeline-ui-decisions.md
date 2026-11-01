# Pipeline UI: Decisions from the UI Prototype

Prototype: [`pipeline-ui.html`](pipeline-ui.html) (throwaway, not production code)
Decided: 2026-11-01, after comparing three variants with the same sample data.

## Chosen direction: Variant C, the list-and-detail workspace, with a dark theme

| Decision | Why |
|----------|-----|
| **Use the list-and-detail workspace** as the hiring pipeline interface: a jobs list, that job's applications grouped by stage, and a detail panel beside the list. | Staff can work with one candidate (actions, notes, history) without opening and closing separate pages. |
| **Keep the stage progress indicator** (stepper) in the detail panel. | It shows at a glance where an application is in the process. |
| **Show actions, notes and stage history beside the list** in the detail panel. | Everything needed to work on an application is in one place. |
| **Use a dark theme**: dark gray backgrounds, readable text, and clear contrast for buttons, stage labels and blocked actions. | The white background caused eye strain during longer use. |

## Not chosen

- **Variant A, the per-job board with stage columns and drag-and-drop:** not needed.
- **Variant B, the application table across all jobs with filters:** not needed.

The board and table won't be built as separate views.

## Rejection and withdrawal reasons (decided after the prototype)

| Decision | Why |
|----------|-----|
| **Reject…** and **Mark withdrawn…** open an **inline confirmation box** in the detail panel with an **optional reason**. Confirmation is required even when the reason is blank. | It guards against misclicks. That matters especially for Withdrawn, which can only reopen to Applied and permanently blocks skipping. |
| The reason is **saved on that stage history entry** and shown in the history timeline. | "Why did this end?" stays tied to the exact move, person and time, separate from editable notes. |
| Reasons are offered **only for moves to Rejected or Withdrawn**, not for other stage moves or reopens. | Matches what was tested, and keeps the other moves simple. |

## Still to settle (continuing in the design interview)

- Other details of the workspace, such as filters, how blocked moves are explained, finding finished applications, and how it connects to the other pages.
