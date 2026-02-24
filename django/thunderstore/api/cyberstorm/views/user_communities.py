from django.db.models import Q
from rest_framework import permissions, response, views

from thunderstore.api.cyberstorm.serializers.community import (
    CyberstormCommunitySerializer,
)
from thunderstore.community.consts import PackageListingReviewStatus
from thunderstore.community.models import Community
from thunderstore.community.models.community_membership import (
    CommunityMemberRole,
    CommunityMembership,
)
from thunderstore.community.models.package_listing import PackageListing
from thunderstore.tickets.models import Ticket, TicketStatus


class UserCommunityListAPIView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if request.user.is_superuser:
            communities = Community.objects.all().select_related("aggregated_fields")
        else:
            memberships = CommunityMembership.objects.filter(
                user=request.user
            ).select_related("community__aggregated_fields")
            communities = [m.community for m in memberships]
        serializer = CyberstormCommunitySerializer(communities, many=True)
        return response.Response(serializer.data)


class UserModerationStatsAPIView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        memberships = CommunityMembership.objects.filter(
            user=request.user
        ).select_related("community")

        moderated_community_ids = []
        for membership in memberships:
            # Optimization: check role directly to avoid N+1 queries from can_user_manage_packages
            if (
                membership.role
                in (CommunityMemberRole.moderator, CommunityMemberRole.owner)
                or request.user.is_superuser
                or request.user.is_staff
            ):
                moderated_community_ids.append(membership.community.id)

        if not moderated_community_ids:
            return response.Response({"pending_package_reviews": 0, "open_tickets": 0})

        # Count pending reviews
        # A package review is pending if:
        # 1. Community requires approval AND review_status is unreviewed.
        # 2. review_status is not rejected (already handled).
        # We should align with `PackageListing.is_waiting_for_approval`.

        pending_package_reviews = PackageListing.objects.filter(
            community_id__in=moderated_community_ids,
            community__require_package_listing_approval=True,
            review_status=PackageListingReviewStatus.unreviewed,
        ).count()

        # Count open tickets
        open_tickets = Ticket.objects.filter(
            community_id__in=moderated_community_ids, status=TicketStatus.OPEN
        ).count()

        return response.Response(
            {
                "pending_package_reviews": pending_package_reviews,
                "open_tickets": open_tickets,
            }
        )
