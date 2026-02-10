import uuid

from django.conf import settings
from django.db import models

from thunderstore.core.mixins import TimestampMixin


class TicketStatus(models.TextChoices):
    OPEN = "open", "Open"
    USER_REPLIED = "user_replied", "User Replied"
    MOD_REPLIED = "mod_replied", "Moderator Replied"
    RESOLVED = "resolved", "Resolved"
    CLOSED = "closed", "Closed"


class Ticket(TimestampMixin, models.Model):
    uuid = models.UUIDField(
        default=uuid.uuid4, editable=False, unique=True, db_index=True
    )
    listing = models.ForeignKey(
        "community.PackageListing",
        on_delete=models.SET_NULL,
        null=True,
        related_name="tickets",
        db_constraint=False,
    )
    community = models.ForeignKey(
        "community.Community",
        on_delete=models.SET_NULL,
        null=True,
        related_name="tickets",
        db_constraint=False,
    )
    team = models.ForeignKey(
        "repository.Team",
        on_delete=models.SET_NULL,
        null=True,
        related_name="tickets",
        db_constraint=False,
    )
    status = models.CharField(
        max_length=32,
        choices=TicketStatus.choices,
        default=TicketStatus.OPEN,
        db_index=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_tickets",
        db_constraint=False,
    )
    is_deleted = models.BooleanField(default=False)

    class Meta:
        indexes = [
            models.Index(fields=["listing", "status"]),
            models.Index(fields=["community", "status"]),
        ]


class TicketTemplate(models.Model):
    uuid = models.UUIDField(
        default=uuid.uuid4, editable=False, unique=True, db_index=True
    )
    community = models.ForeignKey(
        "community.Community",
        on_delete=models.CASCADE,
        related_name="ticket_templates",
        db_constraint=False,
    )
    label = models.CharField(max_length=100)
    content = models.TextField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="+",
        db_constraint=False,
    )
