from django.contrib import admin
from .models import (
    UtilizationReport,
    Project,
    Requirement,
    Resource,
    Allocation,
    Deal,
    ProjectActivityLog,
)

# Register your models here
admin.site.register(UtilizationReport)
admin.site.register(Project)
admin.site.register(Requirement)
admin.site.register(Resource)
admin.site.register(Allocation)
admin.site.register(Deal)
admin.site.register(ProjectActivityLog)