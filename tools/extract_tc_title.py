"""
extract_tc_title.py - TS 36.523-1 Part 1 DOCX에서 Heading 4 기반 TC 제목 추출
→ tc.db의 tcs.short_name 업데이트

Heading 4 패턴: '8.1.2.2 RRC connection establishment / Reject with wait time'
→ tc_id = '36523-1-8.1.2.2', short_name = 'RRC connection establishment / Reject with wait time'
"""
import re
import sqlite3
import os
import sys

BASE = os.path.join(os.path.dirname(__file__), '..')
DB_PATH = os.path.join(BASE, 'tc.db')
DOCX_DIR = os.path.join(BASE, 'specs', '36523-1')

# 섹션 번호 정규화 ('8.1.1.1a' → '8.1.1.1a')
TC_ID_PATTERN = re.compile(r'^(\d+\.[\d\.a-z]+)\s+(.*)')

# Heading 4에 해당하는 스타일 이름들
H4_STYLES = {'Heading 4', 'H4', 'Heading4'}


def normalize_section(raw_section: str) -> str:
    """'8.1.2.2a' 같은 섹션번호 정규화"""
    return raw_section.strip().rstrip('.')


def extract_tc_titles(docx_path: str, spec_prefix: str = '36523-1') -> dict:
    """
    DOCX 파일에서 Heading 4 기반 TC 제목 추출.
    반환: {tc_id: short_name}
    """
    from docx import Document
    doc = Document(docx_path)
    results = {}
    
    for para in doc.paragraphs:
        style_name = para.style.name if para.style else ''
        
        # Heading 4 스타일인지 확인
        is_h4 = (
            style_name in H4_STYLES or
            style_name == 'Heading 4'
        )
        if not is_h4:
            continue
        
        text = para.text.strip()
        if not text:
            continue
        
        # 섹션 번호 + 제목 파싱
        m = TC_ID_PATTERN.match(text)
        if not m:
            continue
        
        section = normalize_section(m.group(1))
        title = m.group(2).strip()
        
        # 최소 2개 이상의 점(숫자.숫자.숫자.숫자)
        if section.count('.') < 2:
            continue
        
        tc_id = f'{spec_prefix}-{section}'
        
        # 'Void' 제목은 건너뜀
        if title.lower() == 'void' or title == '':
            continue
        
        results[tc_id] = title
    
    return results


def main():
    if not os.path.exists(DB_PATH):
        print("❌ tc.db 없음. 먼저 python tools/init_db.py 실행")
        sys.exit(1)
    
    if not os.path.exists(DOCX_DIR):
        print(f"❌ DOCX 디렉토리 없음: {DOCX_DIR}")
        sys.exit(1)
    
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    total_found = 0
    total_updated = 0
    
    # 모든 DOCX 파일 처리 (커버 파일 제외)
    docx_files = sorted([
        f for f in os.listdir(DOCX_DIR)
        if f.endswith('.docx') and 'cover' not in f.lower()
    ])
    
    for filename in docx_files:
        filepath = os.path.join(DOCX_DIR, filename)
        print(f"  처리: {filename}")
        
        try:
            titles = extract_tc_titles(filepath)
            total_found += len(titles)
            
            for tc_id, short_name in titles.items():
                # DB에 있는 TC만 업데이트
                cur.execute(
                    "UPDATE tcs SET short_name=? WHERE id=? AND short_name IS NULL",
                    (short_name[:120], tc_id)
                )
                if cur.rowcount > 0:
                    total_updated += 1
                else:
                    # DB에 없지만 DOCX에는 있는 TC → 새로 INSERT
                    # (DOCX가 TTCN-3보다 더 많은 TC 포함 가능)
                    cur.execute(
                        """INSERT OR IGNORE INTO tcs
                           (id, short_name, generation, category, conf_spec, is_error_case)
                           VALUES (?, ?, '4G', 'Other', ?, ?)""",
                        (
                            tc_id,
                            short_name[:120],
                            f'TS 36.523-1 §{tc_id.replace("36523-1-", "")}',
                            1 if re.search(r'(reject|fail|timeout)', short_name, re.I) else 0,
                        )
                    )
                    if cur.rowcount > 0:
                        total_updated += 1
            
        except Exception as e:
            print(f"    ⚠️  오류: {e}")
    
    conn.commit()
    
    # 결과 확인
    cur.execute("SELECT COUNT(*) FROM tcs WHERE short_name IS NOT NULL")
    with_name = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM tcs")
    total_tcs = cur.fetchone()[0]
    
    print(f"\n✅ TC 제목 추출 완료")
    print(f"   DOCX에서 찾은 TC: {total_found}개")
    print(f"   DB 업데이트/신규: {total_updated}개")
    print(f"   short_name 있는 TC: {with_name}/{total_tcs}개")
    
    conn.close()


if __name__ == '__main__':
    main()
