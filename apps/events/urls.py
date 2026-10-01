from django.urls import path
from . import views
from .calendar_ics import event_ics, event_calendar_page

urlpatterns = [
    path('', views.events_list, name='events_list'),
    path('<int:pk>/calendar/', event_calendar_page, name='event_calendar_page'),
    path('<int:pk>/calendar.ics', event_ics, name='event_ics'),
    path('<int:pk>/', views.event_detail, name='event_detail'),
    path('<int:pk>/delete/', views.event_delete, name='event_delete'),
    path('<int:pk>/edit/', views.event_edit, name='event_edit'),
    path('<int:pk>/send/', views.event_send_now, name='event_send_now'),
    path('<int:pk>/group/<int:group_id>/delete-message/', views.event_group_message_delete, name='event_group_message_delete'),
    path('<int:pk>/checkin/', views.event_checkin, name='event_checkin'),
    path('<int:pk>/toggle/', views.event_toggle_active, name='event_toggle_active'),
    path('rejection/<int:pk>/seen/', views.event_rejection_dismiss, name='event_rejection_dismiss'),
    path('leads/', views.leads_list, name='leads_list'),
    path('leads/<int:pk>/edit/', views.lead_edit, name='lead_edit'),
    path('leads/<int:pk>/delete/', views.lead_delete, name='lead_delete'),
    path('leads/<int:pk>/status/', views.lead_change_status, name='lead_change_status'),
    path('venues/', views.venues_list, name='venues_list'),
    path('venues/<int:pk>/delete/', views.venue_delete, name='venue_delete'),
    path('create/', views.event_wizard, name='event_wizard'),
    path('create/new/', views.event_create_form, name='event_create_form'),
    path('planner/', views.planner_view, name='planner'),
    path('planner/add/', views.planner_add, name='planner_add'),
    path('planner/<int:pk>/delete/', views.planner_delete, name='planner_delete'),
]
