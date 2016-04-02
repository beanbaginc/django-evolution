from datetime import datetime

from django.test.testcases import TestCase

from django_evolution.models import Version


class VersionManagerTests(TestCase):
    """Unit tests for django_evolution.models.VersionManager."""

    def test_current_version_with_dup_timestamps(self):
        """Testing Version.current_version() with two entries with same timestamps"""
        # Remove anything that may already exist.
        Version.objects.all().delete()

        timestamp = datetime(year=2015, month=12, day=10, hour=12, minute=13,
                             second=14)

        Version.objects.create(signature='abc123', when=timestamp)
        version = Version.objects.create(signature='abc123-def456',
                                         when=timestamp)

        latest_version = Version.objects.current_version()
        self.assertEqual(latest_version, version)
