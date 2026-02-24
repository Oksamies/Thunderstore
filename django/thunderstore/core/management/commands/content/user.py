import random
from typing import List, Optional

from django.contrib.auth import get_user_model

from thunderstore.core.management.commands.content.base import (
    ContentPopulator,
    ContentPopulatorContext,
)
from thunderstore.utils.iterators import print_progress

User = get_user_model()


class UserPopulator(ContentPopulator):
    users: Optional[List[User]] = None
    name_prefix = "Test_User_"

    def populate(self, context: ContentPopulatorContext) -> None:
        print("Populating users...")

        existing = list(
            User.objects.filter(username__startswith=self.name_prefix)[
                : context.user_count
            ]
        )
        remainder = context.user_count - len(existing)

        last = last_user.pk if (last_user := User.objects.last()) else 0

        new_users = []
        for i in print_progress(range(remainder), remainder):
            username = f"{self.name_prefix}{last + i}"
            user = User.objects.create_user(
                username=username,
                email=f"{username}@example.com",
                password="password123",
            )
            new_users.append(user)

        self.users = existing + new_users

    def update_context(self, context) -> None:
        if self.users is not None:
            context.users = self.users
        else:
            context.users = User.objects.filter(username__startswith=self.name_prefix)[
                : context.user_count
            ]

    def clear(self) -> None:
        print("Deleting existing test users...")
        User.objects.filter(username__startswith=self.name_prefix).delete()
