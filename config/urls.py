from django.contrib import admin
from django.urls import include, path
from exchange.api import router, LoginTokenView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/token/', LoginTokenView.as_view(), name='api-token'),
    path('api/', include(router.urls)),
    path('api-auth/', include('rest_framework.urls')),
    path('', include('exchange.urls')),
]
