# Design Tokens

> Source of truth: `src/app/globals.css` + `components.json`

## Fonts

### 본문 (sans)
- **Pretendard Variable**
- CDN: `https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable.min.css`
- CSS: `--font-sans: "Pretendard Variable", "Pretendard", -apple-system, BlinkMacSystemFont, system-ui, Roboto, sans-serif`

### 코드 (mono)
- **Geist Mono** (next/font)
- CSS: `--font-mono: var(--font-geist-mono)`

## Color Palette (OKLCH)

모든 색상은 OKLCH 무채색 (chroma = 0). 색상이 필요한 곳은 차트/배지에서만.

### Light Mode (:root)

```css
--background: oklch(1 0 0);          /* 흰색 */
--foreground: oklch(0.145 0 0);      /* 거의 검정 */
--card: oklch(1 0 0);
--card-foreground: oklch(0.145 0 0);
--popover: oklch(1 0 0);
--popover-foreground: oklch(0.145 0 0);
--primary: oklch(0.205 0 0);         /* 매우 어두운 회색 */
--primary-foreground: oklch(0.985 0 0);
--secondary: oklch(0.97 0 0);        /* 매우 밝은 회색 */
--secondary-foreground: oklch(0.205 0 0);
--muted: oklch(0.97 0 0);
--muted-foreground: oklch(0.556 0 0); /* 중간 회색 — 보조 텍스트 */
--accent: oklch(0.97 0 0);
--accent-foreground: oklch(0.205 0 0);
--destructive: oklch(0.577 0.245 27.325); /* 빨강 */
--border: oklch(0.922 0 0);
--input: oklch(0.922 0 0);
--ring: oklch(0.708 0 0);
```

### Dark Mode (.dark)

```css
--background: oklch(0.145 0 0);
--foreground: oklch(0.985 0 0);
--card: oklch(0.205 0 0);
--primary: oklch(0.922 0 0);          /* 라이트와 반전 */
--primary-foreground: oklch(0.205 0 0);
--secondary: oklch(0.269 0 0);
--muted: oklch(0.269 0 0);
--muted-foreground: oklch(0.708 0 0);
--destructive: oklch(0.704 0.191 22.216);
--border: oklch(1 0 0 / 10%);         /* 투명도 기반! */
--input: oklch(1 0 0 / 15%);          /* 투명도 기반! */
--ring: oklch(0.556 0 0);
```

### Chart Colors (블루 그라데이션)

라이트/다크 모드 동일:

```css
--chart-1: oklch(0.809 0.105 251.813);  /* 밝은 하늘색 */
--chart-2: oklch(0.623 0.214 259.815);  /* 중간 파랑 */
--chart-3: oklch(0.546 0.245 262.881);  /* 파랑 */
--chart-4: oklch(0.488 0.243 264.376);  /* 진한 파랑 */
--chart-5: oklch(0.424 0.199 265.638);  /* 가장 진한 파랑 */
```

### Sidebar Colors

```css
/* Light */
--sidebar: oklch(0.985 0 0);
--sidebar-primary: oklch(0.205 0 0);
--sidebar-accent: oklch(0.97 0 0);
--sidebar-border: oklch(0.922 0 0);

/* Dark */
--sidebar: oklch(0.205 0 0);
--sidebar-primary: oklch(0.488 0.243 264.376);  /* chart-4 파랑! */
--sidebar-accent: oklch(0.269 0 0);
--sidebar-border: oklch(1 0 0 / 10%);
```

## shadcn/ui Configuration

```json
{
  "style": "base-nova",
  "rsc": true,
  "tsx": true,
  "tailwind": {
    "config": "",
    "css": "src/app/globals.css",
    "baseColor": "neutral",
    "cssVariables": true
  },
  "iconLibrary": "lucide",
  "aliases": {
    "components": "@/components",
    "utils": "@/lib/utils",
    "ui": "@/components/ui",
    "lib": "@/lib",
    "hooks": "@/hooks"
  }
}
```

## Border Radius System

기본값 `--radius: 0.625rem` (10px)에서 비율로 파생:

| Token | 계산 | 결과 | 용도 |
|-------|------|------|------|
| `--radius-sm` | `* 0.6` | 6px | 작은 요소 |
| `--radius-md` | `* 0.8` | 8px | 입력 필드 |
| `--radius-lg` | `= radius` | 10px | 버튼 (rounded-lg) |
| `--radius-xl` | `* 1.4` | 14px | 카드 (rounded-xl) |
| `--radius-2xl` | `* 1.8` | 18px | 큰 카드 |
| `--radius-3xl` | `* 2.2` | 22px | 모달 |
| `--radius-4xl` | `* 2.6` | 26px | 배지 (rounded-4xl) |

## Typography Hierarchy

| 요소 | 클래스 | 용도 |
|------|--------|------|
| h1 | `text-xl md:text-2xl font-bold` | 페이지 제목 |
| h2 | `text-lg font-semibold` | 섹션 제목 |
| h3 / Card Title | `text-base font-semibold` | 카드/차트 제목 |
| 본문 | `text-sm` (md: `text-base`) | 일반 텍스트 |
| 보조 설명 | `text-sm text-muted-foreground` | 부가 설명 |
| KPI 값 | `text-2xl font-bold` | 숫자, 통계 |
| 캡션/라벨 | `text-xs text-muted-foreground` | 작은 레이블 |

## Spacing System

| 용도 | Tailwind | px |
|------|----------|----|
| 인라인 요소 간격 | `gap-1` / `gap-1.5` | 4 / 6 |
| 컴포넌트 내부 간격 | `gap-2` | 8 |
| 아이템 간 간격 | `gap-3` | 12 |
| 카드 간 간격 | `gap-4` | 16 |
| 섹션 간 간격 | `gap-6` / `space-y-6` | 24 |
| 카드 패딩 | `p-4` ~ `p-6` | 16~24 |
| 메인 콘텐츠 패딩 | `p-3 md:p-6` | 12~24 |
| 헤더/사이드바 높이 | `h-14` | 56 |
| 기본 버튼/입력 높이 | `h-8` | 32 |
| 작은 버튼 높이 | `h-7` | 28 |
| 큰 버튼 높이 | `h-9` | 36 |

## Dark Mode

- **Provider**: next-themes (`ThemeProvider`)
- **Selector**: `.dark` class on html
- **Default**: `light`, `enableSystem` 활성
- **전환 효과**: `disableTransitionOnChange` (깜빡임 방지)
- **차트**: CSS 변수로 자동 대응 — `var(--color-popover)` 등
- **다크모드 입력**: `dark:bg-input/30`, `dark:hover:bg-input/50`
- **다크모드 테두리**: 투명도 기반 `oklch(1 0 0 / 10%)`

## Technology Stack

- Tailwind CSS v4 (`@import "tailwindcss"`)
- Next.js 15+ (App Router, RSC)
- React 19
- Radix UI / Base UI (headless)
- CVA (class-variance-authority)
- `cn()` = clsx + tailwind-merge
