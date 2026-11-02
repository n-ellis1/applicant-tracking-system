from hiring.models import Application, Candidate, JobOpening


def make_candidate(**fields):
    defaults = {
        "first_name": "Jane",
        "last_name": "Doe",
        "email": "jane.doe@example.com",
        "source": Candidate.Source.COMPANY_WEBSITE,
    }
    return Candidate.objects.create(**(defaults | fields))


def make_job(**fields):
    defaults = {
        "title": "Backend Developer",
        "department": "Engineering",
        "employment_type": JobOpening.EmploymentType.FULL_TIME,
        "description": "Builds APIs.",
    }
    return JobOpening.objects.create(**(defaults | fields))


def assert_stage_matches_history():
    """Every application's stage equals its latest history entry's new stage."""
    for application in Application.objects.all():
        latest = application.history.last()
        assert latest is not None, f"{application} has no history"
        assert application.stage == latest.new_stage, application
