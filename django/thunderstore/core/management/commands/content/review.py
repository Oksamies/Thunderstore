import random

from thunderstore.comments.services import create_comment
from thunderstore.community.consts import PackageListingReviewStatus
from thunderstore.community.models import PackageListing
from thunderstore.core.management.commands.content.base import (
    ContentPopulator,
    ContentPopulatorContext,
)
from thunderstore.repository.consts import PackageVersionReviewStatus
from thunderstore.repository.models import PackageVersion


class ReviewPopulator(ContentPopulator):
    def populate(self, context: ContentPopulatorContext) -> None:
        print(
            "Populating reviews (PackageListing and PackageVersion review statuses)..."
        )

        if not context.users:
            print("No users found, skipping reviews.")
            return

        listings = PackageListing.objects.all()
        if listings.exists():
            statuses = [
                PackageListingReviewStatus.unreviewed,
                PackageListingReviewStatus.approved,
                PackageListingReviewStatus.rejected,
            ]

            reviews_created = 0
            for listing in listings:
                status = random.choice(statuses)
                listing.review_status = status

                if status == PackageListingReviewStatus.unreviewed:
                    listing.is_review_requested = random.choice([True, False])

                listing.save(update_fields=["review_status", "is_review_requested"])
                reviews_created += 1

                if random.random() > 0.5:
                    num_comments = random.randint(1, 3)
                    commenters = random.sample(
                        list(context.users), min(num_comments, len(context.users))
                    )

                    parent_comment = None
                    for i, commenter in enumerate(commenters):
                        if i == 0:
                            body = f"Review discussion for {listing.package.name} ({status})."
                            parent_comment = create_comment(
                                user=commenter, obj=listing, body=body
                            )
                        else:
                            body = random.choice(
                                [
                                    "I agree.",
                                    "Please check the latest version.",
                                    "Looks good to me.",
                                    "Needs more work.",
                                ]
                            )
                            create_comment(
                                user=commenter,
                                obj=listing,
                                body=body,
                                parent_id=parent_comment.pk,
                            )

            print(
                f"Updated {reviews_created} listings with review statuses and discussions."
            )

        versions = PackageVersion.objects.all()
        if versions.exists():
            version_statuses = [
                PackageVersionReviewStatus.unreviewed,
                PackageVersionReviewStatus.approved,
                PackageVersionReviewStatus.rejected,
            ]

            version_reviews_created = 0
            for version in versions:
                status = random.choice(version_statuses)
                version.review_status = status
                version.save(update_fields=["review_status"])
                version_reviews_created += 1

                if random.random() > 0.5:
                    num_comments = random.randint(1, 3)
                    commenters = random.sample(
                        list(context.users), min(num_comments, len(context.users))
                    )

                    parent_comment = None
                    for i, commenter in enumerate(commenters):
                        if i == 0:
                            body = f"Version review discussion for {version.full_version_name} ({status})."
                            parent_comment = create_comment(
                                user=commenter, obj=version, body=body
                            )
                        else:
                            body = random.choice(
                                [
                                    "I agree.",
                                    "Please check the latest version.",
                                    "Looks good to me.",
                                    "Needs more work.",
                                ]
                            )
                            create_comment(
                                user=commenter,
                                obj=version,
                                body=body,
                                parent_id=parent_comment.pk,
                            )

            print(
                f"Updated {version_reviews_created} versions with review statuses and discussions."
            )

    def update_context(self, context: ContentPopulatorContext) -> None:
        pass

    def clear(self) -> None:
        print("Resetting review statuses...")
        PackageListing.objects.update(
            review_status=PackageListingReviewStatus.unreviewed,
            is_review_requested=False,
        )
        PackageVersion.objects.update(
            review_status=PackageVersionReviewStatus.unreviewed
        )
