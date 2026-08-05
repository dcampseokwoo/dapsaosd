// ABOUTME: 공용 유틸 — cn() 클래스 병합 (clsx + tailwind-merge)
// ABOUTME: 모든 className 조합은 반드시 이 함수를 거친다 (디자인 시스템 규칙)
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
