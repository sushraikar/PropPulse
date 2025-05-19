"""
MarketingAssetAgent for PropPulse developer portal.

This module provides:
1. AI-powered marketing asset generation using OpenAI Vision and DALL·E 3
2. Automatic creation of hero images, catchy summaries, and USP bullets
3. Brand compliance checks and approval workflow
4. S3 storage integration for generated assets
"""

import os
import json
import uuid
import time
from typing import Dict, List, Optional, Any, Union, Tuple
from datetime import datetime, timedelta
from fastapi import BackgroundTasks
from sqlalchemy.orm import Session
from azure.keyvault.secrets import SecretClient
from azure.identity import DefaultAzureCredential
import boto3
from botocore.exceptions import ClientError
from PIL import Image, ImageDraw, ImageFont
import io
import base64
import requests

# Get OpenAI API key from Azure Key Vault
credential = DefaultAzureCredential()
key_vault_url = os.getenv("AZURE_KEYVAULT_URL")
secret_client = SecretClient(vault_url=key_vault_url, credential=credential)
openai_api_key = secret_client.get_secret("OPENAI-API-KEY").value

# Initialize OpenAI client
from openai import OpenAI
client = OpenAI(api_key=openai_api_key)

# Initialize S3 client
aws_access_key = secret_client.get_secret("AWS-ACCESS-KEY").value
aws_secret_key = secret_client.get_secret("AWS-SECRET-KEY").value
s3_client = boto3.client(
    's3',
    aws_access_key_id=aws_access_key,
    aws_secret_access_key=aws_secret_key
)

# Constants
S3_BUCKET = "proppulse-assets"
BRAND_COLOR = "#1F4AFF"
FONT_FAMILY = "Inter"
IMAGE_SIZE = (1080, 810)  # 4:3 aspect ratio
MAX_REGENERATIONS = 3
REGENERATION_WINDOW_DAYS = 7
REGENERATION_COST = 5.0  # $5 per regeneration after limit

# Banned words and phrases for marketing content
BANNED_PHRASES = [
    "guaranteed", "skyrockets", "risk-free", "100% return", 
    "double your money", "triple your investment", "get rich",
    "never lose", "foolproof", "sure thing", "can't miss"
]

class MarketingAssetAgent:
    """Agent for generating marketing assets using AI."""
    
    def __init__(self, db: Session = None):
        """Initialize the agent."""
        self.db = db
    
    async def generate_property_assets(
        self, 
        property_id: str, 
        developer_id: str,
        regenerate: bool = False,
        background_tasks: Optional[BackgroundTasks] = None
    ) -> Dict[str, Any]:
        """
        Generate marketing assets for a property.
        
        Returns a dictionary with asset URLs and generation status.
        """
        try:
            # Get property data
            from ...db.models.property import Property
            property_data = self.db.query(Property).filter_by(id=property_id).first()
            
            if not property_data:
                return {"success": False, "error": "Property not found"}
            
            # Get developer data
            from ...db.models.developer import Developer
            developer = self.db.query(Developer).filter_by(id=developer_id).first()
            
            if not developer:
                return {"success": False, "error": "Developer not found"}
            
            # Check if this is a regeneration
            asset_id = None
            regeneration_count = 0
            
            if regenerate:
                # Check existing assets
                from ...db.models.marketing import MarketingAsset
                existing_assets = self.db.query(MarketingAsset).filter_by(
                    property_id=property_id
                ).order_by(MarketingAsset.created_at.desc()).all()
                
                if existing_assets:
                    # Get the latest asset
                    latest_asset = existing_assets[0]
                    asset_id = latest_asset.id
                    regeneration_count = latest_asset.regeneration_count + 1
                    
                    # Check regeneration limits
                    if regeneration_count > MAX_REGENERATIONS:
                        # Check if within regeneration window
                        regeneration_window = datetime.utcnow() - timedelta(days=REGENERATION_WINDOW_DAYS)
                        if latest_asset.created_at > regeneration_window:
                            # Charge for regeneration
                            from ...utils.pricing import create_ai_asset_credit_usage
                            credit_usage = create_ai_asset_credit_usage(
                                developer_id=developer_id,
                                plan_id=None,  # Will be filled in by the function
                                asset_type="property_marketing",
                                is_regeneration=True,
                                original_asset_id=asset_id,
                                regeneration_count=regeneration_count
                            )
                            
                            # In a real implementation, save to database
                            # For this example, we'll just print
                            print(f"Charging for regeneration: {credit_usage}")
            
            # Check AI credit availability
            from ...utils.pricing import check_ai_credit_availability
            credit_check = check_ai_credit_availability(developer_id, None)
            
            if not credit_check["has_credits"] and not regenerate:
                return {"success": False, "error": "No AI credits available"}
            
            # Generate assets in background if background_tasks is provided
            if background_tasks:
                background_tasks.add_task(
                    self._generate_and_save_assets,
                    property_data,
                    developer,
                    asset_id,
                    regeneration_count
                )
                
                return {
                    "success": True,
                    "status": "processing",
                    "message": "Asset generation started in background"
                }
            else:
                # Generate assets synchronously
                return await self._generate_and_save_assets(
                    property_data,
                    developer,
                    asset_id,
                    regeneration_count
                )
        except Exception as e:
            print(f"Error generating property assets: {e}")
            return {"success": False, "error": str(e)}
    
    async def _generate_and_save_assets(
        self,
        property_data: Any,
        developer: Any,
        asset_id: Optional[str] = None,
        regeneration_count: int = 0
    ) -> Dict[str, Any]:
        """
        Generate and save marketing assets for a property.
        
        Returns a dictionary with asset URLs and generation status.
        """
        try:
            # Generate hero image
            hero_image_result = await self._generate_hero_image(property_data, developer)
            
            if not hero_image_result["success"]:
                return hero_image_result
            
            # Generate marketing copy
            marketing_copy_result = await self._generate_marketing_copy(property_data, developer)
            
            if not marketing_copy_result["success"]:
                return marketing_copy_result
            
            # Save assets to S3
            s3_result = await self._save_assets_to_s3(
                property_data.id,
                developer.id,
                hero_image_result["image"],
                marketing_copy_result["summary"],
                marketing_copy_result["usp_bullets"]
            )
            
            if not s3_result["success"]:
                return s3_result
            
            # Save to database
            from ...db.models.marketing import MarketingAsset
            
            # Create new asset ID if not regenerating
            if not asset_id:
                asset_id = str(uuid.uuid4())
            
            # Create or update asset record
            asset = MarketingAsset(
                id=asset_id,
                property_id=property_data.id,
                developer_id=developer.id,
                hero_image_url=s3_result["hero_image_url"],
                summary=marketing_copy_result["summary"],
                usp_bullets=marketing_copy_result["usp_bullets"],
                status="draft",  # Requires approval
                is_regeneration=(regeneration_count > 0),
                regeneration_count=regeneration_count,
                created_at=datetime.utcnow()
            )
            
            self.db.add(asset)
            self.db.commit()
            
            # Record AI credit usage
            from ...utils.pricing import create_ai_asset_credit_usage
            credit_usage = create_ai_asset_credit_usage(
                developer_id=developer.id,
                plan_id=None,  # Will be filled in by the function
                asset_type="property_marketing",
                is_regeneration=(regeneration_count > 0),
                original_asset_id=asset_id if regeneration_count > 0 else None,
                regeneration_count=regeneration_count
            )
            
            # In a real implementation, save to database
            # For this example, we'll just print
            print(f"AI credit usage: {credit_usage}")
            
            return {
                "success": True,
                "asset_id": asset_id,
                "hero_image_url": s3_result["hero_image_url"],
                "summary": marketing_copy_result["summary"],
                "usp_bullets": marketing_copy_result["usp_bullets"],
                "status": "draft"
            }
        except Exception as e:
            print(f"Error in _generate_and_save_assets: {e}")
            return {"success": False, "error": str(e)}
    
    async def _generate_hero_image(
        self,
        property_data: Any,
        developer: Any
    ) -> Dict[str, Any]:
        """
        Generate a hero image for a property using DALL·E 3.
        
        Returns a dictionary with the generated image and status.
        """
        try:
            # Create prompt for DALL·E 3
            property_type = property_data.unit_type or "apartment"
            bedrooms = property_data.bedrooms or 1
            view = property_data.view or "city"
            
            prompt = f"""
            Create a photorealistic hero image of a luxury {property_type} with {bedrooms} bedroom(s) in Dubai.
            The property has a beautiful {view} view. The image should be elegant and aspirational,
            showcasing modern architecture and high-end finishes. Use a warm, inviting lighting with
            a professional real estate photography style. The image should be in 4:3 aspect ratio.
            Do not include any text or watermarks in the image.
            """
            
            # Generate image with DALL·E 3
            response = client.images.generate(
                model="dall-e-3",
                prompt=prompt,
                size="1024x768",  # Close to our 1080x810 target
                quality="standard",
                n=1
            )
            
            # Get image URL
            image_url = response.data[0].url
            
            # Download image
            image_response = requests.get(image_url)
            image = Image.open(io.BytesIO(image_response.content))
            
            # Resize to target dimensions
            image = image.resize(IMAGE_SIZE)
            
            # Add developer branding
            image = self._add_branding(image, developer)
            
            # Add disclaimer
            image = self._add_disclaimer(image)
            
            return {
                "success": True,
                "image": image
            }
        except Exception as e:
            print(f"Error generating hero image: {e}")
            return {"success": False, "error": f"Error generating hero image: {str(e)}"}
    
    def _add_branding(self, image: Image.Image, developer: Any) -> Image.Image:
        """
        Add developer branding to an image.
        
        Returns the modified image.
        """
        try:
            # Create a copy of the image
            branded_image = image.copy()
            draw = ImageDraw.Draw(branded_image)
            
            # Load developer logo if available
            logo = None
            if hasattr(developer, 'logo_url') and developer.logo_url:
                try:
                    logo_response = requests.get(developer.logo_url)
                    logo = Image.open(io.BytesIO(logo_response.content))
                    
                    # Resize logo to fit in top-left corner
                    logo_size = (150, 75)  # Adjust as needed
                    logo = logo.resize(logo_size)
                    
                    # Create a white background for the logo
                    logo_bg = Image.new('RGBA', logo_size, (255, 255, 255, 200))
                    
                    # Paste logo background
                    branded_image.paste(logo_bg, (20, 20), logo_bg)
                    
                    # Paste logo
                    branded_image.paste(logo, (20, 20), logo)
                except Exception as logo_error:
                    print(f"Error adding logo: {logo_error}")
            
            # If no logo, add developer name as text
            if not logo:
                # Try to load a font
                try:
                    font = ImageFont.truetype("arial.ttf", 30)
                except:
                    font = ImageFont.load_default()
                
                # Add developer name
                developer_name = developer.legal_name or "Developer"
                draw.rectangle([(20, 20), (320, 70)], fill=(255, 255, 255, 200))
                draw.text((30, 30), developer_name, fill=BRAND_COLOR, font=font)
            
            return branded_image
        except Exception as e:
            print(f"Error adding branding: {e}")
            return image  # Return original image if branding fails
    
    def _add_disclaimer(self, image: Image.Image) -> Image.Image:
        """
        Add disclaimer text to an image.
        
        Returns the modified image.
        """
        try:
            # Create a copy of the image
            disclaimer_image = image.copy()
            draw = ImageDraw.Draw(disclaimer_image)
            
            # Try to load a font
            try:
                font = ImageFont.truetype("arial.ttf", 20)
            except:
                font = ImageFont.load_default()
            
            # Add disclaimer text
            disclaimer = "Images are for illustrative purposes only."
            text_width, text_height = draw.textsize(disclaimer, font=font) if hasattr(draw, 'textsize') else (300, 20)
            
            # Position at bottom right
            x = image.width - text_width - 20
            y = image.height - text_height - 20
            
            # Add background
            draw.rectangle([(x - 10, y - 10), (x + text_width + 10, y + text_height + 10)], fill=(0, 0, 0, 128))
            
            # Add text
            draw.text((x, y), disclaimer, fill=(255, 255, 255), font=font)
            
            return disclaimer_image
        except Exception as e:
            print(f"Error adding disclaimer: {e}")
            return image  # Return original image if disclaimer fails
    
    async def _generate_marketing_copy(
        self,
        property_data: Any,
        developer: Any
    ) -> Dict[str, Any]:
        """
        Generate marketing copy for a property using GPT-4o.
        
        Returns a dictionary with the generated summary, USP bullets, and status.
        """
        try:
            # Create prompt for GPT-4o
            property_type = property_data.unit_type or "apartment"
            bedrooms = property_data.bedrooms or 1
            bathrooms = property_data.bathrooms or 1
            size = property_data.size_ft2 or 1000
            view = property_data.view or "city"
            price = property_data.price or 1000000
            
            # Format price with commas
            formatted_price = f"AED {price:,}"
            
            prompt = f"""
            Create marketing content for a luxury {property_type} in Dubai with the following details:
            - {bedrooms} bedroom(s)
            - {bathrooms} bathroom(s)
            - {size} sq ft
            - {view} view
            - Price: {formatted_price}
            
            Please provide:
            1. A catchy 150-word summary that highlights the property's unique features and investment potential
            2. 5 bullet points highlighting the unique selling propositions (USPs)
            
            The tone should be neutral and investor-oriented. Avoid hype words like "guaranteed", "skyrockets", etc.
            Focus on factual information and the property's actual features.
            """
            
            # Generate content with GPT-4o
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are a professional real estate copywriter specializing in luxury properties in Dubai."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=1000
            )
            
            # Extract content
            content = response.choices[0].message.content
            
            # Parse content
            summary = ""
            usp_bullets = []
            
            # Simple parsing logic - can be improved
            parts = content.split("\n\n")
            if len(parts) >= 2:
                summary = parts[0].strip()
                
                # Extract bullets
                for part in parts[1:]:
                    if "•" in part or "-" in part or "*" in part:
                        lines = part.split("\n")
                        for line in lines:
                            line = line.strip()
                            if line.startswith("•") or line.startswith("-") or line.startswith("*"):
                                bullet = line[1:].strip()
                                usp_bullets.append(bullet)
            
            # Ensure we have exactly 5 USP bullets
            if len(usp_bullets) < 5:
                # Generate more bullets if needed
                additional_prompt = f"""
                Based on the property details:
                - {bedrooms} bedroom(s)
                - {bathrooms} bathroom(s)
                - {size} sq ft
                - {view} view
                - Price: {formatted_price}
                
                Please provide {5 - len(usp_bullets)} more unique selling proposition bullet points.
                """
                
                additional_response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": "You are a professional real estate copywriter specializing in luxury properties in Dubai."},
                        {"role": "user", "content": additional_prompt}
                    ],
                    temperature=0.7,
                    max_tokens=500
                )
                
                additional_content = additional_response.choices[0].message.content
                
                # Extract additional bullets
                for line in additional_content.split("\n"):
                    line = line.strip()
                    if line.startswith("•") or line.startswith("-") or line.startswith("*"):
                        bullet = line[1:].strip()
                        usp_bullets.append(bullet)
                        if len(usp_bullets) >= 5:
                            break
            
            # Truncate to 5 bullets if we have more
            usp_bullets = usp_bullets[:5]
            
            # Check for banned phrases
            for phrase in BANNED_PHRASES:
                if phrase.lower() in summary.lower():
                    summary = summary.replace(phrase, "[investment opportunity]")
                
                for i, bullet in enumerate(usp_bullets):
                    if phrase.lower() in bullet.lower():
                        usp_bullets[i] = bullet.replace(phrase, "[investment opportunity]")
            
            return {
                "success": True,
                "summary": summary,
                "usp_bullets": usp_bullets
            }
        except Exception as e:
            print(f"Error generating marketing copy: {e}")
            return {"success": False, "error": f"Error generating marketing copy: {str(e)}"}
    
    async def _save_assets_to_s3(
        self,
        property_id: str,
        developer_id: str,
        hero_image: Image.Image,
        summary: str,
        usp_bullets: List[str]
    ) -> Dict[str, Any]:
        """
        Save generated assets to S3.
        
        Returns a dictionary with asset URLs and status.
        """
        try:
            # Create unique filename
            timestamp = int(time.time())
            filename_base = f"{developer_id}/{property_id}/{timestamp}"
            
            # Save hero image
            hero_image_key = f"{filename_base}_hero.jpg"
            
            # Convert PIL Image to bytes
            img_byte_arr = io.BytesIO()
            hero_image.save(img_byte_arr, format='JPEG')
            img_byte_arr.seek(0)
            
            # Upload to S3
            s3_client.upload_fileobj(
                img_byte_arr,
                S3_BUCKET,
                hero_image_key,
                ExtraArgs={
                    'ContentType': 'image/jpeg',
                    'ACL': 'public-read'
                }
            )
            
            # Generate public URL
            hero_image_url = f"https://{S3_BUCKET}.s3.amazonaws.com/{hero_image_key}"
            
            # Save marketing copy as JSON
            marketing_copy = {
                "summary": summary,
                "usp_bullets": usp_bullets,
                "generated_at": timestamp
            }
            
            copy_key = f"{filename_base}_copy.json"
            
            s3_client.put_object(
                Bucket=S3_BUCKET,
                Key=copy_key,
                Body=json.dumps(marketing_copy),
                ContentType='application/json',
                ACL='public-read'
            )
            
            # Generate public URL for copy
            copy_url = f"https://{S3_BUCKET}.s3.amazonaws.com/{copy_key}"
            
            return {
                "success": True,
                "hero_image_url": hero_image_url,
                "copy_url": copy_url
            }
        except Exception as e:
            print(f"Error saving assets to S3: {e}")
            return {"success": False, "error": f"Error saving assets to S3: {str(e)}"}
    
    async def approve_asset(self, asset_id: str) -> Dict[str, Any]:
        """
        Approve a marketing asset.
        
        Returns a dictionary with approval status.
        """
        try:
            # Get asset
            from ...db.models.marketing import MarketingAsset
            asset = self.db.query(MarketingAsset).filter_by(id=asset_id).first()
            
            if not asset:
                return {"success": False, "error": "Asset not found"}
            
            # Update status
            asset.status = "approved"
            asset.approved_at = datetime.utcnow()
            
            # Save to database
            self.db.commit()
            
            return {
                "success": True,
                "asset_id": asset_id,
                "status": "approved"
            }
        except Exception as e:
            print(f"Error approving asset: {e}")
            return {"success": False, "error": str(e)}
    
    async def reject_asset(self, asset_id: str, feedback: str) -> Dict[str, Any]:
        """
        Reject a marketing asset.
        
        Returns a dictionary with rejection status.
        """
        try:
            # Get asset
            from ...db.models.marketing import MarketingAsset
            asset = self.db.query(MarketingAsset).filter_by(id=asset_id).first()
            
            if not asset:
                return {"success": False, "error": "Asset not found"}
            
            # Update status
            asset.status = "rejected"
            asset.rejection_feedback = feedback
            asset.rejected_at = datetime.utcnow()
            
            # Save to database
            self.db.commit()
            
            return {
                "success": True,
                "asset_id": asset_id,
                "status": "rejected",
                "feedback": feedback
            }
        except Exception as e:
            print(f"Error rejecting asset: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_asset(self, asset_id: str) -> Dict[str, Any]:
        """
        Get a marketing asset by ID.
        
        Returns the asset details.
        """
        try:
            # Get asset
            from ...db.models.marketing import MarketingAsset
            asset = self.db.query(MarketingAsset).filter_by(id=asset_id).first()
            
            if not asset:
                return {"success": False, "error": "Asset not found"}
            
            return {
                "success": True,
                "asset": {
                    "id": asset.id,
                    "property_id": asset.property_id,
                    "developer_id": asset.developer_id,
                    "hero_image_url": asset.hero_image_url,
                    "summary": asset.summary,
                    "usp_bullets": asset.usp_bullets,
                    "status": asset.status,
                    "is_regeneration": asset.is_regeneration,
                    "regeneration_count": asset.regeneration_count,
                    "created_at": asset.created_at.isoformat(),
                    "approved_at": asset.approved_at.isoformat() if asset.approved_at else None,
                    "rejected_at": asset.rejected_at.isoformat() if asset.rejected_at else None,
                    "rejection_feedback": asset.rejection_feedback
                }
            }
        except Exception as e:
            print(f"Error getting asset: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_property_assets(self, property_id: str) -> Dict[str, Any]:
        """
        Get all marketing assets for a property.
        
        Returns a list of assets.
        """
        try:
            # Get assets
            from ...db.models.marketing import MarketingAsset
            assets = self.db.query(MarketingAsset).filter_by(
                property_id=property_id
            ).order_by(MarketingAsset.created_at.desc()).all()
            
            # Format assets
            formatted_assets = []
            for asset in assets:
                formatted_assets.append({
                    "id": asset.id,
                    "property_id": asset.property_id,
                    "developer_id": asset.developer_id,
                    "hero_image_url": asset.hero_image_url,
                    "summary": asset.summary,
                    "usp_bullets": asset.usp_bullets,
                    "status": asset.status,
                    "is_regeneration": asset.is_regeneration,
                    "regeneration_count": asset.regeneration_count,
                    "created_at": asset.created_at.isoformat(),
                    "approved_at": asset.approved_at.isoformat() if asset.approved_at else None,
                    "rejected_at": asset.rejected_at.isoformat() if asset.rejected_at else None,
                    "rejection_feedback": asset.rejection_feedback
                })
            
            return {
                "success": True,
                "assets": formatted_assets
            }
        except Exception as e:
            print(f"Error getting property assets: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_developer_assets(self, developer_id: str) -> Dict[str, Any]:
        """
        Get all marketing assets for a developer.
        
        Returns a list of assets.
        """
        try:
            # Get assets
            from ...db.models.marketing import MarketingAsset
            assets = self.db.query(MarketingAsset).filter_by(
                developer_id=developer_id
            ).order_by(MarketingAsset.created_at.desc()).all()
            
            # Format assets
            formatted_assets = []
            for asset in assets:
                formatted_assets.append({
                    "id": asset.id,
                    "property_id": asset.property_id,
                    "developer_id": asset.developer_id,
                    "hero_image_url": asset.hero_image_url,
                    "summary": asset.summary,
                    "usp_bullets": asset.usp_bullets,
                    "status": asset.status,
                    "is_regeneration": asset.is_regeneration,
                    "regeneration_count": asset.regeneration_count,
                    "created_at": asset.created_at.isoformat(),
                    "approved_at": asset.approved_at.isoformat() if asset.approved_at else None,
                    "rejected_at": asset.rejected_at.isoformat() if asset.rejected_at else None,
                    "rejection_feedback": asset.rejection_feedback
                })
            
            return {
                "success": True,
                "assets": formatted_assets
            }
        except Exception as e:
            print(f"Error getting developer assets: {e}")
            return {"success": False, "error": str(e)}
