"""Per-country configuration: everything that differs between Spain and France."""

import importlib


def get(cc):
    return importlib.import_module(f"countries.{cc}")
