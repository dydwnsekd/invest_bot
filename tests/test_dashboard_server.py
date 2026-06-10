from scripts.run_streamlit_dashboard import APP_PATH, build_streamlit_argv, resolve_dashboard_bind


def test_resolve_dashboard_bind_prefers_environment(monkeypatch) -> None:
    monkeypatch.setenv("INVEST_BOT_DASHBOARD_HOST", "0.0.0.0")
    monkeypatch.setenv("INVEST_BOT_DASHBOARD_PORT", "8123")

    assert resolve_dashboard_bind() == ("0.0.0.0", 8123)


def test_resolve_dashboard_bind_falls_back_on_invalid_port(monkeypatch) -> None:
    monkeypatch.delenv("INVEST_BOT_DASHBOARD_HOST", raising=False)
    monkeypatch.setenv("INVEST_BOT_DASHBOARD_PORT", "not-a-number")

    assert resolve_dashboard_bind(host="127.0.0.1", port=8000) == ("127.0.0.1", 8000)


def test_build_streamlit_argv_sets_host_port_and_headless_mode() -> None:
    assert build_streamlit_argv("0.0.0.0", 8000) == [
        "streamlit",
        "run",
        str(APP_PATH),
        "--server.address",
        "0.0.0.0",
        "--server.port",
        "8000",
        "--server.headless",
        "true",
    ]
