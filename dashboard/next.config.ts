// ABOUTME: Next.js 설정 — 저장소 루트의 data/checkpoints/output 파일을 서버에서 읽는 대시보드
// ABOUTME: standalone 배포와 외부 디렉터리 접근을 위한 최소 설정
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  outputFileTracingIncludes: {
    "/**": ["../data/**", "../checkpoints/**", "../output/**"],
  },
};

export default nextConfig;
