import json
import os
import glob
import statistics
from datetime import datetime, timedelta, timezone
from functools import lru_cache

# 設定為台灣時區 (UTC+8)
tz_tw = timezone(timedelta(hours=8))
now_tw = datetime.now(tz_tw)
gen_time = now_tw.strftime("%Y-%m-%d %H:%M")

# 設定路徑
devices_dir = 'devices'
output_file = 'tw.html'

# 定義要抓取的目標分支
TARGET_TW = "小米澎湃 OS 中国台湾省正式版"
TARGET_GLOBAL = "小米澎湃 OS 国际正式版"

# === 優化 1: 快取版本解析結果 ===
@lru_cache(maxsize=512)
def version_to_tuple(v_str):
    try:
        clean_v = v_str[:-7] if len(v_str) > 7 else v_str
        if clean_v.startswith("OS"): clean_v = clean_v[2:]
        clean_v = clean_v.strip('.')
        return tuple(int(x) for x in clean_v.split('.') if x.isdigit())
    except:
        return (0,)

# === 優化 2: 預編譯地區對照表 ===
REGION_MAPPING = {
    "欧洲": "歐洲", "俄罗斯": "俄羅斯", "印度尼西亚": "印尼",
    "土耳其": "土耳其", "韩国": "韓國", "中国大陆": "中國",
    "中国": "中國", "演示机": "演示機", "运营商": "電信商",
    "定制": "客製", "政企标准": "政企標準", "政企": "政企"
}

def get_region_label(branch_name_zh):
    name = branch_name_zh.replace("小米澎湃 OS ", "")
    if name == "正式版": return "中國"
    if name == "开发版": return "開發版"
    if name == "Beta": return "Beta"
    
    core_name = name.replace("正式版", "").replace("版", "").strip()
    if core_name in REGION_MAPPING:
        return REGION_MAPPING[core_name]
    if core_name == "EEA": return "歐洲 EEA"
    if core_name == "欧洲EEA": return "歐洲 EEA"

    processed_name = core_name
    for sc, tc in REGION_MAPPING.items():
        processed_name = processed_name.replace(sc, tc)
    return processed_name

# === 優化 3: 預解析日期避免重複轉換 ===
def parse_history_dates(history_list):
    """提取並解析所有日期一次"""
    dates = []
    for item in history_list:
        try:
            dates.append(datetime.strptime(item['release'], "%Y-%m-%d"))
        except: 
            pass
    return dates

def is_abandoned_mad(history_list, days_since_last):
    if not history_list or len(history_list) < 2:
        return False
    
    dates = parse_history_dates(history_list)
    if len(dates) < 2:
        return False
    
    # 計算間隔（利用已排序特性）
    intervals = [
        (dates[i] - dates[i+1]).days 
        for i in range(len(dates) - 1) 
        if (dates[i] - dates[i+1]).days >= 0
    ]
    
    if not intervals:
        return False

    median_val = statistics.median(intervals)
    mad = statistics.median([abs(x - median_val) for x in intervals])
    mad_adj = max(mad, 1)
    score = (days_since_last - median_val) / (1.4826 * mad_adj)
    
    return score > 4

def get_max_interval(history_list):
    """計算歷史更新最大間隔天數"""
    if not history_list or len(history_list) < 2:
        return 0
    
    dates = parse_history_dates(history_list)
    if len(dates) < 2:
        return 0
    
    intervals = [
        (dates[i] - dates[i+1]).days 
        for i in range(len(dates) - 1) 
        if (dates[i] - dates[i+1]).days >= 0
    ]
    
    if not intervals:
        return 0
        
    return max(intervals)

print(f"::group::初始化設定")
print(f"工作目錄: {os.getcwd()}")
print(f"輸出檔案: {output_file}")
print(f"::endgroup::")

# === 資料收集階段 ===
devices_map = {}
all_brands = set()
json_files = glob.glob(os.path.join(devices_dir, '*.json'))
print(f"Found {len(json_files)} device files. Processing...")

for file_path in json_files:
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        device_name = data.get('name', {}).get('zh', 'Unknown Device')
        device_code = data.get('device', '')
        
        if device_code not in devices_map:
            devices_map[device_code] = {
                'name': device_name,
                'code': device_code,
                'brand': 'Other',
                'tw': None,
                'global': None,
                'others': []
            }
        
        branches = data.get('branches', [])
        for branch in branches:
            branch_name_zh = branch.get('name', {}).get('zh', '')
            
            target_type = None
            branch_label = ""

            if branch_name_zh == TARGET_TW:
                target_type = 'tw'
                brand = branch.get('brand', 'Xiaomi')
                if brand: 
                    devices_map[device_code]['brand'] = brand
            elif branch_name_zh == TARGET_GLOBAL:
                target_type = 'global'
            else:
                target_type = 'other'
                branch_label = get_region_label(branch_name_zh)
                if not branch_label: 
                    branch_label = branch_name_zh
            
            roms = branch.get('roms', {})
            if not roms: 
                continue
            
            rom_list = [
                {
                    'os': v.get('os', k),
                    'android': v.get('android', ''),
                    'release': v.get('release', '1970-01-01')
                }
                for k, v in roms.items()
            ]
            rom_list.sort(key=lambda x: x['release'], reverse=True)
            
            if rom_list:
                info_obj = {
                    'latest': rom_list[0],
                    'history': rom_list
                }
                
                if target_type == 'tw':
                    devices_map[device_code]['tw'] = info_obj
                elif target_type == 'global':
                    devices_map[device_code]['global'] = info_obj
                elif target_type == 'other':
                    info_obj['label'] = branch_label
                    devices_map[device_code]['others'].append(info_obj)
                
    except Exception as e:
        print(f"Error processing {file_path}: {e}")

# 篩選與排序
final_list = []
for code, info in devices_map.items():
    if info['tw']:
        if info['others']:
            info['others'].sort(key=lambda x: x['latest']['release'], reverse=True)
        final_list.append(info)
        all_brands.add(info['brand'])

final_list.sort(key=lambda x: x['tw']['latest']['release'], reverse=True)

brand_options_list = ['<option value="all">所有品牌</option>']
for brand in sorted(list(all_brands)):
    brand_options_list.append(f'<option value="{brand}">{brand}</option>')
brand_options = ''.join(brand_options_list)

print(f"Collected {len(final_list)} devices.")

# === 優化 4: 批次生成 HTML (使用 list) ===
def generate_history_html(history_list, type_class):
    parts = [
        f'<div class="hidden mt-2 border-t border-gray-100 pt-2 animate-fade-in" data-type="{type_class}">',
        '<table class="w-full text-xs text-left">',
        '<thead class="text-gray-500 font-medium border-b border-gray-50"><tr>',
        '<th class="py-2 pl-1">版本</th><th class="py-2">日期</th>',
        '<th class="py-2 text-center">間隔</th><th class="py-2 text-right pr-1">Android</th>',
        '</tr></thead><tbody class="divide-y divide-gray-50">'
    ]
    
    for i, rom in enumerate(history_list):
        interval_html = '<span class="text-gray-300">-</span>'
        
        if i < len(history_list) - 1:
            try:
                current_date = datetime.strptime(rom['release'], "%Y-%m-%d")
                prev_date = datetime.strptime(history_list[i+1]['release'], "%Y-%m-%d")
                delta_days = (current_date - prev_date).days
                
                if delta_days > 90: 
                    bg_color = "bg-orange-50 text-orange-600"
                elif delta_days < 30: 
                    bg_color = "bg-green-50 text-green-600"
                else: 
                    bg_color = "bg-gray-100 text-gray-600"
                    
                interval_html = f'<span class="px-1.5 py-0.5 rounded {bg_color}">{delta_days} 天</span>'
            except: 
                pass
        else:
            interval_html = '<span class="text-xs text-blue-600">首版</span>'

        parts.append(
            f'<tr class="hover:bg-gray-50 transition-colors">'
            f'<td class="py-2 pl-1 font-mono text-gray-700">{rom["os"]}</td>'
            f'<td class="py-2 text-gray-600">{rom["release"]}</td>'
            f'<td class="py-2 text-center">{interval_html}</td>'
            f'<td class="py-2 text-right pr-1 text-gray-600">{rom["android"]}</td>'
            f'</tr>'
        )
    
    parts.append('</tbody></table></div>')
    return ''.join(parts)

def generate_card_html(info, region_label, region_type, tw_ver_str=None):
    if not info:
        if region_type == 'global':
            return '<div class="flex items-center justify-center p-3 rounded-lg border border-dashed border-gray-200 bg-gray-50 h-[88px]"><span class="text-xs text-gray-400 italic">無國際版資料</span></div>'
        return ""

    latest = info['latest']
    ver_str = latest['os']
    
    # 版本比較
    ver_status_tag = ""
    if region_type != 'tw' and tw_ver_str:
        tw_tup = version_to_tuple(tw_ver_str)
        curr_tup = version_to_tuple(ver_str)
        if tw_tup < curr_tup:
            ver_status_tag = '<span class="text-xs px-1.5 py-0.5 rounded text-green-700 bg-green-50">↑ 領先</span>'
        elif tw_tup > curr_tup:
            ver_status_tag = '<span class="text-xs px-1.5 py-0.5 rounded text-red-700 bg-red-50">↓ 落後</span>'
        else:
            ver_status_tag = '<span class="text-xs px-1.5 py-0.5 rounded text-gray-600 bg-gray-100">= 同步</span>'

    # 樣式配置
    styles = {
        'tw': ('bg-blue-50/50', 'border-blue-100', 'bg-blue-100', 'text-blue-700', 'hover:bg-blue-50', 'group/tw'),
        'global': ('bg-white/50', 'border-gray-300 border-dashed', 'bg-gray-100', 'text-gray-600', 'hover:bg-gray-50', 'group/gl'),
        'other': ('bg-purple-50/30', 'border-purple-100 border-dashed', 'bg-purple-100', 'text-purple-700', 'hover:bg-purple-50', 'group/ot')
    }
    bg_color, border_color, badge_bg, badge_text, hover_bg, group_class = styles[region_type]

    history_html = generate_history_html(info['history'], f'{region_type}-history')
    
    # 計算天數
    ago_html = ""
    try:
        dt = datetime.strptime(latest['release'], "%Y-%m-%d").replace(tzinfo=tz_tw)
        days = (now_tw - dt).days
        ago_html = f'<div class="text-[11px] text-gray-600 mt-0.5">({days} 天前)</div>'
    except: 
        pass

    return (
        f'<div class="{group_class}">'
        f'<button type="button" onclick="toggleHistory(this)" aria-expanded="false" '
        f'class="w-full cursor-pointer flex items-center justify-between p-3 rounded-lg {bg_color} border {border_color} {hover_bg} transition-colors relative select-none focus:outline-none focus:ring-2 focus:ring-blue-500 text-left">'
        f'<div class="flex items-center gap-3">'
        f'<span class="inline-flex items-center px-2 py-1 rounded text-xs font-medium {badge_bg} {badge_text} shadow-sm transition-colors">{region_label} ▾</span>'
        f'<div><div class="text-sm font-mono text-gray-700 font-bold">{ver_str}</div>'
        f'<div class="text-xs text-gray-600">Android {latest["android"]}</div></div></div>'
        f'<div class="flex flex-col items-end">'
        f'<div class="text-xs text-gray-600 font-medium">{latest["release"]}</div>'
        f'{ago_html}{ver_status_tag}</div></button>{history_html}</div>'
    )

# === 優化 5: 主 HTML 使用 list 累積 ===
html_parts = [f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>小米 HyperOS 台灣版更新追蹤</title>
    <meta name="description" content="小米 HyperOS 台灣版更新追蹤 - 提供 Xiaomi, Redmi, POCO 等機型的 HyperOS 台灣版與國際版更新資訊與歷史版本記錄。">
    <meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; font-src 'self'; img-src 'self' data:; connect-src 'self';">
    <link rel="stylesheet" href="assets/css/tw.css">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, "Noto Sans TC", "Microsoft JhengHei", sans-serif; }}
        html {{ scroll-padding-top: 6rem; }}
        .no-scrollbar::-webkit-scrollbar {{ display: none; }}
        .no-scrollbar {{ -ms-overflow-style: none; scrollbar-width: none; }}
        .device-card {{ content-visibility: auto; contain-intrinsic-size: 150px; }}
        @media (prefers-reduced-motion: reduce) {{
            *, ::before, ::after {{
                animation-duration: 0.01ms !important;
                animation-iteration-count: 1 !important;
                transition-duration: 0.01ms !important;
                scroll-behavior: auto !important;
            }}
        }}
    </style>
</head>
<body class="bg-gray-50 text-gray-800 antialiased min-h-screen pb-10">
    <a href="#content" class="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:p-4 focus:bg-white focus:text-blue-600">跳至主要內容</a>
    <div class="sticky top-0 z-50 bg-white/80 backdrop-blur-md border-b border-gray-200 shadow-sm">
        <div class="max-w-4xl mx-auto px-4 py-4">
            <div class="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                    <h1 class="text-2xl font-bold text-gray-900 tracking-tight text-mi-orange">HyperOS TW Tracker</h1>
                    <p class="text-xs text-gray-600 mt-1">更新時間: {gen_time} (UTC+8)</p>
                </div>
                <div class="flex flex-wrap gap-2 w-full md:w-auto items-center">
                    <label class="inline-flex items-center cursor-pointer bg-gray-100 hover:bg-gray-200 px-3 py-2 rounded-full text-sm font-medium transition-colors select-none">
                        <input type="checkbox" id="recentFilter" class="sr-only peer">
                        <div class="w-4 h-4 rounded-sm border-2 border-gray-400 mr-2 peer-checked:bg-mi-orange peer-checked:border-mi-orange flex items-center justify-center transition-all">
                            <svg class="w-3 h-3 text-white scale-0 peer-checked:scale-100 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7"></path></svg>
                        </div>
                        最近 <span id="daysLabel">30</span> 天
                    </label>
                    <select id="brandFilter" aria-label="選擇品牌" class="bg-gray-100 hover:bg-gray-200 text-gray-700 py-2 px-4 rounded-full text-sm font-medium focus:outline-none focus:ring-2 focus:ring-blue-500 transition-colors cursor-pointer border-0">
                        {brand_options}
                    </select>
                    <div class="relative flex-grow md:w-48">
                        <input type="text" id="searchInput" aria-label="搜尋裝置" class="w-full bg-gray-100 hover:bg-gray-200 focus:bg-white text-gray-700 py-2 pl-10 pr-4 rounded-full text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all border-0 placeholder-gray-400" placeholder="搜尋機型...">
                        <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-600">
                            <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path></svg>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    <main class="max-w-4xl mx-auto px-4 mt-6" id="content">
"""]

# 生成設備卡片
for device in final_list:
    tw = device['tw']['latest']
    tw_ver = tw['os']
    tw_date = tw['release']
    tw_history = device['tw']['history']
    
    # Header Info
    ago_html = ""
    try:
        tw_dt = datetime.strptime(tw_date, "%Y-%m-%d").replace(tzinfo=tz_tw)
        days_ago = (now_tw - tw_dt).days
        max_interval = get_max_interval(tw_history)
        is_abandoned = is_abandoned_mad(tw_history, days_ago) or (max_interval > 0 and days_ago > 2 * max_interval)

        if is_abandoned:
            ago_html = f'<span class="text-xs font-medium px-1.5 py-0.5 rounded mt-1 text-white" style="background-color: #6b7280;">疑似棄更 ({days_ago} 天)</span>'
        else:
            status_text = f"已過 {days_ago} 天"
            if days_ago > 90: 
                ago_color = "text-orange-700 bg-orange-50"
            elif days_ago > 30: 
                ago_color = "text-gray-600 bg-gray-100"
            else: 
                ago_color = "text-green-700 bg-green-50"
            ago_html = f'<span class="text-xs font-medium px-1.5 py-0.5 rounded mt-1 {ago_color}">{status_text}</span>'
    except: 
        pass

    tw_card = generate_card_html(device['tw'], "台灣版", 'tw')
    gl_card = generate_card_html(device['global'], "國際版", 'global', tw_ver)
    
    others_cards = ''.join(
        generate_card_html(other, other['label'], 'other', tw_ver)
        for other in device['others']
    ) if device['others'] else ""

    html_parts.append(
        f'<div class="device-card bg-white rounded-2xl p-5 mb-4 shadow-sm hover:shadow-md transition-all border border-gray-100" data-brand="{device["brand"]}" data-date="{tw_date}">'
        f'<div class="flex flex-col sm:flex-row sm:items-start justify-between gap-4 mb-4">'
        f'<div class="flex items-start gap-3">'
        f'<div class="h-10 w-10 rounded-full bg-blue-50 flex items-center justify-center text-blue-700 font-bold text-lg flex-shrink-0">{device["name"][0]}</div>'
        f'<div><h2 class="text-lg font-bold text-gray-900 leading-tight device-title">{device["name"]}</h2>'
        f'<div class="flex items-center gap-2 mt-1">'
        f'<span class="text-xs font-mono text-gray-600 bg-gray-50 px-1.5 py-0.5 rounded border border-gray-100 device-code">{device["code"]}</span>'
        f'<span class="text-xs text-gray-600 bg-gray-50 px-1.5 py-0.5 rounded border border-gray-100">{device["brand"]}</span>'
        f'</div></div></div>'
        f'<div class="flex flex-col items-end">'
        f'<span class="text-sm font-bold text-gray-700 bg-gray-50 px-2 py-1 rounded-md">{tw_date}</span>'
        f'{ago_html}</div></div>'
        f'<div class="grid grid-cols-1 md:grid-cols-2 gap-3">{tw_card}{gl_card}{others_cards}</div>'
        f'</div>'
    )

html_parts.append(f"""
    </main>
    <div class="max-w-4xl mx-auto px-4 py-8 text-center text-gray-500 text-xs">
        Generated by GitHub Actions • Total {len(final_list)} Devices
    </div>
    <script>
        function toggleHistory(element) {{
            const historyDiv = element.nextElementSibling;
            if (historyDiv) {{
                const isHidden = historyDiv.classList.toggle('hidden');
                element.setAttribute('aria-expanded', !isHidden);
            }}
        }}
        const searchInput = document.getElementById('searchInput');
        const brandFilter = document.getElementById('brandFilter');
        const recentFilter = document.getElementById('recentFilter');
        const daysLabel = document.getElementById('daysLabel');
        let recentDaysThreshold = 30;

        function filterContent() {{
            const searchText = searchInput.value.toLowerCase().trim();
            const selectedBrand = brandFilter.value;
            const isRecent = recentFilter.checked;
            const cards = document.querySelectorAll('.device-card');
            const now = new Date();

            cards.forEach(card => {{
                const name = card.querySelector('.device-title').textContent.toLowerCase();
                const code = card.querySelector('.device-code').textContent.toLowerCase();
                const brand = card.getAttribute('data-brand');
                const dateStr = card.getAttribute('data-date');
                
                const matchText = name.includes(searchText) || code.includes(searchText);
                const matchBrand = (selectedBrand === 'all') || (brand === selectedBrand);
                
                let matchRecent = true;
                if (isRecent && dateStr) {{
                    const releaseDate = new Date(dateStr);
                    const diffTime = Math.abs(now - releaseDate);
                    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24)); 
                    matchRecent = diffDays <= recentDaysThreshold;
                }}

                card.classList.toggle('hidden', !(matchText && matchBrand && matchRecent));
            }});
        }}
        
        searchInput.addEventListener('input', filterContent);
        brandFilter.addEventListener('change', filterContent);
        recentFilter.addEventListener('change', filterContent);

        try {{
            const urlParams = new URLSearchParams(window.location.search);
            const query = urlParams.get('q');
            if (query) searchInput.value = query;

            const brandParam = urlParams.get('brand');
            if (brandParam) {{
                const options = Array.from(brandFilter.options);
                const match = options.find(opt => opt.value.toLowerCase() === brandParam.toLowerCase());
                if (match) brandFilter.value = match.value;
            }}

            const daysParam = urlParams.get('days');
            if (daysParam) {{
                const days = parseInt(daysParam);
                if (!isNaN(days) && days > 0) {{
                    recentDaysThreshold = days;
                    daysLabel.textContent = days;
                    recentFilter.checked = true;
                }}
            }}

            if (query || brandParam || daysParam) filterContent();
        }} catch (e) {{ console.error(e); }}
    </script>
</body>
</html>
""")

# 一次性寫入
with open(output_file, 'w', encoding='utf-8') as f:
    f.write(''.join(html_parts))

print(f"✓ Generated {output_file} with {len(final_list)} devices")
