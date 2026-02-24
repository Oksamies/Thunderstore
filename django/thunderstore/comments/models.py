import uuid

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

from thunderstore.core.mixins import TimestampMixin


class Comment(TimestampMixin, models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)

    # Hierarchy
    parent = models.ForeignKey(
        "self", null=True, blank=True, related_name="replies", on_delete=models.PROTECT
    )

    # GFK to Target Object
    # db_constraint=False allows us to link to ContentType in a different DB
    # (or if we just want to loose-couple)
    content_type = models.ForeignKey(
        ContentType, on_delete=models.PROTECT, db_constraint=False
    )
    object_id = models.CharField(max_length=36)  # UUID string usually
    content_object = GenericForeignKey("content_type", "object_id")

    # Content
    # We store author_id manually to avoid cross-DB foreign key constraints with the User model
    author_id = models.IntegerField(null=True, blank=True, db_index=True)
    body = models.TextField()
    is_internal = models.BooleanField(
        default=False, help_text="Internal note/comment not visible to public users"
    )

    # Meta
    # TimestampMixin provides datetime_created and datetime_updated
    is_deleted = models.BooleanField(default=False)

    class Meta:
        indexes = [
            models.Index(fields=["content_type", "object_id"]),
        ]
        # TimestampMixin usually handles ordering if needed, but we can be explicit
        ordering = ["datetime_created"]


class CommentReaction(TimestampMixin, models.Model):
    REACTION_CHOICES = [
        ("thumbs_up", "Thumbs Up"),
        ("thumbs_down", "Thumbs Down"),
        ("heart", "Heart"),
        ("laugh", "Laugh"),
        ("confused", "Confused"),
        ("rocket", "Rocket"),
    ]

    uuid = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    comment = models.ForeignKey(
        Comment, on_delete=models.CASCADE, related_name="reactions"
    )
    author_id = models.IntegerField(db_index=True)
    reaction = models.CharField(max_length=32, choices=REACTION_CHOICES)

    class Meta:
        unique_together = ("comment", "author_id", "reaction")
        indexes = [
            models.Index(fields=["comment", "reaction"]),
        ]
