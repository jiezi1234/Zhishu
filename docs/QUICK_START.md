# 🚀 快速参考 - 在AutoClaw中使用Zhishu Agent

## 问题已解决 ✅

AutoClaw现在可以识别并调用Zhishu Agent Skills。

## 立即测试

在AutoClaw中输入以下任何一个：

### 基本用法
```
我想在北京找个好医院看骨科，最好这周能挂上号。
```

### 完整需求
```
我奶奶最近腰疼得厉害，想在北京找个好医院看骨科，最好这周能挂上号，离家近一点最好，生成一份大字版的就医行程单。
```

### 异地就医
```
我从外地来北京，需要看呼吸科，最好能找个评价好的医院。
```

### 显式调用
```
调用healthpath-agent来帮我规划就医方案。
我想在北京找个好医院看骨科，最好这周能挂上号。
```

## 预期结果

AutoClaw会：
1. ✅ 识别就医需求
2. ✅ 调用healthpath-agent
3. ✅ 执行完整的规划流程
4. ✅ 生成PDF行程单
5. ✅ 返回结果

## 工作流程

```
用户输入
  ↓
意图解析 (healthpath-intent-understanding)
  ↓
号源搜索 (healthpath-hospital-crawler)
  ↓
方案决策 (healthpath-decision-engine)
  ↓
PDF生成 (healthpath-output-generator)
  ↓
返回结果
```

## 支持的科室

骨科、神经内科、呼吸科、儿科、心内科、消化科、泌尿科、妇科、眼科、耳鼻喉科

## 支持的城市

北京、上海、广州、深圳、杭州、南京、武汉、成都、西安、重庆

## 支持的时间

- 本周 (this_week)
- 周末 (weekend)
- 晚上 (evening)
- 下周 (next_week)
- 紧急 (urgent)

## 输出格式

- 标准版 (standard) - 一般用户
- 大字版 (large_font) - 老年人
- 详细版 (detailed) - 包含医生简介
- 简洁版 (compact) - 单页纸张

## 如果不工作

1. **重启AutoClaw** - 可能需要重新加载Skills
2. **检查文件** - 验证SKILL.md和_meta.json是否存在
3. **查看日志** - 检查AutoClaw的错误信息

## 文件位置

```
C:\Users\Administrator\.openclaw-autoclaw\skills\
├── healthpath-agent/
├── healthpath-intent-understanding/
├── healthpath-hospital-crawler/
├── healthpath-decision-engine/
└── healthpath-output-generator/
```

每个目录都包含：
- `SKILL.md` - Skill文档
- `_meta.json` - 元数据

---

**现在就可以在AutoClaw中使用Zhishu Agent了！** 🎉
