from django.db import models

# Create your models here.
class Evolution(models.Model):
  version = models.PositiveIntegerField(core=True)
  signature = models.TextField(core=True)
  app_name = models.CharField(maxlength=200)
  
  def __str__(self):
      return '%s Version %d'%(self.app_name,self.version)
