from io import BytesIO
from PIL import Image
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from .models import Post, Like, Comment, Follow, Notification

User = get_user_model()

class SocialFeatureTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.alex = User.objects.create_user(username="alex", email="alex@example.com", password="LinkoraStrong!483")
        self.jamie = User.objects.create_user(username="jamie", email="jamie@example.com", password="LinkoraStrong!483")
        self.client.force_authenticate(self.alex)

    def test_post_like_comment_and_ownership(self):
        created = self.client.post("/api/posts/", {"content": "A new day #hello"}, format="json")
        self.assertEqual(created.status_code, 201)
        self.assertEqual(self.client.post("/api/posts/", {"content": "   "}, format="json").status_code, 400)
        post_id = created.data["id"]
        self.assertEqual(created.data["hashtags"], ["hello"])
        private_post = Post.objects.create(author=self.alex, content="Private note", is_public=False)
        anonymous = APIClient()
        self.assertEqual(anonymous.get(f"/api/posts/{private_post.id}/").status_code, 404)
        public_feed = anonymous.get("/api/posts/")
        self.assertEqual(public_feed.status_code, 200)
        self.assertNotIn(private_post.id, [item["id"] for item in public_feed.data["results"]])
        self.client.force_authenticate(self.jamie)
        self.assertEqual(self.client.post(f"/api/posts/{post_id}/like/").status_code, 201)
        self.assertEqual(self.client.post(f"/api/posts/{post_id}/like/").data["likes_count"], 1)
        self.assertEqual(Like.objects.filter(post_id=post_id).count(), 1)
        self.assertEqual(self.client.post(f"/api/posts/{post_id}/share/").data["shares_count"], 1)
        comment = self.client.post(f"/api/posts/{post_id}/comments/", {"content": "Love this."}, format="json")
        self.assertEqual(comment.status_code, 201)
        second_post = Post.objects.create(author=self.alex, content="Another post")
        invalid_reply = self.client.post(f"/api/posts/{second_post.id}/comments/", {"content": "Wrong parent", "parent": comment.data["id"]}, format="json")
        self.assertEqual(invalid_reply.status_code, 400)
        self.assertEqual(self.client.get(f"/api/posts/{post_id}/likes/").data["results"][0]["username"], "jamie")
        self.client.force_authenticate(self.alex)
        self.assertEqual(self.client.patch(f"/api/comments/{comment.data['id']}/", {"content": "Changed"}, format="json").status_code, 403)
        self.client.force_authenticate(self.jamie)
        self.assertEqual(self.client.patch(f"/api/comments/{comment.data['id']}/", {"content": "Edited"}, format="json").status_code, 200)
        unliked = self.client.delete(f"/api/posts/{post_id}/like/")
        self.assertEqual(unliked.data["likes_count"], 0)
        self.assertGreaterEqual(Notification.objects.filter(recipient=self.alex).count(), 2)
        self.client.force_authenticate(self.alex)
        notices = self.client.get("/api/notifications/")
        self.assertGreaterEqual(notices.data["unread_count"], 2)
        notification_id = notices.data["results"][0]["id"]
        self.assertTrue(self.client.patch(f"/api/notifications/{notification_id}/read/").data["is_read"])
        self.client.post("/api/notifications/read-all/")
        self.assertEqual(self.client.get("/api/notifications/").data["unread_count"], 0)

    def test_follow_self_duplicate_and_search(self):
        target = self.client.post(f"/api/users/{self.jamie.id}/follow/")
        self.assertEqual(target.status_code, 201)
        self.assertEqual(self.client.post(f"/api/users/{self.jamie.id}/follow/").status_code, 200)
        self.assertEqual(Follow.objects.filter(follower=self.alex, following=self.jamie).count(), 1)
        self.assertEqual(self.client.post(f"/api/users/{self.alex.id}/follow/").status_code, 400)
        post = Post.objects.create(author=self.jamie, content="Evening walk through the old town")
        result = self.client.get("/api/search/?q=old%20town")
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.data["posts"][0]["id"], post.id)
        people = self.client.get("/api/search/?q=jamie")
        self.assertEqual(people.data["users"][0]["username"], "jamie")
        self.assertNotIn("email", people.data["users"][0])

    def test_post_image_upload(self):
        image = Image.new("RGB", (4, 4), "purple")
        content = BytesIO()
        image.save(content, format="PNG")
        from django.core.files.uploadedfile import SimpleUploadedFile
        content.seek(0)
        response = self.client.post("/api/posts/", {"content": "Look at this", "uploaded_images": [SimpleUploadedFile("photo.png", content.getvalue(), content_type="image/png")]}, format="multipart")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(len(response.data["images"]), 1)

    def test_post_edit_can_replace_remove_and_preserve_images(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        def make_image(color, name):
            image = Image.new("RGB", (8, 8), color)
            content = BytesIO()
            image.save(content, format="PNG")
            return SimpleUploadedFile(name, content.getvalue(), content_type="image/png")

        created = self.client.post("/api/posts/", {
            "content": "Original photo", "uploaded_images": [make_image("purple", "original.png")],
        }, format="multipart")
        self.assertEqual(created.status_code, 201, created.data)
        post_id = created.data["id"]
        original_id = created.data["images"][0]["id"]

        replaced = self.client.patch(f"/api/posts/{post_id}/", {
            "content": "Updated photo", "replace_images": "true",
            "uploaded_images": [make_image("orange", "replacement.png")],
        }, format="multipart")
        self.assertEqual(replaced.status_code, 200, replaced.data)
        self.assertEqual(len(replaced.data["images"]), 1)
        self.assertNotEqual(replaced.data["images"][0]["id"], original_id)
        replacement_id = replaced.data["images"][0]["id"]

        self.client.force_authenticate(self.jamie)
        denied = self.client.patch(f"/api/posts/{post_id}/", {"replace_images": "true"}, format="multipart")
        self.assertEqual(denied.status_code, 403)
        self.client.force_authenticate(self.alex)

        text_edit = self.client.patch(f"/api/posts/{post_id}/", {
            "content": "Caption only", "replace_images": "false",
        }, format="multipart")
        self.assertEqual(text_edit.status_code, 200, text_edit.data)
        self.assertEqual([image["id"] for image in text_edit.data["images"]], [replacement_id])

        removed = self.client.patch(f"/api/posts/{post_id}/", {
            "content": "Text after removing photo", "remove_image_ids": [str(replacement_id)],
        }, format="multipart")
        self.assertEqual(removed.status_code, 200, removed.data)
        self.assertEqual(removed.data["images"], [])

        invalid = self.client.patch(f"/api/posts/{post_id}/", {
            "remove_image_ids": [str(original_id)],
        }, format="json")
        self.assertEqual(invalid.status_code, 400)
