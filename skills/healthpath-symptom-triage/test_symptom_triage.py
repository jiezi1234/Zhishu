import importlib.util
import pathlib


def _load_module():
    path = pathlib.Path(__file__).with_name("symptom_triage.py")
    spec = importlib.util.spec_from_file_location("symptom_triage_test_module", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_emergency_detection_for_chest_pain_with_dyspnea():
    module = _load_module()
    result = module.triage("剧烈胸痛，呼吸困难", user_profile={"age_group": "adult"})
    assert result["warning_flags"], result


def test_postural_dizziness_should_not_prioritize_ophthalmology():
    module = _load_module()
    result = module.triage("眼前发黑，站起来头晕", user_profile={"age_group": "adult"})
    assert result["recommended_departments"][0] in {"神经内科", "心内科"}, result
    assert "眼科" not in result["recommended_departments"], result


def test_dysuria_should_prioritize_urology():
    module = _load_module()
    result = module.triage("小便刺痛", user_profile={"age_group": "adult"})
    assert result["recommended_departments"][0] == "泌尿科", result
    assert "消化内科" not in result["recommended_departments"], result
    assert "儿科" not in result["recommended_departments"], result


def test_palpitations_should_not_recommend_nephrology():
    module = _load_module()
    result = module.triage("心慌", user_profile={"age_group": "adult"})
    assert result["recommended_departments"][0] == "心内科", result
    assert "肾内科" not in result["recommended_departments"], result


def test_muscle_soreness_should_not_route_to_fever():
    module = _load_module()
    result = module.triage("昨天感觉腿很酸", user_profile={"age_group": "elderly"})
    assert result["recommended_departments"], result
    assert result["recommended_departments"][0] in {"骨科", "康复科", "风湿免疫科"}, result
    assert "发热门诊" not in result["recommended_departments"], result


def test_vague_input_should_trigger_followup():
    module = _load_module()
    result = module.triage("不太舒服", user_profile={"age_group": "adult"})
    assert result["need_more_info"], result
    assert not result["recommended_departments"], result
