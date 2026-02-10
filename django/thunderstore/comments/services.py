from typing import Any, Dict, List, Optional
from uuid import UUID

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.db import transaction

from thunderstore.comments.models import Comment
from thunderstore.comments.permissions import (
    can_user_delete_comment,
    can_user_restore_comment,
)

User = get_user_model()


def create_comment(
    user: User,
    obj: Any,
    body: str,
    parent_id: Optional[UUID] = None,
    is_internal: bool = False,
) -> Comment:
    """
    Creates a comment for a given object.
    Handles the cross-db author_id mapping.
    """
    content_type = ContentType.objects.get_for_model(obj)

    # Verify parent exists if provided
    parent = None
    if parent_id:
        try:
            parent = Comment.objects.get(uuid=parent_id)
        except Comment.DoesNotExist:
            raise ValueError(f"Parent comment {parent_id} does not exist")

    comment = Comment.objects.create(
        content_type=content_type,
        object_id=str(obj.pk),  # Ensure string for UUID compatibility
        author_id=user.id,
        body=body,
        parent=parent,
        is_internal=is_internal,
    )
    return comment


def get_comments_for_object(
    obj: Any, include_internal: bool = False, include_deleted: bool = False
) -> List[Dict[str, Any]]:
    """
    Fetches comments for an object and merges User data.
    Returns a list of dicts or objects with 'author' populated.
    """
    content_type = ContentType.objects.get_for_model(obj)

    qs = Comment.objects.filter(
        content_type=content_type,
        object_id=str(obj.pk),
    )

    if not include_deleted:
        qs = qs.filter(is_deleted=False)

    if not include_internal:
        qs = qs.filter(is_internal=False)

    comments = list(qs.order_by("datetime_created"))

    if not comments:
        return []

    # Bulk fetch users
    user_ids = {c.author_id for c in comments if c.author_id}
    users = User.objects.in_bulk(list(user_ids))

    # Merge
    # We can't attach a model instance to a persisted model instance field that doesn't exist
    # cleanly without side effects sometimes, but we can return a wrapper or just attach it as a property
    # provided we don't save() it.

    results = []
    for comment in comments:
        comment.author = users.get(comment.author_id)
        results.append(comment)

    return results


def delete_comment(user: User, comment: Comment) -> None:
    """
    Soft deletes a comment if the user has permission.
    """
    if not can_user_delete_comment(user, comment):
        raise PermissionDenied("User does not have permission to delete this comment")

    comment.is_deleted = True
    comment.save()


def restore_comment(user: User, comment: Comment) -> None:
    """
    Restores a soft-deleted comment if the user has permission.
    """
    if not can_user_restore_comment(user, comment):
        raise PermissionDenied("User does not have permission to restore this comment")

    comment.is_deleted = False
    comment.save()
