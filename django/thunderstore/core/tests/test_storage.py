import pytest
from django.core.files.storage import default_storage
from PIL import Image  # type: ignore

from thunderstore.repository.factories import PackageVersionFactory
from thunderstore.repository.models.package_version import get_version_png_filepath


@pytest.mark.django_db
def test_mirrored_storage(settings, dummy_image: Image) -> None:
    # Point the "default" storage (used by the package icon) at MirroredS3Storage.
    # Assigning via the settings fixture emits setting_changed, which resets the
    # storages handler + default_storage so the new backend takes effect.
    settings.STORAGES = {
        **settings.STORAGES,
        "default": {"BACKEND": "thunderstore.core.storage.MirroredS3Storage"},
    }
    settings.S3_MIRRORS = (
        {
            "access_key": "thunderstore",
            "secret_key": "thunderstore",
            "region_name": "",
            "bucket_name": "test",
            "location": "test",
            "custom_domain": "localhost:9000/thunderstore",
            "endpoint_url": "http://minio:9000/",
            "url_protocol": "http:",
            "file_overwrite": True,
            "default_acl": "",
            "object_parameters": {},
        },
    )

    pv = PackageVersionFactory(icon=None, name="MirrorStorageTest")
    icon_path = get_version_png_filepath(pv, "")

    assert hasattr(default_storage, "mirrors")
    assert not default_storage.exists(icon_path)
    for mirror_storage in default_storage.mirrors:
        assert not mirror_storage.exists(icon_path)

    pv.icon = dummy_image
    pv.save()
    assert default_storage.exists(icon_path)
    for mirror_storage in default_storage.mirrors:
        assert mirror_storage.exists(icon_path)

    pv.icon.delete()
    assert not default_storage.exists(icon_path)
    for mirror_storage in default_storage.mirrors:
        assert not mirror_storage.exists(icon_path)
