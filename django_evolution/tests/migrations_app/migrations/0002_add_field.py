from __future__ import unicode_literals

try:
    # Django >= 1.7
    from django.db import migrations, models
except ImportError:
    # Django < 1.7
    migrations = None


if migrations:
    class Migration(migrations.Migration):
        dependencies = [
            ('migrations_app', '0001_initial'),
        ]

        operations = [
            migrations.AddField(
                model_name='MigrationsAppTestModel',
                name='added_field',
                field=models.IntegerField(default=42)),
        ]
