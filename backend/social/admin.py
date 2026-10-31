from django.contrib import admin
from .models import Post, PostImage, Like, Comment, Follow, Notification, Hashtag, PostHashtag, Story, StoryReaction, StoryReply, Reel, ReelLike, ReelSave, ReelComment
admin.site.register([Post, PostImage, Like, Comment, Follow, Notification, Hashtag, PostHashtag, Story, StoryReaction, StoryReply, Reel, ReelLike, ReelSave, ReelComment])
