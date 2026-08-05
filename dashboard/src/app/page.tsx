// ABOUTME: 루트 경로 — 기본 페이지인 투자 스테이지 현황으로 리다이렉트
// ABOUTME: 별도 랜딩 없이 대시보드 진입
import { redirect } from "next/navigation";

export default function Home() {
  redirect("/stages");
}
