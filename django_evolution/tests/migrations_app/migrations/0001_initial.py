from __future__ import unicode_literals

try:
    # Django >= 1.7
    from django.db import migrations, models
except ImportError:
    # Django < 1.7
    migrations = None


if migrations:
    class Migration(migrations.Migration):
        operations = [
            migrations.CreateModel(
                name='MigrationsAppTestModel',
                fields=[
                    ('id', models.AutoField(verbose_name='ID',
                                            serialize=False,
                                            auto_created=True,
                                            primary_key=True)),
                    ('char_field', models.CharField(max_length=10)),
                ],
                options={
                    'db_table': 'migrations_app_migrationsapptestmodel',
                },
                bases=(models.Model,)),
        ]
