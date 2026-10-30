from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from social.models import Post
from .models import Report

User = get_user_model()

class ModerationTests(TestCase):
    def test_report_and_admin_controls(self):
        author = User.objects.create_user(username="author", email="author@example.com", password="LinkoraStrong!483")
        reporter = User.objects.create_user(username="reporter", email="reporter@example.com", password="LinkoraStrong!483")
        admin = User.objects.create_superuser(username="admin", email="admin@example.com", password="LinkoraStrong!483")
        post = Post.objects.create(author=author, content="Reported content")
        client = APIClient(); client.force_authenticate(reporter)
        report = client.post("/api/reports/", {"target_type": "post", "target_post": post.id, "reason": "spam"}, format="json")
        self.assertEqual(report.status_code, 201)
        self.assertEqual(client.get("/api/admin/dashboard/").status_code, 403)
        client.force_authenticate(admin)
        stats = client.get("/api/admin/dashboard/")
        self.assertEqual(stats.status_code, 200)
        self.assertEqual(stats.data["open_reports"], 1)
        update = client.patch(f"/api/admin/reports/{report.data['id']}/", {"status": "reviewed"}, format="json")
        self.assertEqual(update.status_code, 200)
        self.assertEqual(Report.objects.get().status, Report.REVIEWED)
        disable = client.patch(f"/api/admin/users/{author.id}/", {"is_active": False}, format="json")
        self.assertEqual(disable.status_code, 200)
        author.refresh_from_db()
        self.assertFalse(author.is_active)
