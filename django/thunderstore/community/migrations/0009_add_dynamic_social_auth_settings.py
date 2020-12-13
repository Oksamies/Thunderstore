# Generated by Django 3.1.4 on 2020-12-13 21:29

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('community', '0008_add_dynamic_site_meta'),
    ]

    operations = [
        migrations.AddField(
            model_name='communitysite',
            name='social_auth_discord_key',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='communitysite',
            name='social_auth_discord_secret',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='communitysite',
            name='social_auth_github_key',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='communitysite',
            name='social_auth_github_secret',
            field=models.TextField(blank=True, null=True),
        ),
    ]