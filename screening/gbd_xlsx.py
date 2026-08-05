"""GBD 대규모 자동 평가 → 엑셀. output/screening/gbd_auto_eval.xlsx

시트: 1) 요약·퍼널  2) 재단분류 교차표  3) 전체 판정(3,424개사)  4) 방법론
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from screening import rules

OUT = Path(__file__).resolve().parent.parent / "output" / "screening" / "gbd_auto_eval.xlsx"
FONT = "Arial"
HDR = PatternFill("solid", fgColor="1F3864")
HF = Font(name=FONT, bold=True, color="FFFFFF", size=10)
SUB = PatternFill("solid", fgColor="D6DCE4")
GREEN = PatternFill("solid", fgColor="E2EFDA")
YEL = PatternFill("solid", fgColor="FFF2CC")
ORG = PatternFill("solid", fgColor="FCE4D6")
GRY = PatternFill("solid", fgColor="EDEDED")
THIN = Side(style="thin", color="BFBFBF")
BORD = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


def _c(ws, r, c, v, *, bold=False, fill=None, wrap=False, align="left", size=10):
    cell = ws.cell(r, c, v)
    cell.font = Font(name=FONT, bold=bold, size=size)
    cell.alignment = Alignment(horizontal=align, vertical="top", wrap_text=wrap)
    cell.border = BORD
    if fill:
        cell.fill = fill
    return cell


def _hdr(ws, r, hs, ws_):
    for i, (h, w) in enumerate(zip(hs, ws_), 1):
        c = _c(ws, r, i, h, bold=True, fill=HDR, align="center")
        c.font = HF
        ws.column_dimensions[get_column_letter(i)].width = w


def _fill_for(outcome: str) -> PatternFill:
    if "탈락" in outcome or "라우팅" in outcome:
        return ORG
    if "사람 검토" in outcome:
        return YEL
    if "통과" in outcome:
        return GREEN
    return GRY   # 미상/판정불가


def build(rows, s) -> Path:
    wb = Workbook()

    # ---- 시트1 요약 ----
    ws = wb.active
    ws.title = "요약_퍼널"
    ws.sheet_view.showGridLines = False
    _c(ws, 1, 1, f"디캠프 GBD 스타트업 마스터 DB — 500/HAX 엔진 대규모 자동 평가 "
       f"({s['n']:,}개사)", bold=True, size=13)
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=6)
    _c(ws, 2, 1, "DB 정형 필드(업종·기술·스테이지·1줄소개·재단분류)만으로 1차 필터"
       "(트랙 라우팅+하드 게이트)를 결정적 규칙으로 자동 적용. 개별 크롤링·LLM 호출 "
       "없음. 4축 점수(v2/v3)는 1줄 소개만으로 신뢰성 있게 못 매기므로 이 대규모 "
       "단계에서는 산출하지 않는다(팩트시트 있는 102개사는 engine_full_eval.xlsx).",
       size=9, wrap=True)
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=6)
    ws.row_dimensions[2].height = 46

    r = 4
    _c(ws, r, 1, "트랙 라우팅", bold=True, size=11, fill=SUB)
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=2)
    r += 1
    _hdr(ws, r, ["트랙", "기업 수"], [34, 12])
    r += 1
    for k, n in s["track"].most_common():
        _c(ws, r, 1, k)
        _c(ws, r, 2, n, align="center")
        r += 1
    r += 1
    _c(ws, r, 1, "1차 필터 결과", bold=True, size=11, fill=SUB)
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=2)
    r += 1
    _hdr(ws, r, ["게이트 판정", "기업 수"], [34, 12])
    r += 1
    for k, n in s["outcome"].most_common():
        _c(ws, r, 1, k, fill=_fill_for(k))
        _c(ws, r, 2, n, align="center", fill=_fill_for(k))
        r += 1
    scoreable = sum(n for k, n in s["outcome"].items() if "통과" in k)
    r += 1
    _c(ws, r, 1, f"→ 점수화 대상(게이트 통과): {scoreable:,}개사 / "
       f"사람 검토 {s['outcome'].get('사람 검토 (500: A 이후 밴드)', 0):,} / "
       f"게이트 탈락 {s['outcome'].get('게이트 탈락 (HAX 스테이지 이탈 — 시리즈A+)', 0):,}",
       bold=True, wrap=True)
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=6)
    ws.row_dimensions[r].height = 28

    # ---- 시트2 재단분류 교차표 ----
    ws2 = wb.create_sheet("재단분류_교차표")
    ws2.sheet_view.showGridLines = False
    _c(ws2, 1, 1, "재단연관 분류 × 1차 필터 결과 (Type1 패밀리사 / Type2·3 포트폴리오 / 디데이)",
       bold=True, size=12)
    ws2.merge_cells(start_row=1, start_column=1, end_row=1, end_column=7)
    cats = ["Type 1", "Type 2", "Type 3", "디데이 출전팀"]
    buckets = ["점수화 통과", "사람 검토", "게이트 탈락", "바이오 라우팅",
               "스테이지 미상", "정보 부족"]

    def bucket(o):
        if "통과" in o:
            return "점수화 통과"
        if "사람 검토" in o:
            return "사람 검토"
        if "게이트 탈락" in o:
            return "게이트 탈락"
        if "IndieBio" in o:
            return "바이오 라우팅"
        if "미상" in o:
            return "스테이지 미상"
        return "정보 부족"

    cross = {c: Counter() for c in cats}
    for row in rows:
        t = row["type"].split(",")[0].split("(")[0].strip()
        if t in cross:
            cross[t][bucket(row["outcome"])] += 1
    _hdr(ws2, 3, ["재단분류"] + buckets + ["합계"], [16] + [12] * 6 + [10])
    rr = 4
    for c in cats:
        _c(ws2, rr, 1, c, bold=True)
        tot = 0
        for j, b in enumerate(buckets, 2):
            n = cross[c][b]
            tot += n
            _c(ws2, rr, j, n or "", align="center",
               fill=GREEN if b == "점수화 통과" and n else
               YEL if b == "사람 검토" and n else
               ORG if b in ("게이트 탈락", "바이오 라우팅") and n else None)
        _c(ws2, rr, 8, tot, align="center", bold=True)
        rr += 1
    rr += 1
    _c(ws2, rr, 1, "읽는 법: Type1 패밀리사는 디캠프가 직접 투자·입주시킨 기업이라 "
       "스테이지·업종 정보가 충실해 라우팅·게이트가 잘 정해진다. Type3(하위펀드)은 "
       "정보가 얕아 '정보 부족'이 많다. 이는 DB 완결성의 문제이지 엔진의 문제가 아니다.",
       size=9, wrap=True)
    ws2.merge_cells(start_row=rr, start_column=1, end_row=rr, end_column=8)
    ws2.row_dimensions[rr].height = 40

    # ---- 시트3 전체 판정 ----
    ws3 = wb.create_sheet("전체_판정")
    ws3.sheet_view.showGridLines = False
    _c(ws3, 1, 1, f"전체 판정표 ({s['n']:,}개사) — DB 필드 기반 자동 라우팅·게이트",
       bold=True, size=12)
    ws3.merge_cells(start_row=1, start_column=1, end_row=1, end_column=8)
    _hdr(ws3, 3, ["국문명", "영문명", "업종(CB)", "스테이지", "재단분류",
                  "→ 트랙", "밴드", "1차 필터 결과"],
         [20, 18, 20, 12, 18, 12, 10, 32])
    rr = 4
    order = {"통과": 0, "사람 검토": 1, "탈락": 2, "IndieBio": 3, "미상": 4, "부족": 5}

    def okey(row):
        o = row["outcome"]
        for k, v in order.items():
            if k in o:
                return v
        return 9
    for row in sorted(rows, key=lambda r: (okey(r), r["track"])):
        f = _fill_for(row["outcome"])
        _c(ws3, rr, 1, row["name_ko"], fill=f, size=9)
        _c(ws3, rr, 2, row["name_en"], fill=f, size=8)
        _c(ws3, rr, 3, row["sector"][:40], fill=f, size=8)
        _c(ws3, rr, 4, row["stage"], fill=f, size=8, align="center")
        _c(ws3, rr, 5, row["type"][:26], fill=f, size=8)
        _c(ws3, rr, 6, row["track"], fill=f, size=9, align="center")
        _c(ws3, rr, 7, row["band"], fill=f, size=8, align="center")
        _c(ws3, rr, 8, row["outcome"], fill=f, size=8)
        rr += 1
    ws3.freeze_panes = "A4"

    # ---- 시트4 방법론 ----
    ws4 = wb.create_sheet("방법론_한계")
    ws4.sheet_view.showGridLines = False
    ws4.column_dimensions["A"].width = 115
    notes = [
        ("방법론 및 한계 — 대규모 자동 평가", True, 12),
        ("데이터 출처", True, 11),
        ("디캠프 GBD 스타트업 데이터베이스 Ver.26.01 (전체 3,424개사). 대표 이메일·"
         "연락처 등 개인정보는 추출 단계에서 제외했다.", False, 10),
        ("자동화한 것 / 못 한 것", True, 11),
        ("자동화 O: 트랙 라우팅(업종·기술·1줄소개 키워드 → 500/HAX/IndieBio)과 하드 "
         "게이트(투자 스테이지 → 통과/사람검토/탈락)를 결정적 규칙으로 전 기업에 적용. "
         "개별 웹 크롤링·LLM 호출 없이 즉시 실행된다.", False, 10),
        ("자동화 X: 4축 레벨 점수(v2 Tier·v3 구간)는 1줄 소개만으로 Traction/Team/"
         "Market/Moat 를 신뢰성 있게 매길 수 없어 이 단계에서는 내지 않는다. 점수는 "
         "팩트시트를 수집한 102개사(engine_full_eval.xlsx)에서만 산출했다.", False, 10),
        ("라우팅 규칙", True, 11),
        ("① 신약·치료제·항체·백신 등 바이오 치료제 키워드 → IndieBio 라우팅(진단·"
         "의료기기·디지털헬스는 제외). ② 로봇·소재·배터리·센서·제조·에너지·우주 등 "
         "하드웨어 키워드 → HAX. ③ 그 외 → 500(섹터 무관). 업종·기술·소개가 모두 "
         "공란이면 '판정 불가(정보 부족)'.", False, 10),
        ("게이트 규칙", True, 11),
        ("시리즈A 이상 → HAX 는 탈락(프리시드~시드 대상), 500 은 사람 검토. "
         "Seed/Pre-A/Angel → 점수화 대상. 스테이지 미상 → 판정 보류(자료 요청).", False, 10),
        ("이 결과로 말할 수 있는 것 / 없는 것", True, 11),
        ("● 말할 수 있는 것: 엔진의 1차 필터가 3,424개 모집단에서 어떻게 분포하는지 — "
         "트랙 배분, 스테이지 게이트 통과·탈락 비율, 재단분류별 차이. 정형 데이터만으로 "
         "라우팅·게이트가 대규모 자동화된다.", False, 10),
        ("● 말할 수 없는 것: 개별 기업의 합불·점수. 키워드 라우팅은 근사이며 경계 "
         "사례(HW+SW 혼합, 진단 vs 치료제)는 오분류가 있을 수 있다. '정보 부족'·"
         "'스테이지 미상'이 많은 것은 DB 완결성의 문제다.", False, 10),
    ]
    for i, (t, b, sz) in enumerate(notes, 1):
        c = _c(ws4, i, 1, t, bold=b, size=sz, wrap=True)
        if b and sz >= 11:
            c.fill = SUB
        ws4.row_dimensions[i].height = 44 if len(t) > 70 else 16

    OUT.parent.mkdir(parents=True, exist_ok=True)
    wb.save(OUT)
    return OUT


if __name__ == "__main__":
    from screening import gbd_pipeline
    rows = gbd_pipeline.run()
    print(build(rows, gbd_pipeline.summarize(rows)))
