# Generated by Django 3.1.7 on 2023-01-08 09:26

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("community", "0021_remove_unused_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="community",
            name="block_auto_updates",
            field=models.BooleanField(default=True),
        ),
    ]