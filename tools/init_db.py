"""
init_db.py - tc.db SQLite 스키마 초기화
3GPP Protocol Simulator DB (8개 테이블)
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'tc.db')


def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.executescript("""
    PRAGMA journal_mode=WAL;

    -- TC 마스터 (900개+ 전수 입력)
    CREATE TABLE IF NOT EXISTS tcs (
        id              TEXT PRIMARY KEY,   -- '36523-1-8.1.2.2' (스펙 섹션 번호)
        short_name      TEXT,               -- 'RRC Conn Est / Reject with wait time'
        generation      TEXT NOT NULL,      -- '2G'|'3G'|'4G'|'5G'|'NTN'|'USIM'
        category        TEXT,               -- 'RRC'|'NAS'|'MAC'|'Security'|'CA'|'UAC'|'PDCP'|'RLC'|'IMS'|'SMS'|'eCall'|'SNPN'|'NTN'
        cert            TEXT,               -- 'GCF'|'PTCRB'|'GSMA'|NULL
        conf_spec       TEXT,               -- 'TS 36.523-1 §8.1.2.2'
        core_specs      TEXT,               -- 'TS 36.331 §5.3.3; TS 24.301 §5.5.1'
        is_error_case   INTEGER DEFAULT 0,  -- 1=Reject/Fail/Timeout 케이스
        ie_status       TEXT DEFAULT 'stub',-- 'stub'|'partial'|'full'
        usim_interface  TEXT,               -- 'EPS-AKA'|'5G-AKA'|'EAP-AKA-PRIME'|'UMTS-AKA'|'GSM-A3A8'
        usim_ef         TEXT,               -- 'EF_IMSI, EF_KEYS, EF_LOCI'
        auth_algo       TEXT,               -- 'Milenage'|'TUAK'|'COMP128-v1'|NULL
        description     TEXT,               -- 한국어 절차 설명
        background      TEXT,               -- "왜 이 절차?" 교육 설명
        raw_ttcn3_id    TEXT,               -- 원본 TTCN-3 ID ('TC_8_1_2_2')
        source_file     TEXT                -- 소스 파일 경로
    );

    -- TC 메시지 시퀀스
    CREATE TABLE IF NOT EXISTS tc_steps (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        tc_id       TEXT REFERENCES tcs(id) ON DELETE CASCADE,
        step_no     INTEGER,
        from_entity TEXT,   -- 'UE'|'eNB'|'gNB'|'MME'|'AMF'|'BTS'|'BSC'|'MSC'|'RNC'
        to_entity   TEXT,
        message     TEXT,   -- 'RRCSetupRequest'|'AttachRequest'...
        direction   TEXT,   -- 'ul'(UE→net)|'dl'(net→UE)|'int'(internal)
        layer       TEXT,   -- 'RRC'|'NAS'|'MAC'|'RLC'|'PDCP'|'SDAP'
        ue_state_before TEXT, -- JSON: {"rrc":"RRC_IDLE","emm":"..."}
        ue_state_after  TEXT,
        timer_start TEXT,   -- JSON array: ["T300","T3410"]
        timer_stop  TEXT,   -- JSON array
        note        TEXT,   -- UE 모뎀 동작 설명 (한국어)
        log_line    TEXT    -- QXDM 스타일 로그
    );

    -- IE 글로벌 라이브러리 (ASN.1 파싱)
    CREATE TABLE IF NOT EXISTS ies (
        name        TEXT PRIMARY KEY,  -- 'RRCSetupRequest'|'MasterInformationBlock'
        spec_origin TEXT,              -- 'TS 36.331'|'TS 38.331'|'TS 25.331'
        generation  TEXT,              -- '4G'|'5G'|'3G'|'2G'
        asn1_type   TEXT,              -- 'SEQUENCE'|'CHOICE'|'ENUMERATED'|'INTEGER'|'BIT STRING'
        definition  TEXT               -- 원본 ASN.1 텍스트 블록
    );

    -- IE 필드 트리 (SEQUENCE 필드, CHOICE 옵션)
    CREATE TABLE IF NOT EXISTS ie_fields (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        ie_name     TEXT REFERENCES ies(name) ON DELETE CASCADE,
        field_name  TEXT,
        field_type  TEXT,      -- 참조 IE 이름 또는 기본 타입
        is_optional INTEGER DEFAULT 0,  -- 1=OPTIONAL
        comment     TEXT,      -- ASN.1 주석 (-- 이후)
        sort_order  INTEGER    -- 필드 순서
    );

    -- TC ↔ IE 연결
    CREATE TABLE IF NOT EXISTS tc_ies (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        tc_id       TEXT REFERENCES tcs(id) ON DELETE CASCADE,
        step_id     INTEGER REFERENCES tc_steps(id),
        parent_id   INTEGER REFERENCES tc_ies(id),  -- 중첩 IE
        name        TEXT,          -- IE 이름 (ASN.1 필드명 그대로)
        value       TEXT,          -- 예시값 ('mo-Signalling'|'0x01'...)
        mandatory   INTEGER,       -- 1=mandatory, 0=optional
        ref_spec    TEXT,          -- 'TS 36.331 §6.2.2' (IE 정의 위치)
        ref_proc    TEXT           -- 'TS 36.331 §5.3.3' (절차 위치)
    );

    -- 밴드 정보
    CREATE TABLE IF NOT EXISTS bands (
        band_num    TEXT,           -- '1'|'3'|'n78'|'B38' (LTE: 정수, NR: n+정수)
        generation  TEXT,           -- '4G'|'5G'|'3G'|'2G'
        freq_dl_mhz REAL,
        freq_ul_mhz REAL,
        duplex_mode TEXT,           -- 'FDD'|'TDD'|'SDL'|'SUL'
        region      TEXT,           -- 'Global'|'Europe'|'Korea'|'US'|'Japan'
        PRIMARY KEY (band_num, generation)
    );

    -- 밴드 조합 (CA, EN-DC, NR-DC)
    CREATE TABLE IF NOT EXISTS band_combos (
        id              TEXT PRIMARY KEY,   -- 'CA_1A-3A'|'EN-DC_1-n78'
        combo_type      TEXT,               -- 'CA'|'EN-DC'|'NR-DC'|'SUL'
        generation      TEXT,               -- '4G'|'5G'|'NSA'
        bands_involved  TEXT,               -- 'B1,B3'|'B1,n78' (쉼표 구분)
        cert_type       TEXT,               -- 'GCF'|'PTCRB'
        ref_spec        TEXT                -- 'TS 36.523-1 §12.x'
    );

    -- TC ↔ 밴드 조합
    CREATE TABLE IF NOT EXISTS tc_bands (
        tc_id           TEXT REFERENCES tcs(id) ON DELETE CASCADE,
        band_combo_id   TEXT REFERENCES band_combos(id),
        PRIMARY KEY (tc_id, band_combo_id)
    );

    -- 스펙 메타
    CREATE TABLE IF NOT EXISTS specs (
        ts_num      TEXT PRIMARY KEY,   -- '36.523-3'
        title       TEXT,
        release     INTEGER,
        zip_file    TEXT,               -- '36523-3-ib0.zip'
        local_dir   TEXT,               -- 'specs/36523-3/'
        downloaded  INTEGER DEFAULT 0,
        tc_count    INTEGER DEFAULT 0
    );

    -- 인덱스
    CREATE INDEX IF NOT EXISTS idx_tcs_generation ON tcs(generation);
    CREATE INDEX IF NOT EXISTS idx_tcs_category   ON tcs(category);
    CREATE INDEX IF NOT EXISTS idx_tcs_error      ON tcs(is_error_case);
    CREATE INDEX IF NOT EXISTS idx_tc_steps_tc    ON tc_steps(tc_id);
    CREATE INDEX IF NOT EXISTS idx_tc_ies_tc      ON tc_ies(tc_id);
    CREATE INDEX IF NOT EXISTS idx_ie_fields_ie   ON ie_fields(ie_name);
    """)

    # specs 메타데이터 초기 입력
    specs_data = [
        ('36.523-3', 'LTE Protocol Conformance Part 3 (TTCN-3)', 18, '36523-3-ib0.zip', 'specs/36523-3/', 1, 384),
        ('38.523-3', 'NR Protocol Conformance Part 3 (TTCN-3)', 18, '38523-3-i60.zip', 'specs/38523-3/', 1, 413),
        ('34.123-3', 'UMTS UE Protocol Conformance Part 3 (TTCN-3)', 18, '34123-3-i30.zip', 'specs/34123-3/', 1, 77),
        ('36.523-1', 'LTE Protocol Conformance Part 1', 19, '36523-1-j10.zip', 'specs/36523-1/', 1, 0),
        ('51.010-1', 'GSM MS Conformance Part 1', 18, '51010-1-de0.zip', 'specs/51010-1/', 1, 0),
        ('31.121',   'USIM Application Test Spec', 18, '31121-i50.zip', 'specs/31121/', 1, 0),
        ('31.122',   'USIM Conformance Test Spec', 18, '31122-i50.zip', 'specs/31121/', 1, 0),
        ('36.331',   'LTE RRC (Core Spec)', 18, '36331-i90.zip', 'specs/core/', 1, 0),
    ]
    cur.executemany(
        "INSERT OR IGNORE INTO specs (ts_num, title, release, zip_file, local_dir, downloaded, tc_count) VALUES (?,?,?,?,?,?,?)",
        specs_data
    )

    conn.commit()
    conn.close()

    db_size = os.path.getsize(DB_PATH) / 1024
    print(f"✅ tc.db initialized: {DB_PATH}")
    print(f"   Size: {db_size:.1f} KB")
    print(f"   Tables: tcs, tc_steps, tc_ies, ies, ie_fields, bands, band_combos, tc_bands, specs")


if __name__ == '__main__':
    init_db()
