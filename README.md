# 3GPP Protocol Simulator

단말(UE/MS) 기준으로 2G GSM / 3G WCDMA / 4G LTE / 5G NR 무선 프로토콜이 어떻게 동작하는지 시각화하는 인터랙티브 시뮬레이터입니다.
PTCRB / GCF / GSMA 인증 테스트 케이스(TC) 기반 시퀀스 다이어그램 + IE 드릴다운 + UE 상태머신 + 타이머 + QXDM 스타일 로그를 단일 HTML 파일로 제공합니다.

---

## 실행 방법

```bash
# 별도 서버 불필요 — 브라우저에서 직접 열기
open index.html          # macOS
xdg-open index.html      # Linux
start index.html         # Windows
```

또는 로컬 서버:

```bash
python3 -m http.server 8080
# → http://localhost:8080
```

**외부 의존성 없음** — CDN, npm, 빌드 도구 전혀 필요 없습니다.

---

## 파일 구조

```
Protocol_simulator/
└── index.html          # 전체 시뮬레이터 (2383줄, 117KB, 단일 파일)
    ├── <style>         # 다크 텔레콤 테마 CSS (인라인)
    ├── TC_DATA[]       # 55개 테스트 케이스 JSON 데이터
    └── <script>        # 렌더링 / 애니메이션 / 이벤트 처리 JS
```

---

## 주요 기능

### 1. 멀티 RAT 지원

| 세대 | 표준 | 프로토콜 스택 | 네트워크 노드 |
|------|------|--------------|--------------|
| **2G GSM** | TS 44.018, TS 24.008, TS 51.010-1 | PHY → LAPDm → RR / MM / CC / GMM / SM | MS, BTS, BSC, MSC, HLR, SGSN, GGSN |
| **3G WCDMA** | TS 25.331, TS 24.008, TS 34.123-1 | PHY → MAC → RLC → RRC / NAS(MM/CM/GMM/SM) | UE, NodeB, RNC, MSC, SGSN, HLR |
| **4G LTE** | TS 36.331, TS 24.301, TS 36.523-1 | PHY → MAC → RLC → PDCP → RRC / NAS(EMM/ESM) | UE, eNB, MME, HSS, S-GW, P-GW |
| **5G NR** | TS 38.331, TS 24.501, TS 38.523-1 | PHY → MAC → RLC → PDCP → SDAP → RRC / NAS(5GMM/5GSM) | UE, gNB, AMF, SMF, UPF, UDM, AUSF |

### 2. 55개 테스트 케이스

#### 2G GSM — PTCRB/GCF (TC-G01 ~ TC-G10)

| TC ID | Spec | 절차 |
|-------|------|------|
| TC-G01 | TS51.010-8.1.1 | Channel Request + Immediate Assignment (RR) |
| TC-G02 | TS51.010-8.2.1 | Normal Location Updating + IMSI Attach (MM) |
| TC-G03 | TS51.010-8.3.1 | MO Voice Call (CC) |
| TC-G04 | TS51.010-8.3.5 | MT Voice Call (CC) |
| TC-G05 | TS51.010-8.9.1 | GPRS Attach (GMM) |
| TC-G06 | TS51.010-8.9.5 | PDP Context Activation (SM) |
| TC-G07 | TS51.010-8.4.1 | Authentication — A3/A8 (MM) |
| TC-G08 | TS51.010-8.5.1 | Ciphering Mode Command (RR) |
| TC-G09 | TS51.010-8.6.1 | BSS Internal Handover |
| TC-G10 | TS51.010-8.1.5 | RACH Access Class Barring |

#### 3G WCDMA — PTCRB (TC-W01 ~ TC-W10)

| TC ID | Spec | 절차 |
|-------|------|------|
| TC-W01 | TS34.123-7.1.1.1 | RRC Connection Establishment (TS 25.331 §8.1.3) |
| TC-W02 | TS34.123-7.1.1.6 | RRC Connection Release |
| TC-W03 | TS34.123-7.1.2.1 | Radio Bearer Setup (RAB 수립) |
| TC-W04 | TS34.123-7.2.1.1 | Combined RA+LA Update (MM/GMM) |
| TC-W05 | TS34.123-7.3.1.1 | CS Voice Call MO (TS 24.008 CC) |
| TC-W06 | TS34.123-7.4.1.1 | PDP Context Activation (PS Domain) |
| TC-W07 | TS34.123-7.2.2.1 | UMTS-AKA Authentication |
| TC-W08 | TS34.123-7.5.1.1 | Security Mode Control (UIA1+UEA1) |
| TC-W09 | TS34.123-7.3.2.1 | Measurement Report + Soft Handover |
| TC-W10 | TS34.123-7.1.4.1 | Cell Update / URA Update |

#### 4G LTE — PTCRB (TC-L01 ~ TC-L15)

| TC ID | Spec | 절차 | IE 상세 |
|-------|------|------|---------|
| TC-L01 | TS36.523-8.1.4.1 | RRC Connection Establishment | ★ Full IE |
| TC-L02 | TS36.523-8.1.4.6 | RRC Re-establishment (RLF, T310 expire) | 상세 |
| TC-L03 | TS36.523-8.1.4.2 | RRC Connection Release | - |
| TC-L04 | TS36.523-8.1.4.4 | RRC Connection Reconfiguration (DRB 추가) | - |
| TC-L05 | TS36.523-8.1.3.1 | Initial EPS Attach + AKA | ★ Full IE |
| TC-L06 | TS36.523-8.1.3.2 | Tracking Area Update (T3412) | - |
| TC-L07 | TS36.523-8.1.3.4 | EPS Detach (UE-initiated) | - |
| TC-L08 | TS36.523-8.2.1.1 | X2 Intra-LTE Handover (T304) | 상세 |
| TC-L09 | TS36.523-8.2.3.1 | S1 Handover (X2 없음) | - |
| TC-L10 | TS36.523-8.3.1 | EPS-AKA Authentication (RAND/AUTN/RES) | 상세 |
| TC-L11 | TS36.523-8.3.2 | AS Security Mode Command (EEA2+EIA2) | 상세 |
| TC-L12 | TS36.523-8.4.1 | Dedicated EPS Bearer 활성화 (QCI=1, VoLTE) | - |
| TC-L13 | TS36.523-8.5.1 | UE Capability Enquiry | - |
| TC-L14 | TS36.523-8.6.1 | RRC Measurement Config (A3 이벤트) | - |
| TC-L15 | IR.92 | VoLTE MO Call (PTCRB IMS) | - |

#### 5G NR — GCF (TC-N01 ~ TC-N12)

| TC ID | Spec | 절차 | IE 상세 |
|-------|------|------|---------|
| TC-N01 | TS38.523-4.5.1.1 | NR RRC Setup SA — 4-step RACH | ★ Full IE |
| TC-N02 | TS38.523-4.5.3.1 | RRC Inactive Resume (I-RNTI) | 상세 |
| TC-N03 | TS38.523-4.5.2.1 | NR RRC Connection Release | - |
| TC-N04 | TS38.523-4.6.1.1 | 5G Registration + 5G-AKA (SUCI/HXRES*) | ★ Full IE |
| TC-N05 | TS38.523-4.6.1.2 | 5G Deregistration | - |
| TC-N06 | TS38.523-4.6.2.1 | PDU Session 수립 + SDAP/QFI 매핑 | 상세 |
| TC-N07 | TS38.523-4.7.1.1 | NR Intra-freq Handover (Xn) | - |
| TC-N08 | TS38.523-4.8.1.1 | EN-DC Setup — NSA (MN-eNB + SN-gNB) | 상세 |
| TC-N09 | TS38.523-4.8.2.1 | SCell Addition (NR CA) | - |
| TC-N10 | TS38.523-4.9.1.1 | Configured Grant — URLLC (SR 없이 UL) | 상세 |
| TC-N11 | TS38.523-4.6.4.1 | 5G Periodic Registration Update (T3512) | - |
| TC-N12 | TS38.523-4.5.4.1 | NR 2-step RACH (msgA / msgB) | - |

#### GSMA (TC-S01 ~ TC-S08)

| TC ID | Spec | 절차 |
|-------|------|------|
| TC-S01 | IR.92 | VoLTE MO Call (SIP INVITE → RTP) |
| TC-S02 | IR.92 | VoLTE MT Call |
| TC-S03 | IR.51 | VoWiFi IMS Registration — EAP-AKA' (ePDG/IKEv2) |
| TC-S04 | SGP.22 | eSIM Profile Download (ES9+ / SM-DP+) |
| TC-S05 | TS.26 | eCall MSD Transmission (ERA-GLONASS, EN 15722) |
| TC-S06 | IR.21 | IMSI-based Roaming — vPLMN Attach + S6a AIR |
| TC-S07 | SGP.02 | M2M Remote SIM Provisioning (SM-SR / SM-DP) |
| TC-S08 | GSMA NB-IoT | PSM + eDRX 설정 (T3412/T3324) |

---

### 3. IE(Information Element) 드릴다운

시퀀스 다이어그램의 메시지 스텝을 클릭하면 하단에 IE 인스펙터가 열립니다.

```
▶ ue-Identity            CHOICE   s-TMSI       *   TS36.331§6.2.2
  ▶ mmec                 BIT(8)   0x01         *   TS36.331§6.3.6
  ▶ m-TMSI               BIT(32)  0xABCD1234   *   TS36.331§6.3.6
▶ establishmentCause     ENUM     mo-Signalling *   TS36.331§6.2.2
  spare                  BIT(1)   0                 TS36.331§6.2.2
```

- `*` = mandatory IE (빨간색)
- 클릭으로 중첩 IE 펼치기/접기
- `ref` = 정확한 3GPP TS 섹션 번호
- 하단 노란 박스 = UE 모뎀 레이어 동작 설명 (한국어)

### 4. UE 상태머신

현재 세대에 따라 적용되는 상태를 실시간 표시:

| 세대 | 표시 상태 |
|------|----------|
| 2G | RR, MM, CC, GMM |
| 3G | RRC, MM, CM, GMM |
| 4G | RRC (IDLE/CONNECTED), EMM (DEREGISTERED/REGISTERED), ECM (IDLE/CONNECTED) |
| 5G | RRC (IDLE/CONNECTED/INACTIVE), 5GMM (DEREGISTERED/REGISTERED-INITIATED/REGISTERED) |

### 5. 타이머 표시

3GPP 정의 타이머가 step의 `timer.start` / `timer.stop` 에 따라 실시간 갱신:

```
T300    running   1000ms      ← RRCConnectionRequest 전송 후
T3410   running   15s         ← Attach Request 전송 후
T3512   running   54min (def) ← Registration Accept 후
```

주요 타이머 목록:

| 구분 | 타이머 |
|------|--------|
| 4G RRC | T300, T301, T302, T304, T310, T311, T320, T321, T325 |
| 4G NAS | T3410, T3411, T3412, T3416, T3421, T3430, T3440 |
| 5G NAS | T3510, T3511, T3512, T3516, T3521, T3524, T3540, T3324, T3346 |
| 2G/3G | T3122, T3210, T3212, T3240, T3310, T3312, T3380 |

### 6. QXDM 스타일 모뎀 로그

실제 QXDM 필터에서 볼 수 있는 형태로 로그 출력:

```
[RRC] TX RRCConnectionRequest SRB0/CCCH s-TMSI mmec=0x01 m-TMSI=0xABCD1234 cause=mo-Signalling T300 start
[RRC] RX RRCConnectionSetup txId=0 SRB1 AM-RLC LCID=1 T300 stop → RRC_CONNECTED
[NAS] TX AttachRequest IMSI=208931234567890 type=EPS_ONLY EEA=0,1,2,3 EIA=1,2,3 T3410=15s start
[NAS] RX AuthenticationRequest KSI_ASME=3 RAND=0x8D71... AUTN=0xC45F...
```

---

## UI 조작 방법

### 헤더 탭

```
[2G] [3G] [4G] [5G] [ALL]    ← 세대 필터
[PTCRB] [GCF] [GSMA] [ALL]   ← 인증기관 필터
```

### 컨트롤

| 버튼 | 단축 | 동작 |
|------|------|------|
| ▶ Run | - | 자동 재생 (Slow/Normal/Fast/Turbo 속도 선택) |
| ⊳ Step | - | 1 스텝씩 진행 |
| ↺ Reset | - | 시뮬레이션 초기화 |

### 시퀀스 다이어그램

- 각 스텝 행 클릭 → 하단 IE 인스펙터 업데이트
- 현재 실행 중인 스텝 → 파란색 강조
- 완료된 스텝 → 초록색 흐린 배경

### 하단 프로토콜 스택

현재 스텝의 레이어가 강조 표시됩니다:

```
2G: [PHY]─[LAPDm]─[RR]─[MM]─[CC]─[GMM]─[SM]
3G: [PHY]─[MAC]─[RLC]─[RRC]─[MM]─[CM]─[GMM]─[SM]
4G: [PHY]─[MAC]─[RLC]─[PDCP]─[RRC]─[NAS-EMM]─[NAS-ESM]
5G: [PHY]─[MAC]─[RLC]─[PDCP]─[SDAP]─[RRC]─[NAS-5GMM]─[NAS-5GSM]
```

---

## 데이터 구조 (TC 확장 방법)

`index.html` 내 `TC_DATA` 배열에 아래 스키마로 TC를 추가합니다:

```javascript
{
  id:       "TC-L16",            // 고유 ID
  gen:      "4G",                // "2G" | "3G" | "4G" | "5G" | "NSA"
  cert:     "PTCRB",             // "PTCRB" | "GCF" | "GSMA"
  cat:      "RRC",               // 카테고리 문자열
  name:     "RRC Connection ...",
  spec:     "TS 36.523-1 §8.1.4.x / TS 36.331 §5.3.x",
  desc:     "한국어 설명",
  entities: ["UE", "eNB", "MME"],
  stack:    "4G",                // 하단 스택 표시용
  steps: [
    {
      dir:            "ul",      // "ul"(UE→net) | "dl"(net→UE) | "int"(INTERNAL)
      from:           0,         // entities 배열 인덱스
      to:             1,
      msg:            "RRCConnectionRequest",
      layer:          "RRC",     // 색상·스택 하이라이트 결정
      ue_action:      "TX",      // "TX" | "RX" | "INTERNAL"
      ue_state_before: { rrc:"RRC_IDLE", emm:"EMM-REGISTERED", ecm:"ECM-IDLE" },
      ue_state_after:  { rrc:"RRC_IDLE" },
      timer:          { start:["T300"], stop:[] },
      ies: [
        {
          name:      "ue-Identity",
          type:      "CHOICE",
          value:     "s-TMSI",
          mandatory: true,
          ref:       "TS 36.331 §6.2.2",
          children: [
            { name:"mmec",   type:"BIT STRING(8)",  value:"0x01",         mandatory:true, ref:"TS 36.331 §6.3.6" },
            { name:"m-TMSI", type:"BIT STRING(32)", value:"0xABCD1234",   mandatory:true, ref:"TS 36.331 §6.3.6" }
          ]
        }
      ],
      log:      "TX RRCConnectionRequest SRB0/CCCH s-TMSI mmec=0x01 cause=mo-Signalling T300 start",
      ue_note:  "SRB0(CCCH)으로 전송. T300=1000ms 시작."
    }
  ]
}
```

### 레이어 값 → 색상 매핑

| layer 값 | 색상 | 설명 |
|----------|------|------|
| `PHY` | #f97316 orange | Physical |
| `MAC` | #f59e0b yellow | Medium Access Control |
| `RLC` | #10b981 green | Radio Link Control |
| `PDCP` | #3b82f6 blue | Packet Data Convergence Protocol |
| `SDAP` | #8b5cf6 purple | Service Data Adaptation Protocol (5G) |
| `RRC` | #06b6d4 cyan | Radio Resource Control |
| `RR` | #14b8a6 teal | Radio Resource (2G/3G) |
| `NAS` / `MM` / `GMM` | #ef4444 red | Non-Access Stratum |
| `CC` | #fb7185 rose | Call Control |
| `IMS` | #ec4899 pink | IP Multimedia Subsystem |
| `APP` | #6366f1 indigo | Application |
| `SYS` | #64748b gray | System / core network internal |

---

## AI를 이용한 TC 대량 생성

실제 인증 카탈로그는 수천 개 TC를 포함합니다
(PTCRB TS 36.523-1 단독 LTE ~1,000개+, TS 51.010-1 2G ~2,000개+).
아래 프롬프트로 Claude/GPT-4에 TC JSON을 생성시킨 후 `TC_DATA`에 추가하면 됩니다:

```
You are a 3GPP modem protocol engineer writing test case data for a UE-side protocol simulator.

## Perspective
ALL steps must be from UE modem's perspective:
- dir: "ul"(UE sends), "dl"(UE receives), "int"(UE internal state change)
- ue_state_before/after: UE RRC/NAS state at that step
- ue_note: what the UE modem layer actually does (Korean)
- timer: which 3GPP timers start or stop

## IE Detail Rules
For each step, populate "ies" with ALL significant IEs:
- name: exact ASN.1 IE name from TS 36.331 or 38.331
- value: realistic example value (hex for identifiers)
- ref: exact TS section
- mandatory: true if mandatory per spec

## Output
Return ONLY a JSON array matching the TC schema in README.md.
No markdown fences. No explanation.

## Task
Generate UE-perspective test cases for:
Certification: PTCRB
Spec: TS 36.523-1 Section 8.1 — RRC procedures
Cover: 8.1.4.1 ~ 8.1.4.8 (establishment, re-establishment, reconfiguration,
       release, reject, suspend/resume, timer tests T300/T301/T310/T311)
Include full IE details.
```

---

## 개발 환경 / 확장 가이드

### 현재 구조 (단일 파일)

```
index.html
├── CSS         ~200줄  다크 텔레콤 테마
├── HTML        ~100줄  레이아웃 골격
├── TC_DATA[]  ~1600줄  55개 TC JSON 데이터
└── JS          ~500줄  렌더링 / 상태머신 / 애니메이션
```

### 확장 아이디어

| 항목 | 방법 |
|------|------|
| TC 추가 | `TC_DATA[]` 배열에 스키마 맞춰 객체 삽입 |
| 외부 TC 파일 | `tc_data.js` 로 분리 후 `<script src="tc_data.js">` |
| TC 자동 생성 파이프라인 | AI 프롬프트 → JSON 출력 → `TC_DATA`에 merge |
| 실제 QXDM 로그 Import | 파일 읽기 → 메시지 파싱 → step으로 변환 |
| ASN.1 자동 렌더링 | TS 36.331 / 38.331 ASN.1 파싱 → IE 트리 자동 생성 |
| 백엔드 연동 | REST API로 TC JSON 제공, 프론트엔드는 fetch만 |

### 다음 AI 에이전트를 위한 인수인계 포인트

1. **`TC_DATA` 배열 위치**: `index.html` 약 190번째 줄부터 시작
2. **렌더링 함수**: `renderDiagram()`, `renderTCList()`, `executeStep()`, `renderIEInspector()`
3. **상태 관리**: `ueState` 객체 — 모든 세대의 UE 상태를 통합 관리
4. **타이머**: `activeTimers` 객체 — `{timer이름: {status, label, dur}}` 구조
5. **스타일 변수**: CSS에서 레이어 색상은 `LAYER_COLORS` JS 객체와 일치시킬 것
6. **세대 전환**: `renderStack(gen)` 함수가 하단 프로토콜 스택을 세대별로 교체
7. **IE 트리**: `renderIENode(ie, depth)` 재귀 함수로 중첩 IE 렌더링

---

## 참고 스펙

| 문서 | 내용 |
|------|------|
| TS 44.018 | GSM/GPRS RR 프로토콜 |
| TS 24.008 | GSM/UMTS MM, CC, SM 프로토콜 |
| TS 25.331 | UMTS RRC 프로토콜 |
| TS 36.331 | LTE RRC 프로토콜 (IE ASN.1 포함) |
| TS 36.523-1 | LTE UE 적합성 테스트 케이스 (PTCRB 기준) |
| TS 38.331 | NR RRC 프로토콜 (IE ASN.1 포함) |
| TS 38.523-1 | NR UE 적합성 테스트 케이스 (GCF 기준) |
| TS 24.301 | LTE NAS (EMM/ESM) 프로토콜 |
| TS 24.501 | 5G NAS (5GMM/5GSM) 프로토콜 |
| TS 33.401 | LTE 보안 구조 (EPS-AKA) |
| TS 33.501 | 5G 보안 구조 (5G-AKA, SUCI) |
| GSMA IR.92 | VoLTE 프로파일 |
| GSMA IR.51 | VoWiFi 프로파일 (EAP-AKA') |
| GSMA SGP.22 | eSIM Consumer 프로파일 |

---

## 스크린샷 구성

```
┌─────────────────────────────────────────────────────────────────────────┐
│ 3GPP Protocol Simulator  [2G][3G][4G][5G][ALL]  [PTCRB][GCF][GSMA][ALL]│
├──────────────┬──────────────────────────────────────┬────────────────────┤
│ TC-L05       │ TC-L05: Initial EPS Attach + AKA     │ UE STATE           │
│ TC-L01 ◀     │ TS36.523-8.1.3.1 / TS24.301 §5.5.1  │ RRC  : CONNECTED   │
│ TC-L02       │ [▶ Run] [⊳ Step] [↺ Reset] Speed▼   │ EMM  : REGISTERED  │
│ TC-L05       │ ─────────────────────────────────    │ ECM  : CONNECTED   │
│ ─────────    │  UE    eNB   MME   HSS               │                    │
│ TC-G01       │   │─RRC►──│     │     │  Step 1/8   │ TIMERS             │
│ TC-G02       │   │◄─RRC──│     │     │  Step 2/8   │ T3412  54min ✓     │
│ ...          │   │──NAS►─┤─────►─MAP►│  Step 3/8   │                    │
│              │   │◄─NAS──┤◄────┤     │  ▶ Step 4   │ LOG                │
│              │ ─ IE Inspector ──────────────────    │ [NAS] TX Attach... │
│              │  ▶ EPS mobile identity IMEI *        │ [NAS] RX AuthReq.. │
│              │    ▶ type  : IMSI                    │ [NAS] TX AuthResp  │
│              │    ▶ value : 208931234567890          │                    │
└──────────────┴──────────────────────────────────────┴────────────────────┘
│ [PHY]─[MAC]─[RLC]─[PDCP]─[RRC]─[▶NAS-EMM◀]─[NAS-ESM]                  │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 라이선스

교육·연구·내부 개발 목적 자유 사용.
3GPP 스펙 참조 정보는 [3gpp.org](https://www.3gpp.org) 공개 문서 기준입니다.
