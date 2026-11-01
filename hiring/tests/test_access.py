import pytest
from django.contrib.auth.models import User
from django.urls import reverse


@pytest.mark.django_db
def test_anonymous_visitor_is_redirected_to_login(client):
    url = reverse("hiring:candidate_list")

    response = client.get(url)

    assert response.status_code == 302
    assert response.url == f"{reverse('login')}?next={url}"


@pytest.mark.django_db
def test_deactivated_users_existing_session_is_refused(client):
    employee = User.objects.create_user(username="employee", password="pw")
    client.force_login(employee)
    url = reverse("hiring:candidate_list")
    assert client.get(url).status_code == 200

    employee.is_active = False
    employee.save()
    response = client.get(url)

    assert response.status_code == 302
    assert response.url == f"{reverse('login')}?next={url}"
