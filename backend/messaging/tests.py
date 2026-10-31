from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from datetime import timedelta
from .models import Message, Call, CallSignal, Conversation
from social.models import Notification

User = get_user_model()

class MessagingTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.one = User.objects.create_user(username="one", email="one@example.com", password="LinkoraStrong!483")
        self.two = User.objects.create_user(username="two", email="two@example.com", password="LinkoraStrong!483")
        self.client.force_authenticate(self.one)

    def test_start_send_and_read_conversation(self):
        response = self.client.post("/api/messages/conversations/", {"user_id": self.two.id}, format="json")
        self.assertEqual(response.status_code, 201)
        conversation_id = response.data["id"]
        sent = self.client.post("/api/messages/", {"conversation": conversation_id, "body": "Hello there"}, format="json")
        self.assertEqual(sent.status_code, 201)
        self.assertEqual(Message.objects.count(), 1)
        self.client.force_authenticate(self.two)
        read = self.client.get(f"/api/messages/conversations/{conversation_id}/")
        self.assertEqual(read.status_code, 200)
        self.assertIsNotNone(Message.objects.get().read_at)
        self.client.force_authenticate(User.objects.create_user(username="intruder", email="intruder@example.com", password="LinkoraStrong!483"))
        self.assertEqual(self.client.get(f"/api/messages/conversations/{conversation_id}/").status_code, 404)

    def test_audio_video_call_signaling_logs_and_missed_call_notification(self):
        conversation = Conversation.objects.create()
        conversation.participants.add(self.one, self.two)
        offer = {"type": "offer", "sdp": "offer-sdp"}
        started = self.client.post("/api/calls/", {"conversation": conversation.id, "recipient": self.two.id, "kind": "video", "offer": offer}, format="json")
        self.assertEqual(started.status_code, 201, started.data)
        call_id = started.data["id"]
        log = Call.objects.get(pk=call_id).message
        self.assertEqual(log.kind, Message.CALL)
        self.assertEqual(log.call_status, Call.RINGING)
        self.assertTrue(Notification.objects.filter(recipient=self.two, kind=Notification.CALL).exists())

        self.client.force_authenticate(self.two)
        self.assertEqual([item["id"] for item in self.client.get("/api/calls/").data], [call_id])
        candidate = {"candidate": "candidate:1", "sdpMid": "0", "sdpMLineIndex": 0}
        self.assertEqual(self.client.post(f"/api/calls/{call_id}/signals/", {"candidate": candidate}, format="json").status_code, 201)
        self.client.force_authenticate(self.one)
        signals = self.client.get(f"/api/calls/{call_id}/signals/")
        self.assertEqual(signals.data["results"][0]["payload"], candidate)

        self.client.force_authenticate(self.two)
        answer = {"type": "answer", "sdp": "answer-sdp"}
        accepted = self.client.post(f"/api/calls/{call_id}/accept/", {"answer": answer}, format="json")
        self.assertEqual(accepted.status_code, 200, accepted.data)
        self.assertEqual(accepted.data["status"], Call.ACCEPTED)
        self.client.force_authenticate(self.one)
        self.assertEqual(self.client.get(f"/api/calls/{call_id}/").data["answer"], '{"type": "answer", "sdp": "answer-sdp"}')
        self.assertEqual(self.client.post(f"/api/calls/{call_id}/end/").data["status"], Call.ENDED)
        log.refresh_from_db()
        self.assertEqual(log.call_status, Call.ENDED)

        missed = self.client.post("/api/calls/", {"conversation": conversation.id, "recipient": self.two.id, "kind": "audio", "offer": offer}, format="json")
        self.assertEqual(missed.status_code, 201, missed.data)
        missed_id = missed.data["id"]
        Call.objects.filter(pk=missed_id).update(created_at=timezone.now() - timedelta(seconds=50))
        self.client.force_authenticate(self.two)
        self.assertEqual(self.client.get("/api/calls/").data, [])
        self.assertEqual(Call.objects.get(pk=missed_id).status, Call.MISSED)
        self.assertTrue(Notification.objects.filter(recipient=self.one, actor=self.two, kind=Notification.MISSED_CALL).exists())
        self.assertEqual(Message.objects.get(pk=Call.objects.get(pk=missed_id).message_id).call_status, Call.MISSED)
        self.client.force_authenticate(self.one)
        declined = self.client.post("/api/calls/", {"conversation": conversation.id, "recipient": self.two.id, "kind": "audio", "offer": offer}, format="json")
        self.assertEqual(declined.status_code, 201)
        self.client.force_authenticate(self.two)
        self.assertEqual(self.client.post(f"/api/calls/{declined.data['id']}/reject/").status_code, 200)
        self.assertTrue(Notification.objects.filter(recipient=self.one, actor=self.two, kind=Notification.DECLINED_CALL).exists())
