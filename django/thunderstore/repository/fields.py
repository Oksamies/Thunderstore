from django.db import models


class CICharField(models.CharField):
    """Case-insensitive CharField backed by the PostgreSQL ``citext`` type.

    Vendored replacement for ``django.contrib.postgres.fields.CICharField``,
    which was removed in Django 5.1. The existing columns are already ``citext``
    (created via CITextExtension in migration 0028), so mapping to the same
    database type preserves their case-insensitive comparison and uniqueness
    with no data migration. Everything else behaves as a normal CharField.
    """

    def db_type(self, connection):
        return "citext"
