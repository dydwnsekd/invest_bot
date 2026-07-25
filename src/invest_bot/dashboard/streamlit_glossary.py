from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import streamlit as st

from invest_bot.dashboard.service import DashboardDataService

GLOSSARY_CATEGORY_KEY = "glossary_category"


@dataclass(frozen=True, slots=True)
class GlossaryTerm:
    term: str
    category: str
    meaning: str
    how_to_read: str


CORE_TERMS: tuple[GlossaryTerm, ...] = (
    GlossaryTerm("최종 의견", "리포트", "여러 지표와 전략 신호를 종합한 현재 리포트의 결론입니다.", "매수 관점은 긍정, 매도 관점은 부정, 관망은 추가 확인이 필요한 상태로 읽습니다."),
    GlossaryTerm("매수 관점", "리포트", "현재 데이터 기준으로 상승 또는 반등 가능성을 더 우호적으로 보는 해석입니다.", "바로 매수하라는 뜻이 아니라, 차트·수급·리스크를 추가 확인할 후보라는 뜻입니다."),
    GlossaryTerm("매도 관점", "리포트", "현재 데이터 기준으로 하락 또는 약세 위험을 더 크게 보는 해석입니다.", "보유 중이면 손절·비중 축소·추세 회복 여부를 우선 점검하는 신호로 봅니다."),
    GlossaryTerm("관망", "리포트", "매수와 매도 어느 쪽으로도 충분히 기울지 않은 중립 판단입니다.", "새 진입보다는 다음 신호, 거래량, 수급 변화가 확인될 때까지 기다리는 상태입니다."),
    GlossaryTerm("관심 관찰", "리포트", "아직 확정 신호는 약하지만 추적할 가치가 있는 상태입니다.", "관심종목에 넣고 다음 리포트에서 신호가 강화되는지 보는 용도입니다."),
    GlossaryTerm("골든크로스", "전략", "짧은 이동평균선이 긴 이동평균선을 아래에서 위로 돌파하는 현상입니다.", "이 앱에서는 주로 5일선과 20일선 교차를 단기 상승 전환 후보로 해석합니다."),
    GlossaryTerm("데드크로스", "전략", "짧은 이동평균선이 긴 이동평균선을 위에서 아래로 이탈하는 현상입니다.", "단기 흐름이 약해졌다는 경고로 보고, 다른 지표와 함께 확인합니다."),
    GlossaryTerm("RSI", "지표", "최근 상승과 하락의 강도를 0~100 범위로 나타내는 모멘텀 지표입니다.", "보통 낮으면 과매도, 높으면 과열 가능성을 참고하지만 추세장에서는 보조 지표로 봅니다."),
    GlossaryTerm("이동평균선", "지표", "일정 기간 종가 평균을 선으로 연결해 가격 흐름을 부드럽게 보여주는 지표입니다.", "5일선은 단기, 20일선은 한 달 안팎, 60일선은 중기 흐름을 보는 기준으로 사용합니다."),
    GlossaryTerm("추세 필터", "전략", "가격이 장기 기준선 위인지 아래인지로 큰 방향을 거르는 전략입니다.", "상승장 후보와 약세 구간을 구분해 다른 신호의 신뢰도를 보정하는 데 사용합니다."),
    GlossaryTerm("평균회귀", "전략", "가격이 평균에서 과도하게 벗어나면 다시 평균 근처로 돌아올 수 있다고 보는 전략입니다.", "급락 후 반등 후보나 단기 과열 후 조정 가능성을 확인하는 보조 전략입니다."),
    GlossaryTerm("수급", "데이터", "개인, 외국인, 기관 등 투자자별 매수·매도 흐름입니다.", "외국인·기관 순매수가 함께 강하면 우호적, 주체별 방향이 갈리면 혼조로 해석합니다."),
    GlossaryTerm("거래량", "데이터", "해당 기간 실제로 거래된 주식 수량입니다.", "가격 상승과 거래량 증가가 함께 나오면 움직임의 힘이 강하다고 볼 수 있습니다."),
)


def render_glossary_tab(service: DashboardDataService) -> None:
    st.markdown('<h3 class="section-title">용어 해설</h3>', unsafe_allow_html=True)
    st.markdown(
        '<div class="section-copy">리포트와 전략 화면에 나오는 주식·지표·전략 용어를 한곳에서 쉬운 말로 확인합니다.</div>',
        unsafe_allow_html=True,
    )

    terms = build_glossary_terms(service)
    query = st.text_input(
        "용어 검색",
        placeholder="예: RSI, 골든크로스, 수급, 최종 의견",
        key="glossary_query",
    ).strip().lower()
    categories = ["전체", *sorted({term.category for term in terms})]
    category = st.selectbox("분류", options=categories, key=GLOSSARY_CATEGORY_KEY)
    filtered = filter_glossary_terms(terms, query=query, category=category)

    metric_columns = st.columns(3)
    metric_columns[0].metric("전체 용어", len(terms))
    metric_columns[1].metric("표시 용어", len(filtered))
    metric_columns[2].metric("분류", category)

    if not filtered:
        st.warning("현재 검색 조건에 맞는 용어가 없습니다.")
        return

    st.dataframe(glossary_terms_to_frame(filtered), width="stretch", hide_index=True)

    st.markdown(
        """
        <div class="summary-box glossary-guide-box">
          <div class="muted-label">처음 볼 때 추천 순서</div>
          <ol>
            <li><strong>최종 의견</strong>으로 전체 결론을 먼저 봅니다.</li>
            <li><strong>골든크로스, RSI, 추세 필터, 평균회귀</strong>로 전략별 판단 이유를 확인합니다.</li>
            <li><strong>수급, 거래량, 이동평균선</strong>으로 신호에 힘이 실렸는지 보조 확인합니다.</li>
          </ol>
        </div>
        """,
        unsafe_allow_html=True,
    )


def build_glossary_terms(service: DashboardDataService) -> list[GlossaryTerm]:
    terms = list(CORE_TERMS)
    existing = {term.term for term in terms}
    for column, meta in service.COLUMN_META.items():
        if meta.label in existing:
            continue
        category = column_category(column)
        terms.append(
            GlossaryTerm(
                term=meta.label,
                category=category,
                meaning=meta.description,
                how_to_read=meta.why,
            )
        )
        existing.add(meta.label)
    return sorted(terms, key=lambda term: (term.category, term.term))


def column_category(column: str) -> str:
    if "strategy" in column or column in {"signal", "signal_reason", "golden_cross_signal", "golden_cross_reason"}:
        return "전략"
    if column in {"ma_5", "ma_20", "ma_60", "rsi_14", "trend_state", "rsi_state", "volume_state"}:
        return "지표"
    if column in {"foreign_net", "institutional_net", "personal_net", "frgn_ntby_qty", "orgn_ntby_qty", "prsn_ntby_qty", "investor_flow"}:
        return "수급"
    if column in {"close", "open", "high", "low", "volume", "turnover", "date", "start_date", "end_date", "row_count"}:
        return "데이터"
    if column in {"summary", "final_opinion"}:
        return "리포트"
    return "기본 정보"


def filter_glossary_terms(terms: list[GlossaryTerm], *, query: str = "", category: str = "전체") -> list[GlossaryTerm]:
    filtered = terms
    if category != "전체":
        filtered = [term for term in filtered if term.category == category]
    if query:
        filtered = [
            term
            for term in filtered
            if query in term.term.lower()
            or query in term.category.lower()
            or query in term.meaning.lower()
            or query in term.how_to_read.lower()
        ]
    return filtered


def glossary_terms_to_frame(terms: list[GlossaryTerm]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "용어": term.term,
                "분류": term.category,
                "뜻": term.meaning,
                "읽는 법": term.how_to_read,
            }
            for term in terms
        ]
    )
