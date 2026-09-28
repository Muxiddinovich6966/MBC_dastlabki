from django.contrib import admin
from .models import Worker, Template, TemplateTask, WorkEvent, Task, NotificationLog


class TemplateTaskInline(admin.TabularInline):
    model = TemplateTask
    extra = 1
    fields = ('description', 'days_before', 'hours_before', 'workers', 'instruction')


@admin.register(Worker)
class WorkerAdmin(admin.ModelAdmin):
    list_display = ('name', 'telegram_id', 'role', 'department', 'is_head')
    list_filter = ('role', 'department', 'is_head')
    list_editable = ('is_head',)
    search_fields = ('name',)


@admin.register(Template)
class TemplateAdmin(admin.ModelAdmin):
    list_display = ('name',)
    inlines = [TemplateTaskInline]


@admin.register(WorkEvent)
class WorkEventAdmin(admin.ModelAdmin):
    list_display = ('name', 'event_date', 'event_time', 'template')


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('description', 'event', 'deadline_date', 'status', 'completed_by')
    list_filter = ('status',)
    filter_horizontal = ('workers',)
