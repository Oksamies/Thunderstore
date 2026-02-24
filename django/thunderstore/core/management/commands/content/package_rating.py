import random

from thunderstore.core.management.commands.content.base import (
    ContentPopulator,
    ContentPopulatorContext,
)
from thunderstore.repository.models import PackageRating


class PackageRatingPopulator(ContentPopulator):
    def populate(self, context: ContentPopulatorContext) -> None:
        print("Populating package ratings (likes)...")

        if not context.users or not context.packages:
            print("No users or packages found, skipping package ratings.")
            return

        ratings_created = 0
        for package in context.packages:
            # Randomly assign ratings from a subset of users
            num_ratings = random.randint(0, min(5, len(context.users)))
            raters = random.sample(list(context.users), num_ratings)

            for rater in raters:
                PackageRating.objects.get_or_create(rater=rater, package=package)
                ratings_created += 1

        print(f"Created {ratings_created} package ratings.")

    def update_context(self, context: ContentPopulatorContext) -> None:
        pass

    def clear(self) -> None:
        print("Clearing package ratings...")
        PackageRating.objects.all().delete()
