from django.contrib import admin
from .models import SendMessage, SendMessageFile, SendMessageUser


class SendMessageFileInline(admin.TabularInline):
    model = SendMessageFile
    extra = 0


@admin.register(SendMessage)
class SendMessageAdmin(admin.ModelAdmin):
    list_display = ('title', 'tags', 'created_at')
    inlines = [SendMessageFileInline]


@admin.register(SendMessageUser)
class SendMessageUserAdmin(admin.ModelAdmin):
    list_display = ('send_message', 'user', 'status')
    list_filter = ('status',)
