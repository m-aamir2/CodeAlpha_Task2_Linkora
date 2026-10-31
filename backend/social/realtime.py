import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

logger = logging.getLogger(__name__)


def notification_group(user_id):
    return f"notifications.user.{user_id}"


def publish_notification_event(user_id, event):
    layer = get_channel_layer()
    if layer is None:
        return
    try:
        async_to_sync(layer.group_send)(notification_group(user_id), event)
    except Exception:
        # Notification persistence must still succeed during a transient Redis outage.
        logger.exception("Could not publish a notification WebSocket event")
