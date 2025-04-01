from django.urls import path
from . import views

urlpatterns = [
    path('extract/', views.extract_data_view, name='extract_data'),
]