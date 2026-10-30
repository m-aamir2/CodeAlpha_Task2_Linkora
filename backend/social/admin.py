from django.contrib import admin
from .models import Post, PostImage, Like, Comment, Follow, Notification, Hashtag, PostHashtag
admin.site.register([Post, PostImage, Like, Comment, Follow, Notification, Hashtag, PostHashtag])
