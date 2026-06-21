# invest_bot DB migration ERD

## Purpose

이 문서는 **현재 코드 기준 실제 테이블 관계를 간략히 보여주는 보조 문서**다. 세부 책임과 사용자 변경 경계는 [`db_schema.md`](./db_schema.md)를 canonical source로 본다.

## Current relational shape

```mermaid
erDiagram
    SYMBOLS ||--o{ DAILY_PRICES : identifies
    SYMBOLS ||--o{ INVESTOR_DAILY : identifies
    SYMBOLS ||--o{ DATASET_FRAMES : tags
    SYMBOLS ||--o{ STOCK_INFO_SNAPSHOTS : legacy_snapshot

    SYMBOLS {
        string symbol PK
        string symbol_name
        string market
        boolean is_active
        datetime created_at
        datetime updated_at
    }

    DAILY_PRICES {
        int id PK
        string symbol FK
        date trade_date
        numeric open_price
        numeric high_price
        numeric low_price
        numeric close_price
        int volume
        numeric turnover
        string source_filename
        datetime collected_at
    }

    INVESTOR_DAILY {
        int id PK
        string symbol FK
        date trade_date
        numeric foreign_net_qty
        numeric institutional_net_qty
        numeric personal_net_qty
        text raw_payload
        string source_filename
        datetime collected_at
    }

    DATASET_FRAMES {
        int id PK
        string dataset
        string filename
        string symbol FK
        date as_of_date
        int row_count
        text frame_json
        datetime created_at
        datetime updated_at
    }

    STOCK_INFO_SNAPSHOTS {
        int id PK
        string symbol FK
        datetime captured_at
        string product_name
        string market_code
        text raw_payload
        string source_filename
    }
```

## Ownership notes

- `symbols`는 canonical 종목 reference다.
- `daily_prices`, `investor_daily`는 정규화된 fact table이다.
- `dataset_frames`는 raw/derived snapshot store다.
- `stock_info_snapshots`는 현재 정책 기준 **deprecated candidate**다.

## Migration direction

- 사용자 종목 검색/조회 source는 `symbols`로 단일화한다.
- `dataset_frames.stock_info`는 canonical source에서 제외한다.
- `stock_info_snapshots`는 후속 migration에서 제거 후보로 다룬다.
