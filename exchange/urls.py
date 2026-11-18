from django.contrib.auth import views as auth_views
from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('signup/', views.signup, name='signup'),
    path('login/', auth_views.LoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('parts/new/', views.part_create, name='part-create'),
    path('parts/<int:pk>/', views.part_detail, name='part-detail'),
    path('parts/<int:pk>/edit/', views.part_edit, name='part-edit'),
    path('parts/<int:pk>/withdraw/', views.part_withdraw, name='part-withdraw'),
    path('parts/<int:pk>/reserve/', views.part_reserve, name='part-reserve'),
    path('parts/<int:pk>/report/', views.part_report, name='part-report'),
    path('reservations/<int:pk>/cancel/', views.reservation_cancel, name='reservation-cancel'),
    path('reservations/<int:pk>/collect/', views.reservation_collect, name='reservation-collect'),
    path('how-it-works/', views.about, name='about'),
    path('developer/', views.api_docs, name='api-docs'),
]
