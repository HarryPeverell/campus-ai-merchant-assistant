"""Open-Meteo 天气服务与经营标签。"""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, List

import requests


class WeatherError(RuntimeError):
    pass


WEATHER_NAMES = {
    0: "晴", 1: "晴间多云", 2: "多云", 3: "阴", 45: "雾", 48: "雾凇",
    51: "毛毛雨", 53: "毛毛雨", 55: "毛毛雨", 56: "冻毛毛雨", 57: "冻毛毛雨",
    61: "小雨", 63: "中雨", 65: "大雨", 66: "冻雨", 67: "冻雨",
    71: "小雪", 73: "中雪", 75: "大雪", 77: "米雪", 80: "阵雨", 81: "阵雨",
    82: "强阵雨", 85: "阵雪", 86: "强阵雪", 95: "雷暴", 96: "雷暴冰雹", 99: "强雷暴冰雹",
}
RAIN_CODES = set(range(51, 68)) | set(range(80, 83)) | {95, 96, 99}
SNOW_CODES = set(range(71, 78)) | {85, 86}


def business_tags(weather: Dict[str, Any]) -> List[str]:
    tags: List[str] = []
    code = int(weather.get("weather_code", -1) or -1)
    text = str(weather.get("weather", ""))
    precip = float(weather.get("precipitation_probability", 0) or 0)
    current_max = float(weather.get("high", weather.get("temperature", 0)) or 0)
    previous_max = weather.get("previous_high")
    wind_speed = float(weather.get("wind_speed", 0) or 0)
    if code in RAIN_CODES or precip >= 50 or "雨" in text:
        tags.append("雨天")
    if code in SNOW_CODES or "雪" in text:
        tags.append("雨雪天")
    if current_max >= 30 or any(word in text for word in ("高温", "炎热", "闷热")):
        tags.append("高温")
    if "降温" in text or "冷" in text or (previous_max is not None and float(previous_max) - current_max >= 5):
        tags.append("降温")
    if wind_speed >= 20 or any(word in text for word in ("大风", "风大")):
        tags.append("大风")
    if not tags and any(word in text for word in ("晴", "多云", "阴")):
        tags.append("常规天气")
    return tags


def business_impact(weather: Dict[str, Any]) -> str:
    """Return a business-facing impact sentence that follows the current weather."""
    tags = weather.get("tags") or business_tags(weather)
    text = str(weather.get("weather", ""))
    precip = float(weather.get("precipitation_probability", 0) or 0)
    high = float(weather.get("high", weather.get("temperature", 0)) or 0)
    if "雨雪天" in tags:
        return "雨雪天气会降低堂食停留意愿，建议主推热食热饮、外带包装和提前备餐，减少等待。"
    if "雨天" in tags:
        return "雨天建议推出关东煮、热豆浆和外带套餐，提前备好防烫袋，减少学生排队等待。"
    if "高温" in tags:
        return "高温天气适合主推柠檬茶、冷饮和清爽小吃，午后到傍晚增加饮品露出。"
    if "降温" in tags:
        return "降温时学生更愿意买热食热饮，建议主推关东煮、热豆浆和暖胃组合。"
    if "大风" in tags:
        return "大风天气路过停留少，建议用微信群和朋友圈提前提醒，主推可快速打包的套餐。"
    if precip >= 30:
        return "今天有降水可能，建议提前准备外带包装，并把热食套餐放在主推位。"
    if high <= 8 or "冷" in text:
        return "低温天气适合强调热乎、饱腹和快速取餐，晚自习前后可以加推热豆浆。"
    return "天气较稳定，重点抓午间下课和傍晚晚饭两个固定高峰，主推出餐快的组合。"


class WeatherService:
    GEO_URL = "https://geocoding-api.open-meteo.com/v1/search"
    FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

    def fetch(self, city: str, timeout: int = 12) -> Dict[str, Any]:
        city = city.strip()
        if not city:
            raise WeatherError("请先在店铺信息中填写所在城市。")
        try:
            geo = requests.get(
                self.GEO_URL,
                params={"name": city, "count": 1, "language": "zh", "format": "json"},
                timeout=timeout,
            )
            geo.raise_for_status()
            matches = geo.json().get("results") or []
            if not matches:
                raise WeatherError("未找到城市“{}”，请填写更完整的城市名。".format(city))
            location = matches[0]
            response = requests.get(
                self.FORECAST_URL,
                params={
                    "latitude": location["latitude"], "longitude": location["longitude"],
                    "current": "temperature_2m,weather_code,precipitation,wind_speed_10m",
                    "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
                    "past_days": 1, "forecast_days": 1, "timezone": "auto",
                },
                timeout=timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            raise WeatherError("天气服务不可用：{}".format(exc))

        daily = payload.get("daily", {})
        today = date.today().isoformat()
        times = daily.get("time", [])
        index = times.index(today) if today in times else max(0, len(times) - 1)
        current = payload.get("current", {})
        code = int(current.get("weather_code", daily.get("weather_code", [0])[index]))
        highs = daily.get("temperature_2m_max", [])
        previous_high = highs[index - 1] if index > 0 and len(highs) > index - 1 else None
        result = {
            "city": location.get("name", city), "date": today,
            "weather": WEATHER_NAMES.get(code, "未知"), "weather_code": code,
            "temperature": current.get("temperature_2m", 0),
            "high": highs[index] if len(highs) > index else current.get("temperature_2m", 0),
            "low": daily.get("temperature_2m_min", [current.get("temperature_2m", 0)])[index],
            "precipitation_probability": daily.get("precipitation_probability_max", [0])[index],
            "precipitation": current.get("precipitation", 0),
            "wind_speed": current.get("wind_speed_10m", 0), "previous_high": previous_high,
            "source": "Open-Meteo 实时数据",
        }
        result["tags"] = business_tags(result)
        result["business_impact"] = business_impact(result)
        return result

    @staticmethod
    def manual(city: str, weather: str, temperature: float, high: float, low: float,
               precipitation_probability: float, wind_speed: float = 0) -> Dict[str, Any]:
        text = weather.strip() or "手动天气"
        result = {
            "city": city.strip(), "date": date.today().isoformat(), "weather": text,
            "weather_code": 61 if any(word in text for word in ("雨", "雪")) else 0,
            "temperature": temperature, "high": high, "low": low,
            "precipitation_probability": precipitation_probability, "precipitation": 0,
            "wind_speed": wind_speed, "previous_high": None, "source": "手动输入",
        }
        result["tags"] = business_tags(result)
        result["business_impact"] = business_impact(result)
        return result
