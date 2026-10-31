import hmac
import os
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, Exists, OuterRef, Q, F
from django.db.models import Value, BooleanField
from django.shortcuts import get_object_or_404
from django.utils import timezone
from accounts.models import UserProfile
from rest_framework import generics, permissions, status, viewsets
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import Post, PostImage, Like, Comment, Follow, Notification, Hashtag, Story, StoryReaction, StoryReply, Reel, ReelLike, ReelSave, ReelComment
from .serializers import PostSerializer, CommentSerializer, UserSerializer, NotificationSerializer, FollowSerializer, StorySerializer, StoryReactionSerializer, StoryReplySerializer, ReelSerializer, ReelCommentSerializer
from .services import MENTION_PATTERN, cleanup_expired_stories, notify_mentions
from .realtime import publish_notification_event

User = get_user_model()

def decorate_users(queryset, current_user=None):
    queryset = queryset.annotate(posts_count=Count("posts", distinct=True), followers_count=Count("follower_links", distinct=True), following_count=Count("following_links", distinct=True))
    if current_user and current_user.is_authenticated:
        queryset = queryset.annotate(is_following=Exists(Follow.objects.filter(follower=current_user, following=OuterRef("pk"))))
    else:
        queryset = queryset.annotate(is_following=Value(False, output_field=BooleanField()))
    return queryset

def decorate_posts(queryset, current_user=None):
    queryset = queryset.select_related("author").prefetch_related("images", "hashtag_links__hashtag").annotate(likes_count=Count("likes", distinct=True), comments_count=Count("comments", distinct=True))
    if current_user and current_user.is_authenticated:
        queryset = queryset.annotate(liked_by_me=Exists(Like.objects.filter(post=OuterRef("pk"), user=current_user)))
    else:
        queryset = queryset.annotate(liked_by_me=Value(False, output_field=BooleanField()))
    return queryset

def visible_posts_for(user):
    queryset = Post.objects.filter(is_public=True)
    if user and user.is_authenticated:
        queryset = queryset | Post.objects.filter(author=user)
        queryset = queryset | Post.objects.filter(followers_only=True, author__follower_links__follower=user)
    return queryset.distinct()

class PostViewSet(viewsets.ModelViewSet):
    serializer_class = PostSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    def get_queryset(self):
        user = self.request.user
        username = self.request.query_params.get("username")
        if username:
            qs = visible_posts_for(user).filter(author__username=username).order_by("-created_at")
        elif user.is_authenticated:
            qs = Post.objects.filter(
                author__follower_links__follower=user,
            ).filter(Q(is_public=True) | Q(followers_only=True)).order_by("-created_at").distinct()
        else:
            qs = Post.objects.none()
        return decorate_posts(qs, user)
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(author=request.user)
        notify_mentions(serializer.instance.content, request.user, post=serializer.instance)
        return Response(self.get_serializer(decorate_posts(Post.objects.filter(pk=serializer.instance.pk), request.user).get()).data, status=201)

class PostDetailView(APIView):
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    def get(self, request, pk):
        post = get_object_or_404(visible_posts_for(request.user), pk=pk)
        return Response(PostSerializer(decorate_posts(Post.objects.filter(pk=post.pk), request.user).get(), context={"request": request}).data)
    def patch(self, request, pk):
        post = get_object_or_404(Post, pk=pk)
        if post.author_id != request.user.id and not request.user.is_staff:
            raise PermissionDenied("You can only edit your own posts.")
        old_content = post.content
        serializer = PostSerializer(post, data=request.data, partial=True, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        if post.content != old_content:
            notify_mentions(post.content, request.user, post=post, exclude=MENTION_PATTERN.findall(old_content))
        post = decorate_posts(Post.objects.filter(pk=pk), request.user).get()
        return Response(PostSerializer(post, context={"request": request}).data)
    def delete(self, request, pk):
        post = get_object_or_404(Post, pk=pk)
        if post.author_id != request.user.id and not request.user.is_staff:
            raise PermissionDenied("You can only delete your own posts.")
        post.delete()
        return Response(status=204)

class LikeView(APIView):
    def post(self, request, post_id):
        post = get_object_or_404(visible_posts_for(request.user), pk=post_id)
        like, created = Like.objects.get_or_create(user=request.user, post=post)
        if created and post.author_id != request.user.id:
            Notification.objects.create(recipient=post.author, actor=request.user, kind=Notification.LIKE, post=post)
        return Response({"liked": True, "likes_count": post.likes.count()}, status=201 if created else 200)
    def delete(self, request, post_id):
        post = get_object_or_404(visible_posts_for(request.user), pk=post_id)
        Like.objects.filter(user=request.user, post=post).delete()
        return Response({"liked": False, "likes_count": post.likes.count()})

class PostLikesView(generics.ListAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.AllowAny]
    def get_queryset(self):
        post_query = visible_posts_for(self.request.user)
        post = get_object_or_404(post_query, pk=self.kwargs["post_id"])
        user_ids = Like.objects.filter(post=post).values_list("user_id", flat=True)
        return decorate_users(User.objects.filter(pk__in=user_ids), self.request.user).order_by("username")

class ShareView(APIView):
    def post(self, request, post_id):
        post = get_object_or_404(visible_posts_for(request.user), pk=post_id)
        Post.objects.filter(pk=post.pk).update(shares_count=F("shares_count") + 1)
        post.refresh_from_db(fields=["shares_count"])
        return Response({"shares_count": post.shares_count})

class CommentListCreateView(generics.ListCreateAPIView):
    serializer_class = CommentSerializer
    def get_queryset(self):
        post_query = visible_posts_for(self.request.user)
        get_object_or_404(post_query, pk=self.kwargs["post_id"])
        return Comment.objects.filter(post_id=self.kwargs["post_id"], parent__isnull=True).select_related("author")
    def perform_create(self, serializer):
        post = get_object_or_404(visible_posts_for(self.request.user), pk=self.kwargs["post_id"])
        comment = serializer.save(author=self.request.user, post=post)
        if post.author_id != self.request.user.id:
            Notification.objects.create(recipient=post.author, actor=self.request.user, kind=Notification.COMMENT, post=post, comment=comment)
        if comment.parent_id and comment.parent.author_id not in {post.author_id, self.request.user.id}:
            Notification.objects.create(recipient=comment.parent.author, actor=self.request.user, kind=Notification.COMMENT, post=post, comment=comment)
        notify_mentions(comment.content, self.request.user, post=post, comment=comment)

class CommentDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Comment.objects.select_related("author", "post")
    serializer_class = CommentSerializer
    def get_object(self):
        comment = super().get_object()
        if not self.request.user.is_staff and not visible_posts_for(self.request.user).filter(pk=comment.post_id).exists():
            from rest_framework.exceptions import NotFound
            raise NotFound()
        if self.request.method not in permissions.SAFE_METHODS and comment.author_id != self.request.user.id and not self.request.user.is_staff:
            raise PermissionDenied("You can only edit or delete your own comments.")
        return comment

class UserListView(generics.ListAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.AllowAny]
    def get_queryset(self):
        query = self.request.query_params.get("q", "")
        qs = User.objects.filter(is_active=True).filter(Q(username__icontains=query) | Q(profile__full_name__icontains=query)) if query else User.objects.filter(is_active=True)
        return decorate_users(qs, self.request.user).order_by("username")

class UserProfileView(APIView):
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    def get(self, request, username=None):
        user = request.user if username is None and request.user.is_authenticated else get_object_or_404(User, username=username)
        user = decorate_users(User.objects.filter(pk=user.pk), request.user).get()
        return Response(UserSerializer(user, context={"request": request}).data)
    def patch(self, request, username=None):
        if username is not None and username != request.user.username:
            raise PermissionDenied("You can only update your own profile.")
        allowed = {"full_name", "bio", "location", "website", "avatar", "cover_image", "avatar_blob_url", "cover_blob_url"}
        data = {key: value for key, value in request.data.items() if key in allowed}
        serializer = UserSerializer(request.user, data=data, partial=True, context={"request": request})
        serializer.is_valid(raise_exception=True)
        avatar_uploaded = "avatar" in data or "avatar_blob_url" in data
        cover_uploaded = "cover_image" in data or "cover_blob_url" in data
        with transaction.atomic():
            serializer.save()
            profile = UserProfile.objects.get(user_id=request.user.pk)
            shared_images = []
            if avatar_uploaded and profile.avatar:
                shared_images.append((profile.avatar.name, f"{request.user.username}'s profile photo"))
            if cover_uploaded and profile.cover_image:
                shared_images.append((profile.cover_image.name, f"{request.user.username}'s cover photo"))
            if shared_images:
                if avatar_uploaded and cover_uploaded:
                    caption = "updated their profile photos."
                elif avatar_uploaded:
                    caption = "updated their profile photo."
                else:
                    caption = "updated their cover photo."
                post = Post.objects.create(author=request.user, content=caption, is_public=False, followers_only=True)
                PostImage.objects.bulk_create([
                    PostImage(post=post, image=image_name, alt_text=alt_text)
                    for image_name, alt_text in shared_images
                ])
        return Response(serializer.data)

class FollowView(APIView):
    def post(self, request, user_id):
        target = get_object_or_404(User, pk=user_id)
        if target.id == request.user.id:
            raise ValidationError({"detail": "You cannot follow yourself."})
        follow, created = Follow.objects.get_or_create(follower=request.user, following=target)
        if created:
            Notification.objects.create(recipient=target, actor=request.user, kind=Notification.FOLLOW)
        return Response({"following": True}, status=201 if created else 200)
    def delete(self, request, user_id):
        Follow.objects.filter(follower=request.user, following_id=user_id).delete()
        return Response({"following": False})

class FollowListView(generics.ListAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.AllowAny]
    def get_queryset(self):
        user = get_object_or_404(User, pk=self.kwargs["user_id"])
        if self.kwargs["relationship"] == "followers":
            ids = Follow.objects.filter(following=user).values_list("follower_id", flat=True)
        else:
            ids = Follow.objects.filter(follower=user).values_list("following_id", flat=True)
        return decorate_users(User.objects.filter(id__in=ids), self.request.user).order_by("username")

class NotificationListView(generics.ListAPIView):
    serializer_class = NotificationSerializer
    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user).select_related("actor__profile", "post", "story__author").order_by("-created_at")
    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        response.data["unread_count"] = Notification.objects.filter(recipient=request.user, is_read=False).count()
        return response

class NotificationReadView(APIView):
    def patch(self, request, pk):
        notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
        notification.is_read = True
        notification.save(update_fields=["is_read"])
        unread_count = Notification.objects.filter(recipient=request.user, is_read=False).count()
        publish_notification_event(request.user.pk, {
            "type": "notification.read", "notification_id": notification.pk, "unread_count": unread_count,
        })
        return Response(NotificationSerializer(notification, context={"request": request}).data)

class ReadAllNotificationsView(APIView):
    def post(self, request):
        Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
        publish_notification_event(request.user.pk, {"type": "notifications.read_all"})
        return Response({"unread_count": 0})

class SearchView(APIView):
    permission_classes = [permissions.AllowAny]
    def get(self, request):
        query = request.query_params.get("q", "").strip()
        if not query:
            return Response({"users": [], "posts": [], "hashtags": []})
        users = decorate_users(User.objects.filter(Q(username__icontains=query) | Q(profile__full_name__icontains=query), is_active=True), request.user).order_by("username")[:8]
        posts_qs = decorate_posts(visible_posts_for(request.user).filter(Q(content__icontains=query) | Q(hashtag_links__hashtag__name__icontains=query)).distinct(), request.user).order_by("-created_at")[:12]
        tag_query = query.lstrip("#").lower()
        hashtags = list(Hashtag.objects.filter(name__icontains=tag_query).annotate(posts_count=Count("post_links")).values("id", "name", "posts_count")[:8])
        return Response({"users": UserSerializer(users, many=True, context={"request": request}).data,
            "posts": PostSerializer(posts_qs, many=True, context={"request": request}).data, "hashtags": hashtags})

def get_visible_story(story_id, user):
    story = get_object_or_404(Story, pk=story_id, expires_at__gt=timezone.now())
    if story.author_id != user.pk and not Follow.objects.filter(follower=user, following_id=story.author_id).exists():
        from rest_framework.exceptions import NotFound
        raise NotFound()
    return story

class StoryListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        cleanup_expired_stories()
        followed_ids = Follow.objects.filter(follower=request.user).values_list("following_id", flat=True)
        stories = Story.objects.filter(expires_at__gt=timezone.now()).filter(Q(author=request.user) | Q(author_id__in=followed_ids)).select_related("author").order_by("created_at")
        return Response(StorySerializer(stories, many=True, context={"request": request}).data)
    def post(self, request):
        serializer = StorySerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        story = serializer.save(author=request.user)
        return Response(StorySerializer(story, context={"request": request}).data, status=201)

class StoryCleanupCronView(APIView):
    permission_classes = [permissions.AllowAny]
    def get(self, request):
        expected = os.getenv("CRON_SECRET", "")
        if not expected or not hmac.compare_digest(request.headers.get("Authorization", ""), f"Bearer {expected}"):
            return Response({"detail": "Not authorized."}, status=401)
        return Response({"deleted": cleanup_expired_stories()})

class StoryDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def delete(self, request, story_id):
        story = get_object_or_404(Story, pk=story_id, author=request.user)
        if story.media:
            story.media.delete(save=False)
        story.delete()
        return Response(status=204)

class StoryReactionView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def post(self, request, story_id):
        story = get_visible_story(story_id, request.user)
        serializer = StoryReactionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reaction, created = StoryReaction.objects.update_or_create(story=story, user=request.user, defaults={"emoji": serializer.validated_data["emoji"]})
        if created and story.author_id != request.user.id:
            Notification.objects.create(recipient=story.author, actor=request.user, kind=Notification.STORY_REACTION, story=story)
        return Response(StoryReactionSerializer(reaction).data)
    def delete(self, request, story_id):
        story = get_visible_story(story_id, request.user)
        StoryReaction.objects.filter(story=story, user=request.user).delete()
        return Response(status=204)

class StoryReplyListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request, story_id):
        story = get_visible_story(story_id, request.user)
        replies = story.replies.select_related("author").order_by("created_at")
        return Response(StoryReplySerializer(replies, many=True, context={"request": request}).data)
    def post(self, request, story_id):
        story = get_visible_story(story_id, request.user)
        serializer = StoryReplySerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        reply = serializer.save(story=story, author=request.user)
        if story.author_id != request.user.id:
            Notification.objects.create(recipient=story.author, actor=request.user, kind=Notification.STORY_REPLY, story=story)
        notify_mentions(reply.content, request.user, story=story)
        return Response(StoryReplySerializer(reply, context={"request": request}).data, status=201)

def get_visible_reel(reel_id, user):
    reel = get_object_or_404(Reel.objects.select_related("author"), pk=reel_id)
    if reel.author_id != user.pk and not Follow.objects.filter(follower=user, following_id=reel.author_id).exists():
        from rest_framework.exceptions import NotFound
        raise NotFound()
    return reel

class ReelListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        followed_ids = Follow.objects.filter(follower=request.user).values_list("following_id", flat=True)
        reels = Reel.objects.filter(Q(author=request.user) | Q(author_id__in=followed_ids)).select_related("author").order_by("-created_at").distinct()
        page = self.paginate_queryset(reels)
        serializer = ReelSerializer(page, many=True, context={"request": request})
        return self.get_paginated_response(serializer.data)
    def post(self, request):
        serializer = ReelSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        reel = serializer.save(author=request.user)
        return Response(ReelSerializer(reel, context={"request": request}).data, status=201)
    def paginate_queryset(self, queryset):
        from rest_framework.pagination import PageNumberPagination
        self.paginator = PageNumberPagination()
        return self.paginator.paginate_queryset(queryset, self.request, view=self)
    def get_paginated_response(self, data):
        return self.paginator.get_paginated_response(data)

class ReelLikeView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def post(self, request, reel_id):
        reel = get_visible_reel(reel_id, request.user)
        _, created = ReelLike.objects.get_or_create(reel=reel, user=request.user)
        return Response({"liked": True, "likes_count": reel.likes.count()}, status=201 if created else 200)
    def delete(self, request, reel_id):
        reel = get_visible_reel(reel_id, request.user)
        ReelLike.objects.filter(reel=reel, user=request.user).delete()
        return Response({"liked": False, "likes_count": reel.likes.count()})

class ReelSaveView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def post(self, request, reel_id):
        reel = get_visible_reel(reel_id, request.user)
        _, created = ReelSave.objects.get_or_create(reel=reel, user=request.user)
        return Response({"saved": True}, status=201 if created else 200)
    def delete(self, request, reel_id):
        reel = get_visible_reel(reel_id, request.user)
        ReelSave.objects.filter(reel=reel, user=request.user).delete()
        return Response({"saved": False})

class ReelShareView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def post(self, request, reel_id):
        reel = get_visible_reel(reel_id, request.user)
        Reel.objects.filter(pk=reel.pk).update(shares_count=F("shares_count") + 1)
        reel.refresh_from_db(fields=["shares_count"])
        return Response({"shares_count": reel.shares_count})

class ReelCommentListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request, reel_id):
        reel = get_visible_reel(reel_id, request.user)
        comments = reel.comments.select_related("author").order_by("created_at")
        return Response(ReelCommentSerializer(comments, many=True, context={"request": request}).data)
    def post(self, request, reel_id):
        reel = get_visible_reel(reel_id, request.user)
        serializer = ReelCommentSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        comment = serializer.save(reel=reel, author=request.user)
        return Response(ReelCommentSerializer(comment, context={"request": request}).data, status=201)

class AdminDashboardView(APIView):
    permission_classes = [permissions.IsAdminUser]
    def get(self, request):
        from moderation.models import Report
        return Response({"users": User.objects.count(), "posts": Post.objects.count(), "comments": Comment.objects.count(),
            "open_reports": Report.objects.filter(status=Report.OPEN).count(), "reports": Report.objects.order_by("-created_at")[:8].values("id", "target_type", "reason", "status", "created_at")})

class AdminUsersView(generics.ListAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAdminUser]
    def get_queryset(self):
        query = self.request.query_params.get("q", "")
        users = User.objects.all()
        if query:
            users = users.filter(Q(username__icontains=query) | Q(email__icontains=query))
        return decorate_users(users, self.request.user).order_by("username")

class AdminUserDetailView(APIView):
    permission_classes = [permissions.IsAdminUser]
    def patch(self, request, user_id):
        user = get_object_or_404(User, pk=user_id)
        if user.pk == request.user.pk and request.data.get("is_active") is False:
            raise ValidationError({"detail": "You cannot disable your own administrator account."})
        if "is_active" in request.data:
            user.is_active = bool(request.data["is_active"])
        user.save(update_fields=["is_active"])
        return Response(UserSerializer(decorate_users(User.objects.filter(pk=user.pk), request.user).get(), context={"request": request}).data)
