// ABOUTME: 모바일 헤더 — 햄버거 버튼으로 Sheet 사이드바를 여는 반응형 네비게이션
// ABOUTME: 데스크톱(md 이상)에서는 숨김
"use client";

import * as React from "react";
import { BarChart3, Menu } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { SidebarNav, ThemeToggle } from "@/components/dashboard/sidebar";

export function MobileHeader() {
  const [open, setOpen] = React.useState(false);
  return (
    <header className="flex h-14 items-center gap-2 border-b px-3 md:hidden">
      <Sheet open={open} onOpenChange={setOpen}>
        <SheetTrigger asChild>
          <Button variant="ghost" size="icon" aria-label="메뉴 열기">
            <Menu className="h-5 w-5" />
          </Button>
        </SheetTrigger>
        <SheetContent side="left" className="flex w-64 flex-col bg-sidebar p-3">
          <SheetTitle className="flex items-center gap-2 px-3 py-3 text-sm font-bold">
            <BarChart3 className="h-4 w-4" /> dapsaosd
          </SheetTitle>
          <div className="flex flex-1 flex-col">
            <SidebarNav onNavigate={() => setOpen(false)} />
            <div className="mt-auto border-t pt-2">
              <ThemeToggle />
            </div>
          </div>
        </SheetContent>
      </Sheet>
      <p className="text-sm font-bold">dapsaosd 대시보드</p>
    </header>
  );
}
