from campus_growth.services.weather import WeatherService, business_tags


def test_manual_weather_builds_rain_tags():
    weather = WeatherService.manual("北京", "小雨", 20, 22, 17, 80)
    assert "雨天" in weather["tags"]


def test_high_temperature_and_cooling_tags():
    assert "高温" in business_tags({"weather_code": 0, "high": 33, "precipitation_probability": 0})
    assert "降温" in business_tags({"weather_code": 0, "high": 18, "previous_high": 25, "precipitation_probability": 0})
