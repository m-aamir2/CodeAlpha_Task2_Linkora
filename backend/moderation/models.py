from django.conf import settings
from django.db import models
from social.models import Post, Comment

class Report(models.Model):
    OPEN = "open"
    REVIEWED = "reviewed"
    DISMISSED = "dismissed"
    STATUS_CHOICES = [(OPEN, "Open"), (REVIEWED, "Reviewed"), (DISMISSED, "Dismissed")]
    TARGET_CHOICES = [("post", "Post"), ("user", "User"), ("comment", "Comment")]
    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reports")
    target_type = models.CharField(max_length=12, choices=TARGET_CHOICES)
    target_post = models.ForeignKey(Post, null=True, blank=True, on_delete=models.SET_NULL, related_name="reports")
    target_comment = models.ForeignKey(Comment, null=True, blank=True, on_delete=models.SET_NULL, related_name="reports")
    target_user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="user_reports")
    reason = models.CharField(max_length=80)
    details = models.TextField(max_length=1000, blank=True)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=OPEN, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "-created_at"])]
