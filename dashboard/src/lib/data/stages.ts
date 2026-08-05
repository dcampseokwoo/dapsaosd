// ABOUTME: 투자 스테이지 파이프라인 데이터 로더 — 로그 CSV + checkpoints/results.jsonl 서버 사이드 파싱
// ABOUTME: 대시보드 페이지(RSC)에서만 import (fs 사용, 클라이언트 금지)
import "server-only";
import fs from "node:fs";
import path from "node:path";

/** 저장소 루트 — dashboard/에서 실행되므로 한 단계 위. DAPSAOSD_ROOT로 재정의 가능 */
export function repoRoot(): string {
  return process.env.DAPSAOSD_ROOT ?? path.resolve(process.cwd(), "..");
}

export interface StageRecord {
  row: number;
  name: string;
  oldStage: string;
  newStage: string;
  status: string; // 반영 여부 (반영/변경 없음/미반영...)
  confidence: string; // high | medium | low
  evidence: string;
  sourceUrl: string;
  note: string;
}

/** 따옴표 필드를 지원하는 최소 CSV 파서 */
function parseCsv(text: string): string[][] {
  const rows: string[][] = [];
  let field = "";
  let row: string[] = [];
  let inQuotes = false;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (inQuotes) {
      if (ch === '"') {
        if (text[i + 1] === '"') {
          field += '"';
          i++;
        } else {
          inQuotes = false;
        }
      } else {
        field += ch;
      }
    } else if (ch === '"') {
      inQuotes = true;
    } else if (ch === ",") {
      row.push(field);
      field = "";
    } else if (ch === "\n" || ch === "\r") {
      if (ch === "\r" && text[i + 1] === "\n") i++;
      row.push(field);
      field = "";
      if (row.some((c) => c !== "")) rows.push(row);
      row = [];
    } else {
      field += ch;
    }
  }
  row.push(field);
  if (row.some((c) => c !== "")) rows.push(row);
  return rows;
}

/** 1차 완료 로그 CSV (data/스테이지_업데이트_26.07.csv) 로드 */
export function loadStageLog(): StageRecord[] {
  const file = path.join(repoRoot(), "data", "스테이지_업데이트_26.07.csv");
  if (!fs.existsSync(file)) return [];
  const rows = parseCsv(fs.readFileSync(file, "utf-8").replace(/^﻿/, ""));
  if (rows.length < 2) return [];
  const header = rows[0];
  const col = (name: string) => header.indexOf(name);
  const idx = {
    row: col("행"),
    name: col("국문 회사명"),
    oldStage: col("기존 스테이지"),
    newStage: col("최신 스테이지"),
    status: col("반영 여부"),
    confidence: col("신뢰도"),
    evidence: col("근거"),
    sourceUrl: col("출처 URL"),
    note: col("비고"),
  };
  return rows.slice(1).map((r) => ({
    row: Number(r[idx.row] ?? 0) || 0,
    name: r[idx.name] ?? "",
    oldStage: (r[idx.oldStage] ?? "").trim(),
    newStage: (r[idx.newStage] ?? "").trim(),
    status: (r[idx.status] ?? "").trim(),
    confidence: (r[idx.confidence] ?? "").trim().toLowerCase(),
    evidence: r[idx.evidence] ?? "",
    sourceUrl: r[idx.sourceUrl] ?? "",
    note: r[idx.note] ?? "",
  }));
}

export interface CheckpointRecord {
  row: number;
  name: string;
  verdict: string;
  oldStage: string;
  newStage: string;
  confidence: string;
  status: string;
  evidence: string;
  sourceUrl: string;
}

/** 진행 중인 체크포인트 (checkpoints/results.jsonl) 로드 — 없으면 빈 배열 */
export function loadCheckpoints(): CheckpointRecord[] {
  const file = path.join(repoRoot(), "checkpoints", "results.jsonl");
  if (!fs.existsSync(file)) return [];
  const out: CheckpointRecord[] = [];
  for (const line of fs.readFileSync(file, "utf-8").split("\n")) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    try {
      const rec = JSON.parse(trimmed);
      out.push({
        row: Number(rec.row ?? 0) || 0,
        name: String(rec.name_kr ?? rec.name ?? ""),
        verdict: String(rec.verdict ?? ""),
        oldStage: String(rec.old_stage ?? ""),
        newStage: String(rec.new_stage ?? ""),
        confidence: String(rec.confidence ?? ""),
        status: String(rec.status ?? ""),
        evidence: String(rec.evidence ?? ""),
        sourceUrl: String(rec.source_url ?? ""),
      });
    } catch {
      // 손상 라인은 파이프라인이 자체 복구하므로 조용히 무시
    }
  }
  return out;
}

/** 상태 문자열을 4개 그룹으로 정규화: 반영 / 변경 없음 / 확인 필요 / 정보 없음 */
export function statusGroup(status: string): string {
  if (status.startsWith("반영")) return "반영";
  if (status === "변경 없음") return "변경 없음";
  if (status.includes("정보 없음")) return "정보 없음";
  return "확인 필요";
}
