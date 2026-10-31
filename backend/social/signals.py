from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Notification
from .realtime import publish_notification_event


@receiver(post_save, sender=Notification)
def notification_created(sender, instance, created, **kwargs):
    if not created:
        return
    notification_id = instance.pk
    recipient_id = instance.recipient_id
    transaction.on_commit(lambda: publish_notification_event(
        recipient_id,
        {"type": "notification.created", "notification_id": notification_id},
    ))
