"""
extract_asn1_ies.py - ASN.1 RRC IE 파싱 → tc.db의 ies + ie_fields 테이블 입력

대상 파일:
  - EUTRA_RRC_ASN1_Definitions.asn (653KB, TS 36.331 기반 - 4G LTE RRC IE)
  - NR_RRC_ASN1_Definitions.asn    (1.57MB, TS 38.331 기반 - 5G NR RRC IE)
  - UTRAN_RRC_ASN1_Definitions.asn (1.44MB, TS 25.331 기반 - 3G UMTS RRC IE)
  - NBIOT_RRC_ASN1_Definitions.asn (115KB, NB-IoT RRC IE)
"""
import re
import sqlite3
import os
import sys
from typing import Optional

BASE = os.path.join(os.path.dirname(__file__), '..')
DB_PATH = os.path.join(BASE, 'tc.db')

# 대상 ASN.1 파일 설정
ASN1_CONFIGS = [
    {
        'pattern': 'EUTRA_RRC_ASN1_Definitions.asn',
        'search_under': 'specs/36523-3',
        'spec_origin': 'TS 36.331',
        'generation': '4G',
    },
    {
        'pattern': 'NR_RRC_ASN1_Definitions.asn',
        'search_under': 'specs/38523-3',
        'spec_origin': 'TS 38.331',
        'generation': '5G',
    },
    {
        'pattern': 'UTRAN_RRC_ASN1_Definitions.asn',
        'search_under': 'specs/34123-3',
        'spec_origin': 'TS 25.331',
        'generation': '3G',
    },
    {
        'pattern': 'NBIOT_RRC_ASN1_Definitions.asn',
        'search_under': 'specs/36523-3',
        'spec_origin': 'TS 36.331-NB',
        'generation': '4G-NB',
    },
]


def find_asn1_file(pattern: str, search_under: str) -> Optional[str]:
    """중복 파일 중 첫 번째만 반환"""
    base = os.path.join(BASE, search_under)
    for root, dirs, files in os.walk(base):
        if pattern in files:
            return os.path.join(root, pattern)
    return None


# ASN.1 IE 블록 파싱 (정규식 기반)
# 패턴: IEName ::= TYPE { ... }
IE_DEF_PATTERN = re.compile(
    r'(\w[\w-]*)\s*::=\s*(SEQUENCE OF|SEQUENCE|CHOICE|ENUMERATED|INTEGER|BIT STRING|OCTET STRING|BOOLEAN|NULL|VisibleString|UTF8String|IA5String|\w[\w-]*)',
    re.MULTILINE
)
FIELD_PATTERN = re.compile(
    r'^\s{2,}(\w[\w-]*)\s+([\w][\w-]*(?:\s+(?:SIZE|OF|FROM)[^,\n]*)?)\s*(OPTIONAL|DEFAULT\s+\S+)?\s*(?:--\s*(.*))?$',
    re.MULTILINE
)


def parse_asn1_blocks(content: str):
    """
    ASN.1 파일에서 IE 정의 블록 파싱.
    반환: list of (ie_name, asn1_type, fields, full_block)
    """
    results = []
    # 빈 줄 기준으로 블록 분리
    # IE 정의는 "Name ::= TYPE" 패턴으로 시작
    # 중괄호 {} 안에 필드들이 있음
    
    # 방법: IE 이름 + ::= 찾기 → 그 이후 { } 블록 추출
    i = 0
    while i < len(content):
        m = IE_DEF_PATTERN.search(content, i)
        if not m:
            break
        
        ie_name = m.group(1)
        asn1_type_raw = m.group(2)
        
        # ASN.1 타입 분류
        asn1_type = classify_type(asn1_type_raw)
        
        # 블록 추출 (중괄호 포함)
        start = m.start()
        block_start = content.find('{', m.end())
        
        fields = []
        if block_start != -1 and block_start < m.end() + 300:
            # 중괄호 안쪽 추출
            depth = 0
            block_end = block_start
            for j in range(block_start, min(len(content), block_start + 50000)):
                c = content[j]
                if c == '{':
                    depth += 1
                elif c == '}':
                    depth -= 1
                    if depth == 0:
                        block_end = j
                        break
            
            block_content = content[block_start+1:block_end]
            fields = parse_fields(block_content)
            full_block = content[start:block_end+1]
        else:
            # 인라인 정의 (중괄호 없음)
            line_end = content.find('\n', m.end())
            full_block = content[start:line_end if line_end > 0 else m.end()]
        
        # 유효한 IE 이름만 (소문자로만 시작하는 건 필드 참조)
        if ie_name[0].isupper() or ie_name[0].isdigit():
            results.append({
                'name': ie_name,
                'asn1_type': asn1_type,
                'fields': fields,
                'definition': full_block[:2000],  # 최대 2000자
            })
        
        i = m.end()
    
    return results


def classify_type(raw: str) -> str:
    raw_upper = raw.strip().upper()
    if 'SEQUENCE OF' in raw_upper:
        return 'SEQUENCE OF'
    if 'SEQUENCE' in raw_upper:
        return 'SEQUENCE'
    if 'CHOICE' in raw_upper:
        return 'CHOICE'
    if 'ENUMERATED' in raw_upper:
        return 'ENUMERATED'
    if 'INTEGER' in raw_upper:
        return 'INTEGER'
    if 'BIT STRING' in raw_upper:
        return 'BIT STRING'
    if 'OCTET STRING' in raw_upper:
        return 'OCTET STRING'
    if 'BOOLEAN' in raw_upper:
        return 'BOOLEAN'
    if 'NULL' in raw_upper:
        return 'NULL'
    return 'REF'  # 다른 IE 참조


def parse_fields(block: str) -> list:
    """
    SEQUENCE 블록 안의 필드 파싱.
    반환: list of (field_name, field_type, is_optional, comment)
    """
    fields = []
    lines = block.split('\n')
    order = 0
    for line in lines:
        line = line.strip()
        if not line or line.startswith('--'):
            continue
        
        # 주석 분리
        comment = ''
        if '--' in line:
            parts = line.split('--', 1)
            line = parts[0].strip()
            comment = parts[1].strip()
        
        # OPTIONAL / DEFAULT 확인
        is_optional = 0
        if 'OPTIONAL' in line:
            is_optional = 1
            line = line.replace('OPTIONAL', '').strip()
        elif 'DEFAULT' in line:
            is_optional = 1
            line = re.sub(r'DEFAULT\s+\S+', '', line).strip()
        
        # 필드명 + 타입 파싱 (첫 두 토큰)
        # 쉼표 제거
        line = line.rstrip(',').strip()
        tokens = line.split()
        if len(tokens) >= 2:
            field_name = tokens[0]
            field_type = tokens[1]
            # 유효한 필드명인지 확인 (소문자로 시작)
            if field_name and field_name[0].islower():
                fields.append({
                    'name': field_name,
                    'type': field_type,
                    'is_optional': is_optional,
                    'comment': comment,
                    'order': order,
                })
                order += 1
    
    return fields


def process_asn1_file(cfg: dict, cur: sqlite3.Cursor) -> int:
    filepath = find_asn1_file(cfg['pattern'], cfg['search_under'])
    if not filepath:
        print(f"  ⚠️  파일 없음: {cfg['pattern']} (under {cfg['search_under']})")
        return 0
    
    print(f"  파싱: {os.path.relpath(filepath, BASE)} ({os.path.getsize(filepath)//1024}KB)")
    
    with open(filepath, encoding='utf-8', errors='replace') as f:
        content = f.read()
    
    ies = parse_asn1_blocks(content)
    
    count_ie = 0
    count_fields = 0
    
    for ie in ies:
        # ies 테이블 INSERT (중복 시 무시)
        cur.execute("""
            INSERT OR IGNORE INTO ies (name, spec_origin, generation, asn1_type, definition)
            VALUES (?, ?, ?, ?, ?)
        """, (
            ie['name'],
            cfg['spec_origin'],
            cfg['generation'],
            ie['asn1_type'],
            ie['definition'],
        ))
        count_ie += 1
        
        # ie_fields 테이블 INSERT
        for field in ie['fields']:
            cur.execute("""
                INSERT INTO ie_fields (ie_name, field_name, field_type, is_optional, comment, sort_order)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                ie['name'],
                field['name'],
                field['type'],
                field['is_optional'],
                field['comment'],
                field['order'],
            ))
            count_fields += 1
    
    print(f"    → IE: {count_ie}개, Field: {count_fields}개")
    return count_ie


def main():
    if not os.path.exists(DB_PATH):
        print("❌ tc.db 없음. 먼저 python tools/init_db.py 실행")
        sys.exit(1)
    
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    total_ies = 0
    
    for cfg in ASN1_CONFIGS:
        n = process_asn1_file(cfg, cur)
        total_ies += n
    
    conn.commit()
    
    cur.execute("SELECT COUNT(*) FROM ies")
    total_in_db = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM ie_fields")
    total_fields = cur.fetchone()[0]
    
    print(f"\n✅ ASN.1 파싱 완료")
    print(f"   IE 총합: {total_in_db}개")
    print(f"   Field 총합: {total_fields}개")
    
    # 세대별 요약
    cur.execute("SELECT generation, COUNT(*) FROM ies GROUP BY generation ORDER BY 2 DESC")
    for row in cur.fetchall():
        print(f"   {row[0]}: {row[1]}개 IE")
    
    conn.close()


if __name__ == '__main__':
    main()
