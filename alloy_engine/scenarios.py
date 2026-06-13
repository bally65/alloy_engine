"""
三種工業廢熱情境設定

情境       目標 Tc   應用
近室溫廢熱   25°C     太陽能溫水、體溫/環境溫差、資料中心低溫排熱（稀土 MCE 區）
低溫廢熱   150°C    製程冷卻水回收、空調系統、半導體製程
中溫廢熱   350°C    鍋爐排氣、玻璃退火、化工製程
高溫廢熱   500°C    鋼鐵廠、陶瓷窯爐、氣渦輪機尾氣
"""

SCENARIOS: dict[str, dict] = {
    "近室溫廢熱_25C": dict(
        target_tc_celsius=25,
        tc_tolerance=20,
        min_strength_mpa=150,    # 稀土 MCE 合金較軟/脆，門檻放寬
        max_hc=40,
    ),
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
