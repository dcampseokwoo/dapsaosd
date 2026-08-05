// ABOUTME: 조사 결과 테이블 — 필터 바(결과 그룹·신뢰도) + 카드 내 테이블 + 상세 Dialog
// ABOUTME: 클라이언트 컴포넌트, StageRecord 배열을 받아 필터링/상세 보기 제공
"use client";

import * as React from "react";
import { ExternalLink } from "lucide-react";

import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { StageRecord } from "@/lib/data/stages";

interface StageTableProps {
  records: (StageRecord & { group: string })[];
}

const GROUP_OPTIONS = ["반영", "변경 없음", "확인 필요", "정보 없음"];
const CONFIDENCE_OPTIONS = ["high", "medium", "low"];

function groupBadgeVariant(
  group: string
): "default" | "secondary" | "outline" | "destructive" {
  if (group === "반영") return "default";
  if (group === "확인 필요") return "destructive";
  return "secondary";
}

export function StageTable({ records }: StageTableProps) {
  const [groups, setGroups] = React.useState<string[]>([]);
  const [confidences, setConfidences] = React.useState<string[]>([]);
  const [selected, setSelected] = React.useState<
    (StageRecord & { group: string }) | null
  >(null);

  const toggle = (list: string[], set: (v: string[]) => void, value: string) =>
    set(list.includes(value) ? list.filter((v) => v !== value) : [...list, value]);

  const filtered = records.filter(
    (r) =>
      (groups.length === 0 || groups.includes(r.group)) &&
      (confidences.length === 0 || confidences.includes(r.confidence))
  );

  const detailFields = selected
    ? [
        { label: "행 번호", value: String(selected.row) },
        { label: "기존 스테이지", value: selected.oldStage || "(공란)" },
        { label: "최신 스테이지", value: selected.newStage || "-" },
        { label: "반영 여부", value: selected.status },
        { label: "신뢰도", value: selected.confidence || "-" },
        { label: "근거", value: selected.evidence || "-" },
        { label: "비고", value: selected.note || "-" },
      ]
    : [];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">기업별 조사 결과</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs text-muted-foreground">결과:</span>
          {GROUP_OPTIONS.map((opt) => (
            <Button
              key={opt}
              variant={groups.includes(opt) ? "secondary" : "ghost"}
              size="sm"
              className="h-7 text-xs"
              onClick={() => toggle(groups, setGroups, opt)}
            >
              {opt}
            </Button>
          ))}
          <div className="mx-1 h-4 w-px bg-border" />
          <span className="text-xs text-muted-foreground">신뢰도:</span>
          {CONFIDENCE_OPTIONS.map((opt) => (
            <Button
              key={opt}
              variant={confidences.includes(opt) ? "secondary" : "ghost"}
              size="sm"
              className="h-7 text-xs"
              onClick={() => toggle(confidences, setConfidences, opt)}
            >
              {opt}
            </Button>
          ))}
          <span className="ml-auto text-xs text-muted-foreground">
            {filtered.length}건
          </span>
        </div>

        <div className="max-h-[480px] overflow-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>기업명</TableHead>
                <TableHead>기존 → 최신</TableHead>
                <TableHead>결과</TableHead>
                <TableHead>신뢰도</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filtered.map((r) => (
                <TableRow
                  key={`${r.row}-${r.name}`}
                  className="cursor-pointer"
                  onClick={() => setSelected(r)}
                >
                  <TableCell className="font-medium">{r.name}</TableCell>
                  <TableCell>
                    <span
                      className={cn(
                        "text-muted-foreground",
                        r.group === "반영" && "text-foreground font-medium"
                      )}
                    >
                      {r.oldStage || "(공란)"}
                      {" → "}
                      {r.newStage || "-"}
                    </span>
                  </TableCell>
                  <TableCell>
                    <Badge variant={groupBadgeVariant(r.group)} className="text-xs">
                      {r.group}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {r.confidence || "-"}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </CardContent>

      <Dialog open={!!selected} onOpenChange={(open) => !open && setSelected(null)}>
        <DialogContent className="max-h-[85vh] max-w-lg overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{selected?.name}</DialogTitle>
          </DialogHeader>
          <div className="space-y-2">
            {detailFields.map(({ label, value }) => (
              <div
                key={label}
                className="grid grid-cols-[140px_1fr] gap-2 border-b border-border py-1.5 last:border-0"
              >
                <div className="text-sm font-medium text-muted-foreground">
                  {label}
                </div>
                <div className="text-sm">{value}</div>
              </div>
            ))}
            {selected?.sourceUrl && (
              <a
                href={selected.sourceUrl}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1 text-sm text-primary underline-offset-4 hover:underline"
              >
                출처 보기 <ExternalLink className="h-3.5 w-3.5" />
              </a>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
