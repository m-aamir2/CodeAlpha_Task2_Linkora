from django.conf import settings
from django.db import models

class Conversation(models.Model):
    participants = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name="conversations")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)
    def __str__(self):
        return f"Conversation {self.pk}"

class Message(models.Model):
    TEXT = "text"
    CALL = "call"
    KIND_CHOICES = [(TEXT, "Text"), (CALL, "Call")]
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sent_messages")
    body = models.TextField(max_length=5000)
    kind = models.CharField(max_length=8, choices=KIND_CHOICES, default=TEXT)
    call_type = models.CharField(max_length=8, blank=True)
    call_status = models.CharField(max_length=16, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)
    class Meta:
        ordering = ["created_at"]
        indexes = [models.Index(fields=["conversation", "created_at"])]

class Call(models.Model):
    AUDIO = "audio"
    VIDEO = "video"
    KIND_CHOICES = [(AUDIO, "Audio"), (VIDEO, "Video")]
    RINGING = "ringing"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    ENDED = "ended"
    MISSED = "missed"
    STATUS_CHOICES = [(RINGING, "Ringing"), (ACCEPTED, "Accepted"), (REJECTED, "Rejected"), (ENDED, "Ended"), (MISSED, "Missed")]
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="calls")
    caller = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="outgoing_calls")
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="incoming_calls")
    kind = models.CharField(max_length=8, choices=KIND_CHOICES)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=RINGING, db_index=True)
    offer = models.TextField()
    answer = models.TextField(blank=True)
    message = models.OneToOneField(Message, on_delete=models.SET_NULL, null=True, blank=True, related_name="call")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    answered_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    class Meta:
        indexes = [models.Index(fields=["recipient", "status", "created_at"]), models.Index(fields=["caller", "status", "created_at"])]

class CallSignal(models.Model):
    call = models.ForeignKey(Call, on_delete=models.CASCADE, related_name="signals")
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="call_signals")
    payload = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ["id"]
