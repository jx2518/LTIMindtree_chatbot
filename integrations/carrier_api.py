"""
Carrier API Integration Layer

This module handles communication with different carrier APIs:
1. Project44 for multi-carrier tracking
2. FedEx API
3. UPS API
4. Mock implementations for demonstration
"""

import json
import asyncio
import random
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
import httpx

from models.state import ShipmentDetails, ShipmentStatus, APIResponse
from config import CARRIER_CONFIGS, Config

class CarrierType(str, Enum):
    """Supported carrier types"""
    FEDEX = "fedex"
    UPS = "ups"
    YRC = "yrc"
    ESTES = "estes"
    PROJECT44 = "project44"
    UNKNOWN = "unknown"

@dataclass
class TrackingEvent:
    """Individual tracking event"""
    timestamp: datetime
    location: str
    description: str
    status_code: str
    
class MockCarrierAPI:
    """Mock carrier API for demonstration and testing"""
    
    def __init__(self):
        # Import and convert sample data to carrier API format
        try:
            from data.sample_data import SAMPLE_SHIPMENTS
            self.mock_shipments = {}
            
            # Convert sample data format to carrier API format
            for pro_number, shipment_data in SAMPLE_SHIPMENTS.items():
                self.mock_shipments[pro_number] = {
                    "pro_number": pro_number,
                    "carrier": shipment_data["carrier"],
                    "status": shipment_data["status"].value.lower(),
                    "origin": shipment_data["origin"],
                    "destination": shipment_data["destination"],
                    "pickup_date": shipment_data["pickup_date"],
                    "estimated_delivery": shipment_data.get("delivery_date", "2024-01-20"),
                    "weight": shipment_data["weight"],
                    "events": [
                        {
                            "timestamp": event["timestamp"],
                            "location": event["location"],
                            "description": event["event"],
                            "status": event["status"].lower()
                        }
                        for event in shipment_data["tracking_events"]
                    ]
                }
        except ImportError:
            # Fallback to hardcoded data if sample_data not available
            self.mock_shipments = {
                "1234567890": {
                    "pro_number": "1234567890",
                    "carrier": "FedEx",
                    "status": "in_transit",
                    "origin": "Chicago, IL",
                    "destination": "New York, NY",
                    "pickup_date": "2024-01-15",
                    "estimated_delivery": "2024-01-18",
                    "weight": 150.5,
                    "events": [
                        {"timestamp": "2024-01-15T10:00:00Z", "location": "Chicago, IL", "description": "Shipment picked up", "status": "picked_up"},
                        {"timestamp": "2024-01-16T08:30:00Z", "location": "Indianapolis, IN", "description": "In transit", "status": "in_transit"},
                        {"timestamp": "2024-01-17T14:20:00Z", "location": "Pittsburgh, PA", "description": "Arrived at terminal", "status": "in_transit"}
                    ]
                }
            }
    
    async def track_shipment(self, pro_number: str, carrier: str = None) -> APIResponse:
        """Mock tracking API call"""
        
        # Simulate API delay
        await asyncio.sleep(random.uniform(0.5, 2.0))
        
        if pro_number in self.mock_shipments:
            shipment_data = self.mock_shipments[pro_number]
            return APIResponse(
                success=True,
                data=shipment_data,
                carrier=shipment_data["carrier"],
                timestamp=datetime.now()
            )
        else:
            return APIResponse(
                success=False,
                error=f"Shipment not found for PRO number {pro_number}",
                carrier=carrier or "unknown",
                timestamp=datetime.now()
            )

class Project44API:
    """Project44 API integration for multi-carrier tracking"""
    
    def __init__(self, api_key: str, base_url: str = "https://api.project44.com"):
        self.api_key = api_key
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=Config.API_TIMEOUT)
        
    async def track_shipment(self, pro_number: str, carrier: str = None) -> APIResponse:
        """Track shipment via Project44 API"""
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # Project44 tracking endpoint
        url = f"{self.base_url}/api/v4/shipments/search"
        payload = {
            "shipment": {
                "identifiers": {
                    "pro": pro_number
                }
            }
        }
        
        if carrier:
            payload["shipment"]["carrier"] = {"scac": carrier.upper()}
        
        try:
            response = await self.client.post(url, headers=headers, json=payload)
            
            if response.status_code == 200:
                data = response.json()
                shipment_info = self._parse_project44_response(data)
                
                return APIResponse(
                    success=True,
                    data=shipment_info,
                    carrier=carrier,
                    timestamp=datetime.now()
                )
            else:
                return APIResponse(
                    success=False,
                    error=f"Project44 API error: {response.status_code}",
                    carrier=carrier,
                    timestamp=datetime.now()
                )
                
        except Exception as e:
            return APIResponse(
                success=False,
                error=f"Project44 API connection error: {str(e)}",
                carrier=carrier,
                timestamp=datetime.now()
            )
    
    def _parse_project44_response(self, data: Dict) -> Dict[str, Any]:
        """Parse Project44 API response into standard format"""
        # This would parse the actual Project44 response format
        # For now, return a structured format
        return {
            "pro_number": data.get("shipment", {}).get("identifiers", {}).get("pro"),
            "status": data.get("shipment", {}).get("status"),
            "carrier": data.get("shipment", {}).get("carrier", {}).get("name"),
            "events": data.get("shipment", {}).get("positions", [])
        }

class FedExAPI:
    """FedEx API integration"""
    
    def __init__(self, api_key: str, base_url: str = "https://apis.fedex.com"):
        self.api_key = api_key
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=Config.API_TIMEOUT)
    
    async def track_shipment(self, tracking_number: str) -> APIResponse:
        """Track shipment via FedEx API"""
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-locale": "en_US"
        }
        
        url = f"{self.base_url}/track/v1/trackingnumbers"
        payload = {
            "includeDetailedScans": True,
            "trackingInfo": [
                {
                    "trackingNumberInfo": {
                        "trackingNumber": tracking_number
                    }
                }
            ]
        }
        
        try:
            response = await self.client.post(url, headers=headers, json=payload)
            
            if response.status_code == 200:
                data = response.json()
                shipment_info = self._parse_fedex_response(data)
                
                return APIResponse(
                    success=True,
                    data=shipment_info,
                    carrier="FedEx",
                    timestamp=datetime.now()
                )
            else:
                return APIResponse(
                    success=False,
                    error=f"FedEx API error: {response.status_code}",
                    carrier="FedEx",
                    timestamp=datetime.now()
                )
                
        except Exception as e:
            return APIResponse(
                success=False,
                error=f"FedEx API connection error: {str(e)}",
                carrier="FedEx",
                timestamp=datetime.now()
            )
    
    def _parse_fedex_response(self, data: Dict) -> Dict[str, Any]:
        """Parse FedEx API response into standard format"""
        # Parse FedEx-specific response format
        track_results = data.get("output", {}).get("completeTrackResults", [])
        if track_results:
            result = track_results[0]
            track_data = result.get("trackResults", [{}])[0]
            
            return {
                "pro_number": track_data.get("trackingNumberInfo", {}).get("trackingNumber"),
                "status": track_data.get("latestStatusDetail", {}).get("code"),
                "carrier": "FedEx",
                "events": track_data.get("scanEvents", [])
            }
        
        return {}

class CarrierAPIManager:
    """Main manager for all carrier APIs"""
    
    def __init__(self, use_mock: bool = True):
        self.use_mock = use_mock
        
        # Initialize APIs
        if use_mock:
            self.mock_api = MockCarrierAPI()
        else:
            # Initialize real APIs if keys are available
            if Config.PROJECT44_API_KEY:
                self.project44 = Project44API(Config.PROJECT44_API_KEY)
            if Config.FEDEX_API_KEY:
                self.fedex = FedExAPI(Config.FEDEX_API_KEY)
    
    async def track_shipment(self, pro_number: str, carrier: str = None) -> APIResponse:
        """Track a shipment using the appropriate API"""
        
        if self.use_mock:
            return await self.mock_api.track_shipment(pro_number, carrier)
        
        # Determine which API to use based on carrier or PRO number format
        carrier_type = self._identify_carrier(pro_number, carrier)
        
        try:
            if carrier_type == CarrierType.FEDEX and hasattr(self, 'fedex'):
                return await self.fedex.track_shipment(pro_number)
            
            elif hasattr(self, 'project44'):
                # Use Project44 for multi-carrier tracking
                return await self.project44.track_shipment(pro_number, carrier)
            
            else:
                return APIResponse(
                    success=False,
                    error="No suitable API configured for this carrier",
                    carrier=carrier or "unknown",
                    timestamp=datetime.now()
                )
                
        except Exception as e:
            return APIResponse(
                success=False,
                error=f"API tracking error: {str(e)}",
                carrier=carrier or "unknown", 
                timestamp=datetime.now()
            )
    
    async def search_by_details(self, origin: str = None, destination: str = None,
                               pickup_date: str = None, reference: str = None,
                               carrier: str = None) -> APIResponse:
        """Search for shipments by details when PRO number is not available"""
        
        if self.use_mock:
            return await self._mock_search_by_details(origin, destination, pickup_date, reference, carrier)
        
        # In a real implementation, this would call the appropriate carrier APIs
        # For now, return mock data
        return APIResponse(
            success=False,
            error="Search by details not implemented for production APIs",
            carrier=carrier or "unknown",
            timestamp=datetime.now()
        )
    
    async def _mock_search_by_details(self, origin: str = None, destination: str = None,
                                     pickup_date: str = None, reference: str = None,
                                     carrier: str = None) -> APIResponse:
        """Mock search by shipment details"""
        
        await asyncio.sleep(random.uniform(1.0, 3.0))  # Simulate API delay
        
        # Simple mock logic - find shipments that match criteria
        matching_shipments = []
        
        for pro, shipment in self.mock_api.mock_shipments.items():
            match = True
            
            if origin and origin.lower() not in shipment["origin"].lower():
                match = False
            if destination and destination.lower() not in shipment["destination"].lower():
                match = False
            if carrier and carrier.lower() not in shipment["carrier"].lower():
                match = False
            
            if match:
                matching_shipments.append(shipment)
        
        if matching_shipments:
            return APIResponse(
                success=True,
                data={"shipments": matching_shipments},
                carrier=carrier or "multiple",
                timestamp=datetime.now()
            )
        else:
            return APIResponse(
                success=False,
                error="No shipments found matching the provided criteria",
                carrier=carrier or "unknown",
                timestamp=datetime.now()
            )
    
    def _identify_carrier(self, pro_number: str, carrier_hint: str = None) -> CarrierType:
        """Identify carrier based on PRO number format or hint"""
        
        if carrier_hint:
            carrier_hint = carrier_hint.lower()
            if "fedex" in carrier_hint:
                return CarrierType.FEDEX
            elif "ups" in carrier_hint:
                return CarrierType.UPS
            elif "yrc" in carrier_hint:
                return CarrierType.YRC
            elif "estes" in carrier_hint:
                return CarrierType.ESTES
        
        # Identify by PRO number format
        if pro_number.startswith("1Z"):
            return CarrierType.UPS
        elif len(pro_number) == 12 and pro_number.isdigit():
            return CarrierType.FEDEX
        elif len(pro_number) in [7, 8, 9, 10] and pro_number.isdigit():
            return CarrierType.PROJECT44  # General LTL
        
        return CarrierType.UNKNOWN
    
    async def get_carrier_contact_info(self, carrier: str) -> Dict[str, str]:
        """Get contact information for a carrier"""
        
        carrier_lower = carrier.lower()
        
        if carrier_lower in CARRIER_CONFIGS:
            config = CARRIER_CONFIGS[carrier_lower]
            return {
                "name": config["name"],
                "email": config["contact_email"],
                "phone": config.get("phone", "1-800-GO-FEDEX")  # Default or lookup
            }
        
        # Default contact info
        return {
            "name": carrier,
            "email": f"customer.service@{carrier_lower}.com",
            "phone": "Contact customer service"
        }
    
    async def validate_pro_number(self, pro_number: str, carrier: str = None) -> Dict[str, Any]:
        """Validate PRO number format"""
        
        result = {
            "valid": False,
            "carrier": None,
            "format_issues": []
        }
        
        # Basic validation
        if not pro_number or not pro_number.strip():
            result["format_issues"].append("PRO number is empty")
            return result
        
        pro_clean = pro_number.strip().replace(" ", "").replace("-", "")
        
        # Length validation
        if len(pro_clean) < 7:
            result["format_issues"].append("PRO number too short (minimum 7 digits)")
        elif len(pro_clean) > 12:
            result["format_issues"].append("PRO number too long (maximum 12 characters)")
        
        # Format validation
        identified_carrier = self._identify_carrier(pro_clean, carrier)
        
        if identified_carrier != CarrierType.UNKNOWN:
            result["valid"] = True
            result["carrier"] = identified_carrier.value
        else:
            result["format_issues"].append("PRO number format not recognized")
        
        return result
    
    async def close(self):
        """Close HTTP clients"""
        if hasattr(self, 'project44'):
            await self.project44.client.aclose()
        if hasattr(self, 'fedex'):
            await self.fedex.client.aclose() 