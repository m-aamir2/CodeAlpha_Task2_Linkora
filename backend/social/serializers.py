import re
from django.contrib.auth import get_user_model
from django.conf import settings
from django.db import transaction
from rest_framework import serializers
from accounts.serializers import UserSerializer
from .models import Post, PostImage, Like, Comment, Follow, Notification, Hashtag, PostHashtag

User = get_user_model()

class PostImageSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()
    class Meta:
        model = PostImage
        fields = ["id", "url", "alt_text", "created_at"]
    def get_url(self, obj):
        request = self.context.get("request")
        return request.build_absolute_uri(obj.image.url) if request else obj.image.url

class CommentSerializer(serializers.ModelSerializer):
    author = UserSerializer(read_only=True)
    class Meta:
        model = Comment
        fields = ["id", "post", "author", "parent", "content", "created_at", "updated_at"]
        read_only_fields = ["post", "author", "created_at", "updated_at"]
    def validate_parent(self, value):
        view = self.context.get("view")
        expected_post = view.kwargs.get("post_id") if view else None
        if value and expected_post and value.post_id != int(expected_post):
            raise serializers.ValidationError("A reply must belong to the same post as its parent comment.")
        return value

class PostSerializer(serializers.ModelSerializer):
    author = UserSerializer(read_only=True)
    images = PostImageSerializer(many=True, read_only=True)
    uploaded_images = serializers.ListField(child=serializers.ImageField(), write_only=True, required=False, allow_empty=True)
    replace_images = serializers.BooleanField(write_only=True, required=False, default=False)
    remove_image_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), write_only=True, required=False, allow_empty=True)
    likes_count = serializers.IntegerField(read_only=True)
    comments_count = serializers.IntegerField(read_only=True)
    liked_by_me = serializers.BooleanField(read_only=True)
    hashtags = serializers.SerializerMethodField()
    class Meta:
        model = Post
        fields = ["id", "author", "content", "is_public", "images", "uploaded_images", "replace_images", "remove_image_ids", "likes_count", "comments_count", "liked_by_me", "shares_count", "hashtags", "created_at", "updated_at"]
        read_only_fields = ["id", "author", "shares_count", "created_at", "updated_at"]
    def validate_uploaded_images(self, images):
        if len(images) > 6:
            raise serializers.ValidationError("You can add up to 6 images to one post.")
        for image in images:
            if image.size > settings.MAX_UPLOAD_SIZE:
                raise serializers.ValidationError("Each image must be 8 MB or smaller.")
        return images
    def validate(self, attrs):
        content = attrs.get("content", self.instance.content if self.instance else "")
        image_uploads = attrs.get("uploaded_images", [])
        replace_images = attrs.get("replace_images", False)
        remove_image_ids = attrs.get("remove_image_ids", [])
        if len(remove_image_ids) != len(set(remove_image_ids)):
            raise serializers.ValidationError({"remove_image_ids": "Image IDs must be unique."})
        if not self.instance and remove_image_ids:
            raise serializers.ValidationError({"remove_image_ids": "Images can only be removed while editing a post."})
        existing_ids = set(self.instance.images.values_list("id", flat=True)) if self.instance else set()
        invalid_ids = set(remove_image_ids) - existing_ids
        if invalid_ids:
            raise serializers.ValidationError({"remove_image_ids": "One or more selected images do not belong to this post."})
        remaining_images = 0 if replace_images else len(existing_ids - set(remove_image_ids))
        if remaining_images + len(image_uploads) > 6:
            raise serializers.ValidationError({"uploaded_images": "A post can contain up to 6 images."})
        if not content.strip() and remaining_images + len(image_uploads) == 0:
            raise serializers.ValidationError({"content": "Add some text or at least one image to your post."})
        return attrs
    def get_hashtags(self, obj):
        return [link.hashtag.name for link in obj.hashtag_links.select_related("hashtag").all()]
    def create(self, validated_data):
        images = validated_data.pop("uploaded_images", [])
        validated_data.pop("replace_images", None)
        validated_data.pop("remove_image_ids", None)
        post = Post.objects.create(**validated_data)
        for image in images:
            PostImage.objects.create(post=post, image=image)
        sync_hashtags(post)
        return post
    def update(self, instance, validated_data):
        images = validated_data.pop("uploaded_images", [])
        replace_images = validated_data.pop("replace_images", False)
        remove_image_ids = validated_data.pop("remove_image_ids", [])
        with transaction.atomic():
            instance = super().update(instance, validated_data)
            images_to_remove = instance.images.all() if replace_images else instance.images.filter(pk__in=remove_image_ids)
            removed_files = [(image.image.storage, image.image.name) for image in images_to_remove if image.image]
            images_to_remove.delete()
            for storage, name in removed_files:
                transaction.on_commit(lambda storage=storage, name=name: storage.delete(name))
            for image in images:
                PostImage.objects.create(post=instance, image=image)
            sync_hashtags(instance)
        return instance

def sync_hashtags(post):
    names = {name.lower() for name in re.findall(r"(?<!\w)#([\w]{1,80})", post.content)}
    post.hashtag_links.all().delete()
    for name in names:
        tag, _ = Hashtag.objects.get_or_create(name=name)
        PostHashtag.objects.get_or_create(post=post, hashtag=tag)

class NotificationSerializer(serializers.ModelSerializer):
    actor = UserSerializer(read_only=True)
    post_preview = serializers.CharField(source="post.content", read_only=True, default="")
    class Meta:
        model = Notification
        fields = ["id", "actor", "kind", "post", "comment", "post_preview", "is_read", "created_at"]

class FollowSerializer(serializers.ModelSerializer):
    follower = UserSerializer(read_only=True)
    following = UserSerializer(read_only=True)
    class Meta:
        model = Follow
        fields = ["id", "follower", "following", "created_at"]
