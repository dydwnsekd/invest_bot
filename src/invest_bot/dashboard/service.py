from __future__ import annotations

from dataclasses import dataclass
from html import escape
from pathlib import Path
from xml.etree import ElementTree

import pandas as pd


@dataclass(frozen=True, slots=True)
class ColumnMeta:
    label: str
    description: str
    why: str


@dataclass(frozen=True, slots=True)
class DatasetGuide:
    title: str
    summary: str
    purpose: str
    first_look: str
    recommended_columns: tuple[str, ...]


@dataclass(slots=True)
class DatasetPreview:
    name: str
    display_name: str
    path: Path
    row_count: int
    columns: list[str]
    summary: str
    purpose: str
    first_look: str
    symbol: str
    symbol_name: str
    recommended_columns: list[str]
    column_help_html: str
    column_selector_html: str
    preview_html: str


@dataclass(slots=True)
class DashboardSnapshot:
    raw_previews: list[DatasetPreview]
    processed_previews: list[DatasetPreview]


@dataclass(slots=True)
class TestCasePreview:
    name: str
    status: str
    detail: str


@dataclass(slots=True)
class TestReportPreview:
    total: int
    passed: int
    failed: int
    skipped: int
    errors: int
    command: str
    path: Path
    test_cases: list[TestCasePreview]


class DashboardDataService:
    """Render a beginner-friendly local dashboard."""

    DATASET_GUIDES = {
        "daily_prices": DatasetGuide(
            title="일봉 가격 데이터",
            summary="하루 단위로 주가가 어떻게 움직였는지 보여주는 기본 데이터입니다.",
            purpose="가격 흐름과 거래량 변화를 이해할 때 가장 먼저 봅니다.",
            first_look="날짜, 종가, 거래량부터 보면 됩니다. 종가는 장 마감 가격이고 거래량은 얼마나 많이 거래됐는지 뜻합니다.",
            recommended_columns=("date", "close", "open", "high", "low", "volume"),
        ),
        "daily_prices_summary": DatasetGuide(
            title="일봉 수집 요약",
            summary="일봉 데이터를 언제 어떤 범위로 받아왔는지 정리한 정보입니다.",
            purpose="수집이 정상인지, 요청 범위가 맞는지 빠르게 확인할 때 씁니다.",
            first_look="시작일, 종료일, 행 수가 기대한 값과 맞는지 보세요.",
            recommended_columns=("symbol", "start_date", "end_date", "row_count"),
        ),
        "stock_info": DatasetGuide(
            title="종목 기본 정보",
            summary="종목명, 종목코드, 시장, 업종처럼 회사를 식별하는 정보입니다.",
            purpose="다른 데이터가 어떤 회사 것인지 이해하기 쉽게 만듭니다.",
            first_look="종목코드와 종목명부터 확인하면 다른 카드도 읽기 쉬워집니다.",
            recommended_columns=("pdno", "prdt_abrv_name", "rprs_mrkt_kor_name", "bstp_kor_isnm"),
        ),
        "investor_daily": DatasetGuide(
            title="투자자 수급 일별 데이터",
            summary="개인, 외국인, 기관이 하루 동안 얼마나 순매수 또는 순매도했는지 보여줍니다.",
            purpose="누가 많이 샀고 누가 많이 팔았는지 보조적으로 판단할 때 씁니다.",
            first_look="날짜와 개인, 외국인, 기관 순매수 수량을 함께 보세요. 양수면 더 많이 샀다는 뜻입니다.",
            recommended_columns=("stck_bsop_date", "prsn_ntby_qty", "frgn_ntby_qty", "orgn_ntby_qty"),
        ),
        "investor_daily_summary": DatasetGuide(
            title="수급 수집 요약",
            summary="투자자 수급 데이터를 어떤 범위로 저장했는지 정리한 요약입니다.",
            purpose="수집 성공 여부와 기간을 확인할 때 씁니다.",
            first_look="일봉 요약과 마찬가지로 기간과 행 수부터 확인하면 됩니다.",
            recommended_columns=("symbol", "start_date", "end_date", "row_count"),
        ),
        "daily_prices_indicators": DatasetGuide(
            title="기본 지표 계산 결과",
            summary="일봉 가격을 바탕으로 이동평균과 RSI 같은 지표를 계산한 결과입니다.",
            purpose="가격 자체뿐 아니라 추세와 과열 여부를 함께 볼 때 씁니다.",
            first_look="종가, 5일 이동평균, 20일 이동평균, RSI를 함께 보면 흐름을 읽기 좋습니다.",
            recommended_columns=("date", "close", "ma_5", "ma_20", "rsi_14", "volume_ma_5"),
        ),
    }

    COLUMN_META = {
        "symbol": ColumnMeta("종목코드", "주식을 구분하는 고유 코드입니다.", "여러 데이터를 같은 종목끼리 연결할 수 있습니다."),
        "symbol_name": ColumnMeta("종목명", "사람이 읽기 쉬운 회사 이름입니다.", "코드만 볼 때보다 훨씬 이해가 쉽습니다."),
        "date": ColumnMeta("날짜", "해당 데이터가 기록된 날짜입니다.", "언제의 정보인지 확인할 수 있습니다."),
        "open": ColumnMeta("시가", "장이 시작했을 때 가격입니다.", "하루 출발 흐름을 볼 수 있습니다."),
        "high": ColumnMeta("고가", "그날 가장 높았던 가격입니다.", "상승 강도를 확인할 수 있습니다."),
        "low": ColumnMeta("저가", "그날 가장 낮았던 가격입니다.", "하락 폭을 확인할 수 있습니다."),
        "close": ColumnMeta("종가", "장이 끝났을 때 가격입니다.", "가장 많이 쓰는 기준 가격입니다."),
        "volume": ColumnMeta("거래량", "그날 거래된 주식 수량입니다.", "가격 움직임이 얼마나 활발했는지 보여줍니다."),
        "turnover": ColumnMeta("거래대금", "거래를 금액 기준으로 본 값입니다.", "실제로 오간 자금 규모를 볼 수 있습니다."),
        "ma_5": ColumnMeta("5일 이동평균", "최근 5거래일 종가 평균입니다.", "아주 짧은 추세를 빠르게 볼 수 있습니다."),
        "ma_20": ColumnMeta("20일 이동평균", "최근 20거래일 종가 평균입니다.", "한 달 안팎의 흐름을 보기 좋습니다."),
        "ma_60": ColumnMeta("60일 이동평균", "최근 60거래일 종가 평균입니다.", "중기 추세를 확인할 수 있습니다."),
        "volume_ma_5": ColumnMeta("5일 평균 거래량", "최근 5거래일 평균 거래량입니다.", "오늘 거래량이 평소보다 많은지 비교할 수 있습니다."),
        "rsi_14": ColumnMeta("RSI 14", "최근 가격 상승 강도를 수치화한 지표입니다.", "너무 과열됐거나 너무 약한 구간인지 참고할 수 있습니다."),
        "pdno": ColumnMeta("종목코드", "KIS 원본 기준 종목코드입니다.", "다른 데이터와 종목을 연결할 때 기준이 됩니다."),
        "prdt_abrv_name": ColumnMeta("종목명", "KIS 원본 기준 종목명입니다.", "어느 회사인지 바로 알 수 있습니다."),
        "stck_bsop_date": ColumnMeta("영업일자", "주식 영업일 기준 날짜입니다.", "수급 값이 언제의 값인지 알 수 있습니다."),
        "stck_oprc": ColumnMeta("시가", "KIS 원본 일봉 시가입니다.", "원본 가격 흐름을 그대로 볼 수 있습니다."),
        "stck_hgpr": ColumnMeta("고가", "KIS 원본 일봉 고가입니다.", "원본 기준 최고 가격입니다."),
        "stck_lwpr": ColumnMeta("저가", "KIS 원본 일봉 저가입니다.", "원본 기준 최저 가격입니다."),
        "stck_clpr": ColumnMeta("종가", "KIS 원본 일봉 종가입니다.", "원본 기준 마감 가격입니다."),
        "acml_vol": ColumnMeta("누적 거래량", "해당 날짜 기준 거래량입니다.", "그날 거래가 많았는지 판단할 수 있습니다."),
        "acml_tr_pbmn": ColumnMeta("누적 거래대금", "해당 날짜 기준 거래대금입니다.", "자금 유입 크기를 볼 수 있습니다."),
        "frgn_ntby_qty": ColumnMeta("외국인 순매수", "외국인이 산 수량에서 판 수량을 뺀 값입니다.", "양수면 외국인이 더 많이 샀다는 뜻입니다."),
        "orgn_ntby_qty": ColumnMeta("기관 순매수", "기관이 산 수량에서 판 수량을 뺀 값입니다.", "기관 자금 흐름을 볼 수 있습니다."),
        "prsn_ntby_qty": ColumnMeta("개인 순매수", "개인이 산 수량에서 판 수량을 뺀 값입니다.", "개인 투자자 흐름을 볼 수 있습니다."),
        "hts_kor_isnm": ColumnMeta("종목명", "HTS 기준 종목명입니다.", "어떤 종목인지 사람이 읽기 쉽게 보여줍니다."),
        "mksc_shrn_iscd": ColumnMeta("단축 종목코드", "시장 내부에서 쓰는 짧은 종목코드입니다.", "다른 원본 컬럼과 함께 종목을 찾는 데 쓰입니다."),
        "bstp_kor_isnm": ColumnMeta("업종명", "회사가 속한 업종 이름입니다.", "비슷한 업종끼리 비교할 수 있습니다."),
        "rprs_mrkt_kor_name": ColumnMeta("대표 시장", "코스피, 코스닥 같은 시장 구분입니다.", "어느 시장 종목인지 쉽게 알 수 있습니다."),
        "bstp_cls_code": ColumnMeta("업종 분류 코드", "업종을 나누기 위한 코드입니다.", "업종 정리에 활용됩니다."),
        "scts_mket_lstg_dt": ColumnMeta("상장일", "주식이 처음 시장에 상장된 날짜입니다.", "신규 상장주인지 오래된 종목인지 파악할 수 있습니다."),
        "stck_prpr": ColumnMeta("현재가", "조회 시점의 현재 가격입니다.", "가장 최신 가격을 빠르게 볼 수 있습니다."),
        "prdy_vrss": ColumnMeta("전일 대비", "전일 종가와 비교한 가격 차이입니다.", "오늘 얼마나 오르거나 내렸는지 알 수 있습니다."),
        "prdy_ctrt": ColumnMeta("전일 대비율", "전일 대비 등락 비율입니다.", "퍼센트 기준 변화를 보기 좋습니다."),
        "start_date": ColumnMeta("시작일", "수집 요청의 시작 날짜입니다.", "어느 기간을 저장했는지 알 수 있습니다."),
        "end_date": ColumnMeta("종료일", "수집 요청의 종료 날짜입니다.", "데이터 최신 범위를 확인할 수 있습니다."),
        "row_count": ColumnMeta("행 수", "파일 안에 저장된 데이터 개수입니다.", "예상보다 적거나 많으면 수집 상태를 점검할 수 있습니다."),
    }

    def __init__(
        self,
        raw_root: str | Path = "data/raw/domestic_stock",
        processed_root: str | Path = "data/processed/domestic_stock",
        test_report_path: str | Path = "data/processed/test_reports/pytest_results.xml",
    ) -> None:
        self.raw_root = Path(raw_root)
        self.processed_root = Path(processed_root)
        self.test_report_path = Path(test_report_path)

    def build_snapshot(self) -> DashboardSnapshot:
        return DashboardSnapshot(
            raw_previews=self._collect_previews(self.raw_root),
            processed_previews=self._collect_previews(self.processed_root),
        )

    def render_html(self) -> str:
        snapshot = self.build_snapshot()
        return self._render_snapshot(snapshot)

    def load_test_report(self) -> TestReportPreview | None:
        if not self.test_report_path.exists():
            return None

        root = ElementTree.parse(self.test_report_path).getroot()
        suite = root if root.tag == "testsuite" else root.find("testsuite")
        if suite is None:
            return None

        total = int(suite.attrib.get("tests", "0"))
        failures = int(suite.attrib.get("failures", "0"))
        skipped = int(suite.attrib.get("skipped", "0"))
        errors = int(suite.attrib.get("errors", "0"))
        passed = max(total - failures - skipped - errors, 0)

        test_cases: list[TestCasePreview] = []
        for case in suite.findall("testcase"):
            failure = case.find("failure")
            skipped_node = case.find("skipped")
            error = case.find("error")

            status = "passed"
            detail = ""
            if failure is not None:
                status = "failed"
                detail = (failure.attrib.get("message") or failure.text or "").strip()
            elif skipped_node is not None:
                status = "skipped"
                detail = (skipped_node.attrib.get("message") or skipped_node.text or "").strip()
            elif error is not None:
                status = "error"
                detail = (error.attrib.get("message") or error.text or "").strip()

            class_name = case.attrib.get("classname", "").strip()
            case_name = case.attrib.get("name", "").strip()
            name = f"{class_name}::{case_name}" if class_name else case_name
            test_cases.append(TestCasePreview(name=name, status=status, detail=detail[:220]))

        metadata_root = self.test_report_path.parent
        command_file = metadata_root / "pytest_command.txt"
        command = command_file.read_text(encoding="utf-8").strip() if command_file.exists() else ""

        return TestReportPreview(
            total=total,
            passed=passed,
            failed=failures,
            skipped=skipped,
            errors=errors,
            command=command,
            path=self.test_report_path,
            test_cases=test_cases,
        )

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
            guide = self.DATASET_GUIDES.get(
                dataset_dir.name,
                DatasetGuide(
                    title=dataset_dir.name,
                    summary="아직 이 데이터 설명이 준비되지 않았습니다.",
                    purpose="파일과 컬럼 구조를 먼저 확인해 주세요.",
                    first_look="종목명, 날짜, 가격 관련 컬럼부터 보면 이해가 쉽습니다.",
                    recommended_columns=tuple(enriched.columns[: min(6, len(enriched.columns))]),
                ),
            )
            recommended = [column for column in guide.recommended_columns if column in enriched.columns]
            if not recommended:
                recommended = list(enriched.columns[: min(6, len(enriched.columns))])
            if "symbol_name" in enriched.columns and "symbol_name" not in recommended:
                recommended.insert(0, "symbol_name")
            if "symbol" in enriched.columns and "symbol" not in recommended:
                insert_at = 1 if "symbol_name" in recommended else 0
                recommended.insert(insert_at, "symbol")

            previews.append(
                DatasetPreview(
                    name=dataset_dir.name,
                    display_name=guide.title,
                    path=latest_file,
                    row_count=len(enriched),
                    columns=list(enriched.columns),
                    summary=guide.summary,
                    purpose=guide.purpose,
                    first_look=guide.first_look,
                    symbol=symbol,
                    symbol_name=symbol_name,
                    recommended_columns=recommended,
                    column_help_html=self._build_column_help(enriched.columns, recommended),
                    column_selector_html=self._build_column_selector(dataset_dir.name, enriched.columns, recommended),
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
            enriched.insert(1 if "symbol" in enriched.columns else 0, "symbol_name", symbol_name)
        return enriched

    def _column_meta(self, column: str) -> ColumnMeta:
        meta = self.COLUMN_META.get(column)
        if meta:
            return meta
        readable = column.replace("_", " ").strip() or column
        return ColumnMeta(
            label=readable.title(),
            description=f"{readable} 값을 담은 원본 컬럼입니다.",
            why="다른 컬럼과 함께 보면 데이터 구조를 이해하는 데 도움이 됩니다.",
        )

    def _build_column_help(self, columns: list[str], recommended_columns: list[str]) -> str:
        cards = []
        for column in columns:
            meta = self._column_meta(column)
            recommended_badge = '<span class="mini-badge">처음 보기 추천</span>' if column in recommended_columns else ""
            cards.append(
                f"""
<article class="column-card">
  <div class="column-card-head">
    <div>
      <strong>{escape(meta.label)}</strong>
      <div class="column-key">{escape(column)}</div>
    </div>
    {recommended_badge}
  </div>
  <p>{escape(meta.description)}</p>
  <p class="why">왜 중요할까: {escape(meta.why)}</p>
</article>
                """.strip()
            )
        return '<div class="column-grid">' + "".join(cards) + "</div>"

    def _build_column_selector(self, dataset_name: str, columns: list[str], recommended_columns: list[str]) -> str:
        options = []
        recommended_set = set(recommended_columns)
        for column in columns:
            checked = "checked" if column in recommended_set else ""
            options.append(
                f"""
<label class="column-option">
  <input type="checkbox" class="column-toggle" data-target="table-{dataset_name}" data-storage-key="columns-{dataset_name}" data-column="{escape(column)}" {checked} />
  <span>{escape(self._column_meta(column).label)}</span>
  <small>{escape(column)}</small>
</label>
                """.strip()
            )

        return f"""
<section class="controls-panel">
  <div class="controls-text">
    <h4>표에 표시할 컬럼 선택</h4>
    <p>처음에는 추천 컬럼만 켜두고, 필요할 때만 추가해서 보는 편이 읽기 쉽습니다.</p>
  </div>
  <div class="quick-actions">
    <button type="button" class="quick-button" data-target="table-{dataset_name}" data-mode="recommended" data-columns="{escape(','.join(recommended_columns))}">추천 컬럼만</button>
    <button type="button" class="quick-button" data-target="table-{dataset_name}" data-mode="all">전체 컬럼</button>
    <button type="button" class="quick-button" data-target="table-{dataset_name}" data-mode="clear">모두 숨기기</button>
  </div>
  <div class="column-selector">{"".join(options)}</div>
</section>
        """.strip()

    def _frame_to_html(self, dataset_name: str, frame: pd.DataFrame) -> str:
        if frame.empty:
            return '<p class="empty-text">아직 저장된 데이터가 없습니다.</p>'

        safe_frame = frame.fillna("")
        table_id = f"table-{dataset_name}"
        row_options = [value for value in (5, 10, 20, 50) if value <= len(safe_frame)]
        if len(safe_frame) not in row_options:
            row_options.append(len(safe_frame))

        options_html = "".join(f'<option value="{value}">{value}행</option>' for value in row_options)
        headers = "".join(self._build_header(column) for column in safe_frame.columns)
        rows = []
        for index, row in enumerate(safe_frame.itertuples(index=False), start=1):
            cells = [
                f'<td data-column="{escape(column)}" title="{escape(self._column_meta(column).description)}">{escape(str(value))}</td>'
                for column, value in zip(safe_frame.columns, row)
            ]
            rows.append(f'<tr data-row-index="{index}">{"".join(cells)}</tr>')

        return f"""
<div class="table-toolbar">
  <div>
    <strong>데이터 미리보기</strong>
    <span>최신 CSV 파일 내용입니다.</span>
  </div>
  <label class="row-picker">표시 행 수
    <select class="row-selector" data-target="{table_id}" data-storage-key="rows-{dataset_name}">
      {options_html}
    </select>
  </label>
</div>
<table id="{table_id}" class="dataset-table">
  <thead><tr>{headers}</tr></thead>
  <tbody>{"".join(rows)}</tbody>
</table>
        """.strip()

    def _build_header(self, column: str) -> str:
        meta = self._column_meta(column)
        return f"""
<th data-column="{escape(column)}" title="{escape(meta.description)}">
  <div class="th-label">{escape(meta.label)}</div>
  <div class="th-key">{escape(column)}</div>
</th>
        """.strip()

    def _render_test_report_section(self) -> str:
        report = self.load_test_report()
        if report is None:
            return """
<section class="section">
  <div class="section-header">
    <div><h2>테스트 결과</h2><p>아직 저장된 테스트 결과가 없습니다. 테스트 실행 스크립트로 먼저 결과를 저장해 주세요.</p></div>
    <span class="badge">pytest</span>
  </div>
  <div class="empty">`scripts/run_tests.py`로 테스트를 실행하면 이 영역에서 통과, 실패, 스킵 결과를 보기 쉽게 확인할 수 있습니다.</div>
</section>
            """.strip()

        summary_cards = f"""
<div class="hero-stats">
  <div class="hero-stat test-stat"><strong>{report.total}</strong><span>전체 테스트</span></div>
  <div class="hero-stat test-stat"><strong>{report.passed}</strong><span>통과</span></div>
  <div class="hero-stat test-stat fail"><strong>{report.failed + report.errors}</strong><span>실패/에러</span></div>
  <div class="hero-stat test-stat"><strong>{report.skipped}</strong><span>스킵</span></div>
</div>
        """.strip()

        command_html = ""
        if report.command:
            command_html = f'<div class="meta-panel">실행 명령<br />{escape(report.command)}<br /><br />결과 파일<br />{escape(str(report.path))}</div>'

        test_rows = []
        for case in report.test_cases[:20]:
            badge_class = f"case-badge {case.status}"
            detail = f"<div class=\"case-detail\">{escape(case.detail)}</div>" if case.detail else ""
            test_rows.append(
                f"""
<article class="case-row">
  <div class="case-row-head">
    <strong>{escape(case.name)}</strong>
    <span class="{badge_class}">{escape(case.status)}</span>
  </div>
  {detail}
</article>
                """.strip()
            )

        return f"""
<section class="section">
  <div class="section-header">
    <div><h2>테스트 결과</h2><p>최근 저장된 `pytest` 실행 결과입니다. 실패가 있다면 어떤 테스트에서 문제가 났는지 바로 확인할 수 있습니다.</p></div>
    <span class="badge">pytest</span>
  </div>
  {summary_cards}
  <div class="card">
    <div class="card-top">
      <div>
        <h3>최근 테스트 실행</h3>
        <div class="dataset-key">최대 20개 테스트 케이스 미리보기</div>
      </div>
      {command_html}
    </div>
    <div class="guide-grid">
      <article class="guide-card"><h4>이 화면은 무엇인가</h4><p>테스트가 몇 개 통과했고 몇 개 실패했는지 한눈에 보는 영역입니다.</p></article>
      <article class="guide-card"><h4>왜 보는가</h4><p>터미널 로그를 길게 읽지 않아도, 실패한 테스트와 에러 메시지를 빠르게 찾을 수 있습니다.</p></article>
      <article class="guide-card"><h4>처음에는 무엇을 볼까</h4><p>먼저 실패/에러 개수를 보고, 아래 목록에서 `failed` 또는 `error` 상태의 테스트를 확인하면 됩니다.</p></article>
    </div>
    <div class="case-list">{"".join(test_rows) if test_rows else '<div class="empty-text">표시할 테스트 케이스가 없습니다.</div>'}</div>
  </div>
</section>
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
    :root {{ --bg:#f7f3eb; --card:#fffdf8; --ink:#182230; --muted:#667085; --line:#e7dccd; --accent:#0f766e; --accent2:#143c4b; --soft:#e3f5f0; --sand:#faf4e9; --shadow:0 18px 38px rgba(20,60,75,.09); }}
    * {{ box-sizing:border-box; }} body {{ margin:0; font-family:"Segoe UI","Noto Sans KR",sans-serif; color:var(--ink); background:radial-gradient(circle at top left,#fff0cf 0,transparent 24%), radial-gradient(circle at top right,#d6efe9 0,transparent 22%), linear-gradient(180deg,#fcfaf6 0,var(--bg) 100%); }}
    .page {{ max-width:1360px; margin:0 auto; padding:28px 18px 72px; }} .hero {{ background:linear-gradient(135deg,var(--accent2) 0,var(--accent) 100%); color:#fff; border-radius:28px; padding:32px; box-shadow:var(--shadow); }} .hero h1 {{ margin:0 0 10px; font-size:clamp(2rem,4vw,3.2rem); }} .hero p {{ margin:0; max-width:760px; line-height:1.7; color:rgba(255,255,255,.9); }}
    .hero-stats {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:12px; margin-top:22px; }} .hero-stat {{ padding:14px 16px; border-radius:18px; background:rgba(255,255,255,.1); border:1px solid rgba(255,255,255,.14); }} .hero-stat strong {{ display:block; font-size:1.2rem; }} .hero-stat span {{ color:rgba(255,255,255,.84); font-size:.92rem; }}
    .test-stat {{ background:#fff; border:1px solid #efe4d6; color:var(--ink); }} .test-stat span {{ color:var(--muted); }} .test-stat.fail strong {{ color:#b42318; }}
    .section {{ margin-top:28px; }} .section-header {{ display:flex; gap:12px; justify-content:space-between; align-items:end; margin-bottom:14px; }} .section-header h2 {{ margin:0; font-size:1.6rem; }} .section-header p {{ margin:6px 0 0; color:var(--muted); line-height:1.55; }} .badge {{ display:inline-flex; padding:8px 12px; border-radius:999px; background:var(--soft); color:var(--accent); font-weight:700; font-size:.88rem; white-space:nowrap; }}
    .cards {{ display:grid; gap:20px; }} .card {{ background:rgba(255,253,248,.92); border:1px solid var(--line); border-radius:24px; padding:22px; box-shadow:var(--shadow); }} .card-top {{ display:flex; gap:18px; justify-content:space-between; align-items:start; margin-bottom:18px; }} .card h3 {{ margin:0; font-size:1.35rem; }} .dataset-key {{ margin-top:6px; color:var(--muted); font-size:.92rem; }} .meta-panel {{ min-width:240px; padding:14px 16px; border-radius:18px; background:#fff; border:1px solid #efe4d6; color:var(--muted); font-size:.92rem; line-height:1.6; word-break:break-all; }} .symbol-chip {{ display:inline-flex; margin-top:10px; padding:8px 12px; border-radius:999px; background:var(--soft); color:var(--accent2); font-size:.88rem; font-weight:700; }}
    .guide-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:12px; margin-bottom:18px; }} .guide-card,.controls-panel,.column-card {{ background:var(--card); border:1px solid #efe4d6; border-radius:18px; }} .guide-card {{ padding:16px; }} .guide-card h4,.controls-text h4,.info-title {{ margin:0 0 8px; font-size:1rem; color:var(--accent2); }} .guide-card p,.controls-text p,.column-card p {{ margin:0; line-height:1.6; color:#344054; }}
    .info-title {{ margin:0 0 12px; }} .column-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(240px,1fr)); gap:12px; margin-bottom:16px; }} .column-card {{ padding:14px; }} .column-card-head {{ display:flex; gap:10px; justify-content:space-between; align-items:start; margin-bottom:8px; }} .column-key,.th-key,.column-option small {{ color:var(--muted); font-size:.78rem; word-break:break-all; }} .why {{ margin-top:8px !important; color:#475467 !important; }} .mini-badge {{ display:inline-flex; padding:6px 10px; border-radius:999px; background:#fff0cb; color:#8a5a00; font-size:.76rem; font-weight:700; }}
    .controls-panel {{ padding:16px; margin-bottom:16px; background:var(--sand); }} .quick-actions {{ display:flex; flex-wrap:wrap; gap:8px; margin-top:14px; }} .quick-button {{ border:1px solid #cfe8e2; background:#fff; color:var(--accent2); border-radius:999px; padding:9px 14px; font-weight:700; cursor:pointer; }} .quick-button:hover {{ background:#f4fffc; }}
    .column-selector {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:10px; margin-top:14px; }} .column-option {{ display:grid; grid-template-columns:auto 1fr; gap:4px 10px; align-items:start; padding:12px; border-radius:16px; background:rgba(255,255,255,.82); border:1px solid #efe4d6; }} .column-option input {{ margin-top:2px; }} .column-option span {{ font-size:.92rem; font-weight:700; color:#344054; }}
    .table-wrap {{ overflow:auto; border-radius:20px; border:1px solid #efe4d6; background:#fff; }} .table-toolbar {{ display:flex; gap:12px; justify-content:space-between; align-items:end; padding:16px 16px 10px; border-bottom:1px solid #f0e7db; background:#fffaf1; }} .table-toolbar strong {{ display:block; margin-bottom:4px; color:var(--accent2); }} .table-toolbar span,.row-picker {{ color:var(--muted); font-size:.88rem; }} .row-picker {{ display:inline-flex; gap:8px; align-items:center; font-weight:700; }} .row-picker select {{ border:1px solid #e5d9c9; border-radius:12px; background:#fff; padding:8px 10px; }}
    .dataset-table {{ width:100%; border-collapse:collapse; font-size:.92rem; }} .dataset-table th,.dataset-table td {{ padding:11px 12px; border-bottom:1px solid #f0e7db; text-align:left; white-space:nowrap; }} .dataset-table th {{ position:sticky; top:0; background:#fffaf1; z-index:1; }} .dataset-table tbody tr:nth-child(even) {{ background:rgba(250,247,239,.5); }} .dataset-table tbody tr:hover {{ background:rgba(223,244,239,.48); }} .th-label {{ font-weight:800; color:#1f2937; }} .empty,.empty-text {{ color:var(--muted); }} .empty {{ padding:28px; border-radius:22px; background:rgba(255,255,255,.78); border:1px dashed #e4d7c4; line-height:1.7; }} .empty-text {{ padding:18px; }}
    .case-list {{ display:grid; gap:10px; }} .case-row {{ padding:14px 16px; border-radius:18px; background:#fff; border:1px solid #efe4d6; }} .case-row-head {{ display:flex; gap:12px; justify-content:space-between; align-items:start; }} .case-row-head strong {{ word-break:break-word; }} .case-badge {{ display:inline-flex; padding:6px 10px; border-radius:999px; font-size:.78rem; font-weight:700; text-transform:uppercase; }} .case-badge.passed {{ background:#e8f7ef; color:#027a48; }} .case-badge.failed,.case-badge.error {{ background:#fee4e2; color:#b42318; }} .case-badge.skipped {{ background:#fff1d6; color:#9a6700; }} .case-detail {{ margin-top:8px; color:#475467; line-height:1.55; white-space:pre-wrap; }}
    @media (max-width:920px) {{ .card-top,.section-header,.table-toolbar {{ flex-direction:column; align-items:stretch; }} .meta-panel {{ min-width:0; }} }}
  </style>
</head>
<body>
  <div class="page">
    <section class="hero">
      <h1>invest_bot dashboard</h1>
      <p>수집한 주식 데이터를 초보자도 읽기 쉽게 정리한 화면입니다. 먼저 카드 상단 설명을 읽고, 추천 컬럼만 켜서 천천히 확인해보세요.</p>
      <div class="hero-stats">
        <div class="hero-stat"><strong>{len(snapshot.raw_previews)}</strong><span>원본 데이터셋</span></div>
        <div class="hero-stat"><strong>{len(snapshot.processed_previews)}</strong><span>분석 데이터셋</span></div>
        <div class="hero-stat"><strong>추천 컬럼 제공</strong><span>처음엔 필요한 정보만 보이도록 구성했습니다.</span></div>
      </div>
    </section>
    {self._render_test_report_section()}
    {self._render_section("원본 수집 데이터", "실제 KIS 수집 결과", "가격, 종목정보, 수급처럼 외부에서 받아온 원본 데이터입니다.", snapshot.raw_previews)}
    {self._render_section("분석 데이터", "가공 후 계산 결과", "원본 데이터를 바탕으로 계산한 이동평균, RSI 같은 지표 데이터입니다.", snapshot.processed_previews)}
  </div>
  <script>
    const applyRows = (select) => {{
      const table = document.getElementById(select.dataset.target);
      if (!table) return;
      const limit = Number(select.value);
      table.querySelectorAll("tbody tr").forEach((row, index) => row.style.display = index < limit ? "" : "none");
      if (select.dataset.storageKey) localStorage.setItem(select.dataset.storageKey, String(limit));
    }};
    const applyColumns = (tableId) => {{
      const boxes = Array.from(document.querySelectorAll(`.column-toggle[data-target="${{tableId}}"]`));
      const table = document.getElementById(tableId);
      if (!table) return;
      boxes.forEach((box) => {{
        const display = box.checked ? "" : "none";
        table.querySelectorAll(`[data-column="${{box.dataset.column}}"]`).forEach((cell) => cell.style.display = display);
      }});
      const key = boxes.find((box) => box.dataset.storageKey)?.dataset.storageKey;
      if (key) localStorage.setItem(key, JSON.stringify(boxes.filter((box) => box.checked).map((box) => box.dataset.column)));
    }};
    document.querySelectorAll(".row-selector").forEach((select) => {{
      const saved = select.dataset.storageKey ? localStorage.getItem(select.dataset.storageKey) : null;
      if (saved && Array.from(select.options).some((option) => option.value === saved)) select.value = saved;
      select.addEventListener("change", () => applyRows(select));
      applyRows(select);
    }});
    const grouped = new Map();
    document.querySelectorAll(".column-toggle").forEach((box) => {{
      if (!grouped.has(box.dataset.target)) grouped.set(box.dataset.target, []);
      grouped.get(box.dataset.target).push(box);
    }});
    grouped.forEach((boxes, tableId) => {{
      const key = boxes.find((box) => box.dataset.storageKey)?.dataset.storageKey;
      const saved = key ? localStorage.getItem(key) : null;
      if (saved) {{
        try {{
          const selected = new Set(JSON.parse(saved));
          boxes.forEach((box) => box.checked = selected.has(box.dataset.column));
        }} catch (_error) {{}}
      }}
      boxes.forEach((box) => box.addEventListener("change", () => applyColumns(tableId)));
      applyColumns(tableId);
    }});
    document.querySelectorAll(".quick-button").forEach((button) => {{
      button.addEventListener("click", () => {{
        const boxes = Array.from(document.querySelectorAll(`.column-toggle[data-target="${{button.dataset.target}}"]`));
        const recommended = new Set((button.dataset.columns || "").split(",").filter(Boolean));
        boxes.forEach((box) => {{
          if (button.dataset.mode === "all") box.checked = true;
          else if (button.dataset.mode === "clear") box.checked = false;
          else box.checked = recommended.has(box.dataset.column);
        }});
        applyColumns(button.dataset.target);
      }});
    }});
  </script>
</body>
</html>
        """.strip()

    @staticmethod
    def _render_section(title: str, badge: str, description: str, previews: list[DatasetPreview]) -> str:
        if not previews:
            body = '<div class="empty">아직 표시할 CSV 데이터가 없습니다. 먼저 수집 또는 분석 스크립트를 실행해 주세요.</div>'
        else:
            cards = []
            for preview in previews:
                symbol_chip = ""
                if preview.symbol:
                    chip = f"종목코드 {preview.symbol}"
                    if preview.symbol_name:
                        chip += f" · {preview.symbol_name}"
                    symbol_chip = f'<div class="symbol-chip">{escape(chip)}</div>'
                cards.append(
                    f"""
<article class="card">
  <div class="card-top">
    <div>
      <h3>{escape(preview.display_name)}</h3>
      <div class="dataset-key">{escape(preview.name)}</div>
      {symbol_chip}
    </div>
    <div class="meta-panel">
      최신 파일<br />{escape(str(preview.path))}<br /><br />
      데이터 행 수: {preview.row_count}<br />
      전체 컬럼 수: {len(preview.columns)}
    </div>
  </div>
  <div class="guide-grid">
    <article class="guide-card"><h4>이 데이터는 무엇인가</h4><p>{escape(preview.summary)}</p></article>
    <article class="guide-card"><h4>왜 보는가</h4><p>{escape(preview.purpose)}</p></article>
    <article class="guide-card"><h4>처음에는 무엇을 볼까</h4><p>{escape(preview.first_look)}</p></article>
  </div>
  <h4 class="info-title">컬럼 설명</h4>
  {preview.column_help_html}
  {preview.column_selector_html}
  <div class="table-wrap">{preview.preview_html}</div>
</article>
                    """.strip()
                )
            body = '<div class="cards">' + "".join(cards) + "</div>"

        return f"""
<section class="section">
  <div class="section-header">
    <div><h2>{escape(title)}</h2><p>{escape(description)}</p></div>
    <span class="badge">{escape(badge)}</span>
  </div>
  {body}
</section>
        """.strip()
