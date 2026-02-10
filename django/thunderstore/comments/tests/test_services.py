from uuid import uuid4

import pytest

from thunderstore.comments.models import Comment
from thunderstore.comments.services import create_comment, get_comments_for_object
from thunderstore.core.factories import UserFactory
from thunderstore.repository.models import Team


@pytest.mark.django_db
class TestCommentServices:
    @pytest.fixture
    def user(self):
        return UserFactory()

    @pytest.fixture
    def team(self):
        # A simple object to attach comments to.
        # We need to create it manually as we didn't inspect TeamFactory
        t = Team.objects.create(name="TestTeam")
        return t

    def test_create_comment(self, user, team):
        body = "Test Comment"
        comment = create_comment(user, team, body)

        assert comment.body == body
        assert comment.author_id == user.id
        assert str(comment.object_id) == str(team.pk)
        assert comment.parent is None
        assert not comment.is_internal

    def test_create_nested_comment(self, user, team):
        parent = create_comment(user, team, "Parent")
        child = create_comment(user, team, "Child", parent_id=parent.uuid)

        assert child.parent == parent
        assert child.parent_id == parent.pk

    def test_create_comment_invalid_parent(self, user, team):
        with pytest.raises(ValueError):
            create_comment(user, team, "Child", parent_id=uuid4())

    def test_get_comments_for_object(self, user, team):
        c1 = create_comment(user, team, "First")
        c2 = create_comment(user, team, "Second")

        # Add a comment for another object to ensure filtering works
        other_team = Team.objects.create(name="OtherTeam")
        create_comment(user, other_team, "Other")

        comments = get_comments_for_object(team)

        assert len(comments) == 2
        assert comments[0].uuid == c1.uuid
        assert comments[1].uuid == c2.uuid

        # Verify author hydration
        assert comments[0].author == user
        assert comments[1].author == user

    def test_get_comments_internal_filtering(self, user, team):
        create_comment(user, team, "Public")
        create_comment(user, team, "Internal", is_internal=True)

        public_only = get_comments_for_object(team, include_internal=False)
        assert len(public_only) == 1
        assert public_only[0].body == "Public"

        all_comments = get_comments_for_object(team, include_internal=True)
        assert len(all_comments) == 2
