#!/usr/bin/env python3
"""Integration tests for the unified healthpath skill chain."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from main_skill import execute, get_info
import itinerary_builder


def test_get_info_skills():
    info = get_info()
    assert info["name"] == "HealthPath Agent"
    assert "healthpath-intent-understanding" in info["skills"]
    assert "healthpath-itinerary-builder" in info["skills"]


def test_execute_requests_location_when_missing():
    result = execute(user_input="最近头晕，想看医生")
    assert result["status"] in ("need_location", "need_more_info", "emergency_warning")


def test_execute_full_flow_generates_output():
    out_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "_generated_test")
    os.makedirs(out_dir, exist_ok=True)
    itinerary_builder.OUTPUT_DIR = out_dir
    result = execute(
        user_input="最近腰疼，想看骨科",
        user_location="北京市海淀区",
        selected_hospital="北京大学第三医院",
        output_format="pdf",
        user_profile={"age_group": "adult"},
    )

    assert result["status"] == "success"
    assert "final_output" in result
    pdf_path = result["final_output"].get("pdf_path", "")
    assert pdf_path
    assert os.path.exists(pdf_path)
