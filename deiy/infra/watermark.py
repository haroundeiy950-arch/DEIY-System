"""Dynamic anti-piracy watermarking (spec section 2D).

The watermark is not baked into the file server-side (that would multiply
storage); instead every playback/download session receives a short-lived signed
manifest with the student's name and academic ID.  The web player renders it as
a moving overlay, and the same token is validated by the media endpoint.
"""

from __future__ import annotations

from deiy.security import decode_token, sign_token
from deiy.utils import new_id, utcnow

class WatermarkService:
    def __init__(self, secret: str, ttl_seconds: int = 900) -> None:
        self.secret = secret
        self.ttl_seconds = ttl_seconds

    def issue(self, *, user: dict, resource: dict, kind: str = "view") -> dict:
        """Create a signed overlay manifest for one user/resource pair."""

        nonce = new_id()
        token = sign_token(
            {
                "sub": user.get("id"),
                "aid": user.get("academic_id"),
                "rid": resource.get("id"),
                "name": user.get("full_name"),
                "kind": kind,
                "nonce": nonce,
                "purpose": "watermark",
            },
            self.secret,
            ttl_seconds=self.ttl_seconds,
        )
        name = user.get("full_name") or "DEIY Student"
        academic_id = user.get("academic_id") or "N/A"
        return {
            "token": token,
            "nonce": nonce,
            "expires_in": self.ttl_seconds,
            "expires_at": utcnow().isoformat() + "Z",
            "overlay": {
                "text": f"{name} | {academic_id}",
                "secondary_text": resource.get("title") or "",
                "position": "moving",
                "opacity": 0.35,
                "font_size": 14,
                "color": "#eb9f12",
                "shadow": True,
                "move_interval_seconds": 7,
                "applies_to": ["video", "document", "download"],
            },
            "anti_piracy": {
                "block_screen_recording": True,
                "detect_devtools": True,
                "single_session": True,
                "download_bound_to_academic_id": True,
            },
        }

    def verify(self, token: str) -> dict:
        return decode_token(token, self.secret, expected_purpose="watermark")

    def issue_download(self, *, user: dict, resource: dict, variant: str) -> dict:
        manifest = self.issue(user=user, resource=resource, kind="download")
        manifest["variant"] = variant
        manifest["overlay"]["applies_to"] = ["download"]
        return manifest
