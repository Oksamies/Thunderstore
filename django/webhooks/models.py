import uuid
import json

import requests

from django.db import models


class ChoiceEnum(object):

    @classmethod
    def as_choices(cls):
        return [
            (key, value)
            for key, value in vars(cls).items()
            if not key.startswith("_")
        ]

    @classmethod
    def options(cls):
        return [
            value
            for key, value in vars(cls).items()
            if not key.startswith("_")
        ]


class WebhookType(ChoiceEnum):
    mod_release = "mod_release"


class Webhook(models.Model):
    name = models.CharField(max_length=256)
    webhook_url = models.CharField(max_length=2083)
    webhook_type = models.CharField(
        max_length=512,
        default=WebhookType.mod_release,
        choices=WebhookType.as_choices(),
    )

    is_active = models.BooleanField(
        default=True,
    )
    date_created = models.DateTimeField(
        auto_now_add=True,
    )
    uuid4 = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
    )

    def __str__(self):
        return self.name

    def call_with_json(self, webhook_data):
        try:
            requests.post(
                self.webhook_url, data=json.dumps(webhook_data),
                headers={"Content-Type": "application/json"}
            )
        except Exception:
            pass
