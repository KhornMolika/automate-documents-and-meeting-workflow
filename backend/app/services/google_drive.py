"""Optional Google Drive publishing for verified minutes."""

import json
import time
import uuid
from typing import Any, Dict, List

import httpx

from app.core.config import settings
from app.services.exporter import build_action_items_csv, build_mom_docx


class GoogleDriveError(RuntimeError):
    """Raised when Google Drive is not configured or rejects an upload."""


class GoogleDriveService:
    def __init__(self):
        self._token: str | None = None
        self._token_expires_at = 0.0

    @property
    def is_configured(self) -> bool:
        return bool(
            settings.GOOGLE_DRIVE_CLIENT_ID
            and settings.GOOGLE_DRIVE_CLIENT_SECRET
            and settings.GOOGLE_DRIVE_REFRESH_TOKEN
            and settings.GOOGLE_DRIVE_FOLDER_ID
        )

    async def _access_token(self) -> str:
        if self._token and time.time() < self._token_expires_at:
            return self._token
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "https://oauth2.googleapis.com/token",
                    data={
                        "client_id": settings.GOOGLE_DRIVE_CLIENT_ID,
                        "client_secret": settings.GOOGLE_DRIVE_CLIENT_SECRET,
                        "refresh_token": settings.GOOGLE_DRIVE_REFRESH_TOKEN,
                        "grant_type": "refresh_token",
                    },
                )
        except httpx.RequestError as exc:
            raise GoogleDriveError(f"Could not reach Google OAuth: {exc}") from exc
        if response.status_code != 200:
            raise GoogleDriveError(
                f"Google OAuth rejected the credentials (HTTP {response.status_code})."
            )
        payload = response.json()
        token = payload.get("access_token")
        if not token:
            raise GoogleDriveError("Google OAuth did not return an access token.")
        self._token = token
        self._token_expires_at = time.time() + max(60, int(payload.get("expires_in", 3600)) - 60)
        return token

    async def upload_bytes(self, filename: str, content: bytes, mime_type: str) -> Dict[str, Any]:
        if not self.is_configured:
            raise GoogleDriveError("Google Drive publishing is not configured.")
        token = await self._access_token()
        boundary = f"aub-{uuid.uuid4().hex}"
        metadata = json.dumps(
            {"name": filename, "parents": [settings.GOOGLE_DRIVE_FOLDER_ID]}
        ).encode("utf-8")
        body = (
            f"--{boundary}\r\n"
            "Content-Type: application/json; charset=UTF-8\r\n\r\n"
        ).encode("utf-8")
        body += metadata
        body += (
            f"\r\n--{boundary}\r\n"
            f"Content-Type: {mime_type}\r\n\r\n"
        ).encode("utf-8")
        body += content
        body += f"\r\n--{boundary}--\r\n".encode("utf-8")

        url = (
            "https://www.googleapis.com/upload/drive/v3/files"
            "?uploadType=multipart&fields=id,name,webViewLink"
        )
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    url,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": f"multipart/related; boundary={boundary}",
                    },
                    content=body,
                )
        except httpx.RequestError as exc:
            raise GoogleDriveError(f"Could not reach Google Drive: {exc}") from exc
        if response.status_code != 200:
            raise GoogleDriveError(
                f"Google Drive rejected the upload (HTTP {response.status_code}): "
                f"{response.text[:300]}"
            )
        return response.json()

    async def publish_minutes(self, meeting, summary) -> List[Dict[str, Any]]:
        safe_title = "".join(
            character if character.isalnum() or character in {"-", "_"} else "_"
            for character in meeting.title
        ).strip("_") or "meeting"
        docx_bytes = build_mom_docx(meeting, summary)
        csv_text = build_action_items_csv(meeting, summary).encode("utf-8-sig")
        return [
            await self.upload_bytes(
                f"{safe_title}_minutes.docx",
                docx_bytes,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ),
            await self.upload_bytes(
                f"{safe_title}_action_items.csv",
                csv_text,
                "text/csv",
            ),
        ]


google_drive = GoogleDriveService()
