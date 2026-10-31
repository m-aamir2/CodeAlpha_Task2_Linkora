from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone
from datetime import timedelta
from accounts.models import validate_upload

def story_expiry_time():
    return timezone.now() + timedelta(hours=24)

class Post(models.Model):
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="posts")
    content = models.TextField(max_length=5000, blank=True)
    is_public = models.BooleanField(default=True)
    followers_only = models.BooleanField(default=False)
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
    CALL = "call"
    MISSED_CALL = "missed_call"
    DECLINED_CALL = "declined_call"
    MENTION = "mention"
    STORY_REPLY = "story_reply"
    STORY_REACTION = "story_reaction"
    TYPE_CHOICES = [(LIKE, "Like"), (COMMENT, "Comment"), (FOLLOW, "Follow"), (MESSAGE, "Message"), (CALL, "Call"), (MISSED_CALL, "Missed call"), (DECLINED_CALL, "Declined call"), (MENTION, "Mention"), (STORY_REPLY, "Story reply"), (STORY_REACTION, "Story reaction")]
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sent_notifications")
    kind = models.CharField(max_length=16, choices=TYPE_CHOICES)
    post = models.ForeignKey(Post, null=True, blank=True, on_delete=models.CASCADE, related_name="notifications")
    comment = models.ForeignKey(Comment, null=True, blank=True, on_delete=models.CASCADE)
    story = models.ForeignKey("Story", null=True, blank=True, on_delete=models.CASCADE, related_name="notifications")
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

class Story(models.Model):
    IMAGE = "image"
    VIDEO = "video"
    MEDIA_CHOICES = [(IMAGE, "Image"), (VIDEO, "Video")]
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="stories")
    media = models.FileField(upload_to="stories/%Y/%m/%d/", max_length=500)
    media_type = models.CharField(max_length=8, choices=MEDIA_CHOICES)
    caption = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    expires_at = models.DateTimeField(default=story_expiry_time, db_index=True)
    class Meta:
        ordering = ["created_at"]
        indexes = [models.Index(fields=["author", "expires_at"])]

class StoryReaction(models.Model):
    story = models.ForeignKey(Story, on_delete=models.CASCADE, related_name="reactions")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="story_reactions")
    emoji = models.CharField(max_length=16, default="❤️")
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=["story", "user"], name="unique_story_reaction_user")]

class StoryReply(models.Model):
    story = models.ForeignKey(Story, on_delete=models.CASCADE, related_name="replies")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="story_replies")
    content = models.CharField(max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)

class Reel(models.Model):
    NONE = "none"
    FILTER_CHOICES = [(NONE, "None"), ("vivid", "Vivid"), ("mono", "Mono"), ("warm", "Warm"), ("vintage", "Vintage")]
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reels")
    video = models.FileField(upload_to="reels/%Y/%m/", max_length=500)
    thumbnail = models.FileField(upload_to="reel-thumbnails/%Y/%m/", max_length=500, blank=True)
    caption = models.CharField(max_length=2000, blank=True)
    filter_name = models.CharField(max_length=16, choices=FILTER_CHOICES, default=NONE)
    shares_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["author", "-created_at"])]

class ReelLike(models.Model):
    reel = models.ForeignKey(Reel, on_delete=models.CASCADE, related_name="likes")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reel_likes")
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=["reel", "user"], name="unique_reel_like_user")]

class ReelSave(models.Model):
    reel = models.ForeignKey(Reel, on_delete=models.CASCADE, related_name="saves")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="saved_reels")
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=["reel", "user"], name="unique_reel_save_user")]

class ReelComment(models.Model):
    reel = models.ForeignKey(Reel, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reel_comments")
    content = models.CharField(max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ["created_at"]

