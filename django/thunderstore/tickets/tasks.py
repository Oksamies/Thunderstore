from celery import shared_task
from django.db.models import Count

from thunderstore.community.models import Community
from thunderstore.repository.models import Team
from thunderstore.tickets.models import Ticket, TicketStatus


@shared_task
def cleanup_ghost_tickets():
    """
    Scans for tickets that point to non-existent Community or Team records
    (Cross-DB Foreign Keys) and marks them as CLOSED or deletes them.
    """
    # 1. Fetch valid IDs from Default DB
    valid_community_ids = set(Community.objects.values_list("id", flat=True))
    valid_team_ids = set(Team.objects.values_list("id", flat=True))

    # 2. Iterate Tickets (Batch processing recommended for large datasets, simplified here)
    # Finding tickets where community_id is NOT IN valid_community_ids
    # Django ORM doesn't support exclude(community_id__in=list(valid_ids)) efficiently if list is huge.
    # But since we are cross-db, we can't do a join.

    # Strategy: Fetch distinct community_ids used in Tickets
    used_community_ids = set(Ticket.objects.values_list("community_id", flat=True))
    ghost_community_ids = used_community_ids - valid_community_ids

    if ghost_community_ids:
        updated_count = Ticket.objects.filter(
            community_id__in=ghost_community_ids
        ).update(status=TicketStatus.CLOSED)
        print(f"Closed {updated_count} tickets with missing communities.")

    # Strategy: Fetch distinct team_ids used in Tickets
    used_team_ids = set(Ticket.objects.values_list("team_id", flat=True))
    ghost_team_ids = used_team_ids - valid_team_ids

    if ghost_team_ids:
        updated_count = Ticket.objects.filter(team_id__in=ghost_team_ids).update(
            status=TicketStatus.CLOSED
        )
        print(f"Closed {updated_count} tickets with missing teams.")
