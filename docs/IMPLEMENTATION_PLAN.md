# 真实医院数据对接实现计划

## 当前状态

✅ **已完成：**
- 创建HospitalDataAdapter基类框架
- 实现MockDataAdapter（降级方案）
- 创建JingYiTongAdapter和YiHaoAdapter框架
- 实现HospitalDataManager（多源管理和降级）
- 更新hospital_crawler.py集成新框架

## 下一步实现

### Phase 1: 完善114挂号网爬虫（优先）

**文件**: `skills/skill_2_crawl/hospital_adapter.py` - YiHaoAdapter类

```python
class YiHaoAdapter(HospitalDataAdapter):
    def fetch_hospitals(self, city: str = "北京") -> List[Dict]:
        # 使用Playwright访问114网站
        # 解析医院列表
        # 返回标准格式数据
        
    def fetch_available_slots(self, hospital_id: str, department: str, date_range: tuple) -> List[Dict]:
        # 访问医院详情页
        # 解析号源信息
        # 返回标准格式数据
```

**技术方案：**
- 使用Playwright进行浏览器自动化
- BeautifulSoup解析HTML
- 实现反爬虫对策（User-Agent轮换、随机延迟）

**预计工作量**: 3-5天

### Phase 2: 京医通API集成（备选）

**文件**: `skills/skill_2_crawl/hospital_adapter.py` - JingYiTongAdapter类

**前置条件：**
- 申请京医通API密钥
- 获取API文档

**实现步骤：**
1. 配置API认证
2. 实现HTTP请求
3. 解析JSON响应
4. 数据标准化

**预计工作量**: 2-3天

### Phase 3: 缓存机制

**文件**: `skills/skill_2_crawl/cache_manager.py` (新建)

```python
class CacheManager:
    def get_hospitals(self, city: str) -> Optional[List[Dict]]:
        # 检查缓存
        # 如果过期，重新获取
        # 存储到缓存
        
    def get_slots(self, hospital_id: str, department: str) -> Optional[List[Dict]]:
        # 检查缓存
        # 如果过期，重新获取
        # 存储到缓存
```

**缓存策略：**
- 医院信息：24小时过期
- 号源信息：1小时过期
- 使用SQLite本地存储

**预计工作量**: 1-2天

### Phase 4: 错误处理和监控

**文件**: `skills/skill_2_crawl/hospital_adapter.py` - 增强

```python
# 添加重试机制
# 添加日志记录
# 添加性能监控
# 添加数据验证
```

**预计工作量**: 1天

## 测试计划

### 单元测试
```python
# test_hospital_adapter.py
def test_mock_adapter():
    adapter = MockDataAdapter()
    hospitals = adapter.fetch_hospitals()
    assert len(hospitals) > 0
    
def test_adapter_fallback():
    manager = HospitalDataManager()
    hospitals = manager.fetch_hospitals()
    assert len(hospitals) > 0
```

### 集成测试
```python
# test_integration.py
def test_end_to_end():
    task_params = {
        "department": "骨科",
        "target_city": "北京",
        "time_window": "this_week"
    }
    result = search_available_slots(task_params)
    assert result["total_count"] > 0
    assert "data_sources" in result
```

## 时间表

| 阶段 | 任务 | 预计时间 | 状态 |
|------|------|--------|------|
| 1 | 114爬虫实现 | 3-5天 | ⏳ 待开始 |
| 2 | 京医通API集成 | 2-3天 | ⏳ 待开始 |
| 3 | 缓存机制 | 1-2天 | ⏳ 待开始 |
| 4 | 错误处理 | 1天 | ⏳ 待开始 |
| 5 | 测试和优化 | 1-2天 | ⏳ 待开始 |
| **总计** | | **8-13天** | |

## 风险和应对

| 风险 | 概率 | 影响 | 应对方案 |
|------|------|------|--------|
| 114网站结构变更 | 中 | 高 | 定期维护、监控爬虫失败 |
| 反爬虫被封 | 中 | 中 | 使用代理、降低请求频率 |
| 京医通API申请失败 | 低 | 中 | 依赖114爬虫和模拟数据 |
| 性能问题 | 中 | 中 | 实现缓存、异步处理 |

## 成功标准

✅ 系统能从至少一个真实数据源获取医院信息
✅ 系统能获取真实号源信息
✅ 系统能正确处理数据源不可用的情况
✅ 系统性能满足用户体验要求（<5秒响应）
✅ 所有测试通过

## 参考资源

- Playwright文档: https://playwright.dev/python/
- BeautifulSoup文档: https://www.crummy.com/software/BeautifulSoup/
- 114挂号网: https://www.114ygk.com/
- 京医通: https://www.bjguahao.gov.cn/
