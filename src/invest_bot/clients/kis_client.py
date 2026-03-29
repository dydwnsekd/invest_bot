from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
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
            raise ValueError("KIS credentials are missing. Set the appropriate app key and secret in the environment.")

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
