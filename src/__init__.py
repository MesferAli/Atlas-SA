"""Atlas Sovereign Oversight PoC — top-level package.

This package contains the Python implementation of the Atlas middleware
PoC: the rules engine, the intent monitor, the trust dashboard API, and
the interactive CLI demo. It is deliberately independent from the
``provisioning`` package — ``provisioning`` deploys the production Atlas
stack onto OCI, while ``src`` demonstrates the sovereignty / oversight
behaviour on a developer laptop without needing a live Fusion tenancy.
"""

__all__ = ["rules_engine", "dashboard", "demo"]
__version__ = "0.1.0-poc"
