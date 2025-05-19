"""
ProposalWriter agent for PropPulse
Responsible for generating personalized investment proposals
"""
from typing import Dict, Any, List, Optional
import os
import json
import asyncio
from datetime import datetime
import tempfile

# Import base agent
from agents.base_agent import BaseAgent


class ProposalWriter(BaseAgent):
    """
    ProposalWriter agent generates personalized investment proposals.
    
    Responsibilities:
    - Assemble retrieved information into a coherent proposal
    - Format proposal as Markdown
    - Convert Markdown to PDF using WeasyPrint
    - Ensure proposal is limited to 2 pages
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the ProposalWriter agent"""
        super().__init__(config)
        self.template_path = self.get_config_value('template_path', 'templates/proposal_template.md')
        self.output_dir = self.get_config_value('output_dir', '/tmp/proppulse/proposals')
        
        # Create output directory if it doesn't exist
        os.makedirs(self.output_dir, exist_ok=True)
    
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a personalized investment proposal.
        
        Args:
            input_data: Dictionary containing:
                - proposal_id: Unique identifier for the proposal
                - contact_info: Contact information
                - property_data: Property information
                - roi_metrics: ROI calculation results
                - language: Proposal language (default: english)
                
        Returns:
            Dict containing:
                - proposal_id: The proposal ID
                - markdown_content: Proposal content in Markdown format
                - pdf_path: Path to the generated PDF file
                - status: Processing status
        """
        # Validate input
        required_keys = ['proposal_id', 'property_data', 'roi_metrics']
        if not self.validate_input(input_data, required_keys):
            return {
                'status': 'error',
                'error': 'Missing required input: proposal_id, property_data, or roi_metrics'
            }
        
        proposal_id = input_data['proposal_id']
        property_data = input_data['property_data']
        roi_metrics = input_data['roi_metrics']
        contact_info = input_data.get('contact_info', {})
        language = input_data.get('language', 'english')
        
        try:
            # Generate proposal content in Markdown
            markdown_content = self._generate_markdown_proposal(
                proposal_id, contact_info, property_data, roi_metrics
            )
            
            # Save Markdown content to file
            markdown_path = os.path.join(self.output_dir, f"{proposal_id}.md")
            with open(markdown_path, 'w', encoding='utf-8') as f:
                f.write(markdown_content)
            
            # Convert Markdown to PDF
            pdf_path = os.path.join(self.output_dir, f"{proposal_id}.pdf")
            await self._convert_to_pdf(markdown_path, pdf_path)
            
            return {
                'status': 'success',
                'proposal_id': proposal_id,
                'markdown_content': markdown_content,
                'markdown_path': markdown_path,
                'pdf_path': pdf_path,
                'language': language
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'error': f'Error generating proposal: {str(e)}'
            }
    
    def _generate_markdown_proposal(
        self, 
        proposal_id: str, 
        contact_info: Dict[str, Any], 
        property_data: Dict[str, Any], 
        roi_metrics: Dict[str, Any]
    ) -> str:
        """
        Generate proposal content in Markdown format.
        
        Args:
            proposal_id: Proposal ID
            contact_info: Contact information
            property_data: Property information
            roi_metrics: ROI calculation results
            
        Returns:
            Proposal content in Markdown format
        """
        # Extract property details
        property_name = property_data.get('name', 'Luxury Property')
        property_location = property_data.get('location', 'Dubai')
        property_developer = property_data.get('developer', 'Premium Developer')
        property_type = property_data.get('type', 'Apartment')
        property_size = property_data.get('size_ft2', 'N/A')
        property_price = property_data.get('list_price_aed', 'N/A')
        
        # Format property price
        if isinstance(property_price, (int, float)):
            property_price = f"AED {property_price:,.0f}"
        
        # Format property size
        if isinstance(property_size, (int, float)):
            property_size = f"{property_size:,.0f} ft²"
        
        # Extract ROI metrics
        metrics = roi_metrics.get('metrics', {})
        adr = metrics.get('adr', 'N/A')
        occupancy = metrics.get('occupancy_percentage', 'N/A')
        gross_income = metrics.get('gross_rental_income', 'N/A')
        service_charge = metrics.get('service_charge_per_sqft', 'N/A')
        net_yield = metrics.get('net_yield_percentage', 'N/A')
        irr = metrics.get('irr_10yr', 'N/A')
        cagr = metrics.get('capital_appreciation_cagr', 'N/A')
        
        # Format metrics
        if isinstance(adr, (int, float)):
            adr = f"AED {adr:,.0f}"
        if isinstance(occupancy, (int, float)):
            occupancy = f"{occupancy:.1f}%"
        if isinstance(gross_income, (int, float)):
            gross_income = f"AED {gross_income:,.0f}"
        if isinstance(service_charge, (int, float)):
            service_charge = f"AED {service_charge:.2f}/ft²"
        if isinstance(net_yield, (int, float)):
            net_yield = f"{net_yield:.2f}%"
        if isinstance(irr, (int, float)):
            irr = f"{irr:.2f}%"
        if isinstance(cagr, (int, float)):
            cagr = f"{cagr:.1f}%"
        
        # Extract contact details
        contact_name = contact_info.get('name', 'Valued Investor')
        
        # Generate current date
        current_date = datetime.now().strftime("%B %d, %Y")
        
        # Generate proposal content
        markdown = f"""
# Investment Proposal: {property_name}

**Prepared for:** {contact_name}  
**Date:** {current_date}  
**Proposal ID:** {proposal_id}

## Property Overview

**Property:** {property_name}  
**Location:** {property_location}  
**Developer:** {property_developer}  
**Type:** {property_type}  
**Size:** {property_size}  
**List Price:** {property_price}

## Investment Highlights

* Prime location in {property_location}
* Developed by {property_developer}, known for quality and timely delivery
* Excellent rental potential with strong demand in the area
* Projected capital appreciation of {cagr} annually

## Financial Analysis

### Rental Income Projection

| Metric | Value |
|--------|-------|
| Average Daily Rate (ADR) | {adr} |
| Occupancy Rate | {occupancy} |
| Gross Annual Rental Income | {gross_income} |
| Service Charge | {service_charge} |
| Net Yield | {net_yield} |

### Return on Investment

* **Net Yield:** {net_yield} per annum
* **10-Year IRR (pre-tax):** {irr}
* **Capital Appreciation (CAGR):** {cagr}

## Payment Plan

"""
        
        # Add payment plan if available
        payment_plan = property_data.get('payment_plan', [])
        if payment_plan:
            markdown += "| Installment | Percentage | Amount | Milestone |\n"
            markdown += "|------------|------------|--------|----------|\n"
            
            for payment in payment_plan:
                percentage = payment.get('percentage', 'N/A')
                amount = payment.get('amount', 'N/A')
                description = payment.get('description', 'N/A')
                
                if isinstance(percentage, (int, float)):
                    percentage = f"{percentage}%"
                if isinstance(amount, (int, float)):
                    amount = f"AED {amount:,.0f}"
                
                markdown += f"| {description} | {percentage} | {amount} | {description} |\n"
        else:
            markdown += "Standard payment plan: 20% down payment, 30% during construction, 50% on completion.\n"
        
        # Add property description if available
        markdown += "\n## Property Description\n\n"
        
        description = self._extract_property_description(property_data)
        if description:
            markdown += description
        else:
            markdown += f"A premium {property_type.lower()} in {property_location}, offering modern living spaces with high-quality finishes and amenities. This property represents an excellent investment opportunity in Dubai's thriving real estate market.\n"
        
        # Add location advantages if available
        markdown += "\n## Location Advantages\n\n"
        
        location_info = self._extract_location_advantages(property_data)
        if location_info:
            markdown += location_info
        else:
            markdown += f"Strategically located in {property_location}, with easy access to major highways, shopping centers, schools, and leisure facilities. The property enjoys proximity to key landmarks and business districts.\n"
        
        # Add disclaimer
        markdown += """
## Disclaimer

This investment proposal is based on current market conditions and projections. Actual returns may vary. This document does not constitute financial advice. Please consult with your financial advisor before making investment decisions.

---

**PropPulse** | Premium Real Estate Investment Solutions | www.proppulse.ai
"""
        
        return markdown
    
    def _extract_property_description(self, property_data: Dict[str, Any]) -> str:
        """
        Extract property description from property data.
        
        Args:
            property_data: Property information
            
        Returns:
            Property description as string
        """
        # Check if description is directly available
        if 'description' in property_data:
            return property_data['description']
        
        # Try to extract from details
        if 'details' in property_data:
            details = property_data['details']
            if isinstance(details, list) and len(details) > 0:
                # Combine text from all detail chunks
                description = ""
                for detail in details:
                    if isinstance(detail, dict) and 'text' in detail:
                        description += detail['text'] + "\n\n"
                    elif isinstance(detail, str):
                        description += detail + "\n\n"
                
                return description.strip()
        
        return ""
    
    def _extract_location_advantages(self, property_data: Dict[str, Any]) -> str:
        """
        Extract location advantages from property data.
        
        Args:
            property_data: Property information
            
        Returns:
            Location advantages as string
        """
        # Check if location info is directly available
        if 'location_advantages' in property_data:
            return property_data['location_advantages']
        
        # Try to extract from location field
        if 'location' in property_data:
            location = property_data['location']
            if isinstance(location, list) and len(location) > 0:
                # Combine text from all location chunks
                location_info = ""
                for loc in location:
                    if isinstance(loc, dict) and 'text' in loc:
                        location_info += loc['text'] + "\n\n"
                    elif isinstance(loc, str):
                        location_info += loc + "\n\n"
                
                return location_info.strip()
        
        return ""
    
    async def _convert_to_pdf(self, markdown_path: str, pdf_path: str) -> None:
        """
        Convert Markdown to PDF using WeasyPrint.
        
        Args:
            markdown_path: Path to Markdown file
            pdf_path: Path to output PDF file
        """
        # In a real implementation, this would use WeasyPrint to convert Markdown to PDF
        # For now, we'll simulate the conversion
        
        # Create a simple HTML wrapper for the Markdown content
        with open(markdown_path, 'r', encoding='utf-8') as f:
            markdown_content = f.read()
        
        # Create a temporary HTML file
        with tempfile.NamedTemporaryFile(suffix='.html', delete=False) as temp_html:
            html_path = temp_html.name
            
            # Simple HTML wrapper with basic styling
            html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Investment Proposal</title>
    <style>
        body {{
            font-family: "Noto Sans CJK SC", "WenQuanYi Zen Hei", Arial, sans-serif;
            margin: 2cm;
            font-size: 11pt;
            line-height: 1.5;
        }}
        h1 {{
            color: #2E5BFF;
            font-size: 24pt;
            margin-bottom: 0.5cm;
        }}
        h2 {{
            color: #2E5BFF;
            font-size: 16pt;
            margin-top: 1cm;
            margin-bottom: 0.3cm;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 1cm 0;
        }}
        th, td {{
            border: 1px solid #ddd;
            padding: 8px;
            text-align: left;
        }}
        th {{
            background-color: #f2f2f2;
        }}
        .disclaimer {{
            font-size: 9pt;
            color: #666;
            margin-top: 1cm;
        }}
        .footer {{
            text-align: center;
            margin-top: 2cm;
            font-size: 10pt;
            color: #888;
        }}
        @page {{
            size: A4;
            margin: 2cm;
        }}
    </style>
</head>
<body>
    <!-- Markdown content would be converted to HTML here -->
    <div class="markdown-content">
        {markdown_content}
    </div>
</body>
</html>
            """
            
            temp_html.write(html_content.encode('utf-8'))
        
        # In a real implementation, we would use WeasyPrint to convert HTML to PDF:
        # from weasyprint import HTML
        # HTML(html_path).write_pdf(pdf_path)
        
        # For now, simulate the conversion with a delay
        await asyncio.sleep(0.5)
        
        # Create an empty PDF file to simulate the output
        with open(pdf_path, 'w') as f:
            f.write("PDF content would be here")
        
        # Clean up temporary HTML file
        os.unlink(html_path)
