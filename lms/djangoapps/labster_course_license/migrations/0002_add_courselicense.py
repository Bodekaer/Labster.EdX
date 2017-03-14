# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import xmodule_django.models


class Migration(migrations.Migration):

    dependencies = [
        ('labster_course_license', '0001_fix_ccx_overrides'),
    ]

    operations = [
        migrations.CreateModel(
            name='CourseLicense',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('course_id', xmodule_django.models.CourseKeyField(max_length=255, db_index=True)),
                ('license_code', models.CharField(max_length=255, db_index=True)),
            ],
        ),
    ]
