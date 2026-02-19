from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('countries/', views.country_index, name='country_index'),
    path('countries/<str:code>/', views.country_detail, name='country_detail'),
]
