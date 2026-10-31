from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from rest_framework_simplejwt.views import TokenRefreshView
from accounts.views import RegisterView, LoginView, LogoutView, PasswordResetRequestView, PasswordResetConfirmView, ChangePasswordView
from social.views import PostViewSet, PostDetailView, LikeView, PostLikesView, ShareView, CommentListCreateView, CommentDetailView, UserListView, UserProfileView, FollowView, FollowListView, NotificationListView, NotificationReadView, ReadAllNotificationsView, SearchView, AdminDashboardView, AdminUsersView, AdminUserDetailView, StoryListCreateView, StoryDetailView, StoryReactionView, StoryReplyListCreateView, StoryCleanupCronView, ReelListCreateView, ReelLikeView, ReelSaveView, ReelShareView, ReelCommentListCreateView
from messaging.views import ConversationListCreateView, ConversationMessagesView, MessageCreateView, CallListCreateView, CallDetailView, CallAcceptView, CallRejectView, CallEndView, CallSignalListCreateView
from moderation.views import ReportCreateView, AdminReportListView, AdminReportDetailView

admin.site.site_header = "Linkora administration"
admin.site.site_title = "Linkora Admin"
admin.site.index_title = "Platform dashboard"

post_list = PostViewSet.as_view({"get": "list", "post": "create"})
post_detail = PostDetailView.as_view()
urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/register/", RegisterView.as_view()), path("api/auth/login/", LoginView.as_view()),
    path("api/auth/refresh/", TokenRefreshView.as_view()), path("api/auth/logout/", LogoutView.as_view()),
    path("api/auth/password-reset/", PasswordResetRequestView.as_view()),
    path("api/auth/password-reset/confirm/", PasswordResetConfirmView.as_view()),
    path("api/auth/change-password/", ChangePasswordView.as_view()),
    path("api/users/", UserListView.as_view()), path("api/users/profile/", UserProfileView.as_view()),
    path("api/users/<str:username>/", UserProfileView.as_view()),
    path("api/users/<int:user_id>/follow/", FollowView.as_view()),
    path("api/users/<int:user_id>/followers/", FollowListView.as_view(), {"relationship": "followers"}),
    path("api/users/<int:user_id>/following/", FollowListView.as_view(), {"relationship": "following"}),
    path("api/posts/", post_list), path("api/posts/<int:pk>/", post_detail),
    path("api/posts/<int:post_id>/like/", LikeView.as_view()),
    path("api/posts/<int:post_id>/likes/", PostLikesView.as_view()),
    path("api/posts/<int:post_id>/share/", ShareView.as_view()),
    path("api/posts/<int:post_id>/comments/", CommentListCreateView.as_view()),
    path("api/comments/<int:pk>/", CommentDetailView.as_view()),
    path("api/stories/", StoryListCreateView.as_view()),
    path("api/cron/cleanup-stories/", StoryCleanupCronView.as_view()),
    path("api/stories/<int:story_id>/", StoryDetailView.as_view()),
    path("api/stories/<int:story_id>/reaction/", StoryReactionView.as_view()),
    path("api/stories/<int:story_id>/replies/", StoryReplyListCreateView.as_view()),
    path("api/reels/", ReelListCreateView.as_view()),
    path("api/reels/<int:reel_id>/like/", ReelLikeView.as_view()),
    path("api/reels/<int:reel_id>/save/", ReelSaveView.as_view()),
    path("api/reels/<int:reel_id>/share/", ReelShareView.as_view()),
    path("api/reels/<int:reel_id>/comments/", ReelCommentListCreateView.as_view()),
    path("api/notifications/", NotificationListView.as_view()),
    path("api/notifications/<int:pk>/read/", NotificationReadView.as_view()),
    path("api/notifications/read-all/", ReadAllNotificationsView.as_view()),
    path("api/search/", SearchView.as_view()),
    path("api/messages/conversations/", ConversationListCreateView.as_view()),
    path("api/messages/conversations/<int:pk>/", ConversationMessagesView.as_view()),
    path("api/messages/", MessageCreateView.as_view()),
    path("api/calls/", CallListCreateView.as_view()),
    path("api/calls/<int:call_id>/", CallDetailView.as_view()),
    path("api/calls/<int:call_id>/accept/", CallAcceptView.as_view()),
    path("api/calls/<int:call_id>/reject/", CallRejectView.as_view()),
    path("api/calls/<int:call_id>/end/", CallEndView.as_view()),
    path("api/calls/<int:call_id>/signals/", CallSignalListCreateView.as_view()),
    path("api/reports/", ReportCreateView.as_view()), path("api/admin/reports/", AdminReportListView.as_view()),
    path("api/admin/reports/<int:pk>/", AdminReportDetailView.as_view()),
    path("api/admin/dashboard/", AdminDashboardView.as_view()),
    path("api/admin/users/", AdminUsersView.as_view()), path("api/admin/users/<int:user_id>/", AdminUserDetailView.as_view()),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
