# -*- coding: utf-8 -*-
# Generated by Django 1.11 on 2018-03-18 18:08
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('profiles', '0017_auto_20180213_1202'),
        ('entries', '0021_auto_20180306_1045'),
        ('creators', '0011_auto_20171025_1917'),
    ]

    operations = [
        migrations.CreateModel(
            name='EntryCreator',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('entry', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='related_entry_creators', to='entries.Entry')),
                ('profile', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='related_entry_creators', to='profiles.UserProfile')),
            ],
            options={
                'verbose_name': 'Entry Creators',
            },
        ),
        migrations.AlterOrderWithRespectTo(
            name='entrycreator',
            order_with_respect_to='entry',
        ),
    ]
