# Generated by Django 5.0.6 on 2024-07-11 14:18

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('user', '0003_rename_passwordresettoken_passwordreset'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='passwordreset',
            name='expiry',
        ),
    ]
