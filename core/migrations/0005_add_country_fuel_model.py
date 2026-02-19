# Generated manually 2026-02-19

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_add_fuel_model'),
    ]

    operations = [
        migrations.CreateModel(
            name='CountryFuel',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('country', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='country_fuels',
                    to='core.country',
                )),
                ('fuel', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='country_fuels',
                    to='core.fuel',
                )),
                ('share', models.FloatField(
                    help_text="Percentage of this country's electricity supplied by this fuel over the most recent 12 months",
                )),
                ('latest_month', models.DateField(
                    help_text='The latest date for which generation data is available (always the first day of the month)',
                )),
                ('generation_latest_12_months', models.FloatField(
                    help_text='Sum of electricity generation in the most recent 12 months (TWh)',
                )),
                ('generation_previous_12_months', models.FloatField(
                    help_text='Sum of electricity generation from 24-13 months ago (TWh)',
                )),
            ],
            options={
                'unique_together': {('country', 'fuel')},
            },
        ),
    ]
