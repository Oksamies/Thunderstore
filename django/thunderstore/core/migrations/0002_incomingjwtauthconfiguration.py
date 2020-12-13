# Generated by Django 2.2.6 on 2019-11-14 18:39

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='IncomingJWTAuthConfiguration',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=128)),
                ('secret', models.TextField()),
                ('secret_type', models.CharField(choices=[('hs256', 'HS256'), ('rs256', 'RS256')], max_length=16)),
                ('key_id', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Incoming JWT Auth Configuration',
                'verbose_name_plural': 'Incoming JWT Auth Configurations',
            },
        ),
    ]