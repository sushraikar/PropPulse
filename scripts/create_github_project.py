#!/usr/bin/env python3
"""
GitHub Project Creation Script for PropPulse

This script creates a GitHub Project named "PropPulse Roadmap" with the required fields
and views. It uses the GitHub GraphQL API to create the project and configure it.

Usage:
    python create_github_project.py

Environment Variables:
    GITHUB_TOKEN: Personal access token with project admin permissions
    GITHUB_OWNER: Organization or user name that will own the project
"""

import os
import sys
import logging
import requests
from typing import Dict, Any, Optional, List

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

class GitHubProjectCreator:
    """Creates and configures a GitHub Project for PropPulse."""
    
    def __init__(self, token: str, owner: str):
        """
        Initialize the GitHub Project creator.
        
        Args:
            token: GitHub token with project admin permissions
            owner: Organization or user name that will own the project
        """
        self.token = token
        self.owner = owner
        self.api_url = "https://api.github.com/graphql"
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json"
        }
    
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
            
        response = requests.post(self.api_url, json=payload, headers=self.headers)
        
        if response.status_code != 200:
            logger.error(f"Query failed: {response.status_code} {response.text}")
            raise Exception(f"Query failed: {response.status_code}")
            
        result = response.json()
        
        if "errors" in result:
            logger.error(f"GraphQL errors: {result['errors']}")
            raise Exception(f"GraphQL errors: {result['errors']}")
            
        return result["data"]
    
    def get_owner_id(self) -> str:
        """
        Get the node ID of the owner (organization or user).
        
        Returns:
            Node ID of the owner
        """
        query = """
        query($owner: String!) {
          organization(login: $owner) {
            id
          }
        }
        """
        
        variables = {
            "owner": self.owner
        }
        
        try:
            data = self.execute_graphql(query, variables)
            return data["organization"]["id"]
        except Exception:
            # Try as user instead of organization
            query = """
            query($owner: String!) {
              user(login: $owner) {
                id
              }
            }
            """
            
            data = self.execute_graphql(query, variables)
            return data["user"]["id"]
    
    def create_project(self, title: str) -> str:
        """
        Create a new GitHub Project.
        
        Args:
            title: Project title
            
        Returns:
            Project node ID
        """
        logger.info(f"Creating project: {title}")
        
        owner_id = self.get_owner_id()
        
        query = """
        mutation($input: CreateProjectV2Input!) {
          createProjectV2(input: $input) {
            projectV2 {
              id
              number
              url
            }
          }
        }
        """
        
        variables = {
            "input": {
                "ownerId": owner_id,
                "title": title,
                "repositoryId": None
            }
        }
        
        data = self.execute_graphql(query, variables)
        project_id = data["createProjectV2"]["projectV2"]["id"]
        project_number = data["createProjectV2"]["projectV2"]["number"]
        project_url = data["createProjectV2"]["projectV2"]["url"]
        
        logger.info(f"Project created: {project_url}")
        
        return project_id
    
    def create_field(self, project_id: str, name: str, field_type: str) -> str:
        """
        Create a custom field in the project.
        
        Args:
            project_id: Project node ID
            name: Field name
            field_type: Field type (TEXT, NUMBER, DATE, SINGLE_SELECT, etc.)
            
        Returns:
            Field node ID
        """
        logger.info(f"Creating field: {name} ({field_type})")
        
        query = """
        mutation($input: CreateProjectV2FieldInput!) {
          createProjectV2Field(input: $input) {
            projectV2Field {
              id
            }
          }
        }
        """
        
        variables = {
            "input": {
                "projectId": project_id,
                "dataType": field_type,
                "name": name
            }
        }
        
        data = self.execute_graphql(query, variables)
        field_id = data["createProjectV2Field"]["projectV2Field"]["id"]
        
        logger.info(f"Field created: {name}")
        
        return field_id
    
    def create_single_select_field(self, project_id: str, name: str, options: List[Dict[str, str]]) -> str:
        """
        Create a single select field with options.
        
        Args:
            project_id: Project node ID
            name: Field name
            options: List of option objects with name and color
            
        Returns:
            Field node ID
        """
        logger.info(f"Creating single select field: {name}")
        
        # Create the field first
        field_id = self.create_field(project_id, name, "SINGLE_SELECT")
        
        # Add options to the field
        for option in options:
            self.add_select_option(field_id, option["name"], option["color"])
            
        return field_id
    
    def add_select_option(self, field_id: str, name: str, color: str) -> str:
        """
        Add an option to a single select field.
        
        Args:
            field_id: Field node ID
            name: Option name
            color: Option color
            
        Returns:
            Option node ID
        """
        logger.info(f"Adding select option: {name} ({color})")
        
        query = """
        mutation($input: CreateProjectV2FieldOptionInput!) {
          createProjectV2FieldOption(input: $input) {
            projectV2FieldOption {
              id
            }
          }
        }
        """
        
        variables = {
            "input": {
                "fieldId": field_id,
                "name": name,
                "color": color
            }
        }
        
        data = self.execute_graphql(query, variables)
        option_id = data["createProjectV2FieldOption"]["projectV2FieldOption"]["id"]
        
        logger.info(f"Option added: {name}")
        
        return option_id
    
    def create_table_view(self, project_id: str, name: str, fields: List[str]) -> str:
        """
        Create a table view in the project.
        
        Args:
            project_id: Project node ID
            name: View name
            fields: List of field IDs to include
            
        Returns:
            View node ID
        """
        logger.info(f"Creating table view: {name}")
        
        query = """
        mutation($input: CreateProjectV2ViewInput!) {
          createProjectV2View(input: $input) {
            projectV2View {
              id
            }
          }
        }
        """
        
        variables = {
            "input": {
                "projectId": project_id,
                "name": name,
                "layout": "TABLE_LAYOUT"
            }
        }
        
        data = self.execute_graphql(query, variables)
        view_id = data["createProjectV2View"]["projectV2View"]["id"]
        
        logger.info(f"View created: {name}")
        
        # Add fields to the view
        for field_id in fields:
            self.add_field_to_view(view_id, field_id)
            
        return view_id
    
    def add_field_to_view(self, view_id: str, field_id: str) -> None:
        """
        Add a field to a view.
        
        Args:
            view_id: View node ID
            field_id: Field node ID
        """
        logger.info(f"Adding field to view")
        
        query = """
        mutation($input: UpdateProjectV2ViewInput!) {
          updateProjectV2View(input: $input) {
            projectV2View {
              id
            }
          }
        }
        """
        
        variables = {
            "input": {
                "projectViewId": view_id,
                "visibleFields": [field_id]
            }
        }
        
        self.execute_graphql(query, variables)
        
        logger.info(f"Field added to view")
    
    def setup_project(self) -> Dict[str, Any]:
        """
        Set up the PropPulse Roadmap project with required fields and views.
        
        Returns:
            Dictionary with project and field IDs
        """
        logger.info("Setting up PropPulse Roadmap project")
        
        # Create project
        project_id = self.create_project("PropPulse Roadmap")
        
        # Create Status field
        status_field_id = self.create_single_select_field(
            project_id,
            "Status",
            [
                {"name": "Todo", "color": "BLUE"},
                {"name": "In-Progress", "color": "YELLOW"},
                {"name": "Done", "color": "GREEN"},
                {"name": "Blocked", "color": "RED"}
            ]
        )
        
        # Create ETA field
        eta_field_id = self.create_field(project_id, "ETA", "DATE")
        
        # Create Priority field
        priority_field_id = self.create_single_select_field(
            project_id,
            "Priority",
            [
                {"name": "Low", "color": "GREEN"},
                {"name": "Medium", "color": "YELLOW"},
                {"name": "High", "color": "RED"}
            ]
        )
        
        # Create table view
        view_id = self.create_table_view(
            project_id,
            "Table View",
            [status_field_id, eta_field_id, priority_field_id]
        )
        
        return {
            "project_id": project_id,
            "status_field_id": status_field_id,
            "eta_field_id": eta_field_id,
            "priority_field_id": priority_field_id,
            "view_id": view_id
        }

def main():
    """Main function to create the GitHub Project."""
    # Get environment variables
    token = os.environ.get("GITHUB_TOKEN")
    owner = os.environ.get("GITHUB_OWNER")
    
    if not token or not owner:
        logger.error("GITHUB_TOKEN and GITHUB_OWNER environment variables must be set")
        sys.exit(1)
    
    try:
        # Create and set up project
        creator = GitHubProjectCreator(token, owner)
        result = creator.setup_project()
        
        # Print result
        logger.info("Project setup complete")
        logger.info(f"Project ID: {result['project_id']}")
        logger.info(f"Status Field ID: {result['status_field_id']}")
        logger.info(f"ETA Field ID: {result['eta_field_id']}")
        logger.info(f"Priority Field ID: {result['priority_field_id']}")
        
        # Save project number to GitHub output if running in GitHub Actions
        if "GITHUB_OUTPUT" in os.environ:
            with open(os.environ["GITHUB_OUTPUT"], "a") as f:
                f.write(f"project_id={result['project_id']}\n")
                f.write(f"status_field_id={result['status_field_id']}\n")
                f.write(f"eta_field_id={result['eta_field_id']}\n")
                f.write(f"priority_field_id={result['priority_field_id']}\n")
        
    except Exception as e:
        logger.error(f"Error setting up project: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
