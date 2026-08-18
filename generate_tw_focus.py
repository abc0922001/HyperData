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
                    'aspatch': v.get('aspatch', ''),
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

# === 統計數據 ===
total_devices = len(final_list)
recent_7d = sum(1 for d in final_list if (now_tw - datetime.strptime(d['tw']['latest']['release'], "%Y-%m-%d").replace(tzinfo=tz_tw)).days <= 7)
recent_30d = sum(1 for d in final_list if (now_tw - datetime.strptime(d['tw']['latest']['release'], "%Y-%m-%d").replace(tzinfo=tz_tw)).days <= 30)
brand_count = len(all_brands)

print(f"Collected {total_devices} devices.")

# === 優化 4: 批次生成 HTML (使用 list) ===
# 全域計數器用於產生唯一 ID
_panel_counter = 0

def _next_panel_id():
    global _panel_counter
    _panel_counter += 1
    return f"history-panel-{_panel_counter}"

def generate_history_html(history_list, type_class, panel_id):
    parts = [
        f'<div id="{panel_id}" role="region" aria-label="歷史版本列表" class="hidden mt-3 border-t border-gray-100 dark:border-slate-700 pt-3 animate-fade-in" data-type="{type_class}">',
        '<div class="overflow-x-auto">',
        '<table class="w-full text-xs text-left whitespace-nowrap" role="table">',
        '<thead class="text-gray-400 dark:text-slate-500 font-medium border-b border-gray-50 dark:border-slate-700"><tr>',
        '<th scope="col" class="py-2 pl-2">版本</th><th scope="col" class="py-2">日期</th>',
        '<th scope="col" class="py-2 text-center">間隔</th><th scope="col" class="py-2 text-right">Android</th><th scope="col" class="py-2 text-right pr-2">安全性更新</th>',
        '</tr></thead><tbody class="divide-y divide-gray-50 dark:divide-slate-700/50">'
    ]
    
    for i, rom in enumerate(history_list):
        interval_html = '<span class="text-gray-300 dark:text-slate-600" aria-label="無資料">-</span>'
        
        if i < len(history_list) - 1:
            try:
                current_date = datetime.strptime(rom['release'], "%Y-%m-%d")
                prev_date = datetime.strptime(history_list[i+1]['release'], "%Y-%m-%d")
                delta_days = (current_date - prev_date).days
                
                if delta_days > 90: 
                    bg_color = "bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400"
                elif delta_days < 30: 
                    bg_color = "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400"
                else: 
                    bg_color = "bg-gray-100 text-gray-600 dark:bg-slate-700 dark:text-slate-400"
                    
                interval_html = f'<span class="px-2 py-0.5 rounded-full text-[10px] font-medium {bg_color}">{delta_days} 天</span>'
            except: 
                pass
        else:
            interval_html = '<span class="text-[10px] font-medium text-blue-600 bg-blue-50 dark:text-blue-400 dark:bg-blue-900/30 px-2 py-0.5 rounded-full">首版</span>'

        parts.append(
            f'<tr class="hover:bg-gray-50 dark:hover:bg-slate-700/50 transition-colors">'
            f'<td class="py-2.5 pl-2 font-mono text-gray-700 dark:text-slate-300 font-medium">{rom["os"]}</td>'
            f'<td class="py-2.5 text-gray-500 dark:text-slate-400">{rom["release"]}</td>'
            f'<td class="py-2.5 text-center">{interval_html}</td>'
            f'<td class="py-2.5 text-right text-gray-500 dark:text-slate-400">{rom["android"]}</td>'
            f'<td class="py-2.5 text-right pr-2 text-gray-500 dark:text-slate-400">{rom["aspatch"] or "—"}</td>'
            f'</tr>'
        )
    
    parts.append('</tbody></table></div></div>')
    return ''.join(parts)

def generate_card_html(info, region_label, region_type, tw_ver_str=None):
    if not info:
        if region_type == 'global':
            return (
                '<div class="flex items-center justify-center p-4 rounded-xl border border-dashed border-gray-200 dark:border-slate-700 bg-gray-50/50 dark:bg-slate-800/50 h-[104px]">'
                '<span class="text-xs text-gray-400 dark:text-slate-500 font-medium italic">無國際版資料</span>'
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
            ver_status_tag = '<span class="text-[10px] font-bold px-2 py-0.5 rounded-full text-green-700 bg-green-100 border border-green-200 shadow-sm dark:text-green-400 dark:bg-green-900/30 dark:border-green-800" role="status">領先</span>'
        elif tw_tup > curr_tup:
            ver_status_tag = '<span class="text-[10px] font-bold px-2 py-0.5 rounded-full text-rose-700 bg-rose-100 border border-rose-200 shadow-sm dark:text-rose-400 dark:bg-rose-900/30 dark:border-rose-800" role="status">落後</span>'
        else:
            ver_status_tag = '<span class="text-[10px] font-bold px-2 py-0.5 rounded-full text-gray-600 bg-gray-100 border border-gray-200 dark:text-slate-400 dark:bg-slate-700 dark:border-slate-600" role="status">同步</span>'

    # Style Configuration
    styles = {
        'tw': (
            'bg-gradient-to-br from-blue-50 to-white dark:from-blue-950/40 dark:to-slate-800',
            'border-blue-100 dark:border-blue-800/50',
            'bg-blue-100 dark:bg-blue-900/40', 'text-blue-700 dark:text-blue-400',
            'hover:border-blue-300 dark:hover:border-blue-700', 'group/tw'
        ),
        'global': (
            'bg-white dark:bg-slate-800',
            'border-gray-200 dark:border-slate-700',
            'bg-gray-100 dark:bg-slate-700', 'text-gray-600 dark:text-slate-400',
            'hover:border-gray-300 dark:hover:border-slate-600', 'group/gl'
        ),
        'other': (
            'bg-purple-50/30 dark:bg-purple-950/20',
            'border-purple-100 dark:border-purple-800/40',
            'bg-purple-100 dark:bg-purple-900/40', 'text-purple-700 dark:text-purple-400',
            'hover:border-purple-300 dark:hover:border-purple-700', 'group/ot'
        )
    }
    bg_color, border_color, badge_bg, badge_text, hover_border, group_class = styles[region_type]

    panel_id = _next_panel_id()
    history_html = generate_history_html(info['history'], f'{region_type}-history', panel_id)
    
    # Calculate Days Ago
    ago_html = ""
    try:
        dt = datetime.strptime(latest['release'], "%Y-%m-%d").replace(tzinfo=tz_tw)
        days = (now_tw - dt).days
        ago_html = f'<div class="text-[10px] text-gray-500 dark:text-slate-500 font-medium mt-1">({days} 天前)</div>'
    except: 
        pass

    return (
        f'<div class="{group_class} relative">'
        f'<button type="button" onclick="toggleHistory(this)" aria-expanded="false" aria-controls="{panel_id}" '
        f'class="w-full text-left cursor-pointer flex flex-col p-4 rounded-xl {bg_color} border {border_color} {hover_border} transition-all duration-200 shadow-sm hover:shadow-md dark:shadow-none dark:hover:shadow-lg dark:hover:shadow-black/10 relative select-none focus:outline-none focus:ring-2 focus:ring-blue-500/30 dark:focus:ring-blue-400/30">'
        
        f'<div class="flex items-center justify-between w-full mb-2">'
        f'<span class="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wide {badge_bg} {badge_text}">{region_label}</span>'
        f'{ver_status_tag}'
        f'</div>'
        
        f'<div class="flex items-end justify-between w-full">'
        f'<div>'
        f'<div class="text-sm font-mono text-gray-900 dark:text-slate-100 font-bold tracking-tight">{ver_str}</div>'
        f'<div class="text-[10px] text-gray-500 dark:text-slate-500 font-medium mt-0.5">Android {latest["android"]}</div>'
        f'<div class="text-[10px] text-gray-500 dark:text-slate-500 font-medium mt-0.5">安全性更新：{latest["aspatch"] or "—"}</div>'
        f'</div>'
        
        f'<div class="flex flex-col items-end">'
        f'<div class="flex items-center gap-1.5">'
        f'<div class="text-xs font-semibold text-gray-700 dark:text-slate-300">{latest["release"]}</div>'
        f'<svg class="w-3.5 h-3.5 text-gray-400 dark:text-slate-500 transition-transform duration-200 arrow-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M19 9l-7 7-7-7"/></svg>'
        f'</div>'
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
    <title>小米 HyperOS 台灣版更新追蹤 | HyperOS Tracker</title>
    <meta name="description" content="追蹤小米 HyperOS 台灣版最新 ROM 更新，涵蓋 Xiaomi、Redmi、POCO 等 {total_devices} 款機型的版本記錄、更新間隔與全球版本比較。">
    <meta name="keywords" content="HyperOS, 小米, Xiaomi, Redmi, POCO, 台灣, ROM, 更新, OTA, firmware">

    <!-- Open Graph -->
    <meta property="og:type" content="website">
    <meta property="og:title" content="小米 HyperOS 台灣版更新追蹤">
    <meta property="og:description" content="追蹤 {total_devices} 款小米機型的 HyperOS 台灣版 ROM 更新狀態。">
    <meta property="og:url" content="https://hyperos.fans/tw.html">
    <meta property="og:site_name" content="HyperOS Tracker">
    <meta property="og:locale" content="zh_TW">

    <!-- Twitter Card -->
    <meta name="twitter:card" content="summary">
    <meta name="twitter:title" content="小米 HyperOS 台灣版更新追蹤">
    <meta name="twitter:description" content="追蹤 {total_devices} 款小米機型的 HyperOS 台灣版 ROM 更新狀態。">

    <link rel="canonical" href="https://hyperos.fans/tw.html">
    <meta name="theme-color" content="#ff6900" media="(prefers-color-scheme: light)">
    <meta name="theme-color" content="#0f172a" media="(prefers-color-scheme: dark)">

    <!-- Preload critical resources -->
    <link rel="preload" href="assets/css/tw.css" as="style">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link rel="dns-prefetch" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="assets/css/tw.css">

    <!-- JSON-LD Structured Data -->
    <script type="application/ld+json">
    {{
        "@context": "https://schema.org",
        "@type": "WebApplication",
        "name": "HyperOS Tracker — 台灣版更新追蹤",
        "url": "https://hyperos.fans/tw.html",
        "description": "追蹤小米 HyperOS 台灣版 ROM 更新，涵蓋 {total_devices} 款機型。",
        "applicationCategory": "UtilitiesApplication",
        "operatingSystem": "Web",
        "inLanguage": "zh-TW",
        "dateModified": "{now_tw.strftime('%Y-%m-%d')}",
        "offers": {{
            "@type": "Offer",
            "price": "0",
            "priceCurrency": "TWD"
        }}
    }}
    </script>
</head>
<body class="bg-slate-50 dark:bg-slate-900 text-slate-800 dark:text-slate-200 antialiased min-h-screen pb-20 selection:bg-orange-100 selection:text-orange-900 dark:selection:bg-orange-900/40 dark:selection:text-orange-200 transition-colors duration-300">
    <a href="#content" class="sr-only focus:not-sr-only focus:absolute focus:z-[60] focus:p-4 focus:bg-white dark:focus:bg-slate-800 focus:text-blue-600 dark:focus:text-blue-400 focus:ring-2 focus:ring-blue-500 rounded-lg m-4">跳至主要內容</a>
    
    <header class="sticky top-0 z-50 glass-header transition-all duration-300" role="banner">
        <div class="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
            <div class="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div class="flex items-center gap-3">
                    <div class="h-10 w-10 bg-gradient-to-br from-orange-500 to-red-500 rounded-xl flex items-center justify-center text-white font-bold shadow-lg shadow-orange-500/20" aria-hidden="true">
                        <svg class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
                    </div>
                    <div>
                        <h1 class="text-xl font-bold text-slate-900 dark:text-white tracking-tight leading-none">HyperOS <span class="text-mi-orange">Tracker</span></h1>
                        <p class="text-xs text-slate-500 dark:text-slate-400 mt-1 font-medium">
                            <time datetime="{now_tw.strftime('%Y-%m-%dT%H:%M')}">{gen_time}</time> (UTC+8)
                        </p>
                    </div>
                </div>
                
                <div class="flex items-center gap-2">
                    <!-- Dark mode toggle -->
                    <button type="button" id="themeToggle" aria-label="切換深色模式"
                        class="p-2.5 rounded-xl bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-600 dark:text-slate-300 transition-all border border-transparent hover:border-slate-200 dark:hover:border-slate-600 focus:outline-none focus:ring-2 focus:ring-blue-500/30">
                        <svg id="themeIconSun" class="w-5 h-5 hidden" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"/></svg>
                        <svg id="themeIconMoon" class="w-5 h-5 hidden" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z"/></svg>
                    </button>
                </div>
            </div>

            <nav class="mt-4" aria-label="篩選選項" role="search">
                <div class="flex flex-col sm:flex-row gap-2 w-full">
                    <div class="relative flex-grow sm:max-w-xs group">
                        <label for="searchInput" class="sr-only">搜尋機型名稱或代號</label>
                        <input type="search" id="searchInput" autocomplete="off"
                            class="w-full bg-slate-100/50 dark:bg-slate-800/50 hover:bg-slate-100 dark:hover:bg-slate-800 focus:bg-white dark:focus:bg-slate-800 text-slate-700 dark:text-slate-200 py-2.5 pl-10 pr-4 rounded-xl text-sm font-medium focus:outline-none focus:ring-2 focus:ring-blue-500/20 dark:focus:ring-blue-400/20 focus:border-blue-500 dark:focus:border-blue-400 transition-all border border-transparent focus:shadow-sm placeholder-slate-400 dark:placeholder-slate-500" 
                            placeholder="搜尋機型...">
                        <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400 group-focus-within:text-blue-500 dark:group-focus-within:text-blue-400 transition-colors" aria-hidden="true">
                            <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path></svg>
                        </div>
                    </div>
                    
                    <div class="flex gap-2 overflow-x-auto pb-1 sm:pb-0 no-scrollbar">
                        <label for="brandFilter" class="sr-only">品牌篩選</label>
                        <select id="brandFilter" class="bg-white dark:bg-slate-800 hover:bg-slate-50 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 py-2.5 px-4 pr-8 rounded-xl text-sm font-semibold focus:outline-none focus:ring-2 focus:ring-blue-500/20 dark:focus:ring-blue-400/20 border border-slate-200 dark:border-slate-700 cursor-pointer transition-all shadow-sm">
                            {brand_options}
                        </select>
                        
                        <label for="daysFilter" class="sr-only">時間範圍篩選</label>
                        <select id="daysFilter" class="bg-white dark:bg-slate-800 hover:bg-slate-50 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 py-2.5 px-4 pr-8 rounded-xl text-sm font-semibold focus:outline-none focus:ring-2 focus:ring-blue-500/20 dark:focus:ring-blue-400/20 border border-slate-200 dark:border-slate-700 cursor-pointer transition-all shadow-sm">
                            <option value="7">7 天</option>
                            <option value="14">14 天</option>
                            <option value="30" selected>30 天</option>
                            <option value="60">60 天</option>
                            <option value="90">90 天</option>
                            <option value="365">1 年</option>
                        </select>
                        
                        <label class="inline-flex items-center cursor-pointer bg-white dark:bg-slate-800 hover:bg-slate-50 dark:hover:bg-slate-700 px-4 py-2.5 rounded-xl text-sm font-semibold transition-all select-none border border-slate-200 dark:border-slate-700 shadow-sm active:scale-95">
                            <input type="checkbox" id="recentFilter" class="sr-only">
                            <div id="checkboxBox" class="w-4 h-4 rounded border-2 border-slate-300 dark:border-slate-600 mr-2 flex items-center justify-center transition-all bg-slate-50 dark:bg-slate-700" aria-hidden="true">
                                <svg id="checkmark" class="w-3 h-3 text-white scale-0 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7"></path></svg>
                            </div>
                            <span class="text-slate-700 dark:text-slate-200">最近</span>
                        </label>
                    </div>
                </div>
            </nav>
        </div>
    </header>

    <!-- Stats Bar -->
    <div class="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 mt-6">
        <div class="grid grid-cols-2 sm:grid-cols-4 gap-3" role="region" aria-label="統計摘要">
            <div class="bg-white dark:bg-slate-800 rounded-2xl p-4 ring-1 ring-gray-900/5 dark:ring-slate-700/50 shadow-sm">
                <div class="text-2xl font-bold text-slate-900 dark:text-white">{total_devices}</div>
                <div class="text-xs text-slate-500 dark:text-slate-400 font-medium mt-0.5">追蹤機型</div>
            </div>
            <div class="bg-white dark:bg-slate-800 rounded-2xl p-4 ring-1 ring-gray-900/5 dark:ring-slate-700/50 shadow-sm">
                <div class="text-2xl font-bold text-green-600 dark:text-green-400">{recent_7d}</div>
                <div class="text-xs text-slate-500 dark:text-slate-400 font-medium mt-0.5">7 天內更新</div>
            </div>
            <div class="bg-white dark:bg-slate-800 rounded-2xl p-4 ring-1 ring-gray-900/5 dark:ring-slate-700/50 shadow-sm">
                <div class="text-2xl font-bold text-blue-600 dark:text-blue-400">{recent_30d}</div>
                <div class="text-xs text-slate-500 dark:text-slate-400 font-medium mt-0.5">30 天內更新</div>
            </div>
            <div class="bg-white dark:bg-slate-800 rounded-2xl p-4 ring-1 ring-gray-900/5 dark:ring-slate-700/50 shadow-sm">
                <div class="text-2xl font-bold text-mi-orange">{brand_count}</div>
                <div class="text-xs text-slate-500 dark:text-slate-400 font-medium mt-0.5">品牌數</div>
            </div>
        </div>
    </div>

    <!-- Live region for filter results -->
    <div id="filterStatus" class="sr-only" aria-live="polite" aria-atomic="true"></div>

    <main class="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 mt-6 space-y-6" id="content" role="main">"""]

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
            ago_html = f'<span class="text-xs font-medium px-1.5 py-0.5 rounded mt-1 text-white" style="background-color: #6b7280;" role="status" aria-label="疑似棄更，已 {days_ago} 天未更新">疑似棄更 ({days_ago} 天)</span>'
        else:
            status_text = f"已過 {days_ago} 天"
            if threshold_days > 0:
                status_text += f" / 棄更門檻 {threshold_days} 天"

            if days_ago > 90: 
                ago_color = "text-orange-700 bg-orange-50 dark:text-orange-400 dark:bg-orange-900/30"
            elif days_ago > 30: 
                ago_color = "text-gray-600 bg-gray-100 dark:text-slate-400 dark:bg-slate-700"
            else: 
                ago_color = "text-green-700 bg-green-50 dark:text-green-400 dark:bg-green-900/30"
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
        f'<article class="device-card bg-white dark:bg-slate-800 rounded-3xl p-6 shadow-sm ring-1 ring-gray-900/5 dark:ring-slate-700/50 hover:shadow-xl dark:hover:shadow-lg dark:hover:shadow-black/20 hover:ring-gray-900/10 dark:hover:ring-slate-600/50 transition-all duration-300 transform hover:-translate-y-1" data-brand="{device["brand"]}" data-date="{tw_date}" aria-label="{device["name"]} 更新資訊">'
        
        f'<div class="flex flex-col sm:flex-row sm:items-start justify-between gap-4 mb-2">'
        f'<div class="flex items-start gap-4">'
        f'<div class="h-12 w-12 rounded-2xl bg-gradient-to-br from-slate-100 to-slate-200 dark:from-slate-700 dark:to-slate-600 flex items-center justify-center text-slate-700 dark:text-slate-200 font-bold text-xl flex-shrink-0 shadow-inner" aria-hidden="true">{device["name"][0]}</div>'
        f'<div>'
        f'<h2 class="text-xl font-bold text-slate-900 dark:text-white leading-tight device-title tracking-tight">{device["name"]}</h2>'
        f'<div class="flex items-center gap-2 mt-1.5">'
        f'<span class="text-[11px] font-mono font-medium text-slate-500 dark:text-slate-400 bg-slate-50 dark:bg-slate-700 px-2 py-1 rounded-lg border border-slate-100 dark:border-slate-600 device-code">{device["code"]}</span>'
        f'<span class="text-[11px] font-bold text-slate-500 dark:text-slate-400 bg-slate-50 dark:bg-slate-700 px-2 py-1 rounded-lg border border-slate-100 dark:border-slate-600 uppercase tracking-wide">{device["brand"]}</span>'
        f'</div>'
        f'</div>'
        f'</div>'
        
        f'<div class="flex flex-col items-end">'
        f'<div class="flex items-center gap-2">'
        f'<span class="text-xs font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider">更新於</span>'
        f'<time datetime="{tw_date}" class="text-sm font-bold text-slate-700 dark:text-slate-300 bg-slate-50 dark:bg-slate-700 px-2.5 py-1 rounded-lg border border-slate-100 dark:border-slate-600 font-mono">{tw_date}</time>'
        f'</div>'
        f'{ago_html}'
        f'</div>'
        f'</div>'
        
        f'<div class="grid grid-cols-1 lg:grid-cols-2 gap-4 mt-6">'
        f'{tw_card}{gl_card}{others_cards}'
        f'</div>'
        f'</article>'
    )

html_parts.append(f"""
    </main>
    
    <!-- Empty state (hidden by default) -->
    <div id="emptyState" class="hidden max-w-5xl mx-auto px-4 py-20 text-center">
        <svg class="mx-auto h-16 w-16 text-slate-300 dark:text-slate-600" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
        </svg>
        <h3 class="mt-4 text-lg font-semibold text-slate-700 dark:text-slate-300">找不到符合的機型</h3>
        <p class="mt-2 text-sm text-slate-500 dark:text-slate-400">請嘗試調整搜尋條件或篩選設定</p>
    </div>

    <!-- Back to top button -->
    <button type="button" id="backToTop" class="back-to-top" aria-label="回到頂部">
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M5 15l7-7 7 7"/></svg>
    </button>
    
    <footer class="mt-20 border-t border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900" role="contentinfo">
        <div class="max-w-5xl mx-auto px-4 py-12 text-center">
            <p class="text-slate-500 dark:text-slate-400 text-sm font-medium">由 GitHub Actions 自動生成</p>
            <p class="text-slate-400 dark:text-slate-500 text-xs mt-2">共追蹤 {total_devices} 款機型</p>
        </div>
    </footer>

    <script>
        /* === Theme Toggle === */
        (function() {{
            const html = document.documentElement;
            const toggle = document.getElementById('themeToggle');
            const iconSun = document.getElementById('themeIconSun');
            const iconMoon = document.getElementById('themeIconMoon');

            function applyTheme(theme) {{
                if (theme === 'dark') {{
                    html.classList.add('dark');
                    iconSun.classList.remove('hidden');
                    iconMoon.classList.add('hidden');
                }} else {{
                    html.classList.remove('dark');
                    iconSun.classList.add('hidden');
                    iconMoon.classList.remove('hidden');
                }}
            }}

            // Initialize: check localStorage, then system preference
            const saved = localStorage.getItem('theme');
            if (saved) {{
                applyTheme(saved);
            }} else if (window.matchMedia('(prefers-color-scheme: dark)').matches) {{
                applyTheme('dark');
            }} else {{
                applyTheme('light');
            }}

            // Listen for system changes
            window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', e => {{
                if (!localStorage.getItem('theme')) {{
                    applyTheme(e.matches ? 'dark' : 'light');
                }}
            }});

            toggle.addEventListener('click', () => {{
                const isDark = html.classList.contains('dark');
                const next = isDark ? 'light' : 'dark';
                localStorage.setItem('theme', next);
                applyTheme(next);
            }});
        }})();

        /* === History Toggle === */
        function toggleHistory(element) {{
            const historyDiv = element.nextElementSibling;
            if (historyDiv) {{
                const isHidden = historyDiv.classList.toggle('hidden');
                element.setAttribute('aria-expanded', !isHidden);
                const arrow = element.querySelector('.arrow-icon');
                if (arrow) arrow.style.transform = isHidden ? 'rotate(0deg)' : 'rotate(180deg)';
            }}
        }}
        
        /* === Filter Logic === */
        const searchInput = document.getElementById('searchInput');
        const brandFilter = document.getElementById('brandFilter');
        const recentFilter = document.getElementById('recentFilter');
        const daysFilter = document.getElementById('daysFilter');
        const checkboxBox = document.getElementById('checkboxBox');
        const checkmark = document.getElementById('checkmark');
        const emptyState = document.getElementById('emptyState');
        const filterStatus = document.getElementById('filterStatus');

        function updateCheckboxVisual() {{
            if (recentFilter.checked) {{
                checkboxBox.style.backgroundColor = '#ff6900';
                checkboxBox.style.borderColor = '#ff6900';
                checkmark.classList.remove('scale-0', 'hidden');
                checkmark.classList.add('scale-100');
            }} else {{
                checkboxBox.style.backgroundColor = '';
                checkboxBox.style.borderColor = '';
                checkmark.classList.add('scale-0', 'hidden');
                checkmark.classList.remove('scale-100');
            }}
        }}

        function filterContent() {{
            requestAnimationFrame(() => {{
                const searchText = searchInput.value.toLowerCase().trim();
                const selectedBrand = brandFilter.value;
                const isRecent = recentFilter.checked;
                const recentDaysThreshold = parseInt(daysFilter.value) || 30;
                const cards = document.querySelectorAll('.device-card');
                const now = new Date();
                let visibleCount = 0;

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
                        visibleCount++;
                    }} else {{
                        card.classList.add('hidden');
                        card.classList.remove('animate-fade-in');
                    }}
                }});

                // Empty state
                if (visibleCount === 0 && (searchText || selectedBrand !== 'all' || isRecent)) {{
                    emptyState.classList.remove('hidden');
                }} else {{
                    emptyState.classList.add('hidden');
                }}

                // Announce to screen readers
                filterStatus.textContent = visibleCount === cards.length
                    ? ''
                    : `顯示 ${{visibleCount}} / ${{cards.length}} 款機型`;
            }});
        }}
        
        // Debounced search
        let searchTimer = null;
        searchInput.addEventListener('input', () => {{
            clearTimeout(searchTimer);
            searchTimer = setTimeout(filterContent, 300);
        }});
        brandFilter.addEventListener('change', filterContent);
        recentFilter.addEventListener('change', function() {{
            updateCheckboxVisual();
            filterContent();
        }});
        daysFilter.addEventListener('change', function() {{
            if (recentFilter.checked) filterContent();
        }});

        /* === URL Params Initialization === */
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

        /* === Back to Top === */
        const backToTop = document.getElementById('backToTop');
        let ticking = false;
        window.addEventListener('scroll', () => {{
            if (!ticking) {{
                requestAnimationFrame(() => {{
                    if (window.scrollY > 300) {{
                        backToTop.classList.add('visible');
                    }} else {{
                        backToTop.classList.remove('visible');
                    }}
                    ticking = false;
                }});
                ticking = true;
            }}
        }}, {{ passive: true }});

        backToTop.addEventListener('click', () => {{
            window.scrollTo({{ top: 0, behavior: 'smooth' }});
        }});
    </script>
</body>
</html>
""")


# 一次性寫入
with open(output_file, 'w', encoding='utf-8') as f:
    f.write(''.join(html_parts))

print(f"[OK] Generated {output_file} with {total_devices} devices")
