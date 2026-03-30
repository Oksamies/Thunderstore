import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from thunderstore.repository.factories import PackageFactory, PackageVersionFactory
from thunderstore.account.factories import UserFactory
from thunderstore.repository.models.package_readme_revision import (
    PackageReadmeRevision,
    PackageReadmeRevisionSource,
)

@pytest.fixture
def package_to_update():
    user = UserFactory()
    package = PackageFactory(owner__members=[user])
    PackageVersionFactory(package=package)  # Ensure it has a latest version
    return package, user


@pytest.mark.django_db
def test_package_update_unauthenticated(api_client: APIClient, package_to_update) -> None:
    package, _ = package_to_update
    url = reverse(
        "cyberstorm.package.update",
        kwargs={"namespace_id": package.namespace.name, "package_name": package.name},
    )
    response = api_client.patch(url, {"readme": "New readme content"})

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_package_update_unauthorized(api_client: APIClient, package_to_update) -> None:
    package, _ = package_to_update
    random_user = UserFactory()
    api_client.force_authenticate(user=random_user)

    url = reverse(
        "cyberstorm.package.update",
        kwargs={"namespace_id": package.namespace.name, "package_name": package.name},
    )
    response = api_client.patch(url, {"readme": "New readme content"})

    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_package_update_success(api_client: APIClient, package_to_update) -> None:
    package, user = package_to_update
    api_client.force_authenticate(user=user)

    url = reverse(
        "cyberstorm.package.update",
        kwargs={"namespace_id": package.namespace.name, "package_name": package.name},
    )

    new_readme = "# Hello World"
    new_changelog = "- Added features"

    response = api_client.patch(url, {"readme": new_readme, "changelog": new_changelog})

    assert response.status_code == status.HTTP_200_OK

    package.refresh_from_db()
    assert package.readme == new_readme
    assert package.changelog == new_changelog
    assert package.sync_markdown_from_zip is False

    # Check that a revision was created
    revision = PackageReadmeRevision.objects.get(package=package)
    assert revision.content == new_readme
    assert revision.author == user
    assert revision.source == PackageReadmeRevisionSource.WEB_UI
