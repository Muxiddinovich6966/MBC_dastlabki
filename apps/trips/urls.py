from django.urls import path
from . import views

urlpatterns = [
    path('', views.trips_list, name='trips_list'),
    path('<int:pk>/', views.trip_detail, name='trip_detail'),
    path('<int:pk>/delete/', views.trip_delete, name='trip_delete'),
    path('<int:pk>/add/', views.participant_add, name='trip_participant_add'),
    path('participant/<int:pk>/update/', views.participant_update, name='trip_participant_update'),
    path('participant/<int:pk>/delete/', views.participant_delete, name='trip_participant_delete'),
]
