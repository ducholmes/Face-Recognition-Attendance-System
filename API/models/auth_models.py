from pydantic import BaseModel, EmailStr, Field, validator
from typing import Literal, Optional


# Request Models

class RegisterRequest(BaseModel):
    """Request model for user registration with role assignment."""
    email: EmailStr
    password: str = Field(..., min_length=8)
    role: Literal['admin', 'teacher', 'student']


class LoginRequest(BaseModel):
    """Request model for user login."""
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    """Request model for token refresh."""
    refresh_token: str


class UpdateRoleRequest(BaseModel):
    """Request model for updating user role (admin only)."""
    user_id: str
    new_role: Literal['admin', 'teacher', 'student']


# Response Models

class UserInfo(BaseModel):
    """User information included in responses."""
    id: str
    email: str
    role: str


class RegisterResponse(BaseModel):
    """Response model for successful registration."""
    success: bool
    message: str
    user: UserInfo


class LoginResponse(BaseModel):
    """Response model for successful login."""
    success: bool
    message: str
    access_token: str
    refresh_token: str
    user: UserInfo


class RefreshResponse(BaseModel):
    """Response model for successful token refresh."""
    success: bool
    access_token: str
    refresh_token: str


class LogoutResponse(BaseModel):
    """Response model for logout."""
    success: bool
    message: str


class UserProfileResponse(BaseModel):
    """Response model for user profile information."""
    id: str
    email: str
    role: str
    created_at: str
    updated_at: Optional[str] = None


class ErrorResponse(BaseModel):
    """Standard error response format."""
    success: bool = False
    error: str
    detail: Optional[str] = None
    error_code: Optional[str] = None


class RegisterAuthRequest(BaseModel):
    """Legacy registration request model (deprecated)."""
    email: EmailStr
    password: str
    role: str