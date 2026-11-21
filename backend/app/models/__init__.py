"""Importing this package registers every table with the metadata (used by Alembic)."""
from app.models import (  # noqa: F401
    access, activity, business, identity, ingredients, menus, nutrition, ontology, profile, recipes,
)
