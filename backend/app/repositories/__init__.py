"""Repository layer for domain-level data access.

Each domain has its own repository module handling direct SQLAlchemy queries.
Services call repositories instead of writing raw queries.
"""
