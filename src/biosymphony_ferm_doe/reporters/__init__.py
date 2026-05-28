"""Single-file HTML reporters for engine artifacts.

Reporters consume the JSON artifacts that adapters emit (e.g.
``bofire_strategy_report.json``) and produce self-contained HTML for
handoff packets, public demos, and dossier inclusion. Reporters do not
introduce new runtime dependencies on the base engine; each module uses
the stdlib by default and can soft-import richer renderers later.
"""

from . import bofire_html

__all__ = ["bofire_html"]
