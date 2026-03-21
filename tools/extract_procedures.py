"""
extract_procedures.py - TTCN-3 TC 구현 파일에서 메시지 시퀀스 추출 → tc_steps 테이블

TTCN-3 패턴:
  //@siclog "Step 1" siclog@
  //The SS transmits an RRCConnectionSetup message.
  f_EUTRA_RRC_ConnectionSetup_Def(eutra_Cell1);

  //@siclog "Step 2" siclog@
  [] SRB.receive(car_SRB0_RrcPdu_IND(..., cr_508_RRCConnectionRequest))

현재 지원 스펙:
  - LTE (TS 36.523-3): f_TC_8_1_2_2_EUTRA() 형식
  - NR5GC (TS 38.523-3): 유사 패턴
  - IMS (TS 34.229-3): IMS SIP 시퀀스 추출
"""
import re
import sqlite3
import os
import sys
from typing import Optional, List, Tuple

BASE = os.path.join(os.path.dirname(__file__), '..')
DB_PATH = os.path.join(BASE, 'tc.db')

# ─── 메시지 방향 추론 ────────────────────────────────────
# 메시지명 패턴 → (direction, layer, from_entity, to_entity)
MSG_PATTERNS = [
    # SRB send = SS→UE (DL)
    (re.compile(r'\bSRB\.send\b'), 'dl', 'RRC', 'eNB/gNB', 'UE'),
    # SRB receive = UE→SS (UL)
    (re.compile(r'\bSRB\.receive\b'), 'ul', 'RRC', 'UE', 'eNB/gNB'),
    # DRB send = SS→UE (DL data)
    (re.compile(r'\bDRB\.send\b'), 'dl', 'PDCP', 'eNB/gNB', 'UE'),
    # DRB receive = UE→SS (UL data)
    (re.compile(r'\bDRB\.receive\b'), 'ul', 'PDCP', 'UE', 'eNB/gNB'),
    # 자주 쓰이는 헬퍼 함수들
    (re.compile(r'\bf_EUTRA_UE_Page\b'), 'dl', 'RRC', 'eNB/gNB', 'UE'),
    (re.compile(r'\bf_EUTRA_Paging\b'), 'dl', 'RRC', 'eNB/gNB', 'UE'),
    (re.compile(r'\bf_EUTRA_RRC_ConnectionSetup_Def\b'), 'dl', 'RRC', 'eNB/gNB', 'UE'),
    (re.compile(r'\bf_EUTRA_RRC_ConnectionRelease\b'), 'dl', 'RRC', 'eNB/gNB', 'UE'),
    (re.compile(r'\bf_EUTRA_RRC_ConnectionRequest_Def\b'), 'ul', 'RRC', 'UE', 'eNB/gNB'),
    (re.compile(r'\bf_EUTRA_RRCConnectionSetupComplete_Def\b'), 'ul', 'RRC', 'UE', 'eNB/gNB'),
    (re.compile(r'\bf_EUTRA_RRC_SecurityModeCommand_Def\b'), 'dl', 'RRC', 'eNB/gNB', 'UE'),
    (re.compile(r'\bf_EUTRA_RRC_SecurityModeComplete_Def\b'), 'ul', 'RRC', 'UE', 'eNB/gNB'),
    # NAS 방향
    (re.compile(r'\bNAS_Ind\b|\bf_EUTRA_NAS_Indication\b'), 'ul', 'NAS', 'UE', 'MME'),
    (re.compile(r'\bNAS_Req\b|\bf_EUTRA_NAS_Request\b'), 'dl', 'NAS', 'MME', 'UE'),
    # NR5GC 패턴
    (re.compile(r'\bf_NR_RRC_ConnectionRequest_Def\b'), 'ul', 'RRC', 'UE', 'gNB'),
    (re.compile(r'\bf_NR_RRC_Setup_Def\b'), 'dl', 'RRC', 'gNB', 'UE'),
    # IMS SIP
    (re.compile(r'\bIMS_PORT\.send\b|REGISTER|INVITE|BYE'), 'ul', 'SIP', 'UE', 'P-CSCF'),
    (re.compile(r'\b200 OK\b|\b180 Ringing\b'), 'dl', 'SIP', 'P-CSCF', 'UE'),
]

# 메시지 이름 추출 패턴 (cs_/cr_/cas_/car_ 접두사 뒤 이름)
MSG_NAME_RE = re.compile(r'\b(?:cs_|cr_|cas_|car_|c_)(?:508_)?([A-Z][A-Za-z0-9_]+)')

# 타이머 패턴
TIMER_START_RE = re.compile(r'(\bt_\w+)\.start\(')
TIMER_STOP_RE  = re.compile(r'(\bt_\w+)\.stop\b')

SICLOG_RE = re.compile(r'@siclog\s+"(Step\s+[\w]+)"', re.IGNORECASE)
COMMENT_RE = re.compile(r'^\s*//(.*)')

# 에러 판별
ERROR_STEP_RE = re.compile(r'(reject|fail|timeout|refused|not respond|no response)', re.IGNORECASE)


def infer_message_info(block: str) -> Tuple[str, str, str, str, str]:
    """
    TTCN-3 코드 블록에서 메시지 방향/레이어/엔티티/이름 추론.
    반환: (direction, layer, from_entity, to_entity, msg_name)
    """
    for pattern, direction, layer, frm, to in MSG_PATTERNS:
        if pattern.search(block):
            # 메시지 이름 추출
            m = MSG_NAME_RE.search(block)
            msg_name = m.group(1) if m else ''
            # 긴 이름 정리
            msg_name = msg_name.replace('_', '')[:40]
            return direction, layer, frm, to, msg_name

    # 기본: 이름만 추출하고 방향 미정
    m = MSG_NAME_RE.search(block)
    msg_name = m.group(1).replace('_', '')[:40] if m else ''
    return 'int', 'RRC', 'SS', 'UE', msg_name


def extract_steps_from_function(content: str, func_name: str) -> List[dict]:
    """
    TTCN-3 함수 본문에서 @siclog step 기반 시퀀스 추출.
    """
    # 함수 시작 위치 찾기
    func_start = content.find(f'function {func_name}')
    if func_start == -1:
        return []

    # 함수 블록 추출 (중괄호 매칭)
    brace_start = content.find('{', func_start)
    if brace_start == -1:
        return []

    depth = 0
    func_end = brace_start
    for i in range(brace_start, min(len(content), brace_start + 200000)):
        c = content[i]
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                func_end = i
                break

    func_body = content[brace_start:func_end]

    # @siclog Step 기반 파싱
    steps = []
    lines = func_body.split('\n')
    step_no = 0
    current_step_label = None
    current_desc_lines = []
    current_code_lines = []
    in_step = False

    for i, line in enumerate(lines):
        siclog_m = SICLOG_RE.search(line)
        if siclog_m:
            # 이전 스텝 저장
            if in_step and current_step_label:
                steps.append({
                    'label': current_step_label,
                    'step_no': step_no,
                    'desc': ' '.join(current_desc_lines).strip(),
                    'code': '\n'.join(current_code_lines[:10]),  # 최대 10줄
                })

            step_no += 1
            current_step_label = siclog_m.group(1)
            current_desc_lines = []
            current_code_lines = []
            in_step = True
            continue

        if in_step:
            stripped = line.strip()
            comment_m = COMMENT_RE.match(line)

            if comment_m:
                desc_text = comment_m.group(1).strip()
                if desc_text and not desc_text.startswith('@'):
                    current_desc_lines.append(desc_text)
            elif stripped and not stripped.startswith('//') and not stripped.startswith('/*'):
                current_code_lines.append(stripped)

    # 마지막 스텝
    if in_step and current_step_label:
        steps.append({
            'label': current_step_label,
            'step_no': step_no,
            'desc': ' '.join(current_desc_lines).strip(),
            'code': '\n'.join(current_code_lines[:10]),
        })

    # 각 스텝에서 메시지 정보 추론
    result = []
    for s in steps:
        direction, layer, frm, to, msg_name = infer_message_info(s['code'] + s['desc'])
        timer_starts = TIMER_START_RE.findall(s['code'])
        timer_stops = TIMER_STOP_RE.findall(s['code'])

        result.append({
            'step_no': s['step_no'],
            'step_label': s['label'],
            'from_entity': frm,
            'to_entity': to,
            'message': msg_name or s['desc'][:60],
            'direction': direction,
            'layer': layer,
            'note': s['desc'][:200],
            'timer_start': ','.join(timer_starts) if timer_starts else None,
            'timer_stop': ','.join(timer_stops) if timer_stops else None,
        })

    return result


def find_tc_file(tc_id: str, generation: str) -> Optional[Tuple[str, str]]:
    """
    TC ID → (파일 경로, 함수 이름) 반환.
    예: '36523-1-8.1.2.2' → ('specs/36523-3/.../RRC_ConnEst.ttcn', 'f_TC_8_1_2_2_EUTRA')
    """
    # TC ID에서 섹션 번호 추출
    m = re.match(r'[\w-]+-(\d[\d\.a-z]+)$', tc_id)
    if not m:
        return None
    section = m.group(1)  # '8.1.2.2'

    # 섹션 → 폴더 이름 (첫 두 부분: '8_1')
    parts = section.split('.')
    if len(parts) < 2:
        return None

    folder_prefix = f'{parts[0]}_{parts[1]}'  # '8_1'
    func_suffix = section.replace('.', '_')    # '8_1_2_2'

    # 스펙 루트 결정
    if generation in ('4G',):
        spec_roots = [
            os.path.join(BASE, 'specs', '36523-3', '36523-3-ib0_TTCN3', '36523-3-ib0_TTCN3_LTE', 'LTE'),
        ]
        func_name = f'f_TC_{func_suffix}_EUTRA'
    elif generation in ('5G',):
        spec_roots = [
            os.path.join(BASE, 'specs', '38523-3', '38523-3-i60_TTCN3', '38523-3-i60_TTCN3_NR5GC', 'NR5GC'),
        ]
        func_name = f'f_TC_{func_suffix}_NR5GC'
    elif generation in ('3G',):
        spec_roots = [
            os.path.join(BASE, 'specs', '34123-3'),
        ]
        func_name = f'f_TC_{func_suffix}_SSNITZ'
    elif generation in ('IMS-LTE', 'IMS-NR', 'IMS-IRAT', 'IMS-WLAN'):
        spec_roots = [
            os.path.join(BASE, 'specs', '34229-3'),
        ]
        func_name = f'f_TC_{func_suffix}'
    else:
        return None

    # 폴더 탐색
    for root in spec_roots:
        if not os.path.exists(root):
            continue
        for dirpath, dirs, files in os.walk(root):
            # 해당 섹션 폴더 찾기
            folder_name = os.path.basename(dirpath)
            if folder_name != folder_prefix and not folder_name.startswith(folder_prefix):
                continue
            for fname in files:
                if not fname.endswith('.ttcn'):
                    continue
                fpath = os.path.join(dirpath, fname)
                # 파일 안에 함수가 있는지 확인
                try:
                    with open(fpath, encoding='utf-8', errors='replace') as f:
                        snippet = f.read(500000)
                    if f'function {func_name}' in snippet:
                        return fpath, func_name
                except Exception:
                    continue
    return None


def process_tc(tc: dict, cur: sqlite3.Cursor) -> int:
    """TC 하나 처리 → tc_steps INSERT. 반환: 추출된 스텝 수"""
    tc_id = tc['id']
    generation = tc['generation']

    result = find_tc_file(tc_id, generation)
    if not result:
        return 0

    fpath, func_name = result

    try:
        with open(fpath, encoding='utf-8', errors='replace') as f:
            content = f.read()
    except Exception:
        return 0

    steps = extract_steps_from_function(content, func_name)
    if not steps:
        return 0

    for s in steps:
        cur.execute("""
            INSERT INTO tc_steps
              (tc_id, step_no, from_entity, to_entity, message, direction, layer,
               timer_start, timer_stop, note)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (
            tc_id,
            s['step_no'],
            s['from_entity'],
            s['to_entity'],
            s['message'][:100],
            s['direction'],
            s['layer'],
            s['timer_start'],
            s['timer_stop'],
            s['note'],
        ))

    return len(steps)


def main():
    if not os.path.exists(DB_PATH):
        print("❌ tc.db 없음. 먼저 python tools/init_db.py 실행")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # 기존 tc_steps 초기화 (재실행 가능)
    cur.execute("DELETE FROM tc_steps")
    conn.commit()

    # 처리할 TC 목록 (4G LTE + 5G NR5GC + IMS 우선)
    cur.execute("""
        SELECT id, generation, category, raw_ttcn3_id
        FROM tcs
        WHERE generation IN ('4G','5G','3G','IMS-LTE','IMS-NR')
        ORDER BY generation, id
    """)
    tcs = [dict(zip(['id','generation','category','raw_ttcn3_id'], r)) for r in cur.fetchall()]

    total_tc = len(tcs)
    total_steps = 0
    tc_with_steps = 0
    failed = 0

    print(f"TC 처리 시작: {total_tc}개")

    for i, tc in enumerate(tcs):
        n = process_tc(tc, cur)
        if n > 0:
            total_steps += n
            tc_with_steps += 1
        else:
            failed += 1

        if (i + 1) % 50 == 0:
            conn.commit()
            pct = (i + 1) / total_tc * 100
            print(f"  [{i+1}/{total_tc} {pct:.0f}%] 처리 완료 — 스텝 {total_steps}개 추출")

    conn.commit()
    conn.close()

    print(f"\n✅ 메시지 시퀀스 추출 완료")
    print(f"   TC {tc_with_steps}/{total_tc}개에서 스텝 추출 성공")
    print(f"   TC {failed}개: 구현 파일 없음 (공통 절차 참조 등)")
    print(f"   총 tc_steps: {total_steps}개")


if __name__ == '__main__':
    main()
