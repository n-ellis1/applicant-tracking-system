import pytest
from django.contrib.auth.models import User


@pytest.fixture
def employee_client(client, db):
    client.force_login(User.objects.create_user(username="employee", password="pw"))
    return client
