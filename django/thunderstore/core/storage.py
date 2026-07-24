from typing import IO, Any, Dict, Optional, TypedDict

from django.conf import settings
from django.core.files.storage import Storage, storages
from django.utils.deconstruct import deconstructible
from storages.backends.s3boto3 import S3Boto3Storage  # type: ignore

from thunderstore.utils.contexts import TemporarySpooledCopy


# Model FileFields reference these callables as their `storage` argument. Django
# serializes a callable storage by import path, so migrations stay stable across
# environments regardless of which backend STORAGES resolves to at runtime. This
# replaces the old get_storage_class(settings.X_FILE_STORAGE)() + StubStorage
# makemigrations workaround, which is no longer possible after Django 5.1 removed
# get_storage_class and the *_FILE_STORAGE settings.
def get_package_storage() -> Storage:
    return storages["package"]


def get_modpack_storage() -> Storage:
    return storages["modpack"]


def get_schema_storage() -> Storage:
    return storages["schema"]


def get_blob_storage() -> Storage:
    return storages["blob"]


class S3MirrorConfig(TypedDict):
    access_key: str
    secret_key: str
    region_name: str
    bucket_name: str
    location: str
    custom_domain: str
    endpoint_url: str
    url_protocol: str  # django-storages 1.14: replaces the secure_urls bool
    file_overwrite: bool
    default_acl: str
    object_parameters: Dict


@deconstructible
class MirroredS3Storage(S3Boto3Storage):
    @property
    def mirrors(self):
        for mirror in settings.S3_MIRRORS:
            yield S3Boto3Storage(**mirror)

    def save(
        self, name: str, content: IO[Any], max_length: Optional[int] = None
    ) -> str:
        """
        Upload file to main S3 storage and all mirrors.

        Calling .save() closes the file, so use temporary copies for
        mirrors and call the main bucket with the actual file last.
        """
        for storage_mirror in self.mirrors:
            with TemporarySpooledCopy(content) as tmp_content:
                storage_mirror.save(name, tmp_content, max_length)

        return super().save(name, content, max_length)

    def delete(self, name: str) -> None:
        """
        Delete file from main S3 storage and all mirrors.
        """
        super().delete(name)

        for storage_mirror in self.mirrors:
            storage_mirror.delete(name)
