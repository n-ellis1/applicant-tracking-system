import html
import re
from datetime import timedelta
from html.parser import HTMLParser

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

from hiring import services
from hiring.forms import ApplicationDetailsForm
from hiring.models import Application
from hiring.stages import Stage
from hiring.tests.helpers import assert_stage_matches_history, make_candidate, make_job

HTMX = {"HX-Request": "true"}


@pytest.fixture
def employee(employee_client):
    return User.objects.get(username="employee")


def record(candidate, job, employee):
    return services.create_application(
        candidate=candidate,
        job=job,
        applied_on=timezone.localdate(),
        changed_by=employee,
    )


def move_url(application, query):
    return f"{reverse('hiring:application_move', args=[application.pk])}?{query}"


VOID_TAGS = {"br", "hr", "img", "input", "link", "meta"}


class _Element(HTMLParser):
    """Finds the element with an id: its attributes and its inner HTML."""

    def __init__(self, element_id):
        super().__init__(convert_charrefs=False)
        self.element_id = element_id
        self.depth = 0
        self.attrs = None
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if self.depth:
            self.parts.append(self.get_starttag_text())
            if tag not in VOID_TAGS:
                self.depth += 1
        elif dict(attrs).get("id") == self.element_id and self.attrs is None:
            self.attrs = dict(attrs)
            self.depth = 1

    def handle_endtag(self, tag):
        if self.depth and tag not in VOID_TAGS:
            self.depth -= 1
            if self.depth:
                self.parts.append(f"</{tag}>")

    def handle_data(self, data):
        if self.depth:
            self.parts.append(data)

    def handle_entityref(self, name):
        if self.depth:
            self.parts.append(f"&{name};")

    def handle_charref(self, name):
        if self.depth:
            self.parts.append(f"&#{name};")


def element(content, element_id):
    """The element's attributes and inner HTML, or (None, "") if it's missing."""
    parser = _Element(element_id)
    parser.feed(content)
    return parser.attrs, "".join(parser.parts)


def text(fragment):
    """Visible text with tags removed and spaces collapsed."""
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", fragment)).split())


# Stage actions through HTMX


def test_htmx_move_updates_the_panel_list_tab_counts_and_sidebar_together(
    employee_client, employee
):
    job = make_job(title="Data Analyst")
    moved = record(make_candidate(), job, employee)
    record(make_candidate(first_name="Bob", email="bob@example.com"), job, employee)
    services.move_application(moved, Stage.OFFER, changed_by=employee)

    # The All tab keeps the hired application listed. Offer to Hired leaves
    # the active stages, so the in-progress count drops from 2 to 1.
    response = employee_client.post(
        move_url(moved, "jobs=open&tab=all"), {"stage": Stage.HIRED}, headers=HTMX
    )

    assert response.status_code == 200
    content = response.content.decode()
    assert Application.objects.get(pk=moved.pk).stage == Stage.HIRED
    # A partial, not the full page, and the browser stays on the application
    # URL: nothing redirects to or records the POST endpoint.
    assert "<!doctype html>" not in content
    for header in ["HX-Redirect", "HX-Push-Url", "HX-Replace-Url"]:
        assert header not in response.headers
    # The panel shows the new stage and the move in its history.
    assert "Offer → Hired" in html.unescape(content)
    # The list moves the application into the Hired group, out of band.
    attrs, inner = element(content, "application-list")
    assert attrs.get("hx-swap-oob") == "true"
    hired_group = re.search(
        r'aria-label="Hired applications">(.*?)</ul>', inner, re.S
    ).group(1)
    assert text(hired_group) == "Jane Doe jane.doe@example.com"
    # The tab counts follow the move, out of band.
    attrs, inner = element(content, "list-controls")
    assert attrs.get("hx-swap-oob") == "true"
    tabs = [text(tab) for tab in re.findall(r'<a role="tab".*?</a>', inner, re.S)]
    assert tabs == ["Active 1", "Finished 1", "All 2"]
    # The sidebar's in-progress count follows the move, out of band.
    attrs, inner = element(content, "sidebar-jobs")
    assert attrs is not None
    assert attrs.get("hx-swap-oob") == "true"
    assert "Data Analyst 1 in progress" in text(inner)


def detail_url(application):
    return reverse("hiring:application_detail", args=[application.pk])


def test_htmx_move_out_of_the_tab_keeps_the_panel_with_a_note_and_the_same_filters(
    employee_client, employee
):
    job = make_job(title="Data Analyst")
    rejected = record(make_candidate(), job, employee)
    other = record(
        make_candidate(first_name="Bob", email="bob@example.com"), job, employee
    )
    # The Active tab (the default, so no tab parameter) with a search that
    # matches both applications.
    state = "jobs=open&q=example"

    response = employee_client.post(
        move_url(rejected, state), {"stage": Stage.REJECTED}, headers=HTMX
    )

    assert response.status_code == 200
    content = response.content.decode()
    assert Application.objects.get(pk=rejected.pk).stage == Stage.REJECTED
    # The panel still shows the rejected application, updated.
    assert "Applied → Rejected" in html.unescape(content)
    # It explains why the application has left the list.
    _, note = element(content, "unlisted-note")
    assert text(note) == (
        "This application is no longer in the list because it doesn't match "
        "the Active tab. Your tab and search haven't changed."
    )
    # The list drops it and keeps the other application, with links that keep
    # the same filter, tab and search.
    _, inner = element(content, "application-list")
    hrefs = re.findall(r'href="([^"]*)"', inner)
    assert [html.unescape(href) for href in hrefs] == [f"{detail_url(other)}?{state}"]
    # The Active tab stays selected, and the tabs and search keep the filter
    # and search instead of switching to where the application went.
    _, inner = element(content, "list-controls")
    selected_tabs = re.findall(r'<a role="tab"[^>]*tab-active[^>]*>(.*?)</a>', inner)
    assert [text(tab) for tab in selected_tabs] == ["Active 1"]
    tab_hrefs = re.findall(r'<a role="tab" href="([^"]*)"', inner)
    assert [html.unescape(href) for href in tab_hrefs] == [
        f"{detail_url(rejected)}?jobs=open&q=example",
        f"{detail_url(rejected)}?jobs=open&tab=finished&q=example",
        f"{detail_url(rejected)}?jobs=open&tab=all&q=example",
    ]
    assert 'name="q" value="example"' in inner
    assert 'name="tab"' not in inner
    assert '<input type="hidden" name="jobs" value="open">' in inner


def history(application):
    return list(application.history.values_list("pk", "old_stage", "new_stage"))


def test_refused_htmx_move_returns_the_panel_with_the_error_and_refreshed_actions(
    employee_client, employee
):
    application = record(make_candidate(), make_job(), employee)
    # Another tab rejected the application after this page loaded.
    services.move_application(application, Stage.REJECTED, changed_by=employee)
    before = history(application)
    state = "jobs=open&tab=all&q=doe"

    response = employee_client.post(
        move_url(application, state), {"stage": Stage.SCREENING}, headers=HTMX
    )

    assert response.status_code == 200
    content = response.content.decode()
    # A partial for the panel, and the browser stays on the application URL.
    assert "<!doctype html>" not in content
    for header in ["HX-Redirect", "HX-Push-Url", "HX-Replace-Url"]:
        assert header not in response.headers
    # The error explains why, in the panel.
    page = html.unescape(content)
    assert "That move wasn't made." in page
    assert (
        "A Rejected application reopens only to Applied, "
        "the stage it was in before that outcome." in page
    )
    # The actions match the stored stage, Rejected: only the reopen remains,
    # and it posts with the same filter, tab and search.
    move_forms = re.findall(
        r'<form method="post" action="([^"]*)".*?name="stage" value="(\w+)"',
        page,
        re.S,
    )
    assert move_forms == [(move_url(application, state), "applied")]
    assert "Reopen to Applied" in page
    # The list and tabs keep the same filter, tab and search.
    _, inner = element(content, "application-list")
    assert [html.unescape(h) for h in re.findall(r'href="([^"]*)"', inner)] == [
        f"{detail_url(application)}?{state}"
    ]
    _, inner = element(content, "list-controls")
    selected_tabs = re.findall(r'<a role="tab"[^>]*tab-active[^>]*>(.*?)</a>', inner)
    assert [text(tab) for tab in selected_tabs] == ["All 1"]
    assert 'name="q" value="doe"' in inner
    # Nothing changed.
    assert Application.objects.get(pk=application.pk).stage == Stage.REJECTED
    assert history(application) == before


@pytest.mark.parametrize(
    ("state", "excluded_by"),
    [
        ("jobs=open", "the Active tab"),
        ("jobs=open&tab=all&q=smith", "the search “smith”"),
        ("jobs=open&q=smith", "the Active tab or the search “smith”"),
    ],
    ids=["tab", "search", "tab-and-search"],
)
def test_full_page_explains_what_leaves_the_selection_out_of_the_list(
    employee_client, employee, state, excluded_by
):
    application = record(make_candidate(), make_job(), employee)
    services.move_application(application, Stage.REJECTED, changed_by=employee)

    # A normal request, as after a move without JavaScript or from a link.
    response = employee_client.get(f"{detail_url(application)}?{state}")

    content = response.content.decode()
    assert "<!doctype html>" in content
    _, note = element(content, "unlisted-note")
    assert text(note) == (
        f"This application is no longer in the list because it doesn't match "
        f"{excluded_by}. Your tab and search haven't changed."
    )


@pytest.mark.parametrize("state", ["jobs=open&tab=finished", "jobs=open&tab=all&q=doe"])
def test_no_note_when_the_selection_is_listed(employee_client, employee, state):
    application = record(make_candidate(), make_job(), employee)
    services.move_application(application, Stage.REJECTED, changed_by=employee)

    response = employee_client.get(f"{detail_url(application)}?{state}")

    assert element(response.content.decode(), "unlisted-note") == (None, "")


def panel_forms(content):
    """(action, hx attributes) of each form in the panel, in page order."""
    _, panel = element(content, "application-panel")
    forms = []
    for tag in re.findall(r"<form\b[^>]*>", panel):
        attrs = dict(re.findall(r'([\w-]+)="([^"]*)"', tag))
        forms.append({key: html.unescape(value) for key, value in attrs.items()})
    return forms


@pytest.mark.parametrize("stage", [Stage.APPLIED, Stage.REJECTED])
def test_panel_forms_post_through_htmx_to_their_normal_action_without_pushing(
    employee_client, employee, stage
):
    application = record(make_candidate(), make_job(), employee)
    if stage == Stage.REJECTED:
        # A finished application offers the reopen form.
        services.move_application(application, stage, changed_by=employee)
    state = "jobs=all&tab=all&q=doe"

    content = employee_client.get(f"{detail_url(application)}?{state}").content.decode()

    forms = panel_forms(content)
    details = reverse("hiring:application_details", args=[application.pk])
    actions = [form["action"] for form in forms]
    # Every move form, then the details form, keeps the filter, tab and search.
    assert set(actions[:-1]) == {move_url(application, state)}
    assert actions[-1] == f"{details}?{state}"
    for form in forms:
        # The normal action works without JavaScript; HTMX posts to the same
        # URL and replaces the whole panel, never recording the POST URL.
        assert form["method"] == "post"
        assert form["hx-post"] == form["action"]
        assert form["hx-target"] == "#application-panel"
        assert form["hx-swap"] == "outerHTML"
        assert "hx-push-url" not in form
        assert "hx-replace-url" not in form


@pytest.mark.parametrize(
    ("url_name", "data"),
    [
        ("hiring:application_move", {"stage": Stage.SCREENING}),
        ("hiring:application_details", {"applied_on": "2026-01-02", "notes": ""}),
    ],
    ids=["move", "details"],
)
def test_htmx_post_responses_replace_the_panel_element(
    employee_client, employee, url_name, data
):
    application = record(make_candidate(), make_job(), employee)
    url = f"{reverse(url_name, args=[application.pk])}?jobs=open"

    response = employee_client.post(url, data, headers=HTMX)

    content = response.content.decode()
    # outerHTML swaps need the panel element itself, ready for the next swap.
    attrs, _ = element(content, "application-panel")
    assert attrs is not None
    assert "hx-swap-oob" not in attrs
    for header in ["HX-Redirect", "HX-Push-Url", "HX-Replace-Url"]:
        assert header not in response.headers
    vary = {value.strip().lower() for value in response["Vary"].split(",")}
    assert {"hx-request", "hx-history-restore-request"} <= vary


# Application details: applied-on date and notes


def details_url(application, query="jobs=open"):
    url = reverse("hiring:application_details", args=[application.pk])
    return f"{url}?{query}" if query else url


def test_htmx_details_save_updates_the_panel_and_writes_no_history(
    employee_client, employee
):
    application = record(make_candidate(), make_job(), employee)
    services.move_application(application, Stage.SCREENING, changed_by=employee)
    before = history(application)
    applied_on = timezone.localdate() - timedelta(days=3)

    response = employee_client.post(
        details_url(application),
        {"applied_on": applied_on.isoformat(), "notes": "  Strong portfolio.  "},
        headers=HTMX,
    )

    assert response.status_code == 200
    content = response.content.decode()
    assert "<!doctype html>" not in content
    stored = Application.objects.get(pk=application.pk)
    assert stored.applied_on == applied_on
    assert stored.notes == "Strong portfolio."
    assert stored.stage == Stage.SCREENING
    assert history(application) == before
    # The panel confirms the save and shows the stored values.
    _, panel = element(content, "application-panel")
    assert "Details saved." in panel
    assert f'value="{applied_on.isoformat()}"' in panel
    assert "Strong portfolio.</textarea>" in panel
    assert f"{applied_on:%b} {applied_on.day}, {applied_on.year}" in text(panel)


def test_htmx_future_applied_on_date_shows_an_inline_error_and_saves_nothing(
    employee_client, employee
):
    application = record(make_candidate(), make_job(), employee)
    application.notes = "Original notes."
    application.save(update_fields=["notes"])
    before = history(application)
    today = timezone.localdate()
    tomorrow = today + timedelta(days=1)

    response = employee_client.post(
        details_url(application),
        {"applied_on": tomorrow.isoformat(), "notes": "Changed notes."},
        headers=HTMX,
    )

    assert response.status_code == 200
    content = response.content.decode()
    assert "<!doctype html>" not in content
    _, form = element(content, "details-form")
    # The error sits beside the field, and what was typed is kept.
    assert "The applied-on date can&#x27;t be in the future." in form
    assert f'value="{tomorrow.isoformat()}"' in form
    assert "Changed notes.</textarea>" in form
    _, panel = element(content, "application-panel")
    assert "Details saved." not in panel
    # Outside the form, the panel shows the stored date.
    assert f"{today:%b} {today.day}, {today.year}" in text(panel)
    stored = Application.objects.get(pk=application.pk)
    assert (stored.applied_on, stored.notes) == (today, "Original notes.")
    assert history(application) == before


def test_details_save_without_javascript_redirects_keeping_the_filters(
    employee_client, employee
):
    application = record(make_candidate(), make_job(), employee)
    before = history(application)

    response = employee_client.post(
        details_url(application, "jobs=all&tab=all&q=doe"),
        {"applied_on": timezone.localdate().isoformat(), "notes": "Called back."},
    )

    assert response.status_code == 302
    assert response.url == f"{detail_url(application)}?jobs=all&tab=all&q=doe"
    assert Application.objects.get(pk=application.pk).notes == "Called back."
    assert history(application) == before


def test_invalid_details_save_without_javascript_shows_the_full_page_with_the_error(
    employee_client, employee
):
    application = record(make_candidate(), make_job(), employee)
    before = history(application)
    tomorrow = timezone.localdate() + timedelta(days=1)

    response = employee_client.post(
        details_url(application), {"applied_on": tomorrow.isoformat(), "notes": ""}
    )

    assert response.status_code == 200
    content = response.content.decode()
    assert "<!doctype html>" in content
    _, form = element(content, "details-form")
    assert "The applied-on date can&#x27;t be in the future." in form
    assert Application.objects.get(pk=application.pk).applied_on == (
        timezone.localdate()
    )
    assert history(application) == before


def test_details_save_keeps_a_stage_change_made_after_the_application_loaded(
    employee_client, employee, monkeypatch
):
    application = record(make_candidate(), make_job(), employee)
    original_clean = ApplicationDetailsForm.clean

    def clean_during_a_concurrent_move(form):
        # Another request moves the application after this one loaded it.
        services.move_application(
            Application.objects.get(pk=application.pk),
            Stage.SCREENING,
            changed_by=employee,
        )
        return original_clean(form)

    monkeypatch.setattr(ApplicationDetailsForm, "clean", clean_during_a_concurrent_move)

    employee_client.post(
        details_url(application),
        {"applied_on": timezone.localdate().isoformat(), "notes": "Saved."},
        headers=HTMX,
    )

    stored = Application.objects.get(pk=application.pk)
    assert stored.notes == "Saved."
    # The details save didn't put back the Applied stage it loaded.
    assert stored.stage == Stage.SCREENING
    assert_stage_matches_history()


def test_details_save_ignores_candidate_job_and_stage_fields(employee_client, employee):
    application = record(make_candidate(), make_job(), employee)
    other_candidate = make_candidate(email="other@example.com")
    other_job = make_job(title="Other")
    before = history(application)

    employee_client.post(
        details_url(application),
        {
            "applied_on": timezone.localdate().isoformat(),
            "notes": "",
            "candidate": other_candidate.pk,
            "job": other_job.pk,
            "stage": Stage.HIRED,
        },
        headers=HTMX,
    )

    stored = Application.objects.get(pk=application.pk)
    assert (stored.candidate_id, stored.job_id, stored.stage) == (
        application.candidate_id,
        application.job_id,
        Stage.APPLIED,
    )
    assert history(application) == before


def test_details_view_requires_post(employee_client, employee):
    application = record(make_candidate(), make_job(), employee)

    response = employee_client.get(details_url(application))

    assert response.status_code == 405
