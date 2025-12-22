import json
import os
import glob
from datetime import datetime, timedelta, timezone

# 設定為台灣時區 (UTC+8)
tz_tw = timezone(timedelta(hours=8))
now_tw = datetime.now(tz_tw)
gen_time = now_tw.strftime("%Y-%m-%d %H:%M")

# 設定路徑
devices_dir = 'devices'
output_file = 'tw.html'

# 定義要抓取的目標分支 (JSON 內部的名稱)
TARGET_TW = "小米澎湃 OS 中国台湾省正式版"
TARGET_GLOBAL = "小米澎湃 OS 国际正式版"

def version_to_tuple(v_str):
    try:
        clean_v = v_str[:-7] if len(v_str) > 7 else v_str
        if clean_v.startswith("OS"): clean_v = clean_v[2:]
        clean_v = clean_v.strip('.')
        return tuple(int(x) for x in clean_v.split('.') if x.isdigit())
    except:
        return (0,)

def get_region_label(branch_name_zh):
    # 移除通用前綴
    name = branch_name_zh.replace("小米澎湃 OS ", "")
    
    # 特殊完整名稱對應
    if name == "正式版": return "中國"
    if name == "开发版": return "開發版"
    if name == "Beta": return "Beta"
    
    # 移除通用後綴以取得核心名稱
    core_name = name.replace("正式版", "").replace("版", "").strip()
    
    # 地區與詞彙對照表 (簡體 -> 繁體/台灣慣用語)
    mapping = {
        "欧洲": "歐洲",
        "俄罗斯": "俄羅斯",
        "印度尼西亚": "印尼",
        "土耳其": "土耳其",
        "韩国": "韓國",
        "中国大陆": "中國",
        "中国": "中國",
        "演示机": "演示機",
        "运营商": "電信商",
        "定制": "客製",
        "政企标准": "政企標準",
        "政企": "政企"
    }
    
    # 先進行核心名稱的直接對應
    if core_name in mapping:
        return mapping[core_name]
    if core_name == "EEA": return "歐洲 EEA"
    if core_name == "欧洲EEA": return "歐洲 EEA"

    # 若無直接對應，則進行字串替換
    processed_name = core_name
    for sc, tc in mapping.items():
        processed_name = processed_name.replace(sc, tc)
        
    return processed_name

print(f"::group::初始化設定")
print(f"工作目錄: {os.getcwd()}")
print(f"輸出檔案: {output_file}")
print(f"::endgroup::")

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
                if brand: devices_map[device_code]['brand'] = brand
            elif branch_name_zh == TARGET_GLOBAL:
                target_type = 'global'
            else:
                target_type = 'other'
                branch_label = get_region_label(branch_name_zh)
                if not branch_label: branch_label = branch_name_zh # Fallback
            
            roms = branch.get('roms', {})
            if not roms: continue
            
            rom_list = []
            for k, v in roms.items():
                release_date = v.get('release', '1970-01-01')
                rom_list.append({
                    'os': v.get('os', k),
                    'android': v.get('android', ''),
                    'release': release_date
                })
            
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

final_list = []
for code, info in devices_map.items():
    if info['tw']:
        # Sort others by release date desc
        if info['others']:
            info['others'].sort(key=lambda x: x['latest']['release'], reverse=True)
        final_list.append(info)
        all_brands.add(info['brand'])

final_list.sort(key=lambda x: x['tw']['latest']['release'], reverse=True)

brand_options = '<option value="all">所有品牌</option>'
for brand in sorted(list(all_brands)):
    brand_options += f'<option value="{brand}">{brand}</option>'

print(f"Collected {len(final_list)} devices.")

# Helper function to generate history HTML
def generate_history_html(history_list, type_class):
    html = f'<div class="hidden mt-2 border-t border-gray-100 pt-2 animate-fade-in" data-type="{type_class}">'
    html += '<table class="w-full text-xs text-left">'
    html += '''
    <thead class="text-gray-500 font-medium border-b border-gray-50">
        <tr>
            <th class="py-2 pl-1">版本</th>
            <th class="py-2">日期</th>
            <th class="py-2 text-center">間隔</th>
            <th class="py-2 text-right pr-1">Android</th>
        </tr>
    </thead>
    <tbody class="divide-y divide-gray-50">
    '''
    
    # Limit history to latest 10 items to improve performance (DOM size)
    for i, rom in enumerate(history_list[:10]):
        interval_html = '<span class="text-gray-300">-</span>'
        if i < len(history_list) - 1:
            try:
                current_date = datetime.strptime(rom['release'], "%Y-%m-%d")
                prev_date = datetime.strptime(history_list[i+1]['release'], "%Y-%m-%d")
                delta_days = (current_date - prev_date).days
                bg_color = "bg-gray-100 text-gray-600"
                if delta_days > 90: bg_color = "bg-orange-50 text-orange-600"
                elif delta_days < 30: bg_color = "bg-green-50 text-green-600"
                interval_html = f'<span class="px-1.5 py-0.5 rounded {bg_color}">{delta_days} 天</span>'
            except: pass
        else:
            interval_html = '<span class="text-xs text-blue-600">首版</span>'

        html += f'''
        <tr class="hover:bg-gray-50 transition-colors">
            <td class="py-2 pl-1 font-mono text-gray-700">{rom['os']}</td>
            <td class="py-2 text-gray-600">{rom['release']}</td>
            <td class="py-2 text-center">{interval_html}</td>
            <td class="py-2 text-right pr-1 text-gray-600">{rom['android']}</td>
        </tr>
        '''
    html += '</tbody></table></div>'
    return html

# Helper for card generation
def generate_card_html(info, region_label, region_type, tw_ver_str=None):
    # region_type: 'tw', 'global', 'other'
    
    if not info:
        if region_type == 'global':
            return """
            <div class="flex items-center justify-center p-3 rounded-lg border border-dashed border-gray-200 bg-gray-50 h-[88px]">
                <span class="text-xs text-gray-400 italic">無國際版資料</span>
            </div>
            """
        return "" # Should not happen for others/tw based on logic

    latest = info['latest']
    ver_str = latest['os']
    
    # Compare with TW if this is not TW
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

    # Styling configuration
    if region_type == 'tw':
        bg_color = "bg-blue-50/50"
        border_color = "border-blue-100"
        badge_bg = "bg-blue-100"
        badge_text = "text-blue-700"
        hover_bg = "hover:bg-blue-50"
        group_class = "group/tw"
    elif region_type == 'global':
        bg_color = "bg-white/50"
        border_color = "border-gray-300 border-dashed"
        badge_bg = "bg-gray-100"
        badge_text = "text-gray-600"
        hover_bg = "hover:bg-gray-50"
        group_class = "group/gl"
    else: # other
        bg_color = "bg-purple-50/30"
        border_color = "border-purple-100 border-dashed"
        badge_bg = "bg-purple-100"
        badge_text = "text-purple-700"
        hover_bg = "hover:bg-purple-50"
        group_class = "group/ot"

    history_html = generate_history_html(info['history'], f'{region_type}-history')
    
    # Days ago
    ago_html = ""
    try:
        dt = datetime.strptime(latest['release'], "%Y-%m-%d").replace(tzinfo=tz_tw)
        days = (now_tw - dt).days
        ago_html = f'<div class="text-[11px] text-gray-600 mt-0.5">({days} 天前)</div>'
    except: pass

    return f"""
        <div class="{group_class}">
            <button type="button" onclick="toggleHistory(this)" aria-expanded="false" class="w-full cursor-pointer flex items-center justify-between p-3 rounded-lg {bg_color} border {border_color} {hover_bg} transition-colors relative select-none focus:outline-none focus:ring-2 focus:ring-blue-500 text-left">
                <div class="flex items-center gap-3">
                    <span class="inline-flex items-center px-2 py-1 rounded text-xs font-medium {badge_bg} {badge_text} shadow-sm transition-colors">{region_label} ▾</span>
                    <div>
                        <div class="text-sm font-mono text-gray-700 font-bold">{ver_str}</div>
                        <div class="text-xs text-gray-600">Android {latest['android']}</div>
                    </div>
                </div>
                <div class="flex flex-col items-end">
                    <div class="text-xs text-gray-600 font-medium">{latest['release']}</div>
                    {ago_html}
                    {ver_status_tag}
                </div>
            </button>
            {history_html}
        </div>
    """

html_content = f"""<!DOCTYPE html>
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
"""

for device in final_list:
    tw = device['tw']['latest']
    tw_ver = tw['os']
    tw_date = tw['release']
    
    # Header Info
    ago_html = ""
    try:
        tw_dt = datetime.strptime(tw_date, "%Y-%m-%d").replace(tzinfo=tz_tw)
        days_ago = (now_tw - tw_dt).days
        
        ago_color = "text-green-700 bg-green-50"
        if days_ago > 180: ago_color = "text-red-700 bg-red-50"
        elif days_ago > 90: ago_color = "text-orange-700 bg-orange-50"
        elif days_ago > 30: ago_color = "text-gray-600 bg-gray-100"
        
        ago_html = f'<span class="text-xs font-medium px-1.5 py-0.5 rounded mt-1 {ago_color}">已過 {days_ago} 天</span>'
    except: pass

    # Card Generation
    tw_card = generate_card_html(device['tw'], "台灣版", 'tw')
    gl_card = generate_card_html(device['global'], "國際版", 'global', tw_ver)
    
    others_cards = ""
    if device['others']:
        for other in device['others']:
            others_cards += generate_card_html(other, other['label'], 'other', tw_ver)

    html_content += f"""
        <div class="device-card bg-white rounded-2xl p-5 mb-4 shadow-sm hover:shadow-md transition-all border border-gray-100" data-brand="{device['brand']}" data-date="{tw_date}">
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
                    <span class="text-sm font-bold text-gray-700 bg-gray-50 px-2 py-1 rounded-md">{tw_date}</span>
                    {ago_html}
                </div>
            </div>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
                {tw_card}
                {gl_card}
                {others_cards}
            </div>
        </div>
    """

html_content += f"""
    </main>
    <div class="max-w-4xl mx-auto px-4 py-8 text-center text-gray-500 text-xs">
        Generated by GitHub Actions • Total {len(final_list)} Devices
    </div>
"""

html_content += """
    <script>
        function toggleHistory(element) {
            const historyDiv = element.nextElementSibling;
            if (historyDiv) {
                const isHidden = historyDiv.classList.toggle('hidden');
                element.setAttribute('aria-expanded', !isHidden);
            }
        }
        const searchInput = document.getElementById('searchInput');
        const brandFilter = document.getElementById('brandFilter');
        const recentFilter = document.getElementById('recentFilter');
        const daysLabel = document.getElementById('daysLabel');
        
        let recentDaysThreshold = 30;

        function filterContent() {
            const searchText = searchInput.value.toLowerCase().trim();
            const selectedBrand = brandFilter.value;
            const isRecent = recentFilter.checked;
            
            const cards = document.querySelectorAll('.device-card');
            const now = new Date();

            cards.forEach(card => {
                const name = card.querySelector('.device-title').textContent.toLowerCase();
                const code = card.querySelector('.device-code').textContent.toLowerCase();
                const brand = card.getAttribute('data-brand');
                const dateStr = card.getAttribute('data-date');
                
                const matchText = name.includes(searchText) || code.includes(searchText);
                const matchBrand = (selectedBrand === 'all') || (brand === selectedBrand);
                
                let matchRecent = true;
                if (isRecent && dateStr) {
                    const releaseDate = new Date(dateStr);
                    const diffTime = Math.abs(now - releaseDate);
                    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24)); 
                    matchRecent = diffDays <= recentDaysThreshold;
                }

                card.classList.toggle('hidden', !(matchText && matchBrand && matchRecent));
            });
        }
        searchInput.addEventListener('input', filterContent);
        brandFilter.addEventListener('change', filterContent);
        recentFilter.addEventListener('change', filterContent);

        // Auto-filter from URL parameter
        try {
            const urlParams = new URLSearchParams(window.location.search);
            
            // 1. Handle Search (?q=...)
            const query = urlParams.get('q');
            if (query) {
                searchInput.value = query;
            }

            // 2. Handle Brand (?brand=...)
            const brandParam = urlParams.get('brand');
            if (brandParam) {
                // Find matching option (case-insensitive)
                const options = Array.from(brandFilter.options);
                const match = options.find(opt => opt.value.toLowerCase() === brandParam.toLowerCase());
                if (match) {
                    brandFilter.value = match.value;
                }
            }

            // 3. Handle Recent Days (?days=N)
            const daysParam = urlParams.get('days');
            if (daysParam) {
                const days = parseInt(daysParam);
                if (!isNaN(days) && days > 0) {
                    recentDaysThreshold = days;
                    daysLabel.textContent = days;
                    recentFilter.checked = true;
                }
            }

            // Apply filters if needed
            if (query || brandParam || daysParam) {
                filterContent();
            }
        } catch (e) { console.error(e); }
    </script>
</body>
</html>
"""

with open(output_file, 'w', encoding='utf-8') as f:
    f.write(html_content)