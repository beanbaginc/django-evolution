from django.db import models

# Create your models here.
class Evolution(models.Model):
    app_name = models.CharField(maxlength=200)
    version = models.PositiveIntegerField(null=True, blank=True)
    signature = models.TextField()
    when = models.DateTimeField(auto_now=True)

    class Admin:
        pass
        
    class Meta:
        ordering = ('when',)
        db_table = 'django_evolution'

    def __unicode__(self):
        if self.version is None:
            return u'Temporary %s version, applied %s' % (self.app_name,self.when)
        else:
            return u'%s Version %d, applied %s' % (self.app_name,self.version,self.when)
