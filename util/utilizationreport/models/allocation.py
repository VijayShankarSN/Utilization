from django.db import models
from .project import Project
from .resource import Resource
from .requirement import Requirement
from .choices import BILLING_CHOICES, ALLOCATION_STATUS_CHOICES

class Allocation(models.Model):
    resource = models.ForeignKey(Resource, on_delete=models.CASCADE)
    requirement = models.ForeignKey(Requirement, on_delete=models.CASCADE)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    billing_type = models.CharField(max_length=20, choices=BILLING_CHOICES)
    allocation_status = models.CharField(max_length=20, choices=ALLOCATION_STATUS_CHOICES)

    def save(self, *args, **kwargs):
        # Ensure allocation_status matches billing_type
        if self.billing_type == 'Full-Time':
            self.allocation_status = 'On Project-Full Time'
        elif self.billing_type == 'Part-Time':
            self.allocation_status = 'On Project-Part Time'
        
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.resource.resource_name} - {self.project.project_name}"

