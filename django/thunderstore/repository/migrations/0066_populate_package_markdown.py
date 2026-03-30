# Generated manually
from django.db import migrations, models

def populate_package_markdown(apps, schema_editor):
    Package = apps.get_model("repository", "Package")
    PackageReadmeRevision = apps.get_model("repository", "PackageReadmeRevision")

    # Iterate over packages that have a latest version
    # Since we can't use complex methods, we do it safely:
    packages_to_update = []
    revisions_to_create = []

    # Using iterator for memory efficiency if there are many packages
    for package in Package.objects.select_related("latest", "latest__uploaded_by").iterator(chunk_size=1000):
        if package.latest:
            package.readme = package.latest.readme
            package.changelog = package.latest.changelog or ""
            packages_to_update.append(package)

            revisions_to_create.append(
                PackageReadmeRevision(
                    package=package,
                    content=package.latest.readme,
                    author=package.latest.uploaded_by,
                    source="ZIP_UPLOAD",
                )
            )

            if len(packages_to_update) >= 1000:
                Package.objects.bulk_update(packages_to_update, ["readme", "changelog"])
                PackageReadmeRevision.objects.bulk_create(revisions_to_create)
                packages_to_update = []
                revisions_to_create = []

    if packages_to_update:
        Package.objects.bulk_update(packages_to_update, ["readme", "changelog"])
        PackageReadmeRevision.objects.bulk_create(revisions_to_create)

class Migration(migrations.Migration):

    dependencies = [
        ("repository", "0065_package_readme_revisions"),
    ]

    operations = [
        migrations.RunPython(populate_package_markdown, migrations.RunPython.noop),
    ]
