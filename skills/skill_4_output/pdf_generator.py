"""
PDF generation module for HealthPath Agent with beautiful, user-friendly design.
Generates appointment itineraries in a warm, accessible format.
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
        font_paths = [
            "C:\\Windows\\Fonts\\simhei.ttf",
            "C:\\Windows\\Fonts\\simsun.ttc",
            "C:\\Windows\\Fonts\\msyh.ttc",
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
    Generate a beautiful, user-friendly PDF document with appointment recommendations.
    """

    if not REPORTLAB_AVAILABLE:
        generate_text_pdf(recommendations, task_params, output_path, large_font)
        return

    chinese_font = register_chinese_fonts()
    if not chinese_font:
        generate_text_pdf(recommendations, task_params, output_path, large_font)
        return

    # Create PDF document
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=0.6*inch,
        leftMargin=0.6*inch,
        topMargin=0.8*inch,
        bottomMargin=0.8*inch
    )

    elements = []

    # Define styles
    if large_font:
        title_size = 28
        emoji_size = 24
        heading_size = 18
        normal_size = 16
        small_size = 14
    else:
        title_size = 20
        emoji_size = 18
        heading_size = 14
        normal_size = 12
        small_size = 10

    title_style = ParagraphStyle(
        'Title',
        fontName=chinese_font,
        fontSize=title_size,
        textColor=colors.HexColor('#FF6B6B'),
        spaceAfter=6,
        alignment=TA_CENTER,
        leading=title_size + 4
    )

    emoji_heading_style = ParagraphStyle(
        'EmojiHeading',
        fontName=chinese_font,
        fontSize=heading_size,
        textColor=colors.HexColor('#FF6B6B'),
        spaceAfter=12,
        spaceBefore=12,
        leading=heading_size + 4
    )

    normal_style = ParagraphStyle(
        'Normal',
        fontName=chinese_font,
        fontSize=normal_size,
        textColor=colors.HexColor('#333333'),
        spaceAfter=8,
        leading=normal_size + 4
    )

    small_style = ParagraphStyle(
        'Small',
        fontName=chinese_font,
        fontSize=small_size,
        textColor=colors.HexColor('#666666'),
        spaceAfter=6,
        leading=small_size + 2
    )

    # Title
    elements.append(Paragraph("👵 就医行程单", title_style))
    elements.append(Paragraph(f"(本文件采用 {title_size}号超大字体生成，方便阅读)", small_style))
    elements.append(Spacer(1, 0.15*inch))

    # Main recommendation
    if recommendations:
        rec = recommendations[0]

        # 🏥 最重要的就诊信息
        elements.append(Paragraph("🏥 最重要的就诊信息", emoji_heading_style))

        info_data = [
            ["去哪个医院：", f"{rec['hospital_name']}（距离 {rec['distance_km']} 公里，已为您挂好号了）"],
            ["看什么科室：", f"{task_params.get('department', '未指定')}"],
            ["看哪位医生：", f"{rec['doctor_name']} {rec['doctor_title']}"],
            ["什么时间去：", f"{rec['appointment_time']}"],
            ["预计排队：", f"约 {rec['queue_estimate_min']} 分钟"],
        ]

        info_table = Table(info_data, colWidths=[1.8*inch, 3.8*inch])
        info_table.setStyle(TableStyle([
            ('FONT', (0, 0), (-1, -1), chinese_font, normal_size),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#FF6B6B')),
            ('TEXTCOLOR', (1, 0), (1, -1), colors.HexColor('#333333')),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('LINEBELOW', (0, 0), (-1, -1), 0.5, colors.HexColor('#EEEEEE')),
        ]))
        elements.append(info_table)
        elements.append(Spacer(1, 0.2*inch))

        # 🚗 怎么去医院最方便？
        elements.append(Paragraph("🚗 怎么去医院最方便？", emoji_heading_style))
        elements.append(Paragraph(
            f"推荐打车：大概需要 {rec['total_travel_time_min']} 分钟。您可以让家人帮您在手机上叫个车，直接送到医院。",
            normal_style
        ))
        elements.append(Spacer(1, 0.08*inch))
        elements.append(Paragraph(
            f"综合评分：{rec['score']}/10 分 - {rec['reason']}",
            normal_style
        ))
        elements.append(Spacer(1, 0.2*inch))

        # 🎒 出门前检查清单
        elements.append(Paragraph("🎒 出门前，请检查带好这些东西：", emoji_heading_style))
        elements.append(Paragraph("(可以照着打个勾 ✅)", small_style))

        checklist_items = [
            "[ ] 身份证 （千万别忘了）",
            "[ ] 医保卡 / 社保卡",
            "[ ] 手机 & 充电宝",
            "[ ] 钱包 / 支付宝",
        ]

        for item in checklist_items:
            elements.append(Paragraph(item, normal_style))

        elements.append(Spacer(1, 0.15*inch))

        # 💡 特别提醒
        elements.append(Paragraph(
            "💡 特别提醒：请提前 15 分钟到达医院，以便完成挂号和分诊。如果到了医院不知道怎么走，可以直接问医院工作人员。",
            normal_style
        ))
        elements.append(Spacer(1, 0.2*inch))

        # 其他推荐方案
        if len(recommendations) > 1:
            elements.append(Paragraph("📋 其他推荐方案", emoji_heading_style))

            for idx, alt_rec in enumerate(recommendations[1:], 2):
                alt_data = [
                    [f"方案 {idx}：", f"{alt_rec['hospital_name']}"],
                    ["医生：", f"{alt_rec['doctor_name']} {alt_rec['doctor_title']}"],
                    ["时间：", alt_rec['appointment_time']],
                    ["评分：", f"{alt_rec['score']}/10"],
                ]

                alt_table = Table(alt_data, colWidths=[1.5*inch, 4.1*inch])
                alt_table.setStyle(TableStyle([
                    ('FONT', (0, 0), (-1, -1), chinese_font, small_size),
                    ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#FF6B6B')),
                    ('TEXTCOLOR', (1, 0), (1, -1), colors.HexColor('#666666')),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('LEFTPADDING', (0, 0), (-1, -1), 6),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                    ('TOPPADDING', (0, 0), (-1, -1), 4),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                    ('LINEBELOW', (0, 0), (-1, -1), 0.5, colors.HexColor('#EEEEEE')),
                ]))
                elements.append(alt_table)
                elements.append(Spacer(1, 0.1*inch))

    else:
        elements.append(Paragraph("未找到匹配的号源，请稍后重试。", normal_style))

    elements.append(Spacer(1, 0.2*inch))

    # Footer
    footer_text = "❤️ 祝您就医顺利！本文件仅供参考，具体挂号请以医院官网为准。"
    footer_style = ParagraphStyle(
        'Footer',
        fontName=chinese_font,
        fontSize=small_size,
        textColor=colors.HexColor('#FF6B6B'),
        alignment=TA_CENTER
    )
    elements.append(Paragraph(footer_text, footer_style))

    # Build PDF
    doc.build(elements)


def generate_text_pdf(recommendations: List[Dict], task_params: Dict, output_path: str, large_font: bool = False):
    """
    Fallback: Generate text-based PDF.
    """

    lines = []

    lines.append("👵 就医行程单")
    lines.append("")
    lines.append(f"(本文件采用 {'24' if large_font else '12'}号超大字体生成，方便阅读)")
    lines.append("")
    lines.append("=" * 70)
    lines.append("")

    if recommendations:
        rec = recommendations[0]

        lines.append("🏥 最重要的就诊信息")
        lines.append("")
        lines.append(f"去哪个医院：{rec['hospital_name']}（距离 {rec['distance_km']} 公里，已为您挂好号了）")
        lines.append(f"看什么科室：{task_params.get('department', '未指定')}")
        lines.append(f"看哪位医生：{rec['doctor_name']} {rec['doctor_title']}")
        lines.append(f"什么时间去：{rec['appointment_time']}")
        lines.append(f"预计排队：约 {rec['queue_estimate_min']} 分钟")
        lines.append("")

        lines.append("🚗 怎么去医院最方便？")
        lines.append("")
        lines.append(f"推荐打车：大概需要 {rec['total_travel_time_min']} 分钟。您可以让家人帮您在手机上叫个车，直接送到医院。")
        lines.append("")
        lines.append(f"综合评分：{rec['score']}/10 分 - {rec['reason']}")
        lines.append("")

        lines.append("🎒 出门前，请检查带好这些东西：")
        lines.append("")
        lines.append("(可以照着打个勾 ✅)")
        lines.append("")
        lines.append("[ ] 身份证 （千万别忘了）")
        lines.append("[ ] 医保卡 / 社保卡")
        lines.append("[ ] 手机 & 充电宝")
        lines.append("[ ] 钱包 / 支付宝")
        lines.append("")

        lines.append("💡 特别提醒：请提前 15 分钟到达医院，以便完成挂号和分诊。")
        lines.append("")

        if len(recommendations) > 1:
            lines.append("📋 其他推荐方案")
            lines.append("")
            for idx, alt_rec in enumerate(recommendations[1:], 2):
                lines.append(f"方案 {idx}：{alt_rec['hospital_name']}")
                lines.append(f"  医生：{alt_rec['doctor_name']} {alt_rec['doctor_title']}")
                lines.append(f"  时间：{alt_rec['appointment_time']}")
                lines.append(f"  评分：{alt_rec['score']}/10")
                lines.append("")

    else:
        lines.append("未找到匹配的号源，请稍后重试。")
        lines.append("")

    lines.append("=" * 70)
    lines.append("")
    lines.append("❤️ 祝您就医顺利！本文件仅供参考，具体挂号请以医院官网为准。")

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(lines))
