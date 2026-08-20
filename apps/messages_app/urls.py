from django.urls import path
from . import views

urlpatterns = [
    path('', views.messages_list, name='messages_list'),
    path('<int:pk>/', views.message_detail, name='message_detail'),
    path('<int:pk>/delete/', views.message_delete, name='message_delete'),
]
