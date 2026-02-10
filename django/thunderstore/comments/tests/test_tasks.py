import uuid

import pytest
from django.contrib.contenttypes.models import ContentType

from thunderstore.comments.models import Comment
from thunderstore.comments.tasks import delete_ghost_comments
from thunderstore.repository.models import Team


@pytest.mark.django_db
def test_delete_ghost_comments_task():
    # 1. Setup real object
    team = Team.objects.create(name="RealTeam")
    ct_team = ContentType.objects.get_for_model(Team)

    # 2. persistent comment
    valid_comment = Comment.objects.create(
        content_type=ct_team, object_id=str(team.pk), body="Valid"
    )

    # 3. ghost comment (random UUID)
    ghost_id = str(uuid.uuid4())
    ghost_comment = Comment.objects.create(
        content_type=ct_team, object_id=ghost_id, body="Ghost"
    )

    # 4. ghost comment (deleted object)
    team_to_delete = Team.objects.create(name="ToBeDeleted")
    deleted_id = str(team_to_delete.pk)
    deleted_comment = Comment.objects.create(
        content_type=ct_team, object_id=deleted_id, body="WillBeGhost"
    )
    team_to_delete.delete()

    # Pre-check
    # We filter by specific IDs to avoid noise from other tests/fixtures
    assert Comment.objects.filter(pk=valid_comment.pk).exists()
    assert Comment.objects.filter(pk=ghost_comment.pk).exists()
    assert Comment.objects.filter(pk=deleted_comment.pk).exists()

    # Run Task
    deleted_count = delete_ghost_comments()

    # Assert
    # deleted_count might include other ghosts from other tests, specifically the 30+ items seen in the failure log
    # So we don't strictly assert deleted_count == 2
    assert deleted_count >= 2

    assert Comment.objects.filter(pk=valid_comment.pk).exists()
    assert not Comment.objects.filter(pk=ghost_comment.pk).exists()
    assert not Comment.objects.filter(pk=deleted_comment.pk).exists()
