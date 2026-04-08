"""
PDF generation module for HealthPath Agent.
Generates appointment itineraries in PDF format with support for large fonts.
"""

import os
from datetime import datetime
from typing import List, Dict

try:
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch, cm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False


def generate_pdf_document(recommendations: List[Dict], task_params: Dict, output_path: str, large_font: bool = False):
    """
    Generate a PDF document with appointment recommendations.

    Args:
        recommendations: List of ranked recommendations
        task_params: Original task parameters
        output_path: Path to save the PDF file
        large_font: Whether to use large fonts for elderly users
    """

    if not REPORTLAB_AVAILABLE:
        # Fallback: generate text-based PDF
        generate_text_pdf(recommendations, task_params, output_path, large_font)
        return

    # Create PDF document
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=0.5*inch,
        leftMargin=0.5*inch,
        topMargin=0.75*inch,
        bottomMargin=0.75*inch
    )

    # Container for PDF elements
    elements = []

    # Define styles
    styles = getSampleStyleSheet()

    if large_font:
        # Large font styles for elderly users
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=28,
            textColor=colors.HexColor('#000000'),
            spaceAfter=20,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        )
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=18,
            textColor=colors.HexColor('#1f4788'),
            spaceAfter=12,
            spaceBefore=12,
            fontName='Helvetica-Bold'
        )
        normal_style = ParagraphStyle(
            'CustomNormal',
            parent=styles['Normal'],
            fontSize=16,
            textColor=colors.HexColor('#000000'),
            spaceAfter=8,
            leading=24
        )
    else:
        # Standard font sizes
        title_style = styles['Heading1']
        heading_style = styles['Heading2']
        normal_style = styles['Normal']

    # Title
    elements.append(Paragraph("就医行程单", title_style))
    elements.append(Spacer(1, 0.3*inch))

    # Generation timestamp
    timestamp_text = f"生成时间：{datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}"
    elements.append(Paragraph(timestamp_text, normal_style))
    elements.append(Spacer(1, 0.2*inch))

    # Task information section
    elements.append(Paragraph("【就医需求】", heading_style))

    task_info = [
        f"科室：{task_params.get('department', '未指定')}",
        f"症状：{task_params.get('symptom', '未指定')}",
        f"时间要求：{task_params.get('time_window', '本周')}",
    ]

    if task_params.get('special_requirements'):
        task_info.append(f"特殊需求：{task_params.get('special_requirements')}")

    for info in task_info:
        elements.append(Paragraph(info, normal_style))

    elements.append(Spacer(1, 0.2*inch))

    # Recommendations section
    elements.append(Paragraph("【推荐方案】", heading_style))

    if recommendations:
        for rec in recommendations:
            elements.append(Spacer(1, 0.1*inch))

            # Recommendation header
            rec_header = f"方案 {rec['rank']}：{rec['hospital_name']}"
            elements.append(Paragraph(rec_header, ParagraphStyle(
                'RecHeader',
                parent=normal_style,
                fontSize=16 if large_font else 12,
                fontName='Helvetica-Bold',
                textColor=colors.HexColor('#1f4788')
            )))

            # Recommendation details
            rec_details = [
                f"医生：{rec['doctor_name']}（{rec['doctor_title']}）",
                f"挂号时间：{rec['appointment_time']}",
                f"挂号费：{rec['total_cost']} 元",
                f"预计排队：{rec['queue_estimate_min']} 分钟",
                f"距离：{rec['distance_km']} 公里",
                f"交通时间：{rec['total_travel_time_min']} 分钟",
                f"综合评分：{rec['score']}/10",
                f"推荐理由：{rec['reason']}"
            ]

            for detail in rec_details:
                elements.append(Paragraph(detail, normal_style))

    else:
        elements.append(Paragraph("未找到匹配的号源", normal_style))

    elements.append(Spacer(1, 0.3*inch))

    # Footer
    footer_text = "提示：本文件仅供参考，具体挂号请以医院官网为准"
    elements.append(Paragraph(footer_text, ParagraphStyle(
        'Footer',
        parent=normal_style,
        fontSize=10,
        textColor=colors.HexColor('#666666'),
        alignment=TA_CENTER
    )))

    # Build PDF
    doc.build(elements)


def generate_text_pdf(recommendations: List[Dict], task_params: Dict, output_path: str, large_font: bool = False):
    """
    Fallback: Generate text-based PDF (saved as text file with .pdf extension).
    """

    lines = []

    if large_font:
        lines.append("=" * 80)
        lines.append("就医行程单（大字版）".center(80))
        lines.append("=" * 80)
    else:
        lines.append("=" * 60)
        lines.append("就医行程单".center(60))
        lines.append("=" * 60)

    lines.append("")
    lines.append(f"生成时间：{datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}")
    lines.append("")

    lines.append("【就医需求】")
    lines.append(f"科室：{task_params.get('department', '未指定')}")
    lines.append(f"症状：{task_params.get('symptom', '未指定')}")
    lines.append(f"时间要求：{task_params.get('time_window', '本周')}")
    if task_params.get('special_requirements'):
        lines.append(f"特殊需求：{task_params.get('special_requirements')}")
    lines.append("")

    lines.append("【推荐方案】")
    if recommendations:
        for rec in recommendations:
            lines.append("")
            lines.append(f"方案 {rec['rank']}：{rec['hospital_name']}")
            lines.append(f"医生：{rec['doctor_name']}（{rec['doctor_title']}）")
            lines.append(f"挂号时间：{rec['appointment_time']}")
            lines.append(f"挂号费：{rec['total_cost']} 元")
            lines.append(f"预计排队：{rec['queue_estimate_min']} 分钟")
            lines.append(f"距离：{rec['distance_km']} 公里")
            lines.append(f"交通时间：{rec['total_travel_time_min']} 分钟")
            lines.append(f"综合评分：{rec['score']}/10")
            lines.append(f"推荐理由：{rec['reason']}")
    else:
        lines.append("未找到匹配的号源")

    lines.append("")
    lines.append("=" * 60)
    lines.append("提示：本文件仅供参考，具体挂号请以医院官网为准")
    lines.append("=" * 60)

    # Save as text file
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(lines))
