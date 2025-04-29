from django.db import models


class ResourceDetailsFetch(models.Model):
    row_labels = models.CharField(max_length=255)  # For email addresses
    rdm = models.CharField(max_length=255)  # For RDM field
    track = models.CharField(max_length=255)  # For Track field
    billing = models.CharField(max_length=255)  # For Billing field

    def __str__(self):
        return self.row_labels

    class Meta:
        managed = False
        db_table = 'report_req'  # Map to existing table name

