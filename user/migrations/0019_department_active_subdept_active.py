# Generated by Django 5.0.6 on 2024-09-21 12:41

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('user', '0018_staffprofile_department'),
    ]

    operations = [
        migrations.AddField(
            model_name='department',
            name='active',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='subdept',
            name='active',
            field=models.BooleanField(default=True),
        ),
    ]
