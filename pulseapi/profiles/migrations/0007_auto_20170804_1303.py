# -*- coding: utf-8 -*-
# Generated by Django 1.10.3 on 2017-08-04 20:03
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('entries', '0013_entry_help_types'),
        ('profiles', '0006_cleanup_due_to_bookmark_rebind_in_users_emailuser'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='userbookmarks',
            name='user',
        ),
        migrations.AddField(
            model_name='userprofile',
            name='bookmarks',
            field=models.ManyToManyField(through='profiles.UserBookmarks', to='entries.Entry'),
        ),
        migrations.AlterField(
            model_name='userbookmarks',
            name='entry',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='bookmarked_by', to='entries.Entry'),
        ),
        migrations.AlterField(
            model_name='userbookmarks',
            name='profile',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='bookmarks_from', to='profiles.UserProfile'),
        ),
    ]