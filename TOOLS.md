# TOOLS.md - Local Notes

Skills define _how_ tools work. This file is for _your_ specifics — the stuff that is unique to your setup.

## What Goes Here

Things like:

- Camera names and locations
- SSH hosts and aliases
- Preferred voices for TTS
- Speaker/room names
- Device nicknames
- Anything environment-specific

## Examples

```markdown
### Cameras

- living-room → Main area, 180° wide angle
- front-door → Entrance, motion-triggered

### SSH

- home-server → 192.168.1.100, user: admin

### TTS

- Preferred voice: "Nova" (warm, slightly British)
- Default speaker: Kitchen HomePod
```

## Windows Python Skill 调用最佳实践

**问题：** PowerShell 默认 GBK 编码，直接运行 Python 会导致 `UnicodeEncodeError`（特别是输出含中文和特殊符号时）

**解决方案：** 对于需要 UTF-8 输出的 Python skill（如 healthpath-symptom-triage），使用脚本包装：

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
import json
import os

os.environ['PYTHONIOENCODING'] = 'utf-8'
sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, 'skills/skill-name')
from module import function

result = function(args)
print(json.dumps(result, ensure_ascii=False, indent=2))
```

执行：
```bash
cd E:\homework\Zhishu
$env:PYTHONIOENCODING='utf-8'
python temp_script.py
```

**适用 skill：**
- healthpath-symptom-triage（输出含 ⚠️ 符号）

## Why Separate?

Skills are shared. Your setup is yours. Keeping them apart means you can update skills without losing your notes, and share skills without leaking your infrastructure.

---

Add whatever helps you do your job. This is your cheat sheet.
Do not store passwords, API keys, tokens, or secrets here in plain text.
For sensitive items, use aliases and safe context only.
