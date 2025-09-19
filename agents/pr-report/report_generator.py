"""
PDF Report Generator Module

This module provides functionality to generate PDF reports from categorized news articles.
It creates professional-looking reports with proper formatting and structure.
"""

from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor
from datetime import datetime
import io
from typing import List, Dict, Any


def generate_report_pdf(subject: str, sections: List[Dict[str, Any]]) -> bytes:
    """
    Generate a PDF report from categorized news sections.
    
    Args:
        subject: The report subject/title
        sections: List of sections with headings and items
        
    Returns:
        PDF content as bytes
    """
    # Create a BytesIO buffer to hold the PDF
    buffer = io.BytesIO()
    
    # Create the PDF document
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=18
    )
    
    # Get styles
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Title'],
        fontSize=18,
        spaceAfter=30,
        textColor=HexColor('#2E3440')
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        spaceAfter=12,
        spaceBefore=20,
        textColor=HexColor('#5E81AC')
    )
    
    body_style = ParagraphStyle(
        'CustomBody',
        parent=styles['Normal'],
        fontSize=10,
        spaceAfter=8,
        leftIndent=20
    )
    
    link_style = ParagraphStyle(
        'LinkStyle',
        parent=styles['Normal'],
        fontSize=9,
        textColor=HexColor('#81A1C1'),
        leftIndent=20
    )
    
    source_style = ParagraphStyle(
        'SourceStyle',
        parent=styles['Normal'],
        fontSize=8,
        textColor=HexColor('#4C566A'),
        leftIndent=20,
        spaceAfter=12
    )
    
    # Story to hold the content
    story = []
    
    # Add title
    story.append(Paragraph(subject, title_style))
    story.append(Spacer(1, 12))
    
    # Add generation timestamp
    timestamp = datetime.now().strftime("%B %d, %Y at %I:%M %p")
    story.append(Paragraph(f"Generated on {timestamp}", styles['Normal']))
    story.append(Spacer(1, 20))
    
    # Add sections
    for section in sections:
        if not section.get('items'):
            continue
            
        # Section heading
        story.append(Paragraph(section['heading'], heading_style))
        
        # Section items
        for item in section['items']:
            # Article title
            title = item.get('title', 'Untitled')
            story.append(Paragraph(f"• {title}", body_style))
            
            # Source
            source = item.get('source', 'Unknown Source')
            story.append(Paragraph(f"Source: {source}", source_style))
            
            # Link (if available)
            link = item.get('link', '')
            if link:
                story.append(Paragraph(f"<link href='{link}'>Read more</link>", link_style))
            
            story.append(Spacer(1, 8))
        
        story.append(Spacer(1, 16))
    
    # Add footer note
    if not sections or not any(section.get('items') for section in sections):
        story.append(Paragraph("No articles found for this report.", styles['Normal']))
    else:
        total_articles = sum(len(section.get('items', [])) for section in sections)
        story.append(Spacer(1, 20))
        story.append(Paragraph(
            f"This report contains {total_articles} articles across {len(sections)} sections.",
            styles['Italic']
        ))
    
    # Build PDF
    doc.build(story)
    
    # Get the PDF content
    pdf_content = buffer.getvalue()
    buffer.close()
    
    return pdf_content


def create_simple_report(title: str, content: str) -> bytes:
    """
    Create a simple PDF report with just title and content.
    
    Args:
        title: Report title
        content: Report content
        
    Returns:
        PDF content as bytes
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    
    story = [
        Paragraph(title, styles['Title']),
        Spacer(1, 20),
        Paragraph(content, styles['Normal'])
    ]
    
    doc.build(story)
    pdf_content = buffer.getvalue()
    buffer.close()
    
    return pdf_content
