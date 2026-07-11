from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import requests

from invest_bot.config.settings import AppSettings


@dataclass(slots=True)
class AccessToken:
    value: str
    expires_at: datetime

    def is_expired(self) -> bool:
        return datetime.now(UTC) >= self.expires_at


class KISClient:
    """Minimal REST client for KIS quotation APIs used by invest_bot."""

    def __init__(self, settings: AppSettings, session: requests.Session | None = None) -> None:
        self.settings = settings
        self.session = session or requests.Session()
        self._token: AccessToken | None = None

    def authenticate(self) -> AccessToken:
        if self._token and not self._token.is_expired():
            return self._token

        if not self.settings.kis_app_key or not self.settings.kis_app_secret:
            raise ValueError("KIS credentials are missing. Set the appropriate app key and secret in config/app.yaml or environment.")

        cached = self._load_cached_token()
        if cached is not None and not cached.is_expired():
            self._token = cached
            return cached

        response = self.session.post(
            f"{self.settings.kis_base_url}/oauth2/tokenP",
            json={
                "grant_type": "client_credentials",
                "appkey": self.settings.kis_app_key,
                "appsecret": self.settings.kis_app_secret,
            },
            headers={"content-type": "application/json"},
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()

        token_value = payload["access_token"]
        expires_raw = payload.get("access_token_token_expired")
        expires_at = self._parse_expiration(expires_raw)
        self._token = AccessToken(value=token_value, expires_at=expires_at)
        self._save_cached_token(self._token)
        return self._token

    def get_json(self, api_path: str, tr_id: str, params: dict[str, Any], tr_cont: str = "") -> dict[str, Any]:
        token = self.authenticate()
        response = self.session.get(
            f"{self.settings.kis_base_url}{api_path}",
            headers={
                "content-type": "application/json",
                "authorization": f"Bearer {token.value}",
                "appkey": self.settings.kis_app_key,
                "appsecret": self.settings.kis_app_secret,
                "tr_id": tr_id,
                "custtype": "P",
                "tr_cont": tr_cont,
            },
            params=params,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    @staticmethod
    def _parse_expiration(value: str | None) -> datetime:
        if value:
            return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)
        return datetime.now(UTC) + timedelta(hours=23)

    def _token_cache_path(self) -> Path:
        configured = os.getenv("INVEST_BOT_KIS_TOKEN_CACHE", "").strip()
        if configured:
            return Path(configured)
        key_digest = hashlib.sha256(self.settings.kis_app_key.encode("utf-8")).hexdigest()[:12]
        return Path("/tmp") / "invest_bot" / f"kis_token_{self.settings.trading_mode.value}_{key_digest}.json"

    def _load_cached_token(self) -> AccessToken | None:
        try:
            path = self._token_cache_path()
            if not path.exists():
                return None
            payload = json.loads(path.read_text(encoding="utf-8"))
            if payload.get("app_key") != self.settings.kis_app_key:
                return None
            token_value = str(payload.get("access_token", "")).strip()
            expires_raw = str(payload.get("expires_at", "")).strip()
            if not token_value or not expires_raw:
                return None
            expires_at = datetime.fromisoformat(expires_raw)
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=UTC)
            return AccessToken(value=token_value, expires_at=expires_at.astimezone(UTC))
        except Exception:
            return None

    def _save_cached_token(self, token: AccessToken) -> None:
        try:
            path = self._token_cache_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(
                    {
                        "app_key": self.settings.kis_app_key,
                        "access_token": token.value,
                        "expires_at": token.expires_at.astimezone(UTC).isoformat(),
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            path.chmod(0o600)
        except Exception:
            return None
