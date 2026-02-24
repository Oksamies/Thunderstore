import logging

from celery import shared_task
from django.contrib.contenttypes.models import ContentType
from django.db.models import Count

from thunderstore.comments.models import Comment

logger = logging.getLogger(__name__)


@shared_task
def delete_ghost_comments(dry_run=False):
    """
    Scans for comments that point to non-existent objects and marks them as deleted
    (or hard deletes them? Let's assume soft delete or hard delete if there is no point keeping them).

    If an object is GONE, the comment is contextually meaningless.
    Hard delete might be better to save space if it's truly a ghost.
    But let's stick to 'delete()' which might be soft or hard depending on model.
    Comment model has 'is_deleted', but standard .delete() on model usually does hard delete unless overridden.
    Thunderstore usually prefers soft-deletes via a mixin or service.
    However, if the parent object is GONE, who cares about history?
    Let's hard delete to clean up DB space.
    """

    # 1. Identify all ContentTypes used in comments
    ct_ids = Comment.objects.values_list("content_type_id", flat=True).distinct()

    deleted_count = 0

    for ct_id in ct_ids:
        try:
            ct = ContentType.objects.get(id=ct_id)
        except ContentType.DoesNotExist:
            # ContentType itself is gone? That's bad. Delete all comments for it.
            if not dry_run:
                cnt, _ = Comment.objects.filter(content_type_id=ct_id).delete()
                deleted_count += cnt
            continue

        model_class = ct.model_class()
        if not model_class:
            # Model class no longer exists in code
            # We should probably delete these comments too as they are orphans of code refactoring
            if not dry_run:
                cnt, _ = Comment.objects.filter(content_type_id=ct_id).delete()
                deleted_count += cnt
            continue

        # 2. Get all distinct object_ids for this ContentType
        # Note: object_id is CharField.

        # We process in chunks if necessary, but for now simple query.
        # Find comments for this CT
        comments_qs = Comment.objects.filter(content_type=ct)
        comment_object_ids = set(comments_qs.values_list("object_id", flat=True))

        if not comment_object_ids:
            continue

        # 3. Query the actual model to find which match
        # Handle UUID vs Int issues
        # Ideally object_id is string.
        # We need to cast model PK to string to compare?
        # A simpler way: Fetch existing PKs.

        # Warning: If the dataset is HUGE, this 'in' clause might differ.
        # But 'comment_object_ids' is the set of IDs referenced by comments.

        # Optimization: Fetch IDs from the model that are IN the comment_object_ids list.
        # Then valid_ids = set(...)
        # invalid_ids = comment_object_ids - valid_ids

        # Ensure we filter by string-casting if necessary?
        # If model PK is UUID, Django handles str lookup usually.
        # If model PK is Int, 'object_id' (Char)='1' matches PK=1?

        try:
            # We try to filter the model by pk__in argument.
            ids_list = list(comment_object_ids)
            pk_field = model_class._meta.pk

            from django.db import models

            # Identify integer-based PKs
            is_int_pk = isinstance(
                pk_field,
                (
                    models.IntegerField,
                    models.AutoField,
                    models.BigIntegerField,
                    models.SmallIntegerField,
                ),
            )

            query_ids = []
            known_ghosts = set()

            for oid in ids_list:
                if is_int_pk:
                    # If model needs int, but oid is not int-like, it matches nothing -> ghost
                    if str(oid).isdigit():
                        query_ids.append(oid)
                    else:
                        known_ghosts.add(oid)
                else:
                    # Assume string/UUID compatible
                    query_ids.append(oid)

            existing_objects = []
            if query_ids:
                existing_objects = model_class._default_manager.filter(
                    pk__in=query_ids
                ).values_list("pk", flat=True)

            # Convert existing_objects to strings for comparison
            valid_ids = {str(pk) for pk in existing_objects}

            # 4. Identify ghosts
            invalid_ids = list(known_ghosts) + [
                oid for oid in query_ids if str(oid) not in valid_ids
            ]

            if invalid_ids:
                msg = f"Found {len(invalid_ids)} ghost comments for {ct.app_label}.{ct.model}"
                logger.info(msg)

                if not dry_run:
                    # Delete child comments first to avoid PROTECT foreign key errors
                    ghost_comments = Comment.objects.filter(
                        content_type=ct, object_id__in=invalid_ids
                    )

                    # Find all descendants of these ghost comments
                    def get_all_descendants(comments):
                        descendants = Comment.objects.filter(parent__in=comments)
                        if descendants.exists():
                            return descendants | get_all_descendants(descendants)
                        return Comment.objects.none()

                    all_descendants = get_all_descendants(ghost_comments)

                    # Delete descendants first
                    if all_descendants.exists():
                        desc_cnt, _ = all_descendants.delete()
                        deleted_count += desc_cnt

                    # Then delete the ghost comments themselves
                    cnt, _ = ghost_comments.delete()
                    deleted_count += cnt
                    logger.info(f"Deleted {cnt} ghost comments.")

        except Exception as e:
            logger.error(f"Error checking ghost comments for {ct}: {e}")

    return deleted_count
