from django.contrib.auth import get_user_model
from rest_framework import serializers

from thunderstore.comments.models import Comment
from thunderstore.social.utils import get_user_avatar_url

User = get_user_model()


from drf_yasg.utils import swagger_serializer_method


class CommentUserSerializer(serializers.ModelSerializer):
    avatar = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["username", "avatar"]

    @swagger_serializer_method(serializer_or_field=serializers.CharField)
    def get_avatar(self, obj):
        return get_user_avatar_url(obj)


class CommentSerializer(serializers.ModelSerializer):
    author = CommentUserSerializer(read_only=True)
    parent = serializers.PrimaryKeyRelatedField(
        queryset=Comment.objects.all(), required=False, allow_null=True
    )

    # Added for compatibility with Tickets
    content = serializers.CharField(source="body", required=False)
    created_at = serializers.DateTimeField(source="datetime_created", read_only=True)

    class Meta:
        model = Comment
        fields = [
            "uuid",
            "body",
            "content",
            "author",
            "is_internal",
            "is_deleted",
            "datetime_created",
            "created_at",
            "datetime_updated",
            "parent",
        ]
