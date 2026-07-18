#!/usr/bin/env python
import os
import sys

from dotenv import load_dotenv

if __name__ == "__main__":
    # Load .env for local management commands (runserver, seed_demo, ...).
    # Does not override real env vars, so Docker (env_file) and CI are unaffected;
    # pytest does not go through manage.py, so tests stay deterministic.
    load_dotenv()
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)
