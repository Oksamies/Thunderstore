import pytest
from django.contrib.sites.models import Site
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from thunderstore.comments.models import Comment
from thunderstore.community.models import Community, CommunitySite, PackageListing
from thunderstore.community.models.community_membership import (
    CommunityMemberRole,
    CommunityMembership,
)
from thunderstore.core.factories import UserFactory
from thunderstore.repository.models import Namespace, Package, PackageVersion, Team
from thunderstore.tickets.models import Ticket, TicketStatus


@pytest.mark.django_db(transaction=True)
class TestTicketViews:
    @pytest.fixture(autouse=True)
    def setup(self, settings):
        settings.DEBUG = True
        settings.IS_CYBERSTORM_ENABLED = True
        settings.ALLOWED_HOSTS = ["thunderstore.localhost", "testserver"]

        self.user = UserFactory()

        self.team = Team.create(name="TestTeam")
        self.team.add_member(self.user, "owner")

        # Team.create creates Namespace implicitly with same name
        self.namespace = Namespace.objects.get(name="TestTeam")

        self.community = Community.objects.create(
            name="TestCommunity", identifier="test-community"
        )

        # Setup Site and CommunitySite for Middleware
        self.site = Site.objects.create(
            domain="thunderstore.localhost", name="Thunderstore"
        )
        self.community_site = CommunitySite.objects.create(
            site=self.site, community=self.community
        )

        self.client = APIClient(HTTP_HOST="thunderstore.localhost")
        self.client.force_authenticate(user=self.user)

        self.package = Package.objects.create(
            name="TestPackage",
            owner=self.team,
            namespace=self.namespace,
            is_active=True,
        )

        self.listing = PackageListing.objects.create(
            package=self.package,
            community=self.community,
        )

        self.ticket = Ticket.objects.create(
            listing=self.listing,
            community=self.community,
            team=self.team,
            created_by=self.user,
            status=TicketStatus.OPEN,
        )

    def test_listing_ticket_list(self):
        # url: listing/<str:community_id>/<str:namespace_id>/<str:package_name>/tickets/
        url = reverse(
            "api:cyberstorm:cyberstorm.listing.tickets",
            kwargs={
                "community_id": self.community.identifier,
                "namespace_id": self.namespace.name,
                "package_name": self.package.name,
            },
        )

        response = self.client.get(url)
        if response.status_code != 200:
            print(f"Error listing tickets: {response.content}")

        # If the view code checks owner=namespace, it might fail/error 500
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]["uuid"] == str(self.ticket.uuid)

    def test_create_ticket_message(self):
        # url: tickets/<uuid:uuid>/messages/
        url = reverse(
            "api:cyberstorm:cyberstorm.tickets.messages.create",
            kwargs={"uuid": self.ticket.uuid},
        )
        data = {"content": "This is a reply"}

        response = self.client.post(url, data, format="json")
        if response.status_code != 201:
            print(f"Error creating message: {response.content}")
        assert response.status_code == status.HTTP_201_CREATED

        # Verify comment created in comments DB
        comments = (
            self.ticket.prefetched_comments
            if hasattr(self.ticket, "prefetched_comments")
            else []
        )
        # Since we just created it, we need to fetch it via service or reload (but reload won't fetch comments without helper)
        from thunderstore.comments.services import get_comments_for_object

        comments = get_comments_for_object(self.ticket)
        assert len(comments) == 1
        assert comments[0].body == "This is a reply"
        assert comments[0].author == self.user

    def test_create_ticket_note_as_mod(self):
        # Allow user to manage community
        # Community member role handling manual setup
        CommunityMembership.objects.create(
            community=self.community, user=self.user, role=CommunityMemberRole.moderator
        )

        url = reverse(
            "api:cyberstorm:cyberstorm.tickets.notes.create",
            kwargs={"uuid": self.ticket.uuid},
        )
        data = {"content": "Secret note"}

        response = self.client.post(url, data, format="json")
        if response.status_code != 201:
            print(f"Error creating note: {response.content}")
        assert response.status_code == status.HTTP_201_CREATED

        from thunderstore.comments.services import get_comments_for_object

        comments = get_comments_for_object(self.ticket, include_internal=True)
        assert len(comments) == 1
        assert comments[0].body == "Secret note"
        assert comments[0].is_internal

    def test_ticket_detail_retrieve(self):
        from thunderstore.comments.services import create_comment

        create_comment(self.user, self.ticket, "Public Comment")

        url = reverse(
            "api:cyberstorm:cyberstorm.tickets.detail",
            kwargs={"uuid": self.ticket.uuid},
        )
        response = self.client.get(url)
        if response.status_code != 200:
            print(f"Error retrieving ticket: {response.content}")

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["messages"]) == 1
        assert response.data["messages"][0]["content"] == "Public Comment"
