# invest_bot DB ERD Draft

This ERD finalizes the first-pass relational target for the current CSV datasets so the team can implement the migration behind stable repository contracts.

```mermaid
erDiagram
    stocks ||--o{ daily_prices : has
    stocks ||--o{ investor_daily_flows : has
    stocks ||--o{ market_reports : has

    stocks {
        string symbol PK
        string symbol_name
        string market
        datetime updated_at
    }

    daily_prices {
        string symbol FK
        date trade_date PK
        float open_price
        float high_price
        float low_price
        float close_price
        float volume
        datetime collected_at
    }

    investor_daily_flows {
        string symbol FK
        date trade_date PK
        string investor_type PK
        float net_volume
        float net_amount
        datetime collected_at
    }

    market_reports {
        string symbol FK
        date trade_date PK
        string summary
        datetime created_at
    }
```

## Source mapping

- `stocks` ← `data/reference/stock_master.csv` plus `data/raw/domestic_stock/stock_info/*.csv`
- `daily_prices` ← `data/raw/domestic_stock/daily_prices/*.csv`
- `investor_daily_flows` ← `data/raw/domestic_stock/investor_daily/*.csv`
- `market_reports` ← `data/processed/domestic_stock/market_reports/*.md|*.txt`

## Explicitly deferred

- dashboard cache tables
- indicator/output tables for every derived artifact
- execution/order/trade ledgers
- real Alembic revision history and ORM models
