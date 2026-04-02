from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd


@dataclass(slots=True)
class DatasetPreview:
    name: str
    path: Path
    row_count: int
    columns: list[str]
    preview_html: str


@dataclass(slots=True)
class DashboardSnapshot:
    raw_previews: list[DatasetPreview]
    processed_previews: list[DatasetPreview]


class DashboardDataService:
    """Collect previews from saved CSV datasets for a local dashboard."""

    def __init__(
        self,
        raw_root: str | Path = "data/raw/domestic_stock",
        processed_root: str | Path = "data/processed/domestic_stock",
    ) -> None:
        self.raw_root = Path(raw_root)
        self.processed_root = Path(processed_root)

    def build_snapshot(self) -> DashboardSnapshot:
        return DashboardSnapshot(
            raw_previews=self._collect_previews(self.raw_root),
            processed_previews=self._collect_previews(self.processed_root),
        )

    def render_html(self) -> str:
        snapshot = self.build_snapshot()
        return self._render_snapshot(snapshot)

    def _collect_previews(self, root: Path) -> list[DatasetPreview]:
        previews: list[DatasetPreview] = []
        if not root.exists():
            return previews

        for dataset_dir in sorted(path for path in root.iterdir() if path.is_dir()):
            csv_files = sorted(dataset_dir.glob("*.csv"), reverse=True)
            if not csv_files:
                continue

            latest_file = csv_files[0]
            frame = pd.read_csv(latest_file)
            previews.append(
                DatasetPreview(
                    name=dataset_dir.name,
                    path=latest_file,
                    row_count=len(frame),
                    columns=list(frame.columns),
                    preview_html=self._frame_to_html(frame),
                )
            )
        return previews

    @staticmethod
    def _frame_to_html(frame: pd.DataFrame) -> str:
        if frame.empty:
            return "<p>비어 있는 데이터입니다.</p>"
        preview = frame.head(10).fillna("")
        return preview.to_html(index=False, classes="dataset-table", border=0)

    def _render_snapshot(self, snapshot: DashboardSnapshot) -> str:
        return f"""
<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>invest_bot dashboard</title>
  <style>
    :root {{
      --bg: #f4f1ea;
      --card: #fffdf8;
      --ink: #1f2933;
      --muted: #6b7280;
      --line: #d8d2c8;
      --accent: #0f766e;
      --accent-soft: #d9f3ef;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Segoe UI", "Noto Sans KR", sans-serif;
      color: var(--ink);
      background:
        radial-gradient(circle at top right, #d9f3ef 0%, transparent 30%),
        linear-gradient(180deg, #f7f4ee 0%, var(--bg) 100%);
    }}
    .page {{
      max-width: 1200px;
      margin: 0 auto;
      padding: 32px 20px 64px;
    }}
    .hero {{
      background: linear-gradient(135deg, #163a52 0%, #0f766e 100%);
      color: white;
      border-radius: 24px;
      padding: 28px;
      box-shadow: 0 16px 32px rgba(22, 58, 82, 0.18);
    }}
    .hero h1 {{
      margin: 0 0 8px;
      font-size: 32px;
    }}
    .hero p {{
      margin: 0;
      color: rgba(255, 255, 255, 0.88);
    }}
    .section {{
      margin-top: 28px;
    }}
    .section-header {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 12px;
    }}
    .section h2 {{
      margin: 0;
      font-size: 22px;
    }}
    .badge {{
      padding: 6px 10px;
      border-radius: 999px;
      background: var(--accent-soft);
      color: var(--accent);
      font-size: 13px;
      font-weight: 600;
    }}
    .cards {{
      display: grid;
      gap: 18px;
    }}
    .card {{
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 18px;
      box-shadow: 0 8px 18px rgba(31, 41, 51, 0.05);
    }}
    .card h3 {{
      margin: 0 0 6px;
    }}
    .meta {{
      color: var(--muted);
      font-size: 14px;
      margin-bottom: 14px;
      word-break: break-all;
    }}
    .empty {{
      background: rgba(255, 255, 255, 0.7);
      border: 1px dashed var(--line);
      border-radius: 18px;
      padding: 24px;
      color: var(--muted);
    }}
    .dataset-table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 14px;
      overflow: hidden;
    }}
    .dataset-table th,
    .dataset-table td {{
      padding: 10px 12px;
      border-bottom: 1px solid #ece6da;
      text-align: left;
      white-space: nowrap;
    }}
    .dataset-table th {{
      background: #f8f5ef;
      position: sticky;
      top: 0;
    }}
    .table-wrap {{
      overflow: auto;
      border-radius: 12px;
      border: 1px solid #ece6da;
    }}
  </style>
</head>
<body>
  <div class="page">
    <section class="hero">
      <h1>invest_bot dashboard</h1>
      <p>현재 수집된 raw 데이터와 분석된 processed 데이터를 로컬에서 빠르게 확인할 수 있는 간단한 대시보드입니다.</p>
    </section>
    {self._render_section("Raw Data", "수집된 원본 데이터", snapshot.raw_previews)}
    {self._render_section("Processed Data", "지표 계산 결과", snapshot.processed_previews)}
  </div>
</body>
</html>
        """.strip()

    @staticmethod
    def _render_section(title: str, badge: str, previews: list[DatasetPreview]) -> str:
        if not previews:
            body = '<div class="empty">아직 표시할 CSV 데이터가 없습니다. 먼저 수집 또는 분석 스크립트를 실행해 주세요.</div>'
        else:
            cards = []
            for preview in previews:
                cards.append(
                    f"""
<article class="card">
  <h3>{preview.name}</h3>
  <div class="meta">
    최신 파일: {preview.path}<br/>
    행 수: {preview.row_count} / 컬럼 수: {len(preview.columns)}
  </div>
  <div class="table-wrap">
    {preview.preview_html}
  </div>
</article>
                    """.strip()
                )
            body = '<div class="cards">' + "".join(cards) + "</div>"

        return f"""
<section class="section">
  <div class="section-header">
    <h2>{title}</h2>
    <span class="badge">{badge}</span>
  </div>
  {body}
</section>
        """.strip()
