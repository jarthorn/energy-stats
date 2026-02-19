# Generated manually 2026-02-19

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_alter_monthlygenerationdata_country_code'),
    ]

    operations = [
        migrations.CreateModel(
            name='Country',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('code', models.CharField(
                    help_text='3-letter ISO country code',
                    max_length=3,
                    unique=True,
                )),
                ('summary', models.TextField(
                    help_text='A short paragraph summarizing the electricity generation for this country',
                )),
                ('electricity_rank', models.IntegerField(
                    help_text="The country's rank as an electricity producer",
                )),
                ('generation_latest_12_months', models.FloatField(
                    help_text='Sum of electricity generation in the most recent 12 months (TWh)',
                )),
                ('generation_previous_12_months', models.FloatField(
                    help_text='Sum of electricity generation from 24-13 months ago (TWh)',
                )),
            ],
            options={
                'verbose_name_plural': 'countries',
                'ordering': ['electricity_rank'],
            },
        ),
    ]
