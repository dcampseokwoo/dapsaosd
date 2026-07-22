"""Gemini API 래퍼 — google-genai SDK + Google Search grounding.

- 요청 간 딜레이(REQUEST_DELAY_SEC)로 무료/저가 티어 RPM 준수
- 429/5xx 시 지수 백오프(2/4/8/16초) 후 재시도
- 호출 카운터 + max_calls 도달 시 BudgetExceeded (호출 전에 검사 → 유실 없음)
"""
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field

from google import genai
from google.genai import types
from google.genai import errors as genai_errors

import config

log = logging.getLogger(__name__)


class BudgetExceeded(Exception):
    """--max-calls 한도 도달. 파이프라인은 체크포인트 저장 후 정상 종료한다."""


class AllModelsExhausted(Exception):
    """후보 모델 전부 일일 무료 한도 소진 — 내일 재실행하면 이어서 진행."""


_DAILY_QUOTA_MARKERS = ("PerDay", "per_day", "daily")


def _is_daily_quota(err_str: str) -> bool:
    return any(m in err_str for m in _DAILY_QUOTA_MARKERS)


def _retry_seconds(err_str: str) -> float | None:
    m = re.search(r"[Rr]etry in ([\d.]+)\s*s", err_str) \
        or re.search(r"retryDelay[\"':\s]+([\d.]+)s", err_str)
    return float(m.group(1)) if m else None


@dataclass
class GroundedAnswer:
    text: str
    sources: list[dict] = field(default_factory=list)  # [{"url":..., "title":...}]


class GeminiClient:
    def __init__(self, api_key: str | None = None, max_calls: int | None = None):
        import os
        if api_key is not None:
            api_keys = [api_key]
        else:
            api_keys = [k.strip() for k in os.environ.get("GEMINI_API_KEYS", "").split(",")
                        if k.strip()]
        if not api_keys:
            import os
            for env in config.GEMINI_API_KEY_ENVS:
                api_key = os.environ.get(env)
                if api_key:
                    break
            if api_key:
                api_keys = [api_key]
        if not api_keys:
            raise RuntimeError(
                "Gemini API 키가 없습니다. GEMINI_API_KEYS 또는 GEMINI_API_KEY 환경변수를 설정하세요."
            )
        self._api_keys = api_keys
        self._key_index = 0
        self._clients = [genai.Client(api_key=key) for key in api_keys]
        self._client = self._clients[0]
        self.max_calls = max_calls
        self.call_count = 0
        self._last_call_ts = 0.0
        # 키별 모델 차단 사유: {model: "daily" | "404"}
        self._blocked_by_key: list[dict[str, str]] = [{} for _ in api_keys]

    # ------------------------------------------------------------------
    def grounded(self, prompt: str, model: str | None = None,
                 allowed_models: list[str] | None = None) -> GroundedAnswer:
        """Google Search grounding 1회 호출 (유료 티어 필요). 텍스트 + 근거 URL 반환."""
        cfg = types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())],
            temperature=0.2,
        )
        return self._call(prompt, model, cfg, allowed_models)

    def plain(self, prompt: str, model: str | None = None,
              allowed_models: list[str] | None = None) -> GroundedAnswer:
        """검색 도구 없는 일반 호출 (무료 티어 가능) — RSS 검색 모드에서 사용."""
        cfg = types.GenerateContentConfig(temperature=0.2)
        return self._call(prompt, model, cfg, allowed_models)

    def _candidates(self, preferred: str,
                    allowed_models: list[str] | None = None) -> list[str]:
        candidates = allowed_models or [preferred] + config.MODEL_CANDIDATES
        return list(dict.fromkeys(candidates))

    def _pick_slot(self, preferred: str,
                   allowed_models: list[str] | None = None) -> tuple[int, str]:
        """모델 우선순위를 지키며 사용 가능한 (키 인덱스, 모델)을 찾는다."""
        candidates = self._candidates(preferred, allowed_models)
        key_order = list(range(self._key_index, len(self._api_keys))) + \
            list(range(0, self._key_index))
        for model in candidates:
            for key_index in key_order:
                if model not in self._blocked_by_key[key_index]:
                    return key_index, model
        raise AllModelsExhausted(
            "모든 API 키에서 후보 모델 소진 또는 사용 불가: "
            + ", ".join(candidates))

    def _switch_key(self, key_index: int):
        if key_index != self._key_index:
            log.warning("사용 가능한 모델을 찾아 API 키 %d/%d로 전환",
                        key_index + 1, len(self._api_keys))
        self._key_index = key_index
        self._client = self._clients[key_index]

    def has_available_models(self, allowed_models: list[str] | None = None,
                             preferred: str | None = None) -> bool:
        """API 호출이나 키 전환 없이 후보 모델 사용 가능 여부를 확인한다."""
        try:
            self._pick_slot(preferred or config.MODEL_VERIFY, allowed_models)
            return True
        except AllModelsExhausted:
            return False

    def _call(self, prompt: str, model: str | None,
              cfg: types.GenerateContentConfig,
              allowed_models: list[str] | None = None) -> GroundedAnswer:
        if self.max_calls is not None and self.call_count >= self.max_calls:
            raise BudgetExceeded(f"API 호출 한도 {self.max_calls}회 도달")

        preferred = model or config.MODEL_SCREEN
        last_err: Exception | None = None
        backoffs = list(config.BACKOFF_SECONDS)

        # 백오프 재시도 + 모델 전환을 합쳐 최대 10회 시도
        attempts = max(10, len(self._api_keys) * max(1, len(allowed_models or config.MODEL_CANDIDATES)))
        for _ in range(attempts):
            key_index, m = self._pick_slot(preferred, allowed_models)
            self._switch_key(key_index)
            self._throttle()
            try:
                self.call_count += 1
                resp = self._client.models.generate_content(
                    model=m, contents=prompt, config=cfg,
                )
                return GroundedAnswer(
                    text=resp.text or "", sources=self._extract_sources(resp)
                )
            except genai_errors.APIError as e:
                last_err = e
                err = str(e)
                code = getattr(e, "code", None)
                if code == 429 and _is_daily_quota(err):
                    # 일일 한도 소진 — 재시도 무의미, 즉시 다음 모델로 전환
                    self._blocked_by_key[key_index][m] = "daily"
                    log.warning("API 키 %d의 모델 %s 일일 무료 한도 소진",
                                key_index + 1, m)
                    continue
                if code == 404:
                    # 이 키로 사용 불가한 모델 — 목록에서 제외하고 다음 모델로
                    self._blocked_by_key[key_index][m] = "404"
                    log.warning("API 키 %d의 모델 %s 사용 불가(404)", key_index + 1, m)
                    continue
                if code in config.RETRYABLE_CODES:
                    wait = _retry_seconds(err) or (backoffs.pop(0) if backoffs else None)
                    if wait is None:
                        break
                    log.warning("재시도 — %.0fs 대기 (HTTP %s)", wait, code)
                    time.sleep(min(wait, 90))
                    continue
                raise
        raise RuntimeError(f"재시도 소진: {last_err}")

    # ------------------------------------------------------------------
    def _throttle(self):
        wait = config.REQUEST_DELAY_SEC - (time.time() - self._last_call_ts)
        if wait > 0:
            time.sleep(wait)
        self._last_call_ts = time.time()

    @staticmethod
    def _extract_sources(resp) -> list[dict]:
        sources: list[dict] = []
        try:
            for cand in resp.candidates or []:
                gm = getattr(cand, "grounding_metadata", None)
                if not gm:
                    continue
                for chunk in gm.grounding_chunks or []:
                    web = getattr(chunk, "web", None)
                    if web and web.uri:
                        sources.append({"url": web.uri, "title": web.title or ""})
        except Exception:  # grounding 메타데이터 구조 변화에 대한 방어
            log.debug("grounding metadata 파싱 실패", exc_info=True)
        return sources
