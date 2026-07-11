from __future__ import annotations

from datetime import UTC, datetime, timedelta

from invest_bot.clients.kis_client import KISClient
from invest_bot.config.settings import AppSettings
from tests.helpers import make_test_dir


class StubResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return self.payload


class StubSession:
    def __init__(self) -> None:
        self.post_calls = 0

    def post(self, *args, **kwargs) -> StubResponse:
        self.post_calls += 1
        return StubResponse(
            {
                "access_token": f"token-{self.post_calls}",
                "access_token_token_expired": (datetime.now(UTC) + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S"),
            }
        )


def test_kis_client_reuses_cached_token_across_instances(monkeypatch) -> None:
    cache_path = make_test_dir("kis_token_cache") / "token.json"
    monkeypatch.setenv("INVEST_BOT_KIS_TOKEN_CACHE", str(cache_path))
    settings = AppSettings(kis_mock_app_key="mock-key", kis_mock_app_secret="mock-secret")
    first_session = StubSession()
    first_client = KISClient(settings=settings, session=first_session)

    first_token = first_client.authenticate()

    second_session = StubSession()
    second_client = KISClient(settings=settings, session=second_session)
    second_token = second_client.authenticate()

    assert first_token.value == "token-1"
    assert second_token.value == "token-1"
    assert first_session.post_calls == 1
    assert second_session.post_calls == 0


def test_kis_client_ignores_expired_cached_token(monkeypatch) -> None:
    cache_path = make_test_dir("kis_token_cache_expired") / "token.json"
    monkeypatch.setenv("INVEST_BOT_KIS_TOKEN_CACHE", str(cache_path))
    settings = AppSettings(kis_mock_app_key="mock-key", kis_mock_app_secret="mock-secret")
    cache_path.write_text(
        (
            '{"app_key":"mock-key","access_token":"old-token",'
            f'"expires_at":"{(datetime.now(UTC) - timedelta(minutes=1)).isoformat()}"}}'
        ),
        encoding="utf-8",
    )
    session = StubSession()
    client = KISClient(settings=settings, session=session)

    token = client.authenticate()

    assert token.value == "token-1"
    assert session.post_calls == 1
