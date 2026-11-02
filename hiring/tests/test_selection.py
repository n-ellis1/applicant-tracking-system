import html
import re
from html.parser import HTMLParser
from urllib.parse import quote

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

from hiring import services
from hiring.tests.helpers import make_candidate, make_job


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


def app_url(application):
    return reverse("hiring:application_detail", args=[application.pk])


VOID_TAGS = {"br", "hr", "img", "input", "link", "meta"}


class _LinksInside(HTMLParser):
    """Collects the attributes of each link inside the element with an id."""

    def __init__(self, element_id):
        super().__init__()
        self.element_id = element_id
        self.depth = 0
        self.element = None
        self.links = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if self.depth:
            if tag == "a":
                self.links.append(attrs)
            if tag not in VOID_TAGS:
                self.depth += 1
        elif attrs.get("id") == self.element_id:
            self.element = attrs
            self.depth = 1

    def handle_endtag(self, tag):
        if self.depth and tag not in VOID_TAGS:
            self.depth -= 1


def links_inside(content, element_id):
    """The element's own attributes and the attributes of its links."""
    parser = _LinksInside(element_id)
    parser.feed(content)
    return parser.element, parser.links


# Selecting an application through HTMX


@pytest.mark.parametrize(
    ("headers", "full_page"),
    [
        ({}, True),
        ({"HX-Request": "true"}, False),
        # A history-cache miss restores the whole page from the server.
        ({"HX-Request": "true", "HX-History-Restore-Request": "true"}, True),
    ],
    ids=["normal", "htmx", "history-restore"],
)
def test_selection_returns_the_panel_for_htmx_and_the_full_page_otherwise(
    employee_client, employee, headers, full_page
):
    application = record(make_candidate(), make_job(title="Data Analyst"), employee)

    response = employee_client.get(f"{app_url(application)}?jobs=open", headers=headers)

    assert response.status_code == 200
    content = response.content.decode()
    # The selected application's details are there either way.
    assert "jane.doe@example.com" in content
    assert "Stage history" in content
    # Only the full page has the document, nav and jobs sidebar.
    assert ("<!doctype html>" in content) is full_page
    assert ('aria-label="Jobs"' in content) is full_page


def test_htmx_selection_highlights_only_the_new_application_out_of_band(
    employee_client, employee
):
    job = make_job(title="Data Analyst")
    first = record(make_candidate(email="ann@example.com"), job, employee)
    second = record(make_candidate(email="bob@example.com"), job, employee)
    third = record(make_candidate(email="cy@example.com"), job, employee)

    # The server doesn't know which application was highlighted before, so
    # it re-renders the whole list with the new selection.
    response = employee_client.get(
        f"{app_url(second)}?jobs=open", headers={"HX-Request": "true"}
    )

    # The panel element itself replaces the old one (outerHTML).
    panel, _ = links_inside(response.content.decode(), "application-panel")
    assert panel is not None
    assert "hx-swap-oob" not in panel
    element, links = links_inside(response.content.decode(), "application-list")
    # The list comes back as an out-of-band swap beside the panel.
    assert element is not None
    assert element.get("hx-swap-oob") == "true"
    # Every application is listed, and only the new selection is highlighted.
    assert sorted(link["href"] for link in links) == sorted(
        f"{app_url(application)}?jobs=open" for application in [first, second, third]
    )
    highlighted = [link["href"] for link in links if link.get("aria-current")]
    assert highlighted == [f"{app_url(second)}?jobs=open"]
    assert all(
        "menu-active" in link.get("class", "")
        for link in links
        if link.get("aria-current")
    )
    assert not any(
        "menu-active" in link.get("class", "")
        for link in links
        if not link.get("aria-current")
    )


def test_selection_links_load_into_the_panel_and_push_their_own_url(
    employee_client, employee
):
    job = make_job(title="Data Analyst")
    selected = record(make_candidate(last_name="Lee"), job, employee)
    neighbour = record(
        make_candidate(last_name="Leeds", email="leeds@example.com"), job, employee
    )
    state = "jobs=all&tab=all&q=lee"

    content = employee_client.get(f"{app_url(selected)}?{state}").content.decode()

    _, links = links_inside(content, "application-list")
    assert sorted(link["href"] for link in links) == sorted(
        f"{app_url(application)}?{state}" for application in [selected, neighbour]
    )
    for link in links:
        # The normal link still works without JavaScript. HTMX loads the same
        # URL into the panel and pushes it, so Back, Forward and refresh land
        # on the same view.
        assert link.get("hx-get") == link["href"]
        assert link.get("hx-target") == "#application-panel"
        assert link.get("hx-swap") == "outerHTML"
        assert link.get("hx-push-url") == "true"
    # The target exists on the page.
    panel, _ = links_inside(content, "application-panel")
    assert panel is not None


def test_htmx_selection_list_keeps_the_filter_tab_and_search(employee_client, employee):
    job = make_job(title="Data Analyst")
    selected = record(make_candidate(last_name="Lee"), job, employee)
    neighbour = record(
        make_candidate(last_name="Leeds", email="leeds@example.com"), job, employee
    )
    record(make_candidate(last_name="Smith", email="smith@example.com"), job, employee)
    state = "jobs=all&tab=all&q=lee"

    response = employee_client.get(
        f"{app_url(selected)}?{state}", headers={"HX-Request": "true"}
    )

    # Only the search matches are listed, and their links keep the state.
    _, links = links_inside(response.content.decode(), "application-list")
    assert sorted(link["href"] for link in links) == sorted(
        f"{app_url(application)}?{state}" for application in [selected, neighbour]
    )


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"HX-Request": "true"},
        {"HX-Request": "true", "HX-History-Restore-Request": "true"},
    ],
    ids=["normal", "htmx", "history-restore"],
)
def test_selection_responses_vary_on_both_htmx_headers(
    employee_client, employee, headers
):
    application = record(make_candidate(), make_job(), employee)

    response = employee_client.get(app_url(application), headers=headers)

    # Either header changes whether the URL returns the panel or the full
    # page, so a cache must never serve one for the other.
    vary = {value.strip().lower() for value in response["Vary"].split(",")}
    assert {"hx-request", "hx-history-restore-request"} <= vary


def test_htmx_selection_updates_the_controls_that_follow_the_selection(
    employee_client, employee
):
    job = make_job(title="Data Analyst")
    record(make_candidate(last_name="Lee"), job, employee)
    selected = record(
        make_candidate(last_name="Leeds", email="leeds@example.com"), job, employee
    )
    # The Closed filter hides this open job, so the sidebar shows its note.
    state = "jobs=closed&tab=all&q=lee"
    here = f"{app_url(selected)}?{state}"

    content = employee_client.get(here, headers={"HX-Request": "true"}).content.decode()

    # Sidebar filter links and the hidden-job note target the new selection.
    element, links = links_inside(content, "job-filter")
    assert element.get("hx-swap-oob") == "true"
    assert [link["href"] for link in links] == [
        f"{app_url(selected)}?jobs={value}&tab=all&q=lee"
        for value in ["open", "closed", "all", "all"]
    ]
    # Tabs and search target the new selection.
    element, links = links_inside(content, "list-controls")
    assert element.get("hx-swap-oob") == "true"
    assert [link["href"] for link in links] == [
        f"{app_url(selected)}?jobs=closed&q=lee",
        f"{app_url(selected)}?jobs=closed&tab=finished&q=lee",
        f"{app_url(selected)}?jobs=closed&tab=all&q=lee",
    ]
    assert f'action="{app_url(selected)}" role="search"' in content
    # Close job returns to the new selection.
    element, links = links_inside(content, "job-controls")
    assert element.get("hx-swap-oob") == "true"
    close_url = reverse("hiring:job_close", args=[job.pk])
    assert f"{close_url}?next={quote(here)}" in [link["href"] for link in links]


def test_htmx_selection_reopen_job_returns_to_the_new_selection(
    employee_client, employee
):
    job = make_job(title="Data Analyst")
    selected = record(make_candidate(), job, employee)
    services.close_job(job)
    here = f"{app_url(selected)}?jobs=closed&tab=all"

    content = employee_client.get(here, headers={"HX-Request": "true"}).content.decode()

    controls = content.split('id="job-controls"', 1)[1]
    assert f'name="next" value="{html.escape(here)}"' in controls


def test_htmx_selection_title_matches_the_full_page(employee_client, employee):
    application = record(make_candidate(), make_job(title="Data Analyst"), employee)
    url = f"{app_url(application)}?jobs=open"

    full = employee_client.get(url).content.decode()
    partial = employee_client.get(url, headers={"HX-Request": "true"}).content.decode()

    title = re.compile(r"<title>(.*?)</title>", re.S)
    assert title.search(full).group(1) == "Jane Doe · Data Analyst · Applicant Tracking"
    assert title.search(partial).group(1) == title.search(full).group(1)
