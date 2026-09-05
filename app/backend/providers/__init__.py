"""Data-provider selection with a safe file-backend fallback."""

from __future__ import annotations

import os

from .base import DataProvider
from .file_provider import FileProvider
from .manhattan_file_provider import ManhattanFileProvider
from .mumbai_file_provider import MumbaiFileProvider


def _file_provider(profile: str) -> DataProvider:
    if profile == "hyderabad":
        return FileProvider()
    if profile == "manhattan":
        return ManhattanFileProvider()
    if profile == "mumbai":
        return MumbaiFileProvider()
    raise ValueError(f"Unsupported DATA_PROFILE={profile!r}")


def create_provider(profile: str | None = None) -> DataProvider:
    requested = os.getenv("DATA_BACKEND", "file").strip().lower()
    requested_profile = (profile or os.getenv("DATA_PROFILE", "hyderabad")).strip().lower()
    if requested == "postgis":
        try:
            from .postgis_provider import PostGISProvider

            provider = PostGISProvider(profile_id=requested_profile)
            status = provider.health()
            if status.get("status") != "ok":
                raise RuntimeError(str(status.get("detail", "PostGIS health check failed")))
            return provider
        except Exception as exc:
            fallback = _file_provider(requested_profile)
            fallback.requested_backend = "postgis"
            fallback.fallback_reason = str(exc)
            return fallback

    provider = _file_provider(requested_profile)
    if requested not in {"", "file"}:
        provider.requested_backend = requested
        provider.fallback_reason = f"Unsupported DATA_BACKEND={requested!r}"
    return provider


__all__ = ["DataProvider", "FileProvider", "ManhattanFileProvider", "MumbaiFileProvider", "create_provider"]
