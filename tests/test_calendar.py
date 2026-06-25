from campus_growth.services.calendar_analysis import analyze_local


def test_local_calendar_analysis_extracts_tags_times_and_exam():
    raw = "2026 年 6 月 20 日至 6 月 30 日为第 16 周期末考试周。\n7 月 5 日开始放暑假。\n晚自习时间 19:00，课程结束 18:00。\n毕业典礼安排另行通知。"
    result = analyze_local(raw, "示例大学")
    assert "考试周" in result["tags"]
    assert "毕业季" in result["tags"]
    assert "19:00" in result["class_time_slots"]
    assert result["holidays"]
