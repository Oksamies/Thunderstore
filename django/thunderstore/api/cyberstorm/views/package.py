from django.shortcuts import get_object_or_404
from rest_framework import permissions
from rest_framework.generics import UpdateAPIView

from thunderstore.api.cyberstorm.serializers.package import PackageUpdateSerializer
from thunderstore.api.utils import CyberstormAutoSchemaMixin
from thunderstore.repository.models import Package
from thunderstore.repository.models.package_readme_revision import (
    PackageReadmeRevision,
    PackageReadmeRevisionSource,
)


class PackageUpdateAPIView(CyberstormAutoSchemaMixin, UpdateAPIView):
    serializer_class = PackageUpdateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        package = get_object_or_404(
            Package,
            namespace__name=self.kwargs["namespace_id"],
            name=self.kwargs["package_name"],
        )
        
        # Ensure user has authority to manage this package
        package.owner.ensure_user_can_manage_packages(self.request.user)
        
        return package

    def perform_update(self, serializer):
        package = serializer.save(sync_markdown_from_zip=False)
        
        if "readme" in serializer.validated_data:
            PackageReadmeRevision.objects.create(
                package=package,
                content=package.readme,
                author=self.request.user,
                source=PackageReadmeRevisionSource.WEB_UI,
            )
