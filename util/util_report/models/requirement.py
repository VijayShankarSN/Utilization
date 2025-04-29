from django.db import models
from .project import Project
from .choices import PRODUCT_CHOICES, ROLE_CHOICES, BILLING_CHOICES, REQUIREMENT_TYPE_CHOICES

class Requirement(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    product = models.CharField(max_length=50, choices=PRODUCT_CHOICES)
    miscellaneous_skills_required = models.CharField(max_length=50, null=True, blank=True)
    role_required = models.CharField(max_length=20, choices=ROLE_CHOICES)
    level_required = models.IntegerField() # range 2-7
    number_required = models.IntegerField()
    start_date = models.DateField()  # Changed to DateField to store full date
    end_date = models.DateField()    # Changed to DateField to store full date
    billing_type = models.CharField(max_length=20, choices=BILLING_CHOICES)
    fulfilled_quantity = models.IntegerField(default=0)
    requirement_type = models.CharField(max_length=20, choices=REQUIREMENT_TYPE_CHOICES, default="New")
    
    @property
    def is_fulfilled(self):
        """Check if the requirement has been fully fulfilled."""
        return self.fulfilled_quantity >= self.number_required

    def __str__(self):
        return f"{self.product} - {self.role_required} for {self.project.project_name}" 