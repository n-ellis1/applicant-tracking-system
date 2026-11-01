import pytest
from django.contrib.auth.models import User
from django.urls import reverse

PASSWORD = "correct-horse-battery"


@pytest.fixture
def employee(db):
    return User.objects.create_user(username="employee", password=PASSWORD)


@pytest.mark.parametrize(
    "url_name",
    [
        "hiring:pipeline",
        "hiring:candidate_list",
        "hiring:job_list",
        "hiring:skill_list",
    ],
)
@pytest.mark.django_db
def test_every_hiring_page_redirects_anonymous_visitors_to_login(client, url_name):
    url = reverse(url_name)

    response = client.get(url)

    assert response.status_code == 302
    assert response.url == f"{reverse('login')}?next={url}"


@pytest.mark.django_db
def test_login_page_is_reachable_while_signed_out(client):
    response = client.get(reverse("login"))

    assert response.status_code == 200
    assert b'name="username"' in response.content


def test_active_employee_signs_in_and_lands_on_pipeline(client, employee):
    response = client.post(
        reverse("login"), {"username": "employee", "password": PASSWORD}
    )

    assert response.status_code == 302
    assert response.url == reverse("hiring:pipeline")
    assert client.get(reverse("hiring:pipeline")).status_code == 200


def test_sign_in_returns_to_the_requested_page(client, employee):
    response = client.post(
        reverse("login"),
        {"username": "employee", "password": PASSWORD, "next": "/candidates/"},
    )

    assert response.url == "/candidates/"


def test_inactive_account_cannot_sign_in(client, employee):
    employee.is_active = False
    employee.save()

    response = client.post(
        reverse("login"), {"username": "employee", "password": PASSWORD}
    )

    assert response.status_code == 200
    assert response.context["form"].non_field_errors()
    assert "_auth_user_id" not in client.session


def test_regular_employee_cannot_use_admin(client, employee):
    assert not employee.is_staff and not employee.is_superuser
    client.force_login(employee)

    response = client.get(reverse("admin:index"))

    assert response.status_code == 302
    assert response.url.startswith(reverse("admin:login"))


def test_superuser_can_use_admin(client, db):
    admin_user = User.objects.create_superuser(username="admin", password=PASSWORD)
    client.force_login(admin_user)

    assert client.get(reverse("admin:index")).status_code == 200


def test_log_out_by_post_returns_to_login_and_ends_the_session(client, employee):
    client.force_login(employee)

    response = client.post(reverse("logout"))

    assert response.status_code == 302
    assert response.url == reverse("login")
    assert client.get(reverse("hiring:pipeline")).status_code == 302


def test_log_out_by_get_is_not_allowed(client, employee):
    client.force_login(employee)

    response = client.get(reverse("logout"))

    assert response.status_code == 405
    assert client.get(reverse("hiring:pipeline")).status_code == 200


def test_nav_shows_links_username_and_log_out_form(client, employee):
    client.force_login(employee)

    content = client.get(reverse("hiring:pipeline")).content.decode()

    for url_name in ["hiring:candidate_list", "hiring:job_list", "hiring:skill_list"]:
        assert f'href="{reverse(url_name)}"' in content
    assert "employee" in content
    assert f'<form method="post" action="{reverse("logout")}">' in content


def test_pages_use_the_dark_theme(client, employee):
    assert b'data-theme="dark"' in client.get(reverse("login")).content
    client.force_login(employee)
    assert b'data-theme="dark"' in client.get(reverse("hiring:pipeline")).content
