from django.db import models
from django.utils import timezone

class UtilizationHistoryModel(models.Model):
    """Model for tracking utilization history changes."""
    ACTIONS = (
        ('closed', 'Case Closed'),
        ('edited', 'Field Edited'),
        ('updated', 'Record Updated'),
    )
    
    date = models.DateField(default=timezone.now)
    timestamp = models.DateTimeField(auto_now_add=True)
    resource_email = models.CharField(max_length=255)
    action = models.CharField(max_length=20, choices=ACTIONS)
    details = models.CharField(max_length=255)
    field_name = models.CharField(max_length=100, null=True, blank=True)
    previous_value = models.TextField(null=True, blank=True)
    new_value = models.TextField(null=True, blank=True)
    report_date = models.DateField()  # The date of the report that was modified
    user = models.CharField(max_length=255, null=True, blank=True)  # User who made the change, if available
    
    class Meta:
        db_table = 'utilization_history'
        ordering = ['-timestamp']
        
    def __str__(self):
        return f"{self.resource_email} - {self.action} - {self.timestamp}" 