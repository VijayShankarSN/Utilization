from django.urls import path
from . import views

urlpatterns = [
    path('extract/', views.extract_data_view, name='extract_data'),
    path('', views.home_view, name='home'),
    path('upload/', views.upload_file, name='upload'),
    path('view-reports/', views.view_reports, name='view_reports'),
    path('util-leakage/', views.util_leakage, name='util_leakage'),
    path('update-comments/', views.update_comments, name='update_comments'),
]