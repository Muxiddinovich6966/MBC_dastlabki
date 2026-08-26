from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('users/', views.users_list, name='users_list'),
    path('users/send-to-trips/', views.users_send_to_trips_start, name='users_send_to_trips_start'),
    path('users/send-to-trips/bulk/', views.users_send_to_trips_bulk, name='users_send_to_trips_bulk'),
    path('users/manual-add/', views.user_manual_add, name='user_manual_add'),
    path('users/<int:pk>/', views.user_detail, name='user_detail'),
    path('users/<int:pk>/edit/', views.user_edit, name='user_edit'),
    path('users/<int:pk>/delete/', views.user_delete, name='user_delete'),
    path('users/<int:pk>/photo/', views.user_photo_upload, name='user_photo_upload'),
    path('users/<int:pk>/send/', views.user_send_message, name='user_send_message'),
    path('users/<int:pk>/send-to-trips/', views.user_send_to_trips, name='user_send_to_trips'),
    path('users/<int:pk>/plan/add/', views.user_plan_add, name='user_plan_add'),
    path('users/<int:pk>/plan/<int:plan_pk>/delete/', views.user_plan_delete, name='user_plan_delete'),
]