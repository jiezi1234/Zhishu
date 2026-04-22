import os
import sys

sys.path.insert(
    0,
    os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "skills",
        "healthpath-symptom-triage",
    ),
)

import symptom_triage


def test_emergency_detection_for_chest_pain_with_dyspnea():
    result = symptom_triage.triage("剧烈胸痛，呼吸困难", user_profile={"age_group": "adult"})
    assert result["warning_flags"], result


def test_postural_dizziness_should_not_prioritize_ophthalmology():
    result = symptom_triage.triage("眼前发黑，站起来头晕", user_profile={"age_group": "adult"})
    assert result["recommended_departments"][0] in {"神经内科", "心内科"}, result
    assert "眼科" not in result["recommended_departments"], result


def test_dysuria_should_prioritize_urology():
    result = symptom_triage.triage("小便刺痛", user_profile={"age_group": "adult"})
    assert result["recommended_departments"][0] == "泌尿科", result
    assert "消化内科" not in result["recommended_departments"], result
    assert "儿科" not in result["recommended_departments"], result


def test_palpitations_should_not_recommend_nephrology():
    result = symptom_triage.triage("心慌", user_profile={"age_group": "adult"})
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
