from typing import List, Optional

from thunderstore.community.models import Community
from thunderstore.core.management.commands.content.base import (
    ContentPopulator,
    ContentPopulatorContext,
)
from thunderstore.repository.models.cache import (
    APIV1ChunkedPackageCache,
    APIV1PackageCache,
)
from thunderstore.utils.iterators import print_progress


class CommunityPopulator(ContentPopulator):
    communities: Optional[List[Community]] = None
    identifier_prefix = "test-community-"
    name_prefix = "Test Community "

    def populate(self, context: ContentPopulatorContext) -> None:
        print("Populating communities...")

        last = last_obj.pk if (last_obj := Community.objects.last()) else 0

        existing = list(
            Community.objects.filter(name__startswith=self.name_prefix)[
                : context.community_count
            ]
        )
        remainder = context.community_count - len(existing)

        self.communities = existing + [
            Community.objects.create(
                name=f"{self.name_prefix}{last + i}",
                identifier=f"{self.identifier_prefix}{last + i}",
            )
            for i in print_progress(range(remainder), remainder)
        ]

    def update_context(self, context) -> None:
        if self.communities is not None:
            context.communities = self.communities
        else:
            context.communities = Community.objects.filter(
                name__startswith=self.name_prefix
            )[: context.community_count]

    def clear(self) -> None:
        print("Deleting existing test communities...")
        qs = Community.objects.filter(name__startswith=self.name_prefix)

        # Manually clear caches iteratively because S3FileMixin prevents bulk delete
        for cache in APIV1PackageCache.objects.filter(community__in=qs):
            cache.delete()
        for cache in APIV1ChunkedPackageCache.objects.filter(community__in=qs):
            cache.delete()

        qs._raw_delete(using="default")
