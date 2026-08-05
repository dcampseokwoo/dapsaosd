// ABOUTME: 데스크톱 사이드바 — 네비게이션 + 다크모드 토글 (디자인 시스템 Sidebar 패턴)
// ABOUTME: 새 메뉴는 navGroups 배열에 항목 추가로 확장
"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTheme } from "next-themes";
import {
  BarChart3,
  Building2,
  Globe,
  Moon,
  Radar,
  Sun,
  type LucideIcon,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
}

export const navGroups: { title: string; items: NavItem[] }[] = [
  {
    title: "파이프라인",
    items: [{ href: "/stages", label: "투자 스테이지", icon: Building2 }],
  },
  {
    title: "모니터링",
    items: [
      { href: "/global500", label: "500 Global", icon: Globe },
      { href: "/ac-watch", label: "AC 업체 동향", icon: Radar },
    ],
  },
];

export function SidebarNav({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  return (
    <nav className="flex flex-1 flex-col gap-4 overflow-y-auto">
      {navGroups.map((group) => (
        <div key={group.title} className="space-y-1">
          <p className="px-3 text-xs font-medium text-muted-foreground">
            {group.title}
          </p>
          {group.items.map((item) => {
            const isActive = pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={onNavigate}
                className={cn(
                  "flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors",
                  isActive
                    ? "bg-sidebar-accent text-sidebar-accent-foreground font-medium"
                    : "text-sidebar-foreground/70 hover:bg-sidebar-accent/50"
                )}
              >
                <item.icon className="h-4 w-4" />
                {item.label}
              </Link>
            );
          })}
        </div>
      ))}
    </nav>
  );
}

export function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = React.useState(false);
  React.useEffect(() => setMounted(true), []);
  return (
    <Button
      variant="ghost"
      size="sm"
      onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")}
      className="w-full justify-start gap-3 text-sidebar-foreground/70 hover:bg-sidebar-accent/50"
    >
      {mounted && resolvedTheme === "dark" ? (
        <>
          <Sun className="h-4 w-4" /> 라이트 모드
        </>
      ) : (
        <>
          <Moon className="h-4 w-4" /> 다크 모드
        </>
      )}
    </Button>
  );
}

export function Sidebar() {
  return (
    <aside className="flex h-full w-56 flex-col border-r bg-sidebar p-3">
      <Link href="/stages" className="flex items-center gap-2 px-3 py-3">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10">
          <BarChart3 className="h-4 w-4 text-primary" />
        </div>
        <div className="min-w-0">
          <p className="truncate text-sm font-bold">dapsaosd</p>
          <p className="truncate text-xs text-muted-foreground">
            스타트업 조사 대시보드
          </p>
        </div>
      </Link>
      <div className="mt-2 flex flex-1 flex-col">
        <SidebarNav />
        <div className="mt-auto space-y-1 border-t pt-2">
          <ThemeToggle />
        </div>
      </div>
    </aside>
  );
}
