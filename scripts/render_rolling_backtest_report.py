"""Render rolling-window and mixed-strategy backtests as a standalone HTML report."""
from __future__ import annotations

import argparse
import json
import math
from datetime import datetime
from zoneinfo import ZoneInfo
from collections import Counter, defaultdict
from html import escape
from pathlib import Path
from statistics import mean
from typing import Any, Iterable, Mapping, Sequence


REPORT_DATE = "2026-10-13"
DEFAULT_INPUT = Path(f"data/rolling-backtests/{REPORT_DATE}")
DEFAULT_OUTPUT = Path(f"data/reports/rolling-mixed-backtest-{REPORT_DATE}.html")
MODEL_TYPES = {
    "single": "단일 전략",
    "signal_mix": "신호 혼합",
    "capital_mix": "자금 배분",
}
TYPE_ORDER = {"single": 0, "signal_mix": 1, "capital_mix": 2}
REGIME_ORDER = {"상승": 0, "횡보": 1, "하락": 2}
PALETTE = [
    "#2563eb", "#0f8b6d", "#d97706", "#be3e59", "#7c3aed", "#0891b2",
    "#6b7280", "#a16207", "#0369a1", "#4d7c0f", "#c2410c", "#4338ca",
]


CSS = r"""
.sort-button{font:inherit;font-weight:700;color:inherit;background:none;border:0;padding:0;cursor:pointer;text-align:inherit}.sort-button::after{content:' ↕';color:#65758a}.sort-button:focus-visible{outline:2px solid #2563eb;outline-offset:4px}th[aria-sort=ascending] .sort-button::after{content:' ↑';color:#245ec7}th[aria-sort=descending] .sort-button::after{content:' ↓';color:#245ec7}.empty-state{padding:16px;background:#fff7e7;border-radius:8px}.explorer-reset{font:inherit;border:1px solid #bcc8d8;background:#fff;border-radius:7px;padding:7px 12px;cursor:pointer}.explorer-period{font-weight:700;overflow-wrap:anywhere}.detail-search{display:block;margin:15px 0}.detail-search input{font:inherit;max-width:100%;border:1px solid #bcc8d8;border-radius:7px;padding:8px 12px}#explorer-model{max-width:100%}
.grid-2>*{min-width:0}.cards>*{min-width:0}.table-wrap{max-width:100%}.downloads a{overflow-wrap:anywhere}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:#f2f5f8;color:#152238;font:15px/1.7 -apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Malgun Gothic",sans-serif}
main{max-width:1380px;margin:auto;padding:28px 24px 54px}a{color:#245ec7;text-underline-offset:4px}nav{display:flex;gap:16px;flex-wrap:wrap;margin-bottom:20px}.hero{background:linear-gradient(125deg,#12213a,#233b65);color:#fff;border-radius:20px;padding:34px;margin-bottom:22px;box-shadow:0 12px 30px #20304a22}.hero h1{font-size:34px;line-height:1.25;margin:0 0 10px}.hero p{margin:7px 0;color:#d9e4f5}.eyebrow{font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:#91b9ff;font-weight:750}.panel{background:#fff;border:1px solid #dce3eb;border-radius:16px;padding:28px;margin:20px 0;box-shadow:0 3px 12px #13233a0a}.panel h2{font-size:24px;line-height:1.35;margin:0 0 12px}.panel h3{font-size:19px;margin:24px 0 9px}.panel h4{font-size:16px;margin:20px 0 6px}.lead{font-size:17px;line-height:1.75}.muted{font-size:13px;color:#617087}.callout{border-left:4px solid #2563eb;background:#eef5ff;padding:14px 16px;border-radius:4px 10px 10px 4px;margin:16px 0}.warning{border-left-color:#d97706;background:#fff7e7}.stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:18px 0}.stat{background:#edf3fb;border-radius:12px;padding:16px}.stat span{display:block;color:#617087;font-size:12px}.stat strong{display:block;font-size:23px;line-height:1.4;margin-top:2px}.grid-2{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}.cards{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}.card{border:1px solid #dce3eb;border-radius:12px;padding:16px;background:#fbfcfe}.card h3,.card h4{margin-top:0}.pill{display:inline-block;border-radius:999px;padding:2px 9px;font-size:12px;font-weight:700;background:#e6eefc;color:#244d8f}.pill.mix{background:#e6f6f1;color:#08765e}.pill.capital{background:#fff2dc;color:#9a5a00}.table-wrap{overflow:auto;border:1px solid #dce3eb;border-radius:11px;margin:14px 0}table{border-collapse:collapse;width:100%;font-size:13px}th,td{padding:9px 11px;text-align:left;border-bottom:1px solid #e1e7ef;white-space:nowrap}th{position:sticky;top:0;background:#eef2f7;z-index:1}tbody tr:nth-child(even){background:#fafbfd}tbody tr:hover{background:#f1f6fd}tr:last-child td{border-bottom:0}.num{text-align:right;font-variant-numeric:tabular-nums}.positive{color:#08745e;font-weight:650}.negative{color:#b33c50;font-weight:650}.best{background:#eaf7f3;border-radius:5px;padding:1px 5px}.filters{display:flex;gap:12px;align-items:end;flex-wrap:wrap;background:#f5f7fa;border-radius:11px;padding:13px;margin:14px 0}.filters label{display:grid;gap:4px;font-size:12px;color:#536177}.filters select,.filters input{font:inherit;background:#fff;border:1px solid #bcc8d8;border-radius:7px;padding:7px 9px;min-width:140px}.filters input{min-width:220px}.filter-count{margin-left:auto;color:#617087;font-size:13px}details{border-top:1px solid #dce3eb;margin-top:12px}summary{padding:14px 2px;cursor:pointer;font-weight:700}details>div{padding:0 2px 8px}ul,ol{padding-left:22px}li{margin:5px 0}.definition{display:grid;grid-template-columns:210px 1fr;gap:6px 18px}.definition dt{font-weight:700}.definition dd{margin:0;color:#35445c}.chart{border:1px solid #dce3eb;border-radius:11px;padding:12px;margin:14px 0;background:#fff}.chart svg{width:100%;height:auto;display:block}.legend{display:flex;flex-wrap:wrap;gap:9px 16px;font-size:12px;margin:8px 4px}.legend span::before{content:"━";color:var(--c);font-weight:900;margin-right:5px}.rank{font-variant-numeric:tabular-nums}.downloads{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px 18px}.downloads a{display:block}.hidden{display:none!important}footer{color:#617087;font-size:13px;margin-top:24px;padding:0 4px}
@media(max-width:900px){.stats{grid-template-columns:repeat(2,minmax(0,1fr))}.grid-2,.cards{grid-template-columns:1fr}.downloads{grid-template-columns:repeat(2,minmax(0,1fr))}.definition{grid-template-columns:1fr}.definition dd{margin-bottom:8px}}
@media(max-width:600px){main{padding:15px 10px 38px}.panel,.hero{padding:20px 16px}.hero h1{font-size:28px}.stats{grid-template-columns:1fr}.filters>*{width:100%}.filters select,.filters input{width:100%;min-width:0}.filter-count{margin-left:0}.downloads{grid-template-columns:1fr}}
@media(max-width:600px){#stock-explorer .stats{grid-template-columns:repeat(2,minmax(0,1fr))}#stock-explorer .stat{padding:12px}#stock-explorer .stat strong{font-size:20px}}
@media print{body{background:#fff}main{max-width:none;padding:0}.hero{background:#fff;color:#152238;padding:15px 0;box-shadow:none}.hero p{color:#35445c}.panel{border:0;box-shadow:none;padding:14px 0;break-inside:auto}nav,.filters{display:none}.table-wrap{overflow:visible}table{font-size:10px}th{position:static}details{break-inside:avoid}details>div{display:block!important}footer{padding-bottom:20px}}
"""


JS = r"""
(() => {
  'use strict';
  const norm = value => (value ?? '').toString().toLowerCase().trim();
  const collator = new Intl.Collator('ko-KR', {numeric: true});
  const sortKey = cell => {
    const raw = cell?.dataset.sortValue ?? cell?.textContent?.trim() ?? '';
    if (!raw || /^[—–−-]$/.test(raw)) return null;
    if (cell?.dataset.sortValue !== undefined && Number.isFinite(Number(raw))) return Number(raw);
    if (/^[+−-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?:%p?|원|일|회)?$/.test(raw)) {
      return Number(raw.replaceAll(',', '').replace('−', '-').replace(/(%p?|원|일|회)$/, ''));
    }
    return raw;
  };
  const sortTable = table => {
    if (table.dataset.sortColumn === undefined) return;
    const column = Number(table.dataset.sortColumn);
    const direction = table.dataset.sortDirection === 'ascending' ? 1 : -1;
    const rows = Array.from(table.tBodies[0].rows);
    rows.forEach((row, index) => { if (!row.dataset.originalOrder) row.dataset.originalOrder = String(index + 1); });
    rows.sort((a, b) => {
      const x = sortKey(a.cells[column]), y = sortKey(b.cells[column]);
      if (x === null || y === null) return x === y ? Number(a.dataset.originalOrder) - Number(b.dataset.originalOrder) : x === null ? 1 : -1;
      const compared = typeof x === 'number' && typeof y === 'number' ? x - y : collator.compare(String(x), String(y));
      return compared * direction || Number(a.dataset.originalOrder) - Number(b.dataset.originalOrder);
    });
    table.tBodies[0].append(...rows);
  };
  document.querySelectorAll('table').forEach(table => {
    table.addEventListener('report:rows-changed', () => sortTable(table));
    table.querySelectorAll('thead th').forEach((header, column) => {
      header.querySelector('.sort-button')?.addEventListener('click', () => {
        const direction = table.dataset.sortColumn === String(column) && table.dataset.sortDirection === 'ascending' ? 'descending' : 'ascending';
        table.dataset.sortColumn = String(column);
        table.dataset.sortDirection = direction;
        table.querySelectorAll('thead th').forEach(th => th.setAttribute('aria-sort', 'none'));
        header.setAttribute('aria-sort', direction);
        sortTable(table);
      });
    });
  });
  document.querySelectorAll('[data-filter-table]').forEach(box => {
    const target = document.getElementById(box.dataset.filterTable);
    if (!target) return;
    const rows = Array.from(target.querySelectorAll('tbody tr'));
    const controls = Array.from(box.querySelectorAll('[data-filter]'));
    const counter = box.querySelector('[data-filter-count]');
    const apply = () => {
      let visible = 0;
      rows.forEach(row => {
        const ok = controls.every(control => {
          const query = norm(control.value);
          if (!query || query === 'all') return true;
          const key = control.dataset.filter;
          if (key === 'text') return norm(row.textContent).includes(query);
          return norm(row.dataset[key]) === query;
        });
        row.hidden = !ok;
        if (ok) visible += 1;
      });
      if (counter) counter.textContent = `${visible.toLocaleString('ko-KR')}행 표시`;
    };
    controls.forEach(control => control.addEventListener(control.tagName === 'INPUT' ? 'input' : 'change', apply));
    apply();
  });
  const detailSearch = document.getElementById('stock-detail-search');
  if (detailSearch) {
    const details = Array.from(document.querySelectorAll('#stocks details'));
    detailSearch.addEventListener('input', () => {
      const query = norm(detailSearch.value);
      details.forEach(detail => { detail.hidden = !norm(detail.querySelector('summary').textContent).includes(query); });
      document.getElementById('stock-detail-empty').hidden = details.some(detail => !detail.hidden);
    });
  }
  const openDetail = symbol => {
    const detail = document.getElementById(`stock-${symbol}`);
    if (!detail) return;
    if (detailSearch) { detailSearch.value = ''; detailSearch.dispatchEvent(new Event('input')); }
    detail.open = true;
  };
  document.addEventListener('click', event => {
    const link = event.target.closest('a[data-stock-detail]');
    if (link) openDetail(link.dataset.stockDetail);
  });
  if (location.hash.startsWith('#stock-')) openDetail(location.hash.slice(7));
  const payload = document.getElementById('stock-explorer-data');
  if (!payload) return;
  const data = JSON.parse(payload.textContent);
  const family = document.getElementById('explorer-family');
  const windowSelect = document.getElementById('explorer-window');
  const modelSelect = document.getElementById('explorer-model');
  const search = document.getElementById('explorer-search');
  const table = document.getElementById('stock-period-table');
  const groups = new Map();
  data.results.forEach(row => {
    const key = `${row[0]}:${row[1]}`;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(row);
  });
  const addOption = (select, value, label) => {
    const option = document.createElement('option');
    option.value = String(value); option.textContent = label; select.append(option);
  };
  const familyKey = window => window.kind === 'rolling' ? `rolling:${window.length}` : window.kind;
  const familyKeys = [...new Set(data.windows.map(familyKey))];
  familyKeys.sort((a, b) => {
    const order = value => value.startsWith('rolling:') ? Number(value.split(':')[1]) : value === 'recent' ? 0 : Infinity;
    return order(a) - order(b);
  });
  familyKeys.forEach(key => addOption(family, key, key.startsWith('rolling:') ? `슬라이딩 ${key.split(':')[1]}거래일` : key === 'full' ? '전체 기간' : '최근 5거래일'));
  data.models.forEach((model, index) => addOption(modelSelect, index, `${model.type_label} · ${model.name}`));
  const pctText = (value, points = false) => value == null ? '—' : `${value >= 0 ? '+' : ''}${value.toLocaleString('ko-KR', {minimumFractionDigits: 2, maximumFractionDigits: 2})}${points ? '%p' : '%'}`;
  const display = () => {
    const windowIndex = Number(windowSelect.value), modelIndex = Number(modelSelect.value);
    const window = data.windows[windowIndex], model = data.models[modelIndex];
    if (!window || !model) return;
    const query = norm(search.value);
    const rows = (groups.get(`${windowIndex}:${modelIndex}`) || []).filter(row => {
      const stock = data.symbols[row[2]];
      return norm(`${stock.name} ${stock.symbol}`).includes(query);
    });
    document.getElementById('explorer-period').textContent = `${window.start_date} ~ ${window.end_date} · ${window.length}거래일 · ${model.name} · ETF 국면: ${window.regime}`;
    const counts = [rows.length, rows.filter(r => r[3] > 0).length, rows.filter(r => r[3] > r[5]).length, rows.filter(r => r[7] === 0).length];
    document.querySelectorAll('[data-explorer-stat]').forEach((element, index) => { element.textContent = `${counts[index]}종목`; });
    table.tBodies[0].replaceChildren();
    rows.forEach((row, index) => {
      const stock = data.symbols[row[2]];
      const tr = document.createElement('tr'); tr.dataset.originalOrder = String(index + 1);
      const nameCell = tr.insertCell(); const link = document.createElement('a');
      link.href = `#stock-${stock.symbol}`; link.dataset.stockDetail = stock.symbol; link.textContent = stock.name; nameCell.append(link);
      tr.insertCell().textContent = stock.symbol;
      const metrics = [[row[3], pctText(row[3]), true], [Math.abs(row[4]), pctText(Math.abs(row[4])).replace(/^\+/, ''), false],
        [row[5], pctText(row[5]), true], [row[3] - row[5], pctText(row[3] - row[5], true), true],
        [row[6], pctText(row[6]), true], [row[3] - row[6], pctText(row[3] - row[6], true), true],
        [row[7], `${row[7]}회`, false], [row[8], pctText(row[8]).replace(/^\+/, ''), false],
        [row[9], pctText(row[9]).replace(/^\+/, ''), false]];
      metrics.forEach(([value, label, signed]) => {
        const cell = tr.insertCell(); cell.textContent = label; cell.dataset.sortValue = value == null ? '' : String(value);
        cell.classList.add('num'); if (signed) cell.classList.add(value >= 0 ? 'positive' : 'negative');
      });
      table.tBodies[0].append(tr);
    });
    sortTable(table);
    table.hidden = rows.length === 0;
    document.getElementById('explorer-empty').hidden = rows.length !== 0;
    document.getElementById('explorer-count').textContent = `${rows.length} / ${data.symbols.length}종목 표시`;
  };
  const updateWindows = () => {
    windowSelect.replaceChildren();
    data.windows.map((window, index) => ({window, index})).filter(({window}) => familyKey(window) === family.value)
      .sort((a, b) => b.window.end_date.localeCompare(a.window.end_date))
      .forEach(({window, index}) => addOption(windowSelect, index, `${window.start_date} ~ ${window.end_date}`));
    display();
  };
  const reset = () => {
    family.value = familyKeys.includes('rolling:20') ? 'rolling:20' : familyKeys[0];
    const momentum = data.models.findIndex(model => model.id === 'momentum');
    modelSelect.value = String(momentum >= 0 ? momentum : 0); search.value = ''; updateWindows();
  };
  family.addEventListener('change', updateWindows);
  windowSelect.addEventListener('change', display); modelSelect.addEventListener('change', display);
  search.addEventListener('input', display);
  document.getElementById('explorer-reset').addEventListener('click', reset);
  reset();
})();
"""


def _f(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def _i(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def pct(value: Any, *, points: bool = False, signed: bool = True) -> str:
    number = _f(value)
    sign = "+" if signed and number >= 0 else ""
    suffix = "%p" if points else "%"
    return f"{sign}{number:,.2f}{suffix}"


def money(value: Any) -> str:
    return f"{_f(value):,.0f}원"


def performance(value: Any, *, points: bool = False) -> str:
    number = _f(value)
    cls = "positive" if number >= 0 else "negative"
    return f'<span class="{cls}">{pct(number, points=points)}</span>'


def mdd(value: Any) -> str:
    return f"{abs(_f(value)):,.2f}%"


def price_revision_notice(meta: Mapping[str, Any]) -> str:
    count = _i(meta.get("price_revision_count"))
    if count <= 0:
        return ""
    dates = ", ".join(str(value) for value in meta.get("price_revision_dates", []) if value)
    detail = f" 비교된 날짜: {escape(dates)}." if dates else ""
    revision_file = str(meta.get("price_revision_file") or "")
    link = f' <a href="{escape(revision_file, quote=True)}">변경 내역 CSV</a>' if revision_file else ""
    return (
        '<div class="callout warning"><strong>가격 원자료 갱신:</strong> '
        f'중복 날짜 비교에서 {count:,}건의 차이를 확인했습니다. 이전 저장본과 중복 날짜의 종가·거래량이 달라 최신 API 조회값으로 다시 계산했습니다. '
        f'이전 보고서와의 차이에는 기간 연장과 원자료 재조회 차이가 함께 포함됩니다.{detail}{link}</div>'
    )


def html_table(
    headers: Sequence[str],
    rows: Iterable[Sequence[str]],
    *,
    table_id: str | None = None,
    row_attrs: Sequence[str] | None = None,
) -> str:
    attrs = f' id="{escape(table_id)}"' if table_id else ""
    rendered_rows = []
    for index, row in enumerate(rows):
        extra = row_attrs[index] if row_attrs and index < len(row_attrs) else ""
        rendered_rows.append(
            f"<tr{extra}>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>"
        )
    return (
        '<div class="table-wrap"><table'
        + attrs
        + "><thead><tr>"
        + "".join(f'<th scope="col" aria-sort="none"><button type="button" class="sort-button" title="{escape(header)} 정렬">{escape(header)}</button></th>' for header in headers)
        + "</tr></thead><tbody>"
        + "".join(rendered_rows)
        + "</tbody></table></div>"
    )


def model_index(data: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {str(model["id"]): model for model in data.get("models", [])}


def model_label(model: Mapping[str, Any]) -> str:
    return escape(str(model.get("name") or model.get("id") or "알 수 없음"))


def type_badge(model_type: str) -> str:
    css = "mix" if model_type == "signal_mix" else "capital" if model_type == "capital_mix" else ""
    label = MODEL_TYPES.get(model_type, model_type)
    return f'<span class="pill {css}">{escape(label)}</span>'


def group_rows(rows: Iterable[Mapping[str, Any]], *keys: str) -> dict[tuple[Any, ...], list[Mapping[str, Any]]]:
    grouped: dict[tuple[Any, ...], list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[tuple(row.get(key) for key in keys)].append(row)
    return grouped


def best_by(rows: Sequence[Mapping[str, Any]], metric: str = "net_return_pct") -> Mapping[str, Any] | None:
    if not rows:
        return None
    return max(rows, key=lambda row: (_f(row.get(metric)), -_f(row.get("net_mdd_pct")), str(row.get("model_id", ""))))


def latest_window_rows(data: Mapping[str, Any], key: str) -> list[Mapping[str, Any]]:
    """Return the explicit recent-5 window plus rolling windows ending on the as-of date."""
    as_of = str(data.get("metadata", {}).get("as_of", ""))
    return [
        row
        for row in data.get(key, [])
        if row.get("kind") == "recent"
        or (row.get("kind") == "rolling" and str(row.get("end_date", "")) == as_of)
    ]


def within_length_rank_score(
    aggregates: Sequence[Mapping[str, Any]],
    models: Mapping[str, Mapping[str, Any]],
) -> list[tuple[str, float, int]]:
    """Average within-length percentile; never compares raw returns across horizons."""
    grouped = group_rows(aggregates, "length")
    scores: dict[str, list[float]] = defaultdict(list)
    for rows in grouped.values():
        ordered = sorted(rows, key=lambda row: (_f(row.get("median_net_return_pct")), -_f(row.get("median_net_mdd_pct"))), reverse=True)
        denominator = max(len(ordered) - 1, 1)
        for rank, row in enumerate(ordered):
            scores[str(row.get("model_id"))].append(1.0 - rank / denominator)
    result = [(model_id, mean(parts), len(parts)) for model_id, parts in scores.items() if model_id in models]
    return sorted(result, key=lambda item: (item[1], item[2], item[0]), reverse=True)


def filter_controls(
    table_id: str,
    *,
    lengths: Sequence[int] = (),
    regimes: Sequence[str] = (),
    types: bool = True,
    text_placeholder: str = "모델·종목 검색",
) -> str:
    controls = [f'<div class="filters" data-filter-table="{escape(table_id)}">']
    if lengths:
        controls.append('<label>기간<select data-filter="length"><option value="all">전체</option>')
        controls.extend(f'<option value="{length}">{length}거래일</option>' for length in sorted(set(lengths)))
        controls.append("</select></label>")
    if types:
        controls.append('<label>유형<select data-filter="type"><option value="all">전체</option>')
        controls.extend(f'<option value="{key}">{escape(value)}</option>' for key, value in MODEL_TYPES.items())
        controls.append("</select></label>")
    if regimes:
        controls.append('<label>시장 국면<select data-filter="regime"><option value="all">전체</option>')
        controls.extend(f'<option value="{escape(regime)}">{escape(regime)}</option>' for regime in sorted(set(regimes), key=lambda r: REGIME_ORDER.get(r, 99)))
        controls.append("</select></label>")
    controls.append(f'<label>검색<input data-filter="text" type="search" placeholder="{escape(text_placeholder)}"></label>')
    controls.append('<span class="filter-count" data-filter-count></span></div>')
    return "".join(controls)


def line_chart(series: Mapping[str, Sequence[float]], dates: Sequence[str], title: str) -> str:
    valid = {label: list(values) for label, values in series.items() if values and len(values) == len(dates)}
    if not valid or not dates:
        return '<p class="muted">표시할 평가금액 곡선이 없습니다.</p>'
    returns = {
        label: [(_f(value) / max(_f(values[0]), 1e-12) - 1.0) * 100.0 for value in values]
        for label, values in valid.items()
    }
    all_values = [value for values in returns.values() for value in values] + [0.0]
    low, high = min(all_values), max(all_values)
    padding = max((high - low) * 0.08, 1.0)
    low -= padding
    high += padding
    width, height, left, right, top, bottom = 1120, 380, 72, 24, 24, 44

    def x(index: int) -> float:
        return left + index / max(len(dates) - 1, 1) * (width - left - right)

    def y(value: float) -> float:
        return top + (high - value) / max(high - low, 1e-12) * (height - top - bottom)

    svg = [f'<div class="chart"><svg role="img" aria-label="{escape(title)}" viewBox="0 0 {width} {height}"><title>{escape(title)}</title>']
    for index in range(5):
        value = low + (high - low) * index / 4
        yy = y(value)
        svg.append(f'<line x1="{left}" x2="{width-right}" y1="{yy:.2f}" y2="{yy:.2f}" stroke="#e1e7ef"/><text x="{left-8}" y="{yy+4:.2f}" text-anchor="end" font-size="12" fill="#617087">{value:.1f}%</text>')
    svg.append(f'<line x1="{left}" x2="{width-right}" y1="{y(0):.2f}" y2="{y(0):.2f}" stroke="#91a0b5"/>')
    legend = ['<div class="legend">']
    for index, (label, values) in enumerate(returns.items()):
        color = PALETTE[index % len(PALETTE)]
        points = " ".join(f"{x(i):.2f},{y(value):.2f}" for i, value in enumerate(values))
        dash = ' stroke-dasharray="8 5"' if label in {"매수 후 보유", "ETF"} else ""
        svg.append(f'<polyline fill="none" stroke="{color}" stroke-width="2.2" points="{points}"{dash}><title>{escape(label)} · {pct(values[-1])}</title></polyline>')
        legend.append(f'<span style="--c:{color}">{escape(label)} {pct(values[-1])}</span>')
    for index in sorted({0, (len(dates) - 1) // 2, len(dates) - 1}):
        anchor = 'start' if index == 0 else 'end' if index == len(dates)-1 else 'middle'
        svg.append(f'<text x="{x(index):.2f}" y="{height-14}" text-anchor="{anchor}" font-size="12" fill="#617087">{escape(str(dates[index]))}</text>')
    svg.append("</svg>")
    legend.append("</div></div>")
    return "".join(svg + legend)


def executive_section(data: Mapping[str, Any], models: Mapping[str, Mapping[str, Any]]) -> str:
    meta = data.get("metadata", {})
    aggregates = list(data.get("aggregates", []))
    lengths = sorted({_i(row.get("length")) for row in aggregates if _i(row.get("length"))})
    scores = within_length_rank_score(aggregates, models)
    robust = models.get(scores[0][0], {}) if scores else {}
    portfolio = list(data.get("portfolio_results", []))
    latest = latest_window_rows(data, "portfolio_results")
    recent20 = [row for row in latest if _i(row.get("length")) == 20]
    recent5 = [row for row in latest if _i(row.get("length")) == 5]
    best20 = best_by(recent20)
    best5 = best_by(recent5)
    stock_count = len({str(row.get("symbol")) for row in data.get("stock_results", []) if row.get("symbol")})
    rolling_count = len({row.get("window_id") for row in portfolio if row.get("kind") == "rolling"})
    stats = [
        ("분석 가능 구간", f'{_i(meta.get("eligible_rows")):,}거래일'),
        ("슬라이딩 창", f"{rolling_count:,}개"),
        ("검증 모델", f"{len(models):,}개"),
        ("비용 가정", f'편도 {_f(meta.get("cost_rate"))*100:.2f}%'),
    ]
    cards = []
    if robust:
        cards.append(
            '<div class="card"><h3>길이별 상대 순위</h3>'
            f'<p><strong>{model_label(robust)}</strong>이(가) {len(lengths)}개 창 길이에서 계산한 순위 백분위 평균이 가장 높았습니다.</p>'
            '<p class="muted">서로 다른 기간의 누적수익률을 직접 합산하지 않고, 각 길이 안에서만 순위를 매긴 뒤 평균했습니다. 사후 안정성 단서이며 미래 최적 전략을 뜻하지 않습니다.</p></div>'
        )
    for label, row in (("최근 20거래일", best20), ("최근 5거래일", best5)):
        if row:
            model = models.get(str(row.get("model_id")), {})
            exposure = _f(row.get("mean_exposure_pct"))
            no_trade = _i(row.get("no_trade_constituents"))
            cash_note = " 투자 비중이 낮아 상대적 손실 방어의 상당 부분은 현금 보유에서 왔습니다." if exposure < 20 else ""
            cards.append(
                f'<div class="card"><h3>{label}</h3><p><strong>{model_label(model)}</strong> · 비용 후 {performance(row.get("net_return_pct"))}</p>'
                f'<p class="muted">같은 창 매수 후 보유 {pct(row.get("bh_net_return_pct"))}, ETF {pct(row.get("etf_net_return_pct"))}. 평균 투자 관측 비중 {exposure:.1f}%, 무거래 종목 {no_trade}/{stock_count}.{cash_note} 짧은 창은 체결 한두 번과 종료 청산에 민감하므로 행동 점검용입니다.</p></div>'
            )
    body = '<section class="panel" id="summary"><h2>핵심 결론</h2>'
    body += '<div class="stats">' + "".join(f'<div class="stat"><span>{escape(label)}</span><strong>{escape(value)}</strong></div>' for label, value in stats) + "</div>"
    length_text = "·".join(str(length) for length in lengths)
    body += f'<p class="lead">단일 전략과 혼합 전략을 같은 가격·체결·비용 기준으로 비교했습니다. 결과는 하나의 전 구간 숫자가 아니라, {escape(length_text)}거래일 슬라이딩 창의 분포와 최근 구간, 시장 국면, 워크포워드 결과를 함께 읽도록 구성했습니다.</p>'
    body += price_revision_notice(meta)
    body += '<div class="cards">' + "".join(cards) + "</div>"
    body += '<div class="callout warning"><strong>의사결정 범위:</strong> 이 리포트에서 “우수”는 지정된 표본과 규칙에서 비용 후 결과가 상대적으로 좋았다는 뜻입니다. 후보 모델은 같은 과거 자료를 보고 사후 설계됐으며, 워크포워드도 완전히 손대지 않은 독립 표본은 아닙니다.</div></section>'
    return body


def model_definition_section(data: Mapping[str, Any], models: Mapping[str, Mapping[str, Any]]) -> str:
    effective_rules = max(len(models) - 1, 0)
    body = f'<section class="panel" id="models"><h2>검증한 단일·혼합 모델</h2><p>후보는 {len(models)}개지만 평균회귀와 이격도가 현재 기본값에서 동일하므로 서로 다른 거래 규칙은 실질적으로 {effective_rules}개입니다. 혼합 방식은 신호를 결합하거나 초기자금을 여러 독립 슬리브에 배분합니다. 가중 투표의 숫자는 신호 투표권이며 포지션 크기가 아닙니다.</p><div class="cards">'
    ordered = sorted(models.values(), key=lambda model: (TYPE_ORDER.get(str(model.get("type")), 99), str(model.get("name", ""))))
    for model in ordered:
        components = model.get("components") or {}
        def component_name(key: Any) -> str:
            component = models.get(str(key), {})
            return escape(str(component.get("name") or key))

        if str(model.get("type")) == "capital_mix":
            component_text = ", ".join(f"{component_name(key)} {(_f(value)*100):.0f}%" for key, value in components.items()) or "—"
        else:
            component_text = ", ".join(f"{component_name(key)} 가중치 {_f(value):g}" for key, value in components.items()) or "—"
        rules = model.get("rules")
        if isinstance(rules, list):
            rules_text = " / ".join(str(rule) for rule in rules)
        elif isinstance(rules, Mapping):
            rules_text = ", ".join(f"{key}: {value}" for key, value in rules.items())
        else:
            rules_text = str(rules or "기본 단일 전략 규칙")
        body += (
            '<article class="card">'
            f'<h3>{model_label(model)}</h3><p>{type_badge(str(model.get("type", "")))}</p>'
            f'<p>{escape(rules_text)}</p><p class="muted">구성: {component_text}'
            + (" · 수급 데이터 포함" if model.get("includes_flow") else "")
            + "</p></article>"
        )
    body += '</div><div class="callout"><strong>중복 규칙:</strong> 평균회귀와 이격도는 표현만 다르고 현재 기본값에서는 같은 신호입니다. 6개 동일가중 투표 모델은 이 중복 투표를 피하려고 이격도를 제외합니다. AND 모델은 매도도 모든 구성 전략의 합의를 기다리므로 청산이 늦어질 수 있고, 비대칭 모델은 모두 동의할 때 진입하되 하나라도 매도하면 청산합니다.</div><details><summary>기본 파라미터 보기</summary><div>'
    parameter_rows = []
    for model in ordered:
        parameters = model.get("parameters") or {}
        parameter_rows.append([model_label(model), f'<code>{escape(json.dumps(parameters, ensure_ascii=False, sort_keys=True))}</code>'])
    body += html_table(["모델", "기본 파라미터"], parameter_rows) + "</div></details></section>"
    return body


def full_period_section(data: Mapping[str, Any], models: Mapping[str, Mapping[str, Any]]) -> str:
    full = sorted(
        [row for row in data.get("portfolio_results", []) if row.get("kind") == "full"],
        key=lambda row: _f(row.get("net_return_pct")),
        reverse=True,
    )
    if not full:
        return ""
    rows, attrs = [], []
    stock_count = len({str(row.get("symbol")) for row in data.get("stock_results", []) if row.get("symbol")})
    for row in full:
        model = models.get(str(row.get("model_id")), {})
        model_type = str(model.get("type", ""))
        rows.append([
            model_label(model), type_badge(model_type),
            performance(row.get("gross_return_pct")), performance(row.get("net_return_pct")),
            performance(_f(row.get("net_return_pct")) - _f(row.get("bh_net_return_pct")), points=True),
            performance(_f(row.get("net_return_pct")) - _f(row.get("etf_net_return_pct")), points=True),
            mdd(row.get("net_mdd_pct")), str(_i(row.get("trade_count"))), str(_i(row.get("forced_exit_count"))),
            f'{_f(row.get("mean_exposure_pct")):.1f}%', f'{_i(row.get("profitable_constituents"))}/{stock_count}',
        ])
        attrs.append(f' data-type="{escape(model_type)}"')
    by_id = {str(row.get("model_id")): row for row in full}
    body = '<section class="panel" id="full"><h2>전체 준비 이후 기간</h2><p>슬라이딩 분포와 별도로, 준비 이후 첫날부터 기준일까지 한 번만 실행한 경로입니다. 시작일 하나에 의존하므로 이 표만으로 전략을 고르지 않습니다.</p>'
    and_row = by_id.get("mix-mt-and")
    momentum_row = by_id.get("momentum")
    vote_row = by_id.get("mix-unique6-weighted")
    if and_row and momentum_row:
        return_delta = _f(and_row.get("net_return_pct")) - _f(momentum_row.get("net_return_pct"))
        mdd_delta = _f(and_row.get("net_mdd_pct")) - _f(momentum_row.get("net_mdd_pct"))
        body += (
            '<div class="callout"><strong>수익과 낙폭의 교환:</strong> '
            f'{model_label(models.get("mix-mt-and", {}))}: 비용 후 {pct(and_row.get("net_return_pct"))}, MDD {mdd(and_row.get("net_mdd_pct"))}. '
            f'{model_label(models.get("momentum", {}))}: 비용 후 {pct(momentum_row.get("net_return_pct"))}, MDD {mdd(momentum_row.get("net_mdd_pct"))}. '
            f'AND 혼합은 수익률이 {pct(return_delta, points=True)} 높았지만 MDD도 {pct(mdd_delta, points=True)} 커져, 수익 우위와 낙폭 악화가 함께 나타났습니다.</div>'
        )
    if vote_row:
        cost_drag = _f(vote_row.get("gross_return_pct")) - _f(vote_row.get("net_return_pct"))
        body += (
            '<p><strong>혼합 수가 많다고 자동으로 좋아지지는 않았습니다.</strong> '
            f'{model_label(models.get("mix-unique6-weighted", {}))}: 총수익 {pct(vote_row.get("gross_return_pct"))} → 비용 후 {pct(vote_row.get("net_return_pct"))}, '
            f'거래 {_i(vote_row.get("trade_count")):,}건. 비용 반영으로 {pct(cost_drag, points=True)} 줄었으며, 이 설정에서는 잦은 신호와 거래비용이 혼합의 성과를 크게 깎았습니다.</p>'
        )
    body += filter_controls("full-table", types=True)
    body += html_table(["모델", "유형", "총수익", "비용 후", "보유 대비", "ETF 대비", "MDD", "거래", "종료 청산", "평균 보유", "수익 종목"], rows, table_id="full-table", row_attrs=attrs)
    curve = data.get("curves", {}).get(str(full[0].get("window_id")), {})
    selected = []
    for model_type in ("single", "signal_mix", "capital_mix"):
        winner = best_by([row for row in full if models.get(str(row.get("model_id")), {}).get("type") == model_type])
        if winner:
            selected.append(str(winner.get("model_id")))
    series = {}
    for model_id in dict.fromkeys(selected):
        values = curve.get("models", {}).get(model_id, {}).get("net", [])
        if values:
            series[str(models.get(model_id, {}).get("name", model_id))] = values
    if curve.get("buy_hold", {}).get("net"):
        series["매수 후 보유"] = curve["buy_hold"]["net"]
    if curve.get("etf", {}).get("net"):
        series["ETF"] = curve["etf"]["net"]
    body += line_chart(series, curve.get("dates", []), "전체 준비 이후 기간 비용 후 누적수익률")
    return body + "</section>"


def single_vs_mix_section(data: Mapping[str, Any], models: Mapping[str, Mapping[str, Any]]) -> str:
    aggregates = list(data.get("aggregates", []))
    lengths = sorted({_i(row.get("length")) for row in aggregates if _i(row.get("length"))})
    rows = []
    for length in lengths:
        candidates = [row for row in aggregates if _i(row.get("length")) == length]
        single = best_by([row for row in candidates if models.get(str(row.get("model_id")), {}).get("type") == "single"], "median_net_return_pct")
        mixed = best_by([row for row in candidates if models.get(str(row.get("model_id")), {}).get("type") in {"signal_mix", "capital_mix"}], "median_net_return_pct")
        if not single or not mixed:
            continue
        single_model = models.get(str(single.get("model_id")), {})
        mixed_model = models.get(str(mixed.get("model_id")), {})
        delta = _f(mixed.get("median_net_return_pct")) - _f(single.get("median_net_return_pct"))
        rows.append([
            f"{length}일",
            model_label(single_model), performance(single.get("median_net_return_pct")), mdd(single.get("median_net_mdd_pct")),
            model_label(mixed_model), performance(mixed.get("median_net_return_pct")), mdd(mixed.get("median_net_mdd_pct")),
            performance(delta, points=True),
        ])
    return (
        '<section class="panel" id="mix"><h2>단일 전략과 혼합 전략 비교</h2>'
        '<p>각 창 길이 안에서 비용 후 수익률 중앙값이 가장 높은 단일 모델과 혼합 모델을 비교합니다. 길이가 다른 누적수익률은 같은 순위표에 섞지 않았습니다.</p>'
        + html_table(["창 길이", "최고 단일", "단일 중앙값", "단일 중앙 MDD", "최고 혼합", "혼합 중앙값", "혼합 중앙 MDD", "혼합−단일"], rows)
        + '<p class="muted">중앙값 우위가 위험조정 우위를 보장하지 않습니다. 양수 창 비중, 매수 후 보유·ETF 초과 창 비중, 최악 MDD를 다음 분포표에서 함께 확인하세요.</p></section>'
    )


def aggregate_section(data: Mapping[str, Any], models: Mapping[str, Mapping[str, Any]]) -> str:
    aggregates = sorted(data.get("aggregates", []), key=lambda row: (_i(row.get("length")), -_f(row.get("median_net_return_pct"))))
    rows, attrs = [], []
    for row in aggregates:
        model = models.get(str(row.get("model_id")), {})
        model_type = str(model.get("type", ""))
        rows.append([
            f'{_i(row.get("length"))}일', model_label(model), type_badge(model_type), f'{_i(row.get("windows"))}',
            performance(row.get("q25_net_return_pct")), performance(row.get("median_net_return_pct")), performance(row.get("q75_net_return_pct")),
            performance(row.get("min_net_return_pct")), performance(row.get("max_net_return_pct")),
            f'{_f(row.get("positive_window_pct")):.1f}%', f'{_f(row.get("bh_outperform_window_pct")):.1f}%', f'{_f(row.get("etf_outperform_window_pct")):.1f}%',
            mdd(row.get("median_net_mdd_pct")), mdd(row.get("worst_net_mdd_pct")), f'{_f(row.get("mean_trade_count")):.1f}', f'{_f(row.get("mean_exposure_pct")):.1f}%',
        ])
        attrs.append(f' data-length="{_i(row.get("length"))}" data-type="{escape(model_type)}"')
    lengths = [_i(row.get("length")) for row in aggregates]
    body = '<section class="panel" id="distribution"><h2>슬라이딩 창 성과 분포</h2><p>각 시작점에서 새 현금으로 다시 실행한 창의 비용 후 결과입니다. 겹친 창은 시장 환경을 촘촘히 보는 표본이며, 수익률을 서로 이어 붙이거나 통계적으로 독립된 시행처럼 유의확률을 계산하지 않습니다.</p>'
    body += filter_controls("aggregate-table", lengths=lengths)
    body += html_table(["길이", "모델", "유형", "창 수", "Q25", "중앙값", "Q75", "최저", "최고", "수익 창", "보유 초과", "ETF 초과", "중앙 MDD", "최악 MDD", "평균 거래", "평균 보유"], rows, table_id="aggregate-table", row_attrs=attrs)
    body += '<p class="muted">양수 창 비중은 비용 후 수익률이 0%보다 큰 창의 비중입니다. 보유 초과·ETF 초과는 같은 날짜의 비용 후 비교 기준을 넘은 창의 비중입니다. 평균 보유는 종가 관측 시 투자된 비중이며 수익 창 비중과 다릅니다.</p></section>'
    return body


def window_detail_section(data: Mapping[str, Any], models: Mapping[str, Mapping[str, Any]]) -> str:
    rolling = sorted(
        [row for row in data.get("portfolio_results", []) if row.get("kind") == "rolling"],
        key=lambda row: (_i(row.get("length")), str(row.get("start_date", "")), str(row.get("model_id", ""))),
    )
    rows, attrs = [], []
    for row in rolling:
        model = models.get(str(row.get("model_id")), {})
        model_type = str(model.get("type", ""))
        rows.append([
            f'{_i(row.get("length"))}일', escape(str(row.get("start_date", ""))), escape(str(row.get("end_date", ""))),
            model_label(model), type_badge(model_type), escape(str(row.get("regime", ""))),
            performance(row.get("net_return_pct")), mdd(row.get("net_mdd_pct")),
            performance(row.get("bh_net_return_pct")), performance(row.get("etf_net_return_pct")),
            f'{_i(row.get("trade_count")):,}', f'{_f(row.get("mean_exposure_pct")):.1f}%',
            str(_i(row.get("no_trade_constituents"))),
        ])
        attrs.append(f' data-length="{_i(row.get("length"))}" data-type="{escape(model_type)}"')
    lengths = [_i(row.get("length")) for row in rolling]
    window_count = len({str(row.get("window_id")) for row in rolling})
    body = '<section class="panel" id="window-details"><h2>기간별 슬라이딩 창 상세</h2>'
    body += f'<p>{window_count:,}개 기간 창 × {len(models):,}개 모델, 총 {len(rolling):,}행을 개별 확인할 수 있습니다. 같은 시작일·종료일 안에서 전략, 매수 후 보유, ETF를 직접 비교하세요.</p>'
    body += '<details><summary>전체 기간별 상세표 펼치기</summary><div>'
    body += filter_controls("window-detail-table", lengths=lengths, text_placeholder="날짜·모델·국면 검색")
    body += html_table(
        ["길이", "시작일", "종료일", "모델", "유형", "국면", "비용 후 수익", "MDD", "매수 후 보유", "ETF", "거래", "평균 투자", "무거래 종목"],
        rows,
        table_id="window-detail-table",
        row_attrs=attrs,
    )
    stock_count = len({str(row.get("symbol")) for row in data.get("stock_results", []) if row.get("symbol")})
    body += f'</div></details><p class="muted">각 행은 해당 창 시작 시점에 {stock_count}종목을 동일 배분해 새 현금으로 실행한 포트폴리오 결과입니다. 숫자는 portfolio_results.csv와 동일합니다.</p></section>'
    return body


def recent_section(
    data: Mapping[str, Any],
    models: Mapping[str, Mapping[str, Any]],
    *,
    report_date: str | None = None,
) -> str:
    recent = sorted(
        latest_window_rows(data, "portfolio_results"),
        key=lambda row: (_i(row.get("length")), -_f(row.get("net_return_pct"))),
    )
    rows, attrs = [], []
    stock_count = len({str(row.get("symbol")) for row in data.get("stock_results", []) if row.get("symbol")})
    for row in recent:
        model = models.get(str(row.get("model_id")), {})
        model_type = str(model.get("type", ""))
        rows.append([
            f'{_i(row.get("length"))}일', f'{escape(str(row.get("start_date", "")))}~{escape(str(row.get("end_date", "")))}',
            model_label(model), type_badge(model_type), escape(str(row.get("regime", ""))),
            performance(row.get("gross_return_pct")), performance(row.get("net_return_pct")),
            performance(_f(row.get("net_return_pct")) - _f(row.get("bh_net_return_pct")), points=True),
            performance(_f(row.get("net_return_pct")) - _f(row.get("etf_net_return_pct")), points=True),
            mdd(row.get("net_mdd_pct")), str(_i(row.get("trade_count"))), f'{_f(row.get("mean_exposure_pct")):.1f}%',
            f'{_i(row.get("profitable_constituents"))}/{stock_count}', f'{_i(row.get("no_trade_constituents"))}/{stock_count}',
        ])
        attrs.append(f' data-length="{_i(row.get("length"))}" data-type="{escape(model_type)}" data-regime="{escape(str(row.get("regime", "")))}"')
    lengths = [_i(row.get("length")) for row in recent]
    regimes = [str(row.get("regime")) for row in recent if row.get("regime")]
    recent5_row = next((row for row in recent if _i(row.get("length")) == 5), None)
    body = '<section class="panel" id="recent"><h2>기준일 종료 창과 최근 20일·5일 행동 점검</h2><p>각 길이의 가장 최근 창을 같은 기준일로 맞췄습니다. 최근 20일은 단기 국면에서 규칙이 어떤 선택을 했는지, 최근 5일은 체결과 종료 청산 민감도를 보는 보조 창입니다. 두 짧은 창 모두 전략 우열을 확정하기에는 표본이 부족합니다.</p>'
    if recent5_row:
        intervals = max(_i(recent5_row.get("length")) - 1, 0)
        body += (
            '<p class="muted"><strong>기간 기준 차이:</strong> 이 리포트의 최근 5일 창은 '
            f'{escape(str(recent5_row.get("start_date", "")))} 종가에서 {escape(str(recent5_row.get("end_date", "")))} 종가까지 {intervals}개 수익률 구간입니다. '
            f'<a href="weekly-trend-{escape(report_date or REPORT_DATE)}.html">주간 추세 리포트</a>의 2주 수익률은 별도 시작일을 사용하므로 두 수치를 직접 같다고 보면 안 됩니다.</p>'
        )
    body += filter_controls("recent-table", lengths=lengths, regimes=regimes)
    body += html_table(["기간", "날짜", "모델", "유형", "국면", "총수익", "비용 후", "보유 대비", "ETF 대비", "MDD", "거래", "보유", "수익 종목", "무거래 종목"], rows, table_id="recent-table", row_attrs=attrs)

    curves = data.get("curves", {})
    for length in (20, 5):
        candidates = [row for row in recent if _i(row.get("length")) == length]
        winner = best_by(candidates)
        if not winner:
            continue
        window_id = str(winner.get("window_id"))
        curve = curves.get(window_id, {})
        selected_ids = []
        for model_type in ("single", "signal_mix", "capital_mix"):
            candidate = best_by([row for row in candidates if models.get(str(row.get("model_id")), {}).get("type") == model_type])
            if candidate:
                selected_ids.append(str(candidate.get("model_id")))
        series = {}
        for model_id in dict.fromkeys(selected_ids):
            values = curve.get("models", {}).get(model_id, {}).get("net", [])
            if values:
                series[str(models.get(model_id, {}).get("name", model_id))] = values
        if curve.get("buy_hold", {}).get("net"):
            series["매수 후 보유"] = curve["buy_hold"]["net"]
        if curve.get("etf", {}).get("net"):
            series["ETF"] = curve["etf"]["net"]
        body += f'<h3>최근 {length}일 · 유형별 상위 모델 곡선</h3>' + line_chart(series, curve.get("dates", []), f"최근 {length}일 비용 후 누적수익률")
    return body + "</section>"


def regime_section(data: Mapping[str, Any], models: Mapping[str, Mapping[str, Any]]) -> str:
    regime_rows = sorted(
        data.get("regime_aggregates", []),
        key=lambda row: (_i(row.get("length")), REGIME_ORDER.get(str(row.get("regime")), 99), -_f(row.get("median_net_return_pct"))),
    )
    rows, attrs = [], []
    for row in regime_rows:
        model = models.get(str(row.get("model_id")), {})
        model_type = str(model.get("type", ""))
        regime = str(row.get("regime", ""))
        rows.append([
            f'{_i(row.get("length"))}일', escape(regime), model_label(model), type_badge(model_type), str(_i(row.get("windows"))),
            performance(row.get("median_net_return_pct")), performance(row.get("q25_net_return_pct")), performance(row.get("q75_net_return_pct")),
            f'{_f(row.get("positive_window_pct")):.1f}%', f'{_f(row.get("bh_outperform_window_pct")):.1f}%', f'{_f(row.get("etf_outperform_window_pct")):.1f}%',
            mdd(row.get("median_net_mdd_pct")), mdd(row.get("worst_net_mdd_pct")),
        ])
        attrs.append(f' data-length="{_i(row.get("length"))}" data-type="{escape(model_type)}" data-regime="{escape(regime)}"')
    lengths = [_i(row.get("length")) for row in regime_rows]
    regimes = [str(row.get("regime")) for row in regime_rows if row.get("regime")]
    body = '<section class="panel" id="regime"><h2>시장 국면별 결과</h2><p>각 창의 ETF 가격수익률이 +3% 이상이면 상승, −3% 이하이면 하락, 그 사이면 횡보로 분류했습니다. 국면은 사후 관측 분류라서 실시간 전환 신호가 아닙니다.</p>'
    body += filter_controls("regime-table", lengths=lengths, regimes=regimes)
    body += html_table(["길이", "국면", "모델", "유형", "창 수", "중앙값", "Q25", "Q75", "수익 창", "보유 초과", "ETF 초과", "중앙 MDD", "최악 MDD"], rows, table_id="regime-table", row_attrs=attrs)
    body += '<p class="muted">창 수가 적은 조합은 중앙값과 비율이 한두 관측에 크게 달라질 수 있습니다. 국면별 표는 구조적 우위 증명보다 취약한 환경을 찾는 용도입니다.</p></section>'
    return body


def walk_forward_section(data: Mapping[str, Any], models: Mapping[str, Mapping[str, Any]]) -> str:
    wf = data.get("walk_forward") or {}
    summaries = list(wf.get("policy_summaries", []))
    fixed = list(wf.get("fixed_summaries", []))
    blocks = list(wf.get("blocks", []))
    policy_names = {"max_return": "훈련 수익률 최대", "return_minus_mdd": "훈련 수익률−MDD 최대"}
    rows = []
    for row in summaries:
        rows.append([
            escape(policy_names.get(str(row.get("policy")), str(row.get("policy", "")))), performance(row.get("net_return_pct")),
            mdd(row.get("net_mdd_pct")), performance(row.get("bh_net_return_pct")), performance(row.get("etf_net_return_pct")),
        ])
    fixed_rows = []
    for row in sorted(fixed, key=lambda item: _f(item.get("net_return_pct")), reverse=True):
        fixed_rows.append([model_label(models.get(str(row.get("model_id")), {})), performance(row.get("net_return_pct")), mdd(row.get("net_mdd_pct"))])
    selection_rows = []
    selection_counts: dict[str, Counter[str]] = defaultdict(Counter)
    for block in blocks:
        for selection in block.get("selections", []):
            policy = str(selection.get("policy", ""))
            model_id = str(selection.get("model_id", ""))
            selection_counts[policy][model_id] += 1
            selection_rows.append([
                escape(str(block.get("block_id", ""))), f'{escape(str(block.get("train_start", "")))}~{escape(str(block.get("train_end", "")))}',
                f'{escape(str(block.get("test_start", "")))}~{escape(str(block.get("test_end", "")))}',
                escape(policy_names.get(policy, policy)), model_label(models.get(model_id, {})),
                performance(selection.get("train_net_return_pct")), mdd(selection.get("train_net_mdd_pct")),
                performance(selection.get("test_net_return_pct")), mdd(selection.get("test_net_mdd_pct")),
                performance(selection.get("test_bh_net_return_pct")), performance(selection.get("test_etf_net_return_pct")),
            ])
    body = '<section class="panel" id="walk-forward"><h2>워크포워드 선택 검증</h2>'
    test_observations = len(blocks) * _i(wf.get("test_length"))
    body += f'<p>{_i(wf.get("train_length"))}거래일 훈련 구간에서 비용 후 값으로 모델을 선택하고 바로 다음 {_i(wf.get("test_length"))}거래일에 실행했습니다. 훈련 구간끼리는 겹칠 수 있지만 테스트 {len(blocks)}개 블록, 합계 {test_observations}거래일은 서로 겹치지 않습니다. 각 블록은 새 현금으로 시작해 끝에서 청산한 뒤 종료자산만 복리로 연결했습니다.</p>'
    body += '<p class="muted">선택 정책은 훈련 비용 후 수익률 최대와 훈련 비용 후 수익률−MDD 최대입니다. 점수가 같으면 MDD가 낮은 모델, 그래도 같으면 모델 ID 순으로 고릅니다.</p>'
    best_fixed_rows = fixed_rows[:1]
    body += '<div class="grid-2"><div><h3>선택 정책 연결 성과</h3>' + html_table(["정책", "비용 후 수익률", "MDD", "매수 후 보유", "ETF"], rows) + f'</div><div><h3>고정 모델 사후 최고 참고</h3><p class="muted">{len(fixed_rows)}개 고정 모델의 전체 테스트 블록 연결 결과를 사후 비교한 최고값입니다. 선택 정책의 실시간 성과처럼 해석하지 않습니다.</p>' + html_table(["모델", "비용 후 수익률", "MDD"], best_fixed_rows) + "</div></div>"
    if selection_counts:
        body += '<h3>훈련 구간에서 선택된 횟수</h3><div class="cards">'
        for policy, counts in selection_counts.items():
            description = ", ".join(f'{model_label(models.get(model_id, {}))} {count}회' for model_id, count in counts.most_common())
            body += f'<div class="card"><h4>{escape(policy_names.get(policy, policy))}</h4><p>{description}</p></div>'
        body += "</div>"
    body += f'<details><summary>{len(fixed_rows)}개 고정 모델 연결 결과 전체</summary><div><p class="muted">모든 테스트 블록에 같은 모델을 고정 적용한 사후 비교표입니다.</p>' + html_table(["모델", "비용 후 수익률", "MDD"], fixed_rows) + "</div></details>"
    body += '<details><summary>블록별 선택과 테스트 결과</summary><div>' + html_table(["블록", "훈련", "테스트", "정책", "선택 모델", "훈련 수익", "훈련 MDD", "테스트 수익", "테스트 MDD", "보유", "ETF"], selection_rows) + "</div></details>"
    curve = wf.get("curves", {})
    series = {policy_names.get(policy, policy): values for policy, values in (curve.get("policies") or {}).items()}
    if curve.get("buy_hold"):
        series["매수 후 보유"] = curve["buy_hold"]
    if curve.get("etf"):
        series["ETF"] = curve["etf"]
    body += line_chart(series, curve.get("dates", []), "워크포워드 블록 연결 평가금액")
    stock_count = len({str(row.get("symbol")) for row in data.get("stock_results", []) if row.get("symbol")})
    body += f'<div class="callout warning"><strong>연결 성과 해석:</strong> 각 테스트 블록은 {stock_count}종목에 초기금액을 다시 동일 배분하고, 앞 블록과 같은 모델이 선택돼도 포지션을 이어받지 않습니다. 블록 사이 overnight 가격 변화도 반영하지 않습니다. 따라서 연속 보유 계좌의 실제 경로와 다릅니다. 후보군 자체도 이 과거 자료를 본 뒤 설계돼 완전한 독립 OOS 검증은 아닙니다.</div></section>'
    return body


def stock_explorer_payload(data: Mapping[str, Any]) -> dict[str, Any]:
    """Keep original metrics in indexed rows; avoid mounting 18,496 table rows."""
    windows = [{key: window.get(key) for key in ("id", "kind", "length", "start_date", "end_date", "regime")} for window in data.get("windows", [])]
    models = [{"id": model["id"], "name": model["name"], "type_label": MODEL_TYPES.get(model["type"], model["type"])} for model in data.get("models", [])]
    symbol_names = {str(row["symbol"]): str(row.get("symbol_name") or row["symbol"]) for row in data.get("stock_results", [])}
    symbols = [{"symbol": symbol, "name": name} for symbol, name in sorted(symbol_names.items(), key=lambda item: item[1])]
    window_index = {window["id"]: index for index, window in enumerate(windows)}
    model_indices = {model["id"]: index for index, model in enumerate(models)}
    symbol_index = {stock["symbol"]: index for index, stock in enumerate(symbols)}
    metrics = ("net_return_pct", "net_mdd_pct", "bh_net_return_pct", "etf_net_return_pct", "trade_count", "exposure_pct", "win_rate_net_pct")
    results = []
    for row in data.get("stock_results", []):
        values = [row.get(key) for key in metrics]
        if not _i(row.get("trade_count")):
            values[-1] = None
        results.append([window_index[row["window_id"]], model_indices[row["model_id"]], symbol_index[str(row["symbol"])], *values])
    return {"windows": windows, "models": models, "symbols": symbols, "results": results}


def stock_explorer_section(data: Mapping[str, Any]) -> str:
    packet = stock_explorer_payload(data)
    payload = json.dumps(packet, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    # JSON is embedded in a script element: HTML escaping would corrupt JSON,
    # while escaping angle brackets prevents data from terminating the element.
    payload = payload.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    table = html_table(["종목", "코드", "비용 후 수익률", "MDD", "매수 후 보유", "보유 대비", "ETF", "ETF 대비", "거래 수", "투자 비중", "순승률"], [], table_id="stock-period-table")
    cards = "".join(f'<div class="stat"><span>{label}</span><strong data-explorer-stat>—</strong></div>' for label in ("검색 결과", "수익률 양수", "매수 후 보유 초과", "무거래·현금 대기"))
    model_count = len(packet["models"])
    rolling_count = sum(1 for window in packet["windows"] if window.get("kind") == "rolling")
    return f'''<section class="panel" id="stock-explorer"><h2>기간별 종목 한눈에 보기</h2>
<p>같은 기간과 같은 전략으로 종목들을 비교합니다. 기본 화면은 최신 20거래일·모멘텀 단독이며, 단일·혼합 {model_count:,}개 모델과 모든 {rolling_count:,}개 슬라이딩 창·전체 기간·최근 구간을 선택할 수 있습니다.</p>
<div class="filters">
<label>기간 길이<select id="explorer-family"></select></label>
<label>평가 기간<select id="explorer-window"></select></label>
<label>전략<select id="explorer-model"></select></label>
<label>종목명·코드 검색<input id="explorer-search" type="search" placeholder="삼성전자 또는 005930"></label>
<button type="button" id="explorer-reset" class="explorer-reset">선택 초기화</button>
<span id="explorer-count" class="filter-count" role="status"></span></div>
<p id="explorer-period" class="explorer-period"></p><div class="stats">{cards}</div>
<p class="muted">표 제목을 누르면 오름차순·내림차순으로 정렬합니다. 보유 대비·ETF 대비는 비용 후 수익률 차이(%p), 투자 비중은 기간 평균입니다. 순승률은 청산 거래 기준이며 무거래는 —로 표시합니다. 종목명을 누르면 상세로 이동합니다. ETF 국면은 기간 종료 후 분류입니다.</p>
{table}<p id="explorer-empty" class="empty-state" role="status" hidden>일치하는 종목이 없습니다. 종목명이나 6자리 코드를 확인하거나 검색을 지우세요.</p>
<noscript><p class="empty-state">기간 선택·검색·정렬에는 JavaScript가 필요합니다. 아래 종목별 상세와 다운로드 CSV로 결과를 확인할 수 있습니다.</p></noscript>
<script id="stock-explorer-data" type="application/json">{payload}</script></section>'''


def stock_section(data: Mapping[str, Any], models: Mapping[str, Mapping[str, Any]]) -> str:
    aggregates = list(data.get("stock_aggregates", []))
    stock_results = list(data.get("stock_results", []))
    symbols = sorted({(str(row.get("symbol")), str(row.get("symbol_name") or row.get("symbol"))) for row in aggregates or stock_results}, key=lambda item: item[1])
    body = f'<section class="panel" id="stocks"><h2>{len(symbols):,}개 종목별 상세</h2><p>종목마다 각 창 길이의 비용 후 중앙값이 가장 높은 단일·혼합 모델을 나란히 표시합니다. 사후 최고 모델 표이므로 종목 맞춤 전략의 독립 검증으로 해석하면 안 됩니다.</p>'
    body += '<label class="detail-search">상세 종목 검색 <input id="stock-detail-search" type="search" placeholder="종목명 또는 코드"></label><p id="stock-detail-empty" class="empty-state" hidden>일치하는 종목이 없습니다.</p>'
    grouped_agg = group_rows(aggregates, "symbol", "length")
    latest_stock = latest_window_rows(data, "stock_results")
    grouped_recent = group_rows(latest_stock, "symbol", "length")
    for symbol, name in symbols:
        lengths = sorted({_i(key[1]) for key in grouped_agg if str(key[0]) == symbol and _i(key[1])})
        rows = []
        for length in lengths:
            candidates = grouped_agg.get((symbol, length), [])
            single = best_by([row for row in candidates if models.get(str(row.get("model_id")), {}).get("type") == "single"], "median_net_return_pct")
            mixed = best_by([row for row in candidates if models.get(str(row.get("model_id")), {}).get("type") in {"signal_mix", "capital_mix"}], "median_net_return_pct")
            if not single or not mixed:
                continue
            rows.append([
                f"{length}일", model_label(models.get(str(single.get("model_id")), {})), performance(single.get("median_net_return_pct")), mdd(single.get("worst_net_mdd_pct")),
                model_label(models.get(str(mixed.get("model_id")), {})), performance(mixed.get("median_net_return_pct")), mdd(mixed.get("worst_net_mdd_pct")),
                performance(_f(mixed.get("median_net_return_pct")) - _f(single.get("median_net_return_pct")), points=True),
            ])
        recent_rows = []
        for length in (20, 5):
            candidates = grouped_recent.get((symbol, length), [])
            winner = best_by(candidates)
            if winner:
                recent_rows.append([
                    f"최근 {length}일", model_label(models.get(str(winner.get("model_id")), {})), performance(winner.get("net_return_pct")),
                    performance(winner.get("bh_net_return_pct")), performance(winner.get("etf_net_return_pct")),
                    mdd(winner.get("net_mdd_pct")), str(_i(winner.get("trade_count"))), "—" if not _i(winner.get("trade_count")) else f'{_f(winner.get("win_rate_net_pct")):.1f}%', f'{_f(winner.get("exposure_pct")):.1f}%',
                ])
        body += f'<details id="stock-{escape(symbol)}"><summary>{escape(name)} ({escape(symbol)})</summary><div>'
        body += html_table(["창", "최고 단일", "단일 중앙값", "단일 최악 MDD", "최고 혼합", "혼합 중앙값", "혼합 최악 MDD", "혼합−단일"], rows)
        if recent_rows:
            body += '<h4>최근 구간 사후 최고 모델</h4>' + html_table(["기간", "모델", "비용 후", "매수 후 보유", "ETF", "MDD", "거래", "순승률", "보유"], recent_rows)
        body += "</div></details>"
    body += "</section>"
    return body


def methodology_section(data: Mapping[str, Any]) -> str:
    meta = data.get("metadata", {})
    lengths = ", ".join(f"{value}일" for value in meta.get("lengths", []))
    step = _i(meta.get("step"))
    cost = _f(meta.get("cost_rate")) * 100
    stock_count = len({str(row.get("symbol")) for row in data.get("stock_results", []) if row.get("symbol")})
    verification = data.get("_verification") or data.get("verification") or {}
    missing = verification.get("missing_indicators_after_ready") or {}
    symbol_names = {
        str(row.get("symbol")): str(row.get("symbol_name") or row.get("symbol"))
        for row in data.get("stock_results", [])
        if row.get("symbol")
    }
    missing_items = []
    for symbol, indicators in missing.items():
        for indicator, count in indicators.items():
            missing_items.append(f'{escape(symbol_names.get(str(symbol), str(symbol)))} ({escape(str(symbol))})의 {escape(str(indicator))} {int(count)}일')
    missing_note = ""
    if missing_items:
        missing_note = f'<li>공통 준비 이후 지표 결측은 {", ".join(missing_items)}입니다. 해당 조건에 의존하는 전략은 그 관측일에 신호를 내지 않습니다.</li>'
    return f'''<section class="panel" id="method"><h2>검증 설계와 계산 규칙</h2>
<dl class="definition">
<dt>자료와 준비 구간</dt><dd>{escape(str(meta.get("raw_start", "")))}부터 {_i(meta.get("raw_rows")):,}개 원자료를 사용했습니다. 모든 지표가 준비된 {escape(str(meta.get("eligible_start", "")))}부터 {_i(meta.get("eligible_rows")):,}개 거래일을 창 분석 대상으로 삼았습니다.</dd>
<dt>슬라이딩 창</dt><dd>{escape(lengths)} 길이를 {step}거래일 간격으로 이동했습니다. 길이 L의 가격수익률은 첫 종가부터 끝 종가까지 L−1개 가격 간격입니다. 같은 길이의 최신 창은 기준일 {escape(str(meta.get("as_of", "")))}에 끝납니다.</dd>
<dt>신호와 체결</dt><dd>전체 이력으로 지표를 먼저 계산하되 각 창은 현금 100만원으로 새로 시작합니다. 당일 신호는 다음 거래일 종가에 체결하며, 마지막 날 보유분은 종가로 강제 청산합니다. 공매도는 없고 소수점 주식에 전액 투자할 수 있습니다.</dd>
<dt>거래비용</dt><dd>매수와 매도 각각 평가금액에 편도 {cost:.2f}%를 곱합니다. 가격 변화가 없는 왕복 거래의 비용 후 손실은 약 {(1-(1-cost/100)**2)*100:.4f}%입니다. 이 비율은 세율 가정이 아니라 수수료·슬리피지 등을 단순화한 통합 비용입니다.</dd>
<dt>자금 배분 혼합</dt><dd>각 전략 슬리브가 배정 자금 안에서 독립적으로 재투자합니다. 슬리브 간 및 종목 간 중간 재배분은 없습니다. {stock_count}종목 포트폴리오는 초기 동일 배분이고 MDD는 종목 평가금액 합산 곡선에서 계산합니다. 자금 배분 모델의 순승률은 슬리브별 청산 거래 건수 기준이며, 자본가중 승률이나 포트폴리오 승률이 아닙니다.</dd>
<dt>시장 비교</dt><dd>매수 후 보유와 ETF를 같은 날짜·같은 비용 규칙으로 계산합니다. ETF 창 수익률 ±3%를 기준으로 상승·횡보·하락 국면을 기간 종료 후 설명용으로 분류합니다. 전략을 미리 고르는 예측 정보로 사용하지 않았습니다.</dd>
</dl>
<h3>읽을 때 지켜야 할 경계</h3>
<ul>
<li>겹친 슬라이딩 창의 수익률을 연결하거나 모두 독립 시행으로 취급하지 않습니다.</li>
<li>양수 창 비중과 평균 보유 비중은 다른 지표입니다. 현금 유지 전략은 거래가 없으면 수익률·MDD가 모두 0%라서 하락 구간에서 상대 순위가 높아질 수 있습니다.</li>
<li>서로 다른 길이의 누적수익률을 한 숫자로 섞지 않습니다. 이 리포트의 교차 길이 평가는 길이별 상대 순위만 사용합니다.</li>
<li>최근 5일은 성과 검증보다 규칙의 민감도와 행동을 확인하는 창입니다.</li>
{missing_note}
<li>수급 데이터의 과거 공개 시각을 검증하지 못했습니다. 수급 포함 모델은 당시 장 마감 전에 동일 값이 이용 가능했다고 단정할 수 없습니다.</li>
<li>배당과 현금 이자는 0으로 두었습니다. 현재 {stock_count}종목 표본에는 생존 편향과 종목 선택 편향이 있습니다.</li>
<li>후보 전략과 혼합 규칙은 이 과거 자료를 본 뒤 설계됐습니다. 워크포워드는 선택 시점의 미래 구간을 분리하지만 후보 설계까지 포함한 완전한 독립 표본은 아닙니다.</li>
</ul></section>'''


def download_section(data_href: str, *, report_date: str = REPORT_DATE) -> str:
    files = [
        ("window_results.csv", "종목별 창 결과"),
        ("portfolio_results.csv", "포트폴리오 창 결과"),
        ("aggregates.csv", "모델·길이별 집계"),
        ("stock_aggregates.csv", "종목별 집계"),
        ("regime_aggregates.csv", "시장 국면별 집계"),
        ("windows.csv", "창 정의"),
        ("models.json", "모델 정의"),
        ("walk_forward_selections.csv", "워크포워드 선택"),
        ("trade_log.csv", "전체 거래 로그"),
        ("stock_equity_selected.csv.gz", "선택 창 종목 평가금액"),
        ("069500_prices.csv", "ETF 기준 가격"),
        ("benchmark_manifest.json", "ETF 수집 명세"),
        ("inputs_manifest.json", "입력 자료 명세"),
        ("verification.json", "검증 결과"),
        ("results.json", "리포트 전체 입력"),
    ]
    links = "".join(f'<a href="{escape(data_href)}/{escape(filename)}" download>{escape(label)} <span class="muted">({escape(filename)})</span></a>' for filename, label in files)
    return (
        '<section class="panel" id="downloads"><h2>근거 데이터와 재현 자료</h2><p>표와 차트의 근거를 파일 단위로 확인할 수 있습니다. 압축 파일을 공유할 때는 폴더 구조를 유지하면 로컬 브라우저에서도 링크가 작동합니다.</p>'
        f'<div class="downloads">{links}<a href="rolling-mixed-backtest-{escape(report_date)}.zip" download>전체 HTML·CSV·JSON ZIP</a></div>'
        '<p class="muted">stock_equity_selected.csv.gz에는 전체 기간, 최근 5일, 각 길이의 최신 창에 대한 종목별 평가금액만 담습니다. 전체 창 결과는 window_results.csv와 portfolio_results.csv에서 확인하세요.</p></section>'
    )


def render(
    data: Mapping[str, Any],
    data_href: str | None = None,
    *,
    report_date: str | None = None,
) -> str:
    models = model_index(data)
    meta = data.get("metadata", {})
    report_date = str(report_date or meta.get("as_of") or REPORT_DATE)
    data_href = data_href or f"../rolling-backtests/{report_date}"
    body = executive_section(data, models)
    body += stock_explorer_section(data)
    body += full_period_section(data, models)
    body += single_vs_mix_section(data, models)
    body += aggregate_section(data, models)
    body += window_detail_section(data, models)
    body += recent_section(data, models, report_date=report_date)
    body += regime_section(data, models)
    body += walk_forward_section(data, models)
    body += stock_section(data, models)
    body += model_definition_section(data, models)
    body += methodology_section(data)
    body += download_section(data_href, report_date=report_date)
    generated_at = str(meta.get('generated_at', ''))
    try:
        generated_at = datetime.fromisoformat(generated_at).astimezone(ZoneInfo('Asia/Seoul')).strftime('%Y.%m.%d %H:%M KST')
    except ValueError:
        pass
    subtitle = (
        f'{escape(str(meta.get("eligible_start", "")))}~{escape(str(meta.get("as_of", "")))} · '
        f'{len(models)}개 단일·혼합 모델 · 비용 반영 · 생성 {escape(generated_at)}'
    )
    stock_count = len({str(row.get("symbol")) for row in data.get("stock_results", []) if row.get("symbol")})
    nav = "".join(
        f'<a href="#{anchor}">{label}</a>'
        for anchor, label in [
            ("summary", "핵심 결론"), ("stock-explorer", "기간·종목 탐색"), ("full", "전체 기간"), ("mix", "단일 vs 혼합"), ("distribution", "창 분포"),
            ("window-details", "기간별 상세"),
            ("recent", "최근 구간"), ("regime", "시장 국면"), ("walk-forward", "워크포워드"),
            ("stocks", "종목별"), ("method", "계산 기준"), ("downloads", "다운로드"),
        ]
    )
    return (
        '<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<meta name="description" content="{stock_count}개 주요 종목의 슬라이딩 윈도우 단일·혼합 전략 백테스트 리포트">'
        f'<title>슬라이딩 윈도우·다중 전략 검증</title><style>{CSS}</style></head><body><main><nav><a href="index.html">리포트 목록</a>'
        f'{nav}</nav><header class="hero"><span class="eyebrow">Rolling window &amp; multi-strategy validation</span><h1>슬라이딩 윈도우·다중 전략 검증</h1><p>{subtitle}</p></header>'
        f'{body}<footer>출처: 이 프로젝트가 수집한 KIS 수정주가·투자자별 일별 수급 및 지정 ETF 가격, 기존 전략 신호와 백테스트 규칙. 이 문서는 과거 시뮬레이션 분석이며 실제 체결 성과나 미래 수익을 보장하지 않습니다.</footer></main><script>{JS}</script></body></html>'
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--data-href")
    parser.add_argument("--report-date", help="보고서/공유 파일 날짜. 생략하면 metadata.as_of를 사용합니다.")
    args = parser.parse_args()

    input_path = args.input_dir / "results.json"
    data = json.loads(input_path.read_text(encoding="utf-8"))
    verification_path = args.input_dir / "verification.json"
    if verification_path.exists():
        data["_verification"] = json.loads(verification_path.read_text(encoding="utf-8"))
    report_date = str(args.report_date or data.get("metadata", {}).get("as_of") or REPORT_DATE)
    output = args.output or Path(f"data/reports/rolling-mixed-backtest-{report_date}.html")
    data_href = args.data_href or f"../rolling-backtests/{report_date}"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render(data, data_href, report_date=report_date), encoding="utf-8")
    print(output.resolve())


if __name__ == "__main__":
    main()
