## Project #1: Applicant Tracking System

## Question 1 - Trace your Django forms
One regular Form in my project is MoveForm in hiring/forms.py. It handles moving an application to another stage. When someone clicks a stage button in _application_panel.html, it sends the stage and optional reason to application_move in hiring/views.py. The view validates the form, then calls move_application() in hiring/services.py. That service checks the rules and saves the move and its history. If the move is blocked, the page shows an error.

One ModelForm is JobOpeningForm in hiring/forms.py. It is connected to the JobOpening model and handles information like the title, description and skills. The job_create and job_edit views use it, and job_form.html displays it. When the user submits valid information, the view calls form.save() and sends them to the job’s detail page.

The main difference is that a ModelForm is connected to a database model and can save it. A regular Form checks the information, but needs other code to decide what to do with it.

## Question 2 - Trace a many-to-many relationship
Jobs and skills have a many-to-many relationship in my project. One job can require several skills, and one skill can be used by several jobs. For example, both a developer job and a data analyst job could require Python.

A single foreign key would only let one side point to one record. It would not let several jobs share several skills.

The relationship is defined by the skills ManyToManyField on JobOpening in hiring/models.py. Django automatically creates the connecting table, hiring_jobopening_skills. That table stores which job goes with which skill. I did not need to create a separate model because there was no extra information to store about each connection.

## Question 3 - Explain one prototype decision
The UI prototype helped me choose how the application screen should look. I compared a board with stage columns, a table of applications, and a layout with a list and a detail panel.

I picked the list-and-detail layout because I could select an application and see its information beside the list. It keeps the stage buttons, notes and history together, which makes it easier to work through applications. I also picked a dark theme because I preferred it over the white background.

This choice is recorded in prototypes/pipeline-ui-decisions.md and the PRD. The finished application uses it in the pipeline workspace, with jobs on the side, applications in the middle and details beside them.

## Question 4 - Defend one code-design decision
One decision was how to keep track of whether an application had been reopened after being withdrawn. The agent recommended storing extra fields on the application. I chose to get that information from stage history instead.

The history already records each move, so storing the same information somewhere else could lead to the two getting out of sync. Reading the history keeps that information in one place.

This is handled by stage_facts() in hiring/services.py. It checks whether the history contains a move from Withdrawn back to Applied. If it does, the application cannot skip forward anymore. It also checks which stage an application should return to when reopening from Hired or Rejected.