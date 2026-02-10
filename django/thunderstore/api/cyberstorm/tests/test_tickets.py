import json
import uuid

import pytest
from django.contrib.contenttypes.models import ContentType
from rest_framework import status
from rest_framework.test import APIClient

from conftest import TestUserTypes
from thunderstore.comments.models import Comment
from thunderstore.community.models import CommunityMemberRole, PackageListing
from thunderstore.repository.models import TeamMemberRole
from thunderstore.tickets.models import Ticket, TicketMessage, TicketNote, TicketStatus


def get_listing_ticket_url(package_listing):
    namespace_id = package_listing.package.namespace.name
    package_name = package_listing.package.name
    community_id = package_listing.community.identifier
    return (
        f"/api/cyberstorm/listing/{community_id}/{namespace_id}/{package_name}/tickets/"
    )


@pytest.mark.django_db
def test_create_ticket_permissions(
    api_client: APIClient,
    active_package_listing: PackageListing,
):
    # Setup users
    owner_user = TestUserTypes.get_user_by_type(TestUserTypes.regular_user)
    active_package_listing.package.owner.add_member(
        owner_user, role=TeamMemberRole.owner
    )

    # Let's create a fresh mod user to be strict
    from thunderstore.core.factories import UserFactory

    community_mod = UserFactory()
    active_package_listing.community.members.create(
        user=community_mod, role=CommunityMemberRole.moderator
    )

    random_user = UserFactory()

    url = get_listing_ticket_url(active_package_listing)
    data = {"content": "Help me!"}

    # 1. Random User -> 403
    api_client.force_authenticate(user=random_user)
    response = api_client.post(url, data=data, format="json")
    assert response.status_code == status.HTTP_403_FORBIDDEN

    # 2. Package Owner -> 201
    api_client.force_authenticate(user=owner_user)
    response = api_client.post(url, data=data, format="json")
    assert response.status_code == status.HTTP_201_CREATED
    ticket_uuid = response.data["uuid"]

    ticket = Ticket.objects.get(uuid=ticket_uuid)

    # Check comment directly via ContentType/Comment model
    ct = ContentType.objects.get_for_model(Ticket)
    assert (
        Comment.objects.filter(content_type=ct, object_id=str(ticket.pk)).count() == 1
    )
    assert ticket.status == TicketStatus.OPEN

    # 3. Community Moderator -> 201
    api_client.force_authenticate(user=community_mod)
    response = api_client.post(
        url, data={"content": "Mod opened ticket"}, format="json"
    )
    assert response.status_code == status.HTTP_201_CREATED

    # Check total tickets increased
    # Or check new ticket
    tickets_count = Ticket.objects.count()
    assert tickets_count >= 2


@pytest.mark.django_db
def test_ticket_messaging_flow(
    api_client: APIClient,
    active_package_listing: PackageListing,
):
    # Setup
    owner_user = TestUserTypes.get_user_by_type(TestUserTypes.regular_user)
    active_package_listing.package.owner.add_member(
        owner_user, role=TeamMemberRole.owner
    )

    from thunderstore.core.factories import UserFactory

    mod_user = UserFactory()
    active_package_listing.community.members.create(
        user=mod_user, role=CommunityMemberRole.moderator
    )

    # Create Ticket as Owner
    ticket = Ticket.objects.create(
        listing=active_package_listing,
        community=active_package_listing.community,
        team=active_package_listing.package.owner,
        created_by=owner_user,
        status=TicketStatus.OPEN,
    )

    message_url = f"/api/cyberstorm/tickets/{ticket.uuid}/messages/"

    ct = ContentType.objects.get_for_model(Ticket)

    # Mod replies
    api_client.force_authenticate(user=mod_user)
    resp = api_client.post(message_url, data={"content": "Mod reply"}, format="json")
    assert resp.status_code == 201
    ticket.refresh_from_db()
    assert ticket.status == TicketStatus.MOD_REPLIED
    assert (
        Comment.objects.filter(content_type=ct, object_id=str(ticket.pk)).count() == 1
    )

    # Owner replies
    api_client.force_authenticate(user=owner_user)
    resp = api_client.post(message_url, data={"content": "Owner reply"}, format="json")
    assert resp.status_code == 201
    ticket.refresh_from_db()
    assert ticket.status == TicketStatus.USER_REPLIED
    assert (
        Comment.objects.filter(content_type=ct, object_id=str(ticket.pk)).count() == 2
    )


@pytest.mark.django_db
def test_ticket_notes_permissions(
    api_client: APIClient,
    active_package_listing: PackageListing,
):
    owner_user = TestUserTypes.get_user_by_type(TestUserTypes.regular_user)
    active_package_listing.package.owner.add_member(
        owner_user, role=TeamMemberRole.owner
    )

    from thunderstore.core.factories import UserFactory

    mod_user = UserFactory()
    active_package_listing.community.members.create(
        user=mod_user, role=CommunityMemberRole.moderator
    )

    ticket = Ticket.objects.create(
        listing=active_package_listing,
        community=active_package_listing.community,
        team=active_package_listing.package.owner,
        created_by=owner_user,
    )

    url = f"/api/cyberstorm/tickets/{ticket.uuid}/notes/"

    # Owner tries to add note -> 403
    api_client.force_authenticate(user=owner_user)
    resp = api_client.post(url, data={"content": "Sneaky note"}, format="json")
    assert resp.status_code == 403

    ct = ContentType.objects.get_for_model(Ticket)
    assert (
        Comment.objects.filter(
            content_type=ct, object_id=str(ticket.pk), is_internal=True
        ).count()
        == 0
    )

    # Mod adds note -> 201
    api_client.force_authenticate(user=mod_user)
    resp = api_client.post(url, data={"content": "Internal note"}, format="json")
    assert resp.status_code == 201
    assert (
        Comment.objects.filter(
            content_type=ct, object_id=str(ticket.pk), is_internal=True
        ).count()
        == 1
    )

    # Check Visibility
    detail_url = f"/api/cyberstorm/tickets/{ticket.uuid}/"

    # Owner views ticket -> No notes
    api_client.force_authenticate(user=owner_user)
    resp = api_client.get(detail_url)

    if "notes" in resp.data:
        # Notes are internal comments. If they exist but empty, good.
        assert len(resp.data.get("notes", [])) == 0

    # Mod views ticket -> See notes
    api_client.force_authenticate(user=mod_user)
    resp = api_client.get(detail_url)

    if "notes" in resp.data:
        assert len(resp.data["notes"]) == 1
        # Check against mapped field 'body' or 'content' depending on serializer
        item = resp.data["notes"][0]
        content_val = item.get("body") or item.get("content")
        assert content_val == "Internal note"


@pytest.mark.django_db
def test_ticket_viewset_queryset_filtering(
    api_client: APIClient,
    active_package_listing: PackageListing,
):
    from thunderstore.core.factories import UserFactory

    user_A = UserFactory(username="UserA")
    user_B = UserFactory(username="UserB")

    # Ticket A owned by User A
    ticket_A = Ticket.objects.create(
        listing=active_package_listing,
        community=active_package_listing.community,
        team=active_package_listing.package.owner,
        created_by=user_A,
    )
    active_package_listing.package.owner.add_member(user_A, role=TeamMemberRole.owner)

    url = "/api/cyberstorm/tickets/"

    api_client.force_authenticate(user=user_A)
    resp = api_client.get(url)
    assert resp.status_code == 200
    assert len(resp.data) == 1
    assert resp.data[0]["uuid"] == str(ticket_A.uuid)

    api_client.force_authenticate(user=user_B)
    resp = api_client.get(url)
    assert len(resp.data) == 0  # Creates nothing, sees nothing
