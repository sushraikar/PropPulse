"""
Translator agent for PropPulse
Responsible for translating proposals to multiple languages
"""
from typing import Dict, Any, List, Optional
import os
import json
import asyncio

# Import base agent
from agents.base_agent import BaseAgent


class Translator(BaseAgent):
    """
    Translator agent translates proposals to multiple languages.
    
    Responsibilities:
    - Translate proposal content to Arabic, French, Hindi
    - Preserve formatting and layout during translation
    - Handle specialized real estate terminology correctly
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the Translator agent"""
        super().__init__(config)
        self.supported_languages = {
            'arabic': 'ar',
            'french': 'fr',
            'hindi': 'hi',
            'english': 'en'
        }
        self.output_dir = self.get_config_value('output_dir', '/tmp/proppulse/proposals')
        
        # Create output directory if it doesn't exist
        os.makedirs(self.output_dir, exist_ok=True)
    
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Translate proposal content to the specified language.
        
        Args:
            input_data: Dictionary containing:
                - proposal_id: Unique identifier for the proposal
                - markdown_content: Proposal content in Markdown format
                - target_language: Target language (arabic, french, hindi)
                
        Returns:
            Dict containing:
                - proposal_id: The proposal ID
                - translated_content: Translated proposal content
                - language: Target language
                - markdown_path: Path to the translated Markdown file
                - status: Processing status
        """
        # Validate input
        required_keys = ['proposal_id', 'markdown_content', 'target_language']
        if not self.validate_input(input_data, required_keys):
            return {
                'status': 'error',
                'error': 'Missing required input: proposal_id, markdown_content, or target_language'
            }
        
        proposal_id = input_data['proposal_id']
        markdown_content = input_data['markdown_content']
        target_language = input_data['target_language'].lower()
        
        # Validate target language
        if target_language not in self.supported_languages:
            return {
                'status': 'error',
                'error': f'Unsupported language: {target_language}. Supported languages: {", ".join(self.supported_languages.keys())}'
            }
        
        # Skip translation if target language is English
        if target_language == 'english':
            return {
                'status': 'success',
                'proposal_id': proposal_id,
                'translated_content': markdown_content,
                'language': 'english',
                'language_code': 'en',
                'markdown_path': os.path.join(self.output_dir, f"{proposal_id}.md")
            }
        
        try:
            # Translate content
            translated_content = await self._translate_content(markdown_content, target_language)
            
            # Save translated content to file
            language_code = self.supported_languages[target_language]
            markdown_path = os.path.join(self.output_dir, f"{proposal_id}_{language_code}.md")
            with open(markdown_path, 'w', encoding='utf-8') as f:
                f.write(translated_content)
            
            return {
                'status': 'success',
                'proposal_id': proposal_id,
                'translated_content': translated_content,
                'language': target_language,
                'language_code': language_code,
                'markdown_path': markdown_path
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'error': f'Error translating proposal: {str(e)}'
            }
    
    async def _translate_content(self, content: str, target_language: str) -> str:
        """
        Translate content to the target language.
        
        Args:
            content: Content to translate
            target_language: Target language
            
        Returns:
            Translated content
        """
        # In a real implementation, this would use GPT-4o or Azure Cognitive Services
        # For now, we'll simulate translation with placeholder text
        
        # Simulate translation delay
        await asyncio.sleep(0.5)
        
        # Get language code
        language_code = self.supported_languages[target_language]
        
        # For demonstration purposes, we'll add a language indicator to the content
        if target_language == 'arabic':
            translated_header = "# تقرير الاستثمار العقاري\n\n"
            return translated_header + f"[This content would be translated to Arabic ({language_code}) using GPT-4o or Azure Cognitive Services]\n\n" + content
        elif target_language == 'french':
            translated_header = "# Proposition d'Investissement Immobilier\n\n"
            return translated_header + f"[This content would be translated to French ({language_code}) using GPT-4o or Azure Cognitive Services]\n\n" + content
        elif target_language == 'hindi':
            translated_header = "# रियल एस्टेट निवेश प्रस्ताव\n\n"
            return translated_header + f"[This content would be translated to Hindi ({language_code}) using GPT-4o or Azure Cognitive Services]\n\n" + content
        else:
            return content
