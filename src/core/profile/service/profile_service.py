import secrets
import string
from fastapi import HTTPException
from sqlalchemy.orm import Session
from core.user.model.User import User
from core.profile.model.Profile import Profile
from core.exceptions import *
from core.profile.dto.request.profileupdate import ProfileUpdateRequest
from core.profile.dto.response.profile_response import ProfileResponse
from core.user.dto.response.message_response import MessageResponse
from typing import Optional
from datetime import datetime

class ProfileService:
    def __init__(self, db: Session):
        self.db = db

    def get_user_profile(self, email: str) -> ProfileResponse:
        """Get profile information for the current user"""
        user = self.db.query(User).filter(User.email == email).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        if not user.profile:
            raise HTTPException(status_code=404, detail="Profile information not found for this user")
            
        return self._profile_to_response(user.profile)

    def update_user_profile(self, email: str, profile_data: ProfileUpdateRequest) -> ProfileResponse:
        """Update profile information for the current user"""
        user = self.db.query(User).filter(User.email == email).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        if not user.profile:
            # Create new profile if it doesn't exist
            profile = Profile(
                id=self._generate_profile_id(),
                user_id=user.id,
                **profile_data.dict(exclude_unset=True)
            )
            self.db.add(profile)
        else:
            # Update existing profile
            profile = user.profile
            for field, value in profile_data.dict(exclude_unset=True).items():
                setattr(profile, field, value)
            profile.updated_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(profile)
        return self._profile_to_response(profile)

    def get_profile_by_user_id(self, user_id: str) -> ProfileResponse:
        """Get profile information by user ID"""
        profile = self._get_profile_by_user_id(user_id)
        if not profile:
            raise HTTPException(status_code=404, detail="Profile information not found")
        return self._profile_to_response(profile)

    def update_profile_by_user_id(self, user_id: str, profile_data: ProfileUpdateRequest) -> ProfileResponse:
        """Update profile information by user ID"""
        profile = self._get_profile_by_user_id(user_id)
        if not profile:
            raise HTTPException(status_code=404, detail="Profile information not found")
            
        for field, value in profile_data.dict(exclude_unset=True).items():
            setattr(profile, field, value)
        profile.updated_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(profile)
        return self._profile_to_response(profile)

    def _get_profile_by_user_id(self, user_id: str) -> Optional[Profile]:
        """Internal method to get profile entity by user ID"""
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return None
        return user.profile

    def _profile_to_response(self, profile: Profile) -> ProfileResponse:
        """Convert Profile model to ProfileResponse DTO"""
        return ProfileResponse(
            id=profile.id,
            user_id=profile.user_id,
            name=profile.name,
            description=profile.description,
            category=profile.category,
            website=profile.website,
            address=profile.address,
            city=profile.city,
            state=profile.state,
            country=profile.country,
            postal_code=profile.postal_code,
            tax_id=profile.tax_id,
            registration_number=profile.registration_number,
            established_date=profile.established_date,
            created_at=profile.created_at,
            updated_at=profile.updated_at
        )

    def _generate_profile_id(self) -> str:
        """Generate a unique profile ID"""
        alphabet = string.ascii_letters + string.digits
        return "".join(secrets.choice(alphabet) for i in range(16))