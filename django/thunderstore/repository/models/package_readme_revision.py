from django.conf import settings
from django.db import models

class PackageReadmeRevisionSource(models.TextChoices):
    WEB_UI = "WEB_UI", "Web UI"
    ZIP_UPLOAD = "ZIP_UPLOAD", "Zip Upload"

class PackageReadmeRevision(models.Model):
    package = models.ForeignKey(
        "repository.Package",
        related_name="readme_revisions",
        on_delete=models.CASCADE,
    )
    content = models.TextField(blank=True, default="")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    source = models.CharField(
        max_length=32,
        choices=PackageReadmeRevisionSource.choices,
        default=PackageReadmeRevisionSource.WEB_UI,
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.package.full_package_name} - {self.created_at.isoformat()}"
