from django.urls import path
from . import views

urlpatterns = [
    path('', views.groups_list, name='groups_list'),
    path('<int:pk>/edit/', views.group_edit, name='group_edit'),
    path('<int:pk>/delete/', views.group_delete, name='group_delete'),
]
