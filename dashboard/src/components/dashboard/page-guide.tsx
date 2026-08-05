// ABOUTME: PageGuide — 경영진용 접이식 페이지 설명 (디자인 시스템 패턴 5)
// ABOUTME: title + items 배열을 받아 접었다 펼치는 안내 카드
"use client";

import * as React from "react";
import { ChevronDown, Info } from "lucide-react";

import { cn } from "@/lib/utils";

interface PageGuideProps {
  title: string;
  items: string[];
}

export function PageGuide({ title, items }: PageGuideProps) {
  const [open, setOpen] = React.useState(false);
  return (
    <div className="rounded-xl border bg-card">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-2 px-4 py-3 text-left"
      >
        <Info className="h-4 w-4 shrink-0 text-muted-foreground" />
        <span className="flex-1 text-sm font-medium">{title}</span>
        <ChevronDown
          className={cn(
            "h-4 w-4 text-muted-foreground transition-transform",
            open && "rotate-180"
          )}
        />
      </button>
      {open && (
        <ul className="space-y-1.5 border-t px-4 py-3">
          {items.map((item) => (
            <li
              key={item}
              className="flex gap-2 text-sm text-muted-foreground"
            >
              <span className="select-none">·</span>
              {item}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
