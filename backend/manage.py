#!/usr/bin/env python
import os
import sys

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    if len(sys.argv) > 1 and sys.argv[1] == "runserver":
        has_address = any(not arg.startswith("-") for arg in sys.argv[2:])
        if not has_address:
            sys.argv.append(os.getenv("DJANGO_RUNSERVER_ADDRESS", "127.0.0.1:8001"))
    from django.core.management import execute_from_command_line
    execute_from_command_line(sys.argv)
