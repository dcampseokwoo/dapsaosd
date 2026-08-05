// ABOUTME: AC 업체 동향 페이지 — 서비스/가격 변경·인력 영입 감지 결과
// ABOUTME: monitor_ac.py 실행 산출물(output/ac_watch)을 읽어 표시, 없으면 빈 상태
import { FileSearch, Radar, TriangleAlert } from "lucide-react";

import { PageGuide } from "@/components/dashboard/page-guide";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { loadAcWatch } from "@/lib/data/monitors";

export const dynamic = "force-dynamic";

function EmptyState() {
  return (
    <Card>
      <CardContent className="flex flex-col items-center gap-3 py-16 text-center">
        <FileSearch className="h-8 w-8 text-muted-foreground" />
        <div>
          <p className="text-sm font-medium">아직 수집된 리포트가 없습니다</p>
          <p className="mt-1 text-sm text-muted-foreground">
            <code className="font-mono text-xs">python monitor_ac.py</code>
            {" 를 실행하면 output/ac_watch/ 리포트가 여기에 표시됩니다."}
          </p>
        </div>
      </CardContent>
    </Card>
  );
}

export default function AcWatchPage() {
  const targets = loadAcWatch();
  const changedCount = targets?.filter((t) => t.changed).length ?? 0;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold md:text-2xl">AC 업체 동향</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          액셀러레이터/컨설팅 업체의 서비스·가격 변경과 인력 영입 시그널 감시
          {targets && changedCount > 0 && ` · 변경 감지 ${changedCount}건`}
        </p>
      </div>

      <PageGuide
        title="이 페이지에서 볼 수 있는 것"
        items={[
          "감시 대상 업체별 웹사이트 스냅샷 diff 기반 실질 변경 여부",
          "서비스 신설·가격 변경 등 비교 시트 갱신이 필요한 알림",
          "뉴스 검색으로 수집한 멘토/인력 영입 소식",
        ]}
      />

      {!targets ? (
        <EmptyState />
      ) : (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {targets.map((t) => (
            <Card key={t.name}>
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="flex items-center gap-2 text-base">
                  <Radar className="h-4 w-4 text-muted-foreground" />
                  {t.name}
                </CardTitle>
                <div className="flex gap-1.5">
                  {t.changed && (
                    <Badge variant="destructive" className="gap-1 text-xs">
                      <TriangleAlert className="h-3 w-3" /> 변경 감지
                    </Badge>
                  )}
                  {t.fetchFailed && (
                    <Badge variant="outline" className="text-xs">
                      수집 실패
                    </Badge>
                  )}
                  {!t.changed && !t.fetchFailed && (
                    <Badge variant="secondary" className="text-xs">
                      변동 없음
                    </Badge>
                  )}
                </div>
              </CardHeader>
              <CardContent className="space-y-3">
                {t.summary ? (
                  <p className="whitespace-pre-wrap text-sm text-muted-foreground">
                    {t.summary}
                  </p>
                ) : (
                  <p className="text-sm text-muted-foreground">
                    분석 요약이 없습니다.
                  </p>
                )}
                {t.news.length > 0 && (
                  <div className="space-y-1 border-t pt-3">
                    <p className="text-xs font-medium text-muted-foreground">
                      관련 뉴스
                    </p>
                    {t.news.slice(0, 5).map((n) => (
                      <a
                        key={n.url || n.title}
                        href={n.url}
                        target="_blank"
                        rel="noreferrer"
                        className="block truncate text-sm underline-offset-4 hover:underline"
                      >
                        {n.title}
                      </a>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
