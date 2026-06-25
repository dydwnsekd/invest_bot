from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree

import pandas as pd

from invest_bot.config.settings import AppSettings
from invest_bot.db.engine import build_engine, build_session_factory
from invest_bot.db.frame_storage import DbFrameStorage
from invest_bot.db.repositories import SqlAlchemyStockRepository
from invest_bot.market.stock_master import StockMasterRepository


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
    """Load dashboard data for the Streamlit UI."""

    RAW_DATASETS = ("daily_prices", "daily_prices_summary", "stock_info", "investor_daily", "investor_daily_summary")
    PROCESSED_DATASETS = (
        "daily_prices_indicators",
        "golden_cross_signals",
        "market_reports",
        "backtest_trades",
        "backtest_summaries",
    )

    DATASET_GUIDES = {
        "daily_prices": DatasetGuide(
            title="일봉 가격 데이터",
            summary="하루 단위 주가와 거래량을 보여주는 가장 기본적인 데이터입니다.",
            purpose="가격 흐름과 거래량 변화를 이해하는 출발점입니다.",
            first_look="날짜, 종가, 시가, 고가, 저가, 거래량을 먼저 보세요.",
            recommended_columns=("date", "close", "open", "high", "low", "volume"),
        ),
        "daily_prices_summary": DatasetGuide(
            title="일봉 수집 요약",
            summary="일봉 데이터를 어떤 범위로 수집했는지 정리한 파일입니다.",
            purpose="수집 요청이 원하는 기간으로 잘 들어갔는지 확인할 수 있습니다.",
            first_look="종목 코드, 시작일, 종료일, 행 수를 보면 충분합니다.",
            recommended_columns=("symbol", "start_date", "end_date", "row_count"),
        ),
        "stock_info": DatasetGuide(
            title="종목 기본정보",
            summary="종목명, 시장, 업종 같은 회사의 기본 정보를 담은 데이터입니다.",
            purpose="다른 데이터가 어떤 회사 이야기인지 쉽게 이해할 수 있습니다.",
            first_look="종목명과 시장, 업종을 먼저 확인해 보세요.",
            recommended_columns=("pdno", "prdt_abrv_name", "rprs_mrkt_kor_name", "bstp_kor_isnm"),
        ),
        "investor_daily": DatasetGuide(
            title="투자자 수급 일별 데이터",
            summary="개인, 외국인, 기관이 얼마나 순매수했는지 보여주는 데이터입니다.",
            purpose="가격 외에 수급 흐름이 우호적인지도 함께 판단할 수 있습니다.",
            first_look="날짜, 개인 순매수, 외국인 순매수, 기관 순매수를 먼저 보세요.",
            recommended_columns=("stck_bsop_date", "prsn_ntby_qty", "frgn_ntby_qty", "orgn_ntby_qty"),
        ),
        "investor_daily_summary": DatasetGuide(
            title="투자자 수급 수집 요약",
            summary="수급 데이터를 어떤 날짜 범위로 받았는지 요약한 파일입니다.",
            purpose="수집 성공 여부와 기간 범위를 확인할 수 있습니다.",
            first_look="종목 코드, 시작일, 종료일, 행 수를 먼저 보세요.",
            recommended_columns=("symbol", "start_date", "end_date", "row_count"),
        ),
        "daily_prices_indicators": DatasetGuide(
            title="기본 지표 계산 결과",
            summary="일봉 데이터를 바탕으로 이동평균과 RSI를 계산한 결과입니다.",
            purpose="숫자만 보지 않고 추세와 과열 상태를 해석할 수 있습니다.",
            first_look="종가, ma_5, ma_20, ma_60, rsi_14를 먼저 보세요.",
            recommended_columns=("date", "close", "ma_5", "ma_20", "ma_60", "rsi_14"),
        ),
        "golden_cross_signals": DatasetGuide(
            title="골든크로스 신호",
            summary="5일선과 20일선의 교차를 기준으로 만든 매수, 매도, 관망 신호입니다.",
            purpose="전략이 지금 어떤 판단을 내렸는지 빠르게 확인할 수 있습니다.",
            first_look="날짜, signal, signal_reason, signal_ma_5, signal_ma_20을 먼저 보세요.",
            recommended_columns=("date", "signal", "signal_reason", "signal_ma_5", "signal_ma_20", "close"),
        ),
        "market_reports": DatasetGuide(
            title="시장 상황 요약 리포트",
            summary="지표, 골든크로스, 추가 전략 판단, 투자자 수급을 묶어 현재 장 상황을 정리한 리포트입니다.",
            purpose="종합 의견과 전략별 판단을 함께 읽어 현재 상태를 더 입체적으로 이해할 수 있습니다.",
            first_look="final_opinion, summary, golden_cross_signal, rsi_strategy_signal, trend_filter_signal, mean_reversion_signal을 먼저 보세요.",
            recommended_columns=(
                "date",
                "symbol_name",
                "final_opinion",
                "summary",
                "rsi_strategy_signal",
                "trend_filter_signal",
                "mean_reversion_signal",
                "trend_state",
                "golden_cross_signal",
                "rsi_state",
                "investor_flow",
            ),
        ),
    }

    COLUMN_META = {
        "symbol": ColumnMeta("종목코드", "주식을 구분하는 고유 코드입니다.", "여러 데이터를 같은 종목끼리 연결할 때 기준이 됩니다."),
        "symbol_name": ColumnMeta("종목명", "사람이 읽기 쉬운 회사 이름입니다.", "숫자 코드보다 훨씬 이해하기 쉽습니다."),
        "date": ColumnMeta("날짜", "해당 데이터가 기록된 날짜입니다.", "언제 기준 정보인지 알 수 있습니다."),
        "open": ColumnMeta("시가", "장이 시작했을 때의 가격입니다.", "하루 출발 흐름을 볼 수 있습니다."),
        "high": ColumnMeta("고가", "그날 가장 높았던 가격입니다.", "상승 강도를 확인할 수 있습니다."),
        "low": ColumnMeta("저가", "그날 가장 낮았던 가격입니다.", "하락 폭을 확인할 수 있습니다."),
        "close": ColumnMeta("종가", "장이 끝났을 때의 가격입니다.", "가장 많이 보는 기준 가격입니다."),
        "volume": ColumnMeta("거래량", "그날 거래된 주식 수량입니다.", "가격 움직임에 힘이 실렸는지 파악할 수 있습니다."),
        "turnover": ColumnMeta("거래대금", "거래를 금액 기준으로 본 값입니다.", "실제로 오간 자금 규모를 이해하는 데 도움이 됩니다."),
        "ma_5": ColumnMeta("5일 이동평균", "최근 5거래일 종가 평균입니다.", "아주 짧은 단기 흐름을 빠르게 보여줍니다."),
        "ma_20": ColumnMeta("20일 이동평균", "최근 20거래일 종가 평균입니다.", "한 달 안팎 흐름을 보기 좋습니다."),
        "ma_60": ColumnMeta("60일 이동평균", "최근 60거래일 종가 평균입니다.", "중기 추세를 볼 때 기준이 됩니다."),
        "volume_ma_5": ColumnMeta("5일 평균 거래량", "최근 5거래일 평균 거래량입니다.", "오늘 거래량이 평소보다 많은지 비교할 수 있습니다."),
        "rsi_14": ColumnMeta("RSI 14", "최근 가격 상승 강도를 수치화한 지표입니다.", "과열 가능성이나 약세 구간을 참고할 수 있습니다."),
        "pdno": ColumnMeta("종목코드", "KIS 원본 기준 종목코드입니다.", "원본 데이터를 연결할 때 기준이 됩니다."),
        "prdt_abrv_name": ColumnMeta("종목명", "KIS 원본 기준 종목명입니다.", "어느 회사인지 바로 이해할 수 있습니다."),
        "stck_bsop_date": ColumnMeta("영업일자", "수급 데이터 기준 날짜입니다.", "수급 값이 언제의 값인지 확인할 수 있습니다."),
        "stck_oprc": ColumnMeta("시가", "KIS 원본 일봉 시가입니다.", "원본 가격 흐름을 그대로 볼 수 있습니다."),
        "stck_hgpr": ColumnMeta("고가", "KIS 원본 일봉 고가입니다.", "원본 기준 최고 가격입니다."),
        "stck_lwpr": ColumnMeta("저가", "KIS 원본 일봉 저가입니다.", "원본 기준 최저 가격입니다."),
        "stck_clpr": ColumnMeta("종가", "KIS 원본 일봉 종가입니다.", "원본 기준 마감 가격입니다."),
        "acml_vol": ColumnMeta("누적 거래량", "해당 날짜 기준 거래량입니다.", "그날 거래가 활발했는지 판단할 수 있습니다."),
        "acml_tr_pbmn": ColumnMeta("누적 거래대금", "해당 날짜 기준 거래대금입니다.", "자금 유입 규모를 볼 수 있습니다."),
        "frgn_ntby_qty": ColumnMeta("외국인 순매수", "외국인이 산 수량에서 판 수량을 뺀 값입니다.", "양수면 외국인이 더 많이 샀다는 뜻입니다."),
        "orgn_ntby_qty": ColumnMeta("기관 순매수", "기관이 산 수량에서 판 수량을 뺀 값입니다.", "기관 자금 흐름을 볼 수 있습니다."),
        "prsn_ntby_qty": ColumnMeta("개인 순매수", "개인이 산 수량에서 판 수량을 뺀 값입니다.", "개인 투자자 흐름을 볼 수 있습니다."),
        "hts_kor_isnm": ColumnMeta("종목명", "HTS 기준 종목명입니다.", "종목을 사람 눈으로 구분하기 쉽게 도와줍니다."),
        "mksc_shrn_iscd": ColumnMeta("단축 종목코드", "시장 내부에서 쓰는 짧은 종목코드입니다.", "원본 데이터 연결 시 보조 키로 볼 수 있습니다."),
        "bstp_kor_isnm": ColumnMeta("업종명", "회사가 속한 업종 이름입니다.", "비슷한 업종끼리 비교할 수 있습니다."),
        "rprs_mrkt_kor_name": ColumnMeta("대표 시장", "코스피, 코스닥 같은 시장 구분입니다.", "어느 시장 종목인지 쉽게 알 수 있습니다."),
        "bstp_cls_code": ColumnMeta("업종 분류 코드", "업종을 구분하는 코드입니다.", "업종 정리용 보조 정보입니다."),
        "scts_mket_lstg_dt": ColumnMeta("상장일", "해당 주식이 상장된 날짜입니다.", "신규 상장주인지 오래된 종목인지 파악할 수 있습니다."),
        "stck_prpr": ColumnMeta("현재가", "조회 시점의 현재 가격입니다.", "최신 가격을 빠르게 확인할 수 있습니다."),
        "prdy_vrss": ColumnMeta("전일 대비", "전일 종가 대비 가격 차이입니다.", "오늘 얼마나 올랐거나 내렸는지 알 수 있습니다."),
        "prdy_ctrt": ColumnMeta("전일 대비율", "전일 대비 등락 비율입니다.", "가격 변화를 퍼센트로 볼 수 있습니다."),
        "start_date": ColumnMeta("시작일", "수집 요청의 시작 날짜입니다.", "어느 기간을 조회했는지 확인할 수 있습니다."),
        "end_date": ColumnMeta("종료일", "수집 요청의 종료 날짜입니다.", "최신 범위가 맞는지 확인할 수 있습니다."),
        "row_count": ColumnMeta("행 수", "파일 안에 저장된 데이터 개수입니다.", "수집 결과가 비정상적으로 적지 않은지 확인할 수 있습니다."),
        "signal": ColumnMeta("신호", "전략이 낸 최종 판단입니다.", "buy, sell, hold 중 어떤 상태인지 바로 볼 수 있습니다."),
        "signal_reason": ColumnMeta("신호 이유", "전략이 그 신호를 낸 이유를 적은 문장입니다.", "왜 매수나 매도가 나왔는지 이해할 수 있습니다."),
        "signal_prev_ma_5": ColumnMeta("직전 5일선", "신호 직전 시점의 5일 이동평균 값입니다.", "교차 전 상태를 비교할 수 있습니다."),
        "signal_prev_ma_20": ColumnMeta("직전 20일선", "신호 직전 시점의 20일 이동평균 값입니다.", "비교 기준이 되는 직전 상태입니다."),
        "signal_ma_5": ColumnMeta("현재 5일선", "신호 발생 시점의 5일 이동평균 값입니다.", "단기선이 올라섰는지 확인할 수 있습니다."),
        "signal_ma_20": ColumnMeta("현재 20일선", "신호 발생 시점의 20일 이동평균 값입니다.", "5일선과 비교해 골든크로스 여부를 판단합니다."),
        "golden_cross_signal": ColumnMeta("골든크로스 신호", "골든크로스 전략이 낸 최종 신호입니다.", "현재 전략 판단이 매수인지 관망인지 빠르게 이해할 수 있습니다."),
        "golden_cross_reason": ColumnMeta("골든크로스 신호 이유", "왜 해당 신호가 나왔는지 설명한 문장입니다.", "숫자만 보지 않고 판단 근거를 함께 볼 수 있습니다."),
        "trend_state": ColumnMeta("추세 상태", "가격과 이동평균을 기준으로 분류한 추세 상태입니다.", "상승 우세인지 하락 우세인지 큰 방향을 파악할 수 있습니다."),
        "rsi_state": ColumnMeta("RSI 상태", "RSI 값을 해석한 상태값입니다.", "과열, 과매도, 강한 흐름 같은 상태를 쉽게 읽을 수 있습니다."),
        "volume_state": ColumnMeta("거래량 상태", "오늘 거래량이 최근 평균과 비교해 어떤 상태인지 보여줍니다.", "신호에 힘이 실리는지 참고할 수 있습니다."),
        "investor_flow": ColumnMeta("수급 상태", "외국인과 기관 순매수 흐름을 요약한 값입니다.", "수급이 우호적인지 약한지 빠르게 볼 수 있습니다."),
        "foreign_net": ColumnMeta("외국인 순매수", "외국인이 순수하게 얼마나 샀는지 보여줍니다.", "외국인 자금 방향을 정량적으로 볼 수 있습니다."),
        "institutional_net": ColumnMeta("기관 순매수", "기관이 순수하게 얼마나 샀는지 보여줍니다.", "기관 자금 유입 여부를 확인할 수 있습니다."),
        "personal_net": ColumnMeta("개인 순매수", "개인이 순수하게 얼마나 샀는지 보여줍니다.", "개인 투자자 흐름을 비교할 수 있습니다."),
        "summary": ColumnMeta("한 줄 요약", "현재 장 상황을 사람이 읽기 쉬운 문장으로 정리한 내용입니다.", "숫자에 익숙하지 않아도 상황을 바로 이해할 수 있습니다."),
        "final_opinion": ColumnMeta("최종 판단", "현재 데이터 기준으로 정리한 최종 의견입니다.", "매수, 매도, 관망 중 어떤 해석이 적절한지 바로 볼 수 있습니다."),
        "rsi_strategy_signal": ColumnMeta("RSI 전략 판단", "RSI 전략이 낸 직접 신호입니다.", "과매수·과매도 기준에서 전략이 매수, 매도, 관망 중 무엇으로 해석했는지 보여줍니다."),
        "rsi_strategy_reason": ColumnMeta("RSI 전략 이유", "RSI 전략이 왜 그런 판단을 했는지 설명한 문장입니다.", "RSI 값과 임계값 비교 근거를 함께 읽을 수 있습니다."),
        "trend_filter_signal": ColumnMeta("추세 필터 전략 판단", "추세 필터 전략이 낸 직접 신호입니다.", "종가, 장기 이동평균, 직전 종가 비교 기준에서 현재 방향을 볼 수 있습니다."),
        "trend_filter_reason": ColumnMeta("추세 필터 전략 이유", "추세 필터 전략의 판단 근거입니다.", "close, ma_60, prev_close 비교 결과를 설명합니다."),
        "mean_reversion_signal": ColumnMeta("평균회귀 전략 판단", "평균회귀 전략이 낸 직접 신호입니다.", "현재 가격이 기준 이동평균에서 얼마나 벗어났는지 바탕으로 판단합니다."),
        "mean_reversion_reason": ColumnMeta("평균회귀 전략 이유", "평균회귀 전략의 판단 근거입니다.", "가격과 ma_20 비율이 밴드 안인지 밖인지 설명합니다."),
    }

    STATE_LABELS = {
        "buy": "매수 관점",
        "sell": "매도 관점",
        "hold": "관망",
        "watch": "관심 관찰",
        "bullish": "상승 우세",
        "bearish": "하락 우세",
        "neutral": "중립",
        "unknown": "정보 부족",
        "overbought": "과열 가능성",
        "oversold": "과매도 가능성",
        "strong": "강한 흐름",
        "weak": "약한 흐름",
        "active": "거래 활발",
        "normal": "거래 보통",
        "quiet": "거래 한산",
        "supportive": "수급 우호적",
        "mixed": "수급 혼조",
    }

    def __init__(
        self,
        raw_root: str | Path | None = None,
        processed_root: str | Path | None = None,
        test_report_path: str | Path = "data/processed/test_reports/pytest_results.xml",
        dataset_storage=None,
        settings: AppSettings | None = None,
    ) -> None:
        self.dataset_storage = dataset_storage
        self._default_db_storage = self.dataset_storage is None and raw_root is None and processed_root is None
        self._settings = settings
        self.raw_root = Path(raw_root) if raw_root is not None else Path("data/raw/domestic_stock")
        self.processed_root = Path(processed_root) if processed_root is not None else Path("data/processed/domestic_stock")
        self.test_report_path = Path(test_report_path)

    def build_snapshot(self) -> DashboardSnapshot:
        if self.get_dataset_storage() is not None:
            return DashboardSnapshot(
                raw_previews=self._collect_db_previews(self.RAW_DATASETS),
                processed_previews=self._collect_db_previews(self.PROCESSED_DATASETS),
            )
        return DashboardSnapshot(
            raw_previews=self._collect_previews(self.raw_root),
            processed_previews=self._collect_previews(self.processed_root),
        )

    def load_preview_frame(self, preview: DatasetPreview) -> pd.DataFrame:
        storage = self.get_dataset_storage()
        if storage is None:
            try:
                return pd.read_csv(preview.path)
            except pd.errors.EmptyDataError:
                return pd.DataFrame()
        try:
            return storage.load(preview.name, preview.path.name)
        except FileNotFoundError:
            return pd.DataFrame()

    def get_dataset_storage(self):
        if self.dataset_storage is None and self._default_db_storage:
            self.dataset_storage = DbFrameStorage.from_settings(self._settings)
        return self.dataset_storage

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

        command_file = self.test_report_path.parent / "pytest_command.txt"
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
            csv_files = sorted(dataset_dir.glob("*.csv"), key=lambda path: path.stat().st_mtime, reverse=True)
            if not csv_files:
                continue

            latest_file = csv_files[0]
            try:
                frame = pd.read_csv(latest_file)
            except pd.errors.EmptyDataError:
                frame = pd.DataFrame()

            symbol = self._extract_symbol(latest_file)
            symbol_name = symbol_name_map.get(symbol, "")
            enriched = self._enrich_frame(frame, symbol=symbol, symbol_name=symbol_name)
            guide = self.DATASET_GUIDES.get(
                dataset_dir.name,
                DatasetGuide(
                    title=dataset_dir.name,
                    summary="아직 이 데이터셋 설명이 준비되지 않았습니다.",
                    purpose="파일 구조와 컬럼을 먼저 확인해 주세요.",
                    first_look="종목명, 날짜, 가격 관련 컬럼부터 보면 이해가 쉬워집니다.",
                    recommended_columns=tuple(enriched.columns[: min(6, len(enriched.columns))]),
                ),
            )
            recommended = [column for column in guide.recommended_columns if column in enriched.columns]
            if not recommended:
                recommended = list(enriched.columns[: min(6, len(enriched.columns))])
            if "symbol_name" in enriched.columns and "symbol_name" not in recommended:
                recommended.insert(0, "symbol_name")
            if "symbol" in enriched.columns and "symbol" not in recommended:
                recommended.insert(1 if "symbol_name" in recommended else 0, "symbol")

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
                )
            )

        return previews

    def _collect_db_previews(self, datasets: tuple[str, ...]) -> list[DatasetPreview]:
        previews: list[DatasetPreview] = []
        storage = self.get_dataset_storage()
        if storage is None:
            return previews

        symbol_name_map = self._load_symbol_name_map()
        for dataset in datasets:
            latest_records = self._list_latest_records(dataset)
            for filename in latest_records:
                frame = storage.load(dataset, filename)
                symbol = self._extract_symbol(Path(filename))
                symbol_name = symbol_name_map.get(symbol, "")
                enriched = self._enrich_frame(frame, symbol=symbol, symbol_name=symbol_name)
                guide = self.DATASET_GUIDES.get(
                    dataset,
                    DatasetGuide(
                        title=dataset,
                        summary="아직 이 데이터셋 설명이 준비되지 않았습니다.",
                        purpose="데이터 구조를 먼저 확인해 주세요.",
                        first_look="종목, 날짜, 핵심 지표 컬럼을 먼저 보세요.",
                        recommended_columns=tuple(enriched.columns[: min(6, len(enriched.columns))]),
                    ),
                )
                recommended = [column for column in guide.recommended_columns if column in enriched.columns]
                if not recommended:
                    recommended = list(enriched.columns[: min(6, len(enriched.columns))])
                if "symbol_name" in enriched.columns and "symbol_name" not in recommended:
                    recommended.insert(0, "symbol_name")
                if "symbol" in enriched.columns and "symbol" not in recommended:
                    recommended.insert(1 if "symbol_name" in recommended else 0, "symbol")
                previews.append(
                    DatasetPreview(
                        name=dataset,
                        display_name=guide.title,
                        path=storage.root_dir / dataset / filename,
                        row_count=len(enriched),
                        columns=list(enriched.columns),
                        summary=guide.summary,
                        purpose=guide.purpose,
                        first_look=guide.first_look,
                        symbol=symbol,
                        symbol_name=symbol_name,
                        recommended_columns=recommended,
                    )
                )
        return previews

    @staticmethod
    def _extract_symbol(file_path: Path) -> str:
        stem = file_path.stem
        symbol = stem.split("_")[0] if "_" in stem else stem
        return DashboardDataService._normalize_symbol(symbol)

    def _load_symbol_name_map(self) -> dict[str, str]:
        mapping = self._load_symbol_name_map_from_db()
        if mapping:
            return mapping

        mapping = self._load_symbol_name_map_from_master()
        if mapping:
            return mapping

        return self._load_symbol_name_map_from_stock_info()

    def _load_symbol_name_map_from_db(self) -> dict[str, str]:
        storage = self.get_dataset_storage()
        database_url = getattr(storage, "database_url", "").strip() if storage is not None else ""
        if not database_url:
            return {}
        try:
            engine = build_engine(database_url)
            try:
                session_factory = build_session_factory(engine)
                repository = SqlAlchemyStockRepository(session_factory)
                return {
                    self._normalize_symbol(record.symbol): record.symbol_name.strip()
                    for record in repository.list_all()
                    if self._normalize_symbol(record.symbol) and record.symbol_name.strip()
                }
            finally:
                engine.dispose()
        except Exception:
            return {}

    def _load_symbol_name_map_from_master(self) -> dict[str, str]:
        try:
            repository = StockMasterRepository()
            return {
                self._normalize_symbol(entry.get("symbol", "")): str(entry.get("symbol_name", "")).strip()
                for entry in repository.load_entries()
                if self._normalize_symbol(entry.get("symbol", "")) and str(entry.get("symbol_name", "")).strip()
            }
        except Exception:
            return {}

    def _load_symbol_name_map_from_stock_info(self) -> dict[str, str]:
        storage = self.get_dataset_storage()
        if storage is not None:
            mapping: dict[str, str] = {}
            previews = self._list_latest_records("stock_info")
            for item in previews:
                frame = storage.load("stock_info", item)
                if frame.empty:
                    continue
                code = str(frame.iloc[0].get("pdno", "")).strip() or Path(item).stem
                code = self._normalize_symbol(code)
                name = str(frame.iloc[0].get("prdt_abrv_name", "")).strip()
                if code and self._is_meaningful_symbol_name(code, name):
                    mapping[code] = name
            return mapping

        stock_info_dir = self.raw_root / "stock_info"
        if not stock_info_dir.exists():
            return {}

        mapping: dict[str, str] = {}
        for csv_file in sorted(stock_info_dir.glob("*.csv")):
            try:
                frame = pd.read_csv(csv_file)
            except pd.errors.EmptyDataError:
                continue
            if frame.empty:
                continue
            code = str(frame.iloc[0].get("pdno", "")).strip() or csv_file.stem
            code = self._normalize_symbol(code)
            name = str(frame.iloc[0].get("prdt_abrv_name", "")).strip()
            if code and self._is_meaningful_symbol_name(code, name):
                mapping[code] = name
        return mapping

    def _list_latest_records(self, dataset: str) -> list[str]:
        storage = self.get_dataset_storage()
        if storage is None:
            return []
        entries = storage.repository.list_latest([dataset])
        return [entry.filename for entry in entries if entry.dataset == dataset]

    @staticmethod
    def _normalize_symbol(value: object) -> str:
        text = str(value).strip()
        if not text:
            return ""
        if text.endswith(".0"):
            text = text[:-2]
        if text.isdigit():
            return text.zfill(6)
        return text

    @classmethod
    def _is_meaningful_symbol_name(cls, symbol: str, name: str) -> bool:
        cleaned = str(name).strip()
        return bool(cleaned) and cls._normalize_symbol(cleaned) != cls._normalize_symbol(symbol)

    @staticmethod
    def _enrich_frame(frame: pd.DataFrame, symbol: str, symbol_name: str) -> pd.DataFrame:
        enriched = frame.copy()
        if symbol and "symbol" not in enriched.columns:
            enriched.insert(0, "symbol", symbol)
        if symbol_name and "symbol_name" not in enriched.columns:
            enriched.insert(1 if "symbol" in enriched.columns else 0, "symbol_name", symbol_name)

        rename_map = {
            "stck_bsop_date": "date",
            "stck_oprc": "open",
            "stck_hgpr": "high",
            "stck_lwpr": "low",
            "stck_clpr": "close",
            "acml_vol": "volume",
            "acml_tr_pbmn": "turnover",
        }
        rename_targets = {
            old: new for old, new in rename_map.items() if old in enriched.columns and new not in enriched.columns
        }
        if rename_targets:
            enriched = enriched.rename(columns=rename_targets)
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
