"""
HVAC 清潔設計精靈 — 互動式填空設計工具

逐步提問，自動生成完整清潔設計報告。
用法:
  python design_assist/scripts/design_wizard.py          ← 互動模式
  python design_assist/scripts/design_wizard.py --batch  ← 讀取 wizard_input.json
"""
import sys
import os
import json
import subprocess

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

# ── 問題定義 ──────────────────────────────────────────────────────────────────

QUESTIONS = [
    {
        'key':     'equipment',
        'label':   '設備名稱',
        'default': '日立 RAS-28NK',
        'hint':    '例：三菱 MSZ-GR28VF、大金 FTXS28GVMW',
        'type':    'str',
    },
    {
        'key':     'type',
        'label':   '機型類別',
        'default': 'split-2hp',
        'hint':    'split-1hp / split-1.5hp / split-2hp / cassette-2hp / cassette-4hp',
        'choices': ['split-1hp','split-1.5hp','split-2hp','cassette-2hp','cassette-4hp'],
        'type':    'choice',
    },
    {
        'key':     'contamination',
        'label':   '主要污垢類型',
        'default': 'dust',
        'hint':    'dust（灰塵）/ grease（油脂）/ scale（水垢）/ biofilm（生物膜）/ mixed（複合）',
        'choices': ['dust','grease','scale','biofilm','mixed'],
        'type':    'choice',
    },
    {
        'key':     'environment',
        'label':   '使用環境',
        'default': 'ac_indoor_unit',
        'hint':    'ac_indoor_unit / ac_outdoor_unit / city_water / coastal_air / industrial_air / kitchen_exhaust',
        'choices': ['ac_indoor_unit','ac_outdoor_unit','city_water','coastal_air','industrial_air','kitchen_exhaust'],
        'type':    'choice',
    },
    {
        'key':     'supply',
        'label':   '供水壓力 (bar)',
        'default': '3.0',
        'hint':    '一般自來水 2–4 bar，高壓清洗機 40–80 bar',
        'type':    'float',
        'min':     0.5,
        'max':     150.0,
    },
    {
        'key':     'width',
        'label':   '翅片寬度 (mm)',
        'default': '750',
        'hint':    '蒸發器/冷凝器盤管寬度方向尺寸',
        'type':    'int',
        'min':     100,
        'max':     3000,
    },
    {
        'key':     'height',
        'label':   '翅片高度 (mm)',
        'default': '200',
        'hint':    '蒸發器/冷凝器盤管高度方向尺寸',
        'type':    'int',
        'min':     50,
        'max':     2000,
    },
    {
        'key':     'fin_spacing',
        'label':   '翅片間距 (mm)',
        'default': '1.8',
        'hint':    '相鄰翅片中心距，住宅機典型 1.4–2.5 mm',
        'type':    'float',
        'min':     0.5,
        'max':     10.0,
    },
    {
        'key':     'fin_type',
        'label':   '翅片幾何類型',
        'default': 'plain',
        'hint':    'plain（平直）/ wavy（波浪）/ louvered（百葉）',
        'choices': ['plain','wavy','louvered'],
        'type':    'choice',
    },
    {
        'key':     'fin_material',
        'label':   '翅片材質',
        'default': 'aluminum',
        'hint':    'aluminum（鋁）/ copper（銅）',
        'choices': ['aluminum','copper'],
        'type':    'choice',
    },
    {
        'key':     'elapsed_hours',
        'label':   '已運行時數 (h)',
        'default': '1000',
        'hint':    '上次清潔後至今累積運行時數；不確定請填 1000',
        'type':    'int',
        'min':     0,
        'max':     50000,
    },
    {
        'key':     'face_velocity',
        'label':   '面風速 (m/s)',
        'default': '1.5',
        'hint':    '翅片前緣面風速；住宅機典型 1.0–2.5 m/s',
        'type':    'float',
        'min':     0.1,
        'max':     10.0,
    },
    {
        'key':     'rated_power_kw',
        'label':   '設備額定功率 (kW)',
        'default': '0.75',
        'hint':    '壓縮機+風機額定輸入功率；2HP 機約 0.7–1.0 kW',
        'type':    'float',
        'min':     0.1,
        'max':     50.0,
    },
    {
        'key':     'cleaning_cost',
        'label':   '清潔費用估算 (台幣)',
        'default': '1500',
        'hint':    '本次清潔作業費用（含工資、藥劑、耗材）',
        'type':    'int',
        'min':     100,
        'max':     100000,
    },
    {
        'key':     'output',
        'label':   '輸出報告檔名',
        'default': 'hvac_report.md',
        'hint':    '留空則直接印出，填入檔名則存檔',
        'type':    'str',
    },
]

# ── 互動詢問 ──────────────────────────────────────────────────────────────────

def _ask(q: dict, batch: dict | None = None) -> str:
    default = q['default']
    if batch is not None:
        val = str(batch.get(q['key'], default))
        print(f"  {q['label']}: {val}")
        return val

    hint = f"  ({q['hint']})" if q.get('hint') else ''
    prompt = f"\n● {q['label']}{hint}\n  [預設: {default}] → "
    while True:
        raw = input(prompt).strip()
        if not raw:
            return default
        # 驗證
        qtype = q['type']
        if qtype == 'choice' and raw not in q['choices']:
            print(f"  ⚠ 請從 {q['choices']} 中選擇")
            continue
        if qtype in ('float', 'int'):
            try:
                v = float(raw)
            except ValueError:
                print(f"  ⚠ 請輸入數字")
                continue
            if 'min' in q and v < q['min']:
                print(f"  ⚠ 最小值 {q['min']}")
                continue
            if 'max' in q and v > q['max']:
                print(f"  ⚠ 最大值 {q['max']}")
                continue
        return raw


def collect_answers(batch: dict | None = None) -> dict:
    answers = {}
    for q in QUESTIONS:
        answers[q['key']] = _ask(q, batch)
    return answers


# ── 組裝 comprehensive_report.py 指令 ────────────────────────────────────────

def build_command(a: dict) -> list[str]:
    script = os.path.join(os.path.dirname(__file__), 'comprehensive_report.py')
    cmd = [
        sys.executable, script,
        '--equipment',     a['equipment'],
        '--type',          a['type'],
        '--supply',        a['supply'],
        '--width',         a['width'],
        '--height',        a['height'],
        '--contamination', a['contamination'],
        '--environment',   a['environment'],
        '--fin-material',  a['fin_material'],
        '--fin-spacing',   a['fin_spacing'],
        '--fin-type',      a['fin_type'],
        '--elapsed-hours', a['elapsed_hours'],
        '--face-velocity', a['face_velocity'],
        '--rated-power',   a['rated_power_kw'],
        '--cleaning-cost', a['cleaning_cost'],
    ]
    if a.get('output'):
        cmd += ['--output', a['output']]
    return cmd


# ── 主程式 ────────────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description='HVAC 清潔設計精靈')
    parser.add_argument('--batch', type=str, default=None,
                        help='批次模式：傳入 JSON 檔路徑（略過互動）')
    parser.add_argument('--dump-template', action='store_true',
                        help='輸出填空模板 wizard_template.json 後結束')
    args = parser.parse_args()

    if args.dump_template:
        template = {q['key']: q['default'] for q in QUESTIONS}
        fname = 'wizard_template.json'
        with open(fname, 'w', encoding='utf-8') as f:
            json.dump(template, f, ensure_ascii=False, indent=2)
        print(f'模板已存至 {fname}，填好後以 --batch wizard_template.json 執行')
        return

    print('=' * 60)
    print('  HVAC 清潔設計精靈')
    print('  直接按 Enter 接受預設值；輸入 q 隨時離開')
    print('=' * 60)

    batch_data = None
    if args.batch:
        with open(args.batch, encoding='utf-8') as f:
            batch_data = json.load(f)
        print(f'[批次模式] 讀取 {args.batch}')

    try:
        answers = collect_answers(batch_data)
    except (KeyboardInterrupt, EOFError):
        print('\n已取消。')
        return

    print('\n' + '─' * 60)
    print('  確認設計參數，開始運算...')
    print('─' * 60)

    cmd = build_command(answers)
    result = subprocess.run(cmd, capture_output=False)
    if result.returncode != 0:
        print('\n⚠ 報告生成失敗，請確認參數是否正確。')


if __name__ == '__main__':
    main()
