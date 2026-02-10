import random
from typing import Optional

from thunderstore.comments.models import Comment
from thunderstore.comments.services import create_comment
from thunderstore.community.models import PackageListing
from thunderstore.core.management.commands.content.base import (
    ContentPopulator,
    ContentPopulatorContext,
)
from thunderstore.repository.models import PackageVersion


class CommentPopulator(ContentPopulator):
    def clear(self) -> None:
        print("Clearing comments...")
        # Only delete generic comments, avoiding deleting tickets comments if possible?
        # Actually ticket messages are comments too.
        # If we run clear=True on all populators, tickets are wiped so their comments die too (cascade).
        # But create_test_data deletes in reverse order.
        # TicketPopulator clears Tickets.
        # CommentPopulator will clear Comments.
        # So we should be fine clearing all.
        # Break self-referential links first to avoid recursion depth errors
        # and "relation does not exist" phantom errors during cascade collection.
        Comment.objects.all().update(parent=None)
        Comment.objects.all().delete()

    def populate(self, context: ContentPopulatorContext) -> None:
        print("Populating comments...")

        # 1. Communities
        for community in context.communities:
            if random.random() > 0.3:
                self._create_random_comments(community, context.teams)

        # 2. Teams
        for team in context.teams:
            if random.random() > 0.3:
                self._create_random_comments(team, context.teams)

        # 3. Packages (Repository Package)
        for package in context.packages:
            if random.random() > 0.5:
                self._create_random_comments(package, context.teams)

        # 4. Package Listings (Community Package Page)
        # We need to query these as they are not in context explicitly
        listings = PackageListing.objects.all()
        for listing in listings:
            if random.random() > 0.7:
                self._create_random_comments(listing, context.teams)

        # 5. Package Versions
        # A bit expensive to do all, let's do random subset
        versions = PackageVersion.objects.all().order_by("?")[:100]
        for version in versions:
            self._create_random_comments(version, context.teams)

        print("Done populating comments.")

    def _create_random_comments(self, obj, teams):
        count = random.randint(1, 4)
        for _ in range(count):
            # Pick a random author from a random team
            team = random.choice(teams) if teams else None
            user = team.members.first().user if team and team.members.exists() else None

            if not user:
                continue

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
                    "Lorem ipsum dolor sit amet.",
                    "10/10 would download again ⭐⭐⭐⭐⭐",
                    "Does this work in multiplayer? 🎮",
                    "Any plans for DLC support?",
                    "Thanks for the hard work! ❤️",
                    "Here is a stack trace:\n`NullReferenceException: Object reference not set to an instance of an object`",
                    "Pog!",
                    "Does this conflict with any other mods?",
                    "Underrated mod 💎",
                    "Can I include this in my modpack? 📦",
                    "Please fix the typo in the readme 📝",
                    "First!",
                    "Broken on my end 😕",
                ]
            )

            create_comment(user, obj, body)

    def update_context(self, context: ContentPopulatorContext) -> None:
        pass
