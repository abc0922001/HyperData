import OScommon
from datetime import datetime, timedelta
import json
import os
import config
import time
from sys import platform

weekday_number = datetime.now().date().weekday()
weeks = []

for i in range(0 - weekday_number , 7):
	day = datetime.now().date() + timedelta(days=i)
	weeks.append(day.strftime("%Y-%m-%d"))
updates = {
	"recent":{
		"time": "",
		"developing": "no",
		"roms": {}
	}
}
updates["recent"]['time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

for device in OScommon.order:
	devdata = OScommon.localData(device)
	code = devdata['device']
	name = {
		"zh": devdata['name']['zh'],
		"en": devdata['name']['en']
	}
	device_roms = []
	for num in range(len(devdata['branches'])):
		tag = devdata['branches'][num]['idtag']
		branch = devdata["branches"][num]["branchtag"]
		if branch == 'X' or branch == 'D' or "Enterprise" in devdata["branches"][num]["name"]["en"] or "EP" in devdata["branches"][num]["name"]["en"] or "Demo" in devdata["branches"][num]["name"]["en"]:
			i = 0
		else:
			for rom_version, rom_data in devdata['branches'][num]['roms'].items():
				if rom_data['release'] in weeks:
					device_roms.append({
						"release_date": rom_data['release'],
						"version": rom_data['os']
					})
	
	if device_roms:
		updates["recent"]['roms'][code] = {
			"name": name,
			"versions": device_roms
		}

with open('public/data/index.json', 'w', encoding='utf-8') as f:
	json.dump(updates, f, ensure_ascii=False, indent=2)
f.close()
errors = []
for device in OScommon.currentStable:
	if device in OScommon.unreleased:
		i = 0
	else:
		devdata = OScommon.localData(device)
		checker = OScommon.entryChecker(devdata,device)
		devlength = len(devdata["branches"])
		for num in range(devlength): 	
			branch = devdata["branches"][num]["branchtag"]
			if branch == 'X' or branch == 'D' or "Enterprise" in devdata["branches"][num]["name"]["en"] or "EP" in devdata["branches"][num]["name"]["en"]:
				i = 0
			else:
				roms = [list(devdata['branches'][num]["roms"].keys())][0]
				for i in range(len(roms)-1):
					if OScommon.compare(roms[i],roms[i+1]) == False:
						errors.append(1)
						print(device,roms[i],roms[i+1],"版本顺序有误，请核实")
					else:
						i = 0
		if checker ==0:
			i = 0
		else:
			errors.append(1)

if 1 in list(set(errors)):
	print("数据有误，请核实后提交git")
else:
	os.system(f"cd public/data && git add . && git commit -m {updates['recent']['time'].replace(" " , "-")} && git push origin main")
	time.sleep(8)
	os.system(f"curl -X POST \"{config.deploy_url}\"")
	if platform == "win32":
		os.system(f"cls")
	else:
		os.system(f"clear")
	print("数据提交成功")
	print("网站已更新")
