"""
Loyihaning bosh URL ro'yxati.
Har bir app o'z urls.py ga ega, shu yerda ularga yo'l ko'rsatiladi.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from .auth_views import login_view, logout_view
from apps.events.views import calendar_view

urlpatterns = [
    path('django-admin/', admin.site.urls),

    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),

    path('calendar/', calendar_view, name='calendar'),

    path('', include('apps.users.urls')),
    path('events/', include('apps.events.urls')),
    path('groups/', include('apps.groups.urls')),
    path('messages/', include('apps.messages_app.urls')),
    path('workers/', include('apps.workers.urls')),
    path('trips/', include('apps.trips.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
