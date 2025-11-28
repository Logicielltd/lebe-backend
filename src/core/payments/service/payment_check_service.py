import logging
import os
from datetime import datetime
from sqlalchemy.orm import Session
from apscheduler.schedulers.background import BackgroundScheduler
from core.payments.model.payment import Payment
from core.payments.model.paymentstatus import PaymentStatus
from utilities.paymentgatewayclient import PaymentGatewayClient

logger = logging.getLogger(__name__)

class PaymentCheckService:
    _scheduler_instance = None
    _payment_attempt_counts = {}  # Track attempts per payment

    # Default configuration
    DEFAULT_CHECK_INTERVAL_SECONDS = 30
    DEFAULT_MAX_ATTEMPTS = 10

    def __init__(self, db: Session = None):
        self.db = db
        self.payment_gateway_client = PaymentGatewayClient()

        # Use singleton scheduler instance
        if PaymentCheckService._scheduler_instance is None:
            PaymentCheckService._scheduler_instance = BackgroundScheduler()
        self.scheduler = PaymentCheckService._scheduler_instance

        # Load configuration from environment variables
        self.check_interval_seconds = self._get_check_interval()
        self.max_attempts = self._get_max_attempts()

    @staticmethod
    def _get_check_interval() -> int:
        """
        Get check interval from environment variable PAYMENT_CHECK_INTERVAL_SECONDS.
        Default: 30 seconds
        """
        try:
            interval = int(os.getenv("PAYMENT_CHECK_INTERVAL_SECONDS", PaymentCheckService.DEFAULT_CHECK_INTERVAL_SECONDS))
            logger.info(f"[CONFIG] Payment check interval set to: {interval} seconds")
            return interval
        except ValueError:
            logger.warning(f"[CONFIG] Invalid PAYMENT_CHECK_INTERVAL_SECONDS, using default: {PaymentCheckService.DEFAULT_CHECK_INTERVAL_SECONDS}")
            return PaymentCheckService.DEFAULT_CHECK_INTERVAL_SECONDS

    @staticmethod
    def _get_max_attempts() -> int:
        """
        Get max attempts from environment variable PAYMENT_CHECK_MAX_ATTEMPTS.
        Default: 10 attempts
        """
        try:
            max_attempts = int(os.getenv("PAYMENT_CHECK_MAX_ATTEMPTS", PaymentCheckService.DEFAULT_MAX_ATTEMPTS))
            logger.info(f"[CONFIG] Payment check max attempts set to: {max_attempts}")
            return max_attempts
        except ValueError:
            logger.warning(f"[CONFIG] Invalid PAYMENT_CHECK_MAX_ATTEMPTS, using default: {PaymentCheckService.DEFAULT_MAX_ATTEMPTS}")
            return PaymentCheckService.DEFAULT_MAX_ATTEMPTS

    def schedule_payment_status_check(self, payment_id: int, check_interval_seconds: int = None, max_attempts: int = None):
        """
        Schedule a background job to check payment status.

        Uses configured intervals from environment variables if not explicitly provided.

        Args:
            payment_id: The payment ID to check
            check_interval_seconds: Check every N seconds (default: from env or 30)
            max_attempts: Maximum number of checks before marking as failed (default: from env or 10)
        """
        try:
            # Use instance config if not provided
            if check_interval_seconds is None:
                check_interval_seconds = self.check_interval_seconds
            if max_attempts is None:
                max_attempts = self.max_attempts

            job_id = f"payment_check_{payment_id}"

            # Initialize attempt counter for this payment
            PaymentCheckService._payment_attempt_counts[payment_id] = 0

            # Calculate total duration
            total_duration_seconds = check_interval_seconds * max_attempts

            # Schedule the check to run every N seconds
            self.scheduler.add_job(
                func=self.check_payment_status,
                trigger="interval",
                seconds=check_interval_seconds,
                args=[payment_id, max_attempts, check_interval_seconds],
                id=job_id,
                replace_existing=True,
                max_instances=1  # Prevent multiple concurrent runs of same job
            )

            logger.info(f"[PAYMENT_CHECK_SCHEDULED] Job {job_id} scheduled for payment {payment_id} - Check every {check_interval_seconds}s, max {max_attempts} attempts ({total_duration_seconds}s total)")

            if not self.scheduler.running:
                self.scheduler.start()
                logger.info("[SCHEDULER] Background scheduler started")

        except Exception as e:
            logger.error(f"[PAYMENT_CHECK_SCHEDULE_ERROR] Failed to schedule payment check: {str(e)}", exc_info=True)

    def check_payment_status(self, payment_id: int, max_attempts: int, check_interval_seconds: int):
        """
        Check the payment status with Orchard API.
        Runs every 30 seconds, up to 10 times (5 minutes total).
        If still processing after max attempts, mark as failed.
        """
        try:
            from utilities.dbconfig import SessionLocal
            db = SessionLocal()

            # Increment attempt counter
            current_attempt = PaymentCheckService._payment_attempt_counts.get(payment_id, 0) + 1
            PaymentCheckService._payment_attempt_counts[payment_id] = current_attempt

            logger.info(f"[PAYMENT_CHECK_START] Checking status for payment {payment_id} (Attempt {current_attempt}/{max_attempts})")

            payment = db.query(Payment).filter(Payment.id == payment_id).first()

            if not payment:
                logger.error(f"[PAYMENT_CHECK_NOT_FOUND] Payment not found: {payment_id}")
                self._stop_check_job(payment_id)
                db.close()
                return

            logger.info(f"[PAYMENT_CHECK_STATUS] Current status: {payment.status} | Transaction ID: {payment.transaction_id} | MTC Transaction ID: {payment.mtc_transaction_id}")

            # If already SUCCESS, stop checking
            if payment.status == PaymentStatus.SUCCESS:
                logger.info(f"[PAYMENT_CHECK_ALREADY_SUCCESS] Payment {payment_id} already marked SUCCESS")
                self._stop_check_job(payment_id)
                db.close()
                return

            # If terminal failed state, stop checking
            if payment.status in [PaymentStatus.CTM_FAILED, PaymentStatus.MTC_FAILED, PaymentStatus.ATP_FAILED, PaymentStatus.BLP_FAILED, PaymentStatus.FAILED]:
                logger.info(f"[PAYMENT_CHECK_TERMINAL_FAILED] Payment {payment_id} in terminal failed state: {payment.status}")
                logger.info(f"[PAYMENT_CHECK_TERMINAL_FAILED_STOP] Stopping job - no further checks needed")
                self._stop_check_job(payment_id)
                db.close()
                return

            # Query Orchard API for either CTM or MTC status based on payment status
            transaction_id_to_check = None
            check_type = None

            if payment.status == PaymentStatus.PENDING:
                # Check CTM status using main transaction_id
                if payment.transaction_id:
                    transaction_id_to_check = payment.transaction_id
                    check_type = "CTM"
                else:
                    logger.warning(f"[PAYMENT_CHECK_MISSING_TXN_ID] Payment {payment_id} is PENDING but has no transaction_id")
            elif payment.status == PaymentStatus.MTC_PROCESSING:
                # Check MTC status using mtc_transaction_id
                if payment.mtc_transaction_id:
                    transaction_id_to_check = payment.mtc_transaction_id
                    check_type = "MTC"
                else:
                    logger.warning(f"[PAYMENT_CHECK_MISSING_MTC_TXN_ID] Payment {payment_id} is MTC_PROCESSING but has no mtc_transaction_id")
            elif payment.status == PaymentStatus.ATP_PROCESSING:
                # Check ATP status using atp_transaction_id
                if payment.atp_transaction_id:
                    transaction_id_to_check = payment.atp_transaction_id
                    check_type = "ATP"
                else:
                    logger.warning(f"[PAYMENT_CHECK_MISSING_ATP_TXN_ID] Payment {payment_id} is ATP_PROCESSING but has no atp_transaction_id")
            elif payment.status == PaymentStatus.BLP_PROCESSING:
                # Check BLP status using blp_transaction_id
                if payment.blp_transaction_id:
                    transaction_id_to_check = payment.blp_transaction_id
                    check_type = "BLP"
                else:
                    logger.warning(f"[PAYMENT_CHECK_MISSING_BLP_TXN_ID] Payment {payment_id} is BLP_PROCESSING but has no blp_transaction_id")

            if transaction_id_to_check:
                logger.info(f"[PAYMENT_CHECK_QUERY_API] Querying Orchard API for {check_type} transaction: {transaction_id_to_check}")

                # Query Orchard API for transaction status
                status = self._query_orchard_transaction_status(transaction_id_to_check)

                if status == "SUCCESS":
                    logger.info(f"[PAYMENT_CHECK_API_SUCCESS] Orchard API confirms payment success for {payment_id} on attempt {current_attempt}")

                    # Check if this is a reversal payment (has original_payment_id set)
                    is_reversal = payment.original_payment_id is not None

                    if is_reversal:
                        # This is a reversal payment - it's just a single MTC, no second stage
                        logger.info(f"[PAYMENT_CHECK_REVERSAL_SUCCESS] Reversal payment {payment_id} confirmed successful (refund to original sender)")
                        payment.status = PaymentStatus.SUCCESS
                        payment.updated_on = datetime.now()
                        db.add(payment)
                        db.commit()
                        db.refresh(payment)
                        logger.info(f"[PAYMENT_CHECK_UPDATED] Reversal payment {payment_id} marked SUCCESS")
                        self._stop_check_job(payment_id)
                    elif payment.status == PaymentStatus.PENDING:
                        # This is CTM success - initiate second stage (MTC or ATP)
                        logger.info(f"[PAYMENT_CHECK_CTM_SUCCESS] CTM confirmed successful for payment {payment_id}")
                        payment.status = PaymentStatus.CTM_SUCCESS
                        payment.updated_on = datetime.now()
                        db.add(payment)
                        db.commit()
                        db.refresh(payment)  # Refresh to ensure object is in sync with database
                        logger.info(f"[PAYMENT_CHECK_STATUS_UPDATED] Payment {payment_id} marked CTM_SUCCESS")

                        # Determine second stage based on intent
                        try:
                            from core.payments.service.paymentservice import PaymentService
                            payment_service = PaymentService(db)

                            if payment.intent == "buy_airtime":
                                # Check if ATP was already initiated by callback to prevent duplicate ATP initiation
                                if payment.atp_transaction_id is not None:
                                    logger.info(f"[PAYMENT_CHECK_ATP_ALREADY_INITIATED] ATP already initiated with transaction ID {payment.atp_transaction_id}, skipping duplicate ATP initiation for payment {payment_id}")
                                    # Continue job - it will now check ATP status since payment.status is ATP_PROCESSING
                                    logger.info(f"[PAYMENT_CHECK_JOB_CONTINUING] Job will continue to check ATP status for payment {payment_id}")
                                else:
                                    # Initiate ATP for airtime
                                    logger.info(f"[PAYMENT_CHECK_ATP_INITIATING] Initiating ATP from background check for payment {payment_id}")
                                    payment_service._initiate_atp(payment)
                                    logger.info(f"[PAYMENT_CHECK_ATP_INITIATED] ATP initiated from background check for payment {payment_id}")
                                    # Continue job - it will now check ATP status since payment.status is ATP_PROCESSING
                                    logger.info(f"[PAYMENT_CHECK_JOB_CONTINUING] Job will continue to check ATP status for payment {payment_id}")
                            elif payment.intent == "pay_bill":
                                # Check if BLP was already initiated by callback to prevent duplicate BLP initiation
                                if payment.blp_transaction_id is not None:
                                    logger.info(f"[PAYMENT_CHECK_BLP_ALREADY_INITIATED] BLP already initiated with transaction ID {payment.blp_transaction_id}, skipping duplicate BLP initiation for payment {payment_id}")
                                    # Continue job - it will now check BLP status since payment.status is BLP_PROCESSING
                                    logger.info(f"[PAYMENT_CHECK_JOB_CONTINUING] Job will continue to check BLP status for payment {payment_id}")
                                else:
                                    # Initiate BLP for bill payment
                                    logger.info(f"[PAYMENT_CHECK_BLP_INITIATING] Initiating BLP from background check for payment {payment_id}")
                                    payment_service._initiate_blp(payment)
                                    logger.info(f"[PAYMENT_CHECK_BLP_INITIATED] BLP initiated from background check for payment {payment_id}")
                                    # Continue job - it will now check BLP status since payment.status is BLP_PROCESSING
                                    logger.info(f"[PAYMENT_CHECK_JOB_CONTINUING] Job will continue to check BLP status for payment {payment_id}")
                            else:
                                # Check if MTC was already initiated by callback to prevent duplicate MTC initiation
                                if payment.mtc_transaction_id is not None:
                                    logger.info(f"[PAYMENT_CHECK_MTC_ALREADY_INITIATED] MTC already initiated with transaction ID {payment.mtc_transaction_id}, skipping duplicate MTC initiation for payment {payment_id}")
                                    # Continue job - it will now check MTC status since payment.status is MTC_PROCESSING
                                    logger.info(f"[PAYMENT_CHECK_JOB_CONTINUING] Job will continue to check MTC status for payment {payment_id}")
                                else:
                                    # Initiate MTC for send_money and other intents
                                    logger.info(f"[PAYMENT_CHECK_MTC_INITIATING] Initiating MTC from background check for payment {payment_id}")
                                    payment_service._initiate_mtc(payment)
                                    logger.info(f"[PAYMENT_CHECK_MTC_INITIATED] MTC initiated from background check for payment {payment_id}")
                                    # Continue job - it will now check MTC status since payment.status is MTC_PROCESSING
                                    logger.info(f"[PAYMENT_CHECK_JOB_CONTINUING] Job will continue to check MTC status for payment {payment_id}")
                        except Exception as e:
                            logger.error(f"[PAYMENT_CHECK_SECOND_STAGE_ERROR] Error initiating second stage: {str(e)}", exc_info=True)
                            # Reload payment from DB to get current state
                            payment = db.query(Payment).filter(Payment.id == payment_id).first()
                            if payment:
                                payment.status = PaymentStatus.CTM_FAILED
                                db.add(payment)
                                db.commit()

                    elif payment.status == PaymentStatus.MTC_PROCESSING:
                        # This is MTC success - final success
                        logger.info(f"[PAYMENT_CHECK_MTC_SUCCESS] MTC confirmed successful for payment {payment_id}")
                        payment.status = PaymentStatus.SUCCESS
                        payment.updated_on = datetime.now()
                        db.add(payment)
                        db.commit()
                        db.refresh(payment)  # Refresh to ensure object is in sync with database
                        logger.info(f"[PAYMENT_CHECK_UPDATED] Payment {payment_id} marked SUCCESS")

                        # Send WhatsApp notification with receipt
                        try:
                            from core.payments.service.paymentservice import PaymentService
                            payment_service = PaymentService(db)
                            payment_service.send_payment_notification(payment, is_success=True)
                            logger.info(f"[PAYMENT_CHECK_NOTIFICATION] Success notification sent for payment {payment_id}")
                        except Exception as e:
                            logger.error(f"[PAYMENT_CHECK_NOTIFICATION_ERROR] Failed to send success notification for payment {payment_id}: {str(e)}", exc_info=True)

                        self._stop_check_job(payment_id)

                    elif payment.status == PaymentStatus.ATP_PROCESSING:
                        # This is ATP success - final success
                        logger.info(f"[PAYMENT_CHECK_ATP_SUCCESS] ATP confirmed successful for payment {payment_id}")
                        payment.status = PaymentStatus.SUCCESS
                        payment.updated_on = datetime.now()
                        db.add(payment)
                        db.commit()
                        db.refresh(payment)  # Refresh to ensure object is in sync with database
                        logger.info(f"[PAYMENT_CHECK_UPDATED] Payment {payment_id} marked SUCCESS")

                        # Send WhatsApp notification with receipt
                        try:
                            from core.payments.service.paymentservice import PaymentService
                            payment_service = PaymentService(db)
                            payment_service.send_payment_notification(payment, is_success=True)
                            logger.info(f"[PAYMENT_CHECK_NOTIFICATION] Success notification sent for payment {payment_id}")
                        except Exception as e:
                            logger.error(f"[PAYMENT_CHECK_NOTIFICATION_ERROR] Failed to send success notification for payment {payment_id}: {str(e)}", exc_info=True)

                        self._stop_check_job(payment_id)

                    elif payment.status == PaymentStatus.BLP_PROCESSING:
                        # This is BLP success - final success
                        logger.info(f"[PAYMENT_CHECK_BLP_SUCCESS] BLP confirmed successful for payment {payment_id}")
                        payment.status = PaymentStatus.SUCCESS
                        payment.updated_on = datetime.now()
                        db.add(payment)
                        db.commit()
                        db.refresh(payment)  # Refresh to ensure object is in sync with database
                        logger.info(f"[PAYMENT_CHECK_UPDATED] Payment {payment_id} marked SUCCESS")

                        # Send WhatsApp notification with receipt
                        try:
                            from core.payments.service.paymentservice import PaymentService
                            payment_service = PaymentService(db)
                            payment_service.send_payment_notification(payment, is_success=True)
                            logger.info(f"[PAYMENT_CHECK_NOTIFICATION] Success notification sent for payment {payment_id}")
                        except Exception as e:
                            logger.error(f"[PAYMENT_CHECK_NOTIFICATION_ERROR] Failed to send success notification for payment {payment_id}: {str(e)}", exc_info=True)

                        self._stop_check_job(payment_id)

                    else:
                        # Unexpected status, mark as success anyway
                        logger.warning(f"[PAYMENT_CHECK_UNEXPECTED_STATUS] Payment {payment_id} in status {payment.status}, marking SUCCESS")
                        payment.status = PaymentStatus.SUCCESS
                        payment.updated_on = datetime.now()
                        db.add(payment)
                        db.commit()
                        self._stop_check_job(payment_id)

                elif status == "FAILED":
                    logger.warning(f"[PAYMENT_CHECK_API_FAILED] Orchard API confirms payment failed for {payment_id}")

                    # Check if this is a reversal payment
                    is_reversal = payment.original_payment_id is not None

                    if is_reversal:
                        # Reversal payment failed - just mark as failed, don't create another reversal
                        logger.warning(f"[PAYMENT_CHECK_REVERSAL_FAILED] Reversal payment {payment_id} failed")
                        payment.status = PaymentStatus.FAILED
                    elif payment.status == PaymentStatus.PENDING:
                        # CTM failed - send notification to user
                        logger.warning(f"[PAYMENT_CHECK_CTM_FAILED] Payment {payment_id} CTM failed")
                        payment.status = PaymentStatus.CTM_FAILED

                        # Send failure notification for CTM
                        try:
                            from core.payments.service.paymentservice import PaymentService
                            payment_service = PaymentService(db)
                            payment_service.send_payment_notification(
                                payment,
                                is_success=False,
                                failure_reason="Payment collection failed. No money was deducted from your account."
                            )
                            logger.info(f"[PAYMENT_CHECK_CTM_NOTIFICATION] CTM failure notification sent for payment {payment_id}")
                        except Exception as e:
                            logger.error(f"[PAYMENT_CHECK_CTM_NOTIFICATION_ERROR] Failed to send CTM failure notification: {str(e)}", exc_info=True)
                    elif payment.status == PaymentStatus.MTC_PROCESSING:
                        # MTC failed - initiate reversal and send failure notification
                        logger.warning(f"[PAYMENT_CHECK_MTC_FAILED] Payment {payment_id} MTC failed")
                        payment.status = PaymentStatus.MTC_FAILED

                        # Initiate reversal transaction (refund to sender)
                        try:
                            from core.payments.service.paymentservice import PaymentService
                            payment_service = PaymentService(db)
                            payment_service._initiate_reversal(payment)
                            logger.info(f"[REVERSAL_INITIATED] Reversal initiated for failed payment {payment_id}")
                        except Exception as e:
                            logger.error(f"[REVERSAL_ERROR] Error initiating reversal: {str(e)}", exc_info=True)

                        # Send failure notification with receipt
                        try:
                            from core.payments.service.paymentservice import PaymentService
                            payment_service = PaymentService(db)
                            payment_service.send_payment_notification(
                                payment,
                                is_success=False,
                                failure_reason="Payout failed. Reversal being processed."
                            )
                            logger.info(f"[PAYMENT_CHECK_NOTIFICATION] Failure notification sent for payment {payment_id}")
                        except Exception as e:
                            logger.error(f"[PAYMENT_CHECK_NOTIFICATION_ERROR] Failed to send failure notification: {str(e)}", exc_info=True)
                    elif payment.status == PaymentStatus.ATP_PROCESSING:
                        # ATP failed - initiate reversal and send failure notification
                        logger.warning(f"[PAYMENT_CHECK_ATP_FAILED] Payment {payment_id} ATP failed")
                        payment.status = PaymentStatus.ATP_FAILED

                        # Initiate reversal transaction (refund to sender)
                        try:
                            from core.payments.service.paymentservice import PaymentService
                            payment_service = PaymentService(db)
                            payment_service._initiate_reversal(payment)
                            logger.info(f"[REVERSAL_INITIATED] Reversal initiated for failed payment {payment_id}")
                        except Exception as e:
                            logger.error(f"[REVERSAL_ERROR] Error initiating reversal: {str(e)}", exc_info=True)

                        # Send failure notification with receipt
                        try:
                            from core.payments.service.paymentservice import PaymentService
                            payment_service = PaymentService(db)
                            payment_service.send_payment_notification(
                                payment,
                                is_success=False,
                                failure_reason="Airtime request failed. Refund being processed."
                            )
                            logger.info(f"[PAYMENT_CHECK_NOTIFICATION] Failure notification sent for payment {payment_id}")
                        except Exception as e:
                            logger.error(f"[PAYMENT_CHECK_NOTIFICATION_ERROR] Failed to send failure notification: {str(e)}", exc_info=True)

                    elif payment.status == PaymentStatus.BLP_PROCESSING:
                        # BLP failed - initiate reversal and send failure notification
                        logger.warning(f"[PAYMENT_CHECK_BLP_FAILED] Payment {payment_id} BLP failed")
                        payment.status = PaymentStatus.BLP_FAILED

                        # Initiate reversal transaction (refund to sender)
                        try:
                            from core.payments.service.paymentservice import PaymentService
                            payment_service = PaymentService(db)
                            payment_service._initiate_reversal(payment)
                            logger.info(f"[REVERSAL_INITIATED] Reversal initiated for failed payment {payment_id}")
                        except Exception as e:
                            logger.error(f"[REVERSAL_ERROR] Error initiating reversal: {str(e)}", exc_info=True)

                        # Send failure notification with receipt
                        try:
                            from core.payments.service.paymentservice import PaymentService
                            payment_service = PaymentService(db)
                            payment_service.send_payment_notification(
                                payment,
                                is_success=False,
                                failure_reason="Bill payment failed. Refund being processed."
                            )
                            logger.info(f"[PAYMENT_CHECK_NOTIFICATION] Failure notification sent for payment {payment_id}")
                        except Exception as e:
                            logger.error(f"[PAYMENT_CHECK_NOTIFICATION_ERROR] Failed to send failure notification: {str(e)}", exc_info=True)

                    payment.updated_on = datetime.now()
                    db.add(payment)
                    db.commit()
                    logger.warning(f"[PAYMENT_CHECK_UPDATED] Payment {payment_id} marked as failed")
                    self._stop_check_job(payment_id)

                else:
                    # Still processing (PENDING)
                    if current_attempt >= max_attempts:
                        # Max attempts reached, mark as failed
                        total_wait_seconds = check_interval_seconds * max_attempts
                        logger.warning(f"[PAYMENT_CHECK_MAX_ATTEMPTS] Payment {payment_id} reached max attempts ({max_attempts}) after {total_wait_seconds}s")

                        # Check if this is a reversal payment
                        is_reversal = payment.original_payment_id is not None

                        if is_reversal:
                            # Reversal timeout - just mark as failed
                            payment.status = PaymentStatus.FAILED
                            logger.warning(f"[PAYMENT_CHECK_REVERSAL_TIMEOUT] Reversal payment {payment_id} timeout after {total_wait_seconds}s")
                        elif payment.status == PaymentStatus.PENDING:
                            payment.status = PaymentStatus.CTM_FAILED
                            logger.warning(f"[PAYMENT_CHECK_CTM_TIMEOUT] Payment {payment_id} CTM timeout after {total_wait_seconds}s")

                            # Send timeout notification for CTM
                            try:
                                from core.payments.service.paymentservice import PaymentService
                                payment_service = PaymentService(db)
                                payment_service.send_payment_notification(
                                    payment,
                                    is_success=False,
                                    failure_reason="Payment request timed out. No money was deducted from your account."
                                )
                                logger.info(f"[PAYMENT_CHECK_CTM_TIMEOUT_NOTIFICATION] CTM timeout notification sent for payment {payment_id}")
                            except Exception as e:
                                logger.error(f"[PAYMENT_CHECK_CTM_TIMEOUT_NOTIFICATION_ERROR] Failed to send CTM timeout notification: {str(e)}", exc_info=True)
                        else:
                            payment.status = PaymentStatus.MTC_FAILED
                            logger.warning(f"[PAYMENT_CHECK_MTC_TIMEOUT] Payment {payment_id} MTC timeout after {total_wait_seconds}s")

                        payment.updated_on = datetime.now()
                        db.add(payment)
                        db.commit()
                        logger.warning(f"[PAYMENT_CHECK_UPDATED] Payment {payment_id} marked as failed due to timeout")
                        self._stop_check_job(payment_id)
                    else:
                        # Still processing, will retry on next interval
                        remaining_attempts = max_attempts - current_attempt
                        logger.info(f"[PAYMENT_CHECK_CONTINUE] Payment {payment_id} still processing. {remaining_attempts} attempts remaining")
            else:
                # Can't query API (no valid transaction ID), check if max attempts reached
                logger.warning(f"[PAYMENT_CHECK_NO_TRANSACTION_ID] Cannot query for payment {payment_id} - no valid transaction ID to check")

                if current_attempt >= max_attempts:
                    # Max attempts reached, mark as failed
                    total_wait_seconds = check_interval_seconds * max_attempts
                    logger.warning(f"[PAYMENT_CHECK_MAX_ATTEMPTS] Payment {payment_id} reached max attempts ({max_attempts}) after {total_wait_seconds}s")

                    # Check if this is a reversal payment
                    is_reversal = payment.original_payment_id is not None

                    if is_reversal:
                        # Reversal timeout - just mark as failed
                        payment.status = PaymentStatus.FAILED
                        logger.warning(f"[PAYMENT_CHECK_REVERSAL_TIMEOUT] Reversal payment {payment_id} timeout after {total_wait_seconds}s")
                    elif payment.status == PaymentStatus.PENDING:
                        payment.status = PaymentStatus.CTM_FAILED
                        logger.warning(f"[PAYMENT_CHECK_CTM_TIMEOUT] Payment {payment_id} CTM timeout after {total_wait_seconds}s")
                    else:
                        payment.status = PaymentStatus.MTC_FAILED
                        logger.warning(f"[PAYMENT_CHECK_MTC_TIMEOUT] Payment {payment_id} MTC timeout after {total_wait_seconds}s")

                    payment.updated_on = datetime.now()
                    db.add(payment)
                    db.commit()
                    logger.warning(f"[PAYMENT_CHECK_UPDATED] Payment {payment_id} marked as failed due to timeout")

                    # Send notification for CTM timeout (no transaction ID case)
                    if payment.status == PaymentStatus.CTM_FAILED:
                        try:
                            from core.payments.service.paymentservice import PaymentService
                            payment_service = PaymentService(db)
                            payment_service.send_payment_notification(
                                payment,
                                is_success=False,
                                failure_reason="Payment request timed out. No money was deducted from your account."
                            )
                            logger.info(f"[PAYMENT_CHECK_CTM_TIMEOUT_NOTIFICATION] CTM timeout notification sent for payment {payment_id}")
                        except Exception as e:
                            logger.error(f"[PAYMENT_CHECK_CTM_TIMEOUT_NOTIFICATION_ERROR] Failed to send CTM timeout notification: {str(e)}", exc_info=True)

                    self._stop_check_job(payment_id)

            logger.info(f"[PAYMENT_CHECK_END] Status check completed for payment {payment_id} (Attempt {current_attempt}/{max_attempts})")

        except Exception as e:
            logger.error(f"[PAYMENT_CHECK_ERROR] Error checking payment status for payment {payment_id}: {str(e)}", exc_info=True)
            # Continue retrying on error unless max attempts reached
            current_attempt = PaymentCheckService._payment_attempt_counts.get(payment_id, 0)
            if current_attempt >= max_attempts:
                self._stop_check_job(payment_id)
        finally:
            db.close()

    def _stop_check_job(self, payment_id: int):
        """
        Stop the background job for a payment and clean up attempt counter.
        """
        try:
            job_id = f"payment_check_{payment_id}"
            if self.scheduler.get_job(job_id):
                self.scheduler.remove_job(job_id)
                logger.info(f"[PAYMENT_CHECK_JOB_REMOVED] Job {job_id} removed for payment {payment_id}")

            # Clean up attempt counter
            if payment_id in PaymentCheckService._payment_attempt_counts:
                del PaymentCheckService._payment_attempt_counts[payment_id]

        except Exception as e:
            logger.error(f"[PAYMENT_CHECK_JOB_REMOVE_ERROR] Error removing job for payment {payment_id}: {str(e)}", exc_info=True)

    def _query_orchard_transaction_status(self, transaction_id: str) -> str:
        """
        Query Orchard API to get transaction status using checkTransaction endpoint.

        Response format:
        {
          "trans_status": "000/01",
          "trans_ref": "031059294635",
          "trans_id": "21870173572",
          "message": "SUCCESSFUL"
        }

        Returns: "SUCCESS", "FAILED", or "PENDING"
        """
        try:
            logger.info(f"[ORCHARD_QUERY_START] Querying transaction status for: {transaction_id}")

            # Log request details
            logger.info(f"[ORCHARD_REQUEST] Endpoint: POST /checkTransaction")
            logger.info(f"[ORCHARD_REQUEST] Transaction ID to check: {transaction_id}")
            logger.debug(f"[ORCHARD_REQUEST] Using API Key: {self.payment_gateway_client.client_id[:20]}...")

            # Call Orchard API checkTransaction endpoint
            response = self.payment_gateway_client.check_transaction_status(transaction_id)

            logger.info(f"[ORCHARD_RESPONSE_HTTP] HTTP Status Code: {response.status_code}")
            logger.debug(f"[ORCHARD_RESPONSE_HEADERS] Response Headers: {dict(response.headers)}")

            if response.status_code == 200:
                # Parse response
                response_data = response.json()
                logger.info(f"[ORCHARD_RESPONSE_BODY] Raw Response: {response_data}")

                # Extract fields from response
                trans_status = response_data.get("trans_status")
                trans_ref = response_data.get("trans_ref")
                trans_id = response_data.get("trans_id")
                message = response_data.get("message")

                logger.info(f"[ORCHARD_RESPONSE_PARSED] trans_status: '{trans_status}'")
                logger.info(f"[ORCHARD_RESPONSE_PARSED] trans_ref: '{trans_ref}'")
                logger.info(f"[ORCHARD_RESPONSE_PARSED] trans_id: '{trans_id}'")
                logger.info(f"[ORCHARD_RESPONSE_PARSED] message: '{message}'")

                # Validate we have required fields
                if not trans_status:
                    logger.error(f"[ORCHARD_RESPONSE_MISSING_FIELD] Missing trans_status in response for transaction {transaction_id}")
                    logger.error(f"[ORCHARD_RESPONSE_DEBUG] Full response: {response_data}")
                    return "PENDING"

                # Extract first 3 digits from trans_status (e.g., "000" from "000/01")
                status_code = trans_status[:3] if len(trans_status) >= 3 else trans_status
                logger.info(f"[ORCHARD_STATUS_CODE_EXTRACTED] Extracted code: '{status_code}' from '{trans_status}'")

                # Determine result
                if status_code == "000":
                    logger.info(f"[ORCHARD_QUERY_SUCCESS] ✅ Transaction {transaction_id} is SUCCESS")
                    logger.info(f"[ORCHARD_DECISION] Result: SUCCESS - Status code 000 indicates successful transaction")
                    return "SUCCESS"
                elif status_code == "001":
                    logger.warning(f"[ORCHARD_QUERY_FAILED] ❌ Transaction {transaction_id} is FAILED")
                    logger.warning(f"[ORCHARD_DECISION] Result: FAILED - Status code 001 indicates transaction failure")
                    return "FAILED"
                else:
                    logger.warning(f"[ORCHARD_QUERY_UNKNOWN] ⚠️ Transaction {transaction_id} returned unknown status code: {status_code}")
                    logger.warning(f"[ORCHARD_DECISION] Result: PENDING - Unknown status code, will retry")
                    return "PENDING"
            else:
                logger.error(f"[ORCHARD_RESPONSE_HTTP_ERROR] ❌ API returned HTTP {response.status_code}")
                logger.error(f"[ORCHARD_RESPONSE_BODY_ERROR] Error Response: {response.text}")
                logger.error(f"[ORCHARD_DECISION] Result: PENDING - HTTP error, will retry")
                return "PENDING"

        except Exception as e:
            logger.error(f"[ORCHARD_QUERY_EXCEPTION] ❌ Exception querying Orchard API: {str(e)}", exc_info=True)
            logger.error(f"[ORCHARD_DECISION] Result: PENDING - Exception occurred, will retry")
            return "PENDING"

    @staticmethod
    def shutdown_scheduler():
        """Gracefully shutdown the background scheduler"""
        if PaymentCheckService._scheduler_instance and PaymentCheckService._scheduler_instance.running:
            PaymentCheckService._scheduler_instance.shutdown()
            logger.info("[SCHEDULER] Background scheduler shutdown")
