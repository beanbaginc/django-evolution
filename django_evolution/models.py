from django.db import models

# Create your models here.
class Evolution(models.Model):
    app_name = models.CharField(maxlength=200)
    version = models.PositiveIntegerField()
    signature = models.TextField()
    
    class Meta:
        ordering = ('version',)
        db_table = 'django_evolution'

    def __unicode__(self):
        return u'%s Version %d, applied %s' % (self.app_name,self.version,self.date)
