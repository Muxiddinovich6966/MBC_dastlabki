from django.contrib import admin
from .models import Group


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ('title', 'tg_id', 'created_at')
    search_fields = ('title', 'tg_id')
