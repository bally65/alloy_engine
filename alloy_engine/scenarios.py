"""
三種工業廢熱情境設定

情境      目標 Tc   應用
低溫廢熱   150°C    製程冷卻水回收、空調系統、半導體製程
中溫廢熱   350°C    鍋爐排氣、玻璃退火、化工製程
高溫廢熱   500°C    鋼鐵廠、陶瓷窯爐、氣渦輪機尾氣
"""

SCENARIOS: dict[str, dict] = {
    "低溫廢熱_150C": dict(
        target_tc_celsius=150,
        tc_tolerance=20,
        min_strength_mpa=350,
        max_hc=50,
    ),
    "中溫廢熱_350C": dict(
        target_tc_celsius=350,
        tc_tolerance=30,
        min_strength_mpa=400,
        max_hc=80,
    ),
    "高溫廢熱_500C": dict(
        target_tc_celsius=500,
        tc_tolerance=40,
        min_strength_mpa=450,
        max_hc=100,
    ),
}
