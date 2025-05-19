#!/usr/bin/env python3
"""
GitHub Projects Automation Script for PropPulse

This script automates GitHub Projects management:
- Adds new issues to the project with status "Todo"
- Moves linked issues to "Done" when PR is merged
- Sets status to "Blocked" on CI failure

Usage:
    python auto_project.py [--event-type EVENT_TYPE] [--event-path EVENT_PATH]

Environment Variables:
    GITHUB_TOKEN: Personal access token with project admin permissions
    PROJECT_NUMBER: GitHub Project number
    GITHUB_REPOSITORY: Repository name (owner/repo)
"""

import os
import sys
import json
import logging
import argparse
import requests
from typing import Dict, Any, Optional, List, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

class GitHubProjectsAutomation:
    """Automates GitHub Projects management for PropPulse."""
    
    def __init__(self, token: str, repository: str, project_number: int):
        """
        Initialize the GitHub Projects automation.
        
        Args:
            token: GitHub token with project admin permissions
            repository: Repository name (owner/repo)
            project_number: GitHub Project number
        """
        self.token = token
        self.repository = repository
        self.owner, self.repo = repository.split('/')
        self.project_number = project_number
        self.rest_api_url = "https://api.github.com"
        self.graphql_api_url = "https://api.github.com/graphql"
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        self.graphql_headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        # Cache for project data
        self._project_id = None
        self._status_field_id = None
        self._status_option_ids = {}
    
    def execute_graphql(self, query: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute a GraphQL query against the GitHub API.
        
        Args:
            query: GraphQL query string
            variables: Variables for the query
            
        Returns:
            Response data
            
        Raises:
            Exception: If the query fails
        """
        payload = {"query": query}
        if variables:
            payload["variables"] = variables
            
        response = requests.post(self.graphql_api_url, json=payload, headers=self.graphql_headers)
        
        if response.status_code != 200:
            logger.error(f"Query failed: {response.status_code} {response.text}")
            raise Exception(f"Query failed: {response.status_code}")
            
        result = response.json()
        
        if "errors" in result:
            logger.error(f"GraphQL errors: {result['errors']}")
            raise Exception(f"GraphQL errors: {result['errors']}")
            
        return result["data"]
    
    def get_project_data(self) -> Tuple[str, str, Dict[str, str]]:
        """
        Get project ID, status field ID, and status option IDs.
        
        Returns:
            Tuple of project ID, status field ID, and status option IDs
        """
        if self._project_id and self._status_field_id and self._status_option_ids:
            return self._project_id, self._status_field_id, self._status_option_ids
            
        query = """
        query($owner: String!, $number: Int!) {
          organization(login: $owner) {
            projectV2(number: $number) {
              id
              fields(first: 20) {
                nodes {
                  ... on ProjectV2SingleSelectField {
                    id
                    name
                    options {
                      id
                      name
                    }
                  }
                }
              }
            }
          }
        }
        """
        
        variables = {
            "owner": self.owner,
            "number": self.project_number
        }
        
        try:
            data = self.execute_graphql(query, variables)
            project = data["organization"]["projectV2"]
        except Exception:
            # Try as user instead of organization
            query = """
            query($owner: String!, $number: Int!) {
              user(login: $owner) {
                projectV2(number: $number) {
                  id
                  fields(first: 20) {
                    nodes {
                      ... on ProjectV2SingleSelectField {
                        id
                        name
                        options {
                          id
                          name
                        }
                      }
                    }
                  }
                }
              }
            }
            """
            
            data = self.execute_graphql(query, variables)
            project = data["user"]["projectV2"]
        
        self._project_id = project["id"]
        
        # Find status field and options
        for field in project["fields"]["nodes"]:
            if field.get("name") == "Status":
                self._status_field_id = field["id"]
                for option in field.get("options", []):
                    self._status_option_ids[option["name"]] = option["id"]
                break
        
        if not self._status_field_id:
            raise Exception("Status field not found in project")
            
        return self._project_id, self._status_field_id, self._status_option_ids
    
    def get_item_id_for_issue(self, issue_number: int) -> Optional[str]:
        """
        Get project item ID for an issue.
        
        Args:
            issue_number: Issue number
            
        Returns:
            Project item ID or None if not found
        """
        project_id, _, _ = self.get_project_data()
        
        query = """
        query($project_id: ID!, $query: String!) {
          node(id: $project_id) {
            ... on ProjectV2 {
              items(first: 1, query: $query) {
                nodes {
                  id
                  content {
                    ... on Issue {
                      number
                    }
                  }
                }
              }
            }
          }
        }
        """
        
        variables = {
            "project_id": project_id,
            "query": f"repo:{self.repository} #{issue_number}"
        }
        
        data = self.execute_graphql(query, variables)
        items = data["node"]["items"]["nodes"]
        
        if items and items[0]["content"] and items[0]["content"].get("number") == issue_number:
            return items[0]["id"]
            
        return None
    
    def add_issue_to_project(self, issue_number: int) -> str:
        """
        Add an issue to the project and set status to Todo.
        
        Args:
            issue_number: Issue number
            
        Returns:
            Project item ID
        """
        logger.info(f"Adding issue #{issue_number} to project")
        
        project_id, status_field_id, status_option_ids = self.get_project_data()
        
        # Check if issue is already in project
        item_id = self.get_item_id_for_issue(issue_number)
        if item_id:
            logger.info(f"Issue #{issue_number} already in project")
            return item_id
        
        # Add issue to project
        query = """
        mutation($input: AddProjectV2ItemByIdInput!) {
          addProjectV2ItemById(input: $input) {
            item {
              id
            }
          }
        }
        """
        
        variables = {
            "input": {
                "projectId": project_id,
                "contentId": self.get_issue_node_id(issue_number)
            }
        }
        
        data = self.execute_graphql(query, variables)
        item_id = data["addProjectV2ItemById"]["item"]["id"]
        
        logger.info(f"Issue #{issue_number} added to project")
        
        # Set status to Todo
        self.set_item_status(item_id, "Todo")
        
        return item_id
    
    def get_issue_node_id(self, issue_number: int) -> str:
        """
        Get node ID for an issue.
        
        Args:
            issue_number: Issue number
            
        Returns:
            Issue node ID
        """
        query = """
        query($owner: String!, $repo: String!, $number: Int!) {
          repository(owner: $owner, name: $repo) {
            issue(number: $number) {
              id
            }
          }
        }
        """
        
        variables = {
            "owner": self.owner,
            "repo": self.repo,
            "number": issue_number
        }
        
        data = self.execute_graphql(query, variables)
        return data["repository"]["issue"]["id"]
    
    def set_item_status(self, item_id: str, status: str) -> None:
        """
        Set status for a project item.
        
        Args:
            item_id: Project item ID
            status: Status name (Todo, In-Progress, Done, Blocked)
        """
        logger.info(f"Setting item status to {status}")
        
        _, status_field_id, status_option_ids = self.get_project_data()
        
        if status not in status_option_ids:
            logger.error(f"Status {status} not found in project")
            return
        
        query = """
        mutation($input: UpdateProjectV2ItemFieldValueInput!) {
          updateProjectV2ItemFieldValue(input: $input) {
            projectV2Item {
              id
            }
          }
        }
        """
        
        variables = {
            "input": {
                "projectId": self._project_id,
                "itemId": item_id,
                "fieldId": status_field_id,
                "value": {
                    "singleSelectOptionId": status_option_ids[status]
                }
            }
        }
        
        self.execute_graphql(query, variables)
        
        logger.info(f"Item status set to {status}")
    
    def get_linked_issues(self, pr_number: int) -> List[int]:
        """
        Get issues linked to a PR.
        
        Args:
            pr_number: PR number
            
        Returns:
            List of linked issue numbers
        """
        logger.info(f"Getting issues linked to PR #{pr_number}")
        
        # Get PR body
        url = f"{self.rest_api_url}/repos/{self.repository}/pulls/{pr_number}"
        response = requests.get(url, headers=self.headers)
        
        if response.status_code != 200:
            logger.error(f"Error getting PR: {response.status_code} {response.text}")
            return []
        
        pr_data = response.json()
        body = pr_data.get("body", "")
        
        # Extract issue numbers from body
        # Look for patterns like "Fixes #123", "Closes #456", etc.
        import re
        patterns = [
            r"(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+#(\d+)",
            r"(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+(?:{})/(?:{})/issues/(\d+)".format(self.owner, self.repo)
        ]
        
        issue_numbers = []
        for pattern in patterns:
            matches = re.findall(pattern, body, re.IGNORECASE)
            issue_numbers.extend([int(num) for num in matches])
        
        logger.info(f"Found linked issues: {issue_numbers}")
        
        return issue_numbers
    
    def handle_new_issue(self, issue_number: int) -> None:
        """
        Handle a new issue by adding it to the project.
        
        Args:
            issue_number: Issue number
        """
        logger.info(f"Handling new issue #{issue_number}")
        
        self.add_issue_to_project(issue_number)
    
    def handle_pr_merged(self, pr_number: int) -> None:
        """
        Handle a merged PR by moving linked issues to Done.
        
        Args:
            pr_number: PR number
        """
        logger.info(f"Handling merged PR #{pr_number}")
        
        linked_issues = self.get_linked_issues(pr_number)
        
        for issue_number in linked_issues:
            item_id = self.get_item_id_for_issue(issue_number)
            
            if item_id:
                self.set_item_status(item_id, "Done")
            else:
                # Add issue to project and set status to Done
                item_id = self.add_issue_to_project(issue_number)
                self.set_item_status(item_id, "Done")
    
    def handle_ci_failure(self, pr_number: int) -> None:
        """
        Handle a CI failure by setting linked issues to Blocked.
        
        Args:
            pr_number: PR number
        """
        logger.info(f"Handling CI failure for PR #{pr_number}")
        
        linked_issues = self.get_linked_issues(pr_number)
        
        for issue_number in linked_issues:
            item_id = self.get_item_id_for_issue(issue_number)
            
            if item_id:
                self.set_item_status(item_id, "Blocked")
            else:
                # Add issue to project and set status to Blocked
                item_id = self.add_issue_to_project(issue_number)
                self.set_item_status(item_id, "Blocked")
                
        # Comment on PR
        url = f"{self.rest_api_url}/repos/{self.repository}/issues/{pr_number}/comments"
        payload = {
            "body": "⚠️ CI checks failed. Linked issues have been marked as Blocked in the project."
        }
        
        response = requests.post(url, headers=self.headers, json=payload)
        
        if response.status_code != 201:
            logger.error(f"Error commenting on PR: {response.status_code} {response.text}")
    
    def process_event(self, event_type: str, event_data: Dict[str, Any]) -> None:
        """
        Process a GitHub event.
        
        Args:
            event_type: Event type (issues, pull_request, workflow_run)
            event_data: Event data
        """
        logger.info(f"Processing {event_type} event")
        
        if event_type == "issues":
            action = event_data.get("action")
            issue = event_data.get("issue", {})
            issue_number = issue.get("number")
            
            if action == "opened" and issue_number:
                self.handle_new_issue(issue_number)
                
        elif event_type == "pull_request":
            action = event_data.get("action")
            pr = event_data.get("pull_request", {})
            pr_number = pr.get("number")
            
            if action == "closed" and pr.get("merged") and pr_number:
                self.handle_pr_merged(pr_number)
                
        elif event_type == "workflow_run":
            workflow_run = event_data.get("workflow_run", {})
            conclusion = workflow_run.get("conclusion")
            
            if conclusion == "failure":
                # Find associated PR
                url = f"{self.rest_api_url}/repos/{self.repository}/pulls"
                params = {
                    "head": f"{self.owner}:{workflow_run.get('head_branch', '')}"
                }
                
                response = requests.get(url, headers=self.headers, params=params)
                
                if response.status_code == 200:
                    prs = response.json()
                    
                    for pr in prs:
                        self.handle_ci_failure(pr.get("number"))

def main():
    """Main function to process GitHub events."""
    parser = argparse.ArgumentParser(description="GitHub Projects Automation")
    parser.add_argument("--event-type", help="GitHub event type")
    parser.add_argument("--event-path", help="Path to GitHub event payload file")
    args = parser.parse_args()
    
    # Get environment variables
    token = os.environ.get("GITHUB_TOKEN")
    repository = os.environ.get("GITHUB_REPOSITORY")
    project_number = os.environ.get("PROJECT_NUMBER")
    
    if not token or not repository or not project_number:
        logger.error("GITHUB_TOKEN, GITHUB_REPOSITORY, and PROJECT_NUMBER environment variables must be set")
        sys.exit(1)
    
    try:
        project_number = int(project_number)
    except ValueError:
        logger.error("PROJECT_NUMBER must be an integer")
        sys.exit(1)
    
    # Get event type and data
    event_type = args.event_type or os.environ.get("GITHUB_EVENT_NAME")
    event_path = args.event_path or os.environ.get("GITHUB_EVENT_PATH")
    
    if not event_type or not event_path:
        logger.error("Event type and path must be provided")
        sys.exit(1)
    
    try:
        with open(event_path, "r") as f:
            event_data = json.load(f)
    except Exception as e:
        logger.error(f"Error reading event data: {e}")
        sys.exit(1)
    
    try:
        # Process event
        automation = GitHubProjectsAutomation(token, repository, project_number)
        automation.process_event(event_type, event_data)
        
    except Exception as e:
        logger.error(f"Error processing event: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
