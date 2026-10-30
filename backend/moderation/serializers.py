from rest_framework import serializers
from .models import Report

class ReportSerializer(serializers.ModelSerializer):
    reporter_username = serializers.CharField(source="reporter.username", read_only=True)
    target = serializers.SerializerMethodField()
    class Meta:
        model = Report
        fields = ["id", "reporter_username", "target_type", "target_post", "target_comment", "target_user", "target", "reason", "details", "status", "created_at", "reviewed_at"]
        read_only_fields = ["id", "reporter_username", "status", "created_at", "reviewed_at"]
    def get_target(self, obj):
        if obj.target_post_id: return {"id": obj.target_post_id, "content": obj.target_post.content[:160]}
        if obj.target_comment_id: return {"id": obj.target_comment_id, "content": obj.target_comment.content[:160]}
        if obj.target_user_id: return {"id": obj.target_user_id, "username": obj.target_user.username}
        return None
    def validate(self, attrs):
        target_type = attrs.get("target_type")
        mapping = {"post": "target_post", "comment": "target_comment", "user": "target_user"}
        if target_type not in mapping or not attrs.get(mapping.get(target_type, "")):
            raise serializers.ValidationError({"target_type": "A matching target is required."})
        return attrs
