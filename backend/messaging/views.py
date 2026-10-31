import json
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import Conversation, Message, Call, CallSignal
from .serializers import ConversationSerializer, MessageSerializer, CallSerializer
from social.models import Notification

User = get_user_model()


def mark_call_missed(call):
    """Persist a missed call once so the chat log and notifications agree."""
    if call.status != Call.RINGING or call.created_at > timezone.now() - timedelta(seconds=45):
        return False
    ended_at = timezone.now()
    if not Call.objects.filter(pk=call.pk, status=Call.RINGING).update(status=Call.MISSED, ended_at=ended_at):
        return False
    call.status = Call.MISSED
    call.ended_at = ended_at
    if call.message_id:
        Message.objects.filter(pk=call.message_id).update(call_status=Call.MISSED)
    Notification.objects.create(recipient=call.caller, actor=call.recipient, kind=Notification.MISSED_CALL)
    return True

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

class CallListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "call_poll"
    def get(self, request):
        cutoff = timezone.now() - timedelta(seconds=45)
        missed = Call.objects.filter(recipient=request.user, status=Call.RINGING, created_at__lte=cutoff).select_related("caller", "recipient", "message")
        for call in missed:
            mark_call_missed(call)
        incoming = Call.objects.filter(recipient=request.user, status=Call.RINGING).select_related("caller", "recipient").order_by("created_at")
        return Response(CallSerializer(incoming, many=True, context={"request": request}).data)

    def post(self, request):
        conversation = get_object_or_404(Conversation, pk=request.data.get("conversation"), participants=request.user)
        recipient = get_object_or_404(User, pk=request.data.get("recipient"))
        if recipient.pk == request.user.pk or not conversation.participants.filter(pk=recipient.pk).exists():
            raise ValidationError({"recipient": "Choose the other participant in this conversation."})
        kind = request.data.get("kind")
        if kind not in {Call.AUDIO, Call.VIDEO}:
            raise ValidationError({"kind": "Choose audio or video."})
        offer = request.data.get("offer")
        if not isinstance(offer, dict) or offer.get("type") != "offer" or not isinstance(offer.get("sdp"), str):
            raise ValidationError({"offer": "A valid WebRTC offer is required."})
        active = Call.objects.filter(status__in=[Call.RINGING, Call.ACCEPTED]).filter(Q(caller__in=[request.user, recipient]) | Q(recipient__in=[request.user, recipient])).exists()
        if active:
            return Response({"detail": "One of these accounts is already on a call."}, status=409)
        with transaction.atomic():
            message = Message.objects.create(conversation=conversation, sender=request.user, body=f"Started an {kind} call", kind=Message.CALL, call_type=kind, call_status=Call.RINGING)
            call = Call.objects.create(conversation=conversation, caller=request.user, recipient=recipient, kind=kind, offer=json.dumps(offer), message=message)
            conversation.save()
            Notification.objects.create(recipient=recipient, actor=request.user, kind=Notification.CALL)
        return Response(CallSerializer(call, context={"request": request}).data, status=201)

def get_participant_call(call_id, user):
    return get_object_or_404(Call.objects.filter(Q(caller=user) | Q(recipient=user)).select_related("caller", "recipient", "conversation", "message"), pk=call_id)

class CallDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "call_signaling"
    def get(self, request, call_id):
        call = get_participant_call(call_id, request.user)
        mark_call_missed(call)
        return Response(CallSerializer(call, context={"request": request}).data)

class CallAcceptView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def post(self, request, call_id):
        call = get_participant_call(call_id, request.user)
        if call.recipient_id != request.user.pk:
            raise PermissionDenied("Only the person receiving the call can accept it.")
        if call.status != Call.RINGING:
            raise ValidationError({"detail": "This call is no longer ringing."})
        if call.created_at < timezone.now() - timedelta(seconds=45):
            mark_call_missed(call)
            return Response({"detail": "This call has expired."}, status=410)
        answer = request.data.get("answer")
        if not isinstance(answer, dict) or answer.get("type") != "answer" or not isinstance(answer.get("sdp"), str):
            raise ValidationError({"answer": "A valid WebRTC answer is required."})
        call.answer = json.dumps(answer)
        call.status = Call.ACCEPTED
        call.answered_at = timezone.now()
        call.save(update_fields=["answer", "status", "answered_at"])
        if call.message_id:
            Message.objects.filter(pk=call.message_id).update(call_status=Call.ACCEPTED)
        return Response(CallSerializer(call, context={"request": request}).data)

class CallRejectView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def post(self, request, call_id):
        call = get_participant_call(call_id, request.user)
        if call.recipient_id != request.user.pk:
            raise PermissionDenied("Only the person receiving the call can reject it.")
        if call.status != Call.RINGING:
            raise ValidationError({"detail": "This call is no longer ringing."})
        call.status = Call.REJECTED
        call.ended_at = timezone.now()
        call.save(update_fields=["status", "ended_at"])
        if call.message_id:
            Message.objects.filter(pk=call.message_id).update(call_status=Call.REJECTED)
        Notification.objects.create(recipient=call.caller, actor=request.user, kind=Notification.DECLINED_CALL)
        return Response(CallSerializer(call, context={"request": request}).data)

class CallEndView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def post(self, request, call_id):
        call = get_participant_call(call_id, request.user)
        if call.status not in {Call.RINGING, Call.ACCEPTED}:
            return Response(CallSerializer(call, context={"request": request}).data)
        call.status = Call.ENDED
        call.ended_at = timezone.now()
        call.save(update_fields=["status", "ended_at"])
        if call.message_id:
            Message.objects.filter(pk=call.message_id).update(call_status=Call.ENDED)
        return Response(CallSerializer(call, context={"request": request}).data)

class CallSignalListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "call_signaling"
    def get(self, request, call_id):
        call = get_participant_call(call_id, request.user)
        after = request.query_params.get("after", "0")
        try:
            after_id = max(0, int(after))
        except (TypeError, ValueError):
            raise ValidationError({"after": "Signal cursor must be an integer."})
        signals = list(call.signals.filter(pk__gt=after_id).select_related("sender").order_by("pk")[:100])
        return Response({
            "results": [{"id": signal.pk, "payload": signal.payload} for signal in signals if signal.sender_id != request.user.pk],
            "next_after": signals[-1].pk if signals else after_id,
        })
    def post(self, request, call_id):
        call = get_participant_call(call_id, request.user)
        if call.status not in {Call.RINGING, Call.ACCEPTED}:
            raise ValidationError({"detail": "This call is no longer active."})
        candidate = request.data.get("candidate")
        if not isinstance(candidate, dict) or len(call.signals.all()) > 300:
            raise ValidationError({"candidate": "A valid ICE candidate is required."})
        signal = CallSignal.objects.create(call=call, sender=request.user, payload=candidate)
        return Response({"id": signal.pk}, status=201)
