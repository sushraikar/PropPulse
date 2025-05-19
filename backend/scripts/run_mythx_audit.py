"""
MythX audit runner for PropPulse smart contracts

This script runs MythX security audits on the PropPulse smart contracts
and generates audit reports.
"""
import os
import json
import logging
import argparse
import subprocess
from datetime import datetime
from typing import Dict, Any, List, Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MythXAudit:
    """
    MythX audit runner for PropPulse smart contracts
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the MythXAudit"""
        self.config = config or {}
        
        # MythX configuration
        self.mythx_api_key = self.config.get('mythx_api_key', os.getenv('MYTHX_API_KEY'))
        
        # Contract paths
        self.contracts_dir = self.config.get('contracts_dir', os.path.join(os.path.dirname(__file__), '..', '..', 'contracts'))
        self.audit_reports_dir = self.config.get('audit_reports_dir', os.path.join(os.path.dirname(__file__), '..', '..', 'audit_reports'))
        
        # Create audit reports directory if it doesn't exist
        os.makedirs(self.audit_reports_dir, exist_ok=True)
    
    def run_audit(self, contract_file: str, audit_mode: str = 'quick') -> Dict[str, Any]:
        """
        Run MythX audit on a smart contract
        
        Args:
            contract_file: Contract file path (relative to contracts directory)
            audit_mode: Audit mode (quick, standard, deep)
            
        Returns:
            Audit result
        """
        try:
            # Check if MythX API key is available
            if not self.mythx_api_key:
                return {
                    'status': 'error',
                    'message': 'MythX API key not provided',
                    'contract_file': contract_file
                }
            
            # Get absolute path to contract file
            contract_path = os.path.join(self.contracts_dir, contract_file)
            
            # Check if contract file exists
            if not os.path.isfile(contract_path):
                return {
                    'status': 'error',
                    'message': f"Contract file not found: {contract_path}",
                    'contract_file': contract_file
                }
            
            # Get contract name from file name
            contract_name = os.path.splitext(os.path.basename(contract_file))[0]
            
            # Get timestamp for report file name
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            # Create report file path
            report_file = os.path.join(
                self.audit_reports_dir,
                f"{contract_name}_{audit_mode}_{timestamp}.json"
            )
            
            # Run MythX CLI command
            command = [
                'mythx',
                'analyze',
                '--api-key', self.mythx_api_key,
                '--mode', audit_mode,
                '--format', 'json',
                '--output', report_file,
                contract_path
            ]
            
            logger.info(f"Running MythX audit on {contract_file} in {audit_mode} mode")
            
            # Execute command
            process = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True
            )
            
            # Check if report file was created
            if not os.path.isfile(report_file):
                return {
                    'status': 'error',
                    'message': f"Report file not created: {report_file}",
                    'contract_file': contract_file,
                    'stdout': process.stdout,
                    'stderr': process.stderr
                }
            
            # Load report file
            with open(report_file, 'r') as f:
                report = json.load(f)
            
            # Count issues by severity
            issue_counts = {
                'high': 0,
                'medium': 0,
                'low': 0,
                'none': 0
            }
            
            for issue in report.get('issues', []):
                severity = issue.get('severity', 'none').lower()
                if severity in issue_counts:
                    issue_counts[severity] += 1
            
            return {
                'status': 'success',
                'message': f"MythX audit completed for {contract_file}",
                'contract_file': contract_file,
                'audit_mode': audit_mode,
                'report_file': report_file,
                'issue_counts': issue_counts,
                'total_issues': sum(issue_counts.values())
            }
        
        except subprocess.CalledProcessError as e:
            logger.error(f"MythX audit failed: {str(e)}")
            return {
                'status': 'error',
                'message': f"MythX audit failed: {str(e)}",
                'contract_file': contract_file,
                'stdout': e.stdout,
                'stderr': e.stderr
            }
        
        except Exception as e:
            logger.error(f"Error running MythX audit: {str(e)}")
            return {
                'status': 'error',
                'message': f"Error running MythX audit: {str(e)}",
                'contract_file': contract_file
            }
    
    def run_audits(self, audit_mode: str = 'quick') -> List[Dict[str, Any]]:
        """
        Run MythX audits on all smart contracts
        
        Args:
            audit_mode: Audit mode (quick, standard, deep)
            
        Returns:
            List of audit results
        """
        try:
            # Get all Solidity files in contracts directory
            contract_files = []
            for root, _, files in os.walk(self.contracts_dir):
                for file in files:
                    if file.endswith('.sol'):
                        rel_path = os.path.relpath(os.path.join(root, file), self.contracts_dir)
                        contract_files.append(rel_path)
            
            # Run audits on all contracts
            results = []
            for contract_file in contract_files:
                result = self.run_audit(contract_file, audit_mode)
                results.append(result)
            
            return results
        
        except Exception as e:
            logger.error(f"Error running MythX audits: {str(e)}")
            return [{
                'status': 'error',
                'message': f"Error running MythX audits: {str(e)}"
            }]
    
    def generate_summary_report(self, audit_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generate summary report from audit results
        
        Args:
            audit_results: List of audit results
            
        Returns:
            Summary report
        """
        try:
            # Count successful and failed audits
            successful_audits = [result for result in audit_results if result.get('status') == 'success']
            failed_audits = [result for result in audit_results if result.get('status') != 'success']
            
            # Count total issues by severity
            total_issues = {
                'high': 0,
                'medium': 0,
                'low': 0,
                'none': 0
            }
            
            for result in successful_audits:
                issue_counts = result.get('issue_counts', {})
                for severity, count in issue_counts.items():
                    if severity in total_issues:
                        total_issues[severity] += count
            
            # Create summary report
            summary = {
                'timestamp': datetime.now().isoformat(),
                'total_contracts': len(audit_results),
                'successful_audits': len(successful_audits),
                'failed_audits': len(failed_audits),
                'total_issues': sum(total_issues.values()),
                'issues_by_severity': total_issues,
                'contracts': [
                    {
                        'contract_file': result.get('contract_file'),
                        'status': result.get('status'),
                        'report_file': result.get('report_file') if result.get('status') == 'success' else None,
                        'issue_counts': result.get('issue_counts') if result.get('status') == 'success' else None,
                        'total_issues': result.get('total_issues') if result.get('status') == 'success' else None,
                        'error_message': result.get('message') if result.get('status') != 'success' else None
                    }
                    for result in audit_results
                ]
            }
            
            # Save summary report
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            summary_file = os.path.join(
                self.audit_reports_dir,
                f"summary_{timestamp}.json"
            )
            
            with open(summary_file, 'w') as f:
                json.dump(summary, f, indent=2)
            
            summary['summary_file'] = summary_file
            
            return summary
        
        except Exception as e:
            logger.error(f"Error generating summary report: {str(e)}")
            return {
                'status': 'error',
                'message': f"Error generating summary report: {str(e)}"
            }

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='MythX audit runner for PropPulse smart contracts')
    parser.add_argument('--mode', choices=['quick', 'standard', 'deep'], default='quick',
                        help='Audit mode (quick, standard, deep)')
    parser.add_argument('--contract', help='Specific contract file to audit (relative to contracts directory)')
    args = parser.parse_args()
    
    # Initialize MythX audit
    mythx_audit = MythXAudit()
    
    # Run audits
    if args.contract:
        # Run audit on specific contract
        result = mythx_audit.run_audit(args.contract, args.mode)
        print(json.dumps(result, indent=2))
    else:
        # Run audits on all contracts
        results = mythx_audit.run_audits(args.mode)
        
        # Generate summary report
        summary = mythx_audit.generate_summary_report(results)
        print(json.dumps(summary, indent=2))

if __name__ == '__main__':
    main()
