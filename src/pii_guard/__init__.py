# Copyright (c) 2026 Thomas Körting / b-imtec GmbH
# Lizenz: MIT – siehe LICENSE
"""PII Guard – Lokaler Datenschutz-Filter für KI-Coding-Tools."""

import logging

__version__ = "0.3.0"

# Standard-Logging auf stderr (stdout ist für Hook-JSON reserviert).
# NullHandler als Default – wird nur aktiv wenn der Aufrufer konfiguriert.
logging.getLogger("pii_guard").addHandler(logging.NullHandler())
