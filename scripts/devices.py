import json
from collections import OrderedDict


def load_devices_data():
    """加载 devices.json 数据"""
    with open('public/data/devices.json', 'r', encoding='utf-8') as f:
        return json.load(f)


def get_brand_display_name(brand_key, brand_data):
    """获取品牌的显示名称"""
    if brand_key == 'mi':
        return '小米手机'
    elif brand_key == 'redmi':
        return 'Redmi 手机'
    elif brand_key == 'poco':
        return 'POCO 手机'
    return brand_data.get('zh', brand_key)


def group_devices_by_series(devices):
    """按 series 字段分组设备，保持原始顺序"""
    series_dict = OrderedDict()
    for device in devices:
        series = device.get('series', '其他')
        if series not in series_dict:
            series_dict[series] = []
        series_dict[series].append(device)
    return series_dict


def generate_device_chip(device):
    """生成单个设备的 chip HTML"""
    code = device.get('code', '')
    name_zh = device.get('name', {}).get('zh', '')
    
    # 构建显示文本：中文名(代号)
    display_text = f"{name_zh}({code})"
    
    return f'<div class="mdui-chip"><a href="devices/{code}.json"><span class="mdui-chip-title HyperBlue"> {display_text} </span></a></div>'


def generate_series_section(series_name, devices):
    """生成一个 series 分区的 HTML"""
    html_parts = []
    
    # Series 标题
    html_parts.append(f'<div class="series HyperBlue"> {series_name}：</div>')
    
    # 设备列表
    for device in devices:
        html_parts.append(generate_device_chip(device))
    
    return '\n                '.join(html_parts)


def generate_brand_section(brand_key, brand_data):
    """生成一个品牌分区的 HTML"""
    display_name = get_brand_display_name(brand_key, brand_data)
    devices = brand_data.get('devices', [])
    
    # 按 series 分组
    series_groups = group_devices_by_series(devices)
    
    # 生成 HTML
    html_parts = []
    html_parts.append(f'''        <div id="{brand_key.upper()}" class="mdui-container-fluid">
          <div mdui-panel class="mdui-panel mdui-panel-gapless mdui-shadow-0">
            <div class="mdui-panel-item mdui-panel-item-open">
              <div class="mdui-panel-item-header">
                <div class="mdui-panel-item-title HyperBlue"> {display_name}</div> <i class="mdui-panel-item-arrow mdui-icon material-icons">keyboard_arrow_down</i>
              </div>
              <div class="mdui-panel-item-body">''')
    
    # 添加各个 series 分区
    for series_name, series_devices in series_groups.items():
        html_parts.append('                ' + generate_series_section(series_name, series_devices))
    
    html_parts.append('''              </div>
            </div>
          </div>
        </div>''')
    
    return '\n'.join(html_parts)


def generate_html(data):
    """生成完整的 HTML 文件"""
    # HTML 头部模板
    html_header = '''<!doctype html>
<html data-n-head-ssr lang="zh-CN">

<head>
  <title>HyperOS ROMS Data</title>
  <meta charset="utf-8">
  <meta name="author" content="HegeKen">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta data-hid="description" name="description" content="">
  <meta name="format-detection" content="telephone">
  <link rel="icon" type="image/x-icon" href="https://www.hyperos.fans/favicon.ico">
  <link rel="stylesheet" href="https://data.miuier.com/assets/mdui/css/mdui.min.css">
  <link rel="stylesheet" href="https://cdn-font.hyperos.mi.com/font/css?family=MiSans_VF:VF:Chinese_Simplify,Latin&display=swap">
  <link rel="stylesheet" href="https://data.miuier.com/assets/miuiroms.css">
  <link rel="stylesheet" href="https://at.alicdn.com/t/c/font_2478867_iq2uuq05ql.css">
  <script src="https://data.miuier.com/assets/mdui/js/mdui.min.js"></script>
  <script src="https://data.miuier.com/assets/jquery/jquery.min.js"></script>
  <script defer src='https://static.cloudflareinsights.com/beacon.min.js' data-cf-beacon='{"token": "2c63818efa744adc8db506104596506e"}'></script>
</head>

<body>
  <div>
    <div>
      <div>
        <div>
          <div class="mdui-appbar mdui-appbar-fixed mdui-color-blue-accent mdui-text-color-white">
            <div class="mdui-toolbar"><span class="mdui-typo-title">HyperOS ROMS Data</span>
            </div>
          </div>
          <br />
          <br />
          <br />
        </div> <br>
        <!-- 此处开始自动化替换 -->'''
    
    # HTML 尾部模板
    html_footer = '''        <!-- 此处结束自动化替换 -->
        <div><br> <br> <br>
          <div class="mdui-bottom-nav footer mdui-color-grey-100"><a href="https://github.com/HegeKen" class="mdui-ripple mdui-bottom-nav-active"><i class="mdui-icon icon-GitHub fic"></i><label>GitHub</label></a> <a href="https://gitlab.com/HegeKen" class="mdui-ripple mdui-bottom-nav-active"><i class="mdui-icon icon-gitlab fic"></i><label>GitLab</label></a> <a href="https://weibo.com/Heliljan" class="mdui-ripple mdui-bottom-nav-active"><i class="mdui-icon icon-weibo fic"></i><label>微博</label></a> <a href="https://web.vip.miui.com/page/info/mio/mio/homePage?uid=311975809" class="mdui-ripple mdui-bottom-nav-active"><i class="mdui-icon icon-MiBBS fic"></i><label>小米社区</label></a> <a href="https://space.bilibili.com/19940729" class="mdui-ripple mdui-bottom-nav-active"><i class="mdui-icon icon-bilibili fic"></i><label>哔哩哔哩</label></a> <a href="#top" class="mdui-ripple mdui-bottom-nav-active"><i class="mdui-icon material-icons">arrow_upward</i><label>返回顶部</label></a></div>
          <div class="mdui-bottom-nav footer mdui-color-grey-100 fs">
            <div class="mdui-center mdui-text-center">2023 - 2025 -- 非小米集团旗下网站 . 我们与小米以及Hyper<span class="HyperBlue"> OS</span>开发团队没有任何联系</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</body>
<style>
  .mdui-color-white-accent {
    background-color: #155ffe !important;
  }

  .HyperBlue {
    color: #155ffe !important;
  }
</style>

</html>'''
    
    # 生成品牌分区
    brand_sections = []
    for brand_key in ['mi', 'redmi', 'poco']:
        if brand_key in data:
            brand_sections.append(generate_brand_section(brand_key, data[brand_key]))
    
    # 组合完整 HTML
    html_content = html_header + '\n' + '\n'.join(brand_sections) + '\n' + html_footer
    
    return html_content


def main():
    """主函数"""
    print("正在加载 devices.json...")
    data = load_devices_data()
    
    print("正在生成 index.html...")
    html_content = generate_html(data)
    
    output_path = 'public/data/index.html'
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"成功生成 {output_path}")
    
    # 统计信息
    for brand_key in ['mi', 'redmi', 'poco']:
        if brand_key in data:
            brand_data = data[brand_key]
            devices = brand_data.get('devices', [])
            series_set = set(d.get('series', '其他') for d in devices)
            print(f"{brand_key}: {len(devices)} 个设备, {len(series_set)} 个系列")


if __name__ == '__main__':
    main()
