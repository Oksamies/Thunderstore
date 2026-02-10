from django.contrib.auth.models import User
from rest_framework import serializers

from thunderstore.api.cyberstorm.serializers.comments import CommentSerializer
from thunderstore.tickets.models import Ticket, TicketStatus, TicketTemplate


class UserSerializer(serializers.ModelSerializer):
    avatar = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["username", "email", "avatar"]

    def get_avatar(self, obj):
        return None


class TicketSerializer(serializers.ModelSerializer):
    created_by = UserSerializer(read_only=True)
    messages = serializers.SerializerMethodField()
    last_updated = serializers.DateTimeField(source="datetime_updated")
    created_at = serializers.DateTimeField(source="datetime_created")

    class Meta:
        model = Ticket
        fields = [
            "uuid",
            "listing",
            "community",
            "team",
            "status",
            "created_by",
            "created_at",
            "last_updated",
            "messages",
        ]

    def get_messages(self, obj):
        # If the view has attached comments, use them
        if hasattr(obj, "prefetched_comments"):
            return [comment.uuid for comment in obj.prefetched_comments]
        return []


class TicketCreateSerializer(serializers.Serializer):
    content = serializers.CharField(required=True)


class TicketStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=TicketStatus.choices)


class TicketTemplateSerializer(serializers.ModelSerializer):
    created_by = UserSerializer(read_only=True)

    class Meta:
        model = TicketTemplate
        fields = ["uuid", "community", "label", "content", "created_by"]
