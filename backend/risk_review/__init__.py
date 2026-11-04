"""Risk review: agent-based codebase review for the AI Governance Intake repository.

Layout follows the agent playbook reference architecture (agents with a spec, factory,
instructions, private skills and tools; shared tools; deterministic workflow; durable
steps; observability; policy). Everything here is a developer tool: it is not part of the
``app`` package or the production image.
"""

from __future__ import annotations

PACKAGE_VERSION = "0.1.0"
CONTRACT_VERSION = 1
