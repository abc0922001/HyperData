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
images_dir = os.path.join('assets', 'images')
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
    "土耳其": "土耳其", "韩国": "韓國", "泰国": "泰國",
    "危地马拉": "瓜地馬拉", "秘鲁": "秘魯",
    "中国大陆": "中國", "中国": "中國", "大陆": "中國",
    "国际": "國際", "演示机": "演示機", "系统": "系統",
    "运营商": "電信商", "定制": "客製",
    "政企标准": "政企標準", "政企": "政企",
    "体验增强": "體驗增強", "开发者": "開發者", "预览": "預覽",
    "每日构建": "每日建置"
}

def get_region_label(branch_name_zh):
    name = branch_name_zh.replace("小米澎湃 OS ", "")
    if name == "正式版": return "中國"
    if name == "开发版": return "開發版"
    if name == "Beta": return "Beta"
    
    core_name = name.replace("正式版", "").replace("版本", "").replace("版", "").strip()
    if core_name in REGION_MAPPING:
        return REGION_MAPPING[core_name]
    if core_name in ("EEA", "欧洲EEA"): return "歐洲 EEA"

    processed_name = core_name
    for sc, tc in REGION_MAPPING.items():
        processed_name = processed_name.replace(sc, tc)
    return processed_name

DEVICE_NAME_MAPPING = {
    "国际": "國際", "电竞": "電競", "极速": "極速",
    "游戏": "遊戲", "增强": "增強", "纪念": "紀念",
    "天玑": "天璣", "钛金属": "鈦金屬", "卫星通讯": "衛星通訊",
    "后排": "後排", "移动": "移動", "控制屏": "控制螢幕",
    "智能座舱": "智慧座艙", "标准": "標準", "长焦": "長焦",
    "闪充": "閃充", "冠军": "冠軍", "骁龙": "驍龍"
}

def get_device_name(name_zh):
    for sc, tc in DEVICE_NAME_MAPPING.items():
        name_zh = name_zh.replace(sc, tc)
    return name_zh

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
        
        device_name = get_device_name(data.get('name', {}).get('zh', 'Unknown Device'))
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

# 全域計數器與歷史資料儲存
_panel_counter = 0
rom_history_store = {}

def _next_panel_id():
    global _panel_counter
    _panel_counter += 1
    return f"p{_panel_counter}"

def register_history(history_list):
    pid = _next_panel_id()
    # 壓縮為陣列格式: [os, release, android, aspatch]
    rom_history_store[pid] = [
        [r['os'], r['release'], r['android'], r['aspatch']]
        for r in history_list
    ]
    return pid

def generate_card_html(info, region_label, region_type, tw_ver_str=None):
    if not info:
        if region_type == 'global':
            return (
                '<div class="flex items-center justify-center p-4 rounded-xl border border-dashed border-slate-200 dark:border-slate-700 bg-slate-50/50 dark:bg-slate-800/50 min-h-[6.5rem]">'
                '<span class="text-xs text-slate-500 dark:text-slate-400 font-medium italic">無國際版資料</span>'
                '</div>'
            )
        return ""

    latest = info['latest']
    ver_str = latest['os']
    panel_id = register_history(info['history'])
    
    # Version Comparison Logic
    ver_status_tag = ""
    if region_type != 'tw' and tw_ver_str:
        tw_tup = version_to_tuple(tw_ver_str)
        curr_tup = version_to_tuple(ver_str)
        if tw_tup < curr_tup:
            ver_status_tag = '<span class="text-[0.625rem] font-bold px-2 py-0.5 rounded-full text-emerald-800 bg-emerald-100 border border-emerald-200 shadow-sm dark:text-emerald-300 dark:bg-emerald-950/60 dark:border-emerald-800" role="status">領先</span>'
        elif tw_tup > curr_tup:
            ver_status_tag = '<span class="text-[0.625rem] font-bold px-2 py-0.5 rounded-full text-rose-800 bg-rose-100 border border-rose-200 shadow-sm dark:text-rose-300 dark:bg-rose-950/60 dark:border-rose-800" role="status">落後</span>'
        else:
            ver_status_tag = '<span class="text-[0.625rem] font-bold px-2 py-0.5 rounded-full text-slate-700 bg-slate-100 border border-slate-200 dark:text-slate-200 dark:bg-slate-700 dark:border-slate-600" role="status">同步</span>'

    # Style Configuration with WCAG AA compliant contrast ratios
    styles = {
        'tw': (
            'bg-gradient-to-br from-blue-50 to-white dark:from-blue-950/40 dark:to-slate-800',
            'border-blue-200 dark:border-blue-800/50',
            'bg-blue-100 dark:bg-blue-900/60', 'text-blue-800 dark:text-blue-300',
            'hover:border-blue-300 dark:hover:border-blue-700', 'group/tw'
        ),
        'global': (
            'bg-white dark:bg-slate-800',
            'border-slate-200 dark:border-slate-700',
            'bg-slate-100 dark:bg-slate-700', 'text-slate-700 dark:text-slate-200',
            'hover:border-slate-300 dark:hover:border-slate-600', 'group/gl'
        ),
        'other': (
            'bg-purple-50/30 dark:bg-purple-950/20',
            'border-purple-200 dark:border-purple-800/40',
            'bg-purple-100 dark:bg-purple-900/60', 'text-purple-800 dark:text-purple-300',
            'hover:border-purple-300 dark:hover:border-purple-700', 'group/ot'
        )
    }
    bg_color, border_color, badge_bg, badge_text, hover_border, group_class = styles[region_type]

    # Calculate Days Ago
    ago_html = ""
    try:
        dt = datetime.strptime(latest['release'], "%Y-%m-%d").replace(tzinfo=tz_tw)
        days = (now_tw - dt).days
        ago_html = f'<div class="text-[0.625rem] text-slate-600 dark:text-slate-300 font-medium mt-1 tabular-nums">({days} 天前)</div>'
    except: 
        pass

    return (
        f'<div class="{group_class} relative">'
        f'<button type="button" data-history-toggle aria-expanded="false" aria-controls="{panel_id}" '
        f'class="w-full text-left cursor-pointer flex flex-col p-4 rounded-xl {bg_color} border {border_color} {hover_border} transition-all duration-200 shadow-sm hover:shadow-md dark:shadow-none dark:hover:shadow-lg dark:hover:shadow-black/10 relative select-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 dark:focus-visible:ring-blue-400">'
        
        f'<div class="flex items-center justify-between w-full mb-2">'
        f'<span class="inline-flex items-center px-2 py-0.5 rounded text-[0.625rem] font-bold uppercase tracking-wide {badge_bg} {badge_text}">{region_label}</span>'
        f'{ver_status_tag}'
        f'</div>'
        
        f'<div class="flex items-end justify-between w-full">'
        f'<div>'
        f'<div class="text-sm font-mono tabular-nums text-slate-900 dark:text-slate-100 font-bold tracking-tight">{ver_str}</div>'
        f'<div class="text-[0.625rem] text-slate-600 dark:text-slate-300 font-medium mt-0.5">Android {latest["android"]}</div>'
        f'<div class="text-[0.625rem] text-slate-600 dark:text-slate-300 font-medium mt-0.5">安全性更新：{latest["aspatch"] or "—"}</div>'
        f'</div>'
        
        f'<div class="flex flex-col items-end">'
        f'<div class="flex items-center gap-1.5">'
        f'<div class="text-xs font-semibold tabular-nums text-slate-700 dark:text-slate-200">{latest["release"]}</div>'
        f'<svg class="w-3.5 h-3.5 text-slate-500 dark:text-slate-400 transition-transform duration-200 arrow-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M19 9l-7 7-7-7"/></svg>'
        f'</div>'
        f'{ago_html}'
        f'</div>'
        f'</div>'
        
        f'</button>'
        f'<div id="{panel_id}" role="region" aria-label="{region_label} 歷史版本列表" class="hidden mt-3 border-t border-slate-200 dark:border-slate-700 pt-3 animate-fade-in" data-type="{region_type}-history"></div>'
        f'</div>'
    )

# === 主 HTML 結構 ===
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
    <meta name="color-scheme" content="light dark">
    <script>
        (function() {{
            try {{
                const saved = localStorage.getItem('theme');
                const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
                const isDark = saved === 'dark' || (!saved && prefersDark);
                document.documentElement.classList.toggle('dark', isDark);
                document.querySelector('meta[name="color-scheme"]').content = saved || 'light dark';
            }} catch (e) {{}}
        }})();
    </script>
    <meta name="text-scale" content="scale">
    <meta name="theme-color" content="#ff6900" media="(prefers-color-scheme: light)">
    <meta name="theme-color" content="#0f172a" media="(prefers-color-scheme: dark)">

    <!-- Font optimization: Preconnect and asynchronous stylesheet loading to avoid render blocking -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link rel="preload" as="style" href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap">
    <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" media="print" onload="this.media='all'">
    <noscript>
        <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap">
    </noscript>

    <!-- Critical CSS -->
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
    <a href="#content" class="sr-only focus:not-sr-only focus:absolute focus:z-[60] focus:p-4 focus:bg-white dark:focus:bg-slate-800 focus:text-blue-700 dark:focus:text-blue-300 focus:ring-2 focus:ring-blue-500 rounded-lg m-4">跳至主要內容</a>
    
    <header class="sticky top-0 z-50 glass-header transition-all duration-300">
        <div class="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
            <div class="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div class="flex items-center gap-3">
                    <div class="h-10 w-10 bg-gradient-to-br from-orange-500 to-red-500 rounded-xl flex items-center justify-center text-white font-bold shadow-lg shadow-orange-500/20" aria-hidden="true">
                        <svg class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
                    </div>
                    <div>
                        <h1 class="text-xl font-bold text-slate-900 dark:text-white tracking-tight leading-none">HyperOS <span class="text-mi-orange">Tracker</span></h1>
                        <p class="text-xs text-slate-600 dark:text-slate-300 mt-1 font-medium tabular-nums">
                            <time datetime="{now_tw.strftime('%Y-%m-%dT%H:%M')}">{gen_time}</time> (UTC+8)
                        </p>
                    </div>
                </div>
                
                <div class="flex items-center gap-2">
                    <!-- Dark mode toggle -->
                    <button type="button" id="themeToggle" aria-label="切換深色模式"
                        class="min-h-[44px] min-w-[44px] flex items-center justify-center p-2.5 rounded-xl bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 transition-all border border-slate-200 dark:border-slate-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 dark:focus-visible:ring-blue-400">
                        <svg id="themeIconSun" class="w-5 h-5 hidden" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"/></svg>
                        <svg id="themeIconMoon" class="w-5 h-5 hidden" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z"/></svg>
                    </button>
                </div>
            </div>

            <search class="mt-4 block" aria-label="機型搜尋與篩選">
                <div class="flex flex-col sm:flex-row gap-2 w-full">
                    <div class="relative flex-grow sm:max-w-xs group">
                        <label for="searchInput" class="sr-only">搜尋機型名稱或代號</label>
                        <input type="search" id="searchInput" autocomplete="off"
                            class="w-full min-h-[44px] bg-slate-100 dark:bg-slate-800/80 hover:bg-slate-200/60 dark:hover:bg-slate-800 focus:bg-white dark:focus:bg-slate-800 text-slate-800 dark:text-slate-100 py-2.5 pl-10 pr-4 rounded-xl text-sm font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 dark:focus-visible:ring-blue-400 focus:border-blue-500 dark:focus:border-blue-400 transition-all border border-slate-200 dark:border-slate-700 focus:shadow-sm placeholder-slate-500 dark:placeholder-slate-400" 
                            placeholder="搜尋機型...">
                        <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-500 dark:text-slate-400 group-focus-within:text-blue-600 dark:group-focus-within:text-blue-400 transition-colors" aria-hidden="true">
                            <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path></svg>
                        </div>
                    </div>
                    
                    <div class="flex gap-2 overflow-x-auto pb-1 sm:pb-0 no-scrollbar">
                        <label for="brandFilter" class="sr-only">品牌篩選</label>
                        <select id="brandFilter" class="min-h-[44px] bg-white dark:bg-slate-800 hover:bg-slate-50 dark:hover:bg-slate-700 text-slate-800 dark:text-slate-100 py-2.5 px-4 pr-8 rounded-xl text-sm font-semibold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 dark:focus-visible:ring-blue-400 border border-slate-300 dark:border-slate-600 cursor-pointer transition-all shadow-sm">
                            {brand_options}
                        </select>
                        
                        <label for="daysFilter" class="sr-only">時間範圍篩選</label>
                        <select id="daysFilter" class="min-h-[44px] bg-white dark:bg-slate-800 hover:bg-slate-50 dark:hover:bg-slate-700 text-slate-800 dark:text-slate-100 py-2.5 px-4 pr-8 rounded-xl text-sm font-semibold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 dark:focus-visible:ring-blue-400 border border-slate-300 dark:border-slate-600 cursor-pointer transition-all shadow-sm">
                            <option value="7">7 天</option>
                            <option value="14">14 天</option>
                            <option value="30" selected>30 天</option>
                            <option value="60">60 天</option>
                            <option value="90">90 天</option>
                            <option value="365">1 年</option>
                        </select>
                        
                        <label for="recentFilter" class="min-h-[44px] inline-flex items-center cursor-pointer bg-white dark:bg-slate-800 hover:bg-slate-50 dark:hover:bg-slate-700 px-4 py-2.5 rounded-xl text-sm font-semibold transition-all select-none border border-slate-300 dark:border-slate-600 shadow-sm active:scale-95">
                            <input type="checkbox" id="recentFilter" class="sr-only peer">
                            <span id="checkboxBox" class="w-4 h-4 rounded border-2 border-slate-400 dark:border-slate-500 mr-2 flex items-center justify-center transition-all bg-slate-100 dark:bg-slate-700 peer-checked:bg-mi-orange peer-checked:border-mi-orange peer-focus-visible:ring-2 peer-focus-visible:ring-blue-500 dark:peer-focus-visible:ring-blue-400 peer-focus-visible:ring-offset-2 peer-checked:[&>svg]:scale-100" aria-hidden="true">
                                <svg id="checkmark" class="w-3 h-3 text-white scale-0 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7"></path></svg>
                            </span>
                            <span class="text-slate-800 dark:text-slate-100">最近</span>
                        </label>
                    </div>
                </div>
            </search>
        </div>
    </header>

    <!-- Stats Bar -->
    <div id="statsBar" class="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 mt-6">
        <div class="grid grid-cols-2 sm:grid-cols-4 gap-3" role="region" aria-label="統計摘要">
            <div class="bg-white dark:bg-slate-800 rounded-2xl p-4 ring-1 ring-slate-200 dark:ring-slate-700/50 shadow-sm">
                <div class="text-2xl font-bold tabular-nums text-slate-900 dark:text-white">{total_devices}</div>
                <div class="text-xs text-slate-600 dark:text-slate-300 font-medium mt-0.5">追蹤機型</div>
            </div>
            <div class="bg-white dark:bg-slate-800 rounded-2xl p-4 ring-1 ring-slate-200 dark:ring-slate-700/50 shadow-sm">
                <div class="text-2xl font-bold tabular-nums text-emerald-700 dark:text-emerald-400">{recent_7d}</div>
                <div class="text-xs text-slate-600 dark:text-slate-300 font-medium mt-0.5">7 天內更新</div>
            </div>
            <div class="bg-white dark:bg-slate-800 rounded-2xl p-4 ring-1 ring-slate-200 dark:ring-slate-700/50 shadow-sm">
                <div class="text-2xl font-bold tabular-nums text-blue-700 dark:text-blue-400">{recent_30d}</div>
                <div class="text-xs text-slate-600 dark:text-slate-300 font-medium mt-0.5">30 天內更新</div>
            </div>
            <div class="bg-white dark:bg-slate-800 rounded-2xl p-4 ring-1 ring-slate-200 dark:ring-slate-700/50 shadow-sm">
                <div class="text-2xl font-bold tabular-nums text-mi-orange">{brand_count}</div>
                <div class="text-xs text-slate-600 dark:text-slate-300 font-medium mt-0.5">品牌數</div>
            </div>
        </div>
    </div>

    <!-- Live region for filter results -->
    <div id="filterStatus" class="sr-only" aria-live="polite" aria-atomic="true"></div>

    <main class="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 mt-6 space-y-6" id="content" tabindex="-1">"""]

# 生成設備卡片
for index, device in enumerate(final_list):
    tw = device['tw']['latest']
    tw_ver = tw['os']
    tw_date = tw['release']
    tw_history = device['tw']['history']
    image_filename = f'{device["code"]}.png'
    image_file_path = os.path.join(images_dir, image_filename)

    # 僅對前 2 個首屏關鍵圖片設定 fetchpriority="high"，第 3-4 個維持 eager 預設優先權，其餘延遲載入
    if index < 2:
        img_loading_attr = 'loading="eager" fetchpriority="high"'
    elif index < 4:
        img_loading_attr = 'loading="eager"'
    else:
        img_loading_attr = 'loading="lazy"'

    if os.path.isfile(image_file_path):
        device_visual_html = (
            f'<img src="assets/images/{image_filename}" alt="{device["name"]} 機身圖" '
            f'width="64" height="80" {img_loading_attr} decoding="async" '
            f'class="h-20 w-16 object-contain flex-shrink-0">'
        )
    else:
        device_visual_html = (
            f'<div class="h-12 w-12 rounded-2xl bg-gradient-to-br from-slate-100 to-slate-200 '
            f'dark:from-slate-700 dark:to-slate-600 flex items-center justify-center text-slate-800 '
            f'dark:text-slate-200 font-bold text-xl flex-shrink-0 shadow-inner" aria-hidden="true">'
            f'{device["name"][0]}</div>'
        )
    
    # Header Info
    ago_html = ""
    try:
        tw_dt = datetime.strptime(tw_date, "%Y-%m-%d").replace(tzinfo=tz_tw)
        days_ago = (now_tw - tw_dt).days
        
        threshold_days = get_abandoned_threshold(tw_history)
        is_abandoned = threshold_days > 0 and days_ago > threshold_days

        if is_abandoned:
            ago_html = f'<span class="text-xs font-medium px-2 py-0.5 rounded mt-1 text-white bg-slate-700 dark:bg-slate-700" role="status" aria-label="疑似棄更，已 {days_ago} 天未更新">疑似棄更 ({days_ago} 天)</span>'
        else:
            status_text = f"已過 {days_ago} 天"
            if threshold_days > 0:
                status_text += f" / 棄更門檻 {threshold_days} 天"

            if days_ago > 90: 
                ago_color = "text-orange-800 bg-orange-100 dark:text-orange-300 dark:bg-orange-950/60"
            elif days_ago > 30: 
                ago_color = "text-slate-700 bg-slate-100 dark:text-slate-200 dark:bg-slate-700"
            else: 
                ago_color = "text-emerald-800 bg-emerald-100 dark:text-emerald-300 dark:bg-emerald-950/60"
            ago_html = f'<span class="text-xs font-medium px-2 py-0.5 rounded mt-1 {ago_color}">{status_text}</span>'
    except: 
        pass

    tw_card = generate_card_html(device['tw'], "台灣版", 'tw')
    gl_card = generate_card_html(device['global'], "國際版", 'global', tw_ver)
    
    others_cards = ''.join(
        generate_card_html(other, other['label'], 'other', tw_ver)
        for other in device['others']
    ) if device['others'] else ""

    html_parts.append(
        f'<article class="device-card bg-white dark:bg-slate-800 rounded-3xl p-6 shadow-sm ring-1 ring-slate-200/80 dark:ring-slate-700/50 hover:shadow-xl dark:hover:shadow-lg dark:hover:shadow-black/20 hover:ring-slate-300 dark:hover:ring-slate-600/50 transition-all duration-300 transform hover:-translate-y-1" data-brand="{device["brand"]}" data-date="{tw_date}" aria-label="{device["name"]} 更新資訊">'
        
        f'<div class="flex flex-col sm:flex-row sm:items-start justify-between gap-4 mb-2">'
        f'<div class="flex items-start gap-4">'
        f'{device_visual_html}'
        f'<div>'
        f'<h2 class="text-xl font-bold text-slate-900 dark:text-white leading-tight device-title tracking-tight">{device["name"]}</h2>'
        f'<div class="flex items-center gap-2 mt-1.5">'
        f'<span class="text-[0.6875rem] font-mono font-medium text-slate-700 dark:text-slate-200 bg-slate-100 dark:bg-slate-700/80 px-2 py-1 rounded-lg border border-slate-200 dark:border-slate-600 device-code">{device["code"]}</span>'
        f'<span class="text-[0.6875rem] font-bold text-slate-700 dark:text-slate-200 bg-slate-100 dark:bg-slate-700/80 px-2 py-1 rounded-lg border border-slate-200 dark:border-slate-600 uppercase tracking-wide">{device["brand"]}</span>'
        f'</div>'
        f'</div>'
        f'</div>'
        
        f'<div class="flex flex-col items-end">'
        f'<div class="flex items-center gap-2">'
        f'<span class="text-xs font-bold text-slate-600 dark:text-slate-300 uppercase tracking-wider">更新於</span>'
        f'<time datetime="{tw_date}" class="text-sm font-bold tabular-nums text-slate-800 dark:text-slate-100 bg-slate-100 dark:bg-slate-700/80 px-2.5 py-1 rounded-lg border border-slate-200 dark:border-slate-600 font-mono">{tw_date}</time>'
        f'</div>'
        f'{ago_html}'
        f'</div>'
        f'</div>'
        
        f'<div class="grid grid-cols-1 lg:grid-cols-2 gap-4 mt-6">'
        f'{tw_card}{gl_card}{others_cards}'
        f'</div>'
        f'</article>'
    )

# 歷史資料序列化為緊湊 JSON
history_json_str = json.dumps(rom_history_store, ensure_ascii=False, separators=(',', ':'))

html_parts.append(f"""
    </main>
    
    <!-- Empty state (hidden by default) -->
    <div id="emptyState" class="hidden max-w-5xl mx-auto px-4 py-20 text-center">
        <svg class="mx-auto h-16 w-16 text-slate-400 dark:text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
        </svg>
        <h3 class="mt-4 text-lg font-semibold text-slate-800 dark:text-slate-200">找不到符合的機型</h3>
        <p class="mt-2 text-sm text-slate-600 dark:text-slate-300">請嘗試調整搜尋條件或篩選設定</p>
    </div>

    <!-- Back to top button -->
    <button type="button" id="backToTop" class="back-to-top" aria-label="回到頂部">
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M5 15l7-7 7 7"/></svg>
    </button>
    
    <footer class="mt-20 border-t border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900">
        <div class="max-w-5xl mx-auto px-4 py-12 text-center">
            <p class="text-slate-600 dark:text-slate-300 text-sm font-medium">由 GitHub Actions 自動生成</p>
            <p class="text-slate-500 dark:text-slate-400 text-xs mt-2">共追蹤 {total_devices} 款機型</p>
        </div>
    </footer>

    <!-- ROM History Data -->
    <script id="romHistoryData" type="application/json">
    {history_json_str}
    </script>

    <script>
        /* === Theme Toggle === */
        (function() {{
            const html = document.documentElement;
            const toggle = document.getElementById('themeToggle');
            const iconSun = document.getElementById('themeIconSun');
            const iconMoon = document.getElementById('themeIconMoon');
            const metaColorScheme = document.querySelector('meta[name="color-scheme"]');
            const darkQuery = window.matchMedia('(prefers-color-scheme: dark)');

            function getSavedTheme() {{
                try {{
                    return localStorage.getItem('theme');
                }} catch (e) {{
                    return null;
                }}
            }}

            function syncThemeUI() {{
                const saved = getSavedTheme();
                const isDark = saved === 'dark' || (!saved && darkQuery.matches);
                html.classList.toggle('dark', isDark);
                iconSun.classList.toggle('hidden', !isDark);
                iconMoon.classList.toggle('hidden', isDark);
                if (metaColorScheme) {{
                    metaColorScheme.content = saved || 'light dark';
                }}
            }}

            syncThemeUI();

            // Listen for system changes (only when following system preference)
            darkQuery.addEventListener('change', () => {{
                if (!getSavedTheme()) {{
                    syncThemeUI();
                }}
            }});

            // Sync across open tabs
            window.addEventListener('storage', (e) => {{
                if (e.key === 'theme') {{
                    syncThemeUI();
                }}
            }});

            toggle.addEventListener('click', () => {{
                const isDark = html.classList.contains('dark');
                const next = isDark ? 'light' : 'dark';
                const matchesSystem = (next === 'dark') === darkQuery.matches;
                try {{
                    if (matchesSystem) {{
                        localStorage.removeItem('theme');
                    }} else {{
                        localStorage.setItem('theme', next);
                    }}
                }} catch (e) {{}}
                html.classList.toggle('dark', next === 'dark');
                iconSun.classList.toggle('hidden', next !== 'dark');
                iconMoon.classList.toggle('hidden', next === 'dark');
                if (metaColorScheme) {{
                    metaColorScheme.content = matchesSystem ? 'light dark' : next;
                }}
            }});
        }})();

        /* === Location-Agnostic Calendar Date Utilities === */
        function parsePlainDateMs(dateStr) {{
            const parts = String(dateStr || '').split('-');
            if (parts.length !== 3) return NaN;
            const y = Number(parts[0]), m = Number(parts[1]), d = Number(parts[2]);
            if (!Number.isInteger(y) || !Number.isInteger(m) || !Number.isInteger(d)) return NaN;
            return Date.UTC(y, m - 1, d);
        }}

        function diffCalendarDays(laterDateStr, earlierDateStr) {{
            if (typeof Temporal !== 'undefined' && Temporal.PlainDate) {{
                try {{
                    const later = Temporal.PlainDate.from(laterDateStr);
                    const earlier = Temporal.PlainDate.from(earlierDateStr);
                    return later.since(earlier, {{ largestUnit: 'day' }}).days;
                }} catch (e) {{}}
            }}
            const laterMs = parsePlainDateMs(laterDateStr);
            const earlierMs = parsePlainDateMs(earlierDateStr);
            if (Number.isNaN(laterMs) || Number.isNaN(earlierMs)) return NaN;
            return Math.round((laterMs - earlierMs) / 86400000);
        }}

        function getTodayTaipeiStr() {{
            if (typeof Temporal !== 'undefined' && Temporal.Now) {{
                try {{
                    return Temporal.Now.plainDateISO('Asia/Taipei').toString();
                }} catch (e) {{}}
            }}
            return new Intl.DateTimeFormat('en-CA', {{
                timeZone: 'Asia/Taipei',
                year: 'numeric',
                month: '2-digit',
                day: '2-digit'
            }}).format(new Date());
        }}

        /* === On-Demand History Table Rendering === */
        let romHistoryCache = null;
        function getRomHistory(panelId) {{
            if (!romHistoryCache) {{
                const dataEl = document.getElementById('romHistoryData');
                if (dataEl) {{
                    try {{
                        romHistoryCache = JSON.parse(dataEl.textContent);
                    }} catch (e) {{
                        romHistoryCache = {{}};
                    }}
                }} else {{
                    romHistoryCache = {{}};
                }}
            }}
            return romHistoryCache[panelId] || null;
        }}

        function renderHistoryTable(container, romList) {{
            if (!romList || !romList.length) return;
            let rowsHtml = '';
            for (let i = 0; i < romList.length; i++) {{
                const [os, release, android, aspatch] = romList[i];
                let intervalHtml = '<span class="text-slate-500 dark:text-slate-400 font-medium" aria-label="無資料">—</span>';
                if (i < romList.length - 1) {{
                    const diffDays = diffCalendarDays(release, romList[i + 1][1]);
                    if (!Number.isNaN(diffDays) && diffDays >= 0) {{
                        let colorClass = 'bg-slate-100 text-slate-700 dark:bg-slate-700/80 dark:text-slate-200';
                        if (diffDays > 90) colorClass = 'bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300';
                        else if (diffDays < 30) colorClass = 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300';
                        intervalHtml = `<span class="px-2 py-0.5 rounded-full text-[0.625rem] font-medium tabular-nums ${{colorClass}}">${{diffDays}} 天</span>`;
                    }}
                }} else {{
                    intervalHtml = '<span class="text-[0.625rem] font-medium text-blue-800 bg-blue-100 dark:text-blue-300 dark:bg-blue-950/60 px-2 py-0.5 rounded-full">首版</span>';
                }}
                rowsHtml += `
                    <tr class="hover:bg-slate-50 dark:hover:bg-slate-700/50 transition-colors">
                        <td class="py-2.5 pl-2 font-mono text-slate-800 dark:text-slate-200 font-medium">${{os}}</td>
                        <td class="py-2.5 text-slate-600 dark:text-slate-300 tabular-nums">${{release}}</td>
                        <td class="py-2.5 text-center">${{intervalHtml}}</td>
                        <td class="py-2.5 text-right text-slate-600 dark:text-slate-300 tabular-nums">${{android || '—'}}</td>
                        <td class="py-2.5 text-right pr-2 text-slate-600 dark:text-slate-300 tabular-nums">${{aspatch || '—'}}</td>
                    </tr>
                `;
            }}

            container.innerHTML = `
                <div class="overflow-x-auto focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 rounded-lg" tabindex="0" role="region" aria-label="歷史版本表格">
                    <table class="w-full text-xs text-left whitespace-nowrap tabular-nums">
                        <thead class="text-slate-600 dark:text-slate-300 font-semibold border-b border-slate-200 dark:border-slate-700">
                            <tr>
                                <th scope="col" class="py-2 pl-2">版本</th>
                                <th scope="col" class="py-2">日期</th>
                                <th scope="col" class="py-2 text-center">間隔</th>
                                <th scope="col" class="py-2 text-right">Android</th>
                                <th scope="col" class="py-2 text-right pr-2">安全性更新</th>
                            </tr>
                        </thead>
                        <tbody class="divide-y divide-slate-100 dark:divide-slate-700/50">
                            ${{rowsHtml}}
                        </tbody>
                    </table>
                </div>
            `;
            container.dataset.rendered = "true";
        }}

        /* === History Toggle (Event Delegation) === */
        function toggleHistory(element) {{
            const historyDiv = element.nextElementSibling;
            if (historyDiv) {{
                if (historyDiv.dataset.rendered !== 'true') {{
                    const panelId = historyDiv.id;
                    const roms = getRomHistory(panelId);
                    if (roms) {{
                        renderHistoryTable(historyDiv, roms);
                    }}
                }}
                const isHidden = historyDiv.classList.toggle('hidden');
                element.setAttribute('aria-expanded', String(!isHidden));
                const arrow = element.querySelector('.arrow-icon');
                if (arrow) arrow.style.transform = isHidden ? 'rotate(0deg)' : 'rotate(180deg)';
            }}
        }}

        const mainContent = document.getElementById('content');
        mainContent.addEventListener('click', (e) => {{
            const btn = e.target.closest('[data-history-toggle]');
            if (btn) {{
                toggleHistory(btn);
            }}
        }});
        
        /* === Filter Logic === */
        const searchInput = document.getElementById('searchInput');
        const brandFilter = document.getElementById('brandFilter');
        const recentFilter = document.getElementById('recentFilter');
        const daysFilter = document.getElementById('daysFilter');
        const emptyState = document.getElementById('emptyState');
        const filterStatus = document.getElementById('filterStatus');

        function filterContent() {{
            requestAnimationFrame(() => {{
                const searchText = searchInput.value.toLowerCase().trim();
                const selectedBrand = brandFilter.value;
                const isRecent = recentFilter.checked;
                const recentDaysThreshold = parseInt(daysFilter.value, 10) || 30;
                const cards = document.querySelectorAll('.device-card');
                const todayStr = isRecent ? getTodayTaipeiStr() : '';
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
                        const diffDays = diffCalendarDays(todayStr, dateStr);
                        matchRecent = !Number.isNaN(diffDays) && diffDays >= 0 && diffDays <= recentDaysThreshold;
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
        recentFilter.addEventListener('change', filterContent);
        daysFilter.addEventListener('change', () => {{
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
                const days = parseInt(daysParam, 10);
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
                }}
            }}

            if (query || brandParam || daysParam) filterContent();
        }} catch (e) {{ console.error(e); }}

        /* === Back to Top via IntersectionObserver === */
        const backToTop = document.getElementById('backToTop');
        const statsBar = document.getElementById('statsBar');
        if (backToTop && statsBar && 'IntersectionObserver' in window) {{
            const observer = new IntersectionObserver((entries) => {{
                entries.forEach((entry) => {{
                    const scrolledPast = !entry.isIntersecting && entry.boundingClientRect.top < 0;
                    backToTop.classList.toggle('visible', scrolledPast);
                }});
            }}, {{ threshold: 0 }});
            observer.observe(statsBar);
        }}

        if (backToTop) {{
            backToTop.addEventListener('click', () => {{
                const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
                window.scrollTo({{ top: 0, behavior: prefersReducedMotion ? 'auto' : 'smooth' }});
            }});
        }}
    </script>
</body>
</html>
""")

# 一次性寫入
with open(output_file, 'w', encoding='utf-8') as f:
    f.write(''.join(html_parts))

print(f"[OK] Generated {output_file} with {total_devices} devices")
