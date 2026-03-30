from typing import Optional

from rest_framework import serializers

from thunderstore.api.cyberstorm.serializers.community import (
    CyberstormPackageCategorySerializer,
)
from thunderstore.api.cyberstorm.serializers.team import CyberstormTeamMemberSerializer
from thunderstore.community.models import Community
from thunderstore.repository.models import Namespace, Package, PackageVersion


class PackageInfoSerializer(serializers.Serializer):
    community_id = serializers.CharField()
    namespace_id = serializers.CharField()
    package_name = serializers.CharField()


class PermissionsSerializer(serializers.Serializer):
    can_manage = serializers.BooleanField()
    can_manage_wiki = serializers.BooleanField()
    can_manage_deprecation = serializers.BooleanField()
    can_manage_categories = serializers.BooleanField()
    can_deprecate = serializers.BooleanField()
    can_undeprecate = serializers.BooleanField()
    can_unlist = serializers.BooleanField()
    can_moderate = serializers.BooleanField()
    can_view_package_admin_page = serializers.BooleanField()
    can_view_listing_admin_page = serializers.BooleanField()


class PackagePermissionsSerializer(serializers.Serializer):
    package = PackageInfoSerializer()
    permissions = PermissionsSerializer()


class CyberstormPackagePreviewSerializer(serializers.Serializer):
    """
    Data shown on "PackageCard" component on frontend.
    """

    categories = CyberstormPackageCategorySerializer(many=True)
    community_identifier = serializers.CharField(
        max_length=Community._meta.get_field("identifier").max_length,
    )
    description = serializers.CharField(
        max_length=PackageVersion._meta.get_field("description").max_length,
    )
    download_count = serializers.IntegerField(min_value=0)
    icon_url = serializers.CharField()
    is_deprecated = serializers.BooleanField()
    is_nsfw = serializers.BooleanField()
    is_pinned = serializers.BooleanField()
    last_updated = serializers.DateTimeField()
    name = serializers.CharField(max_length=Package._meta.get_field("name").max_length)
    namespace = serializers.CharField(
        max_length=Namespace._meta.get_field("name").max_length,
    )
    rating_count = serializers.IntegerField(min_value=0)
    size = serializers.IntegerField(min_value=0)
    datetime_created = serializers.DateTimeField()


class CyberstormPackageDependencySerializer(serializers.Serializer):
    description = serializers.SerializerMethodField()
    icon_url = serializers.SerializerMethodField()
    is_active = serializers.BooleanField(source="is_effectively_active")
    name = serializers.CharField()
    namespace = serializers.CharField(source="package.namespace.name")
    version_number = serializers.CharField()
    is_removed = serializers.SerializerMethodField()

    def get_is_removed(self, obj: PackageVersion) -> bool:
        package_is_removed = not (
            obj.package.is_active and obj.package_has_active_versions
        )
        if package_is_removed:
            return True
        return not obj.is_active

    def get_description(self, obj: PackageVersion) -> str:
        return (
            obj.description
            if obj.is_effectively_active
            else "This package has been removed."
        )

    def get_icon_url(self, obj: PackageVersion) -> Optional[str]:
        return obj.icon.url if obj.is_effectively_active else None


class CyberstormPackageTeamSerializer(serializers.Serializer):
    """
    Minimal information to present the team on package detail view.
    """

    name = serializers.CharField()
    members = CyberstormTeamMemberSerializer(many=True, source="public_members")


class PackageUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Package
        fields = ["readme", "changelog", "sync_markdown_from_zip"]

    def update(self, instance, validated_data):
        # If readme or changelog is explicitly provided in the data, default sync to False unless it's given
        if "readme" in validated_data or "changelog" in validated_data:
            if "sync_markdown_from_zip" not in validated_data:
                validated_data["sync_markdown_from_zip"] = False
        return super().update(instance, validated_data)
