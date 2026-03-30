from typing import Optional

from django.http import Http404
from rest_framework import serializers
from rest_framework.generics import RetrieveAPIView, get_object_or_404

from thunderstore.api.utils import CyberstormAutoSchemaMixin, PublicCacheMixin
from thunderstore.markdown.templatetags.markdownify import render_markdown
from thunderstore.repository.models import Package, PackageVersion


class CyberstormMarkdownResponseSerializer(serializers.Serializer):
    html = serializers.CharField()


class PackageVersionReadmeAPIView(
    PublicCacheMixin, CyberstormAutoSchemaMixin, RetrieveAPIView
):
    """
    Return README.md prerendered as HTML.

    If no version number is provided, the latest version is used.
    """

    serializer_class = CyberstormMarkdownResponseSerializer

    def get_object(self):
        package, package_version = get_package_and_version(
            namespace_id=self.kwargs["namespace_id"],
            package_name=self.kwargs["package_name"],
            version_number=self.kwargs.get("version_number"),
        )
        
        readme_content = package_version.readme if package_version else package.readme

        return {"html": render_markdown(readme_content)}


class PackageVersionChangelogAPIView(
    PublicCacheMixin, CyberstormAutoSchemaMixin, RetrieveAPIView
):
    """
    Return CHANGELOG.md prerendered as HTML.

    If no version number is provided, the latest version is used.
    """

    serializer_class = CyberstormMarkdownResponseSerializer

    cache_404s = True

    def get_object(self):
        package, package_version = get_package_and_version(
            namespace_id=self.kwargs["namespace_id"],
            package_name=self.kwargs["package_name"],
            version_number=self.kwargs.get("version_number"),
        )
        
        if package_version:
            changelog_content = package_version.changelog
        else:
            # Dynamic changelog aggregation for /latest/
            versions = package.versions.active().order_by("-date_created")
            changelogs = []
            for v in versions:
                if v.changelog:
                    changelogs.append(f"# Version {v.version_number}\n\n{v.changelog}\n\n")
            changelog_content = "".join(changelogs) if changelogs else package.changelog

        if not changelog_content:
            raise Http404

        return {"html": render_markdown(changelog_content)}


def get_package_and_version(
    namespace_id: str,
    package_name: str,
    version_number: Optional[str],
) -> tuple[Package, Optional[PackageVersion]]:
    package = get_object_or_404(
        Package.objects.active().select_related("latest"),
        namespace__name=namespace_id,
        name=package_name,
    )

    if version_number:
        version = get_object_or_404(
            package.versions.active(),
            version_number=version_number,
        )
        return package, version

    if package.latest and package.latest.is_active:
        return package, None

    raise Http404
