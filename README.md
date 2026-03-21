# 3GPP Protocol Simulator

신입 모뎀 개발자를 위한 인터랙티브 프로토콜 시뮬레이터.  
**3GPP 공식 TTCN-3/DOCX 스펙에서 직접 추출한 900개+ TC**를 SQLite DB로 관리하고, DB → HTML 파이프라인으로 시각화합니다.

---

## 지원 범위

| 세대 | 표준 | TC 소스 스펙 | TC 수 |
|------|------|------------|-------|
| **2G GSM** | TS 44.018, TS 24.008 | TS 51.010-1 (DOCX) | TBD |
| **3G UMTS** | TS 25.331, TS 24.008 | TS 34.123-3 (TTCN-3) | 77개 |
| **4G LTE** | TS 36.331, TS 24.301, TS 33.401 | TS 36.523-3 (TTCN-3) | **384개** |
| **5G NR SA** | TS 38.331, TS 24.501, TS 33.501 | TS 38.523-3 (TTCN-3) | **413개** |
| **5G EN-DC** | TS 38.331 + TS 36.331 | TS 38.523-3 ENDC (TTCN-3) | TBD |
| **NTN (위성)** | TS 38.863 | TS 38.523-3 §6.7 (TTCN-3) | 포함됨 |
| **USIM** | TS 31.102, TS 33.102 | TS 31.121/31.122 (DOCX) | TBD |

---

## TC ID 체계

TC ID = **3GPP 스펙 번호 + 섹션 번호** (기존 임의 번호 대신 스펙 직접 추적 가능)

```
형식:  {스펙번호}-{섹션번호}
예시:  36523-1-8.1.2.2
       ↑TS 36.523-1 §8.1.2.2 → RRC connection establishment / Reject with wait time

       38523-1-4.5.1.1
       ↑TS 38.523-1 §4.5.1.1 → NR RRC Setup SA

       51010-1-8.1.1
       ↑TS 51.010-1 §8.1.1 → GSM Location Update
```

**TTCN-3 자동 변환**: `TC_8_1_2_2` → `36523-1-8.1.2.2`

---

## 프로젝트 구조

```
Protocol_simulator/
├── README.md              ← 이 파일
├── index.html             ← 교육용 시뮬레이터 (tc.db에서 생성됨)
├── tc.db                  ← SQLite DB (소스 오브 트루스)
│
├── specs/                 ← 3GPP 공식 스펙 파일
│   ├── 36523-3/          ← LTE TTCN-3 (TS 36.523-3, 384 TCs)
│   ├── 38523-3/          ← NR TTCN-3 (TS 38.523-3, 413 TCs, NTN/UAC 포함)
│   ├── 34123-3/          ← 3G TTCN-3 (TS 34.123-3, 77 TCs)
│   ├── 36523-1/          ← LTE Part 1 DOCX (TC 제목 추출용)
│   ├── 51010-1/          ← 2G DOCX (TS 51.010-1)
│   ├── 31121/            ← USIM DOCX (TS 31.121 + 31.122)
│   └── core/             ← Core 스펙 DOCX (TS 36.331 LTE RRC 등)
│
└── tools/                 ← DB 구축 파이프라인
    ├── init_db.py         ← DB 스키마 초기화 (8개 테이블)
    ├── extract_from_ttcn3.py  ← TTCN-3 → tcs 전수 입력
    ├── extract_asn1_ies.py    ← ASN.1 → ies + ie_fields
    ├── extract_tc_title.py    ← Part 1 DOCX → short_name
    ├── extract_procedures.py  ← Core DOCX → tc_steps
    └── generate_html.py       ← tc.db → index.html 재생성
```

---

## DB 구조 (tc.db)

```
tcs          — TC 마스터 (900개+, 세대/카테고리/스펙 정보)
tc_steps     — 메시지 시퀀스 (UE↔네트워크 메시지 흐름)
tc_ies       — TC별 IE 연결 (어떤 step에서 어떤 IE 사용)
ies          — IE 글로벌 라이브러리 (ASN.1 IE 정의)
ie_fields    — IE 필드 트리 (SEQUENCE/CHOICE 재귀 구조)
bands        — 밴드 정보 (주파수, FDD/TDD, 지역)
band_combos  — 밴드 조합 (CA, EN-DC, NR-DC)
specs        — 스펙 메타데이터
```

### `tcs` 주요 컬럼

| 컬럼 | 예시 | 설명 |
|------|------|------|
| `id` | `36523-1-8.1.2.2` | TC ID = 스펙 섹션번호 |
| `short_name` | `RRC Conn Est / Reject` | 제목 (Part 1 DOCX 추출) |
| `generation` | `4G` | `2G`\|`3G`\|`4G`\|`5G`\|`NTN`\|`USIM` |
| `category` | `RRC` | `RRC`\|`NAS`\|`MAC`\|`Security`\|`CA`... |
| `conf_spec` | `TS 36.523-1 §8.1.2.2` | 적합성 스펙 참조 |
| `core_specs` | `TS 36.331 §5.3.3` | 코어 스펙 참조 |
| `is_error_case` | `1` | 에러/Reject/Timeout 케이스 |
| `usim_interface` | `EPS-AKA` | USIM 인증 방식 |
| `auth_algo` | `Milenage` | `Milenage`\|`TUAK`\|`COMP128` |

---

## 환경 구성 및 실행

```bash
# 1. Python 의존성 설치
pip install python-docx asn1tools

# 2. DB 초기화
python tools/init_db.py

# 3. TTCN-3 → DB 전수 입력 (LTE 384 + NR 413 + 3G 77개)
python tools/extract_from_ttcn3.py

# 4. ASN.1 IE 라이브러리 구축
python tools/extract_asn1_ies.py

# 5. TC 제목 채우기 (Part 1 DOCX)
python tools/extract_tc_title.py

# 6. HTML 재생성
python tools/generate_html.py

# 7. 브라우저에서 열기
start index.html  # Windows
open index.html   # macOS
```

---

## 교육 활용법 (DB 쿼리 예시)

```sql
-- 4G LTE RRC TC 전체
SELECT id, short_name FROM tcs WHERE generation='4G' AND category='RRC';

-- 에러/실패 케이스만 (중요!)
SELECT id, short_name, generation FROM tcs WHERE is_error_case=1;

-- 5G-AKA / SUCI 인증 TC
SELECT id, short_name FROM tcs WHERE usim_interface='5G-AKA';

-- NTN (위성통신) TC
SELECT id, short_name FROM tcs WHERE generation='5G' AND category LIKE '%NTN%';

-- UAC (Unified Access Control) TC
SELECT id, short_name FROM tcs WHERE category='UAC';

-- 세대별 TC 수량
SELECT generation, COUNT(*) FROM tcs GROUP BY generation;

-- 특정 밴드 조합 TC
SELECT t.id, t.short_name FROM tcs t
JOIN tc_bands tb ON t.id=tb.tc_id
JOIN band_combos bc ON tb.band_combo_id=bc.id
WHERE bc.combo_type='EN-DC';
```

---

## TTCN-3 소스 인벤토리

### 4G LTE — TS 36.523-3 (384 TCs)

| 섹션 | 폴더 | 내용 |
|------|------|------|
| §6.1 | `LTE/6_1/` | 셀 재선택, PLMN 선택 |
| §7.1~7.3 | `LTE/7_x/` | MAC / RLC / PDCP |
| §8.1~8.5 | `LTE/8_x/` | RRC 연결/핸드오버/재구성/RLF |
| **§9.1** | `LTE/9_1/` | **EPS-AKA 인증 10개** (Mac Fail/Sync Fail/Auth Reject 포함) |
| §9.2~9.4 | `LTE/9_x/` | Attach/Detach/TAU, NAS 보안 |
| §10 | `LTE/10/` | ESM Bearer 관리 |
| §11 | `LTE/11/` | IMS 긴급통화, SMS |
| **§12** | `LTE/12.x` | **Band Combination (CA)** |
| **§13** | `LTE/13/` | **EAB (Enhanced Access Barring)** |
| §14 | `LTE/14.x` | UE Capability 보고 |
| - | `NB/` | NB-IoT 인증/보안 |

**ASN.1**: `EUTRA_RRC_ASN1_Definitions.asn` (653KB), `UTRAN_RRC_ASN1_Definitions.asn` (1.44MB)

### 5G NR SA — TS 38.523-3 (413 TCs)

| 섹션 | 폴더 | 내용 |
|------|------|------|
| §6.1.2 | `6_1_2/` | **셀 선택/재선택** |
| **§6.7** | `6_7_1~2/` | 🛰 **NTN (위성통신) — Idle/Inactive** |
| §7.1 | `7_1_x/` | MAC/RLC/PDCP/SDAP (NTN 포함) |
| §8.x | (다수) | **RRC 141개** — CA/NRDC 포함 (최대 섹션) |
| §9.x | `Auth/` | **5G-AKA, EAP-AKA', SUCI/SUPI 식별** |
| §10.1 | `10_1/` | IMS/GSM 음성 over NR5GC |
| **§11.3** | `11_3/` | 🔒 **UAC (Unified Access Control)** |
| §11.5~11.7 | `11_x/` | eCall, PS Data Off, eDRX |

**ASN.1**: `NR_RRC_ASN1_Definitions.asn` (1.57MB)

### 5G EN-DC — TS 38.523-3 ENDC

LTE+NR 동시 사용 (NSA 모드): `RRC_UECapability_ENDC_*.ttcn`, `RRC_CarrierAggregation_ENDC_*.ttcn`, `MAC_CA_ENDC_*.ttcn`, `NR_CapabilityFunctions_MRDC.ttcn` 등

### 3G UMTS — TS 34.123-3 (77 TCs)

| 섹션 | 폴더 | 내용 |
|------|------|------|
| §8.1 | `8_1/` | 3G 페이징, UE 능력 보고 |
| §9 | `9/` | Location Updating |
| §12 | `12/` | GPRS GMM |
| **§15** | `15/` | **보충서비스 73개** — CallFwd/Hold/Wait/MultiParty/CLIP/CLIR |

### USIM — TS 31.121 / 31.122

- UICC ↔ 단말 APDU 인터페이스 테스트
- EF 파일 접근: EF_IMSI, EF_KEYS, EF_LOCI, EF_ACC, EF_HPPLMN
- PIN/PUK 검증, SIM Lock (Network Personalisation)

---

## 주요 기능 (index.html)

- **멀티 RAT**: 2G GSM / 3G WCDMA / 4G LTE / 5G NR SA / EN-DC / NTN / USIM
- **시퀀스 다이어그램**: UE 기준 메시지 흐름 시각화
- **IE 드릴다운**: ASN.1 기반 정확한 필드명·값·레퍼런스 (클릭 확장)
- **UE 상태머신**: RRC/NAS 상태 실시간 표시
- **타이머**: T300/T310/T3410/T3512 등 3GPP 정의 타이머
- **QXDM 스타일 로그**: 실제 모뎀 디버깅 포맷과 동일
- **에러 케이스**: Reject/Timeout/Failure TC 포함 (`is_error_case=1`)
- **세대 비교**: 인증 발전사 (SIM A3A8 → UMTS-AKA → EPS-AKA → 5G-AKA/SUCI)

---

## 스펙 다운로드 정보

3GPP 스펙 파일은 `specs/` 폴더에 포함되어 있습니다.  
다운로드 URL 패턴: `https://www.3gpp.org/ftp/Specs/archive/{N}_series/{spec}/{filename}.zip`

| 파일 | 스펙 | 역할 |
|------|------|------|
| 36523-3-ib0.zip | TS 36.523-3 | LTE TTCN-3 (384 TCs) |
| 38523-3-i60.zip | TS 38.523-3 | NR TTCN-3 (413 TCs + NTN) |
| 34123-3-i30.zip | TS 34.123-3 | 3G TTCN-3 (77 TCs) |
| 36523-1-j10.zip | TS 36.523-1 | LTE Part 1 (TC 제목) |
| 51010-1-de0.zip | TS 51.010-1 | 2G DOCX |
| 31121-i50.zip | TS 31.121 | USIM Application Test |
| 36331-i90.zip | TS 36.331 | LTE RRC Core |

---

## 기여 방법

1. `tc.db`에 SQL로 TC 추가/수정 (`INSERT INTO tcs ...`)
2. `python tools/generate_html.py` 실행으로 index.html 재생성
3. Pull Request

```sql
-- 새 TC 추가 예시
INSERT INTO tcs (id, short_name, generation, category, conf_spec, core_specs, is_error_case)
VALUES ('36523-1-9.1.2.5', 'EPS-AKA Sync Failure', '4G', 'NAS',
        'TS 36.523-1 §9.1.2.5', 'TS 33.401 §6.1.2', 1);
```
