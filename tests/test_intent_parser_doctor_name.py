import os
import sys
import types

# 在导入 intent_parser 之前,先用 fake semantic_matcher 替掉,避免拉 sentence_transformers。
# extract_doctor_name 是纯规则逻辑,不依赖语义匹配;parse_intent 本地分支会调 search_knowledge,
# 返回 [] 即走规则兜底,对本测试无影响。
_fake_sm = types.ModuleType("semantic_matcher")
_fake_sm.search_knowledge = lambda text, k=1: []
sys.modules.setdefault("semantic_matcher", _fake_sm)

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "skills", "healthpath-intent-understanding"
))

from intent_parser import extract_doctor_name, parse_intent


def test_extract_explicit_doctor_with_keyword():
    assert extract_doctor_name("我要挂协和医院王立凡医生的号") == "王立凡"
    assert extract_doctor_name("挂张铁柱主任的号") == "张铁柱"
    assert extract_doctor_name("找李小红大夫看看") == "李小红"


def test_extract_returns_empty_when_no_doctor():
    assert extract_doctor_name("最近头疼,想看神经内科") == ""
    assert extract_doctor_name("帮我找北京协和医院的号") == ""


def test_extract_skips_stopwords():
    # "医生" 本身不是名字
    assert extract_doctor_name("我要找个医生看看") == ""
    # "专家" 也不应该当人名
    assert extract_doctor_name("找个专家看看") == ""


def test_extract_skips_hospital_and_dept_names():
    # 协和/神经内科 不应被当成人名(含"医院""科")
    assert extract_doctor_name("协和医院神经内科的号") == ""


def test_parse_intent_returns_doctor_name_field():
    r = parse_intent("我要挂协和医院王立凡医生的号", use_deepseek=False)
    assert r["doctor_name"] == "王立凡"


def test_parse_intent_doctor_empty_when_unspecified():
    r = parse_intent("最近头疼想看神经内科", use_deepseek=False)
    assert r["doctor_name"] == ""
