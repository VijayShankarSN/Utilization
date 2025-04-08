from django.db import models
from .choices import (
    PRODUCT_CHOICES, ROLE_CHOICES, CLUSTER_CHOICES,
    RESOURCE_STATUS_CHOICES, ALLOCATION_STATUS_CHOICES, INDUSTRY_CHOICES
)
from datetime import date, datetime

class Resource(models.Model):
    resource_id = models.CharField(max_length=10, unique=True)
    resource_name = models.CharField(max_length=50)
    resource_email = models.EmailField(max_length=50, unique=True)

    # Skills
    resource_primary_skill_1 = models.CharField(max_length=50, choices=PRODUCT_CHOICES)
    resource_primary_skill_1_level = models.IntegerField()  #1-3
    resource_primary_skill_2 = models.CharField(max_length=50, choices=PRODUCT_CHOICES, null=True, blank=True)
    resource_primary_skill_2_level = models.IntegerField(null=True, blank=True)  #1-3
    resource_secondary_skill_1 = models.CharField(max_length=50, choices=PRODUCT_CHOICES, null=True, blank=True)
    resource_secondary_skill_1_level = models.IntegerField(null=True, blank=True)  #1-3
    resource_secondary_skill_2 = models.CharField(max_length=50, choices=PRODUCT_CHOICES, null=True, blank=True)
    resource_secondary_skill_2_level = models.IntegerField(null=True, blank=True)  #1-3
    resource_tertiary_skill_1 = models.CharField(max_length=50, choices=PRODUCT_CHOICES, null=True, blank=True)
    resource_tertiary_skill_1_level = models.IntegerField(null=True, blank=True)  #1-3
    resource_tertiary_skill_2 = models.CharField(max_length=50, choices=PRODUCT_CHOICES, null=True, blank=True)
    resource_tertiary_skill_2_level = models.IntegerField(null=True, blank=True)  #1-3
    resource_miscellaneous_skills = models.CharField(max_length=50, null=True, blank=True)

    # Role and Experience
    resource_role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    resource_level = models.IntegerField() #2-7
    resource_YOE = models.IntegerField()
    resource_EPM_exp = models.IntegerField()
    resource_location = models.CharField(max_length=50, choices=CLUSTER_CHOICES)
    resource_industry_1 = models.CharField(max_length=50, choices=INDUSTRY_CHOICES, null=True, blank=True)
    resource_industry_2 = models.CharField(max_length=50, choices=INDUSTRY_CHOICES, null=True, blank=True)
    resource_industry_3 = models.CharField(max_length=50, choices=INDUSTRY_CHOICES, null=True, blank=True)


    # Dates
    resource_DOJ = models.CharField(max_length=10)  # Format: YYYY-MM-DD
    resource_exit_date = models.CharField(max_length=10, blank=True, null=True)  # Format: YYYY-MM-DD
    resource_onleave_start_date = models.CharField(max_length=10, blank=True, null=True)  # Format: YYYY-MM-DD
    resource_onleave_end_date = models.CharField(max_length=10, blank=True, null=True)  # Format: YYYY-MM-DD

    # Status
    resource_isbillable = models.CharField(max_length=20, choices=[('Yes', 'Yes'), ('No', 'No')], default='Yes')
    resource_status = models.CharField(max_length=20, choices=RESOURCE_STATUS_CHOICES, default="To-join")
    resource_availability = models.CharField(max_length=20, choices=ALLOCATION_STATUS_CHOICES, default="Available", null=True, blank=True)

    def __str__(self):
        return self.resource_name
        
    def save(self, *args, **kwargs):
        # If resource is marked as inactive, set availability to null
        if self.resource_status == 'Inactive':
            self.resource_availability = None
        
        # Check DOJ against current date to set appropriate status
        try:
            today = date.today()
            doj_date = datetime.strptime(self.resource_DOJ, '%Y-%m-%d').date()
            
            # Auto-set status based on DOJ if not being explicitly set to Inactive or On-leave
            if self.resource_status not in ['Inactive', 'On-leave']:
                if doj_date > today:
                    # Future DOJ should be To-join
                    self.resource_status = 'To-join'
                elif doj_date <= today:
                    # Current or past DOJ should be Active
                    self.resource_status = 'Active'
                    
                    # If transitioning from To-join to Active, set availability to On Bench
                    if not self.pk or Resource.objects.get(pk=self.pk).resource_status == 'To-join':
                        self.resource_availability = 'On Bench'
        except (ValueError, TypeError):
            # Handle invalid date format gracefully
            pass
            
        super().save(*args, **kwargs) 