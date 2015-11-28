try:
    from django.utils.timezone import now
except ImportError:
    from datetime import datetime
    now = datetime.now

from django.db import models


class VersionManager(models.Manager):
    """Manage Version models.

    This introduces a convenience function for finding the current Version
    model for the database.
    """

    def current_version(self, using=None):
        """Return the Version model for the current schema.

        This will find the Version with both the latest timestamp and the
        latest ID. It's here as a replacement for the old call to
        :py:meth:`latest`, which only operated on the timestamp and would
        find the wrong entry if two had the same exact timestamp.

        Args:
            using (unicode):
                The database alias name to use for the query. Defaults
                to ``None``, the default database.

        Raises:
            Version.DoesNotExist: No such version exists.

        Returns:
            Version: The current Version object for the database.
        """
        versions = self.using(using).order_by('-when', '-id')

        try:
            return versions[0]
        except IndexError:
            raise self.model.DoesNotExist


class Version(models.Model):
    signature = models.TextField()
    when = models.DateTimeField(default=now)

    objects = VersionManager()

    def __unicode__(self):
        if not self.evolutions.count():
            return u'Hinted version, updated on %s' % self.when

        return u'Stored version, updated on %s' % self.when

    class Meta:
        ordering = ('-when',)
        db_table = 'django_project_version'


class Evolution(models.Model):
    version = models.ForeignKey(Version, related_name='evolutions')
    app_label = models.CharField(max_length=200)
    label = models.CharField(max_length=100)

    class Meta:
        db_table = 'django_evolution'

    def __unicode__(self):
        return u"Evolution %s, applied to %s" % (self.label, self.app_label)
