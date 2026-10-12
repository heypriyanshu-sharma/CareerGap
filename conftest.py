"""Pytest configuration for CareerGap tests.

Sets dummy Supabase credentials before any test modules are imported
to avoid RuntimeError from auth.py module-level check.
"""
import os

# Set dummy Supabase credentials BEFORE any test modules import auth
# This prevents RuntimeError from auth.py module-level check
os.environ.setdefault("SUPABASE_URL", "https://dummy.supabase.co")
os.environ.setdefault("SUPABASE_PUBLISHABLE_KEY", "dummy-key")

# Now safe to import test modules that depend on auth