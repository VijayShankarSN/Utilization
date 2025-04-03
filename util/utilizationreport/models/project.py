from django.db import models
from django.db.models.signals import pre_save
from django.dispatch import receiver
from .choices import REGION_CHOICES, CLUSTER_CHOICES, PROJECT_STATUS_CHOICES, INDUSTRY_CHOICES
import logging

# Configure logging
logger = logging.getLogger(__name__)

class Project(models.Model):
    project_name = models.CharField(max_length=50, unique=True)
    fcrm_id = models.CharField(max_length=20, unique=True, blank=True, null=True)
    industry = models.CharField(max_length=25, blank=True, null=True, choices=INDUSTRY_CHOICES)
    start_date = models.CharField(max_length=7)  # Format: YYYY-MM
    end_date = models.CharField(max_length=7)    # Format: YYYY-MM
    region = models.CharField(max_length=50, choices=REGION_CHOICES)
    cluster = models.CharField(max_length=50, choices=CLUSTER_CHOICES)
    rdm = models.CharField(max_length=50)
    priority= models.CharField(max_length=2, choices=(("P1","P1"),("P2","P2"),("P3","P3")), default="P1")
    status = models.CharField(max_length=50, choices=PROJECT_STATUS_CHOICES, default="Yet to Start")
    ownership = models.CharField(max_length=50, choices=(("OC", "OC Owner"), ("GSC", "GSC Owned")), default="GSC")

    def __str__(self):
        return self.project_name

@receiver(pre_save, sender=Project)
def handle_project_status_change(sender, instance, **kwargs):
    """
    Signal handler to release all resources when a project is manually set to Closed or Dropped
    
    NOTE: This signal handler is now DISABLED because the cleanup is handled directly in the views
    to ensure proper transaction management and to avoid race conditions.
    """
    # Skip processing - we now handle this directly in the views
    return
    
    print(f"[DEBUG] Project pre_save signal triggered for project ID: {instance.id}, Name: {instance.project_name}")
    try:
        # Check if this is an existing project (not a new one)
        if instance.pk:
            # Get the old instance from the database
            old_instance = Project.objects.get(pk=instance.pk)
            
            print(f"[DEBUG] Project status change: {old_instance.status} -> {instance.status}")
            
            # Check if status is changing to Closed or Dropped
            if (instance.status in ['Closed', 'Dropped'] and 
                old_instance.status not in ['Closed', 'Dropped']):
                
                print(f"[DEBUG] Project status changing to {instance.status}. Will release resources and remove requirements.")
                
                # This import is here to avoid circular imports
                from ..services.project import ProjectService
                
                # Use the project service to release all resources
                reason = f"Project {instance.status}"
                released_count, removed_count, error = ProjectService.release_all_project_resources(
                    project=instance,
                    reason=reason
                )
                
                if error:
                    print(f"Warning: Error cleaning up project {instance.id}: {error}")
                elif released_count > 0 or removed_count > 0:
                    print(f"Project cleanup: Released {released_count} resources and removed {removed_count} requirements from {reason.lower()} '{instance.project_name}'")
                else:
                    print(f"[DEBUG] No resources or requirements needed cleanup for project '{instance.project_name}'")
            else:
                print(f"[DEBUG] No resource cleanup needed for project status change from {old_instance.status} to {instance.status}")
    
    except Exception as e:
        # Log the exception but don't stop the save
        error_msg = f"Error in project status change signal: {str(e)}"
        print(error_msg)
        logger.error(error_msg)
        # We don't re-raise the exception to allow the save to continue 