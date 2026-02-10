import random
from typing import List

from thunderstore.comments.services import create_comment
from thunderstore.community.models import PackageListing
from thunderstore.core.management.commands.content.base import (
    ContentPopulator,
    ContentPopulatorContext,
)
from thunderstore.tickets.models import Ticket, TicketStatus


class TicketPopulator(ContentPopulator):
    def clear(self) -> None:
        Ticket.objects.all().delete()
        print("Cleared tickets")

    def populate(self, context: ContentPopulatorContext) -> None:
        print(f"Creating tickets...")

        # We need listings to attach tickets to
        listings = PackageListing.objects.select_related(
            "package__owner", "community"
        ).all()

        if not listings.exists():
            print("No listings found, skipping ticket generation")
            return

        tickets_created = 0

        for listing in listings:
            # Create 1-3 tickets per listing for a subset of listings
            if random.random() > 0.5:
                continue

            num_tickets = random.randint(1, 3)
            for _ in range(num_tickets):
                # Pick a random "submitter" from the team or just a random user logic?
                # For simplicity, we'll use the package owner (team member) for now
                # In real scenarios, it would be a user reporting an issue.

                # We need a user. Let's just grab the first member of the listing's team
                team = listing.package.owner
                member_obj = team.members.first()
                if not member_obj:
                    continue
                member = member_obj.user

                ticket = Ticket.objects.create(
                    listing=listing,
                    community=listing.community,
                    team=listing.package.owner,
                    created_by=member,
                    status=random.choice(TicketStatus.values),
                )

                # Add initial comment
                initial_comment = create_comment(
                    user=member,
                    obj=ticket,
                    body=f"Issue report for {listing.package.name}. Something is broken.",
                )

                # Add a reply (Simulate mod response)
                if random.choice([True, False]):
                    create_comment(
                        user=member,  # Simulating another user/mod in real life, but re-using member for ease
                        obj=ticket,
                        body="We are looking into it.",
                        parent_id=initial_comment.id,
                    )

                tickets_created += 1

        print(f"Created {tickets_created} tickets")

    def update_context(self, context: ContentPopulatorContext) -> None:
        pass
