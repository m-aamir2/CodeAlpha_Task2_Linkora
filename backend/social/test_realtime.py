from asgiref.sync import async_to_sync
from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.test import TransactionTestCase, override_settings
from rest_framework_simplejwt.tokens import RefreshToken

from config.asgi import application
from social.models import Notification

User = get_user_model()


class NotificationWebSocketTests(TransactionTestCase):
    @override_settings(CHANNEL_LAYERS={
        "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"},
    })
    def test_access_token_connects_and_new_notifications_are_pushed(self):
        recipient = User.objects.create_user(username="socket-user", email="socket-user@example.com", password="SocketPassword!483")
        actor = User.objects.create_user(username="socket-actor", email="socket-actor@example.com", password="SocketPassword!483")
        access = str(RefreshToken.for_user(recipient).access_token)

        async def exchange():
            communicator = WebsocketCommunicator(
                application,
                "/ws/notifications/",
                headers=[(b"origin", b"http://localhost:5180")],
            )
            connected, _ = await communicator.connect()
            assert connected
            await communicator.send_json_to({"type": "authenticate", "token": access})
            ready = await communicator.receive_json_from(timeout=3)
            assert ready == {"type": "ready", "unread_count": 0}
            await database_sync_to_async(Notification.objects.create)(
                recipient=recipient, actor=actor, kind=Notification.FOLLOW,
            )
            pushed = await communicator.receive_json_from(timeout=3)
            assert pushed["type"] == "notification.created"
            assert pushed["notification"]["kind"] == Notification.FOLLOW
            assert pushed["notification"]["actor"]["username"] == actor.username
            assert pushed["unread_count"] == 1
            await communicator.disconnect()

        async_to_sync(exchange)()
