import json
import requests
from OScommon import order
from typing import List, Dict, Any, Optional

others = ["MI 5","MI 5s","MI 5s Plus","MIX","Mi Note 2",
	"apollo","begonia","bomb","cepheus","cezanne","chiron","chopin","crux","davinci","dipper","equuleus","gauguinpro","grus","jason",
	"kaiser","katyusha","lmi","lmipro","mars","patriot","penrose","perseus","phoenix","picasso","pissarropro","polaris",
	"pyxis","raphael","renoir","river","rubyplus","rubypro","sagit","tucana","ursa","vangogh","vela","xagapro"]

def analyze_device_models():
	api_url = "https://sf.pay.xiaomi.com/api/device/swipeArea/query"
	headers = {
		"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
		"Accept": "application/json, text/plain, */*",
		"Content-Type": "application/json"
	}
	try:
		response = requests.get(api_url, headers=headers, timeout=10)
		response.raise_for_status()
		data = response.json()
		device_models = extract_device_models(data)
		results = check_models_in_order_and_others(device_models)
		print_statistics(results)
		return results
	except requests.exceptions.RequestException as e:
		print(f"请求失败: {e}")
		return None
	except json.JSONDecodeError as e:
		print(f"JSON解析失败: {e}")
		return None
	except Exception as e:
		print(f"发生错误: {e}")
		import traceback
		traceback.print_exc()
		return None
def extract_device_models(data: Any, models: Optional[List[str]] = None) -> List[str]:
	if models is None:
		models = []
	if isinstance(data, dict):
		for key, value in data.items():
			if key == "deviceModel" and isinstance(value, str):
				models.append(value)
			else:
				extract_device_models(value, models)
	elif isinstance(data, list):
		for item in data:
			extract_device_models(item, models)
	return models
def check_models_in_order_and_others(device_models: List[str]) -> Dict[str, Any]:
	order_set = set(order)	# 转换为集合以提高查找效率
	others_set = set(others)	# 转换为集合以提高查找效率
	exists_in_order_or_others = []
	not_in_both = []
	for model in device_models:
		if model in order_set or model in others_set:
			exists_in_order_or_others.append(model)
		else:
			not_in_both.append(model)
	return {
		"exists": exists_in_order_or_others,
		"not_exists": not_in_both,
		"total": len(device_models),
		"exists_count": len(exists_in_order_or_others),
		"not_exists_count": len(not_in_both)
	}
def print_statistics(results: Dict[str, Any]):
	if results['not_exists_count'] > 0:
		print("不在order和others数组中的设备型号:")
		for i, model in enumerate(results['not_exists'], 1):
			print(f"{i}. {model}")
		print("-" * 60)
if __name__ == "__main__":
	results = analyze_device_models()
	if results:
		pass
	else:
		print("\n分析失败，请检查网络连接或API地址是否正确。")
