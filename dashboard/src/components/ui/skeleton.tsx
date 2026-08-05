// ABOUTME: shadcn/ui Skeleton — 비동기 콘텐츠 로딩 상태 표시 (필수 패턴)
// ABOUTME: shadcn 관리 컴포넌트, 수동 편집 최소화
import { cn } from "@/lib/utils";

function Skeleton({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      className={cn("animate-pulse rounded-md bg-muted", className)}
      {...props}
    />
  );
}

export { Skeleton };
