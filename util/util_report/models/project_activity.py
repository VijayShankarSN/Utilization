from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from .project import Project
from .requirement import Requirement
from .resource import Resource

class ProjectActivityLog(models.Model):
    """
    Model to track activities related to projects, requirements, and allocations.
    This provides a chronological log of events for each project.
    """
    ACTIVITY_TYPES = (
        ('requirement_added', 'Requirement Added'),
        ('requirement_updated', 'Requirement Updated'),
        ('requirement_removed', 'Requirement Removed'),
        ('resource_allocated', 'Resource Allocated'),
        ('resource_deallocated', 'Resource Deallocated'),
        ('project_created', 'Project Created'),
        ('project_updated', 'Project Updated'),
        ('project_status_changed', 'Project Status Changed'),
    )
    
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='activities')
    activity_type = models.CharField(max_length=30, choices=ACTIVITY_TYPES)
    description = models.TextField()
    timestamp = models.DateTimeField(default=timezone.now)
    
    # Optional related objects
    requirement = models.ForeignKey(Requirement, on_delete=models.SET_NULL, null=True, blank=True)
    resource = models.ForeignKey(Resource, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Track who performed the action if authenticated
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        ordering = ['-timestamp']
        
    def __str__(self):
        return f"{self.get_activity_type_display()} - {self.timestamp.strftime('%Y-%m-%d %H:%M')}" 