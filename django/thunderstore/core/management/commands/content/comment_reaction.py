import random

from thunderstore.comments.models import Comment, CommentReaction
from thunderstore.core.management.commands.content.base import (
    ContentPopulator,
    ContentPopulatorContext,
)


class CommentReactionPopulator(ContentPopulator):
    def populate(self, context: ContentPopulatorContext) -> None:
        print("Populating comment reactions...")

        if not context.users:
            print("No users found, skipping comment reactions.")
            return

        comments = Comment.objects.all()
        if not comments.exists():
            print("No comments found, skipping comment reactions.")
            return

        reactions_created = 0
        reaction_choices = [choice[0] for choice in CommentReaction.REACTION_CHOICES]

        for comment in comments:
            # Randomly assign reactions to some comments
            if random.random() > 0.4:
                continue

            num_reactions = random.randint(1, min(3, len(context.users)))
            reactors = random.sample(list(context.users), num_reactions)

            for reactor in reactors:
                reaction = random.choice(reaction_choices)
                CommentReaction.objects.get_or_create(
                    comment=comment, author_id=reactor.pk, reaction=reaction
                )
                reactions_created += 1

        print(f"Created {reactions_created} comment reactions.")

    def update_context(self, context: ContentPopulatorContext) -> None:
        pass

    def clear(self) -> None:
        print("Clearing comment reactions...")
        CommentReaction.objects.all().delete()
