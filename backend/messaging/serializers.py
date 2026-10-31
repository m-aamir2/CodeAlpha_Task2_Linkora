from rest_framework import serializers
from accounts.serializers import UserSerializer
from .models import Conversation, Message, Call

class MessageSerializer(serializers.ModelSerializer):
    sender = UserSerializer(read_only=True)
    class Meta:
        model = Message
        fields = ["id", "conversation", "sender", "body", "kind", "call_type", "call_status", "created_at", "read_at"]
        read_only_fields = ["id", "conversation", "sender", "created_at", "read_at"]

class CallSerializer(serializers.ModelSerializer):
    caller = UserSerializer(read_only=True)
    recipient = UserSerializer(read_only=True)
    class Meta:
        model = Call
        fields = ["id", "conversation", "caller", "recipient", "kind", "status", "offer", "answer", "created_at", "answered_at", "ended_at"]
        read_only_fields = fields

class ConversationSerializer(serializers.ModelSerializer):
    participants = UserSerializer(many=True, read_only=True)
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()
    class Meta:
        model = Conversation
        fields = ["id", "participants", "last_message", "unread_count", "updated_at"]
    def get_last_message(self, obj):
        message = obj.messages.select_related("sender").order_by("-created_at").first()
        return MessageSerializer(message, context=self.context).data if message else None
    def get_unread_count(self, obj):
        user = self.context["request"].user
        return obj.messages.filter(read_at__isnull=True).exclude(sender=user).count()
