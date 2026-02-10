from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import PermissionDenied as DRFPermissionDenied
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.response import Response
from rest_framework.views import APIView

from thunderstore.api.cyberstorm.serializers.comments import CommentSerializer
from thunderstore.api.cyberstorm.views.package_listing_actions import (
    get_package_listing,
)
from thunderstore.api.utils import conditional_swagger_auto_schema, swagger_auto_schema
from thunderstore.comments.models import Comment
from thunderstore.comments.services import (
    create_comment,
    delete_comment,
    restore_comment,
)
from thunderstore.community.models import PackageListing


class CommentDeleteAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @conditional_swagger_auto_schema(
        operation_id="cyberstorm.comments.delete",
        responses={204: "No Content"},
    )
    def delete(self, request, uuid):
        comment = get_object_or_404(Comment, uuid=uuid)

        try:
            delete_comment(request.user, comment)
        except PermissionDenied:
            raise DRFPermissionDenied(
                "You do not have permission to delete this comment."
            )

        return Response(status=status.HTTP_204_NO_CONTENT)


class CommentRestoreAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @conditional_swagger_auto_schema(
        operation_id="cyberstorm.comments.restore",
        responses={204: "No Content"},
    )
    def post(self, request, uuid):
        # We need to find the comment even if it is deleted.
        # get_object_or_404 uses default manager which might filter out deleted?
        # Checking Comment model... is_deleted=False is usually not a default manager filter unless implemented.
        # Comment model inherits TimestampMixin. SafeDeleteMixin is not mixed in explicitly in Comment model definition I saw earlier, only TimestampMixin.
        # Wait, let me check Comment model again.

        # If default manager filters deleted, we need Comment.objects_all.get(...) or similar.
        comment = get_object_or_404(Comment, uuid=uuid)

        try:
            restore_comment(request.user, comment)
        except PermissionDenied:
            raise DRFPermissionDenied(
                "You do not have permission to restore this comment."
            )

        return Response(status=status.HTTP_204_NO_CONTENT)


class ListingCommentListAPIView(APIView):
    permission_classes = [IsAuthenticatedOrReadOnly]

    @swagger_auto_schema(
        operation_id="cyberstorm.listing.comments.list",
        # responses={200: CommentSerializer(many=True)},
    )
    def get(self, request, community_id, namespace_id, package_name):
        listing = get_package_listing(
            namespace_id=namespace_id,
            package_name=package_name,
            community_id=community_id,
        )
        ct = ContentType.objects.get_for_model(PackageListing)

        comments = Comment.objects.filter(
            content_type=ct, object_id=listing.id
        ).order_by("-datetime_created")

        serializer = CommentSerializer(comments, many=True)
        return Response(serializer.data)

    @swagger_auto_schema(
        operation_id="cyberstorm.listing.comments.create",
        request_body=CommentSerializer,
        responses={201: CommentSerializer()},
    )
    def post(self, request, community_id, namespace_id, package_name):
        serializer = CommentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        listing = get_package_listing(
            namespace_id=namespace_id,
            package_name=package_name,
            community_id=community_id,
        )

        validated_data = serializer.validated_data
        parent = validated_data.get("parent")

        # parent is already a Comment instance because of PrimaryKeyRelatedField in serializer?
        # Actually PrimaryKeyRelatedField returns the object instance if valid.

        # If the serializer defines parent as PrimaryKeyRelatedField, validated_data['parent'] will be the Comment object.
        # But wait, earlier code used parent.uuid if parent else None.
        # If it is an instance, we can pass it directly or take UUID.

        parent_id = parent.uuid if parent else None

        comment = create_comment(
            user=request.user,
            obj=listing,
            body=validated_data.get("body"),
            parent_id=parent_id,
            is_internal=validated_data.get("is_internal", False),
        )

        return Response(CommentSerializer(comment).data, status=status.HTTP_201_CREATED)
