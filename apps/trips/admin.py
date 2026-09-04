from django.contrib import admin
from .models import Trip, TripParticipant, TripCountry


@admin.register(TripCountry)
class TripCountryAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at')
    search_fields = ('name',)


class TripParticipantInline(admin.TabularInline):
    model = TripParticipant
    extra = 0
    fields = ('order', 'status', 'full_name', 'travel_status', 'subscription',
              'entry_sum', 'trip_sum', 'deposit', 'paid', 'payment_status', 'comment')


@admin.register(Trip)
class TripAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name',)
    inlines = [TripParticipantInline]


@admin.register(TripParticipant)
class TripParticipantAdmin(admin.ModelAdmin):
    list_display = ('display_name', 'trip', 'status', 'travel_status', 'payment_status', 'must_pay', 'remaining')
    list_filter = ('trip', 'status', 'travel_status', 'payment_status')
    search_fields = ('full_name', 'user__tg_username')
