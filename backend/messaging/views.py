from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import Conversation, Message
from .serializers import ConversationSerializer, MessageSerializer
from social.models import Notification

User = get_user_model()

class ConversationListCreateView(APIView):
    def get(self, request):
        conversations = Conversation.objects.filter(participants=request.user).prefetch_related("participants", "messages").order_by("-updated_at")
        return Response(ConversationSerializer(conversations, many=True, context={"request": request}).data)
    def post(self, request):
        user_id = request.data.get("user_id")
        recipient = get_object_or_404(User, pk=user_id)
        if recipient.id == request.user.id:
            raise ValidationError({"detail": "Choose another person to start a conversation."})
        candidates = Conversation.objects.filter(participants=request.user).annotate(participant_count=Count("participants")).filter(participant_count=2, participants=recipient)
        conversation = candidates.first()
        if conversation is None:
            conversation = Conversation.objects.create()
            conversation.participants.add(request.user, recipient)
        return Response(ConversationSerializer(conversation, context={"request": request}).data, status=201)

class ConversationMessagesView(generics.ListAPIView):
    serializer_class = MessageSerializer
    def get_queryset(self):
        conversation = get_object_or_404(Conversation, pk=self.kwargs["pk"], participants=self.request.user)
        Message.objects.filter(conversation=conversation, read_at__isnull=True).exclude(sender=self.request.user).update(read_at=timezone.now())
        return conversation.messages.select_related("sender").order_by("created_at")

class MessageCreateView(APIView):
    def post(self, request):
        conversation = get_object_or_404(Conversation, pk=request.data.get("conversation"), participants=request.user)
        body = request.data.get("body", "").strip()
        if not body:
            raise ValidationError({"body": "Message cannot be empty."})
        if len(body) > 5000:
            raise ValidationError({"body": "Message is too long."})
        message = Message.objects.create(conversation=conversation, sender=request.user, body=body)
        conversation.save()
        recipient = conversation.participants.exclude(pk=request.user.pk).first()
        if recipient:
            Notification.objects.create(recipient=recipient, actor=request.user, kind=Notification.MESSAGE)
        return Response(MessageSerializer(message, context={"request": request}).data, status=201)
