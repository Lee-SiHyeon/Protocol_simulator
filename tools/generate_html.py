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
    '2G':     '#6b7280',
    '3G':     '#7c3aed',
    '4G':     '#2563eb',
    '5G':     '#059669',
    '5G-NSA': '#0891b2',
    'NTN':    '#dc2626',
    'USIM':   '#d97706',
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


def build_html(tcs):
    # 세대/카테고리 집계
    gen_counts = {}
    cat_counts = {}
    error_count = sum(1 for t in tcs if t['is_error_case'])

    for t in tcs:
        g = t['generation'] or 'Unknown'
        c = t['category'] or 'Unknown'
        gen_counts[g] = gen_counts.get(g, 0) + 1
        cat_counts[c] = cat_counts.get(c, 0) + 1

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
.steps-title {{ font-weight: 700; margin-bottom: 12px; color: var(--text2); font-size: 0.875rem; }}
.step-placeholder {{ color: var(--text2); font-size: 0.875rem; padding: 16px; background: var(--bg); border-radius: 6px; text-align: center; }}
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
    <div class="steps-title">메시지 시퀀스</div>
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
  
  document.getElementById('modalSteps').innerHTML =
    `<div class="step-placeholder">메시지 시퀀스 데이터를 로드하려면 tc_steps 테이블을 채워야 합니다.<br>
     <code style="font-size:0.8rem;color:var(--accent)">python tools/extract_procedures.py</code> 실행 후 재생성하세요.</div>`;
  
  document.getElementById('modalOverlay').classList.add('open');
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
    conn.close()

    html = build_html(tcs)

    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        f.write(html)

    size_kb = os.path.getsize(OUT_PATH) // 1024
    print(f"✅ index.html 생성 완료")
    print(f"   TC 수: {len(tcs)}개")
    print(f"   파일 크기: {size_kb}KB")
    print(f"   경로: {OUT_PATH}")


if __name__ == '__main__':
    main()
