from django.db import models

# Create your models here.
class Evolution(models.Model):
    version = models.PositiveIntegerField(null=True, blank=True)
    signature = models.TextField()
    when = models.DateTimeField(auto_now=True)

    class Admin:
        pass
        
    class Meta:
        ordering = ('-when',)
        db_table = 'django_evolution'

    def __unicode__(self):
        if self.version is None:
            return u'Temporary version, applied %s' % self.when
        else:
            return u'Version %d, applied %s' % (self.version,self.when)
