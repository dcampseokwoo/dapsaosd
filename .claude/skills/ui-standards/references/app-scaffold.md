# App Scaffold

프로젝트를 새로 구성할 때 필요한 인증, 레이아웃, 다크모드 패턴.
이 가이드대로 구현하면 기존 batchIntelli와 동일한 기반 구조가 만들어집니다.

## 1. Root Layout (ThemeProvider + Pretendard)

**참조**: `src/app/layout.tsx`

```tsx
import type { Metadata, Viewport } from "next";
import { Geist_Mono } from "next/font/google";
import { ThemeProvider } from "@/components/theme-provider";
import "./globals.css";

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 5,
};

export const metadata: Metadata = {
  title: "프로젝트 이름",
  description: "프로젝트 설명",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko" suppressHydrationWarning>
      <head>
        <link rel="icon" href="/favicon.svg" type="image/svg+xml" />
        <link
          rel="preload"
          as="style"
          crossOrigin="anonymous"
          href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css"
        />
        <link
          rel="stylesheet"
          crossOrigin="anonymous"
          href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css"
        />
      </head>
      <body className={`${geistMono.variable} font-sans antialiased`}>
        <ThemeProvider
          attribute="class"
          defaultTheme="light"
          enableSystem
          disableTransitionOnChange
        >
          {children}
        </ThemeProvider>
      </body>
    </html>
  );
}
```

## 2. ThemeProvider (다크모드)

**참조**: `src/components/theme-provider.tsx`

```tsx
"use client";

import * as React from "react";
import { ThemeProvider as NextThemesProvider } from "next-themes";

export function ThemeProvider({
  children,
  ...props
}: React.ComponentProps<typeof NextThemesProvider>) {
  return <NextThemesProvider {...props}>{children}</NextThemesProvider>;
}
```

## 3. Dashboard Layout (사이드바 + 헤더 + 콘텐츠)

**참조**: `src/app/(dashboard)/layout.tsx`

```tsx
import { Sidebar } from "@/components/dashboard/sidebar";
import { Header } from "@/components/dashboard/header";
import { MobileHeader } from "@/components/dashboard/mobile-header";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-dvh">
      {/* 데스크톱: 사이드바 */}
      <div className="hidden md:flex">
        <Sidebar />
      </div>
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* 모바일: 햄버거 헤더 */}
        <MobileHeader />
        {/* 데스크톱: 검색 헤더 */}
        <Header />
        <main className="flex-1 overflow-y-auto p-3 md:p-6">{children}</main>
      </div>
    </div>
  );
}
```

핵심:
- `h-dvh` (dynamic viewport height) — 모바일 주소창 대응
- 사이드바: `hidden md:flex` — 모바일에서 숨김
- 콘텐츠 패딩: `p-3 md:p-6` — 반응형

## 4. Sidebar (네비게이션 + 다크모드 + 사용자)

**참조**: `src/components/dashboard/sidebar.tsx`

사이드바 하단 구성:

```tsx
{/* 하단: 관리 + 다크모드 + 계정 */}
<div className="mt-auto border-t pt-2 space-y-1">
  {/* 설정/매뉴얼 링크 */}
  {adminItems.map((item) => (
    <Link key={item.href} href={item.href} className={cn(
      "flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors",
      isActive ? "bg-sidebar-accent text-sidebar-accent-foreground font-medium"
               : "text-sidebar-foreground/70 hover:bg-sidebar-accent/50"
    )}>
      <item.icon className="h-4 w-4" />
      {item.label}
    </Link>
  ))}

  {/* 다크모드 토글 */}
  <Button
    variant="ghost"
    size="sm"
    onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")}
    className="w-full justify-start gap-3 text-sidebar-foreground/70 hover:bg-sidebar-accent/50"
  >
    {mounted && resolvedTheme === "dark"
      ? <><Sun className="h-4 w-4" /> 라이트 모드</>
      : <><Moon className="h-4 w-4" /> 다크 모드</>
    }
  </Button>

  {/* 사용자 이메일 + 로그아웃 */}
  {user && (
    <div className="flex items-center gap-2 px-3 py-2">
      <p className="flex-1 min-w-0 truncate text-xs text-muted-foreground">
        {user.email}
      </p>
      <Button variant="ghost" size="icon" onClick={handleLogout}
        className="h-7 w-7 shrink-0" title="로그아웃">
        <LogOut className="h-3.5 w-3.5" />
      </Button>
    </div>
  )}
</div>
```

핵심:
- `mt-auto` — 하단 고정
- `useTheme()` + `mounted` 체크 — SSR hydration 불일치 방지
- `truncate` — 긴 이메일 말줄임

## 5. SSO Login Page (Google + Magic Link)

**참조**: `src/app/login/page.tsx`

```tsx
<div className="flex min-h-screen items-center justify-center bg-background">
  <div className="mx-auto w-full max-w-sm space-y-8 text-center">
    {/* 로고 */}
    <div className="flex flex-col items-center gap-3">
      <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-primary/10">
        <BarChart3 className="h-8 w-8 text-primary" />
      </div>
      <div>
        <h1 className="text-2xl font-bold text-foreground">앱 이름</h1>
        <p className="text-sm text-muted-foreground">한 줄 설명</p>
      </div>
    </div>

    {/* Google SSO 버튼 */}
    <Button onClick={handleGoogleLogin} size="lg" className="w-full gap-3">
      <GoogleIcon />
      @dcamp.kr 계정으로 로그인
    </Button>

    {/* 구분선 */}
    <div className="flex items-center gap-3">
      <div className="h-px flex-1 bg-border" />
      <span className="text-xs text-muted-foreground">또는</span>
      <div className="h-px flex-1 bg-border" />
    </div>

    {/* 매직 링크 폼 */}
    <form onSubmit={handleMagicLink} className="space-y-3">
      <Input type="email" placeholder="외부 이메일 주소" />
      {error && <p className="text-xs text-destructive">{error}</p>}
      <Button type="submit" variant="outline" size="lg" className="w-full gap-2">
        <Mail className="h-4 w-4" />
        이메일로 로그인 링크 받기
      </Button>
    </form>
  </div>
</div>
```

핵심:
- `min-h-screen items-center justify-center` — 화면 중앙 배치
- `max-w-sm` — 좁은 폼 폭
- `bg-primary/10` — 로고 배경 (투명도 10%)
- 에러: `text-xs text-destructive`

## 6. Supabase Client (Browser / Server)

### 브라우저용 (`src/lib/supabase/client.ts`)

```tsx
import { createBrowserClient } from "@supabase/ssr";

export function createClient() {
  return createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
  );
}
```

### 서버용 (`src/lib/supabase/server.ts`)

```tsx
import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";

export async function createClient() {
  const cookieStore = await cookies();
  return createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() { return cookieStore.getAll(); },
        setAll(cookiesToSet) {
          try {
            cookiesToSet.forEach(({ name, value, options }) =>
              cookieStore.set(name, value, options));
          } catch { /* Server Component에서 호출 시 무시 */ }
        },
      },
    }
  );
}
```

## 7. Auth Middleware

**참조**: `src/middleware.ts`

```tsx
import { updateSession } from "@/lib/supabase/middleware";
import type { NextRequest } from "next/server";

export async function middleware(request: NextRequest) {
  return await updateSession(request);
}

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)",
  ],
};
```

## 8. OAuth Callback

**참조**: `src/app/auth/callback/route.ts`

```tsx
import { NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const code = searchParams.get("code");
  const next = searchParams.get("next") ?? "/operations";

  if (code) {
    const supabase = await createClient();
    const { error } = await supabase.auth.exchangeCodeForSession(code);
    if (!error) {
      return NextResponse.redirect(new URL(next, request.url));
    }
  }

  return NextResponse.redirect(new URL("/login?error=auth_failed", request.url));
}
```

## 필수 환경 변수

```env
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJ...
SUPABASE_SERVICE_ROLE_KEY=eyJ...  # 서버 전용, admin 작업에만
```

## 필수 패키지

```bash
npm install @supabase/ssr @supabase/supabase-js next-themes
```
