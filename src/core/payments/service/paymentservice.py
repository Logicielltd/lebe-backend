from decimal import Decimal
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from enum import Enum
import logging
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from fastapi import HTTPException

from core.payments.dto.paymentdto import PaymentDto
from core.payments.dto.response.paymentresultresponse import PaymentResultResponse
from core.payments.model.paymentmethod import PaymentMethod
from core.payments.model.timeline import Timeline
from core.payments.model.paymentstatus import PaymentStatus
from core.payments.model.paynetwork import Network
from core.exceptions.PaymentException import PaymentNotFoundException, PaymentValidationException, PaymentGatewayException
from core.payments.model.payment import Payment
from core.payments.model.bill import Bill
from core.payments.model.invoice import Invoice
from utilities.paymentgatewayclient import PaymentGatewayClient
from utilities.uniqueidgenerator import UniqueIdGenerator

logger = logging.getLogger(__name__)

class PaymentService:
    def __init__(self, db: Session):
        self.db = db
        self.payment_gateway_client = PaymentGatewayClient()
        self.service_id = self.payment_gateway_client.service_id
    
    def make_payment(self, payment_dto: PaymentDto, intent: str, request: Any = None) -> PaymentResultResponse:
        """
        Process payment through Orchard API.

        Args:
            payment_dto: Payment data object
            intent: The NLU intent (buy_airtime, send_money, pay_bill, etc.)
            request: Optional HTTP request object

        Returns:
            PaymentResultResponse with status and transaction details
        """
        logger.info(f"[PAYMENT_SERVICE] Processing payment for intent: {intent}, amount: {payment_dto.amountPaid}")
        print(f"[PAYMENT_SERVICE] Processing payment for intent: {intent}, amount: {payment_dto.amountPaid}")

        # Map PaymentDto (camelCase) to Payment model (snake_case)
        payment_data = {
            'bill_id': payment_dto.billId or 0,
            'response_id': payment_dto.responseId,
            'amount_paid': payment_dto.amountPaid or 0,
            'payment_method': payment_dto.paymentMethod,
            'status': payment_dto.status or PaymentStatus.PENDING,
            'transaction_id': payment_dto.transactionId,
            'service_name': payment_dto.serviceName,
            'intent': intent,
            'customer_email': payment_dto.customerEmail,
            'customer_name': payment_dto.customerName,
            'phone_number': payment_dto.phoneNumber,
            'bank_code': payment_dto.bankCode,
            'network': payment_dto.network,
        }

        # Create or retrieve payment record
        payment = Payment(**payment_data)

        # Validate payment data
        self._validate_payment(payment)

        # Generate transaction ID if needed
        if not payment.transaction_id:
            payment.transaction_id = str(UniqueIdGenerator.generate())

        try:
            # Save payment record to database (status: PENDING)
            payment.status = PaymentStatus.PENDING
            self.db.add(payment)
            self.db.commit()
            self.db.refresh(payment)
            print(f"[PAYMENT_SERVICE] Payment record created: {payment.id} with transaction_id: {payment.transaction_id}")
            logger.info(f"Payment record created: {payment.id} with transaction_id: {payment.transaction_id}")

            # Build request following Orchard spec
            payment_request = self._build_payment_request(payment, intent)
            print(f"[PAYMENT_SERVICE] Built payment request: {payment_request}")

            # Send to Orchard API
            print(f"[PAYMENT_SERVICE] Sending payment request to Orchard API...")
            http_response = self.payment_gateway_client.process_payment(payment_request)
            print(f"[PAYMENT_SERVICE] Received response from Orchard API: status_code={http_response.status_code}")

            # Process response and update payment status
            return self._process_gateway_response(http_response, payment)

        except PaymentGatewayException as e:
            logger.error(f"Payment gateway error for transactionId: {payment.transaction_id}", exc_info=True)
            return self._handle_system_error(payment, e)
        except Exception as e:
            logger.error(f"Unexpected error processing payment for intent {intent}", exc_info=True)
            return self._handle_system_error(payment, Exception(str(e)))
    
    def _process_gateway_response(self, http_response: Any, payment: Payment) -> PaymentResultResponse:
        try:
            if http_response.status_code == 200:
                response_data = http_response.json()

                if response_data and response_data.get("resp_code") == "015":
                    logger.info(f"Payment successful for transactionId: {payment.transaction_id}")
                    return self._handle_success(payment, response_data)
                else:
                    logger.warn(f"Payment failed with response code: {response_data.get('resp_code') if response_data else 'null'} for transactionId: {payment.transaction_id}")
                    return self._handle_gateway_failure(payment, response_data)
            else:
                logger.error(f"Payment gateway returned HTTP status: {http_response.status_code} for transactionId: {payment.transaction_id}")
                return self._handle_system_error(payment, PaymentGatewayException(f"HTTP Status: {http_response.status_code}"))
                
        except Exception as e:
            logger.error(f"Failed to parse payment gateway response for transactionId: {payment.transaction_id}", exc_info=True)
            return self._handle_system_error(payment, PaymentGatewayException(f"Response parsing error: {str(e)}"))
    
    def process_payment_callback(self, callback_response: Any) -> None:
        try:
            logger.info(f"Callback details - Trans_ref: {callback_response.trans_ref}, Trans_id: {callback_response.trans_id}, Status: {callback_response.trans_status}, Message: {callback_response.message}")

            # Validate callback data
            if not callback_response.trans_ref:
                raise ValueError("Transaction reference (trans_ref) is required")

            payment = self.db.query(Payment).filter(Payment.transaction_id == str(callback_response.trans_ref)).first()
            if not payment:
                logger.error(f"Payment not found for Transaction ID: {callback_response.trans_ref}")
                raise PaymentNotFoundException(f"Payment not found for Transaction ID: {callback_response.trans_ref}")

            incoming_status = self._determine_payment_status(callback_response.trans_status)
            logger.info(f"Payment ID: {payment.id} | Current Status: {payment.status} | Incoming Status: {incoming_status}")

            # Skip processing if no status change or already successful
            if self._should_skip_callback_processing(payment, incoming_status):
                return

            # Update payment status
            payment.status = incoming_status
            payment.updated_on = datetime.now()

            self.db.commit()
            logger.info(f"Payment status updated to {incoming_status} for payment ID: {payment.id}")

        except Exception as e:
            self.db.rollback()
            logger.error("Unexpected error during callback processing", exc_info=True)
            raise
    
    def _should_skip_callback_processing(self, payment: Payment, incoming_status: PaymentStatus) -> bool:
        # Skip if status unchanged
        if payment.status == incoming_status:
            logger.info("Skipping callback - status unchanged")
            return True
        
        # Skip if already successful
        if payment.status == PaymentStatus.SUCCESS:
            logger.info("Skipping callback - payment already successful")
            return True
        
        return False
    
    def _determine_payment_status(self, trans_status: str) -> PaymentStatus:
        if not trans_status:
            return PaymentStatus.FAILED
        
        # According to API docs, first 3 digits determine status
        status_code = trans_status[:3] if len(trans_status) >= 3 else trans_status
        
        if status_code == "000":
            return PaymentStatus.SUCCESS
        elif status_code == "001":
            return PaymentStatus.FAILED
        else:
            logger.warn(f"Unknown status code received: {trans_status}")
            return PaymentStatus.FAILED
    
    def get_payment_by_id(self, id: int) -> Payment:
        payment = self.db.query(Payment).filter(Payment.id == id).first()
        if not payment:
            raise PaymentNotFoundException(f"Payment not found with id {id}")
        return payment
    
    def get_all_payments(self, page: int, size: int, timeline: Timeline) -> Any:
        query = self.db.query(Payment)
        
        if timeline and timeline != Timeline.ALL:
            start_date = self._calculate_start_date(timeline)
            query = query.filter(Payment.date_paid >= start_date)
        
        return query.order_by(desc(Payment.date_paid)).offset(page * size).limit(size).all()
    
    def get_payments_by_method(self, payment_method: PaymentMethod) -> List[Payment]:
        return self.db.query(Payment).filter(Payment.payment_method == payment_method).all()
    
    def get_total_revenue(self) -> Decimal:
        total_revenue = self.db.query(func.sum(Payment.amount_paid)).scalar()
        return total_revenue or Decimal('0.00')
    
    def get_total_revenue_within_timeline(self, timeline: Timeline) -> Decimal:
        if timeline == Timeline.ALL:
            return self.get_total_revenue()
        
        start_date = self._calculate_start_date(timeline)
        total_revenue = self.db.query(func.sum(Payment.amount_paid))\
            .filter(Payment.date_paid >= start_date)\
            .scalar()
        
        return total_revenue or Decimal('0.00')
    
    def get_payments_by_service_name(self, service_name: str) -> List[Payment]:
        return self.db.query(Payment)\
            .filter(Payment.service_name.ilike(f"%{service_name}%"))\
            .all()
    
    def get_payments_by_customer_name(self, customer_name: str) -> List[Payment]:
        return self.db.query(Payment)\
            .filter(Payment.customer_name.ilike(f"%{customer_name}%"))\
            .all()
    
    # Helper Methods
    def _validate_payment(self, payment: Payment) -> None:
        if not payment.payment_method:
            raise PaymentValidationException("Payment method is required")
        
        if not payment.network:
            raise PaymentValidationException("Network is required")

        if payment.payment_method == PaymentMethod.MOBILE_MONEY:
            if not payment.phone_number:
                raise PaymentValidationException("Phone number is required for mobile money payments")
            # Valid networks for mobile money: MTN, VOD (Vodafone), AIR (AirtelTigo)
            if payment.network not in [Network.MTN, Network.VOD, Network.AIR]:
                raise PaymentValidationException(f"Invalid network for mobile money payment: {payment.network}")

        elif payment.payment_method == PaymentMethod.CREDIT_DEBIT_CARD:
            # Card payments: VIS (VISA), MAS (Mastercard)
            if payment.network not in [Network.VIS, Network.MAS]:
                raise PaymentValidationException(f"Invalid network for card payment: {payment.network}")

        elif payment.payment_method == PaymentMethod.BANK_TRANSFER:
            # Bank transfers need BNK network and bank code
            if payment.network != Network.BNK:
                raise PaymentValidationException(f"Network must be BNK for bank payments, got: {payment.network}")
            if not payment.bank_code:
                raise PaymentValidationException("Bank code is required for bank payments")
    
    def _build_payment_request(self, payment: Payment, intent: str) -> Dict[str, Any]:
        """
        Build Orchard API request following specification.
        trans_type is determined by intent.
        """
        # Map intent to transaction type
        transaction_type_map = {
            "buy_airtime": "ATP",           # Airtime Top-Up
            "send_money": "CTM",            # Customer to Merchant
            "pay_bill": "CTM",              # Bill payment (also CTM)
            "get_loan": "MTC",              # Merchant to Customer (Payout)
            "verify_account": "AII"         # Account Inquiry
        }

        trans_type = transaction_type_map.get(intent, "CTM")  # Default to CTM

        # Build base request (all transaction types need these)
        # Ensure amount_paid is a Decimal before formatting
        amount = payment.amount_paid if isinstance(payment.amount_paid, Decimal) else Decimal(str(payment.amount_paid))
        request_data = {
            "amount": str(amount.quantize(Decimal('0.00'))),
            "customer_number": payment.phone_number,
            "exttrid": payment.transaction_id,  # Keep as string, not int
            "nw": payment.network.value,
            "reference": f"{intent.replace('_', ' ').title()}",
            "service_id": self.service_id,
            "ts": self.payment_gateway_client.get_current_timestamp(),
            "callback_url": self.payment_gateway_client.build_callback_url(),
            "trans_type": trans_type
        }

        # Add optional fields only if they exist (as per Orchard spec)
        if payment.customer_name and intent in ["send_money", "get_loan"]:
            request_data["recipient_name"] = payment.customer_name

        if payment.bank_code and intent in ["pay_bill", "get_loan"]:
            request_data["bank_code"] = payment.bank_code

        logger.info(f"Built payment request for {intent}: trans_type={trans_type}")
        return request_data
    
    def _create_invoice(self, payment: Payment) -> None:
        invoice = Invoice(
            bill_id=payment.bill_id,
            invoice_number=UniqueIdGenerator.generate_invoice_id(payment.bill_id),
            customer_name=payment.customer_name,
            customer_email=payment.customer_email,
            service_name=payment.service_name,
            amount=payment.amount_paid
        )
        self.db.add(invoice)
        self.db.commit()
    
    def _calculate_start_date(self, timeline: Timeline) -> datetime:
        now = datetime.now()
        if timeline == Timeline.TODAY:
            return now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif timeline == Timeline.THIS_WEEK:
            return now - timedelta(days=now.weekday())
        elif timeline == Timeline.THIS_MONTH:
            return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        elif timeline == Timeline.THIS_YEAR:
            return now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            return datetime.min
    
    def _handle_success(self, payment: Payment, response: Dict[str, Any]) -> PaymentResultResponse:
        logger.info(f"Handling successful payment for transactionId: {payment.transaction_id}")
        payment.status = PaymentStatus.SUCCESS

        logger.debug(f"Creating invoice for transactionId: {payment.transaction_id}")
        self._create_invoice(payment)

        logger.info(f"Persisting payment for transactionId: {payment.transaction_id}")
        self.db.add(payment)
        self.db.commit()

        logger.info(f"Payment persisted successfully with paymentId: {payment.id} for transactionId: {payment.transaction_id}")

        return PaymentResultResponse(
            payment_id=payment.id,
            status=PaymentStatus.SUCCESS,
            responseCode=response.get("resp_code"),
            responseDescription=response.get("resp_desc"),
            transactionId=payment.transaction_id,
            paymentMethod=payment.payment_method
        )
    
    def _handle_gateway_failure(self, payment: Payment, response: Dict[str, Any]) -> PaymentResultResponse:
        logger.warn(f"Handling gateway failure for transactionId: {payment.transaction_id}. Response code: {response.get('resp_code')}, description: {response.get('resp_desc')}")

        payment.status = PaymentStatus.FAILED
        self.db.add(payment)
        self.db.commit()

        logger.info(f"Payment persisted failed with paymentId: {payment.id} for transactionId: {payment.transaction_id}")
        logger.info(f"Returning FAILED status for transactionId: {payment.transaction_id}")

        return PaymentResultResponse(
            payment_id=payment.id,
            status=PaymentStatus.FAILED,
            responseCode=response.get("resp_code"),
            responseDescription=response.get("resp_desc"),
            transactionId=payment.transaction_id,
            paymentMethod=payment.payment_method
        )
    
    def _handle_system_error(self, payment: Payment, exception: Exception) -> PaymentResultResponse:
        logger.error(f"System error processing payment for transactionId: {payment.transaction_id}. Error: {str(exception)}")
        # Transaction will auto-rollback
        
        logger.info(f"Returning SYSTEM_ERROR for transactionId: {payment.transaction_id}")
        
        return PaymentResultResponse(
            payment_id=None,  # No persisted ID
            status=PaymentStatus.FAILED,
            response_code="SYSTEM_ERROR",
            response_description="Technical error processing payment",
            transaction_id=payment.transaction_id,
            payment_method=payment.payment_method
        )