import hmac
import hashlib
import json
import httpx
import os
from datetime import datetime, timezone
from typing import Dict, Any, Optional
import logging
from urllib.parse import urljoin

logger = logging.getLogger(__name__)

class PaymentGatewayException(Exception):
    pass

class PaymentGatewayClient:
    def __init__(self):
        # Load from environment variables
        self.client_id = os.getenv("ORCHARD_API_KEY")
        self.client_secret = os.getenv("ORCHARD_SECRET_KEY")
        self.service_id = os.getenv("ORCHARD_SERVICE_ID")
        self.base_url = os.getenv("ORCHARD_BASE_URL", "https://orchard-api.anmgw.com")
        self.callback_url = os.getenv("PAYMENT_CALLBACK_URL")
        self.timeout = int(os.getenv("PAYMENT_TIMEOUT", "30"))

        # Validate required config
        self._validate_config()

    def _validate_config(self):
        """Validate that all required config is present"""
        required_vars = {
            "ORCHARD_API_KEY": self.client_id,
            "ORCHARD_SECRET_KEY": self.client_secret,
            "ORCHARD_SERVICE_ID": self.service_id,
            "PAYMENT_CALLBACK_URL": self.callback_url
        }

        missing_vars = [key for key, value in required_vars.items() if not value]

        if missing_vars:
            error_msg = f"Missing required environment variables: {', '.join(missing_vars)}"
            logger.error(error_msg)
            raise PaymentGatewayException(error_msg)
    
    def process_payment(self, payment_request: Dict[str, Any]) -> httpx.Response:
        try:
            # Create authorization header with sorted JSON (for consistent signature)
            authorization = self._create_authorization_header(payment_request)
            logger.info(f"Authorization Header: {authorization}")

            # Use the same sorted JSON format for the request body to match signature
            json_string = json.dumps(payment_request, sort_keys=True, separators=(',', ':'))
            logger.debug(f"Request payload: {json_string}")

            # Orchard API endpoint is /sendRequest
            endpoint_url = urljoin(self.base_url, "/sendRequest")
            logger.info(f"Sending payment request to: {endpoint_url}")

            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    endpoint_url,
                    headers={
                        "Authorization": authorization,
                        "Content-Type": "application/json"
                    },
                    content=json_string
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
    
    def _create_authorization_header(self, request: Dict[str, Any]) -> str:
        # Use sorted keys and compact separators for consistent signature generation
        json_payload = json.dumps(request, sort_keys=True, separators=(',', ':'))
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
    
    def check_transaction_status(self, external_transaction_id: str) -> httpx.Response:
        try:
            request = {
                "exttrid": external_transaction_id,
                "service_id": self.service_id,
                "trans_type": "TSC"
            }

            # Use sorted JSON for consistent signature and request body
            json_payload = json.dumps(request, sort_keys=True, separators=(',', ':'))
            signature = self._get_signature(json_payload)
            logger.debug(f"Status check request payload: {json_payload}")

            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    urljoin(self.base_url, "checkTransaction"),
                    headers={
                        "Authorization": f"{self.client_id}:{signature}",
                        "Content-Type": "application/json"
                    },
                    content=json_payload
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

    def check_wallet_balance(self) -> httpx.Response:
        """
        Check merchant wallet balance from Orchard API.
        Uses the dedicated /check_wallet_balance endpoint.

        Returns:
            httpx.Response with wallet balance data
        """
        try:
            request = {
                "service_id": self.service_id,
                "trans_type": "BLC"
            }

            # Use sorted JSON for consistent signature and request body
            json_payload = json.dumps(request, sort_keys=True, separators=(',', ':'))
            signature = self._get_signature(json_payload)
            logger.debug(f"Balance check request payload: {json_payload}")

            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    urljoin(self.base_url, "/check_wallet_balance"),
                    headers={
                        "Authorization": f"{self.client_id}:{signature}",
                        "Content-Type": "application/json"
                    },
                    content=json_payload
                )

            logger.info(f"Wallet balance check response: status={response.status_code}, body={response.text}")
            return response

        except httpx.TimeoutException:
            logger.error("Wallet balance check timeout")
            raise PaymentGatewayException("Wallet balance check timeout")
        except httpx.RequestError as e:
            logger.error(f"Network error checking wallet balance: {e}")
            raise PaymentGatewayException(f"Network error: {e}")
        except Exception as e:
            logger.error(f"Error checking wallet balance: {e}", exc_info=True)
            raise PaymentGatewayException(f"Failed to check wallet balance: {e}")

    def account_inquiry(self, customer_number: str, network: str, bank_code: Optional[str] = None) -> httpx.Response:
        """
        Perform account information inquiry (AII) to verify recipient account details.
        Useful before initiating money transfers to confirm account holder information.

        Args:
            customer_number: Phone number or account number (e.g., 233200018204)
            network: Network/Bank code (MTN, VOD, AIR for mobile, BNK for bank)
            bank_code: Bank code (required if network is BNK)

        Returns:
            httpx.Response with account information from Orchard API
        """
        try:
            from utilities.uniqueidgenerator import UniqueIdGenerator

            request = {
                "service_id": self.service_id,
                "trans_type": "AII",  # Account Information Inquiry
                "customer_number": customer_number,
                "nw": "BNK",  # Always BNK for account inquiry
                "exttrid": str(UniqueIdGenerator.generate()),  # Required: unique transaction ID
                "bank_code": bank_code or network,  # bank_code specifies the actual network (MTN, VOD, AIR, or specific bank code)
                "ts": self.get_current_timestamp()  # Required: timestamp
            }

            # Use sorted JSON with spaces for signature (Orchard API requirement)
            json_payload = json.dumps(request, sort_keys=True, separators=(', ', ': '))
            signature = self._get_signature(json_payload)
            logger.info(f"[ACCOUNT_INQUIRY] Request payload: {json_payload}")

            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    urljoin(self.base_url, "/sendRequest"),
                    headers={
                        "Authorization": f"{self.client_id}:{signature}",
                        "Content-Type": "application/json"
                    },
                    content=json_payload
                )

            logger.info(f"[ACCOUNT_INQUIRY_RESPONSE] Status: {response.status_code}, Body: {response.text}")
            return response

        except httpx.TimeoutException:
            logger.error("Account inquiry timeout")
            raise PaymentGatewayException("Account inquiry timeout")
        except httpx.RequestError as e:
            logger.error(f"Network error during account inquiry: {e}")
            raise PaymentGatewayException(f"Network error: {e}")
        except Exception as e:
            logger.error(f"Error performing account inquiry: {e}", exc_info=True)
            raise PaymentGatewayException(f"Failed to perform account inquiry: {e}")

    def external_billers_inquiry(self, customer_number: str, network: str = "ABS", operation: str = "INF") -> httpx.Response:
        """
        Perform external billers inquiry (BLI) to query available billers and bill information.
        Uses the /extBillers endpoint instead of /sendRequest.

        Args:
            customer_number: Customer phone number or account number (e.g., 020410181221)
            network: Network code (default: "ABS" for external billers)
            operation: Operation type (default: "INF" for information inquiry)

        Returns:
            httpx.Response with available billers and bill information from Orchard API
        """
        try:
            from utilities.uniqueidgenerator import UniqueIdGenerator

            request = {
                "service_id": self.service_id,
                "trans_type": "BLI",  # Bill Inquiry
                "customer_number": customer_number,
                "nw": network,  # Network code (ABS for external billers)
                "operation": operation,  # Operation type (INF for information)
                "exttrid": str(UniqueIdGenerator.generate()),  # Required: unique transaction ID
                "ts": self.get_current_timestamp()  # Required: timestamp
            }

            # Use sorted JSON for consistent signature and request body
            json_payload = json.dumps(request, sort_keys=True, separators=(',', ':'))
            signature = self._get_signature(json_payload)
            logger.info(f"[EXTERNAL_BILLERS_INQUIRY] Request payload: {json_payload}")

            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    urljoin(self.base_url, "/extBillers"),
                    headers={
                        "Authorization": f"{self.client_id}:{signature}",
                        "Content-Type": "application/json"
                    },
                    content=json_payload
                )

            logger.info(f"[EXTERNAL_BILLERS_INQUIRY_RESPONSE] Status: {response.status_code}, Body: {response.text}")
            return response

        except httpx.TimeoutException:
            logger.error("External billers inquiry timeout")
            raise PaymentGatewayException("External billers inquiry timeout")
        except httpx.RequestError as e:
            logger.error(f"Network error during external billers inquiry: {e}")
            raise PaymentGatewayException(f"Network error: {e}")
        except Exception as e:
            logger.error(f"Error performing external billers inquiry: {e}", exc_info=True)
            raise PaymentGatewayException(f"Failed to perform external billers inquiry: {e}")

    def external_biller_invoice_inquiry(self,
                                       ext_biller_ref_id: str,
                                       ext_biller_pan: str,
                                       ext_biller_ref_type: str,
                                       network: str = "ABS",
                                       operation: str = "INV") -> httpx.Response:
        """
        Perform external biller invoice inquiry (BLI with operation INV) to get customer invoice details.
        Uses the /extBillers endpoint with operation "INV".

        Args:
            ext_biller_ref_id: Biller ID from billers list inquiry (e.g., "D9C37F3D52")
            ext_biller_pan: Customer reference/ID for that biller (e.g., "20784533")
            ext_biller_ref_type: Biller category/type (e.g., "School Fees")
            network: Network code (default: "ABS" for external billers)
            operation: Operation type (default: "INV" for invoice inquiry)

        Returns:
            httpx.Response with customer invoice information from Orchard API
        """
        try:
            from utilities.uniqueidgenerator import UniqueIdGenerator

            request = {
                "service_id": self.service_id,
                "trans_type": "BLI",  # Bill Inquiry
                "ext_biller_ref_id": ext_biller_ref_id,  # Biller ID
                "ext_biller_pan": ext_biller_pan,  # Customer reference for biller
                "ext_biller_ref_type": ext_biller_ref_type,  # Biller category/type
                "nw": network,  # Network code (ABS for external billers)
                "operation": operation,  # Operation type (INV for invoice)
                "exttrid": str(UniqueIdGenerator.generate()),  # Required: unique transaction ID
                "ts": self.get_current_timestamp()  # Required: timestamp
            }

            # Use sorted JSON for consistent signature and request body
            json_payload = json.dumps(request, sort_keys=True, separators=(',', ':'))
            signature = self._get_signature(json_payload)
            logger.info(f"[EXTERNAL_BILLER_INVOICE_INQUIRY] Request payload: {json_payload}")

            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    urljoin(self.base_url, "/extBillers"),
                    headers={
                        "Authorization": f"{self.client_id}:{signature}",
                        "Content-Type": "application/json"
                    },
                    content=json_payload
                )

            logger.info(f"[EXTERNAL_BILLER_INVOICE_INQUIRY_RESPONSE] Status: {response.status_code}, Body: {response.text}")
            return response

        except httpx.TimeoutException:
            logger.error("External biller invoice inquiry timeout")
            raise PaymentGatewayException("External biller invoice inquiry timeout")
        except httpx.RequestError as e:
            logger.error(f"Network error during external biller invoice inquiry: {e}")
            raise PaymentGatewayException(f"Network error: {e}")
        except Exception as e:
            logger.error(f"Error performing external biller invoice inquiry: {e}", exc_info=True)
            raise PaymentGatewayException(f"Failed to perform external biller invoice inquiry: {e}")