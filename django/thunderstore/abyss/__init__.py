"""Compatibility shim applied before the abyss package is imported.

The abyss dependency (github.com/akx/abyss) is unmaintained and still imports
``django.core.files.storage.get_storage_class``, which Django 5.1 removed. This
package ``__init__`` runs before ``thunderstore.abyss.middleware`` (the module
that triggers the abyss import), so re-adding a compatible shim here lets the
abyss middleware load unchanged.
"""
import django.core.files.storage
from django.utils.module_loading import import_string

if not hasattr(django.core.files.storage, "get_storage_class"):

    def get_storage_class(import_path=None):
        # Mirror the removed Django helper: import and return the object at
        # import_path (abyss then calls it), defaulting to the configured
        # default storage's class.
        if import_path is None:
            from django.core.files.storage import default_storage

            return default_storage.__class__
        return import_string(import_path)

    django.core.files.storage.get_storage_class = get_storage_class
