import gzip
import io
from hashlib import sha256

from django.core.files.base import ContentFile
from django.db import models

from thunderstore.core.storage import get_schema_storage
from django.utils import timezone

from thunderstore.core.mixins import S3FileMixin


def get_schema_file_path(_, filename: str) -> str:
    return f"schema/sha256/{filename}"


class SchemaFile(S3FileMixin):
    data = models.FileField(
        # Default FileField max_length (100) truncates the content-addressed
        # path under django-storages 1.14 (which now enforces max_length).
        max_length=255,
        upload_to=get_schema_file_path,
        storage=get_schema_storage,
        editable=False,
        blank=True,
        null=True,
    )
    checksum_sha256 = models.CharField(
        max_length=512,
        editable=False,
        null=False,
        unique=True,
        db_index=True,
    )
    file_size = models.PositiveIntegerField()
    gzip_size = models.PositiveBigIntegerField()

    @classmethod
    def get_or_create(cls, content: bytes) -> "SchemaFile":
        hash = sha256()
        hash.update(content)
        checksum = hash.hexdigest()

        if existing := cls.objects.filter(checksum_sha256=checksum).first():
            return existing

        gzipped = io.BytesIO()
        with gzip.GzipFile(fileobj=gzipped, mode="wb") as f:
            f.write(content)
        timestamp = timezone.now()

        file = ContentFile(
            # TODO: This is immediately passed to BytesIO again, meaning
            #       we're just wasting memory. Find a way to pass this to
            #       the Django model without the inefficiency.
            gzipped.getvalue(),
            name=f"{checksum}.json.gz",
        )
        return cls.objects.create(
            data=file,
            content_type="application/json",
            content_encoding="gzip",
            last_modified=timestamp,
            checksum_sha256=checksum,
            file_size=len(content),
            gzip_size=file.size,
        )
