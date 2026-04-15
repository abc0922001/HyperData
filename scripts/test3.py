import OScommon
import json

file = open("public/data/scripts/NewROMs.txt", "r", encoding='utf-8')
lines = file.readlines()
for line in lines:
  line = line.rstrip()
  if line == "":
    continue
  else:
    if line.startswith("http"):
      line = line.split("/")[4].split("?")[0]
    else:
      i = 0
    device, code, android, version, rom_type, bigver, region,tag,zone, branch, filetype = [item for item in OScommon.getData(line)]
    OScommon.checkDatabase(device, code, android, version, rom_type, bigver, region,tag,zone, branch, filetype, line)
    updated_devdata = OScommon.add_rom_to_json(device, code, android, version, filetype, line, OScommon.localData(device))
    if updated_devdata:
      device_file = OScommon.get_platform_path(f"public/data/devices/{device}.json")
      with open(device_file, 'w', encoding='utf-8') as f:
        json.dump(updated_devdata, f, ensure_ascii=False, indent='\t', sort_keys=False)