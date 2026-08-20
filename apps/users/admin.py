from django.contrib import admin
from .models import User, UserProfile, UserPlan, TripsSendLog


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    extra = 0


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('id', 'tg_id', 'tg_username', 'role', 'is_active', 'created_at')
    list_filter = ('role', 'is_active')
    search_fields = ('tg_id', 'tg_username', 'tg_phone')
    inlines = [UserProfileInline]


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('name', 'surname', 'phone', 'industry', 'work_location')
    search_fields = ('name', 'surname', 'phone')


@admin.register(UserPlan)
class UserPlanAdmin(admin.ModelAdmin):
    list_display = ('user', 'price', 'start_date', 'end_date', 'payment_type', 'created_at')
    list_filter = ('payment_type', 'start_date', 'end_date')
    search_fields = ('user__tg_username', 'user__tg_id')
    date_hierarchy = 'end_date'


@admin.register(TripsSendLog)
class TripsSendLogAdmin(admin.ModelAdmin):
    list_display = ('profile', 'sent_by', 'was_member', 'success', 'created_at')
    list_filter = ('success', 'was_member', 'sent_by')
    search_fields = ('profile__name', 'profile__surname', 'profile__phone')
    date_hierarchy = 'created_at'