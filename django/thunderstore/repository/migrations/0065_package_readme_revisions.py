# Generated manually
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("repository", "0064_add_namespaces_for_existing_teams"),
    ]

    operations = [
        migrations.AddField(
            model_name="package",
            name="changelog",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="package",
            name="readme",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="package",
            name="sync_markdown_from_zip",
            field=models.BooleanField(default=True),
        ),
        migrations.CreateModel(
            name="PackageReadmeRevision",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("content", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("source", models.CharField(choices=[("WEB_UI", "Web UI"), ("ZIP_UPLOAD", "Zip Upload")], default="WEB_UI", max_length=32)),
                ("author", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ("package", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="readme_revisions", to="repository.package")),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]
