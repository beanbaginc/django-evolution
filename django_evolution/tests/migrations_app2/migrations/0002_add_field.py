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
            ('migrations_app2', '0001_initial'),
        ]

        operations = [
            migrations.AddField(
                model_name='MigrationsApp2TestModel',
                name='added_field',
                field=models.BooleanField(default=False)),
        ]
