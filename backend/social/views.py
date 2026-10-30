from django.contrib.auth import get_user_model
from django.db.models import Count, Exists, OuterRef, Q, Case, When, IntegerField, F
from django.db.models import Value, BooleanField
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status, viewsets
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import Post, PostImage, Like, Comment, Follow, Notification, Hashtag
from .serializers import PostSerializer, CommentSerializer, UserSerializer, NotificationSerializer, FollowSerializer

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

class PostViewSet(viewsets.ModelViewSet):
    serializer_class = PostSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    def get_queryset(self):
        user = self.request.user
        qs = Post.objects.filter(Q(is_public=True) | Q(author=user)) if user.is_authenticated else Post.objects.filter(is_public=True)
        username = self.request.query_params.get("username")
        if username:
            qs = qs.filter(author__username=username)
        if user.is_authenticated:
            followed = Follow.objects.filter(follower=user, following=OuterRef("author_id"))
            qs = qs.annotate(from_followed=Exists(followed)).order_by(Case(When(from_followed=True, then=0), default=1, output_field=IntegerField()), "-created_at")
        if not user.is_authenticated:
            qs = qs.order_by("-created_at")
        return decorate_posts(qs, user)
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(author=request.user)
        return Response(self.get_serializer(decorate_posts(Post.objects.filter(pk=serializer.instance.pk), request.user).get()).data, status=201)

class PostDetailView(APIView):
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    def get(self, request, pk):
        visible = Post.objects.filter(Q(is_public=True) | Q(author=request.user)) if request.user.is_authenticated else Post.objects.filter(is_public=True)
        post = get_object_or_404(visible, pk=pk)
        return Response(PostSerializer(decorate_posts(Post.objects.filter(pk=post.pk), request.user).get(), context={"request": request}).data)
    def patch(self, request, pk):
        post = get_object_or_404(Post, pk=pk)
        if post.author_id != request.user.id and not request.user.is_staff:
            raise PermissionDenied("You can only edit your own posts.")
        serializer = PostSerializer(post, data=request.data, partial=True, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
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
        visible = Post.objects.filter(Q(is_public=True) | Q(author=request.user))
        post = get_object_or_404(visible, pk=post_id)
        like, created = Like.objects.get_or_create(user=request.user, post=post)
        if created and post.author_id != request.user.id:
            Notification.objects.create(recipient=post.author, actor=request.user, kind=Notification.LIKE, post=post)
        return Response({"liked": True, "likes_count": post.likes.count()}, status=201 if created else 200)
    def delete(self, request, post_id):
        visible = Post.objects.filter(Q(is_public=True) | Q(author=request.user))
        post = get_object_or_404(visible, pk=post_id)
        Like.objects.filter(user=request.user, post=post).delete()
        return Response({"liked": False, "likes_count": post.likes.count()})

class PostLikesView(generics.ListAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.AllowAny]
    def get_queryset(self):
        post_query = Post.objects.filter(pk=self.kwargs["post_id"])
        if self.request.user.is_authenticated:
            post_query = post_query.filter(Q(is_public=True) | Q(author=self.request.user))
        else:
            post_query = post_query.filter(is_public=True)
        post = get_object_or_404(post_query, pk=self.kwargs["post_id"])
        user_ids = Like.objects.filter(post=post).values_list("user_id", flat=True)
        return decorate_users(User.objects.filter(pk__in=user_ids), self.request.user).order_by("username")

class ShareView(APIView):
    def post(self, request, post_id):
        visible = Post.objects.filter(Q(is_public=True) | Q(author=request.user)) if request.user.is_authenticated else Post.objects.filter(is_public=True)
        post = get_object_or_404(visible, pk=post_id)
        Post.objects.filter(pk=post.pk).update(shares_count=F("shares_count") + 1)
        post.refresh_from_db(fields=["shares_count"])
        return Response({"shares_count": post.shares_count})

class CommentListCreateView(generics.ListCreateAPIView):
    serializer_class = CommentSerializer
    def get_queryset(self):
        post_query = Post.objects.filter(pk=self.kwargs["post_id"])
        if self.request.user.is_authenticated:
            post_query = post_query.filter(Q(is_public=True) | Q(author=self.request.user))
        else:
            post_query = post_query.filter(is_public=True)
        get_object_or_404(post_query, pk=self.kwargs["post_id"])
        return Comment.objects.filter(post_id=self.kwargs["post_id"], parent__isnull=True).select_related("author")
    def perform_create(self, serializer):
        post = get_object_or_404(Post, pk=self.kwargs["post_id"])
        if not post.is_public and post.author_id != self.request.user.id:
            raise PermissionDenied()
        comment = serializer.save(author=self.request.user, post=post)
        if post.author_id != self.request.user.id:
            Notification.objects.create(recipient=post.author, actor=self.request.user, kind=Notification.COMMENT, post=post, comment=comment)

class CommentDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Comment.objects.select_related("author", "post")
    serializer_class = CommentSerializer
    def get_object(self):
        comment = super().get_object()
        if not comment.post.is_public and comment.post.author_id != self.request.user.id and not self.request.user.is_staff:
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
        allowed = {"full_name", "bio", "location", "website", "avatar", "cover_image"}
        data = {key: value for key, value in request.data.items() if key in allowed}
        serializer = UserSerializer(request.user, data=data, partial=True, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
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
        return Notification.objects.filter(recipient=self.request.user).select_related("actor", "post").order_by("-created_at")
    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        response.data["unread_count"] = Notification.objects.filter(recipient=request.user, is_read=False).count()
        return response

class NotificationReadView(APIView):
    def patch(self, request, pk):
        notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
        notification.is_read = True
        notification.save(update_fields=["is_read"])
        return Response(NotificationSerializer(notification, context={"request": request}).data)

class ReadAllNotificationsView(APIView):
    def post(self, request):
        Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
        return Response({"unread_count": 0})

class SearchView(APIView):
    permission_classes = [permissions.AllowAny]
    def get(self, request):
        query = request.query_params.get("q", "").strip()
        if not query:
            return Response({"users": [], "posts": [], "hashtags": []})
        users = decorate_users(User.objects.filter(Q(username__icontains=query) | Q(profile__full_name__icontains=query), is_active=True), request.user).order_by("username")[:8]
        posts_qs = decorate_posts(Post.objects.filter(Q(is_public=True) & (Q(content__icontains=query) | Q(hashtag_links__hashtag__name__icontains=query))).distinct(), request.user).order_by("-created_at")[:12]
        tag_query = query.lstrip("#").lower()
        hashtags = list(Hashtag.objects.filter(name__icontains=tag_query).annotate(posts_count=Count("post_links")).values("id", "name", "posts_count")[:8])
        return Response({"users": UserSerializer(users, many=True, context={"request": request}).data,
            "posts": PostSerializer(posts_qs, many=True, context={"request": request}).data, "hashtags": hashtags})

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
