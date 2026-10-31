import re
from django.db.models.functions import Lower
from django.utils import timezone
from accounts.models import User
from .models import Notification, Story

MENTION_PATTERN = re.compile(r"(?<![\w@])@([A-Za-z0-9_]{1,150})")


def notify_mentions(content, actor, *, post=None, comment=None, story=None, exclude=()):
    usernames = {match.casefold() for match in MENTION_PATTERN.findall(content or "")}
    usernames.difference_update(name.casefold() for name in exclude)
    if not usernames:
        return 0
    recipients = User.objects.annotate(username_lower=Lower("username")).filter(
        username_lower__in=usernames, is_active=True
    ).exclude(pk=actor.pk)
    created = 0
    for recipient in recipients:
        Notification.objects.create(
            recipient=recipient, actor=actor, kind=Notification.MENTION,
            post=post, comment=comment, story=story,
        )
        created += 1
    return created


def cleanup_expired_stories():
    """Remove expired story rows and their backing files, retrying storage failures later."""
    expired = list(Story.objects.filter(expires_at__lte=timezone.now()))
    deleted_ids = []
    for story in expired:
        try:
            if story.media:
                story.media.storage.delete(story.media.name)
            deleted_ids.append(story.pk)
        except Exception:
            continue
    if deleted_ids:
        Story.objects.filter(pk__in=deleted_ids).delete()
    return len(deleted_ids)
