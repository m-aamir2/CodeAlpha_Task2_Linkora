import asyncio
from types import SimpleNamespace
from urllib.parse import urlsplit

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import AuthenticationFailed, InvalidToken, TokenError

from .models import Notification
from .realtime import notification_group
from .serializers import NotificationSerializer


@database_sync_to_async
def user_from_access_token(token):
    authentication = JWTAuthentication()
    validated_token = authentication.get_validated_token(token)
    return authentication.get_user(validated_token)


@database_sync_to_async
def notification_payload(notification_id, user, origin):
    notification = Notification.objects.select_related(
        "actor__profile", "post", "story__author"
    ).get(pk=notification_id, recipient=user)

    def build_absolute_uri(value):
        if urlsplit(value).scheme:
            return value
        return f"{origin.rstrip('/')}/{value.lstrip('/')}"

    request = SimpleNamespace(user=user, build_absolute_uri=build_absolute_uri)
    return NotificationSerializer(notification, context={"request": request}).data


@database_sync_to_async
def unread_count_for(user):
    return Notification.objects.filter(recipient=user, is_read=False).count()


class NotificationConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.user = None
        self.group_name = None
        origin = next((value.decode() for key, value in self.scope.get("headers", []) if key == b"origin"), "")
        self.origin = origin or "http://localhost:5180"
        await self.accept()
        self.auth_timeout_task = asyncio.create_task(self.close_if_unauthenticated())

    async def close_if_unauthenticated(self):
        await asyncio.sleep(8)
        if self.user is None:
            await self.close(code=4401)

    async def disconnect(self, close_code):
        timeout_task = getattr(self, "auth_timeout_task", None)
        if timeout_task and timeout_task is not asyncio.current_task():
            timeout_task.cancel()
        if self.group_name:
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content, **kwargs):
        if self.user is not None or content.get("type") != "authenticate":
            await self.close(code=4400)
            return
        token = content.get("token")
        if not isinstance(token, str) or not token:
            await self.close(code=4401)
            return
        try:
            self.user = await user_from_access_token(token)
        except (AuthenticationFailed, InvalidToken, TokenError, ValueError, TypeError):
            await self.close(code=4401)
            return
        if not self.user.is_active:
            await self.close(code=4401)
            return
        self.group_name = notification_group(self.user.pk)
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        timeout_task = getattr(self, "auth_timeout_task", None)
        if timeout_task:
            timeout_task.cancel()
        await self.send_json({
            "type": "ready",
            "unread_count": await unread_count_for(self.user),
        })

    async def notification_created(self, event):
        if not self.user:
            return
        try:
            notification = await notification_payload(event["notification_id"], self.user, self.origin)
        except Notification.DoesNotExist:
            return
        await self.send_json({
            "type": "notification.created",
            "notification": notification,
            "unread_count": await unread_count_for(self.user),
        })

    async def notification_read(self, event):
        if self.user:
            await self.send_json({
                "type": "notification.read",
                "notification_id": event["notification_id"],
                "unread_count": event["unread_count"],
            })

    async def notifications_read_all(self, event):
        if self.user:
            await self.send_json({"type": "notifications.read_all", "unread_count": 0})
