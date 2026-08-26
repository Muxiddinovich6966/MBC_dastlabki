from django.urls import path
from . import views

urlpatterns = [
    path('', views.workers_list, name='workers_list'),
    path('<int:pk>/edit/', views.worker_edit, name='worker_edit'),
    path('<int:pk>/delete/', views.worker_delete, name='worker_delete'),

    path('templates/', views.templates_list, name='templates_list'),
    path('templates/<int:pk>/', views.template_detail, name='template_detail'),
    path('templates/<int:pk>/edit/', views.template_edit, name='template_edit'),
    path('templates/<int:pk>/delete/', views.template_delete, name='template_delete'),
    path('template-task/<int:pk>/edit/', views.template_task_edit, name='template_task_edit'),
    path('template-task/<int:pk>/delete/', views.template_task_delete, name='template_task_delete'),

    path('work-events/', views.work_events_list, name='work_events_list'),
    path('work-events/<int:pk>/', views.work_event_detail, name='work_event_detail'),
    path('work-events/<int:pk>/edit/', views.work_event_edit, name='work_event_edit'),
    path('work-events/<int:pk>/delete/', views.work_event_delete, name='work_event_delete'),
]