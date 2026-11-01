import json
from typing import Dict, Optional

import requests # client


class RegistryClient:
    """REST client used by services and connectors to talk to System Catalog."""

    def __init__(self, catalog_url: str):
        self.catalog_url = catalog_url.rstrip("/")

    def register(self, payload: Dict) -> Dict:
        response = requests.post(f"{self.catalog_url}/register", json=payload, timeout=5)
        response.raise_for_status() # request to register
        data = response.json()
        if data.get("status") != "success":
            raise RuntimeError(f"registration failed: {data}")
        return data.get("setting", {})

    def unregister(self, kind: str, object_id: str):
        response = requests.delete(f"{self.catalog_url}/{kind}/{object_id}", timeout=5)
        response.raise_for_status()
        return response.json()

    def get_setting(self) -> Dict:
        response = requests.get(f"{self.catalog_url}/setting", timeout=5)
        response.raise_for_status()
        return response.json()

    def update_setting(self, payload: Dict) -> Dict:
        response = requests.patch(
            f"{self.catalog_url}/setting",
            json=payload,
            timeout=5,
        )
        response.raise_for_status()
        return response.json()

    def get_devices(self, device_type: Optional[str] = None) -> Dict:
        suffix = f"/devices/{device_type}" if device_type else "/devices"
        response = requests.get(f"{self.catalog_url}{suffix}", timeout=5)
        response.raise_for_status()
        return response.json()

    def get_services(self, service_type: Optional[str] = None) -> Dict:
        suffix = f"/services/{service_type}" if service_type else "/services"
        response = requests.get(f"{self.catalog_url}{suffix}", timeout=5)
        response.raise_for_status()
        return response.json()
