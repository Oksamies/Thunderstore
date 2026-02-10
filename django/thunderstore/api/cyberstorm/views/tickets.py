from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import mixins, status, viewsets

User = get_user_model()
from rest_framework.exceptions import APIException
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView


class ServiceUnavailable(APIException):
    status_code = 503
    default_detail = "Service temporarily unavailable, try again later."
    default_code = "service_unavailable"


from thunderstore.api.cyberstorm.serializers.tickets import (
    CommentSerializer,
    TicketCreateSerializer,
    TicketSerializer,
    TicketStatusSerializer,
    TicketTemplateSerializer,
)
from thunderstore.api.utils import conditional_swagger_auto_schema
from thunderstore.comments.services import create_comment, get_comments_for_object
from thunderstore.community.models import Community, PackageListing
from thunderstore.community.models.community_membership import (
    CommunityMemberRole,
    CommunityMembership,
)
from thunderstore.repository.models import Namespace, Package, Team, TeamMember
from thunderstore.tickets.models import Ticket, TicketStatus, TicketTemplate


class TicketBaseAPI(APIView):
    def check_feature_flag(self):
        if not settings.IS_TICKETS_ENABLED:
            raise ServiceUnavailable(detail="Tickets system is currently disabled.")

    def dispatch(self, request, *args, **kwargs):
        self.check_feature_flag()
        return super().dispatch(request, *args, **kwargs)

    def attach_relations(self, ticket):
        # Application-side join: Manually fetch related objects from default DB
        # This replaces select_related('community', 'team') which is unsafe across DBs
        if ticket.community_id:
            try:
                ticket.community = Community.objects.get(pk=ticket.community_id)
            except Community.DoesNotExist:
                ticket.community = None
        else:
            ticket.community = None

        if ticket.team_id:
            try:
                ticket.team = Team.objects.get(pk=ticket.team_id)
            except Team.DoesNotExist:
                ticket.team = None
        else:
            ticket.team = None
        return ticket


class TicketViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = TicketSerializer
    lookup_field = "uuid"

    def dispatch(self, request, *args, **kwargs):
        if not settings.IS_TICKETS_ENABLED:
            raise ServiceUnavailable(detail="Tickets system is currently disabled.")
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        user = self.request.user
        queryset = Ticket.objects.all()

        if user.is_superuser:
            qs = queryset
        else:
            # Users can see tickets if they are:
            # 1. Member of the Team (Owner)
            # 2. Moderator of the Community

            # Cross-DB compatible filtering: Fetch IDs from default DB first
            team_ids = list(
                TeamMember.objects.filter(user=user).values_list("team_id", flat=True)
            )
            community_ids = list(
                CommunityMembership.objects.filter(
                    user=user,
                    role__in=[
                        CommunityMemberRole.moderator,
                        CommunityMemberRole.owner,
                    ],
                ).values_list("community_id", flat=True)
            )

            qs = queryset.filter(
                Q(team_id__in=team_ids) | Q(community_id__in=community_ids)
            )

        return qs.distinct().order_by("-updated_at")

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        page = self.paginate_queryset(queryset)
        if page is not None:
            tickets = page
        else:
            tickets = list(queryset)

        # Bulk Hydration of Cross-DB Relations
        community_ids = {t.community_id for t in tickets if t.community_id}
        team_ids = {t.team_id for t in tickets if t.team_id}
        listing_id_map = {t.listing_id for t in tickets if t.listing_id}
        user_ids = {t.created_by_id for t in tickets if t.created_by_id}

        communities = {c.id: c for c in Community.objects.filter(id__in=community_ids)}
        teams = {t.id: t for t in Team.objects.filter(id__in=team_ids)}
        # Note: Listing lookup might need complex filtering if listing is deleted, handled gracefully below
        listings = {
            l.id: l for l in PackageListing.objects.filter(id__in=listing_id_map)
        }
        users = {u.id: u for u in User.objects.filter(id__in=user_ids)}

        for t in tickets:
            t.community = communities.get(t.community_id)
            t.team = teams.get(t.team_id)
            t.listing = listings.get(t.listing_id)
            t.created_by = users.get(t.created_by_id)

        if page is not None:
            serializer = self.get_serializer(tickets, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(tickets, many=True)
        return Response(serializer.data)

    @conditional_swagger_auto_schema(
        operation_id="cyberstorm.tickets.detail",
        responses={200: TicketSerializer},
    )
    def retrieve(self, request, *args, **kwargs):
        try:
            instance = self.get_object()

            # Manual Fetch for Relations
            if instance.community_id:
                instance.community = Community.objects.get(pk=instance.community_id)
            if instance.team_id:
                instance.team = Team.objects.get(pk=instance.team_id)

            # Include internal notes ONLY if user is a moderator
            include_internal = (
                instance.community
                and instance.community.can_user_manage_packages(request.user)
            ) or request.user.is_superuser

            # Fetch comments via service layer
            instance.prefetched_comments = get_comments_for_object(
                instance, include_internal=include_internal
            )

            serializer = self.get_serializer(instance)
            return Response(serializer.data)
        except Exception as e:
            import traceback

            traceback.print_exc()
            raise e


class ListingTicketListAPIView(TicketBaseAPI):
    permission_classes = [IsAuthenticated]
    serializer_class = TicketSerializer

    @conditional_swagger_auto_schema(
        operation_id="cyberstorm.listing.tickets.list",
        responses={200: TicketSerializer(many=True)},
    )
    def get(self, request, community_id, namespace_id, package_name):
        # Verify access
        community = get_object_or_404(Community, identifier=community_id)
        namespace = get_object_or_404(Namespace, name=namespace_id)
        package = get_object_or_404(Package, owner=namespace.team, name=package_name)

        # Access Check
        has_access = False
        if community.can_user_manage_packages(request.user):
            has_access = True
        elif package.owner.can_user_access(request.user):
            has_access = True
        elif request.user.is_superuser:
            has_access = True

        if not has_access:
            return Response(status=status.HTTP_403_FORBIDDEN)

        # Get listing to filter tickets
        listing = PackageListing.objects.filter(
            package=package, community=community
        ).first()
        if not listing:
            # If listing is gone, we might still want to find tickets by snapshot fields
            tickets = Ticket.objects.filter(community=community, team=package.owner)
            # Need to filter somewhat vaguely if listing logic is strictly bound
        else:
            tickets = Ticket.objects.filter(listing=listing)

        # Manual hydration for list response is tricky without N+1 problem.
        # Ideally we fetch all needed Communities/Teams in bulk.
        # But for now, let's just prefetch normal relations and accept that 'community' object on ticket might fail serialization if accessed directly
        # The serializer uses TicketSerializer which dumps 'community' ID usually, but if it nests objects we need to inject them.

        # NOTE: TicketSerializer currently nests `community`.
        # We need to manually inject these objects into the tickets queryset results.

        tickets = list(tickets)
        for t in tickets:
            # We already have 'community' and 'package.owner' (team) objects from the view arguments!
            t.community = community
            t.team = package.owner

        serializer = self.serializer_class(tickets, many=True)

        return Response(serializer.data)

    @conditional_swagger_auto_schema(
        operation_id="cyberstorm.listing.tickets.create",
        request_body=TicketCreateSerializer,
        responses={201: TicketSerializer},
    )
    def post(self, request, community_id, namespace_id, package_name):
        community = get_object_or_404(Community, identifier=community_id)
        namespace = get_object_or_404(Namespace, name=namespace_id)
        package = get_object_or_404(Package, owner=namespace.team, name=package_name)

        # Only Team Members or Moderators can open tickets
        is_mod = community.can_user_manage_packages(request.user)
        is_owner = package.owner.can_user_access(request.user)

        if not (is_mod or is_owner or request.user.is_superuser):
            return Response(status=status.HTTP_403_FORBIDDEN)

        listing = get_object_or_404(
            PackageListing, package=package, community=community
        )

        create_serializer = TicketCreateSerializer(data=request.data)
        create_serializer.is_valid(raise_exception=True)
        content = create_serializer.validated_data["content"]

        ticket = Ticket.objects.create(
            listing=listing,
            community=community,
            team=package.owner,
            created_by=request.user,
            status=TicketStatus.OPEN,
        )

        create_comment(request.user, ticket, content)

        return Response(TicketSerializer(ticket).data, status=status.HTTP_201_CREATED)


class TicketMessagesAPIView(TicketBaseAPI):
    permission_classes = [IsAuthenticated]

    @conditional_swagger_auto_schema(
        operation_id="cyberstorm.tickets.messages.list",
        responses={200: CommentSerializer(many=True)},
    )
    def get(self, request, uuid):
        ticket = get_object_or_404(Ticket, uuid=uuid)
        ticket = self.attach_relations(ticket)

        is_mod = ticket.community and ticket.community.can_user_manage_packages(
            request.user
        )
        is_owner = ticket.team and ticket.team.can_user_access(request.user)

        if not (is_mod or is_owner or request.user.is_superuser):
            return Response(status=status.HTTP_403_FORBIDDEN)

        # Include internal notes ONLY if user is a moderator
        include_internal = is_mod or request.user.is_superuser

        comments = get_comments_for_object(ticket, include_internal=include_internal)
        return Response(CommentSerializer(comments, many=True).data)

    @conditional_swagger_auto_schema(
        operation_id="cyberstorm.tickets.messages.create",
        request_body=TicketCreateSerializer,
        responses={201: CommentSerializer},
    )
    def post(self, request, uuid):
        ticket = get_object_or_404(Ticket, uuid=uuid)
        ticket = self.attach_relations(ticket)

        # Permission check reused from ViewSet logic implicitly or explicit here
        is_mod = ticket.community and ticket.community.can_user_manage_packages(
            request.user
        )
        is_owner = ticket.team and ticket.team.can_user_access(request.user)
        if not (is_mod or is_owner or request.user.is_superuser):
            return Response(status=status.HTTP_403_FORBIDDEN)

        serializer = TicketCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        message = create_comment(
            user=request.user, obj=ticket, body=serializer.validated_data["content"]
        )
        # Manually attach author for serializer
        message.author = request.user

        # Update status
        if is_mod:
            ticket.status = TicketStatus.MOD_REPLIED
        elif is_owner:
            ticket.status = TicketStatus.USER_REPLIED
        ticket.save()

        return Response(CommentSerializer(message).data, status=status.HTTP_201_CREATED)


class TicketNoteCreateAPIView(TicketBaseAPI):
    permission_classes = [IsAuthenticated]

    @conditional_swagger_auto_schema(
        operation_id="cyberstorm.tickets.note.create",
        request_body=TicketCreateSerializer,
        responses={201: CommentSerializer},
    )
    def post(self, request, uuid):
        ticket = get_object_or_404(Ticket, uuid=uuid)
        ticket = self.attach_relations(ticket)

        # ONLY Moderators
        if not (
            ticket.community
            and ticket.community.can_user_manage_packages(request.user)
            or request.user.is_superuser
        ):
            return Response(status=status.HTTP_403_FORBIDDEN)

        serializer = TicketCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        note = create_comment(
            user=request.user,
            obj=ticket,
            body=serializer.validated_data["content"],
            is_internal=True,
        )
        note.author = request.user

        return Response(CommentSerializer(note).data, status=status.HTTP_201_CREATED)


class TicketStatusUpdateAPIView(TicketBaseAPI):
    permission_classes = [IsAuthenticated]

    @conditional_swagger_auto_schema(
        operation_id="cyberstorm.tickets.status.update",
        request_body=TicketStatusSerializer,
        responses={200: TicketSerializer},
    )
    def post(self, request, uuid):
        ticket = get_object_or_404(Ticket, uuid=uuid)
        ticket = self.attach_relations(ticket)

        # Moderators or Owners can close? Usually only Mods resolve, but maybe Owners can close their own appeal?
        # For now, let's say Mods or Owners can change status, but maybe restrict RESOLVED to mods?
        # Simplicity: Both can change status.

        is_mod = ticket.community and ticket.community.can_user_manage_packages(
            request.user
        )
        is_owner = ticket.team and ticket.team.can_user_access(request.user)
        if not (is_mod or is_owner or request.user.is_superuser):
            return Response(status=status.HTTP_403_FORBIDDEN)

        serializer = TicketStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_status = serializer.validated_data["status"]

        ticket.status = new_status
        ticket.save()

        # Ensure relations are attached for response serializer
        # (Though we already attached them, save() doesn't clear them on the instance)

        return Response(TicketSerializer(ticket).data)


class TicketTemplateViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = TicketTemplateSerializer

    def dispatch(self, request, *args, **kwargs):
        if not settings.IS_TICKETS_ENABLED:
            raise ServiceUnavailable(detail="Tickets system is currently disabled.")
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        community_id = self.kwargs.get("community_id")
        community = get_object_or_404(Community, identifier=community_id)
        return TicketTemplate.objects.filter(community=community)

    def check_permissions(self, request):
        super().check_permissions(request)
        community_id = self.kwargs.get("community_id")
        community = get_object_or_404(Community, identifier=community_id)
        if not (
            community.can_user_manage_packages(request.user)
            or request.user.is_superuser
        ):
            self.permission_denied(request)

    def perform_create(self, serializer):
        community_id = self.kwargs.get("community_id")
        community = get_object_or_404(Community, identifier=community_id)
        serializer.save(community=community, created_by=self.request.user)
