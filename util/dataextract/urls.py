from django.urls import path
from . import views

urlpatterns = [
    path('extract/', views.extract_data_view, name='extract_data'),
    path('', views.home_view, name='home'),
    path('upload/', views.upload_file, name='upload'),
    path('view-reports/', views.view_reports, name='view_reports'),
    path('util-leakage/', views.util_leakage, name='util_leakage'),
    path('update-comments/', views.update_comments, name='update_comments'),
    path('download-report/', views.download_report, name='download_report'),
    path('download-result/', views.download_result, name='download_result'),
    path('download-util-leakage/', views.download_util_leakage, name='download_util_leakage'),
]