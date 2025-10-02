import hmac
import hashlib
import json
import httpx
from datetime import datetime, timezone
from typing import Dict, Any, Optional
import logging
from urllib.parse import urljoin

logger = logging.getLogger(__name__)

class PaymentGatewayException(Exception):
    pass

class PaymentGatewayClient:
    def __init__(self):
        self.client_secret = "your_client_secret"  # Should be from config
        self.client_id = "your_client_id"          # Should be from config
        self.base_url = "https://orchard-api.anmgw.com/"
        self.service_id = "your_service_id"        # Should be from config
        self.callback_url = "your_callback_url"    # Should be from config
        self.timeout = 30  # seconds
    
    async def process_payment(self, payment_request: Dict[str, Any]) -> httpx.Response:
        try:
            authorization = await self._create_authorization_header(payment_request)
            logger.info(f"Authorization Header: {authorization}")
            
            json_string = json.dumps(payment_request)
            logger.debug(f"Request payload: {json_string}")
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.base_url,
                    headers={
                        "Authorization": authorization,
                        "Content-Type": "application/json"
                    },
                    json=payment_request
                )
                
            logger.info(f"Payment gateway raw response: status={response.status_code}, body={response.text}")
            return response
            
        except httpx.TimeoutException:
            logger.error("Payment processing timeout")
            raise PaymentGatewayException("Payment processing timeout")
        except httpx.RequestError as e:
            logger.error(f"Network error processing payment request: {e}")
            raise PaymentGatewayException(f"Network error: {e}")
        except Exception as e:
            logger.error(f"Error processing payment request: {e}", exc_info=True)
            raise PaymentGatewayException(f"Failed to process payment request: {e}")
    
    async def _create_authorization_header(self, request: Dict[str, Any]) -> str:
        json_payload = json.dumps(request)
        logger.debug(f"Creating signature for payload: {json_payload}")
        signature = self._get_signature(json_payload)
        return f"{self.client_id}:{signature}"
    
    def _get_signature(self, json_payload: str) -> str:
        logger.info(f"HmacSHA256 =================> {json_payload}")
        try:
            # Create HMAC-SHA256 signature
            signature = hmac.new(
                self.client_secret.encode('utf-8'),
                json_payload.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            return signature
        except Exception as e:
            logger.error(f"Error generating signature: {e}")
            raise PaymentGatewayException(f"Signature generation failed: {e}")
    
    def get_current_timestamp(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    
    def build_callback_url(self) -> str:
        return self.callback_url  # Just return the callback URL directly
    
    async def check_transaction_status(self, external_transaction_id: str) -> httpx.Response:
        try:
            request = {
                "exttrid": external_transaction_id,
                "service_id": self.service_id,
                "trans_type": "TSC"
            }
            
            json_payload = json.dumps(request)
            signature = self._get_signature(json_payload)
            logger.debug(f"Status check request payload: {json_payload}")
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    urljoin(self.base_url, "checkTransaction"),
                    headers={
                        "Authorization": f"{self.client_id}:{signature}",
                        "Content-Type": "application/json"
                    },
                    json=request
                )
                
            logger.info(f"Transaction status check response: status={response.status_code}, body={response.text}")
            return response
            
        except httpx.TimeoutException:
            logger.error("Transaction status check timeout")
            raise PaymentGatewayException("Transaction status check timeout")
        except httpx.RequestError as e:
            logger.error(f"Network error checking transaction status: {e}")
            raise PaymentGatewayException(f"Network error: {e}")
        except Exception as e:
            logger.error(f"Error checking transaction status: {e}", exc_info=True)
            raise PaymentGatewayException(f"Failed to check transaction status: {e}")