from django.contrib import admin
from .models import Conversation, Message, Call, CallSignal
admin.site.register([Conversation, Message, Call, CallSignal])
