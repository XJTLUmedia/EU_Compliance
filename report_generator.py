from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.pdfgen import canvas
from datetime import datetime
import json
import os
from typing import Dict, Any

class ComplianceReportGenerator:
    """
    Generates PDF compliance reports and roadmaps
    """
    
    def __init__(self, output_dir='reports'):
        """
        Initialize the report generator
        """
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        self.styles = getSampleStyleSheet()
        self._add_custom_styles()
    
    def _add_custom_styles(self):
        """
        Add custom styles for the report
        """
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            spaceAfter=30,
            alignment=TA_CENTER,
            textColor=colors.darkblue
        ))
        
        self.styles.add(ParagraphStyle(
            name='CustomHeading',
            parent=self.styles['Heading2'],
            fontSize=16,
            spaceAfter=12,
            textColor=colors.darkblue
        ))
        
        self.styles.add(ParagraphStyle(
            name='CustomBody',
            parent=self.styles['Normal'],
            fontSize=11,
            spaceAfter=6,
            alignment=TA_LEFT
        ))
    
    def generate_compliance_report(self, analysis_result: Dict[str, Any], business_info: Dict[str, Any]) -> str:
        """
        Generate a comprehensive compliance report PDF
        """
        # Create filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        business_name = business_info.get('business_name', 'Unknown').replace(' ', '_')
        filename = f"{self.output_dir}/Compliance_Report_{business_name}_{timestamp}.pdf"
        
        # Create the PDF document
        doc = SimpleDocTemplate(filename, pagesize=A4)
        story = []
        
        # Add title
        title = Paragraph("EU Regulatory Compliance Analysis Report", self.styles['CustomTitle'])
        story.append(title)
        story.append(Spacer(1, 0.5*inch))
        
        # Add business information
        story.append(Paragraph("Business Information", self.styles['CustomHeading']))
        business_data = [
            ['Business Name', business_info.get('business_name', 'Unknown')],
            ['Industry', business_info.get('industry', 'Unknown')],
            ['Target Markets', business_info.get('target_markets', 'Unknown')],
            ['Report Date', datetime.now().strftime("%Y-%m-%d")]
        ]
        
        business_table = Table(business_data, colWidths=[2*inch, 4*inch])
        business_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        story.append(business_table)
        story.append(Spacer(1, 0.3*inch))
        
        # Add compliance score
        compliance_score = analysis_result.get('overall_compliance_score', 0)
        score_color = self._get_score_color(compliance_score)
        
        story.append(Paragraph(f"Overall Compliance Score: {compliance_score}/100", self.styles['CustomHeading']))
        story.append(Spacer(1, 0.1*inch))
        
        # Add a visual representation of the score
        score_data = [['Compliance Level', '']]
        score_table = Table(score_data, colWidths=[2*inch, 4*inch])
        score_table.setStyle(TableStyle([
            ('BACKGROUND', (1, 0), (1, 0), score_color),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TEXTCOLOR', (1, 0), (1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        story.append(score_table)
        story.append(Spacer(1, 0.3*inch))
        
        # Add regulatory requirements
        story.append(Paragraph("Regulatory Requirements", self.styles['CustomHeading']))
        requirements = analysis_result.get('regulatory_requirements', [])
        for req in requirements:
            story.append(Paragraph(f"• {req}", self.styles['CustomBody']))
        story.append(Spacer(1, 0.2*inch))
        
        # Add compliance gaps
        story.append(Paragraph("Compliance Gaps", self.styles['CustomHeading']))
        gaps = analysis_result.get('compliance_gaps', [])
        for gap in gaps:
            story.append(Paragraph(f"• {gap}", self.styles['CustomBody']))
        story.append(Spacer(1, 0.2*inch))
        
        # Add action items
        story.append(Paragraph("Recommended Actions", self.styles['CustomHeading']))
        action_items = analysis_result.get('action_items', [])
        
        if action_items:
            action_data = [['Action', 'Priority', 'Timeline', 'Estimated Cost']]
            for item in action_items:
                action_data.append([
                    item.get('action', ''),
                    item.get('priority', ''),
                    item.get('timeline', ''),
                    item.get('estimated_cost', '')
                ])
            
            action_table = Table(action_data, colWidths=[3*inch, 1*inch, 1*inch, 1*inch])
            action_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'TOP')
            ]))
            
            story.append(action_table)
        else:
            story.append(Paragraph("No action items identified.", self.styles['CustomBody']))
        
        story.append(Spacer(1, 0.2*inch))
        
        # Add risks
        story.append(Paragraph("Non-Compliance Risks", self.styles['CustomHeading']))
        risks = analysis_result.get('risks', [])
        for risk in risks:
            story.append(Paragraph(f"• {risk}", self.styles['CustomBody']))
        story.append(Spacer(1, 0.2*inch))
        
        # Add disclaimer
        story.append(PageBreak())
        story.append(Paragraph("Disclaimer", self.styles['CustomHeading']))
        disclaimer_text = """
        This report is generated by an AI system and should be reviewed by qualified legal professionals 
        before taking any compliance actions. The information provided is based on available regulatory 
        data and AI analysis, which may not capture all nuances of specific business situations or 
        the latest regulatory changes. The service provider assumes no liability for decisions made 
        based on this report.
        """
        story.append(Paragraph(disclaimer_text, self.styles['CustomBody']))
        
        # Build the PDF
        doc.build(story)
        
        return filename
    
    def generate_roadmap_report(self, roadmap: Dict[str, Any], business_info: Dict[str, Any]) -> str:
        """
        Generate a compliance roadmap PDF
        """
        # Create filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        business_name = business_info.get('business_name', 'Unknown').replace(' ', '_')
        filename = f"{self.output_dir}/Compliance_Roadmap_{business_name}_{timestamp}.pdf"
        
        # Create the PDF document
        doc = SimpleDocTemplate(filename, pagesize=A4)
        story = []
        
        # Add title
        title = Paragraph("EU Regulatory Compliance Roadmap", self.styles['CustomTitle'])
        story.append(title)
        story.append(Spacer(1, 0.5*inch))
        
        # Add business information
        story.append(Paragraph("Business Information", self.styles['CustomHeading']))
        business_data = [
            ['Business Name', business_info.get('business_name', 'Unknown')],
            ['Industry', business_info.get('industry', 'Unknown')],
            ['Roadmap Date', datetime.now().strftime("%Y-%m-%d")]
        ]
        
        business_table = Table(business_data, colWidths=[2*inch, 4*inch])
        business_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        story.append(business_table)
        story.append(Spacer(1, 0.3*inch))
        
        # Add roadmap content based on the structure
        if 'monthly_milestones' in roadmap:
            story.append(Paragraph("Monthly Milestones", self.styles['CustomHeading']))
            milestones = roadmap['monthly_milestones']
            
            for month, activities in milestones.items():
                story.append(Paragraph(f"Month {month}", self.styles['Heading3']))
                for activity in activities:
                    story.append(Paragraph(f"• {activity}", self.styles['CustomBody']))
                story.append(Spacer(1, 0.1*inch))
            
            story.append(Spacer(1, 0.2*inch))
        
        if 'resource_requirements' in roadmap:
            story.append(Paragraph("Resource Requirements", self.styles['CustomHeading']))
            resources = roadmap['resource_requirements']
            
            for category, details in resources.items():
                story.append(Paragraph(f"{category}:", self.styles['Heading3']))
                if isinstance(details, dict):
                    for item, value in details.items():
                        story.append(Paragraph(f"  {item}: {value}", self.styles['CustomBody']))
                else:
                    story.append(Paragraph(f"  {details}", self.styles['CustomBody']))
                story.append(Spacer(1, 0.1*inch))
            
            story.append(Spacer(1, 0.2*inch))
        
        if 'key_performance_indicators' in roadmap:
            story.append(Paragraph("Key Performance Indicators", self.styles['CustomHeading']))
            kpis = roadmap['key_performance_indicators']
            
            for kpi, description in kpis.items():
                story.append(Paragraph(f"{kpi}:", self.styles['Heading3']))
                story.append(Paragraph(f"  {description}", self.styles['CustomBody']))
                story.append(Spacer(1, 0.1*inch))
            
            story.append(Spacer(1, 0.2*inch))
        
        if 'critical_path_items' in roadmap:
            story.append(Paragraph("Critical Path Items", self.styles['CustomHeading']))
            critical_items = roadmap['critical_path_items']
            
            for i, item in enumerate(critical_items, 1):
                story.append(Paragraph(f"{i}. {item}", self.styles['CustomBody']))
            
            story.append(Spacer(1, 0.2*inch))
        
        if 'contingency_plans' in roadmap:
            story.append(Paragraph("Contingency Plans", self.styles['CustomHeading']))
            contingencies = roadmap['contingency_plans']
            
            for challenge, plan in contingencies.items():
                story.append(Paragraph(f"Challenge: {challenge}", self.styles['Heading3']))
                story.append(Paragraph(f"Plan: {plan}", self.styles['CustomBody']))
                story.append(Spacer(1, 0.1*inch))
            
            story.append(Spacer(1, 0.2*inch))
        
        # Add disclaimer
        story.append(PageBreak())
        story.append(Paragraph("Disclaimer", self.styles['CustomHeading']))
        disclaimer_text = """
        This roadmap is generated by an AI system and should be reviewed by qualified project management 
        and legal professionals before implementation. The timeline and resource estimates are based on 
        typical compliance projects and may need adjustment for specific business circumstances. 
        The service provider assumes no liability for project outcomes based on this roadmap.
        """
        story.append(Paragraph(disclaimer_text, self.styles['CustomBody']))
        
        # Build the PDF
        doc.build(story)
        
        return filename
    
    def _get_score_color(self, score):
        """
        Get color based on compliance score
        """
        if score >= 80:
            return colors.green
        elif score >= 60:
            return colors.yellow
        elif score >= 40:
            return colors.orange
        else:
            return colors.red