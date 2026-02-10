import logging
from typing import Any, Optional

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType

from thunderstore.comments.models import Comment
from thunderstore.community.models import PackageListing
from thunderstore.repository.models import PackageVersion, Team
from thunderstore.tickets.models import Ticket

User = get_user_model()
logger = logging.getLogger(__name__)


def get_comment_content_object(comment: Comment) -> Optional[Any]:
    """
    Manually fetch the content object for a comment.
    This is necessary because GenericForeignKey does not support cross-database relationships
    transparently (Comment is in 'comments' DB, content objects are in 'default' DB).
    """
    if not comment.content_type_id or not comment.object_id:
        return None

    try:
        # Explicitly fetch ContentType from 'default' DB because Comment is in 'comments' DB
        # and standard ORM traversal (comment.content_type) might try to query 'comments' DB
        # where ContentTypes might not exist or be synced.
        ct = ContentType.objects.db_manager("default").get(pk=comment.content_type_id)
    except ContentType.DoesNotExist:
        logger.error(
            f"ContentType {comment.content_type_id} missing for comment {comment.uuid}"
        )
        return None

    model_class = ct.model_class()
    if not model_class:
        return None

    try:
        # Use default manager and let router decide DB invocation (usually 'default' for these models)
        return model_class._default_manager.get(pk=comment.object_id)
    except model_class.DoesNotExist:
        return None
    except Exception as e:
        logger.error(f"Error fetching content object for comment {comment.uuid}: {e}")
        return None


def can_user_view_internal_comments(user: User, obj: Any) -> bool:
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True

    if isinstance(obj, Ticket):
        # Community Moderator or Team Member
        is_mod = obj.community and obj.community.can_user_manage_packages(user)
        is_owner = obj.team and obj.team.can_user_access(user)
        return is_mod or is_owner

    # Add other mappings as needed
    return False


def can_user_delete_comment(user: User, comment: Comment) -> bool:
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True

    # Author can delete their own
    if comment.author_id == user.id:
        return True

    obj = get_comment_content_object(comment)
    if not obj:
        return False

    # Check context permissions
    if isinstance(obj, Ticket):
        # Community Moderator or Team Member
        is_mod = obj.community and obj.community.can_user_manage_packages(user)
        is_owner = obj.team and obj.team.can_user_access(user)
        return is_mod or is_owner

    if isinstance(obj, PackageListing):
        # Community Moderator or Team Member (Package Owner)
        is_mod = obj.community and obj.community.can_user_manage_packages(user)
        is_owner = obj.package.owner.can_user_access(user)
        return is_mod or is_owner

    if isinstance(obj, PackageVersion):
        # Team Member
        return obj.package.owner.can_user_access(user)

    if isinstance(obj, Team):
        # Team Member
        return obj.can_user_access(user)

    return False


def can_user_restore_comment(user: User, comment: Comment) -> bool:
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True

    # Users cannot restore their own comments, only Mods/Owners can

    obj = get_comment_content_object(comment)
    if not obj:
        return False

    if isinstance(obj, Ticket):
        is_mod = obj.community and obj.community.can_user_manage_packages(user)
        # Note: Team members (Owners) can also moderate their ticket
        is_owner = obj.team and obj.team.can_user_access(user)
        return is_mod or is_owner

    if isinstance(obj, PackageListing):
        is_mod = obj.community and obj.community.can_user_manage_packages(user)
        is_owner = obj.package.owner.can_user_access(user)
        return is_mod or is_owner

    if isinstance(obj, PackageVersion):
        return obj.package.owner.can_user_access(user)

    if isinstance(obj, Team):
        return obj.can_user_access(user)

    return False
