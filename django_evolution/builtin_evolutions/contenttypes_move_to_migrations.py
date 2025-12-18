"""Marks django.contrib.contenttypes as managed by Django migrations."""

from __future__ import annotations

from django_evolution.mutations import MoveToDjangoMigrations


MUTATIONS = [
    MoveToDjangoMigrations(),
]
