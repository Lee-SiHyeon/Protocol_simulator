"""
extract_from_ttcn3.py - TTCN-3 Testsuite 파일에서 TC 전수 추출 → tc.db 입력
대상:
  - LTE_Testsuite.ttcn   (384 TCs, TC_8_1_2_2 형식)
  - NR5GC_Testsuite.ttcn (413 TCs, TC_10_1_1_1_NR5GC 형식)
  - ENDC_Testsuite.ttcn  (TBD TCs, TC_7_1_1_1_1_ENDC 형식)
  - SSNITZ_Testsuite.ttcn (77 TCs, TC_12_2_1_13 형식)
"""
import re
import sqlite3
import os
import sys

BASE = os.path.join(os.path.dirname(__file__), '..')
DB_PATH = os.path.join(BASE, 'tc.db')

# TTCN-3 파일 → (spec_prefix, generation, suffix_strip) 매핑
TESTSUITE_CONFIGS = [
    {
        'path': 'specs/36523-3/36523-3-ib0_TTCN3/36523-3-ib0_TTCN3_LTE/LTE_Testsuite.ttcn',
        'spec_prefix': '36523-1',
        'generation': '4G',
        'suffix_strip': '',       # TC_8_1_2_2 → 38523-1-8.1.2.2
    },
    {
        'path': 'specs/38523-3/38523-3-i60_TTCN3/38523-3-i60_TTCN3_NR5GC/NR5GC_Testsuite.ttcn',
        'spec_prefix': '38523-1',
        'generation': '5G',
        'suffix_strip': '_NR5GC',  # TC_10_1_1_1_NR5GC → 38523-1-10.1.1.1
    },
    {
        'path': 'specs/38523-3/38523-3-i60_TTCN3/38523-3-i60_TTCN3_ENDC/ENDC_Testsuite.ttcn',
        'spec_prefix': '38523-1-ENDC',
        'generation': '5G-NSA',
        'suffix_strip': '_ENDC',   # TC_7_1_1_1_1_ENDC → 38523-1-ENDC-7.1.1.1.1
    },
    {
        'path': 'specs/34123-3/34123-3-i30_TTCN3/34123-3-i30_TTCN3_SSNITZ/SSNITZ_Testsuite.ttcn',
        'spec_prefix': '34123-1',
        'generation': '3G',
        'suffix_strip': '',        # TC_12_2_1_13 → 34123-1-12.2.1.13
    },
    # TS 34.229-3 — IMS/VoLTE 전용 TTCN-3 ATS
    {
        'path': 'specs/34229-3/34229-3-i10_TTCN3/34229-3-i10_TTCN3_IMS_EUTRA/IMS_Testsuite_EUTRA.ttcn',
        'spec_prefix': '34229-1-EUTRA',
        'generation': 'IMS-LTE',
        'suffix_strip': '',
        'category_override': 'IMS',
    },
    {
        'path': 'specs/34229-3/34229-3-i10_TTCN3/34229-3-i10_TTCN3_IMS_NR5GC/IMS_Testsuite_NR5GC.ttcn',
        'spec_prefix': '34229-1-NR5GC',
        'generation': 'IMS-NR',
        'suffix_strip': '',
        'category_override': 'IMS',
    },
    {
        'path': 'specs/34229-3/34229-3-i10_TTCN3/34229-3-i10_TTCN3_IMS_IRAT/IMS_IRAT_Testsuite.ttcn',
        'spec_prefix': '34229-1-IRAT',
        'generation': 'IMS-IRAT',
        'suffix_strip': '',
        'category_override': 'IMS',
    },
    {
        'path': 'specs/34229-3/34229-3-i10_TTCN3/34229-3-i10_TTCN3_IMS_WLAN/IMS_Testsuite_WLAN.ttcn',
        'spec_prefix': '34229-1-WLAN',
        'generation': 'IMS-WLAN',
        'suffix_strip': '',
        'category_override': 'IMS',
    },
    # TS 36.579-5 — MCPTT/MCS (공공안전)
    {
        'path': 'specs/36579-5/36579-5-i10_TTCN3/36579-5-i10_TTCN3_MCX_IPCAN/MCX_Testsuite_IPCAN.ttcn',
        'spec_prefix': '36579-1',
        'generation': 'MCPTT',
        'suffix_strip': '',
        'category_override': 'MCPTT',
        'tc_pattern': r'^\s*testcase\s+(TC_[\w]+)\s*\(',   # TC_5_1_MCPTT 형식
    },
    # TS 37.571-4 — Positioning
    {
        'path': 'specs/37571-4/37571-4-i10_TTCN3/37571-4-i10_TTCN3_POS/POS_Testsuite.ttcn',
        'spec_prefix': '37571-1',
        'generation': 'Positioning',
        'suffix_strip': '',
        'category_override': 'Positioning',
        'tc_pattern': r'^\s*testcase\s+(TC_[\w]+)\s*\(',   # TC_6_2_1_1_4s 형식 (suffix 4s 등 포함)
    },
]

# 섹션 번호 → 카테고리 분류
CATEGORY_MAP = {
    # 공통 패턴 (LTE §)
    '6': 'IdleMode',
    '7': 'L2',        # MAC/RLC/PDCP/SDAP
    '8': 'RRC',
    '9': 'NAS',
    '10': 'IMS',
    '11': 'Service',
    '12': 'CA',       # LTE: CA/Bands, 3G: GMM
    '13': 'Barring',  # LTE: EAB
    '14': 'UECap',    # LTE: UE Capability
    '15': 'SupService', # 3G: Supplementary Services
}

# 서브섹션 → 더 세밀한 카테고리 (NR5GC §7 내 하위 분류)
SUBSECTION_MAP = {
    '7_1': 'L2',
    '7_1_1': 'MAC',
    '7_1_2': 'RLC',
    '7_1_3': 'PDCP',
    '7_1_4': 'SDAP',
    '6_7': 'NTN',
    '11_3': 'UAC',
    '11_4': 'Emergency',
    '11_5': 'eCall',
    '11_7': 'eDRX',
    '9': 'Security',
}

ERROR_KEYWORDS = re.compile(
    r'(reject|fail|timeout|failure|refused|abort|limit|error|collision|invalid)',
    re.IGNORECASE
)

# TTCN-3 raw_id → 스펙 섹션 번호 변환
def raw_id_to_spec_section(raw_id: str, suffix_strip: str) -> str:
    """
    TC_8_1_2_2        → '8.1.2.2'
    TC_10_1_1_1_NR5GC → '10.1.1.1'
    TC_7_1_1_1_1_ENDC → '7.1.1.1.1'
    """
    name = raw_id  # e.g. TC_8_1_2_2
    # 'TC_' 접두사 제거
    if name.startswith('TC_'):
        name = name[3:]
    # suffix 제거 (e.g. _NR5GC, _ENDC)
    if suffix_strip and name.endswith(suffix_strip[1:]):  # suffix_strip = '_NR5GC'
        # strip은 '_NR5GC' 같은 형태
        tail = suffix_strip.lstrip('_')
        if name.endswith('_' + tail):
            name = name[:-(len(tail) + 1)]
    # 나머지 언더스코어 → 점
    return name.replace('_', '.')


def get_category(section: str, raw_id: str, generation: str) -> str:
    """섹션 번호로 카테고리 추론"""
    parts = section.split('.')
    if not parts:
        return 'Unknown'

    top = parts[0]
    sub2 = '_'.join(parts[:2]) if len(parts) >= 2 else top
    sub3 = '_'.join(parts[:3]) if len(parts) >= 3 else sub2

    # 서브섹션 우선 확인
    for key in [sub3, sub2]:
        if key in SUBSECTION_MAP:
            return SUBSECTION_MAP[key]

    # NR5GC §9 = Security (NAS Auth)
    if top == '9' and generation in ('5G', '4G', '3G'):
        return 'Security'

    return CATEGORY_MAP.get(top, 'Other')


def extract_from_file(cfg: dict, cur: sqlite3.Cursor) -> int:
    filepath = os.path.join(BASE, cfg['path'])
    if not os.path.exists(filepath):
        print(f"  ⚠️  파일 없음: {filepath}")
        return 0

    spec_prefix = cfg['spec_prefix']
    generation = cfg['generation']
    suffix_strip = cfg['suffix_strip']
    category_override = cfg.get('category_override')  # IMS/MCPTT/Positioning 등 고정 카테고리

    count = 0
    # 커스텀 패턴 또는 기본 패턴
    tc_pattern = re.compile(cfg.get('tc_pattern', r'^\s*testcase\s+(TC_[\w]+)\s*\('))

    with open(filepath, encoding='utf-8', errors='replace') as f:
        for line in f:
            m = tc_pattern.match(line)
            if not m:
                continue

            raw_id = m.group(1)  # 'TC_8_1_2_2' | 'TC_10_1' | 'TC_5_1_MCPTT'
            section = raw_id_to_spec_section(raw_id, suffix_strip)
            tc_id = f'{spec_prefix}-{section}'

            # 카테고리 결정
            if category_override:
                category = category_override
            else:
                category = get_category(section, raw_id, generation)

            # 에러 케이스 판별
            is_error = 1 if ERROR_KEYWORDS.search(raw_id) else 0

            # generation override for NTN
            gen = generation
            if 'NTN' in raw_id:
                gen = 'NTN'

            cur.execute("""
                INSERT OR IGNORE INTO tcs
                  (id, generation, category, conf_spec, is_error_case, raw_ttcn3_id, source_file)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                tc_id,
                gen,
                category,
                f'TS {spec_prefix.replace("-ENDC","").replace("-EUTRA","").replace("-NR5GC","").replace("-IRAT","").replace("-WLAN","")} §{section}',
                is_error,
                raw_id,
                cfg['path'],
            ))
            count += 1

    return count


def main():
    if not os.path.exists(DB_PATH):
        print("❌ tc.db 없음. 먼저 python tools/init_db.py 실행")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    total = 0

    for cfg in TESTSUITE_CONFIGS:
        label = os.path.basename(cfg['path'])
        n = extract_from_file(cfg, cur)
        print(f"  {label}: {n}개 추출")
        total += n

    conn.commit()

    # 결과 요약
    print(f"\n✅ 총 {total}개 TC → tc.db 입력 완료")
    for gen in ['4G', '5G', '5G-NSA', 'NTN', '3G']:
        cur.execute("SELECT COUNT(*) FROM tcs WHERE generation=?", (gen,))
        cnt = cur.fetchone()[0]
        if cnt:
            print(f"   {gen}: {cnt}개")

    # 카테고리별
    cur.execute("SELECT category, COUNT(*) FROM tcs GROUP BY category ORDER BY 2 DESC")
    rows = cur.fetchall()
    print("\n카테고리별:")
    for row in rows:
        print(f"   {row[0] or 'Unknown'}: {row[1]}개")

    conn.close()


if __name__ == '__main__':
    main()
