from __future__ import annotations

import asyncio
import json
import math
import os
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).with_name(".env"))

router = APIRouter()
KST = timezone(timedelta(hours=9))
KMA_SERVICE_KEY = os.getenv("KMA_SERVICE_KEY", "").strip()
KMA_BASE_URL = "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst"


def _latlon_to_grid(lat: float, lon: float) -> tuple[int, int]:
    # 기상청 DFS 격자 변환 공식
    re = 6371.00877 / 5.0
    slat1 = math.radians(30.0)
    slat2 = math.radians(60.0)
    olon = math.radians(126.0)
    olat = math.radians(38.0)
    xo = 43.0
    yo = 136.0

    sn = math.log(math.cos(slat1) / math.cos(slat2)) / math.log(
        math.tan(math.pi * 0.25 + slat2 * 0.5)
        / math.tan(math.pi * 0.25 + slat1 * 0.5)
    )
    sf = (
        math.tan(math.pi * 0.25 + slat1 * 0.5) ** sn
        * math.cos(slat1)
        / sn
    )
    ro = re * sf / (math.tan(math.pi * 0.25 + olat * 0.5) ** sn)
    ra = re * sf / (math.tan(math.pi * 0.25 + math.radians(lat) * 0.5) ** sn)
    theta = math.radians(lon) - olon
    if theta > math.pi:
        theta -= 2.0 * math.pi
    if theta < -math.pi:
        theta += 2.0 * math.pi
    theta *= sn

    x = int(ra * math.sin(theta) + xo + 0.5)
    y = int(ro - ra * math.cos(theta) + yo + 0.5)
    return x, y


def _latest_base(now: datetime) -> tuple[str, str]:
    available = now - timedelta(minutes=15)
    base_hours = [2, 5, 8, 11, 14, 17, 20, 23]
    selected = None
    for hour in base_hours:
        candidate = available.replace(hour=hour, minute=0, second=0, microsecond=0)
        if candidate <= available:
            selected = candidate
    if selected is None:
        selected = (available - timedelta(days=1)).replace(
            hour=23, minute=0, second=0, microsecond=0
        )
    return selected.strftime("%Y%m%d"), selected.strftime("%H%M")


def _fetch_kma(nx: int, ny: int, now: datetime) -> list[dict[str, Any]]:
    if not KMA_SERVICE_KEY:
        raise RuntimeError("KMA_SERVICE_KEY가 설정되지 않았습니다.")

    base_date, base_time = _latest_base(now)
    query = urllib.parse.urlencode(
        {
            "serviceKey": KMA_SERVICE_KEY,
            "pageNo": "1",
            "numOfRows": "1000",
            "dataType": "JSON",
            "base_date": base_date,
            "base_time": base_time,
            "nx": str(nx),
            "ny": str(ny),
        }
    )
    request = urllib.request.Request(
        f"{KMA_BASE_URL}?{query}",
        headers={"User-Agent": "PlantDoctor/1.0"},
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        payload = json.loads(response.read().decode("utf-8"))

    header = payload.get("response", {}).get("header", {})
    if str(header.get("resultCode")) != "00":
        raise RuntimeError(
            f"기상청 API 오류: {header.get('resultCode')} {header.get('resultMsg')}"
        )

    items = (
        payload.get("response", {})
        .get("body", {})
        .get("items", {})
        .get("item", [])
    )
    return items if isinstance(items, list) else []


def _sky_text(sky: str | None, pty: str | None) -> str:
    pty_map = {
        "1": "비",
        "2": "비/눈",
        "3": "눈",
        "4": "소나기",
    }
    if pty and pty != "0":
        return pty_map.get(pty, "강수")
    return {"1": "맑음", "3": "구름많음", "4": "흐림"}.get(sky or "", "날씨")


def _parse_forecast(items: list[dict[str, Any]], now: datetime) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], dict[str, str]] = {}
    for row in items:
        date = str(row.get("fcstDate", ""))
        time = str(row.get("fcstTime", ""))
        category = str(row.get("category", ""))
        value = str(row.get("fcstValue", ""))
        if date and time and category:
            grouped.setdefault((date, time), {})[category] = value

    result: list[dict[str, Any]] = []
    for (date, time), values in sorted(grouped.items()):
        try:
            dt = datetime.strptime(date + time, "%Y%m%d%H%M").replace(tzinfo=KST)
        except ValueError:
            continue
        if dt < now - timedelta(hours=1):
            continue
        result.append(
            {
                "date_time": dt.isoformat(),
                "temperature": _to_float(values.get("TMP")),
                "humidity": _to_int(values.get("REH")),
                "rain_probability": _to_int(values.get("POP")),
                "sky_text": _sky_text(values.get("SKY"), values.get("PTY")),
            }
        )
    return result


def _to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _daily_advice(
    now: datetime,
    temperature: float | None,
    humidity: int | None,
    rain_probability: int | None,
    sky_text: str,
) -> tuple[str, str, str]:
    # 오전 9시를 경계로 추천 날짜를 고정합니다.
    advice_date = now.date() if now.hour >= 9 else (now - timedelta(days=1)).date()

    if (rain_probability or 0) >= 60 or "비" in sky_text:
        return (
            "오늘은 물주기를 잠시 미뤄주세요.",
            "비 예보가 있어 흙이 마른 정도를 먼저 확인하는 편이 좋습니다.",
            advice_date.isoformat(),
        )
    if (humidity or 0) >= 80:
        return (
            "잎이 오래 젖지 않도록 통풍을 확인하세요.",
            "습도가 높으면 곰팡이성 병해가 번지기 쉬워요.",
            advice_date.isoformat(),
        )
    if (temperature or 0) >= 30:
        return (
            "한낮을 피해 오전에 물을 주세요.",
            "기온이 높을 때는 잎보다 흙에 천천히 물을 주는 것이 좋습니다.",
            advice_date.isoformat(),
        )
    if temperature is not None and temperature <= 8:
        return (
            "찬바람과 저온 피해를 확인하세요.",
            "민감한 식물은 밤사이 보온이 필요한지 살펴보세요.",
            advice_date.isoformat(),
        )

    messages = [
        ("흙 표면이 말랐는지 먼저 확인하세요.", "필요할 때만 물을 주면 과습을 줄일 수 있어요."),
        ("오늘은 잎 뒷면도 한 번 살펴보세요.", "작은 반점과 해충 흔적은 일찍 발견할수록 관리가 쉬워요."),
        ("식물 사이 통풍 공간을 확인하세요.", "잎이 겹치면 습기가 오래 머물 수 있어요."),
        ("시든 잎과 떨어진 잎을 정리하세요.", "깨끗한 주변 환경은 병해 확산을 줄이는 데 도움이 됩니다."),
        ("물을 줄 때 잎보다 흙을 적셔주세요.", "잎이 오래 젖어 있으면 일부 병해가 번지기 쉬워요."),
        ("새잎의 색과 모양을 기록해보세요.", "작은 변화도 사진으로 남기면 상태 비교에 도움이 됩니다."),
        ("도구를 사용한 뒤 깨끗이 닦아주세요.", "가위와 장갑을 통한 병원균 이동을 줄일 수 있어요."),
    ]
    index = advice_date.toordinal() % len(messages)
    advice, detail = messages[index]
    return advice, detail, advice_date.isoformat()


@router.get("/v1/weather")
async def weather(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
) -> dict[str, Any]:
    now = datetime.now(KST)
    nx, ny = _latlon_to_grid(lat, lon)

    try:
        items = await asyncio.to_thread(_fetch_kma, nx, ny, now)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    forecast = _parse_forecast(items, now)
    if not forecast:
        raise HTTPException(status_code=502, detail="기상청 단기예보 데이터가 비어 있습니다.")

    current = min(
        forecast,
        key=lambda row: abs(datetime.fromisoformat(row["date_time"]) - now),
    )
    advice, advice_detail, advice_date = _daily_advice(
        now,
        current.get("temperature"),
        current.get("humidity"),
        current.get("rain_probability"),
        str(current.get("sky_text", "")),
    )

    # 홈은 현재값, 더보기는 3시간 간격으로 최대 24개를 표시합니다.
    compact_forecast = forecast[::3][:24]

    return {
        "latitude": lat,
        "longitude": lon,
        "grid": {"nx": nx, "ny": ny},
        "temperature": current.get("temperature"),
        "humidity": current.get("humidity"),
        "rain_probability": current.get("rain_probability"),
        "sky_text": current.get("sky_text"),
        "advice": advice,
        "advice_detail": advice_detail,
        "advice_date": advice_date,
        "updated_at": now.isoformat(),
        "forecast": compact_forecast,
    }
