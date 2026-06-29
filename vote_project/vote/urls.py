
from django.contrib import admin
from django.urls import path, include


urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),
    
    # Include poll app URLs
    path('api/', include('poll.urls')),  # All API endpoints under /api/
]