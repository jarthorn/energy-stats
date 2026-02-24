from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('countries/', views.country_index, name='country_index'),
    path('countries/<str:code>/', views.country_detail, name='country_detail'),
    path('countries/<str:code>/fuels/<str:fuel_type>/', views.country_fuel_detail, name='country_fuel_detail'),
]
