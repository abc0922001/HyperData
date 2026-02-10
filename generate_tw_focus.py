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

def get_abandoned_threshold(history_list):
    """計算棄更門檻天數 (整合 MAD 與 Max Interval)"""
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
        
    # MAD Threshold Calculation
    median_val = statistics.median(intervals)
    mad = statistics.median([abs(x - median_val) for x in intervals])
    mad_adj = max(mad, 1)
    thresh_mad = 3 * 1.4826 * mad_adj + median_val
    
    # Max Interval Threshold Calculation
    max_val = max(intervals)
    thresh_max = 2 * max_val if max_val > 0 else float('inf')
    
    # 若超過任一門檻即視為棄更 -> 取最小值作為判斷標準
    return int(min(thresh_mad, thresh_max))

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
        f'<div class="hidden mt-3 border-t border-gray-100 pt-3 animate-fade-in" data-type="{type_class}">',
        '<div class="overflow-x-auto">',
        '<table class="w-full text-xs text-left whitespace-nowrap">',
        '<thead class="text-gray-400 font-medium border-b border-gray-50"><tr>',
        '<th class="py-2 pl-2">版本</th><th class="py-2">日期</th>',
        '<th class="py-2 text-center">間隔</th><th class="py-2 text-right pr-2">Android</th>',
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
                    bg_color = "bg-orange-100 text-orange-700"
                elif delta_days < 30: 
                    bg_color = "bg-green-100 text-green-700"
                else: 
                    bg_color = "bg-gray-100 text-gray-600"
                    
                interval_html = f'<span class="px-2 py-0.5 rounded-full text-[10px] font-medium {bg_color}">{delta_days} 天</span>'
            except: 
                pass
        else:
            interval_html = '<span class="text-[10px] font-medium text-blue-600 bg-blue-50 px-2 py-0.5 rounded-full">首版</span>'

        parts.append(
            f'<tr class="hover:bg-gray-50 transition-colors">'
            f'<td class="py-2.5 pl-2 font-mono text-gray-700 font-medium">{rom["os"]}</td>'
            f'<td class="py-2.5 text-gray-500">{rom["release"]}</td>'
            f'<td class="py-2.5 text-center">{interval_html}</td>'
            f'<td class="py-2.5 text-right pr-2 text-gray-500">{rom["android"]}</td>'
            f'</tr>'
        )
    
    parts.append('</tbody></table></div></div>')
    return ''.join(parts)

def generate_card_html(info, region_label, region_type, tw_ver_str=None):
    if not info:
        if region_type == 'global':
            return (
                '<div class="flex items-center justify-center p-4 rounded-xl border border-dashed border-gray-200 bg-gray-50/50 h-[104px]">'
                '<span class="text-xs text-gray-400 font-medium italic">無國際版資料</span>'
                '</div>'
            )
        return ""

    latest = info['latest']
    ver_str = latest['os']
    
    # Version Comparison Logic
    ver_status_tag = ""
    if region_type != 'tw' and tw_ver_str:
        tw_tup = version_to_tuple(tw_ver_str)
        curr_tup = version_to_tuple(ver_str)
        if tw_tup < curr_tup:
            ver_status_tag = '<span class="text-[10px] font-bold px-2 py-0.5 rounded-full text-green-700 bg-green-100 border border-green-200 shadow-sm">領先</span>'
        elif tw_tup > curr_tup:
            ver_status_tag = '<span class="text-[10px] font-bold px-2 py-0.5 rounded-full text-rose-700 bg-rose-100 border border-rose-200 shadow-sm">落後</span>'
        else:
            ver_status_tag = '<span class="text-[10px] font-bold px-2 py-0.5 rounded-full text-gray-600 bg-gray-100 border border-gray-200">同步</span>'

    # Style Configuration
    # (Background, Border, BadgeBg, BadgeText, HoverBg, GroupClass)
    styles = {
        'tw': ('bg-gradient-to-br from-blue-50 to-white', 'border-blue-100', 'bg-blue-100', 'text-blue-700', 'hover:border-blue-300', 'group/tw'),
        'global': ('bg-white', 'border-gray-200', 'bg-gray-100', 'text-gray-600', 'hover:border-gray-300', 'group/gl'),
        'other': ('bg-purple-50/30', 'border-purple-100', 'bg-purple-100', 'text-purple-700', 'hover:border-purple-300', 'group/ot')
    }
    bg_color, border_color, badge_bg, badge_text, hover_border, group_class = styles[region_type]

    history_html = generate_history_html(info['history'], f'{region_type}-history')
    
    # Calculate Days Ago
    ago_html = ""
    try:
        dt = datetime.strptime(latest['release'], "%Y-%m-%d").replace(tzinfo=tz_tw)
        days = (now_tw - dt).days
        ago_html = f'<div class="text-[10px] text-gray-500 font-medium mt-1">({days} 天前)</div>'
    except: 
        pass

    return (
        f'<div class="{group_class} relative">'
        f'<button type="button" onclick="toggleHistory(this)" aria-expanded="false" '
        f'class="w-full text-left cursor-pointer flex flex-col p-4 rounded-xl {bg_color} border {border_color} {hover_border} transition-all duration-200 shadow-sm hover:shadow-md relative select-none focus:outline-none focus:ring-2 focus:ring-blue-500/20">'
        
        f'<div class="flex items-center justify-between w-full mb-2">'
        f'<span class="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wide {badge_bg} {badge_text}">{region_label}</span>'
        f'{ver_status_tag}'
        f'</div>'
        
        f'<div class="flex items-end justify-between w-full">'
        f'<div>'
        f'<div class="text-sm font-mono text-gray-900 font-bold tracking-tight">{ver_str}</div>'
        f'<div class="text-[10px] text-gray-500 font-medium mt-0.5">Android {latest["android"]}</div>'
        f'</div>'
        
        f'<div class="flex flex-col items-end">'
        f'<div class="text-xs font-semibold text-gray-700">{latest["release"]}</div>'
        f'{ago_html}'
        f'</div>'
        f'</div>'
        
        f'</button>{history_html}</div>'
    )

# === 優化 5: 主 HTML 使用 list 累積 ===
html_parts = [f"""<!DOCTYPE html>
<html lang="zh-TW" class="scroll-smooth">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>小米 HyperOS 台灣版更新追蹤</title>
    <meta name="description" content="小米 HyperOS 台灣版更新追蹤 - 提供 Xiaomi, Redmi, POCO 等機型的 HyperOS 台灣版與國際版更新資訊與歷史版本記錄。">
    <link rel="stylesheet" href="assets/css/tw.css">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
</head>
<body class="bg-slate-50 text-slate-800 antialiased min-h-screen pb-20 selection:bg-orange-100 selection:text-orange-900">
    <a href="#content" class="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:p-4 focus:bg-white focus:text-blue-600 focus:ring-2 focus:ring-blue-500 rounded-lg m-4">跳至主要內容</a>
    
    <div class="sticky top-0 z-50 glass-header transition-all duration-300">
        <div class="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
            <div class="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div class="flex items-center gap-3">
                    <div class="h-10 w-10 bg-gradient-to-br from-orange-500 to-red-500 rounded-xl flex items-center justify-center text-white font-bold shadow-lg shadow-orange-500/20">
                        <svg class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
                    </div>
                    <div>
                        <h1 class="text-xl font-bold text-slate-900 tracking-tight leading-none">HyperOS <span class="text-mi-orange">Tracker</span></h1>
                        <p class="text-xs text-slate-500 mt-1 font-medium">更新時間: {gen_time} (UTC+8)</p>
                    </div>
                </div>
                
                <div class="flex flex-col sm:flex-row gap-2 w-full md:w-auto">
                    <div class="relative flex-grow sm:w-64 group">
                        <input type="text" id="searchInput" aria-label="搜尋機型" 
                            class="w-full bg-slate-100/50 hover:bg-slate-100 focus:bg-white text-slate-700 py-2.5 pl-10 pr-4 rounded-xl text-sm font-medium focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 transition-all border border-transparent focus:shadow-sm placeholder-slate-400" 
                            placeholder="搜尋機型...">
                        <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400 group-focus-within:text-blue-500 transition-colors">
                            <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path></svg>
                        </div>
                    </div>
                    
                    <div class="flex gap-2 overflow-x-auto pb-1 sm:pb-0 no-scrollbar">
                        <select id="brandFilter" aria-label="品牌篩選" class="bg-white hover:bg-slate-50 text-slate-700 py-2.5 px-4 pr-8 rounded-xl text-sm font-semibold focus:outline-none focus:ring-2 focus:ring-blue-500/20 border border-slate-200 cursor-pointer transition-all shadow-sm">
                            {brand_options}
                        </select>
                        
                        <select id="daysFilter" aria-label="時間範圍" class="bg-white hover:bg-slate-50 text-slate-700 py-2.5 px-4 pr-8 rounded-xl text-sm font-semibold focus:outline-none focus:ring-2 focus:ring-blue-500/20 border border-slate-200 cursor-pointer transition-all shadow-sm">
                            <option value="7">7 天</option>
                            <option value="14">14 天</option>
                            <option value="30" selected>30 天</option>
                            <option value="60">60 天</option>
                            <option value="90">90 天</option>
                            <option value="365">1 年</option>
                        </select>
                        
                        <label class="inline-flex items-center cursor-pointer bg-white hover:bg-slate-50 px-4 py-2.5 rounded-xl text-sm font-semibold transition-all select-none border border-slate-200 shadow-sm active:scale-95">
                            <input type="checkbox" id="recentFilter" class="sr-only">
                            <div id="checkboxBox" class="w-4 h-4 rounded border-2 border-slate-300 mr-2 flex items-center justify-center transition-all bg-slate-50">
                                <svg id="checkmark" class="w-3 h-3 text-white scale-0 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7"></path></svg>
                            </div>
                            最近
                        </label>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <main class="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 mt-8 space-y-6" id="content">"""]

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
        
        threshold_days = get_abandoned_threshold(tw_history)
        is_abandoned = threshold_days > 0 and days_ago > threshold_days

        if is_abandoned:
            ago_html = f'<span class="text-xs font-medium px-1.5 py-0.5 rounded mt-1 text-white" style="background-color: #6b7280;">疑似棄更 ({days_ago} 天)</span>'
        else:
            status_text = f"已過 {days_ago} 天"
            if threshold_days > 0:
                status_text += f" / 棄更門檻 {threshold_days} 天"

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
        f'<div class="device-card bg-white rounded-3xl p-6 shadow-sm ring-1 ring-gray-900/5 hover:shadow-xl hover:ring-gray-900/10 transition-all duration-300 transform hover:-translate-y-1" data-brand="{device["brand"]}" data-date="{tw_date}">'
        
        f'<div class="flex flex-col sm:flex-row sm:items-start justify-between gap-4 mb-2">'
        f'<div class="flex items-start gap-4">'
        f'<div class="h-12 w-12 rounded-2xl bg-gradient-to-br from-slate-100 to-slate-200 flex items-center justify-center text-slate-700 font-bold text-xl flex-shrink-0 shadow-inner">{device["name"][0]}</div>'
        f'<div>'
        f'<h2 class="text-xl font-bold text-slate-900 leading-tight device-title tracking-tight">{device["name"]}</h2>'
        f'<div class="flex items-center gap-2 mt-1.5">'
        f'<span class="text-[11px] font-mono font-medium text-slate-500 bg-slate-50 px-2 py-1 rounded-lg border border-slate-100 device-code">{device["code"]}</span>'
        f'<span class="text-[11px] font-bold text-slate-500 bg-slate-50 px-2 py-1 rounded-lg border border-slate-100 uppercase tracking-wide">{device["brand"]}</span>'
        f'</div>'
        f'</div>'
        f'</div>'
        
        f'<div class="flex flex-col items-end">'
        f'<div class="flex items-center gap-2">'
        f'<span class="text-xs font-bold text-slate-400 uppercase tracking-wider">更新於</span>'
        f'<span class="text-sm font-bold text-slate-700 bg-slate-50 px-2.5 py-1 rounded-lg border border-slate-100 font-mono">{tw_date}</span>'
        f'</div>'
        f'{ago_html}'
        f'</div>'
        f'</div>'
        
        f'<div class="grid grid-cols-1 lg:grid-cols-2 gap-4 mt-6">'
        f'{tw_card}{gl_card}{others_cards}'
        f'</div>'
        f'</div>'
    )

html_parts.append(f"""
    </main>
    
    <footer class="mt-20 border-t border-slate-200 bg-slate-50">
        <div class="max-w-5xl mx-auto px-4 py-12 text-center">
            <p class="text-slate-500 text-sm font-medium">由 GitHub Actions 自動生成</p>
            <p class="text-slate-400 text-xs mt-2">共追蹤 {len(final_list)} 款機型</p>
        </div>
    </footer>

    <script>
        function toggleHistory(element) {{
            const historyDiv = element.nextElementSibling;
            if (historyDiv) {{
                const isHidden = historyDiv.classList.toggle('hidden');
                element.setAttribute('aria-expanded', !isHidden);
                
                // Add rotation to arrow if exists (optional enhancement)
                // const arrow = element.querySelector('.arrow-icon');
                // if(arrow) arrow.style.transform = isHidden ? 'rotate(0deg)' : 'rotate(180deg)';
            }}
        }}
        
        const searchInput = document.getElementById('searchInput');
        const brandFilter = document.getElementById('brandFilter');
        const recentFilter = document.getElementById('recentFilter');
        const daysFilter = document.getElementById('daysFilter');
        const checkboxBox = document.getElementById('checkboxBox');
        const checkmark = document.getElementById('checkmark');

        function updateCheckboxVisual() {{
            if (recentFilter.checked) {{
                checkboxBox.style.backgroundColor = '#ff6900';
                checkboxBox.style.borderColor = '#ff6900';
                checkmark.classList.remove('scale-0', 'hidden');
                checkmark.classList.add('scale-100');
            }} else {{
                checkboxBox.style.backgroundColor = '#f8fafc';
                checkboxBox.style.borderColor = '#cbd5e1';
                checkmark.classList.add('scale-0', 'hidden');
                checkmark.classList.remove('scale-100');
            }}
        }}

        function filterContent() {{
            const searchText = searchInput.value.toLowerCase().trim();
            const selectedBrand = brandFilter.value;
            const isRecent = recentFilter.checked;
            const recentDaysThreshold = parseInt(daysFilter.value) || 30;
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

                if (matchText && matchBrand && matchRecent) {{
                    card.classList.remove('hidden');
                    card.classList.add('animate-fade-in');
                }} else {{
                    card.classList.add('hidden');
                    card.classList.remove('animate-fade-in');
                }}
            }});
        }}
        
        searchInput.addEventListener('input', filterContent);
        brandFilter.addEventListener('change', filterContent);
        recentFilter.addEventListener('change', function() {{
            updateCheckboxVisual();
            filterContent();
        }});
        daysFilter.addEventListener('change', function() {{
            if (recentFilter.checked) filterContent();
        }});

        // Initialize from URL params
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
                    const daysOptions = Array.from(daysFilter.options);
                    const matchDays = daysOptions.find(opt => opt.value === String(days));
                    if (matchDays) {{
                        daysFilter.value = days;
                    }} else {{
                        const newOption = document.createElement('option');
                        newOption.value = days;
                        newOption.textContent = days + ' 天';
                        daysFilter.appendChild(newOption);
                        daysFilter.value = days;
                    }}
                    recentFilter.checked = true;
                    updateCheckboxVisual();
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

print(f"[OK] Generated {output_file} with {len(final_list)} devices")
