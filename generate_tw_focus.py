import json
import os
import glob
from datetime import datetime

# 設定路徑
devices_dir = 'devices'
output_file = 'tw.html'  # 修改為輸出到 tw.html

# 定義要抓取的目標分支 (JSON 內部的名稱)
TARGET_TW = "小米澎湃 OS 中国台湾省正式版"
TARGET_GLOBAL = "小米澎湃 OS 国际正式版"

print(f"::group::初始化設定")
print(f"工作目錄: {os.getcwd()}")
print(f"讀取資料夾: {devices_dir}")
print(f"輸出檔案: {output_file}")
print(f"::endgroup::")

# 用來儲存整理後的資料
devices_map = {}
# 用來收集所有出現過的品牌
all_brands = set()

# 讀取所有 json 檔案
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
                if brand:
                    devices_map[device_code]['brand'] = brand
            elif branch_name_zh == TARGET_GLOBAL:
                target_type = 'global'
            
            if target_type:
                roms = branch.get('roms', {})
                if not roms:
                    continue
                
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
                        'history_count': len(rom_list)
                    }
                
    except Exception as e:
        print(f"Error processing {file_path}: {e}")

# 轉換為列表並過濾
final_list = []
for code, info in devices_map.items():
    if info['tw']:
        final_list.append(info)
        all_brands.add(info['brand'])

# 排序
final_list.sort(key=lambda x: x['tw']['latest']['release'], reverse=True)

# 生成品牌選項 HTML
brand_options = '<option value="all">所有品牌</option>'
for brand in sorted(list(all_brands)):
    brand_options += f'<option value="{brand}">{brand}</option>'

print(f"Collected {len(final_list)} devices.")

# 生成 HTML (使用 Tailwind CSS)
# 加入生成時間標記
gen_time = datetime.now().strftime("%Y-%m-%d %H:%M")

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
                    colors: {{
                        'mi-orange': '#ff6700',
                        'mi-dark': '#1e1e1e',
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

    <!-- 頂部標題與搜尋區 -->
    <div class="sticky top-0 z-50 bg-white/80 backdrop-blur-md border-b border-gray-200 shadow-sm">
        <div class="max-w-4xl mx-auto px-4 py-4">
            <div class="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                    <h1 class="text-2xl font-bold text-gray-900 tracking-tight">HyperOS TW Tracker</h1>
                    <p class="text-xs text-gray-500 mt-1">更新時間: {gen_time} (Auto-generated)</p>
                </div>
                
                <div class="flex gap-2 w-full md:w-auto">
                    <div class="relative group">
                        <select id="brandFilter" class="appearance-none bg-gray-100 hover:bg-gray-200 text-gray-700 py-2.5 pl-4 pr-8 rounded-full text-sm font-medium focus:outline-none focus:ring-2 focus:ring-blue-500 transition-colors cursor-pointer border border-transparent">
                            {brand_options}
                        </select>
                        <div class="pointer-events-none absolute inset-y-0 right-0 flex items-center px-2 text-gray-500">
                            <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path></svg>
                        </div>
                    </div>
                    
                    <div class="relative flex-grow md:flex-grow-0 md:w-64">
                        <input type="text" id="searchInput" 
                            class="w-full bg-gray-100 hover:bg-gray-200 focus:bg-white text-gray-700 py-2.5 pl-10 pr-4 rounded-full text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all border border-transparent placeholder-gray-400" 
                            placeholder="搜尋機型名稱或代號...">
                        <div class="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none">
                            <svg class="h-4 w-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path></svg>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- 主要內容區 -->
    <div class="max-w-4xl mx-auto px-4 mt-6" id="content">
"""

for device in final_list:
    tw = device['tw']['latest']
    gl = device['global']['latest'] if device['global'] else None
    
    tw_date = tw['release']
    tw_ver = tw['os']
    tw_android = tw['android']
    
    ver_status = "text-gray-500"
    ver_icon = ""
    gl_info_html = ""
    
    if gl:
        gl_ver = gl['os']
        gl_date = gl['release']
        gl_android = gl['android']
        
        if tw_ver < gl_ver:
            ver_status = "text-red-500 bg-red-50"
            ver_icon = "↓ 落後"
        elif tw_ver > gl_ver:
            ver_status = "text-green-600 bg-green-50"
            ver_icon = "↑ 領先"
        else:
            ver_status = "text-gray-500 bg-gray-100"
            ver_icon = "= 同步"

        gl_info_html = f"""
            <div class="flex items-center justify-between p-3 rounded-lg border border-dashed border-gray-300 bg-white/50">
                <div class="flex items-center gap-3">
                    <span class="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-gray-100 text-gray-600">國際版</span>
                    <div>
                        <div class="text-sm font-mono text-gray-600">{gl_ver}</div>
                        <div class="text-[10px] text-gray-400">Android {gl_android}</div>
                    </div>
                </div>
                <div class="text-xs text-gray-500 font-medium">{gl_date}</div>
            </div>
        """
    else:
        gl_info_html = f"""
            <div class="flex items-center justify-center p-3 rounded-lg border border-dashed border-gray-200 bg-gray-50">
                <span class="text-xs text-gray-400 italic">無國際版資料</span>
            </div>
        """

    html_content += f"""
        <div class="device-card group bg-white rounded-2xl p-5 mb-4 shadow-sm hover:shadow-md transition-all duration-200 border border-gray-100" data-brand="{device['brand']}">
            <div class="flex flex-col sm:flex-row sm:items-start justify-between gap-4 mb-4">
                <div class="flex items-start gap-3">
                    <div class="h-10 w-10 rounded-full bg-blue-50 flex items-center justify-center text-blue-500 font-bold text-lg flex-shrink-0">
                        {device['name'][0] if device['name'] else '?'}
                    </div>
                    <div>
                        <h3 class="text-lg font-bold text-gray-900 leading-tight device-title group-hover:text-blue-600 transition-colors">{device['name']}</h3>
                        <div class="flex items-center gap-2 mt-1">
                            <span class="text-xs font-mono text-gray-400 bg-gray-50 px-1.5 py-0.5 rounded border border-gray-100 device-code">{device['code']}</span>
                            <span class="text-[10px] text-gray-400 bg-gray-50 px-1.5 py-0.5 rounded border border-gray-100">{device['brand']}</span>
                        </div>
                    </div>
                </div>
                
                <div class="flex flex-col items-end">
                    <span class="text-xs text-gray-400 mb-1">台灣更新</span>
                    <span class="text-sm font-bold text-green-600 bg-green-50 px-2 py-1 rounded-md">{tw_date}</span>
                </div>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div class="flex items-center justify-between p-3 rounded-lg bg-blue-50/50 border border-blue-100">
                    <div class="flex items-center gap-3">
                        <span class="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-blue-100 text-blue-700 shadow-sm">台灣版</span>
                        <div>
                            <div class="text-sm font-bold font-mono text-gray-800">{tw_ver}</div>
                            <div class="text-[10px] text-blue-400">Android {tw_android}</div>
                        </div>
                    </div>
                    {f'<span class="text-[10px] px-1.5 py-0.5 rounded {ver_status}">{ver_icon}</span>' if gl else ''}
                </div>
                {gl_info_html}
            </div>
        </div>
    """

html_content += """
    </div>
    
    <div class="max-w-4xl mx-auto px-4 py-8 text-center">
        <p class="text-xs text-gray-400">Generated by GitHub Actions • <a href="#" class="hover:underline">Top</a></p>
    </div>

    <script>
        const searchInput = document.getElementById('searchInput');
        const brandFilter = document.getElementById('brandFilter');

        function filterContent() {
            const searchText = searchInput.value.toLowerCase().trim();
            const selectedBrand = brandFilter.value;
            const cards = document.querySelectorAll('.device-card');
            
            cards.forEach(card => {
                const name = card.querySelector('.device-title').textContent.toLowerCase();
                const code = card.querySelector('.device-code').textContent.toLowerCase();
                const cardBrand = card.getAttribute('data-brand');
                
                const searchTerms = searchText.split(' ');
                const matchText = searchTerms.every(term => name.includes(term) || code.includes(term));
                const matchBrand = (selectedBrand === 'all') || (cardBrand === selectedBrand);
                
                if (matchText && matchBrand) {
                    card.classList.remove('hidden');
                    card.style.opacity = '1';
                    card.style.transform = 'translateY(0)';
                } else {
                    card.classList.add('hidden');
                }
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

print(f"Successfully generated {output_file}")
