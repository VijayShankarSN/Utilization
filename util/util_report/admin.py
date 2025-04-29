from django.contrib import admin

# Register your models here.
#hello
from .models import (
    ResourceDetailsFetch,
    ExclusionTableModel,
    UtilizationReportModel,
)

# Register your models here
admin.site.register(ResourceDetailsFetch)
admin.site.register(ExclusionTableModel)
admin.site.register(UtilizationReportModel)



