"""Fictional demo data for development, created through the real services."""

from datetime import timedelta
from itertools import cycle

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from hiring import services
from hiring.models import Application, Candidate, JobOpening, Skill
from hiring.stages import Stage

REFUSED = (
    "This database already has hiring data, so seed_demo won't run. "
    "It only seeds an empty database and never mixes with or erases records."
)
USERNAMES_TAKEN = (
    "These demo usernames already exist, so seed_demo won't run: {}. "
    "It never changes existing accounts."
)

# Development only: printed in the terminal, never for a real deployment.
DEMO_PASSWORD = "demo-password-2026"
DEMO_USERS = [
    ("alex.demo", "Alex", "Morgan"),
    ("sam.demo", "Sam", "Taylor"),
]

SKILLS = [
    "Python",
    "Django",
    "SQL",
    "JavaScript",
    "Figma",
    "User Research",
    "Data Analysis",
    "Communication",
    "Customer Support",
    "Social Media",
]

FULL_TIME = JobOpening.EmploymentType.FULL_TIME
PART_TIME = JobOpening.EmploymentType.PART_TIME
CONTRACT = JobOpening.EmploymentType.CONTRACT
INTERNSHIP = JobOpening.EmploymentType.INTERNSHIP

# (title, department, employment type, location, skills, description)
JOBS = [
    (
        "Backend Developer",
        "Engineering",
        FULL_TIME,
        "Remote",
        ["Python", "Django", "SQL"],
        "Builds and maintains the APIs behind our products.",
    ),
    (
        "Product Designer",
        "Design",
        FULL_TIME,
        "Austin, TX",
        ["Figma", "User Research", "Communication"],
        "Designs clear, accessible product experiences from research to "
        "polished screens.",
    ),
    (
        "Data Analyst",
        "Analytics",
        CONTRACT,
        "Remote",
        ["SQL", "Python", "Data Analysis"],
        "Turns product and sales data into reports the team can act on.",
    ),
    (
        "Support Specialist",
        "Customer Success",
        PART_TIME,
        "Dallas, TX",
        ["Customer Support", "Communication"],
        "Helps customers by email and chat and passes product feedback on.",
    ),
    (
        "QA Engineer",
        "Engineering",
        FULL_TIME,
        "",
        ["Python", "JavaScript"],
        "Plans and automates testing for web releases.",
    ),
    (
        "Marketing Intern",
        "Marketing",
        INTERNSHIP,
        "Austin, TX",
        ["Social Media", "Communication"],
        "Supports campaigns and social media for one summer.",
    ),
]
# Closed after its applications are recorded and moved.
CLOSED_JOBS = ["Marketing Intern"]

WEBSITE = Candidate.Source.COMPANY_WEBSITE
JOB_BOARD = Candidate.Source.JOB_BOARD
REFERRAL = Candidate.Source.REFERRAL
OTHER = Candidate.Source.OTHER

# (first name, last name, source, source details, location)
CANDIDATES = [
    ("Maya", "Chen", JOB_BOARD, "Posted on a tech job board", "Austin, TX"),
    ("Jordan", "Rivera", REFERRAL, "Referred by a backend engineer", "Remote"),
    ("Priya", "Patel", WEBSITE, "", "Dallas, TX"),
    ("Sam", "Okafor", WEBSITE, "", "Houston, TX"),
    ("Leo", "Martins", JOB_BOARD, "", "Remote"),
    ("Aisha", "Bello", REFERRAL, "Referred by the design lead", "Austin, TX"),
    ("Ethan", "Brooks", OTHER, "Met at a university career fair", "San Antonio, TX"),
    ("Grace", "Kim", JOB_BOARD, "", "Remote"),
    ("Daniel", "Novak", WEBSITE, "", "Fort Worth, TX"),
    ("Owen", "Hughes", WEBSITE, "", "Dallas, TX"),
    ("Lena", "Fischer", OTHER, "University career center", "Austin, TX"),
    ("Carlos", "Mendez", JOB_BOARD, "", "Austin, TX"),
    ("Hannah", "Lee", WEBSITE, "", "Round Rock, TX"),
]

APPLIED = Stage.APPLIED
SCREENING = Stage.SCREENING
INTERVIEW = Stage.INTERVIEW
FINAL_REVIEW = Stage.FINAL_REVIEW
OFFER = Stage.OFFER
HIRED = Stage.HIRED
REJECTED = Stage.REJECTED
WITHDRAWN = Stage.WITHDRAWN

# (candidate "First Last", job title, days ago applied, moves in order).
# A move is a stage, or (stage, reason) for Rejected and Withdrawn.
# Applications are recorded in this order, so within a stage group the
# later one shows first in the workspace.
APPLICATIONS = [
    # Never moved: the one that can be deleted.
    ("Sam Okafor", "Backend Developer", 2, []),
    # Moved back to Applied: still can't be deleted.
    ("Leo Martins", "Backend Developer", 20, [SCREENING, APPLIED]),
    # Hired after skipping; reopens to Final Review and may still skip.
    ("Jordan Rivera", "Backend Developer", 30, [INTERVIEW, FINAL_REVIEW, HIRED]),
    # Rejected; reopens to Screening.
    (
        "Priya Patel",
        "Backend Developer",
        25,
        [SCREENING, (REJECTED, "Looking for more Django experience.")],
    ),
    # Reopened from Withdrawn: back through Applied, no skipping from now on.
    (
        "Maya Chen",
        "Backend Developer",
        28,
        [
            SCREENING,
            INTERVIEW,
            (WITHDRAWN, "Accepted another offer, then changed their mind."),
            APPLIED,
            SCREENING,
        ],
    ),
    ("Maya Chen", "Product Designer", 14, [INTERVIEW]),
    ("Ethan Brooks", "Product Designer", 18, [OFFER]),
    # Restricted, hired, then reopened to Offer: still can't skip.
    (
        "Aisha Bello",
        "Product Designer",
        40,
        [
            SCREENING,
            (WITHDRAWN, "Paused their job search."),
            APPLIED,
            SCREENING,
            INTERVIEW,
            FINAL_REVIEW,
            OFFER,
            HIRED,
            OFFER,
        ],
    ),
    ("Jordan Rivera", "Data Analyst", 9, [SCREENING]),
    ("Grace Kim", "Data Analyst", 12, [(WITHDRAWN, "")]),
    (
        "Daniel Novak",
        "Data Analyst",
        16,
        [INTERVIEW, (REJECTED, "Chose a candidate with more SQL experience.")],
    ),
    ("Priya Patel", "Support Specialist", 5, []),
    ("Owen Hughes", "Support Specialist", 7, [SCREENING]),
    # The Marketing Intern job closes with these still in progress.
    ("Lena Fischer", "Marketing Intern", 35, [SCREENING, INTERVIEW]),
    ("Carlos Mendez", "Marketing Intern", 33, [SCREENING]),
    ("Ethan Brooks", "Marketing Intern", 45, [FINAL_REVIEW, HIRED]),
    (
        "Hannah Lee",
        "Marketing Intern",
        38,
        [(REJECTED, "Not available for the full summer.")],
    ),
]


class Command(BaseCommand):
    help = "Create fictional demo data on an empty database. There's no reset."

    def handle(self, *args, **options):
        models = (Skill, JobOpening, Candidate, Application)
        if any(model.objects.exists() for model in models):
            raise CommandError(REFUSED)
        usernames = [username for username, _, _ in DEMO_USERS]
        taken = User.objects.filter(username__in=usernames)
        if taken.exists():
            names = ", ".join(sorted(user.username for user in taken))
            raise CommandError(USERNAMES_TAKEN.format(names))

        # All or nothing: any failure leaves the database as it was.
        with transaction.atomic():
            users = self.create_users()
            counts = self.create_data(users)

        self.stdout.write(self.style.SUCCESS("Demo data created."))
        self.stdout.write(counts)
        self.stdout.write("")
        self.stdout.write(
            self.style.WARNING(
                "DEVELOPMENT ONLY: these demo accounts share a known password. "
                "Never seed a real deployment."
            )
        )
        self.stdout.write(f"Usernames: {', '.join(usernames)}")
        self.stdout.write(f"Password:  {DEMO_PASSWORD}")

    def create_users(self):
        # Ordinary employees: not staff, so no admin access.
        return [
            User.objects.create_user(
                username=username,
                password=DEMO_PASSWORD,
                first_name=first_name,
                last_name=last_name,
            )
            for username, first_name, last_name in DEMO_USERS
        ]

    def create_data(self, users):
        skills = {name: Skill.objects.create(name=name) for name in SKILLS}

        jobs = {}
        for title, department, kind, location, skill_names, description in JOBS:
            job = JobOpening.objects.create(
                title=title,
                department=department,
                employment_type=kind,
                location=location,
                description=description,
            )
            job.skills.set([skills[name] for name in skill_names])
            jobs[title] = job

        candidates = {}
        for first, last, source, details, location in CANDIDATES:
            candidates[f"{first} {last}"] = Candidate.objects.create(
                first_name=first,
                last_name=last,
                email=f"{first}.{last}@example.com".lower(),
                source=source,
                source_details=details,
                location=location,
            )

        # Spread the work across the demo employees.
        employees = cycle(users)
        today = timezone.localdate()
        for name, title, days_ago, moves in APPLICATIONS:
            application = services.create_application(
                candidate=candidates[name],
                job=jobs[title],
                applied_on=today - timedelta(days=days_ago),
                changed_by=next(employees),
            )
            for move in moves:
                target, reason = move if isinstance(move, tuple) else (move, "")
                services.move_application(
                    application, target, changed_by=next(employees), reason=reason
                )

        for title in CLOSED_JOBS:
            services.close_job(jobs[title])

        return (
            f"{len(users)} demo employees, {len(skills)} skills, {len(jobs)} jobs "
            f"({len(CLOSED_JOBS)} closed), {len(candidates)} candidates, "
            f"{len(APPLICATIONS)} applications."
        )
