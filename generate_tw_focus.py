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
                'global': None
            }
            
        branches = data.get('branches', [])
        for branch in branches:
            branch_name_zh = branch.get('name', {}).get('zh', '')
            
            target_type = None
            if branch_name_zh == TARGET_TW:
                target_type = 'tw'
                brand = branch.get('brand', 'Xiaomi')
                if brand: devices_map[device_code]['brand'] = brand
            elif branch_name_zh == TARGET_GLOBAL:
                target_type = 'global'
            
            if target_type:
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
                    devices_map[device_code][target_type] = {
                        'latest': rom_list[0],
                        'history': rom_list
                    }
                
    except Exception as e:
        print(f"Error processing {file_path}: {e}")

final_list = []
for code, info in devices_map.items():
    if info['tw']:
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
    <thead class="text-gray-400 font-medium border-b border-gray-50">
        <tr>
            <th class="py-2 pl-1">版本</th>
            <th class="py-2">日期</th>
            <th class="py-2 text-center">間隔</th>
            <th class="py-2 text-right pr-1">Android</th>
        </tr>
    </thead>
    <tbody class="divide-y divide-gray-50">
    '''
    
    for i, rom in enumerate(history_list):
        interval_html = '<span class="text-gray-300">-</span>'
        if i < len(history_list) - 1:
            try:
                current_date = datetime.strptime(rom['release'], "%Y-%m-%d")
                prev_date = datetime.strptime(history_list[i+1]['release'], "%Y-%m-%d")
                delta_days = (current_date - prev_date).days
                bg_color = "bg-gray-100 text-gray-500"
                if delta_days > 90: bg_color = "bg-orange-50 text-orange-600"
                elif delta_days < 30: bg_color = "bg-green-50 text-green-600"
                interval_html = f'<span class="px-1.5 py-0.5 rounded {bg_color}">{delta_days} 天</span>'
            except: pass
        else:
            interval_html = '<span class="text-xs text-blue-300">首版</span>'

        html += f'''
        <tr class="hover:bg-gray-50 transition-colors">
            <td class="py-2 pl-1 font-mono text-gray-700">{rom['os']}</td>
            <td class="py-2 text-gray-500">{rom['release']}</td>
            <td class="py-2 text-center">{interval_html}</td>
            <td class="py-2 text-right pr-1 text-gray-400">{rom['android']}</td>
        </tr>
        '''
    html += '</tbody></table></div>'
    return html

html_content = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>小米 HyperOS 台灣版更新追蹤</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
        tailwind.config = {{
            theme: {{
                extend: {{
                    fontFamily: {{
                        sans: ['"Microsoft JhengHei"', 'ui-sans-serif', 'system-ui', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'Helvetica Neue', 'Arial', 'sans-serif'],
                    }},
                    keyframes: {{
                        fadeIn: {{
                            '0%': {{ opacity: '0', transform: 'translateY(-5px)' }},
                            '100%': {{ opacity: '1', transform: 'translateY(0)' }},
                        }}
                    }},
                    animation: {{
                        'fade-in': 'fadeIn 0.2s ease-out',
                    }}
                }}
            }}
        }}
    </script>
    <style>
        .no-scrollbar::-webkit-scrollbar {{ display: none; }}
        .no-scrollbar {{ -ms-overflow-style: none; scrollbar-width: none; }}
    </style>
</head>
<body class="bg-gray-50 text-gray-800 antialiased min-h-screen pb-10">

    <div class="sticky top-0 z-50 bg-white/80 backdrop-blur-md border-b border-gray-200 shadow-sm">
        <div class="max-w-4xl mx-auto px-4 py-4">
            <div class="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                    <h1 class="text-2xl font-bold text-gray-900 tracking-tight text-mi-orange">HyperOS TW Tracker</h1>
                    <p class="text-xs text-gray-500 mt-1">更新時間: {gen_time} (UTC+8)</p>
                </div>
                <div class="flex gap-2 w-full md:w-auto">
                    <select id="brandFilter" class="bg-gray-100 hover:bg-gray-200 text-gray-700 py-2 px-4 rounded-full text-sm font-medium focus:outline-none focus:ring-2 focus:ring-blue-500 transition-colors cursor-pointer border-0">
                        {brand_options}
                    </select>
                    <div class="relative flex-grow md:w-64">
                        <input type="text" id="searchInput" class="w-full bg-gray-100 hover:bg-gray-200 focus:bg-white text-gray-700 py-2 pl-10 pr-4 rounded-full text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all border-0 placeholder-gray-400" placeholder="搜尋機型名稱或代號...">
                        <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-gray-400">
                            <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path></svg>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <div class="max-w-4xl mx-auto px-4 mt-6" id="content">
"""

for device in final_list:
    tw = device['tw']['latest']
    gl = device['global']['latest'] if device['global'] else None
    
    tw_ver = tw['os']
    tw_date = tw['release']
    
    # 計算距今時間
    ago_html = ""
    try:
        tw_dt = datetime.strptime(tw_date, "%Y-%m-%d").replace(tzinfo=tz_tw)
        days_ago = (now_tw - tw_dt).days
        
        ago_color = "text-green-600 bg-green-50"
        if days_ago > 180: ago_color = "text-red-600 bg-red-50"
        elif days_ago > 90: ago_color = "text-orange-600 bg-orange-50"
        elif days_ago > 30: ago_color = "text-gray-500 bg-gray-100"
        
        ago_html = f'<span class="text-[10px] font-medium px-1.5 py-0.5 rounded mt-1 {ago_color}">已過 {days_ago} 天</span>'
    except: pass

    # 台灣版歷史區塊
    tw_history_html = generate_history_html(device['tw']['history'], 'tw-history')
    
    gl_info_html = ""
    ver_status_tag = ""
    
    if gl:
        gl_ver = gl['os']
        tw_tup = version_to_tuple(tw_ver)
        gl_tup = version_to_tuple(gl_ver)
        
        if tw_tup < gl_tup:
            ver_status_tag = '<span class="text-[10px] px-1.5 py-0.5 rounded text-red-500 bg-red-50">↓ 落後</span>'
        elif tw_tup > gl_tup:
            ver_status_tag = '<span class="text-[10px] px-1.5 py-0.5 rounded text-green-600 bg-green-50">↑ 領先</span>'
        else:
            ver_status_tag = '<span class="text-[10px] px-1.5 py-0.5 rounded text-gray-500 bg-gray-100">= 同步</span>'

        gl_history_html = generate_history_html(device['global']['history'], 'gl-history')

        gl_info_html = f"""
            <div class="group/gl">
                <div onclick="toggleHistory(this)" class="cursor-pointer flex items-center justify-between p-3 rounded-lg border border-dashed border-gray-300 bg-white/50 hover:bg-gray-50 transition-colors relative select-none">
                    <div class="flex items-center gap-3">
                        <span class="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-gray-100 text-gray-600 group-hover/gl:bg-gray-200 transition-colors">國際版 ▾</span>
                        <div>
                            <div class="text-sm font-mono text-gray-600">{gl_ver}</div>
                            <div class="text-[10px] text-gray-400">Android {gl['android']}</div>
                        </div>
                    </div>
                    <div class="text-xs text-gray-500 font-medium">{gl['release']}</div>
                </div>
                {gl_history_html}
            </div>
        """
    else:
        gl_info_html = """
            <div class="flex items-center justify-center p-3 rounded-lg border border-dashed border-gray-200 bg-gray-50">
                <span class="text-xs text-gray-400 italic">無國際版資料</span>
            </div>
        """

    tw_card_block = f"""
        <div class="group/tw">
            <div onclick="toggleHistory(this)" class="cursor-pointer flex items-center justify-between p-3 rounded-lg bg-blue-50/50 border border-blue-100 hover:bg-blue-50 transition-colors relative select-none">
                <div class="flex items-center gap-3">
                    <span class="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-blue-100 text-blue-700 shadow-sm group-hover/tw:bg-blue-200 transition-colors">台灣版 ▾</span>
                    <div>
                        <div class="text-sm font-bold font-mono text-gray-800">{tw_ver}</div>
                        <div class="text-[10px] text-blue-400">Android {tw['android']}</div>
                    </div>
                </div>
                {ver_status_tag}
            </div>
            {tw_history_html}
        </div>
    """

    html_content += f"""
        <div class="device-card bg-white rounded-2xl p-5 mb-4 shadow-sm hover:shadow-md transition-all border border-gray-100" data-brand="{device['brand']}">
            <div class="flex flex-col sm:flex-row sm:items-start justify-between gap-4 mb-4">
                <div class="flex items-start gap-3">
                    <div class="h-10 w-10 rounded-full bg-blue-50 flex items-center justify-center text-blue-500 font-bold text-lg flex-shrink-0">
                        {device['name'][0]}
                    </div>
                    <div>
                        <h3 class="text-lg font-bold text-gray-900 leading-tight device-title">{device['name']}</h3>
                        <div class="flex items-center gap-2 mt-1">
                            <span class="text-xs font-mono text-gray-400 bg-gray-50 px-1.5 py-0.5 rounded border border-gray-100 device-code">{device['code']}</span>
                            <span class="text-[10px] text-gray-400 bg-gray-50 px-1.5 py-0.5 rounded border border-gray-100">{device['brand']}</span>
                        </div>
                    </div>
                </div>
                <div class="flex flex-col items-end">
                    <span class="text-sm font-bold text-gray-700 bg-gray-50 px-2 py-1 rounded-md">{tw_date}</span>
                    {ago_html}
                </div>
            </div>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
                {tw_card_block}
                {gl_info_html}
            </div>
        </div>
    """

html_content += """
    </div>
    <div class="max-w-4xl mx-auto px-4 py-8 text-center text-gray-400 text-xs">
        Generated by GitHub Actions • Total {len(final_list)} Devices
    </div>
    <script>
        function toggleHistory(element) {
            const historyDiv = element.nextElementSibling;
            if (historyDiv) historyDiv.classList.toggle('hidden');
        }
        const searchInput = document.getElementById('searchInput');
        const brandFilter = document.getElementById('brandFilter');
        function filterContent() {
            const searchText = searchInput.value.toLowerCase().trim();
            const selectedBrand = brandFilter.value;
            const cards = document.querySelectorAll('.device-card');
            cards.forEach(card => {
                const name = card.querySelector('.device-title').textContent.toLowerCase();
                const code = card.querySelector('.device-code').textContent.toLowerCase();
                const brand = card.getAttribute('data-brand');
                const matchText = name.includes(searchText) || code.includes(searchText);
                const matchBrand = (selectedBrand === 'all') || (brand === selectedBrand);
                card.classList.toggle('hidden', !(matchText && matchBrand));
            });
        }
        searchInput.addEventListener('input', filterContent);
        brandFilter.addEventListener('change', filterContent);
    </script>
</body>
</html>
"""

with open(output_file, 'w', encoding='utf-8') as f:
    f.write(html_content)
