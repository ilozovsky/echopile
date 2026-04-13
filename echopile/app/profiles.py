"""Small runtime profile differences for local and hosted app launches."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AppProfile:
    name: str
    upload_file_mb: int | None = None
    upload_total_mb: int | None = None


LOCAL_PROFILE = AppProfile(name="local")
WEB_PROFILE = AppProfile(name="web")


def resolve_profile(profile: str | AppProfile | None) -> AppProfile:
    if isinstance(profile, AppProfile):
        return profile
    if profile in (None, "", "local"):
        return LOCAL_PROFILE
    if profile == "web":
        return WEB_PROFILE
    raise ValueError(f"Unknown app profile: {profile}")
