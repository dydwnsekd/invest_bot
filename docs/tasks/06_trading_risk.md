# Task 06. Trading And Risk

> OKF ID: `D-TRADING` · 종류: `status` · 상태: `active` · 관리: 통합, 퀀트 구현·QA 검증
> 현재 기준은 2026-11-24 main `76a8223`과 모의 계좌 조회 점검 작업본이다.

## 모의 계좌 읽기 전용 점검

토큰 발급과 주문 실행을 분리한 [모의 계좌 점검 명령](../../scripts/check_kis_mock_account.py)이다. 호출자가 이미 보유한 모의 토큰으로 주식 잔고 첫 페이지를 조회한다. 응답이 맞으면 서울 시간 기준 당일 현금 주문·체결 내역의 첫 페이지를 확인한다. 두 조회가 성공하면 `balance=ok orders=ok`를 출력한다. 당일 주문이 없는 빈 목록도 유효한 응답이다.

기존 모의 전송 검사를 공유하며 모의 서버로 최대 두 번의 GET을 보낸다. 조회가 실패하면 재시도하지 않는다. 출력은 검사 상태와 누락된 설정 이름이며, 실제 계좌·잔고·주문 내역·토큰 원문은 출력하지 않는다. 이 결과의 범위는 연결과 응답 형식 확인이다. 주문 승인에 필요한 가용 잔고와 전체 체결 내역의 검증은 별도다. [KIS 주식 잔고조회 예제](https://github.com/koreainvestment/open-trading-api/blob/main/examples_llm/domestic_stock/inquire_balance/inquire_balance.py)

개인 실행 환경에 아래 값이 설정돼 있어야 한다. 만료시각은 시간대가 포함된 ISO 8601 형식이다.

- `INVEST_BOT_KIS_MOCK_ACCOUNT_NUMBER`
- `INVEST_BOT_KIS_MOCK_APP_KEY`
- `INVEST_BOT_KIS_MOCK_APP_SECRET`
- `INVEST_BOT_KIS_MOCK_ACCESS_TOKEN`
- `INVEST_BOT_KIS_MOCK_TOKEN_EXPIRES_AT`

```sh
python scripts/check_kis_mock_account.py
```

종료 코드 0은 두 조회 성공, 1은 조회 실패 또는 건너뜀, 2는 입력 누락·오류다. 입력이 빠진 환경에서는 외부 호출 전에 종료한다.

2026-11-24에 [새 테스트 13개](../../tests/test_kis_mock_account_check.py)를 먼저 실행해 기능이 없는 상태에서 실패를 확인했다. 구현 뒤 같은 테스트와 주문 회귀를 포함해 166개가 통과했다. 전체 기본 테스트는 2,363개 통과, 2개 선택 제외, 기존 경고 51개였다. 실제 모의 계좌 번호와 유효 토큰이 준비된 환경에서 읽기 전용 확인을 이어간다. 이후 테스트 주문은 계좌·종목·방향·수량·가격·미체결 처리 범위를 정해 별도 검증한다.

## T06d KIS 모의 주문과 체결 확인

한국투자증권 모의 계좌의 국내 현물 KRX 지정가 매수·매도와 주문·체결 확인을 구현했다. 운영 연결 전 검증은 가짜 전송 세션과 임시 SQLite에서 수행했다.

| 공개 진입점 | 역할 |
| --- | --- |
| [`KISMockCredentials`, `KISMockOrderClient`](../../src/invest_bot/clients/kis_order_client.py) | 모의 계좌·앱 키/시크릿·만료가 명시된 토큰·모의 URL·전송 세션을 받는다. 거래소 KRX와 종합계좌 상품 `01`을 사용한다. 토큰 발급이나 캐시 자동 사용 없이 지정한 토큰을 확인한다. |
| [`OrderStore.bootstrap/open(..., execution_target="kis_mock")`](../../src/invest_bot/trading/order_store.py) | 가상 실행(`dry_run`)과 파일 형식이 구분되는 단일 모의 계좌 원장을 연다. 기존 가상 원장 형식과 재조회는 유지한다. 계좌·상품·앱 키 범위는 비밀 키를 사용해 만든 식별자로 확인한다. |
| [`KISMockOrders(store, client, *, clock, kill_switch)`](../../src/invest_bot/trading/kis_mock_orders.py) | 원장과 어댑터의 계좌 바인딩이 맞을 때만 구성한다. `submit(intent, context=...)`는 리스크 검증·예약·선점을 기록한 후 주문을 한 번 보낸다. `refresh(order_id)`는 해당 원장에 저장된 주문 번호만 조회한다. `fill_receipts()`로 원장에 적용한 체결 증거를 읽는다. |

- **주문은 예약 저장 후 1회.** 저장을 마친 뒤 중지 스위치와 시각·자료의 유효성을 다시 검사한다. 이 검사에서 차단되면 송신 없이 예약을 해제하고 `SEND_SKIPPED`로 남긴다. 접수 결과는 주문일·지점·번호·시각으로 저장한다. 주문 접수와 체결은 개별 상태로 관리한다.
- **근거가 생길 때만 예약 갱신.** 타임아웃·비정상 HTTP 응답·누락된 식별자는 `UNKNOWN`으로 남는다. 주문 번호가 없는 경우 예약과 계좌 차단을 유지한다. 주문 번호가 있는 경우 완결된 조회의 유일한 일치 응답에서 부분/전량 체결·확정 취소·명시 전량 거절을 확인한다. 중복 관측을 반복 적용하지 않는다. 체결 뒤 새 주문은 체결을 반영한 잔고 자료와 원장 기준 시각·버전을 확인해야 한다.
- **명시 구성.** 사용자가 준 모의 토큰과 동기식 전송 세션만 사용한다. 일반 `requests.Session`은 재시도·별도 경로 설정·리디렉션·환경 프록시를 차단한 구성만 허용한다. 다른 주입 전송기는 요청당 1회 호출 준수와 민감정보 보호가 전제다. 가상 실행과 모의투자의 계좌 및 기록을 분리한다. 같은 모의 계좌의 참여자는 동일 원장을 사용한다. 주문 기능은 명시 Python 진입점에서 실행한다.

### KIS 공식 자료에서 확인한 계약 (2026-11-22)

| 항목 | 적용한 규격 | 근거 |
| --- | --- | --- |
| 대상 | 모의투자 HTTPS `openapivts.koreainvestment.com:29443`, 종합계좌 상품 `01`, 계좌 8자리. 모의 키·토큰과 계좌는 호출자가 명시 제공한다. | [KIS 모의 설정 예제](https://github.com/koreainvestment/open-trading-api/blob/main/kis_devlp.yaml), [개발자센터 인증 및 주문](https://apiportal.koreainvestment.com/apiservice) |
| 국내 현금 지정가 | `POST /uapi/domestic-stock/v1/trading/order-cash`, 매수 `VTTC0012U`, 매도 `VTTC0011U`, `ORD_DVSN=00`, 거래소 `KRX`. 수량·가격은 문자열이다. 응답의 주문번호·거래소 전달 조직·주문시각을 접수 식별에 사용한다. | [현금 주문 예제](https://github.com/koreainvestment/open-trading-api/blob/main/examples_llm/domestic_stock/order_cash/order_cash.py), [접수 응답 필드](https://github.com/koreainvestment/open-trading-api/blob/main/examples_llm/domestic_stock/order_cash/chk_order_cash.py) |
| 최근 주문·체결 조회 | `GET /uapi/domestic-stock/v1/trading/inquire-daily-ccld`, 모의 3개월 이내 `VTTC0081R`. 모의 페이지는 최대 15건이며, `M/F`와 연속 키를 받으면 `N`으로 다음 페이지를 요청한다. 날짜·종목·방향·주문번호·원 주문의 수량과 가격 및 누적 체결량/금액을 대조한다. | [일별 주문·체결 조회 예제](https://github.com/koreainvestment/open-trading-api/blob/main/examples_llm/domestic_stock/inquire_daily_ccld/inquire_daily_ccld.py), [체결 응답 필드](https://github.com/koreainvestment/open-trading-api/blob/main/examples_llm/domestic_stock/inquire_daily_ccld/chk_inquire_daily_ccld.py) |

공식 예제에는 모의 연속 조회 간격 0.5초가 쓰인다. 실제 호출 한도와 조회 반영 지연은 계좌 연결 검증에서 확인할 항목이다. 접수 번호 없는 타임아웃을 특정 주문에 연결하거나, 빈 조회만으로 미접수를 확정할 근거는 확인하지 못했다. 조회 응답도 주문 식별·수량·금액이 모두 맞는 경우에만 원장에 반영한다. 실측할 항목에는 지점 필드 일치, 응답의 숫자 표현과 페이지 완결성, 잔고에 체결이 반영되는 시점이 포함된다. [KIS 공통 조회 예제](https://github.com/koreainvestment/open-trading-api/blob/main/examples_user/kis_auth.py)

### 검증과 실제 계좌 연결 범위

어댑터 계약 122개, 메인 원장 연결·전송 경계 21개, 독립 QA 8개를 검증했다. 기존 주문·화면 회귀를 포함한 관련 349개와 전체 기본 **2,350개**가 통과했다(2개 선택 제외, 기존 경고 51개, 112.92초). 이전 버전에서 생성한 가상 주문 DB를 별도 프로세스로 다시 열고 재제출 시 새 주문이 생성되지 않으며 파일이 그대로임을 확인했다. [어댑터 테스트](../../tests/test_t06d_kis_order_client.py) · [원장 연결 테스트](../../tests/test_t06d_kis_mock_orders.py) · [독립 QA](../../tests/test_t06d_independent_qa.py)

실제 모의 인증·토큰 발급·주문과 체결 응답은 별도 검증 단계다. 주문량과 호출 빈도, 시장·잔고 자료의 출처 및 체결 반영 시점을 그 단계에서 확인한다. 주문 결과가 불명이고 주문번호가 없는 경우는 현재도 확인 근거가 필요하다. 예약을 유지하고 자동 조회로 추정하거나 같은 주문을 다시 보내지 않는다.

## T06c 주문 원장과 결과 불명 복구

2026-11-21에 가상 주문의 **상태·예약·확인 근거를 전용 SQLite 원장에 남기는 작업**을 완료했다. 주문 전 검증은 T06b의 한도와 계산을 사용한다. 사용 화면과 정기 수집에서 주문이 시작되는 진입점은 추가하지 않았다.

| 공개 API | 동작 |
| --- | --- |
| [`OrderStore.bootstrap(path, *, book_id, bindings)`](../../src/invest_bot/trading/order_store.py) | 명시 경로에 새 원장과 `.sender-lock` 보조 파일을 만든다. 둘 다 초기 권한은 0600이고 기존 경로는 거절한다. |
| `OrderStore.open(path)`, `get(order_id)`, `orders()`, `book()` | 기존 원장과 잠금 파일을 확인한 뒤 불변 상태를 읽는다. 유실·손상·규격 불일치는 오류로 처리하고 자동으로 새 원장을 만들지 않는다. |
| [`OrderService.submit(intent, *, context, send)`](../../src/invest_bot/trading/order_service.py) | 명시 가상 계좌·정책·시장 자료와 동기식 가상 송신 함수를 받는다. 같은 요청은 저장 결과를 돌려주며, 같은 ID의 주문 내용이 바뀌면 충돌을 반환한다. |
| `OrderService.reconcile(evidence, *, stopped=None)` | 주문·계좌·출처·시각이 맞는 확정 근거로 상태를 갱신한다. 같은 근거의 재적용은 상태나 예약을 바꾸지 않는다. 송신 중 상태가 남았다면 별도의 종료 근거와 배타 잠금이 필요하다. |

유효한 신규 주문은 한 SQLite 트랜잭션에서 최신 원장의 현금·수량을 다시 검사한 뒤 **예약과 `SUBMITTING` 상태를 함께 커밋**한다. 저장 완료 뒤에만 가상 송신을 호출한다. 접수가 확인되면 `ACKNOWLEDGED`로 기록한다. 타임아웃이나 응답 불일치 시 `UNKNOWN`으로 남기고, 응답 기록 전에 중단되면 `SUBMITTING`이 남는다. 두 상태 모두 재시작 후 예약을 유지하고 같은 계좌의 신규 주문을 막는다. 같은 요청의 재제출이나 원장 열기로는 송신을 다시 호출하지 않는다.

조회 실패·시간 경과만으로 예약을 풀 수 없다. 확정된 거절·미접수·취소·만료는 남은 예약을 해제하며, 부분 체결 후에는 남은 주문분과 비용 상한을 유지한다. 체결이 있었다면 후속 잔고 자료에 해당 체결 근거 ID가 모두 포함되고 원장 버전과 관측 시각이 맞아야 새 주문을 승인할 수 있다. 접수·부분 체결·종료 상태와 함께 확인 출처와 이벤트를 저장한다. 원장에는 정규화한 주문·식별자·판정·예약과 상태 전이 기록만 사용한다.

검증 범위는 같은 로컬 POSIX 경로의 원장과 보조 파일을 사용하는 독립 프로세스와 동기식 가상 송신이다. 송신 종료 확인 잠금은 원장 단위라 다른 계좌가 송신 중이면 중단된 주문의 정리가 지연될 수 있다. 송신 근거와 정산 자료의 진위는 주입한 구성에 의존한다. DB와 보조 파일의 손상 검사는 일반적인 유실·편집을 발견하며, 백업 복원·파일 이동·관리자의 원장 롤백·전원 장애·대용량 성능은 후속 검증 범위다. 장부 저장과 외부 접수를 하나의 트랜잭션으로 묶을 수 없으므로 KIS 모의 응답·체결 조회 의미는 T06d에서 확인한다.

[기능 54개](../../tests/test_t06c_order_ledger.py)와 [독립 QA 7개](../../tests/test_t06c_independent_qa.py)로 다중 프로세스의 같은 ID·마지막 현금/수량 경합, 저장 실패 전후, 중단·재시작, 활성 송신 중 해제 차단, 부분 체결과 정산 자료를 검증했다. 최종 관련 196개, 전체 기본 **2199개 통과**(2개 선택 제외, 경고 51개, 110.49초)다. 첫 전체 실행의 실패 5개는 기존 Streamlit 화면 테스트가 남긴 실행 모듈을 자식 프로세스가 읽으면서 발생했다. 신규 테스트의 프로세스 시작만 격리해 화면 테스트와 주문 회귀를 함께 재실행했다. 임시 SQLite와 가상 송신으로 검증했다. 다음 개발 항목은 공식 규격 확인을 선행하는 T06d KIS 모의 전용 어댑터다.

## T06b 완료 기록 (2026-11-18)

T06a는 main `0c909fd`에 반영됐으며 **T06b 오프라인 주문 검증·가상 실행을 완료**했다. 기존 퀀트 구현79개→메인 통합/초기95개→기존 QA 독립55개/합산134개→메인 최종 관련150개·기본2138개를 순차 통과했다. 새 코드7파일과 관련 문서는 커밋 전이다. 실제 KIS 모의 인증/주문·체결·영속 원장·다중 프로세스/재시작 보장은 후속이며 다음 구현은 T06c다. 아래11월17일 설계/미구현 표시는 당시 기록이다.

### T06b 공개 API와 구현 범위

| 구현 | 현재 역할 |
| --- | --- |
| [주문 모델](../../src/invest_bot/trading/models.py) | 불변/slotted 요청·binding·정책·계좌/시장 자료·예약/book·판정/결과와 상태/사유 enum. 입력에 실제 자격정보 필드는 없다. |
| [순수 검증](../../src/invest_bot/risk/order_validation.py) | `validate_order(intent, binding, policy, account, market, book, *, now)`가 명시 입력만으로 `RiskDecision`을 반환한다. 생성/허용 판정은 가상 접수나 체결의 증거가 아니다. |
| [가상 처리](../../src/invest_bot/trading/dry_run.py) | `DryRunBroker(bindings=tuple, book_id=..., outcomes=...)`의 `execute(intent, *, policy, account, market, now, received_at=None)`가 한 인스턴스의 순차 메모리 예약·원본 결과 replay·명시 outcome을 처리한다. |

새 도메인은 settings/KISClient/DB/runner에 직접 의존하지 않는다. 정상 `invest_bot.trading/risk` import는 기존 root의 수동적 설정 클래스 재수출을 거치지만 설정 객체를 만들거나 `from_file`을 호출하지 않는다. 테스트용 가짜 package namespace는 사용하지 않는다.

현재 고정한 동작은 다음과 같다.

- 실행은 `mock` + `dry_run`과 국내현물/KRW/지정가 BUY·SELL만 허용한다. 종목·세션·호가/가격·한도·비용은 주입한 명시 정책/자료를 따른다. 실제 broker 규칙을 자동 추정하지 않는다.
- 시각은 stdlib `datetime.timezone`의 UTC/고정 offset을 받는다. `created_at <= now < expires_at`이며 만료 시각부터 거절한다. 요청/자료 age와 한도의 같음은 허용하고 초과는 거절한다. 이름 기반 timezone 변환은 신뢰된 구성 경계에서 먼저 수행한다.
- 비용 v1은 방향별 `ceil((지정가×수량×fee_rate + fixed_fee) / cost_quantum) × cost_quantum`이다. 임의 양의 금액 단위의 배수로 올림하며 float/호출자 Decimal 정밀도에 영향받지 않는다. 주문 가격/수량은 변경하지 않는다.
- BUY는 금액+비용, SELL은 매도 가능 수량과 기존 현금의 비용을 예약한다. 예상 매도 대금이나 가상 접수로 현금을 늘리지 않는다. 노출은 기보유 평가금액+기존 매수 미체결+미반영 로컬 매수 금액이며 현금/비용은 제외한다. 이미 한도 초과인 계좌의 매도 예외 정책은 추가하지 않았다.
- 자료는 현금/매도 가능 수량이 기존 주문을 반영한 순가용 값임을 전제로 한다. 같은 book과 watermark의 포함 active 예약 ID·매수 노출·주문 수가 맞아야 하며, 미반영 예약만 추가 차감한다. 진짜 broker가 이를 반영했다는 인증 기능은 아니다.
- 같은 유효 scoped ID는 거절 결과까지 같은 불변 객체로 반환한다. 변경된 정책/자료/clock은 재판정하지 않는다. 다른 fingerprint는 충돌 응답이며 기존 기록/예약은 유지한다. raw 불량 객체나 예외 repr 대신 안전한 marker를 사용하며 malformed 값의 wire 직렬화 동등성은 보장하지 않는다.
- 결과에는 안전한 client ID·구성에서 해석된 binding/version·평가 시각을 보존한다. 미해석 binding/부적합 시각은 None이다. 공개 기록/예약/book/outcome은 불변이며 `received_at`은 승인 입력/저장 metadata로 쓰지 않는다.
- outcome은 명시 `ACKNOWLEDGED`, `BROKER_REJECTED`, `UNKNOWN`이다. 허용 판정만 outcome을 소비한다. 명확 거절만 예약을 해제하고 UNKNOWN/스크립트 소진은 예약·계좌 차단을 유지한다. `decision.allowed`만으로 접수 성공을 표시하지 않고 `state`와 `execution_target`을 함께 읽는다. 체결 엔진/해제·재시도·unknown 해결 메서드는 없다.

계좌 capture는 `(binding ID, snapshot version)`별 내용과 as-of/watermark의 역행을 검사한다. **신규 ID의 정책/시장 version→내용의 불변성·진위는 신뢰된 구성의 책임**이며 처리기가 pinning/authenticate하지 않는다. 요청자가 임의 가상 자료·정책을 구성할 수 있는 Python 프로토타입은 권한 경계나 악의적 Python reflection/resource 입력을 막는 서버가 아니다. broker 한 인스턴스를 유지해야 하며 같은 프로세스에서도 재생성하면 메모리 기록을 잃는다.

다음 예제는 저장소 루트의 `PYTHONPATH=src` Python 문맥에서 [명시 가상 fixture](../../tests/t06b_order_fixture.py)를 이용하는 검증용 코드다. fixture의 수치가 운영 정책 기본값이라는 뜻은 아니다. 같은 문맥의 메인 별도 프로세스 smoke에서 정상 import·가상 접수·replay·충돌·현금 초과 거절과 금지 I/O0회를 확인했다.

```python
from tests.t06b_order_fixture import case, NOW
from invest_bot.trading.dry_run import DryRunBroker
from invest_bot.trading.models import VirtualOutcome

c = case()
owner = DryRunBroker(
    bindings=(c.binding,), book_id=c.book.book_id,
    outcomes=(VirtualOutcome.ACKNOWLEDGED,),
)
record = owner.execute(
    c.intent, policy=c.policy, account=c.account, market=c.market, now=NOW,
)
assert record.execution_target == "dry_run"
assert record.state == "ACKNOWLEDGED"  # 가상 접수이며 체결은 아님
assert owner.execute(c.intent, policy=None, account=None, market=None, now=None) is record
assert owner.execution_count == 1
```

### T06b 검증 결과 (2026-11-18)

| 수행 주체/대상 | 새로 확인한 결과 |
| --- | --- |
| 기존 퀀트의 소유6파일 | 기능79 passed /경고0,0.11초. 기존286입력 SHA/권한 보존 |
| 메인 최초 통합 | 관련95 passed,0.64초. 별도 clean 프로세스에서 공개 import·가상 접수·원본 replay·충돌·초과 주문 거절·추적 metadata·금지 부작용0 확인 |
| 기존 QA의 독립 회귀 | [독립55개](../../tests/test_t06b_independent_qa.py) + 기능79개 =134 passed /경고0,0.21초. 제품 결함/수정·실패 제외0, 고정292입력 SHA/권한 보존 |
| 메인 최종 관련 | 독립 파일 통합 후150 passed /경고0,0.69초. 위 문서 예제도 clean Python 문맥에서 실행·replay 확인 |
| 메인 전체 기본 | 최종293입력 후보에서 **2138 passed /2 deselected /51 warnings,111.76초**, 종료0 |

수치는 포함 관계이며 합산하지 않는다. Mac·Python3.13.13, 기존 pytest8.4.2/SQLAlchemy2.0.50/Streamlit1.58.0/Plotly6.8.0에서 수행했다. env-i·기존 venv·-B/PYTHONDONTWRITEBYTECODE·task-local TMPDIR/cache/basetemp/log/XML을 사용했고 실제 설정/자료를 제외한 추적 파일 격리본에서만 테스트했다. 기본 선택은 기존 `not external_network and not postgresql`이며2개를 선택 제외했다. 전체51경고는 기존 코드에서 발생했고 새 기능/독립 관련134개는 경고0이다. Linux/원격 CI·실제 KIS/운영/배포·대용량 성능은 이번에 검증하지 않았다.

초기53실패는 신규 모듈 미구현 RED다. 공개 import 지시 범위를 교정한 뒤에도53 RED를 보존했고, 구현 후53개를 통과했다. 확대 단계57통과/1실패는 fresh import 중 ZoneInfo의 OS 정보 파일 참조였다. 제품의 해당 의존을 제거하고 UTC/고정 offset 경계를 명시해 기존 guard/assertion을 유지한 채67→77→79개를 통과했다. QA는49개 독립 사례의 첫128통과 뒤6개 경계를 추가해 최종134개를 통과했으며 테스트/제품 실패는 없었다. 도구 orchestration 오류2건은 별도 진단 기록으로 구분했다.

전체 통과 후 Python214파일의 SHA를 고정하고 문서만 갱신했다. AST/메모리 compile·새 모듈의 허용 import/금지 I/O 호출 정적 검사와 파일 권한·실제 설정/backup/index/HEAD/branch를 대조했다. 새 lint/typecheck 도구를 설치하거나 실행했다고 주장하지 않는다. 검증 계약의 단일 원본은 이 문서이며 원문 계획·역할/메인 보고서·명세·XML/log·공개 예제 관측은 로컬 임시 `invest-bot-t06b-sgr6jt0k`에 보존한다. stage/commit/push·실제 외부 인증/전송·운영 DB/서비스는 수행하지 않았다.

문서58개·로컬 참조929개·등록ID58개·개념15개/관계18개에서 오류0, HTML12페이지/문서58행/고유ID43개/로컬 참조112개/외부 자원0개·기존7앵커를 확인했다. 기존 JavaScript/스타일을 유지했고 Node 모의 DOM의 탐색/검색/인쇄 복원19개가 통과했다. HTML 실제 브라우저 배치는 이전 file 접근 제한으로 미검증이며 이번에 우회하지 않았다.

## 목적과 현재 사실

모의투자 주문을 보내기 전에 요청의 의미·한도·중복·실패를 검증할 수 있는 경계를 설계한다. 첫 구현은 외부 연결 없는 검증과 가상 실행이며, KIS 모의 API 연결은 원장·결과 확인 조건을 갖춘 뒤의 별도 단계다. 순서는 [개선 색인](../operations/improvements/README.md), 전체 상태는 [task 요약](00_summary.md)을 따른다.

| 확인한 사실 | 코드 근거 | 설계에 미치는 영향 |
| --- | --- | --- |
| T06a 당시 패키지는 설명문뿐이었고 T06b에서 위 순수 모듈3개를 추가했다. | [trading 진입점](../../src/invest_bot/trading/__init__.py), [risk 진입점](../../src/invest_bot/risk/__init__.py)는 유지 | 새 기능은 별도 모듈의 명시 API로 호출한다. |
| 설정은 `TradingMode.MOCK/LIVE`와 해당 URL·키를 선택한다. | [settings](../../src/invest_bot/config/settings.py),16~18·118~134행 | 설정 선택만으로 주문을 허용하지 않는다. 주문 경계에서 mock 조건을 재확인한다. |
| KIS 클라이언트는 인증·시세용 GET을 제공하고 토큰을 캐시한다. | [KISClient](../../src/invest_bot/clients/kis_client.py),25~82·90~131행 | 검증 과정에서 생성·인증하지 않는다. 기존 시세 수집에 주문 POST를 섞지 않는다. |
| 전략 신호와 백테스트 결과는 주문·계좌 상태가 아니다. | [전략 계약](../../src/invest_bot/strategy/base.py),9~26행; [과거 시뮬레이션](../../src/invest_bot/backtest/runner.py),15~70행 | 신호만으로 주문하지 않는다. 과거 체결가·수량·평가금액은 현재 잔고의 대체물이 아니다. |
| 기본 테스트는 외부 네트워크·PostgreSQL을 제외하고 연결을 차단한다. | [pytest 설정](../../pytest.ini),1~8행; [네트워크 차단](../../tests/conftest.py),48~69행 | 첫 구현의 완료 판정에 실제 키·토큰·운영 DB가 필요하지 않아야 한다. |
| 가이드의 `reference/open-trading-api`는 이번 작업본에 없다. | [참조 원칙](../../agent.md#5-참고-자산-사용-원칙)과 시작 시 경로 확인 | endpoint/TR ID·모의 지원·호가/거래시간 규칙을 추정하지 않는다. 공식 자료 확인을 API 단계의 선행 조건으로 남긴다. |

실제 설정·키·토큰·계좌·운영 자료를 설계 입력으로 사용하지 않는다. 이번에 외부 API 규격의 최신성을 검증한 것은 아니다.

## 선택한 범위와 이유

- 첫 주문 형식은 **국내 현물·KRW·매수/매도·지정가**다. 도메인의 범위이며 KIS 지원을 확인한 명세가 아니다.
- **로컬 가상 실행**은 주입한 가상 계좌·시간·시장 자료와 fake broker만 사용한다. 결과에는 `dry_run`을 표시하고 KIS 모의 접수/체결과 구분한다.
- **KIS 모의 연결**은 별도 어댑터와 명시적 진입점으로 분리한다. 검증 함수·조회 화면·일반 수집·기존 scheduler는 주문을 시작하지 않는다.
- 시장가·신용/공매도·취소/정정·자동 신호 주문·손절/익절·실거래·주문 UI/알림은 후속이다. 부분 체결은 신규 주문의 결과로 생길 수 있으므로 상태 모델에는 포함한다.
- 금액 한도나 거래시간을 임의의 기본값으로 정하지 않는다. 명시 정책이 없는 주문은 거절하며 운영 정책값은 후속에서 정한다.

오프라인 검증 → 영속 원장·예약·대사 → 모의 어댑터 순서를 택한다. 기존 `KISClient`에 곧바로 주문 메서드를 붙이는 대안은 구현량이 적지만 인증/캐시 부작용과 시세/주문 책임이 얽힌다. 메모리 중복 집합만으로 API부터 연결하는 대안은 재시작·동시 요청·응답 유실을 다루지 못한다. 가상 검증에는 메모리를 허용하되 외부 주문에는 영속 조건을 요구한다. 새 의존성은 계획하지 않는다.

## 제안하는 도메인 계약

아래 표는 T06a에서 정의한 목표 계약이다. 현재 공개 API와 검증 범위는 위 T06b와 T06c 절을 따른다. KIS 모의 응답과 체결 조회는 T06d에서 확인한다.

| 입력/결과 | 필수 정보와 의미 |
| --- | --- |
| `OrderIntent` | schema 버전, `client_order_id`, `mode=mock`, `execution_target=dry_run/kis_mock`, 계좌 별칭, 종목, 매수/매도, 정수 수량, 통화KRW·`Decimal` 지정가, 전략/신호 출처 ID, 불변 aware `created_at/expires_at`. 실제 계좌번호·키·토큰은 제외한다. |
| `AccountSnapshot` | 같은 계좌 binding/mode/실행 대상의 관측 시각·버전, 주문 가능 현금·수량, 기보유 종목/계좌 평가금액·평가 근거, 이미 반영된 주문/체결 식별자·기준 watermark·조회 완결성. 누락·불일치·신선도 초과·불완전 자료는 거절하되 완결된0현금/빈 보유와 구분한다. |
| `MarketSnapshot` | 종목/시장·거래 가능 여부, 세션/캘린더 근거·버전, 호가 단위/허용 가격 범위와 관측 시각. 요일이나 고정 시각만으로 거래 가능을 추정하지 않는다. |
| `RiskPolicy` | 허용 종목/시장/세션, 주문·종목·계좌 노출 한도, snapshot/요청 유효기간, 비용 버퍼/계산 규칙, 허용 모드. 버전이 있는 명시 입력이며 누락·무한대·모순 값은 거절한다. |
| `RiskDecision` | 허용/거절, 안정된 사유 코드 목록, 요청·snapshot·정책 버전, 예약할 현금/수량. 허용 판정은 접수나 체결이 아니다. |
| `OrderRecord` | 내부 주문 ID/fingerprint, 상태·시각, 검증 근거, 예약, 외부 주문 식별자, 누적 체결량/잔량. 실제 계좌·민감 응답은 일반 로그/결과에서 제외한다. |

구성 경계가 계좌 별칭을 불변 binding ID/버전에 연결하고 정책·Clock·snapshot/캘린더 출처를 제공한다. 요청자가 현금·허용 정책·개장 여부를 임의 선언해 승인받는 계약이 아니다. 테스트에서는 이 구성 경계에 명시 가상 자료를 주입한다.

fingerprint는 schema 버전·실행 대상·mode·계좌 binding·종목·방향·수량·지정가·종류·출처 ID와 불변 created_at/expires_at을 포함한다. 개별 전송 시도의 received_at은 제외한다. 의미가 같은 `Decimal('123')`과 `Decimal('123.0')`은 같은 가격으로 정규화하며 실패 후 ID를 자동 교체하지 않는다. 원장에 binding 버전을 보존해 별칭 재지정이 과거 주문 의미를 바꾸지 못하게 한다. 가상 실행과 KIS 모의 실행의 원장·snapshot 출처를 분리한다.

### 검증 순서

1. **형식/모드:** live/알 수 없는 모드, 빈 ID/계좌, 잘못된 종목·방향·종류를 차단한다. T06b는 `dry_run`, T06d는 검증한 `kis_mock`만 허용하며 환경을 암묵 전환하지 않는다.
2. **수량/가격 정규화:** 수량은 bool을 제외한 양의 정수, 가격은 유한한 양의 `Decimal`이어야 한다. float 혼입·NaN/Infinity는 거절하며 조용한 반올림/수량 축소는 하지 않는다.
3. **중복:** `(execution_target, mode, account_binding_id, client_order_id)`가 같고 fingerprint도 같으면 기존 결과/UNKNOWN, 다르면 `IDEMPOTENCY_CONFLICT`이며 추가 실행0회다. 기존 요청은 새 snapshot/정책/시간으로 재판정하지 않는다. 거절 의도를 재평가하려면 새 ID로 명시 요청하며 UNKNOWN 계좌 차단은 새 ID로 우회하지 못한다.
4. **신규 요청의 시간/시장 자료:** 요청과 snapshot은 aware 시각이며 계좌·종목·모드·실행 대상이 일치해야 한다. 미래/만료/관측 불명·거래 중단·캘린더 불명·잘못된 호가/가격 범위·미허용 종목은 거절한다. `now`를 주입하고 유효기간의 같음/초과를 따로 검증한다.
5. **신규 요청의 한도:** 매수 필요 금액은 지정가×수량+명시 비용 상한, 매도는 주문 가능한 보유수량으로 제한한다. 비용의 금액 단위/상한 반올림은 명시 정책을 따르며 주문 가격/수량은 바꾸지 않는다. 기보유 가치·미체결/예약으로 종목·계좌 노출을 검사한다. broker 순가용액/수량에서 snapshot에 미반영된 로컬 예약만 추가 차감하고 이미 반영된 주문/체결은 재차 차감하지 않는다. 반영분·평가 근거가 불명이면 한도를 생략하지 않고 차단한다. 매도 접수/예상 대금으로 매수 현금을 늘리지 않는다.
6. **실행 전 재검사:** 최신 상태·중복 선점/재확인·한도·예약·전송 예정 기록을 원자적으로 처리한다. 송신 claim은 요청 hash·예약/정책/binding 버전·송신 만료와 묶고 한 번만 선점한다. 미전송 건은 정책/세션/계좌 변경·kill-switch·만료에 따라 차단한다. DB 기록과 외부 전송이 하나의 원자적 거래라고 주장하지 않는다.

대표 사유 코드는 `MODE_NOT_ALLOWED`, `INVALID_ORDER`, `POLICY_REQUIRED`, `SNAPSHOT_INVALID`, `MARKET_UNAVAILABLE`, `INSUFFICIENT_CASH`, `INSUFFICIENT_POSITION`, `LIMIT_EXCEEDED`, `IDEMPOTENCY_CONFLICT`, `RECONCILIATION_REQUIRED`다. 첫 구현에서 의미와 반환 순서를 고정하고 표시 문구와 분리한다.

## 상태·예약·복구

`검증 → 중복 선점/예약 → 전송 시도 기록 → 명시 실행 → 접수/체결 확인 → 원장 갱신`을 분리한다. 부분 응답이나 저장 실패를 성공으로 표시하지 않는다.

| 상태/사건 | 처리 계약 |
| --- | --- |
| `REJECTED` | 사전 거절. 새 전송/예약0회, 사유 반환. |
| `RESERVED` | 검증·중복 선점·예약 완료. 전송 전 원장 실패면 broker 호출0회. |
| `SUBMITTING` | 전송 전에 영속 기록. 이후 프로세스 중단 시 전송 여부를 추정하지 않고 대사 대상으로 둔다. |
| `ACKNOWLEDGED` | broker 접수의 유효한 증거가 있음. 체결/손익 확정으로 표시하지 않는다. |
| `PARTIALLY_FILLED` / `FILLED` | 주문 식별자·누적 체결량/가격·잔량이 검증됐을 때만 반영. 체결/미체결 분량에 맞춰 예약 조정, 같은 체결 이벤트 중복 반영0회. |
| `BROKER_REJECTED` | 명확한 거절 증거가 있어 미체결 예약 해제. HTTP 상태 하나만으로 미접수를 확정하지 않는다. |
| `UNKNOWN` | timeout/응답 유실/불완전 응답/응답 뒤 원장 실패 등 결과 불명. 예약 유지·자동재전송0회·같은 계좌 전체의 신규 주문 차단. |

재시작 시 `SUBMITTING`/`UNKNOWN`은 주문·체결·미체결 증거와 대사한다. 조회 실패·not-found 하나·임의 대기시간/예약 TTL만으로 미접수·예약 해제를 판단하지 않는다. 증거가 부족하면 재시작 뒤에도 미확정·예약/차단을 보존한다. 원장 복구가 실패하면 신규 승인을 차단한다. 외부 취소/만료의 확정 증거도 대사/예약 해제에 반영하되 취소 송신 기능을 구현했다는 뜻은 아니다. 내부 송신 만료와 broker 주문 유효기간/TIF를 구분한다. 외부 수동 주문/계좌 변동까지 로컬 원자성이 통제한다고 보장하지 않으며 broker 중복키·조회 일관성은 API 단계에서 확인한다.

T06b 메모리 가상 실행은 한 프로세스의 순차 호출만 모의한다. 재시작·다중 프로세스 보호의 증거로 쓰지 않으며 T06c를 생략하고 API로 넘어가지 않는다.

## 구현 순서·소유권·완료 조건

새 역할을 만들지 않는다. 메인이 문서/원본 통합을 소유하며 기존 퀀트 → 메인 연결 → 기존 QA → 필요 보완 → 같은 QA 재검증을 한 역할씩 진행한다. 제안 파일의 실제 소유권은 착수 시 명시한다.

| ID / 우선순위 | 범위와 제안 파일 | 완료 조건 | 상태 |
| --- | --- | --- | --- |
| T06a / P1 | 이 설계와 색인·지식·HTML. 담당 통합, 퀀트 자문→QA 문서 검토 | 현재/계획 구분, 계약·복구·검증 시나리오와 선행 관계 문서화, 독립 검토·문서 검사 오류0 | 완료 (2026-11-17 문서 설계) |
| T06b / P1 | 순수 검증+가상 broker. 위 구현3파일과 기능/독립 테스트 | V01~V06·V08·V13~V15의 오프라인 범위, 인증/네트워크/운영 쓰기0, 거절 시 실행0, 같은 인스턴스 중복 추가 실행0. 독립 QA·관련 회귀·고정 입력 기본 suite 통과 | 완료 (2026-11-18, 관련150·기본2138) |
| T06c / P1 | 전용 SQLite 원장과 가상 주문 예약·대사 | 실제 임시 DB와 독립 프로세스에서 중복 전송·초과 예약·자동 재전송 0회, 재시작 후 미확정과 예약 보존 | 완료 (2026-11-21, 관련 196개·기본 2199개) |
| T06d / P2 | KIS 모의 전용 주문·조회와 분리 SQLite 원장 | 공식 예제 대조와 가짜 전송 세션으로 모의 범위·주문 단일 호출·체결 상태 적용 검증 | 오프라인 완료 (2026-11-22, 관련 349개·기본 2350개), 실제 모의 계좌 검증 대기 |

T06d 구현·오프라인 계약 완료와 실제 KIS 모의 인증/주문 성공은 별도 판정이다. 실제 계좌/키를 쓰는 검증의 대상·호출·정리 범위는 해당 후속 작업에서 정한다. 이번 설계나 일반 진행 요청을 실제 주문의 상시 권한으로 사용하지 않는다.

### API 연결 전 확인할 항목

- 공식 KIS 자료의 mock 지원·endpoint/TR ID·계좌/상품·가격/수량·호가/세션·응답 의미를 날짜/근거와 함께 확인한다.
- 주문/체결 조회·연속 조회·호출 제한·timeout 후 조회 가능 시점과 확정 미접수 판단 근거를 확인한다. 미확인이면 모의 전송을 보류한다.
- 인증/캐시·허용 URL/모드·mock 전용 credential 선택을 어댑터 경계에서 검증한다. live 전환이나 설정 변경을 따라 목적지를 자동 변경하지 않는다.
- 로컬 예약과 broker 가용액/수량의 반영 기준·페이지 완결성·반영 지연과 snapshot/체결의 원자적 갱신 기준을 정한다. 실계좌/민감 응답은 일반 로그에 남기지 않는다.
- 실제 모의 정책값·신뢰 출처·한도 운영 담당/승인 주체는 아직 미확정이다. T06b는 명시 가상 정책만 쓰며 실제 계좌용 정책 확정의 대체가 아니다.

## 검증 시나리오

아래는 향후 테스트 요구사항이다. 이번에 구현·실행해 통과한 테스트 목록이 아니다. 각 경계는 개별 parameterized case로 확인한다.

| ID | 시나리오 | 기대 결과 |
| --- | --- | --- |
| V01 | mock/live/알 수 없는 모드, dry_run/kis_mock·환경/계좌/host 불일치, import·검증·조회 | 허용 mock 명시 실행 외 전송/인증/토큰 캐시 접근0, live는 항상 거절, 실행 대상 간 기록/자료 재사용0 |
| V02 | 수량0/음수/소수/bool, NaN/Infinity/float 가격, 잘못된 종목·방향·종류 | 명시 거절 코드, 조정/반올림·broker 실행0 |
| V03 | 정책/snapshot 누락·비정상 금액·불완전 보유/조회, 명시 한도/신선도 경계 | 거절과 완결된0현금/빈 보유 구분, 같은 입력/Clock은 같은 결과·입력 불변, 같음/초과·비용 포함값 검사 |
| V04 | naive/미래/만료 시각, 계좌/종목 불일치, 캘린더·거래 가능 여부 불명 | 명시 거절, 실제 시각/요일 추정이나 자료 자동 수집0 |
| V05 | 현금/매도 가능 수량 부족·비용·미체결/예약을 포함한 연속 주문 | 사용 가능 범위 이내, 이중 차감·공매도0 |
| V06 | 같은 ID/내용·동등 가격/received_at 변경·변경된 snapshot/정책, 다른 내용/created_at/expires_at, 별칭 재지정 | 같은 의미면 기존 결과·재판정/추가 전송0, 다른 내용은 충돌, 실행 대상·mode·불변 binding scope 구분 |
| V07 | 동시에 같은 ID, 또는 다른 ID로 마지막 현금/수량 사용하는 요청 | T06c의 독립 프로세스/DB 연결 경합에서 중복 선점1회 이하·합산 예약 한도 이내, 검사-예약 사이 변경 재검사 |
| V08 | 검증 허용/거절과 fake broker 실행 | 허용 때만 가상1회, dry_run/근거 버전 보존, 거절 때0회, KIS 접수/체결로 표시하지 않음 |
| V09 | 원장/claim 실패·승인 후 정책/세션/binding/만료/kill-switch 변경, 전송 뒤 timeout | 미전송은 broker0회, 전송 가능성 이후 UNKNOWN·자동재전송0·예약/계좌 차단 유지 |
| V10 | 접수·거절·부분/전체 체결, 잘못된/중복/역순 이벤트 | 접수≠체결, 누적 체결량≤요청량, 예약/잔량 정합·중복 적용0, 모순은 대사 요구 |
| V11 | SUBMITTING/UNKNOWN 재시작·복구 실패, 조회 실패/not-found/불완전/확정 근거·외부 취소/만료, 새 ID 우회 | 예약/계좌 차단 유지, 불충분한 증거/TTL로 해제·재전송0, 확정 근거로 한 번만 갱신, 새 ID로도 차단 |
| V12 | broker 응답 뒤 저장 실패·재시작·동일 요청 재제출 | 새 주문으로 재전송0, 원장 복구/대사로만 처리 |
| V13 | 로그·예외·결과 저장과 가상 입력 | 키/토큰/실계좌·전체 민감 응답0, 요청/정책/snapshot 버전과 사유 추적 가능 |
| V14 | 기존 수집·시세 클라이언트·backtest/UI/scheduler 회귀 | 기존 동작 유지, 주문 경로 암묵 연결·자동 실행0 |
| V15 | 설정·고정 소스와 테스트 격리 | env-i·기존 venv·tracked-only 격리본/임시 자료, 보호 파일 SHA/모드 불변, 새 의존성0 |

T06c의 동시성·재시작·저장 실패는 실제 임시 DB와 독립 프로세스/연결로 확인한다. mock만으로 영속 안전성을 승인하지 않는다. 실제 모의 네트워크 검증은 기본 suite 밖의 별도 작업·증거로 관리한다.

## 이번 설계 작업의 완료 판정

- 현재 구현과 제안 계약을 분리하고 선행 조건·소유 범위·테스트 기대값을 기록한다.
- 기존 퀀트의 코드 경계/설계 자문 후 기존 QA가 문서의 검증 가능성·미확정/중복/한도를 순차 검토한다. 수정은 메인이 통합한다.
- Markdown 참조·등록·HTML12페이지/58문서·탐색을 검사한다. 제품/테스트/의존성·실제 설정·운영 자료·Git 상태/권한을 보존한다.
- 결과·검토 근거·미검증 범위를 이 절에 남긴다. 문서 완료를 주문 기능 완료로 체크하지 않으며 전체 기능 suite는 재실행하지 않는다.

### 2026-11-17 결과

**T06a 설계 완료, T06b/c/d는 미구현이다.** main `6595f67`의 고정286입력에서 기존 퀀트 자문→메인 보완→기존 QA 독립 문서 검토를 하나씩 마쳤다. 퀀트 권고에 따라 실행 대상·불변 binding/의도 시각·예약 반영 근거·계좌 단위 UNKNOWN 차단·송신 claim/미확정 대사 조건을 보완했다. QA는 완료 상태 반영 전 설계 SHA `3c65bb5bda566367c5e92d65680a12d8747cbd3b3d9a561f2f3d949c3901b437`를 검토해 **APPROVE, 차단 지적0개**로 판정했다. 이후에는 이 결과와 완료 상태만 반영하며 도메인/단계 계약을 바꾸지 않는다.

메인은 Markdown58개·로컬 링크912개·등록ID58개·개념14개/관계18개, HTML12페이지/문서58행/고유ID43개/로컬 참조111개/외부 자원0개와 기존7앵커, Node 모의 DOM 탐색19개를 확인해 모두 통과했다. 원본·baseline·퀀트/QA 고정 입력의 SHA/권한, 제품/테스트 Python207파일과 실제 설정/backup/index/HEAD/branch의 보존을 대조했다. 기존 JavaScript/스타일을 유지하고 실제 HTML 브라우저 배치는 이전 file 접근 제한으로 미검증이다.

원문 보고서·입력/검토 SHA·검사 결과는 로컬 임시 `invest-bot-task06-plan-t_b22bvl`에 보존한다. 이번 문서11개는 커밋 전이며 구현·기능 테스트/전체 suite·공식 외부 규격 조사·실제 API/키/토큰·운영 DB/데이터·서비스·stage/commit/push는 수행하지 않았다. 미래 V01~V15가 통과한 것으로 보고하지 않으며 다음 구현은 T06b의 오프라인 범위다.

## 남은 기능

- [x] T06b 순수 주문 계약·리스크 검증·가상 실행 (한 인스턴스 순차 메모리 범위)
- [x] T06c 영속 원장·중복/예약·미확정 복구
- [x] T06d KIS 모의 전용 어댑터·공식 예제 대조·오프라인 검증
- [ ] 실제 KIS 모의 계좌 연결 및 주문 검증
- [ ] 실제 모의 계좌/잔고·주문 가능 수량/현금 조회·접수/체결 대사 검증
- [ ] 취소/정정·시장가·자동 실행·손절/익절·알림·실거래: 별도 후속 범위

## 관계

- [작업 원칙](../../agent.md), [OKF](../../OKF.md), [문서 등록부](../knowledge/catalog.md), [검증 가이드](../operations/python_runtime_and_test_guide.md)
- [퀀트 역할](../operations/improvements/quant.md), [QA 역할](../operations/improvements/qa.md), [세션 추적](../operations/improvement_sessions_2026-09-13.md)
