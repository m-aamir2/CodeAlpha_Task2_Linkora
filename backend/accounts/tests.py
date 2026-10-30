from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

User = get_user_model()

class AuthenticationTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_register_login_and_profile_update(self):
        payload = {"username": "storyteller", "full_name": "A Storyteller", "email": "story@example.com", "password": "LinkoraStrong!483", "password_confirm": "LinkoraStrong!483"}
        response = self.client.post("/api/auth/register/", payload, format="json")
        self.assertEqual(response.status_code, 201)
        user = User.objects.get(username="storyteller")
        self.assertTrue(user.check_password(payload["password"]))
        self.assertEqual(user.profile.full_name, "A Storyteller")
        login = self.client.post("/api/auth/login/", {"username": "storyteller", "password": payload["password"]}, format="json")
        self.assertEqual(login.status_code, 200)
        self.assertIn("access", login.data)
        self.assertEqual(login.data["user"]["username"], "storyteller")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        profile = self.client.patch("/api/users/profile/", {"bio": "Making little things."}, format="json")
        self.assertEqual(profile.status_code, 200)
        user.refresh_from_db()
        self.assertEqual(user.profile.bio, "Making little things.")
        logout = self.client.post("/api/auth/logout/", {"refresh": login.data["refresh"]}, format="json")
        self.assertEqual(logout.status_code, 204)
        refresh = self.client.post("/api/auth/refresh/", {"refresh": login.data["refresh"]}, format="json")
        self.assertEqual(refresh.status_code, 401)

    def test_registration_rejects_password_mismatch_and_duplicate_email(self):
        payload = {"username": "one", "full_name": "One", "email": "same@example.com", "password": "LinkoraStrong!483", "password_confirm": "different"}
        self.assertEqual(self.client.post("/api/auth/register/", payload, format="json").status_code, 400)
        payload["password_confirm"] = payload["password"]
        self.assertEqual(self.client.post("/api/auth/register/", payload, format="json").status_code, 201)
        payload["username"] = "two"
        self.assertEqual(self.client.post("/api/auth/register/", payload, format="json").status_code, 400)
