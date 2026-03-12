from decimal import Decimal
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from enum import Enum
import logging
import os
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
from utilities.provider_mapper import ProviderMapper

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
        # Map network to provider names
        sender_provider = ProviderMapper.get_provider(payment_dto.network) if payment_dto.network else "Unknown"

        # For receiver, we need to detect their network from their phone number
        receiver_network = None
        if payment_dto.receiverPhone:
            from core.beneficiaries.utility.network_detector import NetworkDetector
            detected_network, _ = NetworkDetector.detect_network_from_phone(payment_dto.receiverPhone)
            # Map the detected network string to Network enum
            if detected_network:
                network_map = {
                    "MTN": Network.MTN,
                    "VOD": Network.VOD,
                    "AIR": Network.AIR,
                }
                receiver_network = network_map.get(detected_network)
        receiver_provider = ProviderMapper.get_provider(receiver_network) if receiver_network else "Unknown"

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
            'sender_phone': payment_dto.senderPhone or payment_dto.phoneNumber,
            'receiver_phone': payment_dto.receiverPhone,
            'bank_code': payment_dto.bankCode,
            'network': payment_dto.network,
            'sender_name': payment_dto.senderName or payment_dto.customerName,
            'receiver_name': payment_dto.receiverName,
            'sender_provider': payment_dto.senderProvider or sender_provider,
            'receiver_provider': payment_dto.receiverProvider or receiver_provider,
            'ext_biller_ref_id': payment_dto.extBillerRefId,  # Biller ID for ABS bill payments
            'reference': payment_dto.reference,
            'beneficiary_id': payment_dto.beneficiaryId,
            'beneficiary_name': payment_dto.beneficiaryName,
        }

        # Create or retrieve payment record
        payment = Payment(**payment_data)

        # Validate payment data
        self._validate_payment(payment)

        # Check wallet balance BEFORE initiating transaction
        # This prevents creating CTM if we can't fund MTC/ATP or reversals
        self._check_wallet_balance(payment, intent)

        # Generate transaction ID if needed
        if not payment.transaction_id:
            payment.transaction_id = str(UniqueIdGenerator.generate())

        # Set ctm_transaction_id to match transaction_id for CTM leg tracking
        payment.ctm_transaction_id = payment.transaction_id

        try:
            # Save payment record to database (status: PENDING)
            # Only saved after balance check passes
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
                    # 015 = "Request successfully received for processing"
                    # This is NOT final success - we must wait for the callback to confirm
                    logger.info(f"Payment request accepted for processing (resp_code: 015) for transactionId: {payment.transaction_id}")
                    return self._handle_pending_payment(payment, response_data)
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
        """
        Process payment callback from Orchard API.
        Handles both CTM (Customer to Merchant) and MTC (Merchant to Customer) callbacks.
        Two-stage transaction: CTM first, then MTC after CTM succeeds.
        """
        try:
            logger.info(f"[CALLBACK_START] Received callback - Trans_ref: {callback_response.trans_ref}, Trans_id: {callback_response.trans_id}, Status: {callback_response.trans_status}, Message: {callback_response.message}")

            # Validate callback data
            logger.debug(f"[CALLBACK_VALIDATION] Checking if trans_ref is present: {callback_response.trans_ref is not None}")
            if not callback_response.trans_ref:
                logger.error("[CALLBACK_VALIDATION_FAILED] Missing trans_ref in callback")
                raise ValueError("Transaction reference (trans_ref) is required")
            logger.info(f"[CALLBACK_VALIDATION_SUCCESS] trans_ref validation passed: {callback_response.trans_ref}")

            trans_ref_str = str(callback_response.trans_ref)
            logger.debug(f"[CALLBACK_CONVERSION] Converted trans_ref to string: '{trans_ref_str}'")

            # Find payment by looking up both ctm_transaction_id and transaction_id
            logger.debug(f"[DB_QUERY_START] Searching for payment with trans_ref_str: '{trans_ref_str}'")
            logger.debug(f"[DB_QUERY_FILTERS] Looking for payment where: transaction_id='{trans_ref_str}' OR ctm_transaction_id='{trans_ref_str}' OR mtc_transaction_id='{trans_ref_str}' OR atp_transaction_id='{trans_ref_str}' OR blp_transaction_id='{trans_ref_str}'")
            payment = self.db.query(Payment).filter(
                (Payment.transaction_id == trans_ref_str) |
                (Payment.ctm_transaction_id == trans_ref_str) |
                (Payment.mtc_transaction_id == trans_ref_str) |
                (Payment.atp_transaction_id == trans_ref_str) |
                (Payment.blp_transaction_id == trans_ref_str)
            ).first()
            logger.debug(f"[DB_QUERY_END] Query completed, payment found: {payment is not None}")

            if not payment:
                logger.error(f"[PAYMENT_NOT_FOUND] Payment not found for Transaction ID: {callback_response.trans_ref}")
                raise PaymentNotFoundException(f"Payment not found for Transaction ID: {callback_response.trans_ref}")

            logger.info(f"[PAYMENT_FOUND] Payment found - ID: {payment.id}, transaction_id: {payment.transaction_id}, ctm_transaction_id: {payment.ctm_transaction_id}, mtc_transaction_id: {payment.mtc_transaction_id}, atp_transaction_id: {payment.atp_transaction_id}, blp_transaction_id: {payment.blp_transaction_id}")

            # Determine which leg of the transaction this callback is for
            logger.debug(f"[CALLBACK_TYPE_CHECK_START] Determining callback type")
            logger.debug(f"[CALLBACK_TYPE_CHECK] trans_ref_str='{trans_ref_str}' vs payment.transaction_id='{payment.transaction_id}'")
            logger.debug(f"[CALLBACK_TYPE_CHECK] trans_ref_str='{trans_ref_str}' vs payment.ctm_transaction_id='{payment.ctm_transaction_id}'")
            logger.debug(f"[CALLBACK_TYPE_CHECK] trans_ref_str='{trans_ref_str}' vs payment.mtc_transaction_id='{payment.mtc_transaction_id}'")
            logger.debug(f"[CALLBACK_TYPE_CHECK] trans_ref_str='{trans_ref_str}' vs payment.atp_transaction_id='{payment.atp_transaction_id}'")
            logger.debug(f"[CALLBACK_TYPE_CHECK] trans_ref_str='{trans_ref_str}' vs payment.blp_transaction_id='{payment.blp_transaction_id}'")

            is_ctm_callback = (trans_ref_str == payment.transaction_id or trans_ref_str == payment.ctm_transaction_id)
            is_mtc_callback = (trans_ref_str == payment.mtc_transaction_id)
            is_atp_callback = (trans_ref_str == payment.atp_transaction_id)
            is_blp_callback = (trans_ref_str == payment.blp_transaction_id)

            logger.info(f"[CALLBACK_TYPE_DETERMINED] is_ctm_callback={is_ctm_callback}, is_mtc_callback={is_mtc_callback}, is_atp_callback={is_atp_callback}, is_blp_callback={is_blp_callback}")

            incoming_status = self._determine_payment_status(callback_response.trans_status)
            logger.info(f"[CALLBACK_STATUS_ANALYSIS] Payment ID: {payment.id} | Current Status: {payment.status} | Incoming Status: {incoming_status} | Callback Status Code: {callback_response.trans_status}")

            if is_ctm_callback:
                logger.info(f"[CALLBACK_HANDLER_START] Handling CTM callback for payment ID: {payment.id}")
                # Handle CTM (Customer to Merchant) callback
                self._handle_ctm_callback(payment, callback_response, incoming_status)
                logger.info(f"[CALLBACK_HANDLER_END] CTM callback handling completed for payment ID: {payment.id}")
            elif is_atp_callback:
                logger.info(f"[CALLBACK_HANDLER_START] Handling ATP callback for payment ID: {payment.id}")
                # Handle ATP (Airtime Top-Up) callback
                self._handle_atp_callback(payment, callback_response, incoming_status)
                logger.info(f"[CALLBACK_HANDLER_END] ATP callback handling completed for payment ID: {payment.id}")
            elif is_blp_callback:
                logger.info(f"[CALLBACK_HANDLER_START] Handling BLP callback for payment ID: {payment.id}")
                # Handle BLP (Bill Payment) callback
                self._handle_blp_callback(payment, callback_response, incoming_status)
                logger.info(f"[CALLBACK_HANDLER_END] BLP callback handling completed for payment ID: {payment.id}")
            elif is_mtc_callback:
                logger.info(f"[CALLBACK_HANDLER_START] Handling MTC callback for payment ID: {payment.id}")
                # Handle MTC (Merchant to Customer) callback
                self._handle_mtc_callback(payment, callback_response, incoming_status)
                logger.info(f"[CALLBACK_HANDLER_END] MTC callback handling completed for payment ID: {payment.id}")
            else:
                logger.error(f"[CALLBACK_TYPE_ERROR] Unable to determine callback type for transaction {callback_response.trans_ref}. is_ctm_callback={is_ctm_callback}, is_mtc_callback={is_mtc_callback}, is_atp_callback={is_atp_callback}, is_blp_callback={is_blp_callback}")
                raise ValueError("Unable to determine if callback is for CTM, MTC, ATP, or BLP")

            logger.info(f"[CALLBACK_COMPLETE] Callback processing completed successfully for trans_ref: {callback_response.trans_ref}")

        except Exception as e:
            logger.error(f"[CALLBACK_ERROR] Exception occurred during callback processing: {str(e)}", exc_info=True)
            self.db.rollback()
            logger.error("[CALLBACK_ROLLBACK] Database transaction rolled back")
            raise
    
    def _handle_ctm_callback(self, payment: Payment, callback_response: Any, incoming_status: PaymentStatus) -> None:
        """
        Handle CTM (Customer to Merchant) callback.
        If successful, sets status to CTM_SUCCESS and initiates MTC.
        If failed, sets status to CTM_FAILED.
        """
        logger.info(f"[CTM_CALLBACK_HANDLER_START] Processing CTM callback for payment ID: {payment.id}, transaction_id: {payment.transaction_id}")
        logger.debug(f"[CTM_CALLBACK_HANDLER_STATUS] Current payment status: {payment.status}, Incoming status: {incoming_status}")

        if incoming_status == PaymentStatus.SUCCESS:
            logger.info(f"[CTM_CALLBACK_SUCCESS] CTM callback confirmed success for transaction {payment.transaction_id}")
            logger.debug(f"[CTM_CALLBACK_SUCCESS_DETAIL] Updating payment status to CTM_SUCCESS")
            payment.status = PaymentStatus.CTM_SUCCESS
            payment.updated_on = datetime.now()
            self.db.add(payment)
            self.db.commit()
            logger.info(f"[CTM_STATUS_UPDATED] Payment status updated to CTM_SUCCESS for payment ID: {payment.id}")

            # Determine second stage based on intent
            if payment.intent == "buy_airtime":
                # Check if ATP was already initiated by background job
                if payment.atp_transaction_id is not None:
                    logger.info(f"[CTM_CALLBACK_ATP_ALREADY_INITIATED] ATP already initiated with transaction ID {payment.atp_transaction_id}, skipping duplicate ATP initiation for payment {payment.id}")
                    logger.info(f"[CTM_CALLBACK_HANDLER_END] CTM callback handler completed (ATP already initiated) for payment ID: {payment.id}")
                else:
                    # Initiate ATP (Airtime Top-Up) to send airtime to receiver
                    logger.info(f"[CTM_CALLBACK_INITIATING_ATP] Initiating ATP for transaction {payment.transaction_id}")
                    self._initiate_atp(payment)
                    logger.info(f"[CTM_CALLBACK_HANDLER_END] CTM callback handler completed (ATP initiated) for payment ID: {payment.id}")
            elif payment.intent == "pay_bill":
                # Check if BLP was already initiated by background job
                if payment.blp_transaction_id is not None:
                    logger.info(f"[CTM_CALLBACK_BLP_ALREADY_INITIATED] BLP already initiated with transaction ID {payment.blp_transaction_id}, skipping duplicate BLP initiation for payment {payment.id}")
                    logger.info(f"[CTM_CALLBACK_HANDLER_END] CTM callback handler completed (BLP already initiated) for payment ID: {payment.id}")
                else:
                    # Initiate BLP (Bill Payment) to pay bill from merchant account
                    logger.info(f"[CTM_CALLBACK_INITIATING_BLP] Initiating BLP for transaction {payment.transaction_id}")
                    self._initiate_blp(payment)
                    logger.info(f"[CTM_CALLBACK_HANDLER_END] CTM callback handler completed (BLP initiated) for payment ID: {payment.id}")
            else:
                # Default to MTC for send_money and other intents
                # Check if MTC was already initiated by background job to prevent duplicate MTC initiation
                if payment.mtc_transaction_id is not None:
                    logger.info(f"[CTM_CALLBACK_MTC_ALREADY_INITIATED] MTC already initiated with transaction ID {payment.mtc_transaction_id}, skipping duplicate MTC initiation for payment {payment.id}")
                    logger.info(f"[CTM_CALLBACK_HANDLER_END] CTM callback handler completed (MTC already initiated) for payment ID: {payment.id}")
                else:
                    # Now initiate MTC (Merchant to Customer) to send money to receiver
                    logger.info(f"[CTM_CALLBACK_INITIATING_MTC] Initiating MTC for transaction {payment.transaction_id}")
                    self._initiate_mtc(payment)
                    logger.info(f"[CTM_CALLBACK_HANDLER_END] CTM callback handler completed (MTC initiated) for payment ID: {payment.id}")
        else:
            # CTM failed
            logger.warning(f"[CTM_CALLBACK_FAILURE] CTM callback confirmed failure for transaction {payment.transaction_id}")
            logger.debug(f"[CTM_CALLBACK_FAILURE_DETAIL] Incoming status was: {incoming_status}")
            payment.status = PaymentStatus.CTM_FAILED
            payment.updated_on = datetime.now()
            self.db.add(payment)
            self.db.commit()
            logger.info(f"[CTM_CALLBACK_HANDLER_END] Payment marked as CTM_FAILED for payment ID: {payment.id}")

    def _handle_mtc_callback(self, payment: Payment, callback_response: Any, incoming_status: PaymentStatus) -> None:
        """
        Handle MTC (Merchant to Customer) callback.
        If successful, sets status to SUCCESS and creates invoice.
        If failed, sets status to MTC_FAILED.
        """
        logger.info(f"[MTC_CALLBACK_HANDLER_START] Processing MTC callback for payment ID: {payment.id}, mtc_transaction_id: {payment.mtc_transaction_id}")
        logger.debug(f"[MTC_CALLBACK_HANDLER_STATUS] Current payment status: {payment.status}, Incoming status: {incoming_status}")

        if incoming_status == PaymentStatus.SUCCESS:
            logger.info(f"[MTC_CALLBACK_SUCCESS] MTC callback confirmed success for transaction {payment.transaction_id}")
            logger.info(f"[MTC_CALLBACK_SUCCESS_DETAIL] Both CTM and MTC legs completed, marking payment as SUCCESS")
            # MTC succeeded - both legs are complete, mark as SUCCESS
            self._handle_success(payment, {"resp_code": "000", "resp_desc": "Payment successful"})
            logger.info(f"[MTC_CALLBACK_HANDLER_END] MTC callback handler completed successfully for payment ID: {payment.id}")
        else:
            # MTC failed
            logger.warning(f"[MTC_CALLBACK_FAILURE] MTC callback confirmed failure for transaction {payment.transaction_id}")
            logger.debug(f"[MTC_CALLBACK_FAILURE_DETAIL] Incoming status was: {incoming_status}")
            payment.status = PaymentStatus.MTC_FAILED
            payment.updated_on = datetime.now()
            self.db.add(payment)
            self.db.commit()
            logger.info(f"[MTC_CALLBACK_HANDLER_END] Payment marked as MTC_FAILED for payment ID: {payment.id}")

    def _handle_atp_callback(self, payment: Payment, callback_response: Any, incoming_status: PaymentStatus) -> None:
        """
        Handle ATP (Airtime Top-Up) callback.
        If successful, sets status to SUCCESS and creates invoice.
        If failed, sets status to ATP_FAILED.
        """
        logger.info(f"[ATP_CALLBACK_HANDLER_START] Processing ATP callback for payment ID: {payment.id}, atp_transaction_id: {payment.atp_transaction_id}")
        logger.debug(f"[ATP_CALLBACK_HANDLER_STATUS] Current payment status: {payment.status}, Incoming status: {incoming_status}")

        if incoming_status == PaymentStatus.SUCCESS:
            logger.info(f"[ATP_CALLBACK_SUCCESS] ATP callback confirmed success for transaction {payment.transaction_id}")
            logger.info(f"[ATP_CALLBACK_SUCCESS_DETAIL] Both CTM and ATP legs completed, marking payment as SUCCESS")
            # ATP succeeded - both legs are complete, mark as SUCCESS
            self._handle_success(payment, {"resp_code": "000", "resp_desc": "Airtime sent successfully"})
            logger.info(f"[ATP_CALLBACK_HANDLER_END] ATP callback handler completed successfully for payment ID: {payment.id}")
        else:
            # ATP failed
            logger.warning(f"[ATP_CALLBACK_FAILURE] ATP callback confirmed failure for transaction {payment.transaction_id}")
            logger.debug(f"[ATP_CALLBACK_FAILURE_DETAIL] Incoming status was: {incoming_status}")
            payment.status = PaymentStatus.ATP_FAILED
            payment.updated_on = datetime.now()
            self.db.add(payment)
            self.db.commit()
            logger.info(f"[ATP_CALLBACK_HANDLER_END] Payment marked as ATP_FAILED for payment ID: {payment.id}")

    def _handle_blp_callback(self, payment: Payment, callback_response: Any, incoming_status: PaymentStatus) -> None:
        """
        Handle BLP (Bill Payment) callback.
        If successful, sets status to SUCCESS and creates invoice.
        If failed, sets status to BLP_FAILED.
        """
        logger.info(f"[BLP_CALLBACK_HANDLER_START] Processing BLP callback for payment ID: {payment.id}, blp_transaction_id: {payment.blp_transaction_id}")
        logger.debug(f"[BLP_CALLBACK_HANDLER_STATUS] Current payment status: {payment.status}, Incoming status: {incoming_status}")

        if incoming_status == PaymentStatus.SUCCESS:
            logger.info(f"[BLP_CALLBACK_SUCCESS] BLP callback confirmed success for transaction {payment.transaction_id}")
            logger.info(f"[BLP_CALLBACK_SUCCESS_DETAIL] Both CTM and BLP legs completed, marking payment as SUCCESS")
            # BLP succeeded - both legs are complete, mark as SUCCESS
            self._handle_success(payment, {"resp_code": "000", "resp_desc": "Bill payment processed successfully"})
            logger.info(f"[BLP_CALLBACK_HANDLER_END] BLP callback handler completed successfully for payment ID: {payment.id}")
        else:
            # BLP failed
            logger.warning(f"[BLP_CALLBACK_FAILURE] BLP callback confirmed failure for transaction {payment.transaction_id}")
            logger.debug(f"[BLP_CALLBACK_FAILURE_DETAIL] Incoming status was: {incoming_status}")
            payment.status = PaymentStatus.BLP_FAILED
            payment.updated_on = datetime.now()
            self.db.add(payment)
            self.db.commit()
            logger.info(f"[BLP_CALLBACK_HANDLER_END] Payment marked as BLP_FAILED for payment ID: {payment.id}")

    def _initiate_mtc(self, payment: Payment) -> None:
        """
        Initiate MTC (Merchant to Customer) transaction after CTM succeeds.
        Send the same amount from merchant account to receiver.
        """
        try:
            # Generate unique transaction ID for MTC
            mtc_transaction_id = str(UniqueIdGenerator.generate())
            payment.mtc_transaction_id = mtc_transaction_id
            payment.status = PaymentStatus.MTC_PROCESSING
            payment.updated_on = datetime.now()
            self.db.add(payment)
            self.db.commit()

            # Build MTC payment request
            # MTC is Merchant to Customer (payout), so trans_type = "MTC"
            mtc_request = self._build_mtc_payment_request(payment, mtc_transaction_id)
            logger.info(f"Built MTC payment request for transaction: {mtc_transaction_id}")

            # Send to Orchard API
            logger.info(f"Sending MTC request to Orchard API for transaction: {mtc_transaction_id}")
            http_response = self.payment_gateway_client.process_payment(mtc_request)
            logger.info(f"Received MTC response from Orchard API: status_code={http_response.status_code}")

            # Process MTC response - should get 015 or 027 meaning request accepted
            if http_response.status_code == 200:
                response_data = http_response.json()
                resp_code = response_data.get("resp_code") if response_data else None
                # Both 015 (request received for processing) and 027 (request successfully completed) are valid
                if response_data and resp_code in ["015", "027"]:
                    logger.info(f"[MTC_RESPONSE_SUCCESS] MTC request accepted for processing (resp_code: {resp_code}) for transactionId: {mtc_transaction_id}")
                    # MTC is now processing, waiting for callback or status check
                    logger.info(f"[MTC_PROCESSING] Awaiting MTC callback for transaction {mtc_transaction_id}")
                    # Note: The existing check job will continue running and will check MTC status
                    # since payment status is now MTC_PROCESSING (see payment_check_service.py line 151-157)
                else:
                    logger.warning(f"MTC failed with response code: {response_data.get('resp_code')}")
                    payment.status = PaymentStatus.MTC_FAILED
                    self.db.add(payment)
                    self.db.commit()
                    # Initiate reversal for failed MTC
                    self._initiate_reversal(payment)
                    # Send failure notification
                    try:
                        self.send_payment_notification(
                            payment,
                            is_success=False,
                            failure_reason="Payout request rejected. Reversal being processed."
                        )
                    except Exception as e:
                        logger.error(f"Failed to send failure notification: {str(e)}", exc_info=True)
            else:
                logger.error(f"MTC gateway returned HTTP status: {http_response.status_code}")
                payment.status = PaymentStatus.MTC_FAILED
                self.db.add(payment)
                self.db.commit()
                # Initiate reversal for failed MTC
                self._initiate_reversal(payment)
                # Send failure notification
                try:
                    self.send_payment_notification(
                        payment,
                        is_success=False,
                        failure_reason="Payout request failed. Reversal being processed."
                    )
                except Exception as e:
                    logger.error(f"Failed to send failure notification: {str(e)}", exc_info=True)

        except Exception as e:
            logger.error(f"Error initiating MTC for transaction {payment.transaction_id}: {str(e)}", exc_info=True)
            payment.status = PaymentStatus.MTC_FAILED
            self.db.add(payment)
            self.db.commit()
            # Initiate reversal for failed MTC
            try:
                self._initiate_reversal(payment)
                # Send failure notification
                self.send_payment_notification(
                    payment,
                    is_success=False,
                    failure_reason="Payout request error. Reversal being processed."
                )
            except Exception as reversal_error:
                logger.error(f"Error initiating reversal after MTC exception: {str(reversal_error)}", exc_info=True)
            raise

    def _build_mtc_payment_request(self, payment: Payment, mtc_transaction_id: str) -> Dict[str, Any]:
        """
        Build MTC (Merchant to Customer) payment request.
        MTC sends money from merchant account to customer/receiver.
        Detects the correct network based on receiver's phone number.
        """
        from utilities.phone_utils import convert_to_local_ghana_format
        from core.beneficiaries.utility.network_detector import NetworkDetector

        amount = payment.amount_paid if isinstance(payment.amount_paid, Decimal) else Decimal(str(payment.amount_paid))

        # Detect network from receiver's phone number
        detected_network, network_message = NetworkDetector.detect_network_from_phone(payment.receiver_phone)
        network_to_use = detected_network if detected_network else payment.network.value

        logger.info(f"[MTC_NETWORK_DETECTION] Receiver phone: {payment.receiver_phone} -> Detected network: {detected_network} ({network_message})")

        request_data = {
            "amount": str(amount.quantize(Decimal('0.00'))),
            "customer_number": convert_to_local_ghana_format(payment.receiver_phone),  # MTC: receiver (in 0xxx format)
            "exttrid": mtc_transaction_id,
            "nw": network_to_use,  # Use detected network instead of stored network
            "reference": os.getenv("PAYMENT_REFERENCE", "Lemo Financial"),
            "service_id": self.service_id,
            "ts": self.payment_gateway_client.get_current_timestamp(),
            "callback_url": self.payment_gateway_client.build_callback_url(),
            "trans_type": "MTC"  # Merchant to Customer
        }
        logger.info(f"Built MTC payment request: trans_type=MTC, network={network_to_use}")
        return request_data

    def _initiate_atp(self, payment: Payment) -> None:
        """
        Initiate ATP (Airtime Top-Up) transaction after CTM succeeds.
        Send airtime from merchant account to receiver's phone number.
        """
        try:
            # Generate unique transaction ID for ATP
            atp_transaction_id = str(UniqueIdGenerator.generate())
            payment.atp_transaction_id = atp_transaction_id
            payment.status = PaymentStatus.ATP_PROCESSING
            payment.updated_on = datetime.now()
            self.db.add(payment)
            self.db.commit()

            # Build ATP payment request
            atp_request = self._build_atp_payment_request(payment, atp_transaction_id)
            logger.info(f"Built ATP payment request for transaction: {atp_transaction_id}")

            # Send to Orchard API
            logger.info(f"Sending ATP request to Orchard API for transaction: {atp_transaction_id}")
            http_response = self.payment_gateway_client.process_payment(atp_request)
            logger.info(f"Received ATP response from Orchard API: status_code={http_response.status_code}")

            # Process ATP response - should get 015 or 027 meaning request accepted
            if http_response.status_code == 200:
                response_data = http_response.json()
                resp_code = response_data.get("resp_code") if response_data else None
                # Both 015 (request received for processing) and 027 (request successfully completed) are valid
                if response_data and resp_code in ["015", "027"]:
                    logger.info(f"[ATP_RESPONSE_SUCCESS] ATP request accepted for processing (resp_code: {resp_code}) for transactionId: {atp_transaction_id}")
                    # ATP is now processing, waiting for callback or status check
                    logger.info(f"[ATP_PROCESSING] Awaiting ATP callback for transaction {atp_transaction_id}")
                    # Note: The existing check job will continue running and will check ATP status
                else:
                    logger.warning(f"ATP failed with response code: {response_data.get('resp_code')}")
                    payment.status = PaymentStatus.ATP_FAILED
                    self.db.add(payment)
                    self.db.commit()
                    # Initiate reversal for failed ATP
                    self._initiate_reversal(payment)
                    # Send failure notification
                    try:
                        self.send_payment_notification(
                            payment,
                            is_success=False,
                            failure_reason="Airtime request rejected. Reversal being processed."
                        )
                    except Exception as e:
                        logger.error(f"Failed to send failure notification: {str(e)}", exc_info=True)
            else:
                logger.error(f"ATP gateway returned HTTP status: {http_response.status_code}")
                payment.status = PaymentStatus.ATP_FAILED
                self.db.add(payment)
                self.db.commit()
                # Initiate reversal for failed ATP
                self._initiate_reversal(payment)
                # Send failure notification
                try:
                    self.send_payment_notification(
                        payment,
                        is_success=False,
                        failure_reason="Airtime request failed. Reversal being processed."
                    )
                except Exception as e:
                    logger.error(f"Failed to send failure notification: {str(e)}", exc_info=True)

        except Exception as e:
            logger.error(f"Error initiating ATP for transaction {payment.transaction_id}: {str(e)}", exc_info=True)
            payment.status = PaymentStatus.ATP_FAILED
            self.db.add(payment)
            self.db.commit()
            # Initiate reversal for failed ATP
            try:
                self._initiate_reversal(payment)
                # Send failure notification
                self.send_payment_notification(
                    payment,
                    is_success=False,
                    failure_reason="Airtime request error. Reversal being processed."
                )
            except Exception as reversal_error:
                logger.error(f"Error initiating reversal after ATP exception: {str(reversal_error)}", exc_info=True)
            raise

    def _initiate_blp(self, payment: Payment) -> None:
        """
        Initiate BLP (Bill Payment) transaction after CTM succeeds.
        Send bill payment from merchant account using customer's account number.
        """
        try:
            # Generate unique transaction ID for BLP
            blp_transaction_id = str(UniqueIdGenerator.generate())
            payment.blp_transaction_id = blp_transaction_id
            payment.status = PaymentStatus.BLP_PROCESSING
            payment.updated_on = datetime.now()
            self.db.add(payment)
            self.db.commit()

            # Build BLP payment request
            blp_request = self._build_blp_payment_request(payment, blp_transaction_id)
            logger.info(f"Built BLP payment request for transaction: {blp_transaction_id}")

            # Send to Orchard API
            logger.info(f"Sending BLP request to Orchard API for transaction: {blp_transaction_id}")
            http_response = self.payment_gateway_client.process_payment(blp_request)
            logger.info(f"Received BLP response from Orchard API: status_code={http_response.status_code}")

            # Process BLP response - should get 015 or 027 meaning request accepted
            if http_response.status_code == 200:
                response_data = http_response.json()
                resp_code = response_data.get("resp_code") if response_data else None
                # Both 015 (request received for processing) and 027 (request successfully completed) are valid
                if response_data and resp_code in ["015", "027"]:
                    logger.info(f"[BLP_RESPONSE_SUCCESS] BLP request accepted for processing (resp_code: {resp_code}) for transactionId: {blp_transaction_id}")
                    # BLP is now processing, waiting for callback or status check
                    logger.info(f"[BLP_PROCESSING] Awaiting BLP callback for transaction {blp_transaction_id}")
                    # Note: The existing check job will continue running and will check BLP status
                else:
                    logger.warning(f"BLP failed with response code: {response_data.get('resp_code')}")
                    payment.status = PaymentStatus.BLP_FAILED
                    self.db.add(payment)
                    self.db.commit()
                    # Initiate reversal for failed BLP
                    self._initiate_reversal(payment)
                    # Send failure notification
                    try:
                        self.send_payment_notification(
                            payment,
                            is_success=False,
                            failure_reason="Bill payment request rejected. Reversal being processed."
                        )
                    except Exception as e:
                        logger.error(f"Failed to send failure notification: {str(e)}", exc_info=True)
            else:
                logger.error(f"BLP gateway returned HTTP status: {http_response.status_code}")
                payment.status = PaymentStatus.BLP_FAILED
                self.db.add(payment)
                self.db.commit()
                # Initiate reversal for failed BLP
                self._initiate_reversal(payment)
                # Send failure notification
                try:
                    self.send_payment_notification(
                        payment,
                        is_success=False,
                        failure_reason="Bill payment request failed. Reversal being processed."
                    )
                except Exception as e:
                    logger.error(f"Failed to send failure notification: {str(e)}", exc_info=True)

        except Exception as e:
            logger.error(f"Error initiating BLP for transaction {payment.transaction_id}: {str(e)}", exc_info=True)
            payment.status = PaymentStatus.BLP_FAILED
            self.db.add(payment)
            self.db.commit()
            # Initiate reversal for failed BLP
            try:
                self._initiate_reversal(payment)
                # Send failure notification
                self.send_payment_notification(
                    payment,
                    is_success=False,
                    failure_reason="Bill payment request error. Reversal being processed."
                )
            except Exception as reversal_error:
                logger.error(f"Error initiating reversal after BLP exception: {str(reversal_error)}", exc_info=True)
            raise

    def _build_atp_payment_request(self, payment: Payment, atp_transaction_id: str) -> Dict[str, Any]:
        """
        Build ATP (Airtime Top-Up) payment request.
        ATP sends airtime from merchant account to customer/receiver.
        Detects the correct network based on receiver's phone number.
        """
        from utilities.phone_utils import convert_to_local_ghana_format
        from core.beneficiaries.utility.network_detector import NetworkDetector

        amount = payment.amount_paid if isinstance(payment.amount_paid, Decimal) else Decimal(str(payment.amount_paid))

        # Detect network from receiver's phone number
        detected_network, network_message = NetworkDetector.detect_network_from_phone(payment.receiver_phone)
        network_to_use = detected_network if detected_network else payment.network.value

        logger.info(f"[ATP_NETWORK_DETECTION] Receiver phone: {payment.receiver_phone} -> Detected network: {detected_network} ({network_message})")

        request_data = {
            "amount": str(amount.quantize(Decimal('0.00'))),
            "customer_number": convert_to_local_ghana_format(payment.receiver_phone),  # ATP: receiver (in 0xxx format)
            "exttrid": atp_transaction_id,
            "nw": network_to_use,  # Use detected network instead of stored network
            "reference": os.getenv("PAYMENT_REFERENCE", "Lemo Financial"),
            "service_id": self.service_id,
            "ts": self.payment_gateway_client.get_current_timestamp(),
            "callback_url": self.payment_gateway_client.build_callback_url(),
            "trans_type": "ATP"  # Airtime Top-Up
        }
        logger.info(f"Built ATP payment request: trans_type=ATP, network={network_to_use}")
        return request_data

    def _build_blp_payment_request(self, payment: Payment, blp_transaction_id: str) -> Dict[str, Any]:
        """
        Build BLP (Bill Payment) payment request.
        BLP sends bill payment from merchant account to customer's utility bill.
        Uses account_number (smart card number) and utility network codes.
        For ABS (non-telco) bills, includes ext_biller_ref_id.
        """
        amount = payment.amount_paid if isinstance(payment.amount_paid, Decimal) else Decimal(str(payment.amount_paid))

        # For BLP, the network field contains the telco biller code (GOT, DST, MPP, VPP, STT, VBB)
        # This is stored in payment.network during the initial payment creation
        utility_network = payment.network.value if payment.network else "GOT"

        logger.info(f"[BLP_REQUEST] Building BLP request for account: {payment.receiver_phone} (stored as account_number), utility: {utility_network}")

        request_data = {
            "amount": str(amount.quantize(Decimal('0.00'))),
            "account_number": payment.receiver_phone,  # BLP uses account_number (smart card number)
            "exttrid": blp_transaction_id,
            "nw": utility_network,  # Telco biller network codes: GOT, DST, MPP, VPP, STT, VBB
            "reference": os.getenv("PAYMENT_REFERENCE", "Lemo Financial"),
            "service_id": self.service_id,
            "ts": self.payment_gateway_client.get_current_timestamp(),
            "callback_url": self.payment_gateway_client.build_callback_url(),
            "trans_type": "BLP"  # Bill Payment
        }

        # For ABS (non-telco) bill payments, add ext_biller_ref_id to the request
        if payment.ext_biller_ref_id:
            request_data["ext_biller_ref_id"] = payment.ext_biller_ref_id
            logger.info(f"[BLP_REQUEST_ABS] Added ext_biller_ref_id to BLP request for ABS bill payment: {payment.ext_biller_ref_id}")

        logger.info(f"Built BLP payment request: trans_type=BLP, network={utility_network}, has_biller_id={bool(payment.ext_biller_ref_id)}")
        return request_data

    def _initiate_reversal(self, payment: Payment) -> None:
        """
        Initiate reversal transaction when MTC fails.
        Creates a NEW Payment record to represent the refund (MTC to sender).
        Sends money back from merchant account to sender's account.
        """
        try:
            # Safety checks to avoid duplicate reversals
            # 1) Don't attempt to reverse a payment that is itself a reversal
            if payment.original_payment_id is not None:
                logger.info(
                    f"[REVERSAL_SKIP] Payment {payment.id} is itself a reversal "
                    f"(original_payment_id={payment.original_payment_id}); skipping reversal."
                )
                return

            # 2) Idempotency: if a reversal record already exists for this payment, skip creating another
            existing_reversal = (
                self.db.query(Payment)
                .filter(Payment.original_payment_id == payment.id)
                .order_by(Payment.id.desc())
                .first()
            )
            if existing_reversal:
                logger.info(
                    f"[REVERSAL_ALREADY_EXISTS] Reversal already exists for original payment {payment.id} "
                    f"(reversal id={existing_reversal.id}); skipping new reversal."
                )
                return

            # Mark the original payment as MTC_FAILED (terminal state)
            payment.status = PaymentStatus.MTC_FAILED
            payment.updated_on = datetime.now()
            self.db.add(payment)
            self.db.commit()
            logger.info(f"[REVERSAL_ORIGINAL_MARKED_FAILED] Original payment {payment.id} marked MTC_FAILED")

            # Generate unique transaction ID for reversal
            reversal_transaction_id = str(UniqueIdGenerator.generate())

            # Create NEW Payment record for the reversal transaction
            reversal_payment = Payment(
                bill_id=payment.bill_id,
                amount_paid=payment.amount_paid,
                payment_method=payment.payment_method,
                status=PaymentStatus.PENDING,  # Start fresh lifecycle
                transaction_id=reversal_transaction_id,  # The reversal has its own transaction ID
                ctm_transaction_id=reversal_transaction_id,  # For reversal, the transaction ID is the MTC
                mtc_transaction_id=None,  # Reversal payments don't have a second leg
                original_payment_id=payment.id,  # Link back to original payment
                service_name=payment.service_name,
                intent=payment.intent or "reversal",
                customer_email=payment.customer_email,
                customer_name=payment.customer_name,
                sender_phone=payment.sender_phone,  # Sender gets the refund
                receiver_phone=payment.receiver_phone,
                bank_code=payment.bank_code,
                network=payment.network,
                date_paid=datetime.now(),
                updated_on=datetime.now()
            )
            self.db.add(reversal_payment)
            self.db.flush()  # Flush to get the reversal_payment.id
            self.db.commit()
            logger.info(f"[REVERSAL_NEW_PAYMENT_CREATED] New reversal payment created with id={reversal_payment.id}, transaction_id={reversal_transaction_id}")

            # Build reversal payment request (send money back to sender)
            reversal_request = self._build_reversal_payment_request(reversal_payment, reversal_transaction_id)
            logger.info(f"Built reversal payment request for transaction: {reversal_transaction_id}")

            # Send to Orchard API
            logger.info(f"Sending reversal request to Orchard API for transaction: {reversal_transaction_id}")
            http_response = self.payment_gateway_client.process_payment(reversal_request)
            logger.info(f"Received reversal response from Orchard API: status_code={http_response.status_code}")

            # Process reversal response
            if http_response.status_code == 200:
                response_data = http_response.json()
                resp_code = response_data.get("resp_code") if response_data else None
                if response_data and resp_code in ["015", "027"]:
                    logger.info(f"[REVERSAL_RESPONSE_SUCCESS] Reversal request accepted for processing (resp_code: {resp_code}) for transactionId: {reversal_transaction_id}")
                    logger.info(f"[REVERSAL_PROCESSING] Awaiting reversal callback for reversal payment {reversal_payment.id}")

                    # Schedule background job to check REVERSAL PAYMENT status (not original payment)
                    try:
                        from core.payments.service.payment_check_service import PaymentCheckService
                        check_service = PaymentCheckService(self.db)
                        check_service.schedule_payment_status_check(reversal_payment.id)
                        logger.info(f"[REVERSAL_BACKGROUND_JOB_SCHEDULED] Status check scheduled for reversal payment {reversal_payment.id}")
                    except Exception as e:
                        logger.error(f"[REVERSAL_BACKGROUND_JOB_ERROR] Failed to schedule background check: {str(e)}", exc_info=True)
                else:
                    logger.warning(f"Reversal failed with response code: {response_data.get('resp_code')}")
                    reversal_payment.status = PaymentStatus.FAILED
                    self.db.add(reversal_payment)
                    self.db.commit()
            else:
                logger.error(f"Reversal gateway returned HTTP status: {http_response.status_code}")
                reversal_payment.status = PaymentStatus.FAILED
                self.db.add(reversal_payment)
                self.db.commit()

        except Exception as e:
            logger.error(f"Error initiating reversal for payment {payment.id}: {str(e)}", exc_info=True)
            raise

    def _build_reversal_payment_request(self, payment: Payment, reversal_transaction_id: str) -> Dict[str, Any]:
        """
        Build reversal payment request (refund to sender).
        Sends money back to sender when MTC fails.
        Detects the correct network based on sender's phone number.
        """
        from utilities.phone_utils import convert_to_local_ghana_format
        from core.beneficiaries.utility.network_detector import NetworkDetector

        amount = payment.amount_paid if isinstance(payment.amount_paid, Decimal) else Decimal(str(payment.amount_paid))

        # Detect network from sender's phone number (who we're refunding)
        detected_network, network_message = NetworkDetector.detect_network_from_phone(payment.sender_phone)
        network_to_use = detected_network if detected_network else payment.network.value

        logger.info(f"[REVERSAL_NETWORK_DETECTION] Sender phone: {payment.sender_phone} -> Detected network: {detected_network} ({network_message})")

        request_data = {
            "amount": str(amount.quantize(Decimal('0.00'))),
            "customer_number": convert_to_local_ghana_format(payment.sender_phone),  # Reversal: refund to sender
            "exttrid": reversal_transaction_id,
            "nw": network_to_use,  # Use detected network instead of stored network
            "reference": os.getenv("PAYMENT_REFERENCE", "Lemo Financial"),
            "service_id": self.service_id,
            "ts": self.payment_gateway_client.get_current_timestamp(),
            "callback_url": self.payment_gateway_client.build_callback_url(),
            "trans_type": "MTC"  # Reversal is also an MTC (Merchant to Customer)
        }
        logger.info(f"Built reversal payment request: trans_type=MTC (refund), network={network_to_use}")
        return request_data

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
            logger.warning(f"Unknown status code received: {trans_status}")
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
    
    def get_pending_payments_by_sender(self, sender_phone: str) -> List[Payment]:
        """
        Get all pending payments for a sender (user).
        
        This checks for transactions in progress (PENDING, CTM_PROCESSING, MTC_PROCESSING, etc.)
        
        Args:
            sender_phone: Phone number of the sender/user
            
        Returns:
            List of pending Payment records
        """
        pending_statuses = [
            PaymentStatus.PENDING,
            PaymentStatus.CTM_PROCESSING,
            PaymentStatus.MTC_PROCESSING,
            PaymentStatus.ATP_PROCESSING,
            PaymentStatus.BLP_PROCESSING,
            PaymentStatus.REVERSAL_PROCESSING,
        ]
        
        return self.db.query(Payment)\
            .filter(
                Payment.sender_phone == sender_phone,
                Payment.status.in_(pending_statuses)
            )\
            .order_by(desc(Payment.date_paid))\
            .all()
    
    # Helper Methods
    def _validate_payment(self, payment: Payment) -> None:
        if not payment.payment_method:
            raise PaymentValidationException("Payment method is required")

        if not payment.network:
            raise PaymentValidationException("Network is required")

        # Validate minimum amount for airtime transactions
        if payment.intent == "buy_airtime":
            min_airtime_amount = os.getenv("MIN_AIRTIME_AMOUNT", "0.2")
            try:
                min_amount = Decimal(str(min_airtime_amount))
            except:
                min_amount = Decimal("0.2")

            amount = Decimal(str(payment.amount_paid)) if payment.amount_paid else Decimal("0")
            if amount < min_amount:
                raise PaymentValidationException(f"Airtime top-up amount must be at least GHS {min_amount}, got GHS {amount}")

        if payment.payment_method == PaymentMethod.MOBILE_MONEY:
            if not payment.sender_phone:
                raise PaymentValidationException("Sender phone number is required for mobile money payments")
            # Valid networks for mobile money: MTN, VOD (Vodafone), AIR (AirtelTigo)
            # Also includes telco billers: GOT, DST, MPP, VPP, STT, VBB
            # And external biller system: ABS
            valid_networks = [Network.MTN, Network.VOD, Network.AIR, Network.GOT, Network.DST, Network.MPP, Network.VPP, Network.STT, Network.VBB, Network.ABS]
            if payment.network not in valid_networks:
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

    def _check_wallet_balance(self, payment: Payment, intent: str) -> None:
        """
        Check merchant wallet balance before initiating transaction.
        Prevents creating CTM if insufficient balance for MTC/ATP or reversals.

        Raises PaymentValidationException if insufficient balance.
        """
        try:
            logger.info(f"[BALANCE_CHECK_START] Checking wallet balance for intent: {intent}, amount: {payment.amount_paid}")

            # Call Orchard API to check balance using dedicated endpoint
            http_response = self.payment_gateway_client.check_wallet_balance()

            if http_response.status_code != 200:
                logger.error(f"[BALANCE_CHECK_ERROR] Failed to retrieve balance: {http_response.text}")
                raise PaymentValidationException("Unable to check wallet balance. Please try again later.")

            balance_data = http_response.json()
            logger.info(f"[BALANCE_CHECK_RESPONSE] Wallet balances - payout: {balance_data.get('payout_bal')}, airtime: {balance_data.get('airtime_bal')}, billpay: {balance_data.get('billpay_bal')}")

            amount = Decimal(str(payment.amount_paid)) if payment.amount_paid else Decimal("0")

            # Check balance based on intent
            if intent == "send_money":
                payout_bal = Decimal(str(balance_data.get("payout_bal", 0)))
                if payout_bal < amount:
                    raise PaymentValidationException(
                        f"Insufficient payout balance. Required: GHS {amount}, Available: GHS {payout_bal}"
                    )
                logger.info(f"[BALANCE_CHECK_PASS] Payout balance sufficient for send_money: {payout_bal} >= {amount}")

            elif intent == "buy_airtime":
                airtime_bal = Decimal(str(balance_data.get("airtime_bal", 0)))
                payout_bal = Decimal(str(balance_data.get("payout_bal", 0)))

                if airtime_bal < amount:
                    raise PaymentValidationException(
                        f"Insufficient airtime balance. Required: GHS {amount}, Available: GHS {airtime_bal}"
                    )
                if payout_bal < amount:
                    raise PaymentValidationException(
                        f"Insufficient payout balance for reversal. Required: GHS {amount}, Available: GHS {payout_bal}"
                    )
                logger.info(f"[BALANCE_CHECK_PASS] Airtime and payout balance sufficient: airtime={airtime_bal} >= {amount}, payout={payout_bal} >= {amount}")

            elif intent == "pay_bill":
                # Bill payments are CTM (collect), use available_collect_bal from Orchard API
                collect_bal = Decimal(str(balance_data.get("available_collect_bal", 0)))
                payout_bal = Decimal(str(balance_data.get("payout_bal", 0)))

                if collect_bal < amount:
                    raise PaymentValidationException(
                        f"Insufficient collection balance for bill payment. Required: GHS {amount}, Available: GHS {collect_bal}"
                    )
                if payout_bal < amount:
                    raise PaymentValidationException(
                        f"Insufficient payout balance for reversal. Required: GHS {amount}, Available: GHS {payout_bal}"
                    )
                logger.info(f"[BALANCE_CHECK_PASS] Bill payment and payout balance sufficient: collect={collect_bal} >= {amount}, payout={payout_bal} >= {amount}")

            logger.info(f"[BALANCE_CHECK_SUCCESS] Wallet balance check passed for intent: {intent}")

        except PaymentValidationException:
            raise
        except Exception as e:
            logger.error(f"[BALANCE_CHECK_EXCEPTION] Unexpected error during balance check: {str(e)}", exc_info=True)
            raise PaymentValidationException(f"Error checking wallet balance: {str(e)}")

    def _build_payment_request(self, payment: Payment, intent: str) -> Dict[str, Any]:
        """
        Build Orchard API request following specification.
        trans_type is determined by intent.
        """
        # Map intent to transaction type
        transaction_type_map = {
            "buy_airtime": "CTM",           # First stage: Collect payment from customer
            "send_money": "CTM",            # Customer to Merchant
            "pay_bill": "CTM",              # Bill payment (also CTM)
            "get_loan": "MTC",              # Merchant to Customer (Payout)
            "verify_account": "AII"         # Account Inquiry
        }

        trans_type = transaction_type_map.get(intent, "CTM")  # Default to CTM

        # Build base request (all transaction types need these)
        # Ensure amount_paid is a Decimal before formatting
        from utilities.phone_utils import convert_to_local_ghana_format
        from core.beneficiaries.utility.network_detector import NetworkDetector

        # Detect network from sender's phone number
        detected_network, network_message = NetworkDetector.detect_network_from_phone(payment.sender_phone)
        network_to_use = detected_network if detected_network else payment.network.value

        logger.info(f"[CTM_NETWORK_DETECTION] Sender phone: {payment.sender_phone} -> Detected network: {detected_network} ({network_message})")

        amount = payment.amount_paid if isinstance(payment.amount_paid, Decimal) else Decimal(str(payment.amount_paid))
        request_data = {
            "amount": str(amount.quantize(Decimal('0.00'))),
            "customer_number": convert_to_local_ghana_format(payment.sender_phone),  # CTM: sender (in 0xxx format)
            "exttrid": payment.transaction_id,  # Keep as string, not int
            "nw": network_to_use,  # Use detected network instead of stored network
            "reference": os.getenv("PAYMENT_REFERENCE", "Lemo Financial"),
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
    
    def _handle_pending_payment(self, payment: Payment, response: Dict[str, Any]) -> PaymentResultResponse:
        """
        Handle response code 015: Request received for processing.
        Payment is PENDING - schedule background job to check status instead of waiting for callback.
        """
        logger.info(f"Payment request accepted (resp_code: 015), scheduling status checks for transactionId: {payment.transaction_id}")
        payment.status = PaymentStatus.PENDING

        logger.info(f"Persisting pending payment for transactionId: {payment.transaction_id}")
        self.db.add(payment)
        self.db.commit()

        logger.info(f"Payment persisted with PENDING status for paymentId: {payment.id}, transactionId: {payment.transaction_id}")

        # Schedule background job to check CTM status (uses env variables for interval and attempts)
        try:
            from core.payments.service.payment_check_service import PaymentCheckService
            check_service = PaymentCheckService(self.db)
            check_service.schedule_payment_status_check(payment.id)
            logger.info(f"[CTM_BACKGROUND_JOB_SCHEDULED] Status check scheduled for payment {payment.id}")
        except Exception as e:
            logger.error(f"[CTM_BACKGROUND_JOB_ERROR] Failed to schedule background check: {str(e)}", exc_info=True)

        return PaymentResultResponse(
            payment_id=payment.id,
            status=PaymentStatus.PENDING,
            responseCode=response.get("resp_code"),
            responseDescription=response.get("resp_desc"),
            transactionId=payment.transaction_id,
            paymentMethod=payment.payment_method
        )

    def _handle_success(self, payment: Payment, response: Dict[str, Any]) -> PaymentResultResponse:
        """
        Handle final payment success (called from callback when trans_status = 000).
        Create invoice and mark payment as SUCCESS.
        """
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
        logger.warning(f"Handling gateway failure for transactionId: {payment.transaction_id}. Response code: {response.get('resp_code')}, description: {response.get('resp_desc')}")

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

    def send_payment_notification(self, payment: Payment, is_success: bool, failure_reason: str = None) -> None:
        """
        Generate receipt and send WhatsApp notification to user after payment success/failure.
        Called from both callback processing and background status checks.

        Args:
            payment: The payment record
            is_success: Whether payment succeeded
            failure_reason: Reason for failure (if applicable)
        """
        import os
        from core.webhooks.service.whatsapp_service import WhatsAppService
        from core.nlu.nlu import LebeNLUSystem
        from utilities.phone_utils import normalize_ghana_phone_number

        try:
            # Get WhatsApp phone number ID from environment
            phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
            if not phone_number_id:
                logger.warning("WHATSAPP_PHONE_NUMBER_ID not set in environment variables")
                return

            # Normalize phone number for WhatsApp (must be in format 233XXXXXXXXX)
            # Use sender_phone since we're notifying the person who initiated the payment
            normalized_phone = normalize_ghana_phone_number(payment.sender_phone)

            # Initialize WhatsApp service
            whatsapp_service = WhatsAppService()

            if is_success:
                # Generate receipt using NLU system's method (skip for airtime/bill payments).
                intent = (payment.intent or "payment").lower()
                receipt_url = None
                should_send_receipt_image = intent not in {"buy_airtime", "pay_bill"}

                if should_send_receipt_image:
                    try:
                        # Use NLU's receipt generation method
                        nlu_system = LebeNLUSystem()
                        receipt_url = nlu_system.generate_receipt_after_payment(
                            transaction_id=payment.transaction_id,
                            user_id=payment.sender_phone,
                            intent=intent,
                            amount=payment.amount_paid,
                            status='SUCCESS',
                            sender=payment.sender_phone,
                            receiver=payment.receiver_phone,
                            sender_name=payment.sender_name or payment.customer_name or "N/A",
                            receiver_name=payment.receiver_name or "N/A",
                            sender_provider=payment.sender_provider or "N/A",
                            receiver_provider=payment.receiver_provider or "N/A",
                            payment_method=payment.payment_method.name,
                            timestamp=payment.updated_on or datetime.now()
                        )
                    except Exception as e:
                        logger.error(f"[RECEIPT_GENERATION_FAILED] Failed to generate receipt for payment {payment.id}: {str(e)}")
                        receipt_url = None  # Will fall back to text-only message

                # Prepare success message
                success_caption = (
                    f"✅ Payment Successful!\n\n"
                    f"{payment.service_name}\n"
                    f"Amount: GHS {payment.amount_paid}\n"
                    f"Transaction ID: {payment.transaction_id}"
                )

                # Send receipt with image if available, otherwise send text-only
                if receipt_url:
                    whatsapp_service.send_message_receipt(
                        phone_number_id=phone_number_id,
                        recipient_phone=normalized_phone,
                        image_url=receipt_url,
                        caption=success_caption
                    )
                    logger.info(f"[NOTIFICATION] Success receipt sent for payment {payment.id}")
                else:
                    # Fallback to text-only message if receipt generation failed
                    whatsapp_service.send_message(
                        phone_number_id=phone_number_id,
                        recipient_phone=normalized_phone,
                        message_text=success_caption
                    )
                    logger.info(f"[NOTIFICATION] Success text message sent (receipt unavailable) for payment {payment.id}")

            else:
                # Don't send a receipt image for failed payments.
                # Instead send a plain text failure notification to avoid forwarding receipts on errors.
                failure_caption = (
                    f"❌ Payment Failed\n\n"
                    f"{payment.service_name}\n"
                    f"Amount: GHS {payment.amount_paid}\n"
                    f"Transaction ID: {payment.transaction_id or 'N/A'}\n\n"
                    f"Reason: {failure_reason or 'Unknown error'}\n\n"
                    f"Please try again or contact support if the issue persists."
                )

                sent = whatsapp_service.send_message(
                    phone_number_id=phone_number_id,
                    recipient_phone=normalized_phone,
                    message_text=failure_caption,
                    preview_url=False
                )

                if sent:
                    logger.info(f"[NOTIFICATION] Failure notification sent for payment {payment.id}")
                else:
                    logger.warning(f"[NOTIFICATION] Failure notification could not be sent for payment {payment.id}")

        except Exception as e:
            logger.error(f"[NOTIFICATION_ERROR] Error sending payment notification for payment {payment.id}: {str(e)}", exc_info=True)
            # Don't raise exception - notification failure shouldn't break payment processing
