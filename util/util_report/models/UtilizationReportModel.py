from django.db import models


class UtilizationReportModel(models.Model):
    resource_email_address = models.CharField(max_length=255)
    administrative = models.FloatField(default=0)
    billable_hours = models.FloatField(default=0)
    department_mgmt = models.FloatField(default=0)
    investment = models.FloatField(default=0)
    presales = models.FloatField(default=0)
    training = models.FloatField(default=0)
    unassigned = models.FloatField(default=0)
    vacation = models.FloatField(default=0)
    grand_total = models.FloatField(default=0)
    last_week = models.FloatField(default=0)
    status = models.CharField(max_length=100, default='open')
    total_logged = models.FloatField(default=0)
    addtnl_days = models.FloatField(default=0)
    wtd_actuals = models.FloatField(default=0)
    spoc = models.CharField(max_length=255, null=True, blank=True)
    comments = models.TextField(null=True, blank=True)
    spoc_comments = models.TextField(null=True, blank=True)
    rdm = models.CharField(max_length=255, null=True, blank=True)
    track = models.CharField(max_length=255, null=True, blank=True)
    billing = models.CharField(max_length=255, null=True, blank=True)
    date = models.DateField()
    dams_utilization = models.FloatField(default=0)
    capable_utilization = models.FloatField(default=0)
    individual_utilization = models.FloatField(default=0)
    total_capacity = models.FloatField(default=0)


    def __str__(self):
        return f"{self.resource_email_address} - {self.date}"

    class Meta:
        managed = True
        db_table = 'utilization_report'
        unique_together = ('resource_email_address', 'date')
