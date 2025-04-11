from django.contrib import admin

# Register your models here.
#hello
from .models import (
    UtilizationReport,
    Project,
    Requirement,
    Resource,
    Allocation,
    Deal,
    ProjectActivityLog,
    EmailTrack,
    rdmname,
)

# Register your models here
admin.site.register(UtilizationReport)
admin.site.register(Project)
admin.site.register(Requirement)
admin.site.register(Resource)
admin.site.register(Allocation)
admin.site.register(Deal)
admin.site.register(ProjectActivityLog)
admin.site.register(EmailTrack)
admin.site.register(rdmname)



