from django.conf import settings
from django.db import models
from django.db.models import Q
from accounts.models import validate_upload

class Post(models.Model):
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="posts")
    content = models.TextField(max_length=5000, blank=True)
    is_public = models.BooleanField(default=True)
    shares_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["author", "-created_at"]), models.Index(fields=["-created_at"])]
    def __str__(self):
        return f"Post {self.pk} by {self.author.username}"

class PostImage(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="posts/%Y/%m/", max_length=500, validators=[validate_upload])
    alt_text = models.CharField(max_length=180, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

class Like(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="likes")
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="likes")
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "post"], name="unique_user_post_like")]
        indexes = [models.Index(fields=["post", "-created_at"])]

class Comment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="comments")
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.CASCADE, related_name="replies")
    content = models.CharField(max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        ordering = ["created_at"]
        indexes = [models.Index(fields=["post", "created_at"])]

class Follow(models.Model):
    follower = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="following_links")
    following = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="follower_links")
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=["follower", "following"], name="unique_follow_pair"), models.CheckConstraint(condition=~Q(follower=models.F("following")), name="prevent_self_follow")]
        indexes = [models.Index(fields=["following", "-created_at"]), models.Index(fields=["follower", "-created_at"])]

class Notification(models.Model):
    LIKE = "like"
    COMMENT = "comment"
    FOLLOW = "follow"
    MESSAGE = "message"
    TYPE_CHOICES = [(LIKE, "Like"), (COMMENT, "Comment"), (FOLLOW, "Follow"), (MESSAGE, "Message")]
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sent_notifications")
    kind = models.CharField(max_length=16, choices=TYPE_CHOICES)
    post = models.ForeignKey(Post, null=True, blank=True, on_delete=models.CASCADE, related_name="notifications")
    comment = models.ForeignKey(Comment, null=True, blank=True, on_delete=models.CASCADE)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["recipient", "is_read", "-created_at"])]

class Hashtag(models.Model):
    name = models.CharField(max_length=80, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return f"#{self.name}"

class PostHashtag(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="hashtag_links")
    hashtag = models.ForeignKey(Hashtag, on_delete=models.CASCADE, related_name="post_links")
    class Meta:
        constraints = [models.UniqueConstraint(fields=["post", "hashtag"], name="unique_post_hashtag")]

