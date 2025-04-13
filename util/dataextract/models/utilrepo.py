from django.db import models
from ..models import project,allocation,resource

class UtilizationReport(models.Model):
    name = models.CharField(max_length=255)
    administrative = models.FloatField()
    billable_days = models.FloatField()
    training = models.FloatField()
    unassigned = models.FloatField()
    vacation = models.FloatField()
    grand_total = models.FloatField()
    last_week = models.FloatField()
    status = models.CharField(max_length=100)
    addtnl_days = models.FloatField()
    wtd_actual = models.FloatField()
    spoc = models.CharField(max_length=255)
    comments = models.TextField(blank=True, null=True)
    spoc_comments = models.TextField(blank=True, null=True)
    rdm = models.CharField(max_length=255)
    track = models.CharField(max_length=255)
    billing = models.CharField(max_length=500)
    date = models.DateField(null=True, blank=True)
    
    def __str__(self):
        return self.name