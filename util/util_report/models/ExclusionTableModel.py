from django.db import models


class ExclusionTableModel(models.Model):
    exclusion_list = models.CharField(max_length=255)  # For email addresses
    
    def __str__(self):
        return self.exclusion_list

    class Meta:
        managed = False
        db_table = 'exclusion_table'  # Map to existing table name
