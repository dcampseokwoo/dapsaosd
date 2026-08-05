// ABOUTME: 500 Global 모니터링 페이지 — 다음 배치 마감일 D-day·배치 일정·페이지 변경 감지
// ABOUTME: monitor_500global.py 실행 산출물(output/global500)을 읽어 표시, 없으면 빈 상태
import { CalendarClock, FileSearch, Globe, TriangleAlert } from "lucide-react";

import { PageGuide } from "@/components/dashboard/page-guide";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { loadGlobal500 } from "@/lib/data/monitors";
import { formatNumber } from "@/lib/operations/format";
import { daysUntilKst } from "@/lib/utils/kst-date";

export const dynamic = "force-dynamic";

function EmptyState() {
  return (
    <Card>
      <CardContent className="flex flex-col items-center gap-3 py-16 text-center">
        <FileSearch className="h-8 w-8 text-muted-foreground" />
        <div>
          <p className="text-sm font-medium">아직 수집된 리포트가 없습니다</p>
          <p className="mt-1 text-sm text-muted-foreground">
            <code className="font-mono text-xs">
              python monitor_500global.py
            </code>
            {" 를 실행하면 output/global500/ 리포트가 여기에 표시됩니다."}
          </p>
        </div>
      </CardContent>
    </Card>
  );
}

export default function Global500Page() {
  const report = loadGlobal500();
  const dDay =
    report?.dDay ?? (report?.deadline ? daysUntilKst(report.deadline) : null);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold md:text-2xl">500 Global 모니터링</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Flagship 배치 지원 마감일·요강·포트폴리오 변경 감지
        </p>
      </div>

      <PageGuide
        title="이 페이지에서 볼 수 있는 것"
        items={[
          "다음 배치 지원 마감일과 D-day — 이전 실행 대비 변경 시 경고 표시",
          "배치 일정(이름·마감·시작·장소) 구조화 추출 결과",
          "500.co 공식 페이지의 스냅샷 대비 변경 감지 내역",
          "마감일 추적 이력 (checkpoints/global500_deadline.jsonl)",
        ]}
      />

      {!report ? (
        <EmptyState />
      ) : (
        <>
          {report.deadlineChanged && (
            <div className="flex items-center gap-2 rounded-xl border border-destructive/50 bg-destructive/10 px-4 py-3 text-sm">
              <TriangleAlert className="h-4 w-4 shrink-0 text-destructive" />
              마감일이 이전 실행과 달라졌습니다 — 지원 일정을 다시 확인하세요.
            </div>
          )}

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {[
              {
                title: "다음 배치 마감일",
                value: report.deadline || "미확인",
                icon: CalendarClock,
                desc: report.deadlineNote || "마감일 근거 미수집",
              },
              {
                title: "D-day",
                value: dDay === null ? "-" : dDay >= 0 ? `D-${dDay}` : "마감 지남",
                icon: Globe,
                desc: "KST 기준 계산",
              },
              {
                title: "변경 감지 페이지",
                value: formatNumber(report.changedPages.length),
                icon: TriangleAlert,
                desc: "이전 스냅샷 대비 내용 변경",
              },
            ].map((kpi) => (
              <Card key={kpi.title}>
                <CardHeader className="flex flex-row items-center justify-between pb-2">
                  <CardTitle className="text-sm font-medium text-muted-foreground">
                    {kpi.title}
                  </CardTitle>
                  <kpi.icon className="h-4 w-4 text-muted-foreground" />
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">{kpi.value}</div>
                  <p className="mt-1 text-xs text-muted-foreground">{kpi.desc}</p>
                </CardContent>
              </Card>
            ))}
          </div>

          {report.batches.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">배치 일정</CardTitle>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>배치</TableHead>
                      <TableHead>마감</TableHead>
                      <TableHead>시작</TableHead>
                      <TableHead>장소</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {report.batches.map((b) => (
                      <TableRow key={`${b.name}-${b.deadline}`}>
                        <TableCell className="font-medium">{b.name}</TableCell>
                        <TableCell>{b.deadline || "미상"}</TableCell>
                        <TableCell>{b.start || "-"}</TableCell>
                        <TableCell>{b.location || "-"}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          )}

          {report.changedPages.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">페이지 변경 감지</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {report.changedPages.map((p) => (
                  <div key={p.url} className="space-y-1.5">
                    <div className="flex flex-wrap items-center gap-1.5">
                      <Badge variant="secondary" className="text-xs">
                        {p.label}
                      </Badge>
                      <a
                        href={p.url}
                        target="_blank"
                        rel="noreferrer"
                        className="truncate text-xs text-muted-foreground underline-offset-4 hover:underline"
                      >
                        {p.url}
                      </a>
                    </div>
                    {p.diff && (
                      <pre className="max-h-48 overflow-auto rounded-lg bg-muted p-3 font-mono text-xs">
                        {p.diff}
                      </pre>
                    )}
                  </div>
                ))}
              </CardContent>
            </Card>
          )}

          {report.history.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">마감일 추적 이력</CardTitle>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>확인일</TableHead>
                      <TableHead>마감일</TableHead>
                      <TableHead>비고</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {[...report.history].reverse().map((h, i) => (
                      <TableRow key={`${h.checkedAt}-${i}`}>
                        <TableCell>{h.checkedAt}</TableCell>
                        <TableCell className="font-medium">
                          {h.deadline || "미확인"}
                        </TableCell>
                        <TableCell className="text-xs text-muted-foreground">
                          {h.note || "-"}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
