from django.db import models
from .choices import REGION_CHOICES, CLUSTER_CHOICES, PROJECT_STATUS_CHOICES, INDUSTRY_CHOICES

class Deal(models.Model):
    deal_name = models.CharField(max_length=50, unique=True)
    industry = models.CharField(max_length=25, blank=True, null=True, choices=INDUSTRY_CHOICES)
    start_date = models.CharField(max_length=7)  # Format: YYYY-MM
    end_date = models.CharField(max_length=7)    # Format: YYYY-MM
    region = models.CharField(max_length=50, choices=REGION_CHOICES)
    cluster = models.CharField(max_length=50, choices=CLUSTER_CHOICES)
    rdm = models.CharField(max_length=50)
    priority = models.CharField(max_length=2, choices=(("P1","P1"),("P2","P2"),("P3","P3")), default="P1")
    #status = models.CharField(max_length=50, choices=PROJECT_STATUS_CHOICES, default="Active")
    ownership = models.CharField(max_length=50, choices=(("OC", "OC Owner"), ("GSC", "GSC Owned"),("TBD","TBD")), default="TBD",null=True, blank=True)

    def __str__(self):
        return self.deal_name 