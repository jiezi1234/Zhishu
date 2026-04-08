"""
PDF generation module for HealthPath Agent with Chinese font support.
Generates beautiful appointment itineraries in PDF format.
"""

import os
from datetime import datetime
from typing import List, Dict

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch, cm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False


def register_chinese_fonts():
    """Register Chinese fonts for reportlab"""
    try:
        # Try to register system fonts
        font_paths = [
            "C:\\Windows\\Fonts\\simhei.ttf",      # 黑体
            "C:\\Windows\\Fonts\\simsun.ttc",      # 宋体
            "C:\\Windows\\Fonts\\msyh.ttc",        # 微软雅黑
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",  # Linux
            "/System/Library/Fonts/Arial.ttf",     # macOS
        ]

        for font_path in font_paths:
            if os.path.exists(font_path):
                try:
                    if "simhei" in font_path.lower():
                        pdfmetrics.registerFont(TTFont("SimHei", font_path))
                        return "SimHei"
                    elif "msyh" in font_path.lower():
                        pdfmetrics.registerFont(TTFont("MSYH", font_path))
                        return "MSYH"
                    elif "simsun" in font_path.lower():
                        pdfmetrics.registerFont(TTFont("SimSun", font_path))
                        return "SimSun"
                except:
                    continue
    except:
        pass

    return None


def generate_pdf_document(recommendations: List[Dict], task_params: Dict, output_path: str, large_font: bool = False):
    """
    Generate a beautiful PDF document with appointment recommendations.

    Args:
        recommendations: List of ranked recommendations
        task_params: Original task parameters
        output_path: Path to save the PDF file
        large_font: Whether to use large fonts for elderly users
    """

    if not REPORTLAB_AVAILABLE:
        generate_text_pdf(recommendations, task_params, output_path, large_font)
        return

    # Register Chinese fonts
    chinese_font = register_chinese_fonts()
    if not chinese_font:
        # Fallback to text PDF if no Chinese font available
        generate_text_pdf(recommendations, task_params, output_path, large_font)
        return

    # Create PDF document
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=0.8*inch,
        leftMargin=0.8*inch,
        topMargin=1*inch,
        bottomMargin=0.8*inch
    )

    # Container for PDF elements
    elements = []

    # Define styles with Chinese font
    if large_font:
        # Large font styles for elderly users
        title_style = ParagraphStyle(
            'CustomTitle',
            fontName=chinese_font,
            fontSize=32,
            textColor=colors.HexColor('#1f4788'),
            spaceAfter=24,
            alignment=TA_CENTER,
            leading=40
        )
        heading_style = ParagraphStyle(
            'CustomHeading',
            fontName=chinese_font,
            fontSize=20,
            textColor=colors.HexColor('#1f4788'),
            spaceAfter=14,
            spaceBefore=14,
            leading=28
        )
        normal_style = ParagraphStyle(
            'CustomNormal',
            fontName=chinese_font,
            fontSize=18,
            textColor=colors.HexColor('#333333'),
            spaceAfter=10,
            leading=26
        )
        label_style = ParagraphStyle(
            'Label',
            fontName=chinese_font,
            fontSize=16,
            textColor=colors.HexColor('#555555'),
            spaceAfter=8,
            leading=24
        )
    else:
        # Standard font sizes
        title_style = ParagraphStyle(
            'CustomTitle',
            fontName=chinese_font,
            fontSize=24,
            textColor=colors.HexColor('#1f4788'),
            spaceAfter=20,
            alignment=TA_CENTER,
            leading=32
        )
        heading_style = ParagraphStyle(
            'CustomHeading',
            fontName=chinese_font,
            fontSize=16,
            textColor=colors.HexColor('#1f4788'),
            spaceAfter=12,
            spaceBefore=12,
            leading=24
        )
        normal_style = ParagraphStyle(
            'CustomNormal',
            fontName=chinese_font,
            fontSize=12,
            textColor=colors.HexColor('#333333'),
            spaceAfter=8,
            leading=18
        )
        label_style = ParagraphStyle(
            'Label',
            fontName=chinese_font,
            fontSize=11,
            textColor=colors.HexColor('#555555'),
            spaceAfter=6,
            leading=16
        )

    # Title
    elements.append(Paragraph("就医行程单", title_style))
    elements.append(Spacer(1, 0.2*inch))

    # Generation timestamp
    timestamp_text = f"生成时间：{datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}"
    elements.append(Paragraph(timestamp_text, label_style))
    elements.append(Spacer(1, 0.15*inch))

    # Task information section with background
    elements.append(Paragraph("【就医需求】", heading_style))
    elements.append(Spacer(1, 0.08*inch))

    task_info_data = [
        [f"科室：", f"{task_params.get('department', '未指定')}"],
        [f"症状：", f"{task_params.get('symptom', '未指定')}"],
        [f"时间：", f"{task_params.get('time_window', '本周')}"],
    ]

    if task_params.get('special_requirements'):
        task_info_data.append([f"特殊需求：", f"{task_params.get('special_requirements')}"])

    task_table = Table(task_info_data, colWidths=[1.5*inch, 4*inch])
    task_table.setStyle(TableStyle([
        ('FONT', (0, 0), (-1, -1), chinese_font, 11 if not large_font else 14),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#1f4788')),
        ('TEXTCOLOR', (1, 0), (1, -1), colors.HexColor('#333333')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, colors.HexColor('#f5f5f5')]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e0e0e0')),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(task_table)
    elements.append(Spacer(1, 0.2*inch))

    # Recommendations section
    elements.append(Paragraph("【推荐方案】", heading_style))
    elements.append(Spacer(1, 0.08*inch))

    if recommendations:
        for idx, rec in enumerate(recommendations, 1):
            # Recommendation header with background
            rec_header = f"方案 {rec['rank']}：{rec['hospital_name']}"
            rec_header_style = ParagraphStyle(
                f'RecHeader{idx}',
                fontName=chinese_font,
                fontSize=14 if not large_font else 18,
                textColor=colors.white,
                spaceAfter=10,
                spaceBefore=10,
                leading=20
            )

            # Create a table for the header with background color
            header_table = Table([[rec_header]], colWidths=[6.5*inch])
            header_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#1f4788')),
                ('FONT', (0, 0), (-1, -1), chinese_font, 14 if not large_font else 18),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 10),
                ('RIGHTPADDING', (0, 0), (-1, -1), 10),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ]))
            elements.append(header_table)
            elements.append(Spacer(1, 0.08*inch))

            # Recommendation details in table format
            rec_details_data = [
                ["医生", f"{rec['doctor_name']}（{rec['doctor_title']}）"],
                ["挂号时间", rec['appointment_time']],
                ["挂号费", f"{rec['total_cost']} 元"],
                ["预计排队", f"{rec['queue_estimate_min']} 分钟"],
                ["距离", f"{rec['distance_km']} 公里"],
                ["交通时间", f"{rec['total_travel_time_min']} 分钟"],
                ["综合评分", f"{rec['score']}/10"],
                ["推荐理由", rec['reason']],
            ]

            details_table = Table(rec_details_data, colWidths=[1.5*inch, 4*inch])
            details_table.setStyle(TableStyle([
                ('FONT', (0, 0), (-1, -1), chinese_font, 10 if not large_font else 13),
                ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#1f4788')),
                ('TEXTCOLOR', (1, 0), (1, -1), colors.HexColor('#333333')),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, colors.HexColor('#f9f9f9')]),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e0e0e0')),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ]))
            elements.append(details_table)
            elements.append(Spacer(1, 0.15*inch))

    else:
        elements.append(Paragraph("未找到匹配的号源", normal_style))

    elements.append(Spacer(1, 0.2*inch))

    # Footer
    footer_text = "提示：本文件仅供参考，具体挂号请以医院官网为准"
    footer_style = ParagraphStyle(
        'Footer',
        fontName=chinese_font,
        fontSize=9,
        textColor=colors.HexColor('#999999'),
        alignment=TA_CENTER
    )
    elements.append(Paragraph(footer_text, footer_style))

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
