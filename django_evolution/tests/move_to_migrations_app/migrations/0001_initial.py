from __future__ import annotations

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
                name='MoveToMigrationsAppTestModel',
                fields=[
                    ('id', models.AutoField(verbose_name='ID',
                                            serialize=False,
                                            auto_created=True,
                                            primary_key=True)),
                    ('char_field', models.CharField(max_length=10)),
                    ('added_field', models.BooleanField(default=False)),
                ],
                options={
                    'db_table': 'move_to_migrations_app_movetomigrationsapptestmodel',
                },
                bases=(models.Model,)),
        ]
