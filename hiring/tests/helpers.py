from hiring.models import JobOpening


def make_job(**fields):
    defaults = {
        "title": "Backend Developer",
        "department": "Engineering",
        "employment_type": JobOpening.EmploymentType.FULL_TIME,
        "description": "Builds APIs.",
    }
    return JobOpening.objects.create(**(defaults | fields))
