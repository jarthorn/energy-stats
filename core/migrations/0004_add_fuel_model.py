# Generated manually 2026-02-19

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0003_add_country_model'),
    ]

    operations = [
        migrations.CreateModel(
            name='Fuel',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('type', models.CharField(
                    help_text='A unique string representing a particular type of fuel',
                    max_length=100,
                    unique=True,
                )),
                ('rank', models.IntegerField(
                    help_text="This fuel type's rank in total generation across all countries",
                )),
                ('summary', models.TextField(
                    help_text='A paragraph describing this fuel type',
                )),
            ],
            options={
                'ordering': ['rank'],
            },
        ),
    ]
