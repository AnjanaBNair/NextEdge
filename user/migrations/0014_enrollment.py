# Generated by Django 5.0.6 on 2024-09-06 08:03

import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('user', '0013_staffcourse_type'),
    ]

    operations = [
        migrations.CreateModel(
            name='Enrollment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('added', models.DateTimeField(default=django.utils.timezone.now)),
                ('attempts', models.IntegerField(default=0)),
                ('latest_score', models.IntegerField(default=0)),
                ('status', models.BooleanField(default=True)),
                ('course', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='enrolled_course', to='user.staffcourse')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='enrolled_student', to='user.staffcourse')),
            ],
        ),
    ]