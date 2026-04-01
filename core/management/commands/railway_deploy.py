"""
Management command: railway_deploy

Thin wrapper intended to run on every deployment in Railway.

Runs the minimal commands required to prepare the application for running in production.
"""

from __future__ import annotations

from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Run deployment hooks for Railway."

    def handle(self, *args, **options):
        self.stdout.write("Running collectstatic...")
        call_command("collectstatic", "--noinput")

        self.stdout.write(self.style.SUCCESS("Railway deployment complete."))

