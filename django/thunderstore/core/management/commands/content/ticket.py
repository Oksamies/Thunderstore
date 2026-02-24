import random
from typing import List

from django.contrib.auth import get_user_model

from thunderstore.comments.services import create_comment
from thunderstore.community.models import PackageListing
from thunderstore.core.management.commands.content.base import (
    ContentPopulator,
    ContentPopulatorContext,
)
from thunderstore.tickets.models import Ticket, TicketStatus

User = get_user_model()


class TicketPopulator(ContentPopulator):
    def clear(self) -> None:
        Ticket.objects.all().delete()
        print("Cleared tickets")

    def populate(self, context: ContentPopulatorContext) -> None:
        print(f"Creating tickets...")

        listings = PackageListing.objects.select_related(
            "package__owner", "community"
        ).all()

        if not listings.exists():
            print("No listings found, skipping ticket generation")
            return

        users = list(context.users) if context.users else list(User.objects.all()[:10])
        if not users:
            print("No users found, skipping ticket generation")
            return

        tickets_created = 0
        statuses = TicketStatus.values
        listing_iterator = iter(listings)

        # 1. Guarantee coverage: Create one ticket for EVERY status type
        for status in statuses:
            try:
                listing = next(listing_iterator)
            except StopIteration:
                listing_iterator = iter(listings)
                listing = next(listing_iterator)

            self._create_ticket(
                listing, status, f"Test Ticket: {status.upper()}", users
            )
            tickets_created += 1

        # 2. Create a "Complex" ticket with long history and internal notes
        complex_listing = listings.first()
        self._create_complex_ticket(complex_listing, users)
        tickets_created += 1

        # 3. Random fill
        for listing in listings:
            if random.random() > 0.3:
                continue

            self._create_ticket(
                listing,
                random.choice(statuses),
                f"Random issue report for {listing.package.name}",
                users,
            )
            tickets_created += 1

        print(f"Created {tickets_created} tickets")

    def _create_ticket(self, listing, status, title, users):
        # Determine author
        team = listing.package.owner
        member_obj = team.members.first()
        author = member_obj.user if member_obj else random.choice(users)

        ticket = Ticket.objects.create(
            listing=listing,
            community=listing.community,
            team=listing.package.owner,
            created_by=author,
            status=status,
        )

        # Initial message
        create_comment(
            user=author,
            obj=ticket,
            body=f"{title}\n\nI am experiencing an issue where the mod crashes on load.",
        )

        # If resolved/closed, maybe add a closing comment
        if status in [TicketStatus.RESOLVED, TicketStatus.CLOSED]:
            create_comment(
                user=author,
                obj=ticket,
                body="Marking as resolved. Thanks for the fix!",
            )

    def _create_complex_ticket(self, listing, users):
        team = listing.package.owner
        member_obj = team.members.first()
        author = member_obj.user if member_obj else random.choice(users)
        mod_user = (
            random.choice([u for u in users if u != author])
            if len(users) > 1
            else author
        )

        ticket = Ticket.objects.create(
            listing=listing,
            community=listing.community,
            team=listing.package.owner,
            created_by=author,
            status=TicketStatus.OPEN,
        )

        # Conversation
        c1 = create_comment(
            author, ticket, "Complex Ticket: Please allow internal notes testing."
        )
        c2 = create_comment(
            author,
            ticket,
            "Here is a log file:\n```\nError: null\n```",
            parent_id=c1.pk,
        )

        # Internal Note (Moderator only)
        create_comment(
            user=mod_user,
            obj=ticket,
            body="INTERNAL NOTE: User is known for spamming. Check IP.",
            is_internal=True,
        )

        # Public reply
        create_comment(
            user=mod_user,
            obj=ticket,
            body="We are investigating your report.",
            parent_id=c2.pk,
        )

    def update_context(self, context: ContentPopulatorContext) -> None:
        pass
