from __future__ import annotations

from dataclasses import dataclass
from html import escape
from pathlib import Path

import pandas as pd


@dataclass(slots=True)
class DatasetPreview:
    name: str
    path: Path
    row_count: int
    columns: list[str]
    description: str
    symbol: str
    symbol_name: str
    column_help_html: str
    column_selector_html: str
    preview_html: str


@dataclass(slots=True)
class DashboardSnapshot:
    raw_previews: list[DatasetPreview]
    processed_previews: list[DatasetPreview]


class DashboardDataService:
    """Collect previews from saved CSV datasets for a local dashboard."""

    DATASET_DESCRIPTIONS = {
        "daily_prices": "종목별 일봉 원본 데이터입니다. 가격과 거래량 기반 분석의 출발점입니다.",
        "daily_prices_summary": "일봉 수집 요청에 대한 요약 데이터입니다.",
        "stock_info": "종목 기본정보입니다. 종목명과 코드 확인에 사용합니다.",
        "investor_daily": "종목별 투자자 수급 일별 상세 데이터입니다.",
        "investor_daily_summary": "투자자 수급 일별 요약 데이터입니다.",
        "daily_prices_indicators": "일봉 데이터 기반 기본 지표 계산 결과입니다.",
    }

    COLUMN_DESCRIPTIONS = {
        "symbol": "종목 코드",
        "symbol_name": "종목명",
        "date": "영업일 또는 기준 일자",
        "open": "시가",
        "high": "고가",
        "low": "저가",
        "close": "종가",
        "volume": "거래량",
        "turnover": "거래대금",
        "ma_5": "5일 이동평균",
        "ma_20": "20일 이동평균",
        "ma_60": "60일 이동평균",
        "volume_ma_5": "5일 거래량 이동평균",
        "rsi_14": "14일 RSI",
        "pdno": "종목 코드",
        "prdt_abrv_name": "종목명",
        "stck_bsop_date": "주식 영업일자",
        "stck_oprc": "주식 시가",
        "stck_hgpr": "주식 고가",
        "stck_lwpr": "주식 저가",
        "stck_clpr": "주식 종가",
        "acml_vol": "누적 거래량",
        "acml_tr_pbmn": "누적 거래대금",
        "frgn_ntby_qty": "외국인 순매수 수량",
        "orgn_ntby_qty": "기관 순매수 수량",
        "prsn_ntby_qty": "개인 순매수 수량",
        "hts_kor_isnm": "HTS 기준 종목 한글명",
        "mksc_shrn_iscd": "유가증권 단축 종목코드",
        "bstp_kor_isnm": "업종 한글명",
        "rprs_mrkt_kor_name": "대표 시장명",
        "bstp_cls_code": "업종 분류 코드",
        "scts_mket_lstg_dt": "상장일자",
        "stck_prpr": "현재가",
        "prdy_vrss": "전일 대비",
        "prdy_ctrt": "전일 대비율",
    }

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

        symbol_name_map = self._load_symbol_name_map()
        for dataset_dir in sorted(path for path in root.iterdir() if path.is_dir()):
            csv_files = sorted(dataset_dir.glob("*.csv"), reverse=True)
            if not csv_files:
                continue

            latest_file = csv_files[0]
            frame = pd.read_csv(latest_file)
            symbol = self._extract_symbol(latest_file)
            symbol_name = symbol_name_map.get(symbol, "")
            enriched = self._enrich_frame(frame, symbol=symbol, symbol_name=symbol_name)

            previews.append(
                DatasetPreview(
                    name=dataset_dir.name,
                    path=latest_file,
                    row_count=len(enriched),
                    columns=list(enriched.columns),
                    description=self.DATASET_DESCRIPTIONS.get(dataset_dir.name, "데이터셋 설명이 아직 정의되지 않았습니다."),
                    symbol=symbol,
                    symbol_name=symbol_name,
                    column_help_html=self._build_column_help(enriched.columns),
                    column_selector_html=self._build_column_selector(dataset_dir.name, enriched.columns),
                    preview_html=self._frame_to_html(dataset_dir.name, enriched),
                )
            )
        return previews

    @staticmethod
    def _extract_symbol(file_path: Path) -> str:
        stem = file_path.stem
        return stem.split("_")[0] if "_" in stem else stem

    def _load_symbol_name_map(self) -> dict[str, str]:
        stock_info_dir = self.raw_root / "stock_info"
        if not stock_info_dir.exists():
            return {}

        mapping: dict[str, str] = {}
        for csv_file in sorted(stock_info_dir.glob("*.csv")):
            frame = pd.read_csv(csv_file)
            if frame.empty:
                continue
            code = str(frame.iloc[0].get("pdno", "")).strip() or csv_file.stem
            name = str(frame.iloc[0].get("prdt_abrv_name", "")).strip()
            if code and name:
                mapping[code] = name
        return mapping

    @staticmethod
    def _enrich_frame(frame: pd.DataFrame, symbol: str, symbol_name: str) -> pd.DataFrame:
        enriched = frame.copy()
        if symbol and "symbol" not in enriched.columns:
            enriched.insert(0, "symbol", symbol)
        if symbol_name and "symbol_name" not in enriched.columns:
            insert_at = 1 if "symbol" in enriched.columns else 0
            enriched.insert(insert_at, "symbol_name", symbol_name)
        return enriched

    def _build_column_help(self, columns: list[str]) -> str:
        items = []
        for column in columns:
            description = self.COLUMN_DESCRIPTIONS.get(column, self._fallback_column_description(column))
            items.append(f"<li><strong>{escape(str(column))}</strong>: {escape(description)}</li>")
        return '<ul class="column-help">' + "".join(items) + "</ul>"

    @staticmethod
    def _fallback_column_description(column: str) -> str:
        normalized = column.replace("_", " ").strip()
        if not normalized:
            return "컬럼 설명을 아직 정의하지 않았습니다."
        return f"원본 응답 컬럼입니다. 현재 자동 설명: {normalized}"

    @staticmethod
    def _build_column_selector(dataset_name: str, columns: list[str]) -> str:
        items = []
        for index, column in enumerate(columns):
            checked = "checked" if index < min(8, len(columns)) else ""
            items.append(
                f"""
<label class="column-option">
  <input type="checkbox" class="column-toggle" data-target="table-{dataset_name}" data-column="{escape(str(column))}" {checked} />
  <span>{escape(str(column))}</span>
</label>
                """.strip()
            )
        return '<div class="column-selector">' + "".join(items) + "</div>"

    @staticmethod
    def _frame_to_html(dataset_name: str, frame: pd.DataFrame) -> str:
        if frame.empty:
            return "<p>비어 있는 데이터입니다.</p>"

        safe_frame = frame.fillna("")
        table_id = f"table-{dataset_name}"
        row_options = []
        for value in (5, 10, 20, 50):
            if value <= len(safe_frame):
                row_options.append(value)
        if len(safe_frame) not in row_options:
            row_options.append(len(safe_frame))

        options_html = "".join(f'<option value="{value}">{value}행</option>' for value in row_options)
        headers = "".join(
            f'<th data-column="{escape(str(column))}">{escape(str(column))}</th>' for column in safe_frame.columns
        )

        rows = []
        for index, row in enumerate(safe_frame.itertuples(index=False), start=1):
            cells = []
            for column, value in zip(safe_frame.columns, row):
                cells.append(f'<td data-column="{escape(str(column))}">{escape(str(value))}</td>')
            rows.append(f'<tr data-row-index="{index}">{"".join(cells)}</tr>')

        return f"""
<div class="toolbar">
  <label>
    표시 행 수
    <select class="row-selector" data-target="{table_id}">
      {options_html}
    </select>
  </label>
</div>
<table id="{table_id}" class="dataset-table">
  <thead>
    <tr>{headers}</tr>
  </thead>
  <tbody>
    {''.join(rows)}
  </tbody>
</table>
        """.strip()

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
      max-width: 1280px;
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
    .description {{
      margin: 0 0 14px;
      color: #334155;
      line-height: 1.5;
    }}
    .toolbar {{
      display: flex;
      justify-content: flex-end;
      margin-bottom: 10px;
    }}
    .toolbar label {{
      display: inline-flex;
      gap: 8px;
      align-items: center;
      color: var(--muted);
      font-size: 14px;
    }}
    .toolbar select {{
      border: 1px solid var(--line);
      border-radius: 10px;
      background: white;
      padding: 6px 10px;
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
    .column-help {{
      margin: 0 0 14px;
      padding-left: 18px;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.6;
    }}
    .column-selector {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px 12px;
      margin-bottom: 14px;
      padding: 12px;
      border: 1px solid #ece6da;
      border-radius: 12px;
      background: #faf8f2;
    }}
    .column-option {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      color: #334155;
      font-size: 13px;
    }}
    .symbol-chip {{
      display: inline-flex;
      gap: 8px;
      align-items: center;
      margin-bottom: 10px;
      padding: 8px 12px;
      border-radius: 999px;
      background: #eef8f6;
      color: #0f766e;
      font-size: 13px;
      font-weight: 600;
    }}
  </style>
</head>
<body>
  <div class="page">
    <section class="hero">
      <h1>invest_bot dashboard</h1>
      <p>수집된 raw 데이터와 분석된 processed 데이터를 확인할 수 있는 로컬 대시보드입니다. 컬럼 설명은 표 위에 두고, 보고 싶은 컬럼만 선택해서 볼 수 있습니다.</p>
    </section>
    {self._render_section("Raw Data", "수집된 원본 데이터", snapshot.raw_previews)}
    {self._render_section("Processed Data", "지표 계산 결과", snapshot.processed_previews)}
  </div>
  <script>
    const updateVisibleRows = (select) => {{
      const table = document.getElementById(select.dataset.target);
      if (!table) return;
      const limit = Number(select.value);
      table.querySelectorAll("tbody tr").forEach((row, index) => {{
        row.style.display = index < limit ? "" : "none";
      }});
    }};

    const updateVisibleColumns = (checkbox) => {{
      const table = document.getElementById(checkbox.dataset.target);
      if (!table) return;
      const column = checkbox.dataset.column;
      const display = checkbox.checked ? "" : "none";
      table.querySelectorAll(`[data-column="${{column}}"]`).forEach((cell) => {{
        cell.style.display = display;
      }});
    }};

    document.querySelectorAll(".row-selector").forEach((select) => {{
      select.addEventListener("change", () => updateVisibleRows(select));
      updateVisibleRows(select);
    }});

    document.querySelectorAll(".column-toggle").forEach((checkbox) => {{
      checkbox.addEventListener("change", () => updateVisibleColumns(checkbox));
      updateVisibleColumns(checkbox);
    }});
  </script>
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
                symbol_chip = ""
                if preview.symbol:
                    symbol_chip = "종목 코드: " + escape(preview.symbol)
                    if preview.symbol_name:
                        symbol_chip += " / 종목명: " + escape(preview.symbol_name)
                    symbol_chip = f'<div class="symbol-chip">{symbol_chip}</div>'

                cards.append(
                    f"""
<article class="card">
  <h3>{escape(preview.name)}</h3>
  {symbol_chip}
  <p class="description">{escape(preview.description)}</p>
  <div class="meta">
    최신 파일: {escape(str(preview.path))}<br/>
    행 수: {preview.row_count} / 컬럼 수: {len(preview.columns)}
  </div>
  {preview.column_help_html}
  {preview.column_selector_html}
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
