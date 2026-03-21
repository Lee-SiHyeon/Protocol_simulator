"""
extract_procedures.py - TTCN-3 구현 파일에서 메시지 시퀀스 추출 → tc_steps 테이블

전략:
  1. 모든 specs/ TTCN-3 파일을 한 번 스캔 → {func_name: file_path} 인덱스 구축
  2. TC ID → 예상 함수명 목록 생성 (suffix 변형 포함)
  3. 인덱스로 파일 조회 → @siclog Step 주석 파싱
  4. 메시지 방향(DL/UL) 추론 → tc_steps INSERT

TTCN-3 패턴:
  //@siclog "Step 1" siclog@
  //The SS transmits an RRCConnectionSetup message.
  SRB.send(cas_SRB0_RrcPdu_REQ(eutra_Cell1, cs_TimingInfo_Now, cs_RRCConnectionSetup_Def));
"""
import re
import sqlite3
import os
import sys
from typing import Optional, List, Tuple, Dict

BASE = os.path.join(os.path.dirname(__file__), '..')
DB_PATH = os.path.join(BASE, 'tc.db')
SPECS_ROOT = os.path.join(BASE, 'specs')

# ─── 메시지 방향 추론 패턴 ───────────────────────────────
# (regex, direction, layer, from_entity, to_entity)
MSG_DIRECTION_PATTERNS = [
    # SRB.send = SS→UE (DL)
    (re.compile(r'\bSRB\.send\b'), 'dl', 'RRC', 'eNB/gNB', 'UE'),
    # SRB.receive = UE→SS (UL)
    (re.compile(r'\bSRB\.receive\b'), 'ul', 'RRC', 'UE', 'eNB/gNB'),
    # DRB.send = SS→UE (DL data)
    (re.compile(r'\bDRB\.send\b'), 'dl', 'PDCP', 'eNB/gNB', 'UE'),
    # DRB.receive = UE→SS (UL data)
    (re.compile(r'\bDRB\.receive\b'), 'ul', 'PDCP', 'UE', 'eNB/gNB'),
    # Paging helpers
    (re.compile(r'\bf_EUTRA_UE_Page\b|\bf_NR_UE_Page\b'), 'dl', 'RRC', 'eNB/gNB', 'UE'),
    # RRC DL helpers
    (re.compile(r'\bf_EUTRA_RRC_ConnectionSetup_Def\b|\bf_NR_RRC_Setup_Def\b'), 'dl', 'RRC', 'eNB/gNB', 'UE'),
    (re.compile(r'\bf_EUTRA_RRC_ConnectionRelease\b|\bf_NR_RRC_Release\b'), 'dl', 'RRC', 'eNB/gNB', 'UE'),
    (re.compile(r'\bf_EUTRA_RRC_SecurityModeCommand_Def\b|\bf_NR_RRC_SecurityModeCommand\b'), 'dl', 'RRC', 'eNB/gNB', 'UE'),
    (re.compile(r'\bf_EUTRA_RRC_ConnectionReconfiguration_Def\b|\bf_NR_RRC_Reconfiguration_Def\b'), 'dl', 'RRC', 'eNB/gNB', 'UE'),
    # RRC UL helpers
    (re.compile(r'\bf_EUTRA_RRC_ConnectionRequest_Def\b|\bf_NR_RRC_ConnectionRequest_Def\b'), 'ul', 'RRC', 'UE', 'eNB/gNB'),
    (re.compile(r'\bf_EUTRA_RRCConnectionSetupComplete_Def\b|\bf_NR_RRCSetupComplete_Def\b'), 'ul', 'RRC', 'UE', 'eNB/gNB'),
    (re.compile(r'\bf_EUTRA_RRC_SecurityModeComplete_Def\b|\bf_NR_RRC_SecurityModeComplete\b'), 'ul', 'RRC', 'UE', 'eNB/gNB'),
    # NAS UL
    (re.compile(r'\bNAS_Ind\b|\bf_EUTRA_NAS_Indication\b'), 'ul', 'NAS', 'UE', 'MME/AMF'),
    # NAS DL
    (re.compile(r'\bNAS_Req\b|\bf_EUTRA_NAS_Request\b'), 'dl', 'NAS', 'MME/AMF', 'UE'),
    # IMS SIP
    (re.compile(r'\bIMS_PORT\.send\b'), 'dl', 'SIP', 'P-CSCF', 'UE'),
    (re.compile(r'\bIMS_PORT\.receive\b'), 'ul', 'SIP', 'UE', 'P-CSCF'),
    # MCPTT
    (re.compile(r'\bMCX_PORT\.send\b'), 'dl', 'MCPTT', 'Server', 'UE'),
    (re.compile(r'\bMCX_PORT\.receive\b'), 'ul', 'MCPTT', 'UE', 'Server'),
]

# 메시지 이름 추출 (cs_/cr_/cas_/car_ 접두사 뒤, 숫자코드 제거)
MSG_NAME_RE = re.compile(r'\b(?:cas_|car_|cs_|cr_|c_)(?:\d+_)?([A-Z][A-Za-z][A-Za-z0-9_]{1,60})')

# 타이머 패턴
TIMER_START_RE = re.compile(r'(\bt_\w+)\.start\(')
TIMER_STOP_RE  = re.compile(r'(\bt_\w+)\.stop\b')

SICLOG_RE = re.compile(r'@siclog\s+"(Steps?\s+[\w][\w\s\-/,\.]*?)"', re.IGNORECASE)
COMMENT_LINE_RE = re.compile(r'^\s*//(.*)')

# ─── 전역 인덱스 ────────────────────────────────────────
# {함수명 소문자: (전체함수명, 파일경로)}
_FUNC_INDEX: Dict[str, Tuple[str, str]] = {}

FUNC_DEF_RE = re.compile(r'\bfunction\s+((?:f|fl)_TC_\w+)\s*\(')


def build_index():
    """specs/ 전체를 스캔해 {func_name_lower: (func_name, file_path)} 인덱스 구축"""
    global _FUNC_INDEX
    if _FUNC_INDEX:
        return  # 이미 빌드됨

    print("📂 TTCN-3 파일 인덱싱 중...")
    count_files = 0
    count_funcs = 0

    for dirpath, dirs, files in os.walk(SPECS_ROOT):
        # 불필요 폴더 건너뜀 (Common, PicsPixit, NR_TC_Common 등)
        dirs[:] = [d for d in dirs if d not in ('PicsPixit', '__pycache__')]
        for fname in files:
            if not fname.endswith('.ttcn'):
                continue
            fpath = os.path.join(dirpath, fname)
            try:
                with open(fpath, encoding='utf-8', errors='replace') as f:
                    content = f.read()
            except Exception:
                continue
            count_files += 1
            for m in FUNC_DEF_RE.finditer(content):
                func_name = m.group(1)
                key = func_name.lower()
                if key not in _FUNC_INDEX:
                    _FUNC_INDEX[key] = (func_name, fpath)
                    count_funcs += 1

    print(f"   {count_files}개 파일 스캔, {count_funcs}개 함수 인덱싱 완료")


def lookup_func(func_name: str) -> Optional[Tuple[str, str]]:
    """인덱스에서 함수명 조회 (대소문자 무시)"""
    return _FUNC_INDEX.get(func_name.lower())


def make_func_candidates(tc_id: str, generation: str) -> List[str]:
    """
    TC ID + generation → 가능한 함수명 후보 목록 반환
    """
    # ── ENDC 특수 패턴: 38523-1-ENDC-7.1.1.1.1 ──
    endc_m = re.match(r'[\w]+-[\w]+-ENDC-([\d\.a-z]+)', tc_id)
    if endc_m:
        suffix = endc_m.group(1).replace('.', '_')
        return [
            f'f_TC_{suffix}_ENDC_EUTRA',
            f'f_TC_{suffix}_ENDC_NR',
            f'f_TC_{suffix}_ENDC',
        ]

    # ── IMS: 34229-1-EUTRA-10.1, 34229-1-NR5GC-10.1 ──
    ims_m = re.match(r'34229-[\w]+-(?:EUTRA|NR5GC|IRAT|WLAN)-([\d\.a-z]+)', tc_id)
    if ims_m:
        suffix = ims_m.group(1).replace('.', '_')
        return [
            f'f_TC_{suffix}_IMS1',
            f'f_TC_{suffix}_IMS2',
            f'f_TC_{suffix}_IMS',
            f'f_TC_{suffix}',
        ]

    # ── MCPTT/MCData: 36579-1-5.1.MCPTT, 36579-1-5.1.MCData ──
    mcx_m = re.match(r'36579-[\w]+-([\d\.]+)\.(MCPTT|MCData|MCVideo)', tc_id)
    if mcx_m:
        raw = mcx_m.group(1)    # '5.1'
        service = mcx_m.group(2)  # 'MCPTT' or 'MCData'
        suffix = raw.replace('.', '_')  # '5_1'
        return [
            f'f_TC_{suffix}_{service}_MCX_IMS',
            f'f_TC_{suffix}_{service}_MCX_HTTP',
            f'f_TC_{suffix}_MCX_IMS',
            f'f_TC_{suffix}',
        ]

    # ── Positioning: 37571-1-6.2.1.1.4s ──
    pos_m = re.match(r'37571-[\w]+-([\d\.]+(?:\d[a-z]+)?)', tc_id)
    if pos_m:
        raw = pos_m.group(1)  # '6.2.1.1.4s'
        suffix = raw.replace('.', '_')  # '6_2_1_1_4s'
        return [
            f'f_TC_{suffix}_UTRAN',
            f'f_TC_{suffix}_EUTRA',
            f'f_TC_{suffix}_NR5GC',
            f'f_TC_{suffix}',
        ]

    # ── 일반 섹션 번호 추출 ──
    m = re.match(r'[\w]+-[\w]+-(\d[\d\.a-z]+)$', tc_id)
    if not m:
        return []
    section = m.group(1)
    suffix = section.replace('.', '_')

    candidates = []
    if generation == '4G':
        candidates = [
            f'f_TC_{suffix}_EUTRA',
            f'f_TC_{suffix}',
            f'f_TC_{suffix}_EUTRA_1',
            f'f_TC_{suffix}_EUTRA_2',
        ]
    elif generation == '5G':
        candidates = [
            f'f_TC_{suffix}_NR5GC',
            f'f_TC_{suffix}_NR5GC_1',
            f'f_TC_{suffix}_NR5GC_IMS1',
            f'f_TC_{suffix}',
        ]
    elif generation == '5G-NSA':
        candidates = [
            f'f_TC_{suffix}_ENDC_EUTRA',
            f'f_TC_{suffix}_ENDC_NR',
            f'f_TC_{suffix}_ENDC',
            f'f_TC_{suffix}',
        ]
    elif generation == '3G':
        candidates = [
            f'f_TC_{suffix}_SSNITZ',
            f'f_TC_{suffix}_UMTS',
            f'f_TC_{suffix}',
        ]
    elif generation in ('IMS-LTE', 'IMS-NR', 'IMS-IRAT', 'IMS-WLAN'):
        candidates = [
            f'f_TC_{suffix}_IMS1',
            f'f_TC_{suffix}_IMS2',
            f'f_TC_{suffix}',
            f'f_TC_{suffix}_EUTRA',
        ]
    elif generation == 'MCPTT':
        candidates = [
            f'f_TC_{suffix}_MCPTT_MCX_IMS',
            f'f_TC_{suffix}_MCData_MCX_IMS',
            f'f_TC_{suffix}_MCPTT',
            f'f_TC_{suffix}',
        ]
    elif generation == 'Positioning':
        candidates = [
            f'f_TC_{suffix}_EUTRA',
            f'f_TC_{suffix}_NR5GC',
            f'f_TC_{suffix}_UTRAN',
            f'f_TC_{suffix}',
        ]

    return candidates


# ─── 함수 본문 파싱 ─────────────────────────────────────

def extract_function_body(content: str, func_name: str) -> Optional[str]:
    """파일 내용에서 특정 함수 본문 추출"""
    func_start = content.find(f'function {func_name}')
    if func_start == -1:
        return None
    brace_start = content.find('{', func_start)
    if brace_start == -1:
        return None

    depth = 0
    for i in range(brace_start, min(len(content), brace_start + 300000)):
        c = content[i]
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return content[brace_start:i]
    return None


def infer_message_info(block: str) -> Tuple[str, str, str, str, str]:
    """TTCN-3 코드 블록에서 메시지 방향/이름 추론"""
    for pattern, direction, layer, frm, to in MSG_DIRECTION_PATTERNS:
        if pattern.search(block):
            m = MSG_NAME_RE.search(block)
            msg_name = m.group(1)[:60] if m else ''
            return direction, layer, frm, to, msg_name

    m = MSG_NAME_RE.search(block)
    msg_name = m.group(1)[:60] if m else ''
    return 'int', 'internal', 'SS', 'SS', msg_name


def extract_steps_from_body(func_body: str) -> List[dict]:
    """함수 본문에서 @siclog Step 기반 시퀀스 추출"""
    steps = []
    lines = func_body.split('\n')
    step_no = 0
    current_label = None
    current_desc_lines = []
    current_code_lines = []
    in_step = False

    for line in lines:
        siclog_m = SICLOG_RE.search(line)
        if siclog_m:
            # 이전 스텝 저장
            if in_step and current_label:
                steps.append({
                    'label': current_label,
                    'step_no': step_no,
                    'desc': ' '.join(current_desc_lines).strip(),
                    'code': '\n'.join(current_code_lines[:15]),
                })
            step_no += 1
            current_label = siclog_m.group(1)
            current_desc_lines = []
            current_code_lines = []
            in_step = True
            continue

        if not in_step:
            continue

        stripped = line.strip()
        comment_m = COMMENT_LINE_RE.match(line)
        if comment_m:
            text = comment_m.group(1).strip()
            if text and not text.startswith('@') and not text.startswith('*'):
                current_desc_lines.append(text)
        elif stripped and not stripped.startswith('/*') and not stripped.startswith('*'):
            current_code_lines.append(stripped)

    # 마지막 스텝
    if in_step and current_label:
        steps.append({
            'label': current_label,
            'step_no': step_no,
            'desc': ' '.join(current_desc_lines).strip(),
            'code': '\n'.join(current_code_lines[:15]),
        })

    # 결과 변환
    result = []
    for s in steps:
        combined = s['code'] + ' ' + s['desc']
        direction, layer, frm, to, msg_name = infer_message_info(combined)
        timer_starts = TIMER_START_RE.findall(s['code'])
        timer_stops = TIMER_STOP_RE.findall(s['code'])

        # 메시지명이 없으면 설명에서 첫 30자 사용
        if not msg_name and s['desc']:
            msg_name = s['desc'][:50]

        result.append({
            'step_no': s['step_no'],
            'from_entity': frm,
            'to_entity': to,
            'message': msg_name[:100],
            'direction': direction,
            'layer': layer,
            'note': s['desc'][:250],
            'timer_start': ','.join(timer_starts) if timer_starts else None,
            'timer_stop': ','.join(timer_stops) if timer_stops else None,
        })

    return result


# Body 함수 호출 패턴: fl_TC_*_Body / fl_TC_*_TestBody
BODY_CALL_RE = re.compile(r'\b(fl_TC_\w+)\s*\(')


def find_body_func(main_func_body: str, content: str,
                   file_cache: Dict[str, str]) -> Optional[str]:
    """
    메인 함수 본문에서 fl_TC_* 호출 탐지 →
    해당 함수 본문 반환 (Body/TestBody 우선)
    """
    # Body/TestBody 패턴 우선 시도
    for m in BODY_CALL_RE.finditer(main_func_body):
        body_func_name = m.group(1)
        # 같은 파일에서 먼저 찾기
        body = extract_function_body(content, body_func_name)
        if body:
            return body
        # 전역 인덱스에서 찾기
        entry = lookup_func(body_func_name)
        if entry:
            _, fpath = entry
            if fpath not in file_cache:
                try:
                    with open(fpath, encoding='utf-8', errors='replace') as f:
                        file_cache[fpath] = f.read()
                except Exception:
                    continue
            result = extract_function_body(file_cache[fpath], body_func_name)
            if result:
                return result
    return None


def process_tc(tc: dict, cur: sqlite3.Cursor,
               file_cache: Dict[str, str]) -> int:
    """TC 하나 처리 → tc_steps INSERT. 반환: 추출된 스텝 수"""
    tc_id = tc['id']
    generation = tc['generation']

    candidates = make_func_candidates(tc_id, generation)
    if not candidates:
        return 0

    # 후보 함수명 순서대로 인덱스 조회
    found = None
    for func_name in candidates:
        entry = lookup_func(func_name)
        if entry:
            found = entry
            break

    if not found:
        return 0

    real_func_name, fpath = found

    # 파일 내용 캐싱
    if fpath not in file_cache:
        try:
            with open(fpath, encoding='utf-8', errors='replace') as f:
                file_cache[fpath] = f.read()
        except Exception:
            return 0

    content = file_cache[fpath]

    func_body = extract_function_body(content, real_func_name)
    if not func_body:
        return 0

    steps = extract_steps_from_body(func_body)

    # 스텝이 없으면 Body/TestBody 함수 폴백
    if not steps:
        body_func_body = find_body_func(func_body, content, file_cache)
        if body_func_body:
            steps = extract_steps_from_body(body_func_body)

    if not steps:
        return 0

    for s in steps:
        cur.execute("""
            INSERT INTO tc_steps
              (tc_id, step_no, from_entity, to_entity, message, direction, layer,
               timer_start, timer_stop, note)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (
            tc_id, s['step_no'], s['from_entity'], s['to_entity'],
            s['message'], s['direction'], s['layer'],
            s['timer_start'], s['timer_stop'], s['note'],
        ))

    return len(steps)


def main():
    if not os.path.exists(DB_PATH):
        print("❌ tc.db 없음. 먼저 python tools/init_db.py 실행")
        sys.exit(1)

    # 전역 인덱스 구축
    build_index()

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # 기존 tc_steps 초기화
    cur.execute("DELETE FROM tc_steps")
    conn.commit()

    # 처리할 TC 목록
    cur.execute("""
        SELECT id, generation, category, raw_ttcn3_id
        FROM tcs
        ORDER BY generation, id
    """)
    tcs = [dict(zip(['id','generation','category','raw_ttcn3_id'], r))
           for r in cur.fetchall()]

    total_tc = len(tcs)
    total_steps = 0
    tc_with_steps = 0
    file_cache: Dict[str, str] = {}

    print(f"TC 처리 시작: {total_tc}개\n")

    for i, tc in enumerate(tcs):
        n = process_tc(tc, cur, file_cache)
        if n > 0:
            total_steps += n
            tc_with_steps += 1

        if (i + 1) % 100 == 0:
            conn.commit()
            pct = (i + 1) / total_tc * 100
            print(f"  [{i+1:4d}/{total_tc} {pct:4.0f}%] "
                  f"TC {tc_with_steps}개 성공, {total_steps}개 스텝")

    conn.commit()

    # 세대별 결과
    cur.execute("""
        SELECT t.generation, COUNT(DISTINCT s.tc_id), COUNT(s.id)
        FROM tc_steps s JOIN tcs t ON s.tc_id = t.id
        GROUP BY t.generation ORDER BY COUNT(s.id) DESC
    """)
    print("\n── 세대별 결과 ──")
    for r in cur.fetchall():
        print(f"  {r[0]:12s}: TC {r[1]}개, {r[2]}개 스텝")

    conn.close()

    print(f"\n✅ 완료: TC {tc_with_steps}/{total_tc}개에서 총 {total_steps}개 스텝 추출")


if __name__ == '__main__':
    main()
