from django.db import models

# Create your models here.
class Evolution(models.Model):
    app_name = models.CharField(maxlength=200)
    version = models.PositiveIntegerField()
    signature = models.TextField()
  
    def __str__(self):
        return '%s Version %d' % (self.app_name,self.version)
