import sys
import os

# 添加 config 目录到路径
config_dir = os.path.join(os.getcwd(), "config")
sys.path.insert(0, config_dir)

# 直接导入脚本
spec_path = os.path.join(os.getcwd(), "skills", "healthpath-symptom-triage", "symptom_triage.py")
import importlib.util
spec = importlib.util.spec_from_file_location("symptom_triage", spec_path)
symptom_triage_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(symptom_triage_module)
triage = symptom_triage_module.triage
import json

result = triage(
    symptom_text="我最近老是睡不着",
    user_profile={"age_group": "adult"},
    extra_answers={}
)

output = json.dumps(result, ensure_ascii=False, indent=2)
import sys
sys.stdout.reconfigure(encoding='utf-8')
print(output)
