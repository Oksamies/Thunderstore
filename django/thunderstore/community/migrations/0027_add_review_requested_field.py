# Generated by Django 3.1.7 on 2024-01-09 12:30

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("community", "0026_schedule_aggregated_fields_refresh"),
    ]

    operations = [
        migrations.AddField(
            model_name="packagelisting",
            name="is_review_requested",
            field=models.BooleanField(default=False),
        ),
    ]
