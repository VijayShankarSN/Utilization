from django.db import models
class rdmname(models.Model):
    rdm_name = models.CharField(max_length=255)  # For email addresses

    def __str__(self):
        return self.row_labels        
           