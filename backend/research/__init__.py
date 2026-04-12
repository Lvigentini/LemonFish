"""
Research-from-prompt add-on module.

This module is opt-in. The main app conditionally imports and registers it
at startup based on the RESEARCH_ENABLED env var. When disabled or absent,
no /api/research/* routes are registered and the main app is unaffected.

Public surface:
    - is_enabled() -> bool        : check whether the module should be active
    - register_blueprint(app)     : mount the Flask blueprint on a Flask app

See docs/implementation_plan.md Phase 8 and docs/new_features_planning.md
for the full design.
"""

from .config import is_enabled


def register_blueprint(app):
    """Register the research blueprint on the given Flask app.

    Imports the blueprint lazily so that the main app does not pay the import
    cost (and does not require optional dependencies like duckduckgo-search)
    when the module is disabled.
    """
    from .api import research_bp
    app.register_blueprint(research_bp, url_prefix='/api/research')


__all__ = ['is_enabled', 'register_blueprint']
