from invest_bot.config.settings import AppSettings
from invest_bot.db.bootstrap import build_readiness_report


def test_build_readiness_report_points_to_draft_artifacts():
    report = build_readiness_report(AppSettings())

    assert report["draft_only"] is True
    assert report["artifacts"]["docker_compose"]["exists"] is True
    assert report["artifacts"]["erd"]["exists"] is True
    assert report["artifacts"]["migration_plan"]["exists"] is True
    assert report["artifacts"]["repository_contracts"]["exists"] is True
