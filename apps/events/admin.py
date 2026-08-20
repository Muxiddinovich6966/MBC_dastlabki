from django.contrib import admin
from .models import Event, EventReminder, UserEvent, EventSendLog, Lead, LeadStatusLog


class EventReminderInline(admin.TabularInline):
    model = EventReminder
    extra = 1


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('name', 'date', 'time', 'location', 'category', 'sent', 'is_active')
    list_filter = ('category', 'sent', 'is_active')
    search_fields = ('name', 'location', 'speaker')
    filter_horizontal = ('send_groups',)
    inlines = [EventReminderInline]


@admin.register(UserEvent)
class UserEventAdmin(admin.ModelAdmin):
    list_display = ('user', 'event', 'rsvp_choice', 'is_attendance', 'created_at')
    list_filter = ('rsvp_choice', 'is_attendance')


@admin.register(EventSendLog)
class EventSendLogAdmin(admin.ModelAdmin):
    list_display = ('event', 'target_type', 'user', 'group', 'status', 'message_id', 'updated_at')
    list_filter = ('target_type', 'status')
    search_fields = ('event__name', 'chat_id')


class LeadStatusLogInline(admin.TabularInline):
    model = LeadStatusLog
    extra = 0
    readonly_fields = ('old_status', 'new_status', 'changed_by', 'note', 'created_at')
    can_delete = False


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'phone', 'event', 'status', 'status_changed_at', 'created_at')
    list_filter = ('status', 'event')
    search_fields = ('full_name', 'phone', 'event__name')
    inlines = [LeadStatusLogInline]


@admin.register(LeadStatusLog)
class LeadStatusLogAdmin(admin.ModelAdmin):
    list_display = ('lead', 'old_status', 'new_status', 'changed_by', 'created_at')
    list_filter = ('new_status',)
    search_fields = ('lead__full_name', 'lead__phone')
