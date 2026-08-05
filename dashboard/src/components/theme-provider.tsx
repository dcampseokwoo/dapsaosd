// ABOUTME: next-themes 래퍼 — .dark 클래스 기반 다크모드 프로바이더
// ABOUTME: 루트 레이아웃에서 attribute="class", defaultTheme="light"로 사용
"use client";

import * as React from "react";
import { ThemeProvider as NextThemesProvider } from "next-themes";

export function ThemeProvider({
  children,
  ...props
}: React.ComponentProps<typeof NextThemesProvider>) {
  return <NextThemesProvider {...props}>{children}</NextThemesProvider>;
}
