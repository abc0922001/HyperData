import json
import os
import glob
import statistics
import math
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Tuple, Optional, Any

# -----------------------------------------------------------------------------
# 全域配置與常數 (Configuration)
# -----------------------------------------------------------------------------

# 時區設定：台灣時間 (UTC+8)
TZ_TW = timezone(timedelta(hours=8))
NOW_TW = datetime.now(TZ_TW)

# 檔案系統路徑
DIR_DEVICES = 'devices'
FILE_OUTPUT = 'tw.html'

# 分支名稱識別 (Business Logic)
# 這些字串是用於識別 JSON 資料中不同 ROM 分支的關鍵
BRANCH_TW = "小米澎湃 OS 中国台湾省正式版"
BRANCH_GLOBAL = "小米澎湃 OS 国际正式版"

# 地區名稱映射表 (Normalization)
# 將原始 JSON 中的簡體中文或不一致的命名，標準化為台灣慣用詞彙
REGION_MAPPING = {
    "欧洲": "歐洲", "俄罗斯": "俄羅斯", "印度尼西亚": "印尼",
    "土耳其": "土耳其", "韩国": "韓國", "中国大陆": "中國",
    "中国": "中國", "演示机": "演示機", "运营商": "電信商",
    "定制": "客製", "政企标准": "政企標準", "政企": "政企",
    "EEA": "歐洲 EEA", "欧洲EEA": "歐洲 EEA",
    "正式版": "中國", "开发版": "開發版", "Beta": "Beta"
}

# -----------------------------------------------------------------------------
# 核心邏輯函數 (Core Logic)
# -----------------------------------------------------------------------------

def parse_version_tuple(version_str: str) -> Tuple[int, ...]:
    """
    將版本字串解析為整數元組，便於進行版本號比對。
    
    原理：
        移除 OS 前綴與結尾的英文字母，僅保留數字部分進行分割。
        例如: "OS1.0.1.0.UNATWXM" -> (1, 0, 1, 0)
    """
    if not version_str:
        return (0,)
    try:
        # 移除結尾的字母代碼 (通常是 7 碼，如 UNATWXM)
        clean_v = version_str[:-7] if len(version_str) > 7 else version_str
        if clean_v.startswith("OS"):
            clean_v = clean_v[2:]
        
        parts = clean_v.strip('.').split('.')
        return tuple(int(p) for p in parts if p.isdigit())
    except ValueError:
        return (0,)

def normalize_region_name(raw_name: str) -> str:
    """
    標準化地區名稱。
    
    原理：
        先移除通用前綴，再嘗試查表 (Look-up Table)。
        若查無對應，則進行關鍵字替換。此設計消除了大量的 if/else 判斷。
    """
    name = raw_name.replace("小米澎湃 OS ", "")
    
    # 嘗試精確匹配
    if name in REGION_MAPPING:
        return REGION_MAPPING[name]

    # 提取核心名稱 (移除後綴)
    core_name = name.replace("正式版", "").replace("版", "").strip()
    
    # 二次查表
    if core_name in REGION_MAPPING:
        return REGION_MAPPING[core_name]
        
    # 關鍵字替換 (Fallback)
    processed = core_name
    for key, value in REGION_MAPPING.items():
        processed = processed.replace(key, value)
    return processed

def check_abandonment_mad(history_list: List[Dict], days_since_last: int) -> bool:
    """
    使用中位數絕對偏差 (MAD) 演算法檢測是否疑似棄更。
    
    原理：
        更新間隔通常呈現不規則分佈，標準差 (SD) 易受極端值影響。
        MAD 對異常值具有更好的穩健性 (Robustness)。
        
        算法流程：
        1. 計算歷史更新間隔 (Intervals)。
        2. 計算間隔的中位數 (Median)。
        3. 計算每個間隔與中位數的偏差絕對值之中位數 (MAD)。
        4. 計算 Modified Z-score。若 > 4 (約等於 4 個標準差) 則視為異常延遲。
    """
    if len(history_list) < 2:
        return False

    # 解析日期序列
    dates = []
    for item in history_list:
        try:
            dates.append(datetime.strptime(item['release'], "%Y-%m-%d"))
        except (ValueError, TypeError):
            continue
            
    if len(dates) < 2:
        return False

    # 計算相鄰更新的時間間隔 (天)
    intervals = []
    for i in range(len(dates) - 1):
        diff = (dates[i] - dates[i+1]).days
        if diff >= 0:
            intervals.append(diff)

    if not intervals:
        return False

    median_val = statistics.median(intervals)
    deviations = [abs(x - median_val) for x in intervals]
    mad = statistics.median(deviations)

    # 防止除以零，設定最小 MAD 為 1 天
    mad_adj = max(mad, 1)
    
    # 常數 1.4826 用於將 MAD 轉換為估計標準差 (針對常態分佈假設)
    sigma_est = 1.4826 * mad_adj
    z_score = (days_since_last - median_val) / sigma_est

    return z_score > 4

# -----------------------------------------------------------------------------
# 資料處理 (Data Processing)
# -----------------------------------------------------------------------------

def process_device_file(file_path: str) -> Optional[Dict[str, Any]]:
    """
    讀取並處理單個裝置的 JSON 檔案。
    將原始結構轉換為便於渲染的統一格式。
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"Error reading {file_path}: {e}")
        return None

    device_code = data.get('device', '')
    if not device_code:
        return None

    # 初始化結構
    device_info = {
        'name': data.get('name', {}).get('zh', 'Unknown Device'),
        'code': device_code,
        'brand': 'Other', # 預設值，稍後由 TW 分支修正
        'tw': None,
        'global': None,
        'others': []
    }

    branches = data.get('branches', [])
    for branch in branches:
        branch_name = branch.get('name', {}).get('zh', '')
        roms = branch.get('roms', {})
        if not roms:
            continue

        # 轉換 ROM 列表並排序 (最新在前)
        rom_list = [
            {
                'os': v.get('os', k),
                'android': v.get('android', ''),
                'release': v.get('release', '1970-01-01')
            }
            for k, v in roms.items()
        ]
        rom_list.sort(key=lambda x: x['release'], reverse=True)
        
        branch_data = {'latest': rom_list[0], 'history': rom_list}

        # 根據分支名稱分類
        if branch_name == BRANCH_TW:
            device_info['tw'] = branch_data
            # 以台灣版定義的 Brand 為準
            if branch.get('brand'):
                device_info['brand'] = branch.get('brand')
        elif branch_name == BRANCH_GLOBAL:
            device_info['global'] = branch_data
        else:
            branch_data['label'] = normalize_region_name(branch_name)
            # 若無效名稱則 fallback 原名
            if not branch_data['label']:
                branch_data['label'] = branch_name
            device_info['others'].append(branch_data)

    # 若無台灣版資料，則不收錄此裝置
    if not device_info['tw']:
        return None

    # 對其他地區按發布日期排序
    device_info['others'].sort(key=lambda x: x['latest']['release'], reverse=True)
    
    return device_info

def collect_data() -> Tuple[List[Dict], List[str]]:
    """遍歷目錄並收集所有有效裝置資料。"""
    json_files = glob.glob(os.path.join(DIR_DEVICES, '*.json'))
    print(f"::group::初始化設定\n工作目錄: {os.getcwd()}\n處理檔案數: {len(json_files)}\n::endgroup::")

    devices = []
    brands = set()

    for path in json_files:
        if info := process_device_file(path):
            devices.append(info)
            brands.add(info['brand'])

    # 最終列表依據台灣版最新發布日期排序
    devices.sort(key=lambda x: x['tw']['latest']['release'], reverse=True)
    return devices, sorted(list(brands))

# -----------------------------------------------------------------------------
# HTML 生成組件 (View Components)
# -----------------------------------------------------------------------------

def html_tag_status(tw_ver: str, target_ver: str) -> str:
    """比較版本號並生成 領先/落後/同步 的 HTML 標籤。"""
    if not tw_ver or not target_ver:
        return ""
        
    t_tw = parse_version_tuple(tw_ver)
    t_curr = parse_version_tuple(target_ver)
    
    if t_tw < t_curr:
        return '<span class="text-xs px-1.5 py-0.5 rounded text-green-700 bg-green-50">↑ 領先</span>'
    elif t_tw > t_curr:
        return '<span class="text-xs px-1.5 py-0.5 rounded text-red-700 bg-red-50">↓ 落後</span>'
    else:
        return '<span class="text-xs px-1.5 py-0.5 rounded text-gray-600 bg-gray-100">= 同步</span>'

def html_days_ago(release_date: str) -> Tuple[int, str]:
    """計算天數差並返回數值與 HTML 字串。"""
    try:
        dt = datetime.strptime(release_date, "%Y-%m-%d").replace(tzinfo=TZ_TW)
        days = (NOW_TW - dt).days
        return days, f'<div class="text-[11px] text-gray-600 mt-0.5">({days} 天前)</div>'
    except ValueError:
        return -1, ""

def render_history_table(history: List[Dict], type_id: str) -> str:
    """生成隱藏的歷史版本表格。"""
    rows = []
    for i, rom in enumerate(history):
        interval_display = '<span class="text-xs text-blue-600">首版</span>'
        
        # 計算與上一版的間隔
        if i < len(history) - 1:
            try:
                curr = datetime.strptime(rom['release'], "%Y-%m-%d")
                prev = datetime.strptime(history[i+1]['release'], "%Y-%m-%d")
                diff = (curr - prev).days
                
                bg_cls = "bg-gray-100 text-gray-600"
                if diff > 90: bg_cls = "bg-orange-50 text-orange-600"
                elif diff < 30: bg_cls = "bg-green-50 text-green-600"
                
                interval_display = f'<span class="px-1.5 py-0.5 rounded {bg_cls}">{diff} 天</span>'
            except ValueError:
                interval_display = '<span class="text-gray-300">-</span>'

        rows.append(f'''
        <tr class="hover:bg-gray-50 transition-colors">
            <td class="py-2 pl-1 font-mono text-gray-700">{rom['os']}</td>
            <td class="py-2 text-gray-600">{rom['release']}</td>
            <td class="py-2 text-center">{interval_display}</td>
            <td class="py-2 text-right pr-1 text-gray-600">{rom['android']}</td>
        </tr>''')

    return f'''
    <div class="hidden mt-2 border-t border-gray-100 pt-2 animate-fade-in" data-type="{type_id}">
        <table class="w-full text-xs text-left">
            <thead class="text-gray-500 font-medium border-b border-gray-50">
                <tr>
                    <th class="py-2 pl-1">版本</th>
                    <th class="py-2">日期</th>
                    <th class="py-2 text-center">間隔</th>
                    <th class="py-2 text-right pr-1">Android</th>
                </tr>
            </thead>
            <tbody class="divide-y divide-gray-50">{''.join(rows)}</tbody>
        </table>
    </div>'''

def render_rom_card(info: Optional[Dict], label: str, style_type: str, tw_base_ver: str = None) -> str:
    """生成單個 ROM 分支的卡片 (台灣/國際/其他)。"""
    if not info:
        if style_type == 'global':
            return '''
            <div class="flex items-center justify-center p-3 rounded-lg border border-dashed border-gray-200 bg-gray-50 h-[88px]">
                <span class="text-xs text-gray-400 italic">無國際版資料</span>
            </div>'''
        return ""

    latest = info['latest']
    ver_str = latest['os']
    
    # 樣式配置策略 (Style Strategy)
    styles = {
        'tw': {
            'bg': 'bg-blue-50/50', 'border': 'border-blue-100', 
            'badge': 'bg-blue-100 text-blue-700', 'group': 'group/tw'
        },
        'global': {
            'bg': 'bg-white/50', 'border': 'border-gray-300 border-dashed', 
            'badge': 'bg-gray-100 text-gray-600', 'group': 'group/gl'
        },
        'other': {
            'bg': 'bg-purple-50/30', 'border': 'border-purple-100 border-dashed', 
            'badge': 'bg-purple-100 text-purple-700', 'group': 'group/ot'
        }
    }
    s = styles.get(style_type, styles['other'])
    
    # 狀態標籤 (僅非台灣版顯示)
    status_tag = html_tag_status(tw_base_ver, ver_str) if style_type != 'tw' else ""
    _, ago_html = html_days_ago(latest['release'])

    return f'''
    <div class="{s['group']}">
        <button type="button" onclick="toggleHistory(this)" aria-expanded="false" 
            class="w-full cursor-pointer flex items-center justify-between p-3 rounded-lg {s['bg']} border {s['border']} hover:bg-gray-50 transition-colors relative select-none focus:outline-none focus:ring-2 focus:ring-blue-500 text-left">
            <div class="flex items-center gap-3">
                <span class="inline-flex items-center px-2 py-1 rounded text-xs font-medium {s['badge']} shadow-sm transition-colors">{label} ▾</span>
                <div>
                    <div class="text-sm font-mono text-gray-700 font-bold">{ver_str}</div>
                    <div class="text-xs text-gray-600">Android {latest['android']}</div>
                </div>
            </div>
            <div class="flex flex-col items-end">
                <div class="text-xs text-gray-600 font-medium">{latest['release']}</div>
                {ago_html}
                {status_tag}
            </div>
        </button>
        {render_history_table(info['history'], f'{style_type}-hist')}
    </div>'''

def render_device_block(device: Dict) -> str:
    """生成完整裝置區塊 (包含標頭、台灣版卡片、國際版卡片、其他卡片)。"""
    tw_data = device['tw']['latest']
    days, ago_html = html_days_ago(tw_data['release'])
    
    # 判斷棄更狀態
    # 邏輯：MAD 演算法判定異常 OR 超過 100 天未更新
    is_abandoned = check_abandonment_mad(device['tw']['history'], days) or (days > 100)
    
    if is_abandoned:
        status_html = f'<span class="text-xs font-medium px-1.5 py-0.5 rounded mt-1 text-white" style="background-color: #6b7280;">疑似棄更 ({days} 天)</span>'
    else:
        color = "text-green-700 bg-green-50"
        if days > 90: color = "text-orange-700 bg-orange-50"
        elif days > 30: color = "text-gray-600 bg-gray-100"
        status_html = f'<span class="text-xs font-medium px-1.5 py-0.5 rounded mt-1 {color}">已過 {days} 天</span>'

    # 生成各區塊卡片
    card_tw = render_rom_card(device['tw'], "台灣版", 'tw')
    card_gl = render_rom_card(device['global'], "國際版", 'global', tw_data['os'])
    cards_other = "".join([
        render_rom_card(o, o['label'], 'other', tw_data['os']) for o in device['others']
    ])

    return f'''
    <div class="device-card bg-white rounded-2xl p-5 mb-4 shadow-sm hover:shadow-md transition-all border border-gray-100" 
         data-brand="{device['brand']}" data-date="{tw_data['release']}">
        <div class="flex flex-col sm:flex-row sm:items-start justify-between gap-4 mb-4">
            <div class="flex items-start gap-3">
                <div class="h-10 w-10 rounded-full bg-blue-50 flex items-center justify-center text-blue-700 font-bold text-lg flex-shrink-0">
                    {device['name'][0]}
                </div>
                <div>
                    <h2 class="text-lg font-bold text-gray-900 leading-tight device-title">{device['name']}</h2>
                    <div class="flex items-center gap-2 mt-1">
                        <span class="text-xs font-mono text-gray-600 bg-gray-50 px-1.5 py-0.5 rounded border border-gray-100 device-code">{device['code']}</span>
                        <span class="text-xs text-gray-600 bg-gray-50 px-1.5 py-0.5 rounded border border-gray-100">{device['brand']}</span>
                    </div>
                </div>
            </div>
            <div class="flex flex-col items-end">
                <span class="text-sm font-bold text-gray-700 bg-gray-50 px-2 py-1 rounded-md">{tw_data['release']}</span>
                {status_html}
            </div>
        </div>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
            {card_tw}
            {card_gl}
            {cards_other}
        </div>
    </div>'''

# -----------------------------------------------------------------------------
# 主程式 (Main Execution)
# -----------------------------------------------------------------------------

def main():
    devices, brands = collect_data()
    print(f"已收集 {len(devices)} 個裝置資料。")

    # 生成品牌選單
    brand_opts = '<option value="all">所有品牌</option>' + "".join(
        [f'<option value="{b}">{b}</option>' for b in brands]
    )

    # 組合最終 HTML
    # 注意：這裡將 CSS/JS 內嵌以保持單檔獨立性，符合原架構
    html = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>小米 HyperOS 台灣版更新追蹤</title>
    <meta name="description" content="追蹤 Xiaomi, Redmi, POCO 等機型的 HyperOS 台灣版與國際版更新狀態。">
    <link rel="stylesheet" href="assets/css/tw.css">
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; }}
        html {{ scroll-padding-top: 6rem; }}
        .device-card {{ content-visibility: auto; contain-intrinsic-size: 150px; }}
        /* 避免 Tailwind CDN 載入延遲的閃爍 */
        [v-cloak] {{ display: none; }}
    </style>
    <script>
        tailwind.config = {{
            theme: {{ extend: {{ colors: {{ 'mi-orange': '#ff6900' }} }} }}
        }}
    </script>
</head>
<body class="bg-gray-50 text-gray-800 antialiased min-h-screen pb-10">
    <div class="sticky top-0 z-50 bg-white/80 backdrop-blur-md border-b border-gray-200 shadow-sm">
        <div class="max-w-4xl mx-auto px-4 py-4">
            <div class="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                    <h1 class="text-2xl font-bold text-gray-900 tracking-tight text-mi-orange">HyperOS TW Tracker</h1>
                    <p class="text-xs text-gray-600 mt-1">更新時間: {NOW_TW.strftime("%Y-%m-%d %H:%M")} (UTC+8)</p>
                </div>
                <div class="flex flex-wrap gap-2 w-full md:w-auto items-center">
                    <label class="inline-flex items-center cursor-pointer bg-gray-100 hover:bg-gray-200 px-3 py-2 rounded-full text-sm font-medium transition-colors select-none">
                        <input type="checkbox" id="recentFilter" class="sr-only peer">
                        <div class="w-4 h-4 rounded-sm border-2 border-gray-400 mr-2 peer-checked:bg-mi-orange peer-checked:border-mi-orange flex items-center justify-center transition-all">
                            <svg class="w-3 h-3 text-white scale-0 peer-checked:scale-100 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7"></path></svg>
                        </div>
                        最近 <span id="daysLabel">30</span> 天
                    </label>
                    <select id="brandFilter" class="bg-gray-100 hover:bg-gray-200 text-gray-700 py-2 px-4 rounded-full text-sm font-medium focus:outline-none focus:ring-2 focus:ring-blue-500 cursor-pointer border-0">
                        {brand_opts}
                    </select>
                    <input type="text" id="searchInput" class="bg-gray-100 hover:bg-gray-200 focus:bg-white text-gray-700 py-2 px-4 rounded-full text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all border-0 placeholder-gray-400" placeholder="搜尋機型...">
                </div>
            </div>
        </div>
    </div>

    <main class="max-w-4xl mx-auto px-4 mt-6" id="content">
        {"".join([render_device_block(d) for d in devices])}
    </main>
    
    <div class="max-w-4xl mx-auto px-4 py-8 text-center text-gray-500 text-xs">
        Generated by GitHub Actions • Total {len(devices)} Devices
    </div>

    <script>
        function toggleHistory(btn) {{
            const div = btn.nextElementSibling;
            if (div) {{
                div.classList.toggle('hidden');
                btn.setAttribute('aria-expanded', !div.classList.contains('hidden'));
            }}
        }}

        // 過濾邏輯封裝
        (function() {{
            const searchInput = document.getElementById('searchInput');
            const brandFilter = document.getElementById('brandFilter');
            const recentFilter = document.getElementById('recentFilter');
            const daysLabel = document.getElementById('daysLabel');
            let recentDays = 30;

            function update() {{
                const q = searchInput.value.toLowerCase().trim();
                const brand = brandFilter.value;
                const onlyRecent = recentFilter.checked;
                const now = new Date();

                document.querySelectorAll('.device-card').forEach(card => {{
                    const name = card.querySelector('.device-title').textContent.toLowerCase();
                    const code = card.querySelector('.device-code').textContent.toLowerCase();
                    const dBrand = card.getAttribute('data-brand');
                    const dDate = new Date(card.getAttribute('data-date'));
                    
                    const matchText = name.includes(q) || code.includes(q);
                    const matchBrand = (brand === 'all') || (dBrand === brand);
                    let matchRec = true;
                    if (onlyRecent && dDate) {{
                        const diff = Math.ceil(Math.abs(now - dDate) / (86400000));
                        matchRec = diff <= recentDays;
                    }}
                    
                    card.classList.toggle('hidden', !(matchText && matchBrand && matchRec));
                }});
            }}

            // URL 參數處理
            const params = new URLSearchParams(window.location.search);
            if(params.get('q')) searchInput.value = params.get('q');
            if(params.get('brand')) {{
                const opt = Array.from(brandFilter.options).find(o => o.value.toLowerCase() === params.get('brand').toLowerCase());
                if(opt) brandFilter.value = opt.value;
            }}
            if(params.get('days')) {{
                const d = parseInt(params.get('days'));
                if(!isNaN(d) && d > 0) {{ recentDays = d; daysLabel.textContent = d; recentFilter.checked = true; }}
            }}

            [searchInput, brandFilter, recentFilter].forEach(el => el.addEventListener('input', update));
            if(params.toString()) update();
        }})();
    </script>
</body>
</html>"""

    with open(FILE_OUTPUT, 'w', encoding='utf-8') as f:
        f.write(html)

if __name__ == '__main__':
    main()