#!/usr/bin/env python3
"""
GitHub Projects Status Badge Generator for PropPulse

This script queries GitHub Projects GraphQL API to calculate completion percentage
and generates a badge showing "% tasks Done" for the README.

Usage:
    python project_badge.py

Environment Variables:
    GITHUB_TOKEN: Personal access token with project read permissions
    PROJECT_NUMBER: GitHub Project number
    GITHUB_REPOSITORY: Repository name (owner/repo)
    GIST_ID: Gist ID for storing badge data
    GIST_TOKEN: GitHub token with gist write permissions
"""

import os
import sys
import json
import logging
import requests
from typing import Dict, Any, Tuple, List

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

class ProjectBadgeGenerator:
    """Generates status badge for GitHub Projects completion percentage."""
    
    def __init__(self, token: str, repository: str, project_number: int):
        """
        Initialize the badge generator.
        
        Args:
            token: GitHub token with project read permissions
            repository: Repository name (owner/repo)
            project_number: GitHub Project number
        """
        self.token = token
        self.repository = repository
        self.owner = repository.split('/')[0]
        self.project_number = project_number
        self.graphql_api_url = "https://api.github.com/graphql"
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json"
        }
    
    def execute_graphql(self, query: str, variables: Dict[str, Any] = None) -> Dict[str, Any]:
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
            
        response = requests.post(self.graphql_api_url, json=payload, headers=self.headers)
        
        if response.status_code != 200:
            logger.error(f"Query failed: {response.status_code} {response.text}")
            raise Exception(f"Query failed: {response.status_code}")
            
        result = response.json()
        
        if "errors" in result:
            logger.error(f"GraphQL errors: {result['errors']}")
            raise Exception(f"GraphQL errors: {result['errors']}")
            
        return result["data"]
    
    def get_project_items(self) -> List[Dict[str, Any]]:
        """
        Get all items in the project with their status.
        
        Returns:
            List of project items with status information
        """
        logger.info(f"Getting items for project {self.project_number}")
        
        query = """
        query($owner: String!, $number: Int!) {
          organization(login: $owner) {
            projectV2(number: $number) {
              items(first: 100) {
                nodes {
                  id
                  fieldValues(first: 10) {
                    nodes {
                      ... on ProjectV2ItemFieldSingleSelectValue {
                        name
                        field {
                          ... on ProjectV2SingleSelectField {
                            name
                          }
                        }
                      }
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
            return data["organization"]["projectV2"]["items"]["nodes"]
        except Exception:
            # Try as user instead of organization
            query = """
            query($owner: String!, $number: Int!) {
              user(login: $owner) {
                projectV2(number: $number) {
                  items(first: 100) {
                    nodes {
                      id
                      fieldValues(first: 10) {
                        nodes {
                          ... on ProjectV2ItemFieldSingleSelectValue {
                            name
                            field {
                              ... on ProjectV2SingleSelectField {
                                name
                              }
                            }
                          }
                        }
                      }
                    }
                  }
                }
              }
            }
            """
            
            data = self.execute_graphql(query, variables)
            return data["user"]["projectV2"]["items"]["nodes"]
    
    def calculate_completion_percentage(self) -> Tuple[int, int, int]:
        """
        Calculate the percentage of tasks marked as Done.
        
        Returns:
            Tuple of (completion percentage, total items, done items)
        """
        logger.info("Calculating completion percentage")
        
        items = self.get_project_items()
        total_items = len(items)
        done_items = 0
        
        for item in items:
            field_values = item.get("fieldValues", {}).get("nodes", [])
            
            for field_value in field_values:
                if field_value.get("field", {}).get("name") == "Status" and field_value.get("name") == "Done":
                    done_items += 1
                    break
        
        percentage = int((done_items / total_items) * 100) if total_items > 0 else 0
        
        logger.info(f"Completion: {percentage}% ({done_items}/{total_items})")
        
        return percentage, total_items, done_items
    
    def get_badge_color(self, percentage: int) -> str:
        """
        Get the appropriate color for the badge based on completion percentage.
        
        Args:
            percentage: Completion percentage
            
        Returns:
            Badge color
        """
        if percentage < 30:
            return "red"
        elif percentage < 70:
            return "yellow"
        else:
            return "green"
    
    def update_gist(self, gist_id: str, gist_token: str, percentage: int) -> None:
        """
        Update a GitHub Gist with badge data.
        
        Args:
            gist_id: Gist ID
            gist_token: GitHub token with gist write permissions
            percentage: Completion percentage
        """
        logger.info(f"Updating gist {gist_id} with completion percentage")
        
        color = self.get_badge_color(percentage)
        
        # Prepare badge data
        badge_data = {
            "schemaVersion": 1,
            "label": "tasks done",
            "message": f"{percentage}%",
            "color": color
        }
        
        # Update gist
        headers = {
            "Authorization": f"Bearer {gist_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        url = f"https://api.github.com/gists/{gist_id}"
        
        payload = {
            "files": {
                "proppulse-completion.json": {
                    "content": json.dumps(badge_data)
                }
            }
        }
        
        response = requests.patch(url, headers=headers, json=payload)
        
        if response.status_code != 200:
            logger.error(f"Error updating gist: {response.status_code} {response.text}")
            raise Exception(f"Error updating gist: {response.status_code}")
        
        logger.info("Gist updated successfully")

def main():
    """Main function to generate the project badge."""
    # Get environment variables
    token = os.environ.get("GITHUB_TOKEN")
    repository = os.environ.get("GITHUB_REPOSITORY")
    project_number = os.environ.get("PROJECT_NUMBER")
    gist_id = os.environ.get("GIST_ID")
    gist_token = os.environ.get("GIST_TOKEN") or token
    
    if not token or not repository or not project_number or not gist_id:
        logger.error("Required environment variables not set")
        sys.exit(1)
    
    try:
        project_number = int(project_number)
    except ValueError:
        logger.error("PROJECT_NUMBER must be an integer")
        sys.exit(1)
    
    try:
        # Generate badge
        generator = ProjectBadgeGenerator(token, repository, project_number)
        percentage, total_items, done_items = generator.calculate_completion_percentage()
        
        # Update gist
        generator.update_gist(gist_id, gist_token, percentage)
        
        # Output results
        print(f"Completion: {percentage}% ({done_items}/{total_items})")
        
        # Set GitHub Actions output if running in GitHub Actions
        if "GITHUB_OUTPUT" in os.environ:
            with open(os.environ["GITHUB_OUTPUT"], "a") as f:
                f.write(f"percentage={percentage}\n")
                f.write(f"total_items={total_items}\n")
                f.write(f"done_items={done_items}\n")
        
    except Exception as e:
        logger.error(f"Error generating badge: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
