from datetime import timedelta
from io import BytesIO
from PIL import Image
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from .models import Post, Like, Comment, Follow, Notification, Story, StoryReaction, StoryReply, Reel, ReelLike, ReelComment, ReelSave

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

    def test_following_feed_is_personalized_ordered_and_removed_on_unfollow(self):
        other = User.objects.create_user(username="casey", email="casey@example.com", password="LinkoraStrong!483")
        Follow.objects.create(follower=self.alex, following=self.jamie)
        now = timezone.now()
        older = Post.objects.create(author=self.jamie, content="Older followed post")
        follower_post = Post.objects.create(author=self.jamie, content="Follower photo", is_public=False, followers_only=True)
        newest = Post.objects.create(author=self.jamie, content="Newest followed post")
        Post.objects.create(author=other, content="Unfollowed public post")
        Post.objects.create(author=self.alex, content="Own post")
        Post.objects.filter(pk=older.pk).update(created_at=now - timedelta(minutes=2))
        Post.objects.filter(pk=follower_post.pk).update(created_at=now - timedelta(minutes=1))
        Post.objects.filter(pk=newest.pk).update(created_at=now)

        feed = self.client.get("/api/posts/")
        self.assertEqual([post["id"] for post in feed.data["results"]], [newest.id, follower_post.id, older.id])
        self.assertEqual(self.client.post(f"/api/posts/{follower_post.id}/like/").status_code, 201)
        comment = self.client.post(f"/api/posts/{follower_post.id}/comments/", {"content": "Nice photo"}, format="json")
        self.assertEqual(comment.status_code, 201)

        self.client.delete(f"/api/users/{self.jamie.id}/follow/")
        self.assertEqual(self.client.get("/api/posts/").data["results"], [])
        self.assertEqual(self.client.get(f"/api/posts/{follower_post.id}/").status_code, 404)
        self.assertEqual(self.client.get(f"/api/posts/{follower_post.id}/comments/").status_code, 404)

        self.client.force_authenticate(other)
        self.assertEqual(self.client.get("/api/posts/").data["results"], [])

    def test_post_image_upload(self):
        image = Image.new("RGB", (4, 4), "purple")
        content = BytesIO()
        image.save(content, format="PNG")
        from django.core.files.uploadedfile import SimpleUploadedFile
        content.seek(0)
        response = self.client.post("/api/posts/", {"content": "Look at this", "uploaded_images": [SimpleUploadedFile("photo.png", content.getvalue(), content_type="image/png")]}, format="multipart")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(len(response.data["images"]), 1)
        uploaded_post = Post.objects.get(pk=response.data["id"])
        self.assertFalse(uploaded_post.is_public)
        self.assertTrue(uploaded_post.followers_only)
        Follow.objects.create(follower=self.jamie, following=self.alex)
        self.client.force_authenticate(self.jamie)
        feed = self.client.get("/api/posts/")
        self.assertIn(uploaded_post.id, [post["id"] for post in feed.data["results"]])
        self.assertEqual(self.client.post(f"/api/posts/{uploaded_post.id}/like/").status_code, 201)
        comment = self.client.post(f"/api/posts/{uploaded_post.id}/comments/", {"content": "Great photo"}, format="json")
        self.assertEqual(comment.status_code, 201)

    def test_story_visibility_reactions_replies_and_expiration(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from datetime import timedelta

        Follow.objects.create(follower=self.alex, following=self.jamie)
        picture = Image.new("RGB", (4, 4), "orange")
        content = BytesIO(); picture.save(content, format="PNG"); content.seek(0)
        self.client.force_authenticate(self.jamie)
        created = self.client.post("/api/stories/", {
            "media_type": "image", "caption": "A small moment",
            "uploaded_media": SimpleUploadedFile("story.png", content.getvalue(), content_type="image/png"),
        }, format="multipart")
        self.assertEqual(created.status_code, 201, created.data)
        story_id = created.data["id"]
        self.assertGreater(created.data["expires_at"], created.data["created_at"])

        self.client.force_authenticate(self.alex)
        self.assertEqual([item["id"] for item in self.client.get("/api/stories/").data], [story_id])
        self.assertEqual(self.client.post(f"/api/stories/{story_id}/reaction/", {"emoji": "🔥"}, format="json").status_code, 200)
        reply = self.client.post(f"/api/stories/{story_id}/replies/", {"content": "Love this"}, format="json")
        self.assertEqual(reply.status_code, 201)
        self.assertEqual(StoryReaction.objects.filter(story_id=story_id, user=self.alex).count(), 1)
        self.assertEqual(StoryReply.objects.filter(story_id=story_id, author=self.alex).count(), 1)

        story = Story.objects.get(pk=story_id)
        story.expires_at = timezone.now() - timedelta(seconds=1)
        story.save(update_fields=["expires_at"])
        self.assertEqual(self.client.get("/api/stories/").data, [])
        self.assertFalse(Story.objects.filter(pk=story_id).exists())

    def test_reel_feed_and_interactions_are_follower_scoped(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        Follow.objects.create(follower=self.alex, following=self.jamie)
        self.client.force_authenticate(self.jamie)
        created = self.client.post("/api/reels/", {
            "caption": "First reel", "filter_name": "vivid",
            "uploaded_video": SimpleUploadedFile("short.mp4", b"sample video", content_type="video/mp4"),
        }, format="multipart")
        self.assertEqual(created.status_code, 201, created.data)
        reel_id = created.data["id"]
        self.assertEqual([item["id"] for item in self.client.get("/api/reels/").data["results"]], [reel_id])
        self.client.force_authenticate(self.alex)
        reels = self.client.get("/api/reels/")
        self.assertEqual([item["id"] for item in reels.data["results"]], [reel_id])
        self.assertEqual(self.client.post(f"/api/reels/{reel_id}/like/").status_code, 201)
        self.assertEqual(self.client.post(f"/api/reels/{reel_id}/save/").status_code, 201)
        self.assertEqual(self.client.post(f"/api/reels/{reel_id}/share/").data["shares_count"], 1)
        self.assertEqual(self.client.post(f"/api/reels/{reel_id}/comments/", {"content": "Nice"}, format="json").status_code, 201)
        self.assertEqual(ReelLike.objects.filter(reel_id=reel_id, user=self.alex).count(), 1)
        self.assertEqual(ReelSave.objects.filter(reel_id=reel_id, user=self.alex).count(), 1)
        self.assertEqual(ReelComment.objects.filter(reel_id=reel_id, author=self.alex).count(), 1)
        self.client.delete(f"/api/users/{self.jamie.id}/follow/")
        self.assertEqual(self.client.get("/api/reels/").data["results"], [])

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

    def test_mentions_story_replies_and_reactions_create_targeted_notifications(self):
        followed_post = self.client.post("/api/posts/", {"content": "A note for @jamie"}, format="json")
        self.assertEqual(followed_post.status_code, 201)
        mention = Notification.objects.get(recipient=self.jamie, kind=Notification.MENTION)
        self.assertEqual(mention.post_id, followed_post.data["id"])

        Follow.objects.create(follower=self.jamie, following=self.alex)
        story = Story.objects.create(author=self.alex, media="https://blob.example/story.png", media_type=Story.IMAGE)
        self.client.force_authenticate(self.jamie)
        reply = self.client.post(f"/api/stories/{story.id}/replies/", {"content": "Nice story @alex"}, format="json")
        self.assertEqual(reply.status_code, 201)
        self.assertTrue(Notification.objects.filter(recipient=self.alex, actor=self.jamie, kind=Notification.STORY_REPLY, story=story).exists())
        self.assertTrue(Notification.objects.filter(recipient=self.alex, actor=self.jamie, kind=Notification.MENTION, story=story).exists())
        self.client.post(f"/api/stories/{story.id}/reaction/", {"emoji": "🔥"}, format="json")
        self.assertTrue(Notification.objects.filter(recipient=self.alex, actor=self.jamie, kind=Notification.STORY_REACTION, story=story).exists())

        self.client.force_authenticate(self.alex)
        listed = self.client.get("/api/notifications/")
        self.assertEqual(listed.status_code, 200)
        story_notice = next(item for item in listed.data["results"] if item["kind"] == Notification.STORY_REPLY)
        self.assertEqual(story_notice["story_author_id"], self.alex.id)
