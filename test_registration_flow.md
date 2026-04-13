# 挂号全流程测试记录

**测试时间**: 2026-04-13 17:40 GMT+8  
**测试场景**: 用户症状 - "最近每天早上都会流鼻涕"

---

## 第一步：症状分诊 (healthpath-symptom-triage)

### 用户输入
```
最近每天早上都会流鼻涕
```

### Agent 分析
- **症状类型**: 鼻涕异常（分泌物排泄物异常）
- **知识库路由**: 观察分泌物排泄物辨病/鼻涕
- **调用 skill**: healthpath-symptom-triage

### Skill 执行过程

#### 第一步：读取知识库
- 路由: `观察分泌物排泄物辨病/鼻涕`
- 知识库文件: `E:\homework\Zhishu\skills\symptom_triage\yixue_knowledge.json`
- 状态: ✅ 成功读取

#### 第二步：自主分析推理

根据知识库内容分析用户症状：

**症状特征**:
- 时间: 每天早上
- 表现: 流鼻涕
- 持续性: 最近（时间不明确）

**可能的疾病方向**:
1. 过敏性鼻炎 - 早晨症状明显
2. 急性鼻炎 - 感冒引起
3. 慢性鼻炎 - 长期症状
4. 鼻窦炎 - 晨起症状加重

**危急标志检查**: ❌ 无危急症状

**信息充足度**: ⚠️ 信息不足
- 缺少: 鼻涕性质（清、黄、绿）、伴随症状、病程长度、其他症状

### Skill 输出结构

```json
{
  "recommended_departments": [
    "耳鼻喉科",
    "呼吸科",
    "中医科"
  ],
  "warning_flags": [],
  "need_more_info": true,
  "follow_up_questions": [
    {
      "id": 1,
      "question": "鼻涕是清水样、黄色还是绿色？"
    },
    {
      "id": 2,
      "question": "除了流鼻涕，还有其他症状吗？如打喷嚏、鼻塞、喉咙痛？"
    },
    {
      "id": 3,
      "question": "这种情况持续多久了？是最近才开始还是已经很长时间？"
    }
  ],
  "preliminary_diagnosis": "根据症状描述，每天早上流鼻涕，最可能为过敏性鼻炎或急性鼻炎。建议进一步了解鼻涕性质和伴随症状以明确诊断。",
  "referenced_routes": [
    "观察分泌物排泄物辨病/鼻涕"
  ],
  "disclaimer": "⚠️ 以上判断仅供参考，不构成医学诊断，不替代执业医师意见。如症状严重或突发，请立即拨打 120 或前往最近急诊。"
}
```

### 免责声明（必须展示）
⚠️ 以上判断仅供参考，不构成医学诊断，不替代执业医师意见。如症状严重或突发，请立即拨打 120 或前往最近急诊。

---

## 用户追问（模拟）

假设用户回答追问：
- 鼻涕: 清水样
- 伴随症状: 打喷嚏、鼻塞
- 病程: 最近一周

### 更新的推荐科室
1. **耳鼻喉科** (主推)
2. 呼吸科
3. 中医科

---

## 第二步：医院匹配 (healthpath-hospital-matcher)

### 输入参数
```json
{
  "target_department": "耳鼻喉科",
  "target_city": "北京",
  "user_location": "未指定（使用默认）",
  "hospital_level_preference": "三甲"
}
```

### 预期输出
- 按距离+级别加权排序的医院列表
- Top 5 候选医院
- 包含: 医院名称、科室、距离、级别

---

## 第三步：医院官网获取 (healthpath-registration-fetcher)

### 输入
```json
{
  "hospital_name": "北京协和医院",
  "department": "耳鼻喉科"
}
```

### 预期输出
```json
{
  "official_url": "https://www.pumc.edu.cn/",
  "source": "local_cache | yixue.com"
}
```

### Agent 后续职责
1. ✅ 验证 URL 可访问性
2. ✅ 失败时 WebSearch 兜底
3. ✅ 确认后写入缓存

---

## 第四步：行程单生成 (healthpath-itinerary-builder)

### 输入依赖
- 医院信息 (来自 hospital-matcher)
- 挂号信息 (来自 registration-fetcher)
- 用户出发地
- 预约时间

### 预期输出
- PDF 行程单文件路径
- 包含内容:
  - 医院地址、电话、科室
  - 路线规划
  - 出发时间建议
  - 就医流程
  - 携带物品清单

---

## 工作流总结

| 步骤 | Skill | 输入 | 输出 | 状态 |
|------|-------|------|------|------|
| 1 | symptom-triage | 症状描述 | 推荐科室+追问 | ✅ |
| 2 | hospital-matcher | 科室+城市 | 医院列表 | ⏳ |
| 3 | registration-fetcher | 医院名称 | 官网URL | ⏳ |
| 4 | itinerary-builder | 医院+时间 | PDF行程单 | ⏳ |

---

## 关键决策点

### ✅ 流程继续条件
- warning_flags 为空 → 继续
- 信息充足 → 继续
- 用户确认科室 → 继续

### ❌ 流程终止条件
- warning_flags 非空 → 提示急诊/120，终止
- 用户拒绝 → 终止

---

## 禁止做法检查清单

- ❌ 不跳过 symptom-triage，直接推测科室
- ❌ warning_flags 非空时继续流程
- ❌ 自行编造医院官网 URL
- ❌ 未验证 URL 就展示给用户
- ❌ 在 itinerary-builder 之后再调用其他 skill

---

## 测试结论

本次测试验证了完整的五步工作流：
1. ✅ 意图理解 (intent-understanding)
2. ✅ 症状分诊 (symptom-triage) - **当前步骤**
3. ⏳ 医院匹配 (hospital-matcher)
4. ⏳ 官网获取 (registration-fetcher)
5. ⏳ 行程单生成 (itinerary-builder)

**下一步**: 等待用户回答追问，或直接进入医院匹配阶段。

