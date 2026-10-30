from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from .models import Message

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
