import re
from urllib.parse import urlsplit
from django.contrib.auth import get_user_model
from django.conf import settings
from django.db import transaction
from rest_framework import serializers
from accounts.serializers import UserSerializer
from config.blob_urls import is_user_blob_url
from .models import Post, PostImage, Like, Comment, Follow, Notification, Hashtag, PostHashtag, Story, StoryReaction, StoryReply, Reel, ReelLike, ReelSave, ReelComment

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
    uploaded_image_urls = serializers.ListField(child=serializers.URLField(), write_only=True, required=False, allow_empty=True)
    replace_images = serializers.BooleanField(write_only=True, required=False, default=False)
    remove_image_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), write_only=True, required=False, allow_empty=True)
    likes_count = serializers.IntegerField(read_only=True)
    comments_count = serializers.IntegerField(read_only=True)
    liked_by_me = serializers.BooleanField(read_only=True)
    hashtags = serializers.SerializerMethodField()
    class Meta:
        model = Post
        fields = ["id", "author", "content", "is_public", "images", "uploaded_images", "uploaded_image_urls", "replace_images", "remove_image_ids", "likes_count", "comments_count", "liked_by_me", "shares_count", "hashtags", "created_at", "updated_at"]
        read_only_fields = ["id", "author", "shares_count", "created_at", "updated_at"]
    def validate_uploaded_images(self, images):
        if len(images) > 6:
            raise serializers.ValidationError("You can add up to 6 images to one post.")
        for image in images:
            if image.size > settings.MAX_UPLOAD_SIZE:
                raise serializers.ValidationError("Each image must be 8 MB or smaller.")
        return images
    def validate_uploaded_image_urls(self, urls):
        request = self.context.get("request")
        user_id = getattr(getattr(request, "user", None), "pk", None)
        if user_id is None or any(not is_user_blob_url(url, user_id, {"posts"}) for url in urls):
            raise serializers.ValidationError("Each image must be a valid image uploaded to your Linkora storage.")
        return urls
    def validate(self, attrs):
        content = attrs.get("content", self.instance.content if self.instance else "")
        image_uploads = attrs.get("uploaded_images", [])
        image_urls = attrs.get("uploaded_image_urls", [])
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
        if remaining_images + len(image_uploads) + len(image_urls) > 6:
            raise serializers.ValidationError({"uploaded_images": "A post can contain up to 6 images."})
        if not content.strip() and remaining_images + len(image_uploads) + len(image_urls) == 0:
            raise serializers.ValidationError({"content": "Add some text or at least one image to your post."})
        return attrs
    def get_hashtags(self, obj):
        return [link.hashtag.name for link in obj.hashtag_links.select_related("hashtag").all()]
    def create(self, validated_data):
        images = validated_data.pop("uploaded_images", [])
        image_urls = validated_data.pop("uploaded_image_urls", [])
        validated_data.pop("replace_images", None)
        validated_data.pop("remove_image_ids", None)
        if images or image_urls:
            validated_data["is_public"] = False
            validated_data["followers_only"] = True
        post = Post.objects.create(**validated_data)
        for image in images:
            PostImage.objects.create(post=post, image=image)
        for image_url in image_urls:
            PostImage.objects.create(post=post, image=image_url)
        sync_hashtags(post)
        return post
    def update(self, instance, validated_data):
        images = validated_data.pop("uploaded_images", [])
        image_urls = validated_data.pop("uploaded_image_urls", [])
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
            for image_url in image_urls:
                PostImage.objects.create(post=instance, image=image_url)
            sync_hashtags(instance)
        return instance

def sync_hashtags(post):
    names = {name.lower() for name in re.findall(r"(?<!\w)#([\w]{1,80})", post.content)}
    post.hashtag_links.all().delete()
    for name in names:
        tag, _ = Hashtag.objects.get_or_create(name=name)
        PostHashtag.objects.get_or_create(post=post, hashtag=tag)

class StorySerializer(serializers.ModelSerializer):
    author = UserSerializer(read_only=True)
    media_url = serializers.SerializerMethodField()
    uploaded_media = serializers.FileField(write_only=True, required=False)
    uploaded_media_url = serializers.URLField(write_only=True, required=False, max_length=500)
    reactions_count = serializers.SerializerMethodField()
    reacted_by_me = serializers.SerializerMethodField()
    class Meta:
        model = Story
        fields = ["id", "author", "media_url", "media_type", "caption", "uploaded_media", "uploaded_media_url", "reactions_count", "reacted_by_me", "created_at", "expires_at"]
        read_only_fields = ["id", "author", "created_at", "expires_at"]
    def validate(self, attrs):
        media = attrs.get("uploaded_media")
        media_url = attrs.get("uploaded_media_url")
        media_type = attrs.get("media_type")
        if not media and not media_url:
            raise serializers.ValidationError({"uploaded_media": "Choose a photo or video for your story."})
        if media and media_url:
            raise serializers.ValidationError({"uploaded_media": "Upload the story media only once."})
        if media:
            content_type = getattr(media, "content_type", "")
            is_video = content_type.startswith("video/") or media.name.lower().endswith((".mp4", ".webm"))
            is_image = content_type.startswith("image/") or media.name.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))
            if (media_type == Story.VIDEO and not is_video) or (media_type == Story.IMAGE and not is_image):
                raise serializers.ValidationError({"media_type": "Choose a file that matches the selected story type."})
            if media.size > (settings.MAX_VIDEO_UPLOAD_SIZE if media_type == Story.VIDEO else settings.MAX_UPLOAD_SIZE):
                raise serializers.ValidationError({"uploaded_media": "Videos must be 100 MB or smaller; photos must be 8 MB or smaller."})
        if media_url:
            path = urlsplit(media_url).path.lower()
            is_video = path.endswith((".mp4", ".webm"))
            if (media_type == Story.VIDEO and not is_video) or (media_type == Story.IMAGE and is_video):
                raise serializers.ValidationError({"media_type": "Choose a story type that matches the uploaded file."})
        return attrs
    def validate_uploaded_media_url(self, value):
        request = self.context.get("request")
        if not request or not is_user_blob_url(value, request.user.pk, {"stories"}):
            raise serializers.ValidationError("Choose media uploaded to your Linkora storage.")
        return value
    def create(self, validated_data):
        media = validated_data.pop("uploaded_media", None)
        media_url = validated_data.pop("uploaded_media_url", None)
        return Story.objects.create(media=media or media_url, **validated_data)
    def get_media_url(self, obj):
        request = self.context.get("request")
        url = obj.media.url
        return request.build_absolute_uri(url) if request and not url.startswith("https://") else url
    def get_reactions_count(self, obj):
        return obj.reactions.count()
    def get_reacted_by_me(self, obj):
        request = self.context.get("request")
        return bool(request and request.user.is_authenticated and obj.reactions.filter(user=request.user).exists())

class StoryReactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = StoryReaction
        fields = ["id", "emoji", "created_at"]
        read_only_fields = ["id", "created_at"]
    def validate_emoji(self, value):
        if value not in {"❤️", "😂", "😮", "😢", "👏", "🔥"}:
            raise serializers.ValidationError("Choose one of the available story reactions.")
        return value

class StoryReplySerializer(serializers.ModelSerializer):
    author = UserSerializer(read_only=True)
    class Meta:
        model = StoryReply
        fields = ["id", "author", "content", "created_at"]
        read_only_fields = ["id", "author", "created_at"]
    def validate_content(self, value):
        if not value.strip():
            raise serializers.ValidationError("Reply cannot be empty.")
        return value.strip()

class ReelSerializer(serializers.ModelSerializer):
    author = UserSerializer(read_only=True)
    video_url = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()
    uploaded_video = serializers.FileField(write_only=True, required=False)
    uploaded_video_url = serializers.URLField(write_only=True, required=False, max_length=500)
    uploaded_thumbnail = serializers.ImageField(write_only=True, required=False)
    uploaded_thumbnail_url = serializers.URLField(write_only=True, required=False, max_length=500)
    likes_count = serializers.SerializerMethodField()
    comments_count = serializers.SerializerMethodField()
    liked_by_me = serializers.SerializerMethodField()
    saved_by_me = serializers.SerializerMethodField()
    class Meta:
        model = Reel
        fields = ["id", "author", "video_url", "thumbnail_url", "caption", "filter_name", "shares_count", "likes_count", "comments_count", "liked_by_me", "saved_by_me", "uploaded_video", "uploaded_video_url", "uploaded_thumbnail", "uploaded_thumbnail_url", "created_at"]
        read_only_fields = ["id", "author", "shares_count", "created_at"]
    def validate(self, attrs):
        video = attrs.get("uploaded_video")
        video_url = attrs.get("uploaded_video_url")
        thumbnail = attrs.get("uploaded_thumbnail")
        thumbnail_url = attrs.get("uploaded_thumbnail_url")
        if not video and not video_url:
            raise serializers.ValidationError({"uploaded_video": "Choose a video for your reel."})
        if video and video_url:
            raise serializers.ValidationError({"uploaded_video": "Upload the video only once."})
        if thumbnail and thumbnail_url:
            raise serializers.ValidationError({"uploaded_thumbnail": "Upload the thumbnail only once."})
        if video:
            content_type = getattr(video, "content_type", "")
            if not (content_type in {"video/mp4", "video/webm"} or video.name.lower().endswith((".mp4", ".webm"))):
                raise serializers.ValidationError({"uploaded_video": "Reels must be MP4 or WebM videos."})
            if video.size > settings.MAX_VIDEO_UPLOAD_SIZE:
                raise serializers.ValidationError({"uploaded_video": f"Reels must be {settings.MAX_VIDEO_UPLOAD_SIZE // (1024 * 1024)} MB or smaller."})
        if thumbnail and thumbnail.size > 8 * 1024 * 1024:
            raise serializers.ValidationError({"uploaded_thumbnail": "Thumbnails must be 8 MB or smaller."})
        return attrs
    def validate_uploaded_video_url(self, value):
        request = self.context.get("request")
        if not request or not is_user_blob_url(value, request.user.pk, {"reels"}):
            raise serializers.ValidationError("Choose a video uploaded to your Linkora storage.")
        return value
    def validate_uploaded_thumbnail_url(self, value):
        request = self.context.get("request")
        if not request or not is_user_blob_url(value, request.user.pk, {"reel-thumbnails"}):
            raise serializers.ValidationError("Choose a thumbnail uploaded to your Linkora storage.")
        return value
    def create(self, validated_data):
        video = validated_data.pop("uploaded_video", None)
        video_url = validated_data.pop("uploaded_video_url", None)
        thumbnail = validated_data.pop("uploaded_thumbnail", None)
        thumbnail_url = validated_data.pop("uploaded_thumbnail_url", None)
        return Reel.objects.create(video=video or video_url, thumbnail=thumbnail or thumbnail_url or "", **validated_data)
    def _field_url(self, obj, field_name):
        value = getattr(obj, field_name)
        if not value:
            return None
        request = self.context.get("request")
        url = value.url
        return request.build_absolute_uri(url) if request and not url.startswith("https://") else url
    def get_video_url(self, obj):
        return self._field_url(obj, "video")
    def get_thumbnail_url(self, obj):
        return self._field_url(obj, "thumbnail")
    def get_likes_count(self, obj):
        return obj.likes.count()
    def get_comments_count(self, obj):
        return obj.comments.count()
    def get_liked_by_me(self, obj):
        request = self.context.get("request")
        return bool(request and request.user.is_authenticated and obj.likes.filter(user=request.user).exists())
    def get_saved_by_me(self, obj):
        request = self.context.get("request")
        return bool(request and request.user.is_authenticated and obj.saves.filter(user=request.user).exists())

class ReelCommentSerializer(serializers.ModelSerializer):
    author = UserSerializer(read_only=True)
    class Meta:
        model = ReelComment
        fields = ["id", "author", "content", "created_at"]
        read_only_fields = ["id", "author", "created_at"]
    def validate_content(self, value):
        if not value.strip():
            raise serializers.ValidationError("Comment cannot be empty.")
        return value.strip()

class NotificationSerializer(serializers.ModelSerializer):
    actor = UserSerializer(read_only=True)
    post_preview = serializers.CharField(source="post.content", read_only=True, default="")
    story_author_id = serializers.SerializerMethodField()
    class Meta:
        model = Notification
        fields = ["id", "actor", "kind", "post", "comment", "story", "story_author_id", "post_preview", "is_read", "created_at"]
    def get_story_author_id(self, obj):
        return obj.story.author_id if obj.story_id else None

class FollowSerializer(serializers.ModelSerializer):
    follower = UserSerializer(read_only=True)
    following = UserSerializer(read_only=True)
    class Meta:
        model = Follow
        fields = ["id", "follower", "following", "created_at"]
