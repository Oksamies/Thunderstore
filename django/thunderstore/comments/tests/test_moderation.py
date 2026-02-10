import pytest
from django.contrib.contenttypes.models import ContentType
from django.contrib.sites.models import Site
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from thunderstore.comments.models import Comment
from thunderstore.comments.services import create_comment
from thunderstore.community.models import (
    Community,
    CommunityMemberRole,
    CommunitySite,
    PackageListing,
)
from thunderstore.community.models.community_membership import CommunityMembership
from thunderstore.core.factories import UserFactory
from thunderstore.repository.models import Namespace, Package, Team


@pytest.mark.django_db
class TestCommentModeration:
    @pytest.fixture(autouse=True)
    def setup(self, settings):
        settings.DEBUG = True
        settings.IS_CYBERSTORM_ENABLED = True
        settings.ALLOWED_HOSTS = ["thunderstore.localhost", "testserver"]

        # Clear ContentType cache to avoid stale entries in tests
        ContentType.objects.clear_cache()

        self.user = UserFactory()
        self.moderator = UserFactory(username="mod")
        self.outsider = UserFactory(username="outsider")
        self.team_owner = UserFactory(username="owner")
        self.superuser = UserFactory(is_superuser=True)

        self.team = Team.create(name="TestTeam")
        self.team.add_member(self.team_owner, "owner")
        self.namespace = Namespace.objects.get(name="TestTeam")

        self.community = Community.objects.create(
            name="TestCommunity", identifier="test-community"
        )

        # Setup Site
        self.site = Site.objects.create(
            domain="thunderstore.localhost", name="Thunderstore"
        )
        CommunitySite.objects.create(site=self.site, community=self.community)

        self.client = APIClient(HTTP_HOST="thunderstore.localhost")

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

        # Moderator setup
        CommunityMembership.objects.create(
            community=self.community,
            user=self.moderator,
            role=CommunityMemberRole.moderator,
        )

        # Create a comment by self.user on the listing
        self.comment = create_comment(self.user, self.listing, "Test Comment")

    def test_author_can_delete_own_comment(self):
        self.client.force_authenticate(user=self.user)
        url = reverse(
            "api:cyberstorm:cyberstorm.comments.delete",
            kwargs={"uuid": self.comment.uuid},
        )
        response = self.client.delete(url)
        assert response.status_code == status.HTTP_204_NO_CONTENT

        self.comment.refresh_from_db()
        assert self.comment.is_deleted

    def test_outsider_cannot_delete_comment(self):
        self.client.force_authenticate(user=self.outsider)
        url = reverse(
            "api:cyberstorm:cyberstorm.comments.delete",
            kwargs={"uuid": self.comment.uuid},
        )
        response = self.client.delete(url)
        assert response.status_code == status.HTTP_403_FORBIDDEN

        self.comment.refresh_from_db()
        assert not self.comment.is_deleted

    def test_team_owner_can_delete_comment_on_listing(self):
        self.client.force_authenticate(user=self.team_owner)
        url = reverse(
            "api:cyberstorm:cyberstorm.comments.delete",
            kwargs={"uuid": self.comment.uuid},
        )
        response = self.client.delete(url)
        assert response.status_code == status.HTTP_204_NO_CONTENT

        self.comment.refresh_from_db()
        assert self.comment.is_deleted

    def test_moderator_can_delete_comment(self):
        self.client.force_authenticate(user=self.moderator)
        url = reverse(
            "api:cyberstorm:cyberstorm.comments.delete",
            kwargs={"uuid": self.comment.uuid},
        )
        response = self.client.delete(url)
        assert response.status_code == status.HTTP_204_NO_CONTENT

        self.comment.refresh_from_db()
        assert self.comment.is_deleted

    def test_author_cannot_restore_comment(self):
        # First delete it
        self.comment.is_deleted = True
        self.comment.save()

        self.client.force_authenticate(user=self.user)
        url = reverse(
            "api:cyberstorm:cyberstorm.comments.restore",
            kwargs={"uuid": self.comment.uuid},
        )
        response = self.client.post(url)
        assert response.status_code == status.HTTP_403_FORBIDDEN

        self.comment.refresh_from_db()
        assert self.comment.is_deleted

    def test_moderator_can_restore_comment(self):
        self.comment.is_deleted = True
        self.comment.save()

        self.client.force_authenticate(user=self.moderator)
        url = reverse(
            "api:cyberstorm:cyberstorm.comments.restore",
            kwargs={"uuid": self.comment.uuid},
        )
        response = self.client.post(url)
        assert response.status_code == status.HTTP_204_NO_CONTENT

        self.comment.refresh_from_db()
        assert not self.comment.is_deleted

    def test_superuser_can_do_anything(self):
        self.client.force_authenticate(user=self.superuser)
        # Delete
        url = reverse(
            "api:cyberstorm:cyberstorm.comments.delete",
            kwargs={"uuid": self.comment.uuid},
        )
        self.client.delete(url)
        self.comment.refresh_from_db()
        assert self.comment.is_deleted

        # Restore
        url_restore = reverse(
            "api:cyberstorm:cyberstorm.comments.restore",
            kwargs={"uuid": self.comment.uuid},
        )
        self.client.post(url_restore)
        self.comment.refresh_from_db()
        assert not self.comment.is_deleted
