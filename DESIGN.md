# Design

## Source of truth
- Status: Active
- Last refreshed: 2026-08-22
- Primary product surfaces:
  - Streamlit 국내주식 운영 대시보드
  - 홈, 데이터 갱신, 투자 리포트, 관심종목, 백테스트, 데이터 보기, 용어 해설, 시스템 검증
- Evidence reviewed:
  - `src/invest_bot/dashboard/streamlit_dashboard.py`
  - `src/invest_bot/dashboard/streamlit_layout.py`
  - `src/invest_bot/dashboard/streamlit_overview.py`
  - TradingView watchlist help: 관심자산 한 곳 추적, 뉴스/펀더멘털/기술요약 진입점
  - Seeking Alpha earnings help: 종목 검색/포트폴리오에서 시작해 실적 요약·추정·리비전·서프라이즈 탐색
  - 네이버페이 App Store 설명: 관심주식 가격 변동, 공시, 리서치 알림, 시장 흐름, 매매 동향 강조
  - `src/invest_bot/dashboard/streamlit_styles.py`
  - `src/invest_bot/dashboard/streamlit_reports.py`
  - `src/invest_bot/dashboard/streamlit_watchlist.py`
  - `src/invest_bot/dashboard/streamlit_backtest.py`
  - `docs/tasks/04_dashboard.md`
  - `README.md`

## Brand
- Personality: 차분한 투자 연구 도구, 명확한 운영 콘솔, 초보자도 길을 잃지 않는 안내형 화면.
- Trust signals: 최신 기준일, 데이터 상태, 테스트 상태, 실행 결과, 근거 문장을 항상 보이게 한다.
- Avoid: 과도한 장식, 전문용어만 있는 화면, 작은 표에 긴 텍스트를 욱여넣는 구성, 실행 버튼이 맥락 없이 노출되는 구성.

## Product goals
- Goals:
  - 사용자가 “지금 무엇을 봐야 하는지”와 “다음에 무엇을 실행해야 하는지”를 5초 안에 이해한다.
  - 데이터 갱신, 투자 리포트, 백테스트, 원본 데이터 확인을 하나의 흐름으로 연결한다.
  - 초보 사용자를 위해 용어 해설과 판단 근거를 UI 안에서 제공한다.
- Non-goals:
  - 실거래 주문 UX 구현.
  - 신규 데이터 수집 API 추가.
  - 새로운 프론트엔드 프레임워크 도입.
- Success signals:
  - 좌측 메뉴만 보고도 기능 차이를 이해할 수 있다.
  - 홈 화면에서 상태, 추천 흐름, 최신 리포트/신호를 빠르게 파악한다.
  - 각 실행 화면의 위험/결과/다음 행동이 명확하다.

## Personas and jobs
- Primary personas:
  - 개인 투자 연구자: 여러 국내 종목의 데이터와 전략 판단을 반복 확인한다.
  - 초보 사용자: 용어와 전략 의미를 확인하며 리포트를 읽고 싶다.
  - 운영자: 수집/분석/리포트/테스트 상태를 확인하고 필요한 작업을 실행한다.
- User jobs:
  - 오늘 데이터가 최신인지 확인한다.
  - 종목별 리포트와 전략 판단을 읽는다.
  - 전략이 과거에 어떻게 동작했는지 백테스트한다.
  - 원본/가공 데이터를 확인한다.
- Key contexts of use:
  - 데스크톱 브라우저의 Streamlit 앱.
  - 로컬 개발/운영 환경.
  - 한국어 UI.

## Information architecture
- Primary navigation:
  - 홈: 오늘의 투자 브리핑, 우선 확인 종목, 다음 행동, 상태와 추천 흐름.
  - 데이터 갱신: 수집, 지표, 신호, 리포트 생성.
  - 투자 리포트: 종목별 후보 카드, 선택 리포트, 판단 근거와 차트.
  - 관심종목: 리포트 생성 여부와 무관하게 저장한 종목 전체를 카드 보드로 확인하고 선택 리포트를 재확인.
  - 백테스트: 종목/전략 선택, 준비 상태 카드, 결과 카드 중심 전략 성과 검증.
  - 데이터 보기: 원본/가공 데이터 탐색.
  - 용어 해설: 리포트·전략·지표 용어 설명.
  - 시스템 검증: 테스트 결과 확인.
- Core routes/screens:
  - `streamlit_dashboard.py`가 탭 라우팅을 담당한다.
  - 각 탭은 `streamlit_*` 모듈로 분리되어 있다.
- Content hierarchy:
  - 홈은 종목/판단/신호를 먼저 보여주고 운영 상태는 보조 정보로 둔다.
  - 투자 리포트, 관심종목, 백테스트도 상단에서 후보/선택/준비/결과를 카드로 먼저 요약한다.
  - 화면 제목과 “무엇을 하는 화면인지”를 먼저 보여준다.
  - 다음 행동, 핵심 지표, 상세 데이터 순서로 내려간다.

## Design principles
- Principle 1: 메뉴는 기능명이 아니라 사용자 행동을 말한다.
- Principle 2: 홈 본문은 주식 앱처럼 종목 중심 브리핑, 관심 후보, 다음 행동을 먼저 보여준다.
- Principle 3: 표보다 카드와 요약을 먼저 보여주고, 상세 표는 필요할 때만 펼친다.
- Principle 4: 실행 화면은 기본값과 영향 범위를 명확히 말한다.
- Principle 5: 백테스트 결과는 숫자만 표시하지 않고 수익률, 표본 수, 승률, 평균수익, 최대낙폭을 함께 해석한다.
- Principle 6: 후보 카드에서 확인 대상을 발견하면 별도 selectbox 재탐색 없이 바로 선택할 수 있어야 한다.
- Principle 7: 관심종목은 드롭다운을 열지 않아도 등록한 전체 종목과 최신 판단을 먼저 파악할 수 있어야 한다.
- Principle 8: 관심종목은 조회 화면으로 유지하고, 종목별 가격·수급·분석·신호·리포트 기준일과 갱신 필요 사유를 먼저 보여준다.
- Tradeoffs:
  - Streamlit 기본 위젯을 유지해 구현 안정성을 우선한다.
  - 완전한 커스텀 SPA보다는 repo-native CSS/컴포넌트 확장으로 개선한다.

## Visual language
- Color: 기존 high-contrast dark navy/slate palette를 유지한다.
- Typography: 한국어 본문은 Pretendard 계열을 우선하고, 가격·비율·날짜·지표는 tabular 숫자 정렬을 적용해 빠른 비교를 돕는다. 보조 라벨은 데스크톱 기준 최소 0.8rem을 유지한다.
- Spacing/layout rhythm: 1rem 안팎의 카드 간격, 넓은 터치/클릭 영역.
- Shape/radius/elevation: 정보 카드에는 부드러운 radius, 좌측 메뉴는 텍스트형 내비게이션.
- Motion: hover/focus 정도의 미세한 전환만 사용.
- Imagery/iconography: 아이콘 폰트 의존을 줄이고 텍스트 중심으로 명확히 표현한다.

## Components
- Existing components to reuse:
  - `render_sidebar`, `render_header`, `render_action_feedback`
  - `summary-box`, `streamlit-card`, `badge`, interpretation cards
  - Streamlit `st.date_input`, `st.toggle`, `st.container`, `st.metric`
- New/changed components:
  - 사용자 여정 중심 tab metadata.
  - 동적 화면 헤더.
  - 홈 화면의 퀵스타트 카드.
  - 오늘의 투자 브리핑 카드.
  - 홈 데이터 신뢰 상태(리포트·신호 기준일, 데이터 상태, 시스템 검증 결과)와 갱신 안내.
  - 오늘 볼 만한 종목 카드.
  - 화면 이동 버튼이 연결된 다음 행동 카드.
  - 리포트 후보 카드와 선택 리포트 focus card.
  - 후보 수·한글 요약·날짜를 포함한 리포트 후보 카드와 최종 의견/전략 신호 충돌 경고.
  - 종합 신호, 전략 합의도, 핵심 지표·수급 충족 상태, 상승 근거·위험 요인·재평가 기준을 함께 표시하는 리포트 판단 요약.
  - 후보 카드의 직접 선택 버튼.
  - 선택 상세 영역 스크롤 anchor.
  - 작업 실행 중 status/progress 표시.
  - Streamlit 위젯을 포함하는 카드에는 `st.container(border=True)`를 사용하고, 커스텀 HTML 카드는 한 번의 markdown 호출 안에서 완결한다.
  - 전체 등록 종목을 노출하는 관심종목 카드 보드와 카드별 상세 보기 버튼.
  - 백테스트 flow, selection, readiness, result cards.
  - 백테스트 결과 해석 문장.
- Variants and states:
  - selected navigation: 왼쪽 강조선 + 밝은 텍스트.
  - empty/error/success: Streamlit status primitives 사용.
- Token/component ownership:
  - CSS token은 `streamlit_styles.py` 소유.
  - 라우팅/화면 메타는 `streamlit_layout.py` 소유.

## Accessibility
- Target standard: WCAG 2.1 AA 수준의 대비와 키보드 접근성을 지향한다.
- Keyboard/focus behavior: Streamlit 버튼·탭·입력 위젯에 명확한 `:focus-visible` 윤곽선을 제공하고, 키보드만으로 다음 행동과 리포트 선택을 완료할 수 있어야 한다.
- Contrast/readability: dark background에서 본문과 muted text 대비를 충분히 유지한다.
- Screen-reader semantics: 제목 계층과 버튼 라벨은 기능을 설명해야 한다.
- Reduced motion and sensory considerations: 과도한 애니메이션 없음.

## Responsive behavior
- Supported breakpoints/devices: 데스크톱 우선, 좁은 화면에서는 Streamlit column stacking을 수용한다.
- Layout adaptations: 카드 grid는 가능한 경우 자동 줄바꿈한다.
- Touch/hover differences: hover에 의존하지 않고 selected state를 항상 표시한다.

## Interaction states
- Loading: 데이터 갱신처럼 시간이 걸리는 작업은 Streamlit status로 대상과 진행 내용을 표시한다. 홈과 관심종목은 저장된 snapshot만 읽고, 최신화는 사용자가 `데이터 갱신`에서 명시적으로 실행한다.
- Empty: 데이터 없음 메시지는 다음 행동을 제안한다.
- Error: 실패 이유와 영향 범위를 말하되, 외부 API 오류나 내부 아이콘 이름 같은 기술 텍스트를 홈 본문에 그대로 노출하지 않는다.
- Success: 무엇이 완료됐는지와 다음 확인 화면을 제안한다.
- Disabled: 명확한 차단 사유를 제공한다.
- Offline/slow network: 외부 API/DB 실패는 오류 메시지와 재시도 맥락을 제공한다.

## Content voice
- Tone: 짧고 명확한 한국어, 투자 판단은 단정하지 않음.
- Terminology: 어려운 용어는 `용어 해설`과 연결되는 표현을 사용한다.
- Microcopy rules:
  - “무엇을 한다”, “왜 필요한가”, “다음에 볼 것”을 분리한다.
  - `매수 관점`/`매도 관점`은 종합 신호로 표기하고, 전략 합의도·기준일·데이터 충족 상태·위험 요인을 같은 화면에서 함께 제공한다.
  - 수익 가능성을 암시하는 신뢰도 대신 확인 가능한 데이터 충족 상태와 전략 신호 수를 사용한다.
  - 화살표/아이콘 문자가 깨질 수 있는 표현을 피한다.
  - Streamlit이 `stIconMaterial`에 아이콘 이름을 ligature text로 넣는 구조를 고려해, 전역 `span`/폰트 CSS를 수정할 때는 반드시 `[data-testid="stIconMaterial"]`의 Material Symbols 폰트와 `liga` 설정을 다시 보장한다.
  - status, expander, sidebar 등 Streamlit 기본 아이콘을 사용하는 UI를 추가하거나 수정하면 아이콘 이름(`keyboard_arrow_down`, `expand_more` 등)이 화면 텍스트로 노출되지 않는지 CSS 회귀 테스트를 함께 유지한다.

## Implementation constraints
- Framework/styling system: Streamlit + repo-local CSS.
- Design-token constraints: 기존 CSS 변수 유지.
- Markup constraints: 서로 다른 `st.markdown()` 호출 사이에서 HTML wrapper를 열고 닫지 않는다. 빈 카드·깨진 grid가 보이면 먼저 이 규칙을 확인한다.
- Performance constraints: 홈과 관심종목은 저장된 데이터만 조회해 빠르게 렌더링한다. 수집·분석은 `데이터 갱신`에서 대상 종목과 실행 범위를 사용자가 확인한 뒤 수행한다.
- Compatibility constraints: 기존 tests와 탭 라우팅 alias를 유지한다.
- Test/screenshot expectations: 변경 후 `pytest` 전체 통과를 기준으로 한다.

## Open questions
- [ ] 실제 사용자 기준의 선호 메뉴명 확정 / owner: user / impact: navigation copy.
- [ ] 모바일 화면까지 적극 지원할지 여부 / owner: user / impact: layout scope.
- [ ] 시각 레퍼런스 또는 브랜드 참고 이미지 유무 / owner: user / impact: visual redesign depth.
