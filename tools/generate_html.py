"""
generate_html.py - tc.db → index.html 교육용 시뮬레이터 생성기

DB에서 TC 데이터를 읽어 인터랙티브 HTML 페이지를 생성합니다.
"""
import sqlite3
import os
import json
import re

BASE = os.path.join(os.path.dirname(__file__), '..')
DB_PATH = os.path.join(BASE, 'tc.db')
OUT_PATH = os.path.join(BASE, 'index.html')

# 세대별 색상
GEN_COLORS = {
    '2G':         '#6b7280',
    '3G':         '#7c3aed',
    '4G':         '#2563eb',
    '5G':         '#059669',
    '5G-NSA':     '#0891b2',
    'NTN':        '#dc2626',
    'USIM':       '#d97706',
    'IMS-LTE':    '#e11d48',   # VoLTE (LTE 기반 IMS)
    'IMS-NR':     '#c026d3',   # VoNR (NR 기반 IMS)
    'IMS-IRAT':   '#9333ea',   # IMS IRAT
    'IMS-WLAN':   '#0ea5e9',   # IMS over WLAN
    'MCPTT':      '#b45309',   # 공공안전 PTT
    'Positioning':'#16a34a',   # GPS/LTE Positioning
}

# 카테고리 한국어
CAT_KO = {
    'RRC':        'RRC',
    'NAS':        'NAS',
    'Security':   '보안/인증',
    'MAC':        'MAC',
    'RLC':        'RLC',
    'PDCP':       'PDCP',
    'SDAP':       'SDAP',
    'L2':         'L2 (MAC/RLC/PDCP)',
    'IdleMode':   '아이들 모드',
    'IMS':        'IMS/음성',
    'Service':    '서비스',
    'CA':         'CA/밴드',
    'Barring':    '접속 제어',
    'UAC':        'UAC',
    'NTN':        'NTN (위성)',
    'SupService': '보충서비스',
    'Emergency':  '긴급통화',
    'eCall':      'eCall',
    'eDRX':       'eDRX',
    'UECap':      'UE 능력',
    'IMS':        'IMS/VoLTE/VoNR',
    'MCPTT':      'MCPTT (공공안전)',
    'Positioning':'Positioning (측위)',
    'Other':      '기타',
    'Unknown':    '미분류',
}


def load_tcs(conn):
    cur = conn.cursor()
    cur.execute("""
        SELECT id, short_name, generation, category, conf_spec, core_specs,
               is_error_case, ie_status, usim_interface, auth_algo, raw_ttcn3_id
        FROM tcs
        ORDER BY generation, category, id
    """)
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall()
    return [dict(zip(cols, r)) for r in rows]


def load_steps(conn):
    """tc_steps 테이블 → tc_id별 딕셔너리 {tc_id: [steps]}"""
    cur = conn.cursor()
    cur.execute("""
        SELECT tc_id, step_no, from_entity, to_entity, message, direction, layer,
               timer_start, timer_stop, note
        FROM tc_steps
        ORDER BY tc_id, step_no
    """)
    steps = {}
    for row in cur.fetchall():
        tc_id = row[0]
        step = {
            'no': row[1],
            'from': row[2],
            'to': row[3],
            'msg': row[4],
            'dir': row[5],
            'layer': row[6],
            'timerStart': row[7],
            'timerStop': row[8],
            'note': row[9],
        }
        steps.setdefault(tc_id, []).append(step)
    return steps


def build_html(tcs, steps=None):
    # 세대/카테고리 집계
    gen_counts = {}
    cat_counts = {}
    error_count = sum(1 for t in tcs if t['is_error_case'])

    for t in tcs:
        g = t['generation'] or 'Unknown'
        c = t['category'] or 'Unknown'
        gen_counts[g] = gen_counts.get(g, 0) + 1
        cat_counts[c] = cat_counts.get(c, 0) + 1

    if steps is None:
        steps = {}

    # TC 데이터 JSON (검색/필터용)
    tc_json = json.dumps([
        {
            'id': t['id'],
            'name': t['short_name'] or t['raw_ttcn3_id'] or t['id'],
            'gen': t['generation'],
            'cat': t['category'],
            'spec': t['conf_spec'],
            'err': bool(t['is_error_case']),
            'auth': t['usim_interface'],
            'steps': steps.get(t['id'], []),
        }
        for t in tcs
    ], ensure_ascii=False)

    # 세대 필터 옵션 HTML
    gen_opts = ''.join(
        f'<button class="filter-btn" data-gen="{g}" style="--c:{GEN_COLORS.get(g,"#6b7280")}">'
        f'{g} <span class="badge">{n}</span></button>'
        for g, n in sorted(gen_counts.items())
    )

    # 카테고리 필터 옵션 HTML
    cat_opts = ''.join(
        f'<option value="{c}">{CAT_KO.get(c, c)} ({n})</option>'
        for c, n in sorted(cat_counts.items(), key=lambda x: -x[1])
    )

    # TC 카드 HTML (처음 200개만 초기 렌더링, 나머지는 JS로 동적 생성)
    tc_cards = ''
    for t in tcs[:200]:
        color = GEN_COLORS.get(t['generation'], '#6b7280')
        name = t['short_name'] or t['raw_ttcn3_id'] or t['id']
        err_badge = '<span class="err-badge">ERROR</span>' if t['is_error_case'] else ''
        auth_badge = f'<span class="auth-badge">{t["usim_interface"]}</span>' if t['usim_interface'] else ''
        cat_ko = CAT_KO.get(t['category'], t['category'] or '')
        tc_cards += f'''
        <div class="tc-card" data-gen="{t['generation']}" data-cat="{t['category']}"
             data-err="{int(bool(t['is_error_case']))}" data-id="{t['id']}"
             onclick="showTcDetail('{t['id']}')">
          <div class="tc-header" style="border-left: 4px solid {color}">
            <div class="tc-meta">
              <span class="gen-tag" style="background:{color}">{t['generation']}</span>
              <span class="cat-tag">{cat_ko}</span>
              {err_badge}{auth_badge}
            </div>
            <div class="tc-id">{t['id']}</div>
            <div class="tc-name">{name}</div>
          </div>
        </div>'''

    total = len(tcs)
    with_title = sum(1 for t in tcs if t['short_name'])
    total_steps = sum(len(v) for v in steps.values())
    tc_with_steps = len(steps)

    return f'''<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>3GPP Protocol Simulator — 신입 모뎀 개발자 교육</title>
<style>
:root {{
  --bg: #0f172a;
  --bg2: #1e293b;
  --bg3: #334155;
  --text: #f1f5f9;
  --text2: #94a3b8;
  --border: #334155;
  --accent: #3b82f6;
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ background: var(--bg); color: var(--text); font-family: 'Segoe UI', system-ui, sans-serif; }}

/* Header */
.header {{ background: var(--bg2); border-bottom: 1px solid var(--border); padding: 16px 24px; }}
.header h1 {{ font-size: 1.25rem; font-weight: 700; }}
.header p {{ color: var(--text2); font-size: 0.875rem; margin-top: 4px; }}

/* Stats bar */
.stats-bar {{ display: flex; gap: 24px; padding: 12px 24px; background: var(--bg2); border-bottom: 1px solid var(--border); overflow-x: auto; }}
.stat {{ text-align: center; min-width: 80px; }}
.stat-num {{ font-size: 1.5rem; font-weight: 700; color: var(--accent); }}
.stat-label {{ font-size: 0.75rem; color: var(--text2); }}

/* Filters */
.filters {{ padding: 16px 24px; background: var(--bg2); border-bottom: 1px solid var(--border); display: flex; flex-wrap: wrap; gap: 12px; align-items: center; }}
.filter-group {{ display: flex; gap: 8px; flex-wrap: wrap; }}
.filter-btn {{ padding: 6px 14px; border-radius: 20px; border: 2px solid var(--c, #6b7280); background: transparent; color: var(--text); cursor: pointer; font-size: 0.8rem; transition: all 0.15s; }}
.filter-btn:hover, .filter-btn.active {{ background: var(--c, #6b7280); }}
.badge {{ background: rgba(255,255,255,0.2); border-radius: 10px; padding: 1px 6px; font-size: 0.7rem; margin-left: 4px; }}
.filter-btn.all {{ --c: #64748b; }}
select {{ background: var(--bg3); color: var(--text); border: 1px solid var(--border); border-radius: 6px; padding: 6px 10px; font-size: 0.8rem; }}
input[type=text] {{ background: var(--bg3); color: var(--text); border: 1px solid var(--border); border-radius: 6px; padding: 6px 12px; font-size: 0.875rem; width: 260px; }}
input[type=text]::placeholder {{ color: var(--text2); }}
.toggle-btn {{ padding: 6px 14px; border-radius: 6px; border: 1px solid #ef4444; background: transparent; color: #ef4444; cursor: pointer; font-size: 0.8rem; }}
.toggle-btn.active {{ background: #ef4444; color: white; }}

/* Grid */
.grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 12px; padding: 20px 24px; }}

/* TC Card */
.tc-card {{ background: var(--bg2); border-radius: 8px; cursor: pointer; transition: transform 0.15s, box-shadow 0.15s; overflow: hidden; }}
.tc-card:hover {{ transform: translateY(-2px); box-shadow: 0 4px 20px rgba(0,0,0,0.4); }}
.tc-header {{ padding: 14px 16px; }}
.tc-meta {{ display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 8px; }}
.gen-tag {{ padding: 2px 8px; border-radius: 4px; font-size: 0.7rem; font-weight: 700; color: white; }}
.cat-tag {{ padding: 2px 8px; border-radius: 4px; font-size: 0.7rem; background: var(--bg3); color: var(--text2); }}
.err-badge {{ padding: 2px 8px; border-radius: 4px; font-size: 0.7rem; background: #dc2626; color: white; font-weight: 700; }}
.auth-badge {{ padding: 2px 8px; border-radius: 4px; font-size: 0.7rem; background: #d97706; color: white; }}
.tc-id {{ font-family: 'Courier New', monospace; font-size: 0.75rem; color: var(--accent); margin-bottom: 4px; }}
.tc-name {{ font-size: 0.875rem; font-weight: 600; line-height: 1.4; }}

/* Count display */
.result-count {{ padding: 8px 24px; color: var(--text2); font-size: 0.875rem; }}

/* Modal */
.modal-overlay {{ display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.7); z-index: 100; align-items: center; justify-content: center; }}
.modal-overlay.open {{ display: flex; }}
.modal {{ background: var(--bg2); border-radius: 12px; width: 90%; max-width: 700px; max-height: 85vh; overflow-y: auto; padding: 28px; border: 1px solid var(--border); }}
.modal-header {{ display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px; }}
.modal-title {{ font-size: 1.1rem; font-weight: 700; line-height: 1.4; }}
.modal-close {{ background: none; border: none; color: var(--text2); font-size: 1.5rem; cursor: pointer; padding: 0 4px; }}
.modal-spec {{ font-family: monospace; font-size: 0.8rem; color: var(--accent); margin-bottom: 16px; padding: 8px 12px; background: var(--bg); border-radius: 6px; }}
.info-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 20px; }}
.info-item label {{ font-size: 0.75rem; color: var(--text2); display: block; margin-bottom: 4px; }}
.info-item span {{ font-size: 0.875rem; }}
/* Steps sequence */
.seq-diagram-wrap {{
  overflow-x: auto;
  background: #0a0f1e;
  border-radius: 8px;
  border: 1px solid var(--border);
  padding: 0;
  margin-top: 4px;
}}
.seq-svg {{ display: block; }}
.steps-title {{ font-weight: 700; margin-bottom: 12px; color: var(--text2); font-size: 0.875rem; display: flex; justify-content: space-between; align-items: center; }}
.steps-badge {{ font-size: 0.7rem; background: var(--bg3); padding: 2px 8px; border-radius: 10px; }}
.step-placeholder {{ color: var(--text2); font-size: 0.875rem; padding: 16px; background: var(--bg); border-radius: 6px; text-align: center; }}
.no-steps {{ color: var(--text2); font-size: 0.8rem; padding: 12px; text-align: center; background: var(--bg); border-radius: 6px; }}
</style>
</head>
<body>

<div class="header">
  <h1>3GPP Protocol Simulator</h1>
  <p>신입 모뎀 개발자를 위한 인터랙티브 프로토콜 시뮬레이터 — 3GPP 공식 TTCN-3 스펙에서 직접 추출</p>
</div>

<div class="stats-bar">
  <div class="stat"><div class="stat-num">{total}</div><div class="stat-label">전체 TC</div></div>
  <div class="stat"><div class="stat-num">{with_title}</div><div class="stat-label">제목 확보</div></div>
  <div class="stat"><div class="stat-num">{error_count}</div><div class="stat-label">에러 케이스</div></div>
  <div class="stat"><div class="stat-num">{tc_with_steps}</div><div class="stat-label">시퀀스 있는 TC</div></div>
  <div class="stat"><div class="stat-num">{total_steps}</div><div class="stat-label">총 스텝 수</div></div>
  <div class="stat"><div class="stat-num">{gen_counts.get('4G', 0)}</div><div class="stat-label">4G LTE</div></div>
  <div class="stat"><div class="stat-num">{gen_counts.get('5G', 0)}</div><div class="stat-label">5G NR SA</div></div>
  <div class="stat"><div class="stat-num">{gen_counts.get('5G-NSA', 0)}</div><div class="stat-label">5G EN-DC</div></div>
  <div class="stat"><div class="stat-num">{gen_counts.get('3G', 0)}</div><div class="stat-label">3G UMTS</div></div>
</div>

<div class="filters">
  <div class="filter-group">
    <button class="filter-btn all active" data-gen="all">전체 <span class="badge">{total}</span></button>
    {gen_opts}
  </div>
  <select id="catFilter" onchange="applyFilters()">
    <option value="">모든 카테고리</option>
    {cat_opts}
  </select>
  <button class="toggle-btn" id="errToggle" onclick="toggleError()">⚠️ 에러 케이스만</button>
  <input type="text" id="searchInput" placeholder="TC 검색... (ID, 제목)" oninput="applyFilters()">
</div>

<div class="result-count" id="resultCount">전체 {total}개 표시 중</div>

<div class="grid" id="tcGrid">
  {tc_cards}
  <div id="loadMore" style="grid-column:1/-1;text-align:center;padding:20px">
    <button onclick="loadMoreCards()" style="background:var(--bg3);border:1px solid var(--border);color:var(--text);padding:10px 24px;border-radius:6px;cursor:pointer">
      더 보기 ({total - 200}개 추가)
    </button>
  </div>
</div>

<!-- 상세 모달 -->
<div class="modal-overlay" id="modalOverlay" onclick="closeModal(event)">
  <div class="modal" id="modalContent">
    <div class="modal-header">
      <div class="modal-title" id="modalTitle"></div>
      <button class="modal-close" onclick="closeModalBtn()">×</button>
    </div>
    <div class="modal-spec" id="modalSpec"></div>
    <div class="info-grid" id="modalInfo"></div>
    <div class="steps-title">
      메시지 시퀀스
      <span class="steps-badge" id="stepsCountBadge"></span>
    </div>
    <div id="modalSteps"></div>
  </div>
</div>

<script>
const TC_DATA = {tc_json};
const GEN_COLORS = {json.dumps(GEN_COLORS)};
const CAT_KO = {json.dumps(CAT_KO, ensure_ascii=False)};

let activeGen = 'all';
let showErrorOnly = false;
let renderedCount = 200;

// 필터링된 TC 목록
function getFiltered() {{
  const cat = document.getElementById('catFilter').value;
  const q = document.getElementById('searchInput').value.toLowerCase();
  return TC_DATA.filter(t => {{
    if (activeGen !== 'all' && t.gen !== activeGen) return false;
    if (cat && t.cat !== cat) return false;
    if (showErrorOnly && !t.err) return false;
    if (q && !t.id.toLowerCase().includes(q) && !(t.name||'').toLowerCase().includes(q)) return false;
    return true;
  }});
}}

function renderCards(tcs, limit) {{
  const grid = document.getElementById('tcGrid');
  const loadMore = document.getElementById('loadMore');
  grid.innerHTML = '';
  
  const visible = tcs.slice(0, limit);
  visible.forEach(t => {{
    const color = GEN_COLORS[t.gen] || '#6b7280';
    const catKo = CAT_KO[t.cat] || t.cat || '';
    const errBadge = t.err ? '<span class="err-badge">ERROR</span>' : '';
    const authBadge = t.auth ? `<span class="auth-badge">${{t.auth}}</span>` : '';
    const div = document.createElement('div');
    div.className = 'tc-card';
    div.dataset.id = t.id;
    div.onclick = () => showTcDetail(t.id);
    div.innerHTML = `
      <div class="tc-header" style="border-left:4px solid ${{color}}">
        <div class="tc-meta">
          <span class="gen-tag" style="background:${{color}}">${{t.gen}}</span>
          <span class="cat-tag">${{catKo}}</span>
          ${{errBadge}}${{authBadge}}
        </div>
        <div class="tc-id">${{t.id}}</div>
        <div class="tc-name">${{t.name || t.id}}</div>
      </div>`;
    grid.appendChild(div);
  }});
  
  if (tcs.length > limit) {{
    const btn = document.createElement('div');
    btn.style.cssText = 'grid-column:1/-1;text-align:center;padding:20px';
    btn.innerHTML = `<button onclick="loadMoreCards()" style="background:var(--bg3);border:1px solid var(--border);color:var(--text);padding:10px 24px;border-radius:6px;cursor:pointer">더 보기 (${{tcs.length - limit}}개 추가)</button>`;
    grid.appendChild(btn);
  }}
  
  document.getElementById('resultCount').textContent = `${{tcs.length}}개 중 ${{Math.min(limit, tcs.length)}}개 표시 중`;
}}

window._currentFiltered = TC_DATA;

function applyFilters() {{
  const filtered = getFiltered();
  window._currentFiltered = filtered;
  renderedCount = 100;
  renderCards(filtered, renderedCount);
}}

function loadMoreCards() {{
  renderedCount += 100;
  renderCards(window._currentFiltered, renderedCount);
}}

// 세대 필터
document.querySelectorAll('.filter-btn').forEach(btn => {{
  btn.addEventListener('click', () => {{
    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    activeGen = btn.dataset.gen;
    applyFilters();
  }});
}});

function toggleError() {{
  showErrorOnly = !showErrorOnly;
  document.getElementById('errToggle').classList.toggle('active', showErrorOnly);
  applyFilters();
}}

// TC 상세 모달
function showTcDetail(id) {{
  const tc = TC_DATA.find(t => t.id === id);
  if (!tc) return;
  const color = GEN_COLORS[tc.gen] || '#6b7280';
  
  document.getElementById('modalTitle').innerHTML =
    `<span style="color:${{color}}">${{tc.gen}}</span> · ${{tc.name || id}}`;
  document.getElementById('modalSpec').textContent = tc.spec || id;
  
  const info = [
    ['TC ID', id],
    ['세대', tc.gen],
    ['카테고리', CAT_KO[tc.cat] || tc.cat || '—'],
    ['에러 케이스', tc.err ? '⚠️ Yes' : 'No'],
    ['인증 방식', tc.auth || '—'],
    ['TTCN-3 ID', id.replace(/^[\\w-]+-([\\d].*)/, '$1').replace(/\\./g, '_')],
  ];
  
  document.getElementById('modalInfo').innerHTML = info.map(([l, v]) =>
    `<div class="info-item"><label>${{l}}</label><span>${{v}}</span></div>`
  ).join('');
  
  // 메시지 시퀀스 렌더링
  const stepsEl = document.getElementById('modalSteps');
  const badgeEl = document.getElementById('stepsCountBadge');
  const steps = tc.steps || [];
  
  if (steps.length === 0) {{
    badgeEl.textContent = '0 steps';
    stepsEl.innerHTML = '<div class="no-steps">이 TC의 시퀀스 데이터가 없습니다.<br><small>공통 절차 참조 또는 파싱 불가 케이스일 수 있습니다.</small></div>';
  }} else {{
    badgeEl.textContent = `${{steps.length}} steps`;
    stepsEl.innerHTML = renderSteps(steps);
  }}
  
  document.getElementById('modalOverlay').classList.add('open');
}}

function renderSteps(steps) {{
  // ── 엔티티 정규화 ──────────────────────────────────
  const ENTITY_ORDER = ['UE', 'eNB/gNB', 'SS', 'MME/AMF', 'P-CSCF', 'Server'];
  const ENTITY_STYLE = {{
    'UE':      {{ fill: '#1e3a5f', stroke: '#3b82f6', text: '#93c5fd', label: 'UE' }},
    'eNB/gNB': {{ fill: '#1a3a1a', stroke: '#22c55e', text: '#86efac', label: 'eNB/gNB' }},
    'SS':      {{ fill: '#2a2a1a', stroke: '#eab308', text: '#fde047', label: 'SS' }},
    'MME/AMF': {{ fill: '#3a1a1a', stroke: '#ef4444', text: '#fca5a5', label: 'MME/AMF' }},
    'P-CSCF':  {{ fill: '#2a1a3a', stroke: '#a855f7', text: '#d8b4fe', label: 'P-CSCF' }},
    'Server':  {{ fill: '#1a2a3a', stroke: '#06b6d4', text: '#67e8f9', label: 'Server'  }},
  }};
  const DEFAULT_STYLE = {{ fill: '#1e293b', stroke: '#64748b', text: '#94a3b8', label: '?' }};

  // 참여 엔티티 수집 (순서 고정)
  const usedSet = new Set();
  steps.forEach(s => {{ usedSet.add(s.from); usedSet.add(s.to); }});
  const entities = ENTITY_ORDER.filter(e => usedSet.has(e));
  // 미등록 엔티티 뒤에 추가
  usedSet.forEach(e => {{ if (!ENTITY_ORDER.includes(e)) entities.push(e); }});

  // ── SVG 레이아웃 상수 ──────────────────────────────
  const COL_W   = 160;   // 엔티티 열 폭
  const PAD_L   = 40;    // 좌측 여백 (스텝 번호)
  const PAD_R   = 16;    // 우측 여백
  const BOX_H   = 44;    // 엔티티 박스 높이
  const BOX_W   = 110;   // 엔티티 박스 너비
  const ROW_H   = 46;    // 스텝 행 높이
  const NOTE_H  = 14;    // 노트 줄 높이 (노트 있을 때 추가)
  const ARROW_Y = 22;    // 행 내 화살표 y 위치
  const MSG_Y   = 14;    // 행 내 메시지 라벨 y 위치

  const N = entities.length;
  const SVG_W = PAD_L + N * COL_W + PAD_R;

  // 각 엔티티 중심 x
  const cx = i => PAD_L + i * COL_W + COL_W / 2;

  // 각 스텝의 실제 높이 계산
  const rowHeights = steps.map(s => ROW_H + (s.note ? NOTE_H : 0));
  const totalRows = rowHeights.reduce((a, b) => a + b, 0);
  const SVG_H = BOX_H + totalRows + 20;

  // ── SVG 생성 ──────────────────────────────────────
  let svg = `<svg class="seq-svg" width="${{SVG_W}}" height="${{SVG_H}}" viewBox="0 0 ${{SVG_W}} ${{SVG_H}}" xmlns="http://www.w3.org/2000/svg">
<defs>
  <marker id="arr-dl" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto">
    <path d="M0,0 L0,6 L8,3 z" fill="#60a5fa"/>
  </marker>
  <marker id="arr-ul" markerWidth="8" markerHeight="8" refX="1" refY="3" orient="auto">
    <path d="M8,0 L8,6 L0,3 z" fill="#34d399"/>
  </marker>
  <marker id="arr-int" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">
    <path d="M0,0 L0,6 L6,3 z" fill="#64748b"/>
  </marker>
</defs>`;

  // 배경
  svg += `<rect width="${{SVG_W}}" height="${{SVG_H}}" fill="#0a0f1e"/>`;

  // 엔티티 박스 + 라이프라인
  entities.forEach((e, i) => {{
    const style = ENTITY_STYLE[e] || DEFAULT_STYLE;
    const x = cx(i);
    const boxX = x - BOX_W / 2;

    // 라이프라인 (세로 점선)
    svg += `<line x1="${{x}}" y1="${{BOX_H}}" x2="${{x}}" y2="${{SVG_H - 10}}"
      stroke="${{style.stroke}}" stroke-width="1" stroke-dasharray="4,4" opacity="0.4"/>`;

    // 엔티티 박스
    svg += `<rect x="${{boxX}}" y="4" width="${{BOX_W}}" height="${{BOX_H - 8}}"
      rx="6" fill="${{style.fill}}" stroke="${{style.stroke}}" stroke-width="1.5"/>`;

    // 엔티티 레이블
    svg += `<text x="${{x}}" y="${{BOX_H / 2 + 2}}" text-anchor="middle" dominant-baseline="middle"
      font-family="'Segoe UI',system-ui,sans-serif" font-size="12" font-weight="700"
      fill="${{style.text}}">${{style.label}}</text>`;
  }});

  // ── 스텝 행 ──────────────────────────────────────
  let y = BOX_H;
  steps.forEach((s, idx) => {{
    const rh = rowHeights[idx];
    const ay = y + ARROW_Y;   // 화살표 y
    const my = y + MSG_Y;     // 메시지 라벨 y

    const fromIdx = entities.indexOf(s.from);
    const toIdx   = entities.indexOf(s.to);
    const dir     = s.dir || 'int';
    const msg     = (s.msg || '').replace(/_/g, ' ');

    // 줄무늬 배경 (짝수/홀수)
    const rowFill = idx % 2 === 0 ? 'rgba(255,255,255,0.02)' : 'transparent';
    svg += `<rect x="0" y="${{y}}" width="${{SVG_W}}" height="${{rh}}" fill="${{rowFill}}"/>`;

    // 스텝 번호
    svg += `<text x="28" y="${{ay + 4}}" text-anchor="end" font-family="monospace"
      font-size="10" fill="#475569">${{s.no}}</text>`;

    if (dir === 'int' || fromIdx === toIdx || fromIdx < 0 || toIdx < 0) {{
      // 내부/unknown → 점선 self-loop 또는 note box
      const bx = PAD_L + (fromIdx >= 0 ? fromIdx : 0) * COL_W + 10;
      svg += `<line x1="${{bx}}" y1="${{ay}}" x2="${{SVG_W - PAD_R}}" y2="${{ay}}"
        stroke="#334155" stroke-width="1" stroke-dasharray="3,3"/>`;
      if (msg) {{
        svg += `<text x="${{bx + 6}}" y="${{my}}" font-family="'Segoe UI',system-ui,sans-serif"
          font-size="10" fill="#64748b" font-style="italic"
          clip-path="url(#clipRow)">${{escXml(truncate(msg, 50))}}</text>`;
      }}
    }} else {{
      // 실제 화살표
      const x1 = cx(fromIdx);
      const x2 = cx(toIdx);
      const arrowColor = dir === 'dl' ? '#60a5fa' : '#34d399';
      const markerId  = dir === 'dl' ? 'arr-dl' : 'arr-ul';
      const layerColor = dir === 'dl' ? '#1e3a5f' : '#14532d';

      // 화살표 선
      svg += `<line x1="${{x1}}" y1="${{ay}}" x2="${{x2}}" y2="${{ay}}"
        stroke="${{arrowColor}}" stroke-width="2" marker-end="url(#${{markerId}})"/>`;

      // 레이어 뱃지 (RRC/NAS/PDCP)
      if (s.layer && s.layer !== 'internal') {{
        const midX = (x1 + x2) / 2;
        const bw = 36;
        svg += `<rect x="${{midX - bw/2}}" y="${{ay - 17}}" width="${{bw}}" height="13"
          rx="3" fill="${{layerColor}}" stroke="${{arrowColor}}" stroke-width="0.5" opacity="0.8"/>`;
        svg += `<text x="${{midX}}" y="${{ay - 7}}" text-anchor="middle"
          font-family="monospace" font-size="9" font-weight="700" fill="${{arrowColor}}">${{s.layer}}</text>`;
      }}

      // 메시지 이름 (화살표 위)
      if (msg) {{
        const midX = (x1 + x2) / 2;
        const available = Math.abs(x2 - x1) - 20;
        const truncMsg = truncatePx(msg, available);
        svg += `<text x="${{midX}}" y="${{my}}" text-anchor="middle"
          font-family="'Segoe UI',system-ui,sans-serif" font-size="11" font-weight="600"
          fill="${{arrowColor}}">${{escXml(truncMsg)}}</text>`;
      }}
    }}

    // 노트 (하단 작은 글씨)
    if (s.note) {{
      const noteY = y + ROW_H + 2;
      svg += `<text x="${{PAD_L + 8}}" y="${{noteY + 10}}" font-family="'Segoe UI',system-ui,sans-serif"
        font-size="9.5" fill="#475569" font-style="italic">${{escXml(truncate(s.note, 90))}}</text>`;
    }}

    // 타이머 표시
    if (s.timerStart) {{
      const tx = SVG_W - PAD_R - 4;
      svg += `<text x="${{tx}}" y="${{ay + 4}}" text-anchor="end" font-family="monospace"
        font-size="9" fill="#fbbf24">⏱ ${{s.timerStart.split(',')[0]}}</text>`;
    }}

    y += rh;
  }});

  svg += `</svg>`;
  return `<div class="seq-diagram-wrap">${{svg}}</div>`;
}}

// 유틸리티
function escXml(s) {{
  return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}}
function truncate(s, n) {{
  return s.length > n ? s.slice(0, n) + '…' : s;
}}
function truncatePx(s, px) {{
  // 대략 1자 = 6.5px (11px font) 기준
  const maxChars = Math.max(4, Math.floor(px / 6.5));
  return truncate(s, maxChars);
}}

function closeModal(e) {{
  if (e.target === document.getElementById('modalOverlay'))
    document.getElementById('modalOverlay').classList.remove('open');
}}

function closeModalBtn() {{
  document.getElementById('modalOverlay').classList.remove('open');
}}

document.addEventListener('keydown', e => {{
  if (e.key === 'Escape') document.getElementById('modalOverlay').classList.remove('open');
}});
</script>
</body>
</html>'''


def main():
    if not os.path.exists(DB_PATH):
        print("❌ tc.db 없음. 먼저 python tools/init_db.py 실행")
        return

    conn = sqlite3.connect(DB_PATH)
    tcs = load_tcs(conn)
    steps = load_steps(conn)
    conn.close()

    html = build_html(tcs, steps)

    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        f.write(html)

    size_kb = os.path.getsize(OUT_PATH) // 1024
    print(f"✅ index.html 생성 완료")
    print(f"   TC 수: {len(tcs)}개")
    print(f"   시퀀스 있는 TC: {len(steps)}개 ({sum(len(v) for v in steps.values())}개 스텝)")
    print(f"   파일 크기: {size_kb}KB")
    print(f"   경로: {OUT_PATH}")


if __name__ == '__main__':
    main()
