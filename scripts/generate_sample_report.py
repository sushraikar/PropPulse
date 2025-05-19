#!/usr/bin/env python3
"""
Sample Progress Report Generator for PropPulse

This script generates a sample progress report to demonstrate the format and content
of the weekly progress reports. It uses mock data to simulate real GitHub metrics.

Usage:
    python generate_sample_report.py [output_file]

Args:
    output_file: Optional path to save the report (defaults to docs/sample_progress_report.md)
"""

import os
import sys
import logging
import datetime
from pathlib import Path
from typing import Dict, Any, List, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

class SampleReportGenerator:
    """Generates a sample progress report with mock data."""
    
    def __init__(self):
        """Initialize the sample report generator."""
        # Get current date and week number
        now = datetime.datetime.now()
        self.current_date = now.strftime("%Y-%m-%d")
        self.year = now.strftime("%Y")
        self.week = now.strftime("%U")  # Week number (00-53)
        
        # Mock data
        self.closed_issues = self._generate_mock_issues(12)
        self.merged_prs = self._generate_mock_prs(8)
        self.deployments = self._generate_mock_deployments(3)
        self.avg_lead_time = 3.7  # days
    
    def _generate_mock_issues(self, count: int) -> List[Dict[str, Any]]:
        """
        Generate mock closed issues.
        
        Args:
            count: Number of issues to generate
            
        Returns:
            List of mock issues
        """
        issues = []
        
        for i in range(1, count + 1):
            closed_date = (datetime.datetime.now() - datetime.timedelta(days=i % 7)).strftime("%Y-%m-%d")
            
            issue = {
                "number": 100 + i,
                "title": f"Sample issue {i}: {self._get_mock_issue_title(i)}",
                "closed_at": closed_date
            }
            
            issues.append(issue)
        
        return issues
    
    def _get_mock_issue_title(self, index: int) -> str:
        """
        Get a mock issue title based on index.
        
        Args:
            index: Issue index
            
        Returns:
            Mock issue title
        """
        titles = [
            "Fix data ingestion for PDF files with complex layouts",
            "Implement caching for frequently accessed property data",
            "Add support for Arabic language in proposal writer",
            "Optimize MongoDB queries for property search",
            "Fix mobile responsiveness in dashboard view",
            "Add unit tests for ROI calculation agent",
            "Update documentation for API endpoints",
            "Implement rate limiting for external API calls",
            "Fix security vulnerability in authentication flow",
            "Add logging for better debugging",
            "Optimize Docker image size",
            "Implement CI/CD pipeline improvements"
        ]
        
        return titles[index % len(titles)]
    
    def _generate_mock_prs(self, count: int) -> List[Dict[str, Any]]:
        """
        Generate mock merged PRs.
        
        Args:
            count: Number of PRs to generate
            
        Returns:
            List of mock PRs
        """
        prs = []
        
        for i in range(1, count + 1):
            merged_date = (datetime.datetime.now() - datetime.timedelta(days=i % 5)).strftime("%Y-%m-%d")
            
            pr = {
                "number": 200 + i,
                "title": f"PR {i}: {self._get_mock_pr_title(i)}",
                "closed_at": merged_date
            }
            
            prs.append(pr)
        
        return prs
    
    def _get_mock_pr_title(self, index: int) -> str:
        """
        Get a mock PR title based on index.
        
        Args:
            index: PR index
            
        Returns:
            Mock PR title
        """
        titles = [
            "Fix data ingestion module",
            "Add caching layer",
            "Implement Arabic translation",
            "Optimize database queries",
            "Fix mobile UI issues",
            "Add test coverage",
            "Update API documentation",
            "Implement rate limiting"
        ]
        
        return titles[index % len(titles)]
    
    def _generate_mock_deployments(self, count: int) -> List[Dict[str, Any]]:
        """
        Generate mock deployments.
        
        Args:
            count: Number of deployments to generate
            
        Returns:
            List of mock deployments
        """
        deployments = []
        
        environments = ["development", "staging", "production"]
        
        for i in range(count):
            deployed_at = (datetime.datetime.now() - datetime.timedelta(days=i * 2)).strftime("%Y-%m-%d %H:%M")
            
            deployment = {
                "name": "PropPulse CD",
                "environment": environments[i % len(environments)],
                "created_at": deployed_at
            }
            
            deployments.append(deployment)
        
        return deployments
    
    def generate_report(self) -> str:
        """
        Generate the sample progress report.
        
        Returns:
            Report content
        """
        logger.info("Generating sample progress report")
        
        report = f"""# PropPulse Weekly Progress Report

**Week {self.week}, {self.year}**

Generated on: {self.current_date}

## Summary

- **Issues Closed**: {len(self.closed_issues)}
- **PRs Merged**: {len(self.merged_prs)}
- **Deployments**: {len(self.deployments)}
- **Average Lead Time**: {self.avg_lead_time:.2f} days

## Closed Issues

| Issue | Title | Closed At |
|-------|-------|-----------|
"""
        
        # Add closed issues
        for issue in self.closed_issues:
            report += f"| #{issue['number']} | {issue['title']} | {issue['closed_at']} |\n"
        
        report += """
## Merged PRs

| PR | Title | Merged At |
|-------|-------|-----------|
"""
        
        # Add merged PRs
        for pr in self.merged_prs:
            report += f"| #{pr['number']} | {pr['title']} | {pr['closed_at']} |\n"
        
        report += """
## Deployments

| Workflow | Environment | Deployed At |
|----------|-------------|-------------|
"""
        
        # Add deployments
        for deployment in self.deployments:
            report += f"| {deployment['name']} | {deployment['environment']} | {deployment['created_at']} |\n"
        
        report += """
## Risk Engine Status

| Risk Grade | Count | Percentage |
|------------|-------|------------|
| Green      | 42    | 65%        |
| Amber      | 18    | 28%        |
| Red        | 5     | 7%         |

## Next Steps

1. Complete implementation of co-investment module
2. Improve test coverage for risk scoring engine
3. Deploy updated UI components to staging environment
4. Finalize documentation for developer portal

"""
        
        logger.info("Sample report generated successfully")
        
        return report
    
    def save_report(self, output_file: str) -> str:
        """
        Save the report to a file.
        
        Args:
            output_file: Path to save the report
            
        Returns:
            Path to the saved report
        """
        logger.info(f"Saving report to {output_file}")
        
        # Create directory if it doesn't exist
        Path(os.path.dirname(output_file)).mkdir(parents=True, exist_ok=True)
        
        # Generate report
        report_content = self.generate_report()
        
        # Write report
        with open(output_file, "w") as f:
            f.write(report_content)
        
        logger.info("Report saved successfully")
        
        return output_file

def main():
    """Main function to generate a sample progress report."""
    # Get output file from command line argument or use default
    output_file = sys.argv[1] if len(sys.argv) > 1 else "docs/sample_progress_report.md"
    
    try:
        # Generate and save report
        generator = SampleReportGenerator()
        report_path = generator.save_report(output_file)
        
        print(f"Sample progress report generated: {report_path}")
        
    except Exception as e:
        logger.error(f"Error generating sample report: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
