from django.urls import path, include
from . import views
from django.views.generic import RedirectView

urlpatterns = [
    # Redirect root path to view_reports
    path('', RedirectView.as_view(pattern_name='view_reports', permanent=False), name='index'),
    path('extract/', views.extract_data_view, name='extract_data'),
    path('view-reports/', views.view_reports, name='view_reports'),
    path('util-leakage/', views.util_leakage, name='util_leakage'),
    path('util-summary/', views.util_summary, name='util_summary'),
    path('update-comments/', views.update_comments, name='update_comments'),
    path('update-billable-hours/', views.update_billable_hours, name='update_billable_hours'),
    path('update-additional-days/', views.update_additional_days, name='update_additional_days'),
    path('download-report/', views.download_report, name='download_report'),
    path('download-result/', views.download_result, name='download_result'),
    path('download-util-leakage/', views.download_util_leakage, name='download_util_leakage'),
    path('close-cases/', views.close_cases, name='close_cases'),
    path('extract-date/<str:extraction_date>/', views.date_extraction, name='date_extraction'),
    path('extract-date/', views.date_extraction, name='date_extraction_form'),
    path('get-history-data/', views.get_history_data, name='get_history_data'),
    path('get-utilization-data/', views.get_utilization_data, name='get_utilization_data'),
    path('get-low-utilization-resources/', views.get_low_utilization_resources, name='get_low_utilization_resources'),
    path('get_rdm_summary/', views.get_rdm_summary, name='get_rdm_summary'),
    path('download-rdm-summary/', views.download_rdm_summary_excel, name='download_rdm_summary_excel'),
    # path('', views.upload_file, name='upload'), # Commented out - replaced by modal
]