// ABOUTME: 모니터링 리포트 로더 — output/global500·ac_watch 최신 JSON + 마감일 이력 jsonl
// ABOUTME: 리포트가 아직 없으면 null 반환 → 페이지에서 빈 상태(empty state) 렌더
import "server-only";
import fs from "node:fs";
import path from "node:path";

import { repoRoot } from "./stages";

function latestFile(dir: string, prefix: string, ext: string): string | null {
  if (!fs.existsSync(dir)) return null;
  const files = fs
    .readdirSync(dir)
    .filter((f) => f.startsWith(prefix) && f.endsWith(ext))
    .sort();
  return files.length ? path.join(dir, files[files.length - 1]) : null;
}

function readJson(file: string | null): Record<string, unknown> | null {
  if (!file) return null;
  try {
    return JSON.parse(fs.readFileSync(file, "utf-8"));
  } catch {
    return null;
  }
}

export interface DeadlineEntry {
  checkedAt: string;
  deadline: string;
  note: string;
}

export interface Global500Report {
  generatedAt: string | null;
  deadline: string;
  deadlineNote: string;
  dDay: number | null;
  deadlineChanged: boolean;
  batches: { name: string; deadline: string; start: string; location: string }[];
  program: Record<string, unknown> | null;
  changedPages: { label: string; url: string; diff: string }[];
  history: DeadlineEntry[];
  raw: Record<string, unknown>;
}

/** 500 Global 최신 리포트 — output/global500/global500_status_*.json */
export function loadGlobal500(): Global500Report | null {
  const dir = path.join(repoRoot(), "output", "global500");
  const data = readJson(latestFile(dir, "global500_status", ".json"));

  const historyFile = path.join(
    repoRoot(),
    "checkpoints",
    "global500_deadline.jsonl"
  );
  const history: DeadlineEntry[] = [];
  if (fs.existsSync(historyFile)) {
    for (const line of fs.readFileSync(historyFile, "utf-8").split("\n")) {
      if (!line.trim()) continue;
      try {
        const rec = JSON.parse(line);
        history.push({
          checkedAt: String(rec.checked_at ?? ""),
          deadline: String(rec.deadline ?? ""),
          note: String(rec.note ?? ""),
        });
      } catch {
        // skip
      }
    }
  }

  if (!data && history.length === 0) return null;

  const deadlineInfo = (data?.deadline ?? {}) as Record<string, unknown>;
  const program = (data?.program ?? null) as Record<string, unknown> | null;
  const pages = Array.isArray(data?.changed_pages) ? data.changed_pages : [];
  const batches = Array.isArray(program?.batches) ? program.batches : [];

  return {
    generatedAt: String(data?.generated_at ?? data?.date ?? "") || null,
    deadline: String(
      deadlineInfo.deadline ?? history[history.length - 1]?.deadline ?? ""
    ),
    deadlineNote: String(
      deadlineInfo.note ?? history[history.length - 1]?.note ?? ""
    ),
    dDay:
      typeof deadlineInfo.d_day === "number"
        ? (deadlineInfo.d_day as number)
        : null,
    deadlineChanged: Boolean(deadlineInfo.changed),
    batches: (batches as Record<string, unknown>[]).map((b) => ({
      name: String(b.name ?? ""),
      deadline: String(b.deadline ?? ""),
      start: String(b.start ?? ""),
      location: String(b.location ?? ""),
    })),
    program,
    changedPages: (pages as Record<string, unknown>[]).map((p) => ({
      label: String(p.label ?? ""),
      url: String(p.url ?? ""),
      diff: String(p.diff ?? ""),
    })),
    history,
    raw: data ?? {},
  };
}

export interface AcWatchTarget {
  name: string;
  changed: boolean;
  fetchFailed: boolean;
  summary: string;
  news: { title: string; url: string }[];
  raw: Record<string, unknown>;
}

/** AC 업체 동향 최신 리포트 — output/ac_watch/ac_watch_status_*.json */
export function loadAcWatch(): AcWatchTarget[] | null {
  const dir = path.join(repoRoot(), "output", "ac_watch");
  const data = readJson(latestFile(dir, "ac_watch_status", ".json"));
  if (!data) return null;
  const records = Array.isArray(data) ? data : Object.values(data);
  return (records as Record<string, unknown>[]).map((r) => {
    const pages = Array.isArray(r.pages) ? (r.pages as Record<string, unknown>[]) : [];
    const news = Array.isArray(r.news) ? (r.news as Record<string, unknown>[]) : [];
    return {
      name: String(r.name ?? r.target ?? r.slug ?? ""),
      changed:
        Boolean(r.changed) || pages.some((p) => Boolean(p.changed)),
      fetchFailed: pages.length > 0 && pages.every((p) => Boolean(p.fetch_failed)),
      summary: String(r.summary ?? r.analysis ?? ""),
      news: news.map((n) => ({
        title: String(n.title ?? ""),
        url: String(n.url ?? n.link ?? ""),
      })),
      raw: r,
    };
  });
}
