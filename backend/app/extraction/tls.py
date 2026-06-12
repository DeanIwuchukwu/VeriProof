"""Shared TLS helpers for vision providers."""

from __future__ import annotations

_TRUST_STORE_READY = False


def use_system_trust_store() -> None:
    """Trust the OS certificate store for TLS."""
    global _TRUST_STORE_READY
    if _TRUST_STORE_READY:
        return
    try:
        import truststore

        truststore.inject_into_ssl()
    except Exception:  # noqa: BLE001
        pass
    _TRUST_STORE_READY = True
