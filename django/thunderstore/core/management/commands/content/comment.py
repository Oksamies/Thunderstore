import random
from typing import Optional

from django.contrib.auth import get_user_model

from thunderstore.comments.models import Comment
from thunderstore.comments.services import create_comment
from thunderstore.community.models import PackageListing
from thunderstore.core.management.commands.content.base import (
    ContentPopulator,
    ContentPopulatorContext,
)
from thunderstore.repository.models import PackageVersion

User = get_user_model()


class CommentPopulator(ContentPopulator):
    def clear(self) -> None:
        print("Clearing comments...")
        # Break self-referential links first to avoid recursion depth errors
        Comment.objects.all().update(parent=None)
        Comment.objects.all().delete()

    def populate(self, context: ContentPopulatorContext) -> None:
        print("Populating comments...")

        # Get users for authorship
        users = list(context.users) if context.users else list(User.objects.all()[:10])
        if not users:
            print("No users found, skipping comment generation.")
            return

        # 1. Package Listings (Community Package Page) - PRIMARY FOCUS
        listings = PackageListing.objects.all()
        for i, listing in enumerate(listings):
            # Create a "Complex" thread on the first few listings
            if i < 3:
                self._create_complex_thread(listing, users)
                self._create_moderated_thread(listing, users)

            # Random noise on others
            if random.random() > 0.5:
                self._create_random_comments(listing, users)

        # 2. Communities
        for community in context.communities:
            if random.random() > 0.7:
                self._create_random_comments(community, users)

        # 3. Teams
        for team in context.teams:
            if random.random() > 0.7:
                self._create_random_comments(team, users)

        # 4. Package Versions (Older versions maybe?)
        versions = PackageVersion.objects.all().order_by("?")[:20]
        for version in versions:
            self._create_random_comments(version, users)

        print("Done populating comments.")

    def _get_random_user(self, users):
        return random.choice(users)

    def _create_complex_thread(self, obj, users):
        # Root comment
        root = create_comment(
            self._get_random_user(users),
            obj,
            "This mod is amazing! But I have a question about configuration.",
        )

        # Reply 1
        r1 = create_comment(
            self._get_random_user(users),
            obj,
            "Check the wiki, it explains everything.",
            parent_id=root.pk,
        )

        # Reply 2 (Nested)
        create_comment(
            self._get_random_user(users),
            obj,
            "The wiki is outdated actually. Try checking the discord.",
            parent_id=r1.pk,
        )

        # Reply 3 (Peer to Reply 1)
        create_comment(
            self._get_random_user(users),
            obj,
            "I have the same question! +1",
            parent_id=root.pk,
        )

    def _create_moderated_thread(self, obj, users):
        # A thread with deleted content
        root = create_comment(
            self._get_random_user(users), obj, "REPORTED THREAD: Contains spam below."
        )

        # Spam comment (Soft Deleted)
        spam = create_comment(
            self._get_random_user(users),
            obj,
            "BUY CHEAP GOLD NOW!!! www.fake-site.com",
            parent_id=root.pk,
        )
        spam.is_deleted = True
        spam.save()

        # Reply to spam (Active, but parent is deleted - orphans check)
        create_comment(
            self._get_random_user(users),
            obj,
            "Please don't click that link guys.",
            parent_id=spam.pk,
        )

        # Internal Note on the root
        note = create_comment(
            self._get_random_user(users),
            obj,
            "INTERNAL NOTE: User banned for spamming.",
            is_internal=True,
        )
        # Verify internal notes can hang off objects too, not just as replies?
        # Actually notes usually shouldn't be replies to public comments?
        # Typically internal notes are top-level on the object (Ticket), but on a Comment thread?
        # The schema supports is_internal on any comment.
        # But for now let's leave it disjoint or as a reply to root if that's the model.
        # Let's attach it to the Object itself as a separate "Top Level" internal note
        create_comment(
            self._get_random_user(users),
            obj,
            "INTERNAL NOTE ON OBJECT: Monitoring this thread.",
            is_internal=True,
        )

    def _create_random_comments(self, obj, users):
        count = random.randint(1, 4)
        for _ in range(count):
            user = self._get_random_user(users)
            body = random.choice(
                [
                    "This is great! 🔥",
                    "I found a bug 🐛. Please fix!",
                    "Can you add this feature? 🥺",
                    "Works on my machine 💻.",
                    "Update please! 🚀",
                    "Is this compatible with the latest patch? 🤔",
                    "Nice work! 👏",
                    "How do I install this? ⚙️",
                    "Check out my mod too 👀.",
                    "10/10 would download again ⭐⭐⭐⭐⭐",
                    "Does this work in multiplayer? 🎮",
                    "Here is a stack trace:\n`NullReferenceException: Object reference not set to an instance of an object`",
                    "Pog!",
                    "Underrated mod 💎",
                    "First!",
                    "Broken on my end 😕",
                ]
            )
            create_comment(user, obj, body)

    def update_context(self, context: ContentPopulatorContext) -> None:
        pass
