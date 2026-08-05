// ABOUTME: 대시보드 레이아웃 — 데스크톱 사이드바 + 모바일 햄버거 헤더 + 콘텐츠 영역
// ABOUTME: h-dvh, 사이드바 hidden md:flex, 콘텐츠 패딩 p-3 md:p-6 (스캐폴드 표준)
import { Sidebar } from "@/components/dashboard/sidebar";
import { MobileHeader } from "@/components/dashboard/mobile-header";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex h-dvh">
      <div className="hidden md:flex">
        <Sidebar />
      </div>
      <div className="flex flex-1 flex-col overflow-hidden">
        <MobileHeader />
        <main className="flex-1 overflow-y-auto p-3 md:p-6">{children}</main>
      </div>
    </div>
  );
}
