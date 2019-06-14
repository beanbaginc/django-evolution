from __future__ import unicode_literals

import json
from datetime import datetime

from django.test.testcases import TestCase

from django_evolution.models import Version
from django_evolution.signature import AppSignature, ProjectSignature


class VersionManagerTests(TestCase):
    """Unit tests for django_evolution.models.VersionManager."""

    def test_current_version_with_dup_timestamps(self):
        """Testing Version.current_version() with two entries with same
        timestamps
        """
        # Remove anything that may already exist.
        Version.objects.all().delete()

        timestamp = datetime(year=2015, month=12, day=10, hour=12, minute=13,
                             second=14)

        Version.objects.create(signature=ProjectSignature(),
                               when=timestamp)
        version = Version.objects.create(signature=ProjectSignature(),
                                         when=timestamp)

        latest_version = Version.objects.current_version()
        self.assertEqual(latest_version, version)


class VersionTests(TestCase):
    """Unit tests for django_evolution.models.Version."""

    def setUp(self):
        super(VersionTests, self).setUp()

        # Remove anything that may already exist.
        Version.objects.all().delete()

    def test_signature_load_v1(self):
        """Testing Version.signature field loaded from a pickle-serialized
        v1 signature
        """
        Version.objects.create(
            signature="(dp0\nS'__version__'\np1\nI1\nsS'app2'\np2\n(dp3\n"
                      "sS'app1'\np4\n(dp5\ns.")

        version = Version.objects.get()
        project_sig = version.signature
        self.assertIsInstance(project_sig, ProjectSignature)

        self.assertIsNotNone(project_sig.get_app_sig('app1'))
        self.assertIsNotNone(project_sig.get_app_sig('app2'))

    def test_signature_load_v2(self):
        """Testing Version.signature field loaded from a JSON-serialized
        v2 signature
        """
        Version.objects.create(
            signature='json!{"__version__": 2,'
                      '"apps": {'
                      '"app1": {"legacy_app_label": "app1", "models": {}}, '
                      '"app2": {"legacy_app_label": "app2", "models": {}}}}')

        version = Version.objects.get()
        project_sig = version.signature
        self.assertIsInstance(project_sig, ProjectSignature)

        self.assertIsNotNone(project_sig.get_app_sig('app1'))
        self.assertIsNotNone(project_sig.get_app_sig('app2'))

    def test_signature_save(self):
        """Testing Version.signature field serializes JSON-encoded v2
        signatures
        """
        project_sig = ProjectSignature()
        project_sig.add_app_sig(AppSignature('app1'))
        project_sig.add_app_sig(AppSignature('app2'))

        version = Version.objects.create(signature=project_sig)

        raw_signature = (
            Version.objects
            .filter(pk=version.pk)
            .values_list('signature')
        )[0][0]

        self.assertTrue(raw_signature.startswith('json!'))
        sig_data = json.loads(raw_signature[len('json!'):])

        self.assertEqual(
            sig_data,
            {
                '__version__': 2,
                'apps': {
                    'app1': {
                        'legacy_app_label': 'app1',
                        'models': {},
                    },
                    'app2': {
                        'legacy_app_label': 'app2',
                        'models': {},
                    },
                },
            })
