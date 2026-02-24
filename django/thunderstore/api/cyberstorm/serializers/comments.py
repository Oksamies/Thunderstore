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
    author = serializers.SerializerMethodField()
    parent = serializers.PrimaryKeyRelatedField(
        queryset=Comment.objects.all(), required=False, allow_null=True
    )

    # Added for compatibility with Tickets
    content = serializers.CharField(source="body", required=False)
    created_at = serializers.DateTimeField(source="datetime_created", read_only=True)
    reactions = serializers.SerializerMethodField()

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
            "reactions",
        ]

    @swagger_serializer_method(serializer_or_field=serializers.DictField)
    def get_reactions(self, obj):
        request = self.context.get("request")
        user_id = request.user.id if request and request.user.is_authenticated else None

        reactions_data = {}
        for reaction in obj.reactions.all():
            if reaction.reaction not in reactions_data:
                reactions_data[reaction.reaction] = {"count": 0, "user_reacted": False}
            reactions_data[reaction.reaction]["count"] += 1
            if user_id and reaction.author_id == user_id:
                reactions_data[reaction.reaction]["user_reacted"] = True

        return reactions_data

    @swagger_serializer_method(serializer_or_field=CommentUserSerializer)
    def get_author(self, obj):
        if not obj.author_id:
            return None
        try:
            user = User.objects.get(pk=obj.author_id)
            return CommentUserSerializer(user).data
        except User.DoesNotExist:
            return None
