import pytest

from thunderstore.repository.factories import PackageFactory, PackageVersionFactory
from thunderstore.account.factories import UserFactory
from thunderstore.repository.models.package_readme_revision import (
    PackageReadmeRevision,
    PackageReadmeRevisionSource,
)


@pytest.mark.django_db
def test_package_handle_created_version_sync_true():
    package = PackageFactory(sync_markdown_from_zip=True, readme="", changelog="")
    
    # Simulating uploading a new version which triggers handle_created_version
    # (actually PackageVersion.post_save calls it)
    version = PackageVersionFactory(package=package, readme="Zip Readme", changelog="Zip Changelog")
    
    package.refresh_from_db()

    assert package.readme == "Zip Readme"
    assert package.changelog == "Zip Changelog"
    
    revision = PackageReadmeRevision.objects.get(package=package)
    assert revision.content == "Zip Readme"
    assert revision.source == PackageReadmeRevisionSource.ZIP_UPLOAD


@pytest.mark.django_db
def test_package_handle_created_version_sync_false():
    package = PackageFactory(sync_markdown_from_zip=False, readme="Custom Readme", changelog="Custom Changelog")
    
    version = PackageVersionFactory(package=package, readme="Zip Readme", changelog="Zip Changelog")
    
    package.refresh_from_db()

    assert package.readme == "Custom Readme"
    assert package.changelog == "Custom Changelog"
    
    # Should not create a revision
    assert PackageReadmeRevision.objects.filter(package=package).count() == 0
