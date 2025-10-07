import random
import string
from datetime import datetime, timedelta, timezone
from typing import Optional
from sqlalchemy.orm import Session
from core.otp.model.otp import OTP
from core.otp.dto.response.otp_send_response import OTPSendResponse
from config import settings
import logging

logger = logging.getLogger(__name__)


class OTPService:
    def __init__(self, db: Session):
        self.db = db

    def generate_otp(self) -> str:
        """Generate a 5-digit OTP"""
        return ''.join(random.choices(string.digits, k=5))

    def send_otp_phone(self, phone: str) -> OTPSendResponse:
        """Send OTP to phone number"""
        try:
            otp_code = self.generate_otp()
            expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.OTP_EXPIRE_MINUTES)
            
            # Delete any existing OTP for this phone
            self.db.query(OTP).filter(OTP.phone == phone).delete()
            
            # Create new OTP record
            otp_record = OTP(
                phone=phone,
                otp=otp_code,
                expires_at=expires_at
            )
            
            self.db.add(otp_record)
            self.db.commit()
            self.db.refresh(otp_record)
            
            # TODO: Integrate with SMS service to actually send the OTP
            # For now, we'll just log it
            logger.info(f"OTP for {phone}: {otp_code}")
            
            return OTPSendResponse(
                success=True,
                message="OTP sent successfully to your phone",
                data={
                    "phone": phone,
                    "expires_at": expires_at.isoformat()
                }
            )
            
        except Exception as e:
            logger.error(f"Error sending OTP to phone {phone}: {str(e)}")
            return OTPSendResponse(
                success=False,
                message="Failed to send OTP. Please try again."
            )

    def send_otp_email(self, email: str) -> OTPSendResponse:
        """Send OTP to email address"""
        try:
            otp_code = self.generate_otp()
            expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.OTP_EXPIRE_MINUTES)
            
            # Delete any existing OTP for this email
            self.db.query(OTP).filter(OTP.email == email).delete()
            
            # Create new OTP record
            otp_record = OTP(
                email=email,
                otp=otp_code,
                expires_at=expires_at
            )
            
            self.db.add(otp_record)
            self.db.commit()
            self.db.refresh(otp_record)
            
            # TODO: Integrate with email service to actually send the OTP
            # For now, we'll just log it (remove this in production)
            logger.info(f"OTP for {email}: {otp_code}")
            
            return OTPSendResponse(
                success=True,
                message="OTP sent successfully to your email",
                data={
                    "email": email,
                    "expires_at": expires_at.isoformat()
                }
            )
            
        except Exception as e:
            logger.error(f"Error sending OTP to email {email}: {str(e)}")
            return OTPSendResponse(
                success=False,
                message="Failed to send OTP. Please try again."
            )

    def validate_otp(self, phone: Optional[str] = None, email: Optional[str] = None, otp: str = None) -> bool:
        """Validate OTP for phone or email"""
        try:
            if not otp:
                return False
            
            # Build query based on what's provided
            query = self.db.query(OTP).filter(OTP.otp == otp)
            
            if phone:
                query = query.filter(OTP.phone == phone)
            elif email:
                query = query.filter(OTP.email == email)
            else:
                return False
            
            otp_record = query.first()
            
            if not otp_record:
                return False
            
            # Check if OTP has expired
            if otp_record.is_expired():
                # Clean up expired OTP
                self.db.delete(otp_record)
                self.db.commit()
                return False
            
            # OTP is valid, delete it to prevent reuse
            self.db.delete(otp_record)
            self.db.commit()
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating OTP: {str(e)}")
            return False

    def cleanup_expired_otps(self):
        """Clean up expired OTP records"""
        try:
            current_time = datetime.now(timezone.utc)
            expired_count = self.db.query(OTP).filter(OTP.expires_at < current_time).delete()
            self.db.commit()
            logger.info(f"Cleaned up {expired_count} expired OTP records")
        except Exception as e:
            logger.error(f"Error cleaning up expired OTPs: {str(e)}")