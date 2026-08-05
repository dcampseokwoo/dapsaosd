// ABOUTME: 투자 스테이지 현황 페이지 — 파이프라인 조사 결과 KPI·분포 차트·기업별 테이블
// ABOUTME: RSC에서 CSV/체크포인트를 읽어 클라이언트 컴포넌트에 전달
import { PageGuide } from "@/components/dashboard/page-guide";
import {
  LazyConfidenceChart,
  LazyStageDistributionChart,
  LazyUpdateResultChart,
} from "@/components/operations/charts/lazy-charts";
import { StageKpiCards } from "@/components/stages/stage-kpi-cards";
import { StageTable } from "@/components/stages/stage-table";
import {
  loadCheckpoints,
  loadStageLog,
  statusGroup,
} from "@/lib/data/stages";
import { STAGE_ORDER, stageGroup } from "@/lib/operations/format";

export const dynamic = "force-dynamic";

export default function StagesPage() {
  const log = loadStageLog();
  const checkpoints = loadCheckpoints();
  const records = log.map((r) => ({ ...r, group: statusGroup(r.status) }));

  const total = records.length;
  const applied = records.filter((r) => r.group === "반영").length;
  const unchanged = records.filter((r) => r.group === "변경 없음").length;
  const noInfo = records.filter((r) => r.group === "정보 없음").length;
  const needsReview = total - applied - unchanged - noInfo;
  const exited = records.filter((r) =>
    ["IPO", "M&A"].includes(stageGroup(r.newStage))
  ).length;

  const stageCounts = new Map<string, number>();
  for (const r of records) {
    const g = stageGroup(r.newStage);
    stageCounts.set(g, (stageCounts.get(g) ?? 0) + 1);
  }
  const stageData = [...stageCounts.entries()]
    .map(([stage, count]) => ({ stage, count }))
    .sort(
      (a, b) =>
        STAGE_ORDER.indexOf(a.stage as (typeof STAGE_ORDER)[number]) -
        STAGE_ORDER.indexOf(b.stage as (typeof STAGE_ORDER)[number])
    );

  const resultData = ["반영", "변경 없음", "확인 필요", "정보 없음"]
    .map((group) => ({
      group,
      count: records.filter((r) => r.group === group).length,
    }))
    .filter((d) => d.count > 0);

  const confidenceData = ["high", "medium", "low"]
    .map((confidence) => ({
      confidence,
      count: records.filter((r) => r.confidence === confidence).length,
    }))
    .filter((d) => d.count > 0);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold md:text-2xl">투자 스테이지 현황</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          스타트업 DB G열(투자 스테이지) 자동 조사 파이프라인의 1차 완료분
          {checkpoints.length > 0 &&
            ` · 진행 중 체크포인트 ${checkpoints.length}건`}
        </p>
      </div>

      <PageGuide
        title="이 페이지에서 볼 수 있는 것"
        items={[
          "1차 조사 완료 기업의 스테이지 반영 결과 — 반영·변경 없음·확인 필요 분류",
          "최신 투자 스테이지 분포 — Seed부터 IPO/M&A 종결까지",
          "검증 신뢰도(high/medium/low) 분포 — 보수적 반영 정책의 근거",
          "기업별 상세 — 행을 클릭하면 근거·출처·비고를 확인",
        ]}
      />

      <StageKpiCards
        total={total}
        applied={applied}
        unchanged={unchanged}
        needsReview={needsReview + noInfo}
        exited={exited}
      />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <LazyStageDistributionChart data={stageData} />
        <div className="grid grid-cols-1 gap-4">
          <LazyUpdateResultChart data={resultData} />
          <LazyConfidenceChart data={confidenceData} />
        </div>
      </div>

      <StageTable records={records} />
    </div>
  );
}
