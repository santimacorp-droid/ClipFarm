"""
Posting relatedAPIRouter - refactored versionbilitoolDirect dependency, no transitive expansionAPICall
"""

import logging
import json
import os
import uuid
import time
import base64
import io
import aiohttp
import asyncio
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Body
from fastapi.responses import Response
from sqlalchemy.orm import Session
import qrcode

from ...core.database import get_db
from ...schemas.bilibili import (
    BilibiliAccountCreate, 
    BilibiliAccountResponse,
    UploadRequest,
    UploadRecordResponse,
    UploadStatusResponse,
    QRLoginRequest,
    QRLoginResponse
)
from ...services.bilibili_service import BilibiliAccountService, BilibiliUploadService
from ...tasks.upload import upload_clip_task

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/upload", tags=["Submission management"])

# Dictionary storing QR code login sessions
qr_sessions = {}

# Getting service instance
def get_account_service(db: Session = Depends(get_db)) -> BilibiliAccountService:
    return BilibiliAccountService(db)

def get_upload_service(db: Session = Depends(get_db)) -> BilibiliUploadService:
    return BilibiliUploadService(db)


# Account managementAPI
@router.get("/login-methods")
async def get_login_methods():
    """Getting supported login methods"""
    return {
        "methods": [
            {
                "id": "cookie",
                "name": "CookieImport",
                "description": "Most secure way, won't trigger anti-fraud system",
                "icon": "🔐",
                "recommended": True,
                "risk_level": "low"
            },
            {
                "id": "password",
                "name": "Account password login",
                "description": "Traditional login method, might require captcha",
                "icon": "👤",
                "recommended": True,
                "risk_level": "medium"
            },
            {
                "id": "qr",
                "name": "Scan login",
                "description": "UseBStationAPPScan login",
                "icon": "📱",
                "recommended": False,
                "risk_level": "high"
            },
            {
                "id": "wechat",
                "name": "WeChat login",
                "description": "Logging in with WeChat account",
                "icon": "💬",
                "recommended": False,
                "risk_level": "medium"
            },
            {
                "id": "qq",
                "name": "QQLogin",
                "description": "UseQQAccount login",
                "icon": "🐧",
                "recommended": False,
                "risk_level": "medium"
            }
        ]
    }


@router.post("/cookie-login", response_model=BilibiliAccountResponse)
async def cookie_login(
    request: dict = Body(...),
    account_service: BilibiliAccountService = Depends(get_account_service)
):
    """CookieImport login"""
    try:
        cookies = request.get("cookies")
        nickname = request.get("nickname")
        
        if not cookies:
            raise HTTPException(status_code=400, detail="CookieCannot be empty")
        
        # ValidateCookieValidity
        cookie_validation = await validate_bilibili_cookies(cookies)
        
        if cookie_validation.get("valid"):
            # BuildCookieString for storing
            cookie_str = "; ".join([f"{k}={v}" for k, v in cookies.items()])
            
            account_data = BilibiliAccountCreate(
                username=cookie_validation.get("username", "cookie_user"),
                password="",
                nickname=nickname or cookie_validation.get("nickname", "BSite user"),
                cookie_content=cookie_str
            )
            
            account = await account_service.create_account(account_data)
            return BilibiliAccountResponse.from_orm(account)
        else:
            raise HTTPException(status_code=400, detail="CookieInvalid or expired")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"CookieLogin failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Login failed")


@router.post("/password-login", response_model=BilibiliAccountResponse)
async def password_login(
    request: dict = Body(...),
    account_service: BilibiliAccountService = Depends(get_account_service)
):
    """Account password login"""
    try:
        username = request.get("username")
        password = request.get("password")
        nickname = request.get("nickname")
        
        if not username or not password:
            raise HTTPException(status_code=400, detail="Username and password cannot be empty")
        
        # Here should implement real password login logic
        # Currently returning mock data
        mock_cookie_data = {
            "code": 0,
            "message": "Login successful",
            "data": {
                "user_info": {
                    "username": username,
                    "nickname": nickname or username,
                    "mid": "12345678"
                },
                "cookie_info": {
                    "cookies": [{"name": "SESSDATA", "value": "mock_sessdata"}]
                }
            }
        }
        
        account_data = BilibiliAccountCreate(
            username=username,
            password=password,
            nickname=nickname or username,
            cookie_content=json.dumps(mock_cookie_data)
        )
        
        account = await account_service.create_account(account_data)
        return BilibiliAccountResponse.from_orm(account)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Password login failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Login failed")


@router.post("/qr-login")
async def start_qr_login(
    request: dict = Body(...),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """Starting QR code login"""
    try:
        nickname = request.get("nickname")
        
        # Generate sessionID
        session_id = str(uuid.uuid4())
        
        # Create session
        qr_sessions[session_id] = {
            "session_id": session_id,
            "status": "pending",
            "nickname": nickname,
            "created_at": time.time(),
            "qr_code": None,
            "error_message": None
        }
        
        # Starting background task to generate QR code
        background_tasks.add_task(generate_qr_code_async, session_id)
        
        return {
            "session_id": session_id,
            "status": "pending",
            "message": "Generating QR code......"
        }
        
    except Exception as e:
        logger.error(f"QR code login failed to start: {str(e)}")
        raise HTTPException(status_code=500, detail="Starting login failed")


@router.get("/qr-login/{session_id}")
async def check_qr_login_status(session_id: str):
    """Checking QR code login status"""
    try:
        if session_id not in qr_sessions:
            raise HTTPException(status_code=404, detail="Session does not exist")
        
        session = qr_sessions[session_id]
        
        return {
            "session_id": session_id,
            "status": session["status"],
            "message": session.get("error_message", "Waiting for scan..."),
            "qr_code": session.get("qr_code")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to check QR code login status: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to check login status")


@router.post("/qr-login/{session_id}/complete", response_model=BilibiliAccountResponse)
async def complete_qr_login(
    session_id: str,
    request: dict = Body(...),
    account_service: BilibiliAccountService = Depends(get_account_service)
):
    """QR code login completed"""
    try:
        if session_id not in qr_sessions:
            raise HTTPException(status_code=404, detail="Session does not exist")
        
        session = qr_sessions[session_id]
        
        if session["status"] != "success":
            raise HTTPException(status_code=400, detail="Login failed")
        
        nickname = request.get("nickname") or session.get("nickname")
        
        # Create simulatedCookieData
        mock_cookie_data = {
            "code": 0,
            "message": "Login successful",
            "data": {
                "user_info": {
                    "username": f"qr_user_{session_id[:8]}",
                    "nickname": nickname or "BSite user",
                    "mid": "87654321"
                },
                "cookie_info": {
                    "cookies": [{"name": "SESSDATA", "value": f"qr_sessdata_{session_id[:8]}"}]
                }
            }
        }
        
        account_data = BilibiliAccountCreate(
            username=f"qr_user_{session_id[:8]}",
            password="",
            nickname=nickname or "BSite user",
            cookie_content=json.dumps(mock_cookie_data)
        )
        
        account = await account_service.create_account(account_data)
        
        # Clear session
        del qr_sessions[session_id]
        
        return BilibiliAccountResponse.from_orm(account)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"QR code login failed to complete: {str(e)}")
        raise HTTPException(status_code=500, detail="Completed login failure")


@router.get("/accounts")
async def get_accounts(account_service: BilibiliAccountService = Depends(get_account_service)):
    """Get all accounts"""
    try:
        accounts = account_service.get_accounts()
        return [BilibiliAccountResponse.from_orm(account) for account in accounts]
    except Exception as e:
        logger.error(f"Failed to get account list: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get account list")


@router.delete("/accounts/{account_id}")
async def delete_account(
    account_id: UUID,
    account_service: BilibiliAccountService = Depends(get_account_service)
):
    """Delete account"""
    try:
        success = account_service.delete_account(account_id)
        if success:
            return {"message": "Account deleted successfully"}
        else:
            raise HTTPException(status_code=404, detail="Account does not exist")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete account: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete account")


@router.post("/accounts/{account_id}/check")
async def check_account_status(
    account_id: UUID,
    account_service: BilibiliAccountService = Depends(get_account_service)
):
    """Checking account status..."""
    try:
        is_valid = account_service.check_account_status(account_id)
        return {
            "is_valid": is_valid,
            "message": "Account status normal" if is_valid else "Account status abnormal"
        }
    except Exception as e:
        logger.error(f"Failed to check account status: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to check account status")


# Submission managementAPI
@router.post("/projects/{project_id}/upload")
async def create_upload_task(
    project_id: UUID,
    upload_data: UploadRequest,
    upload_service: BilibiliUploadService = Depends(get_upload_service)
):
    """Create submission task - function temporarily disabled"""
    # Function temporarily disabled, returns in-development message
    raise HTTPException(status_code=503, detail="BUploading feature is under development, please stay tuned! ")
    
    # Original code is disabled
    try:
        record = upload_service.create_upload_record(project_id, upload_data)
        
        # Starting async upload task
        for clip_id in upload_data.clip_ids:
            upload_clip_task.delay(str(record.id), clip_id)
        
        return {
            "message": "Submission task created successfully",
            "record_id": str(record.id),
            "clip_count": len(upload_data.clip_ids)
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create post task: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create post task")


@router.post("/records/{record_id}/retry")
async def retry_upload_task(
    record_id: int,
    upload_service: BilibiliUploadService = Depends(get_upload_service)
):
    """Retrying posting task"""
    try:
        success = upload_service.retry_upload_task(record_id)
        if success:
            return {"message": "Resubmission task restart initiated"}
        else:
            raise HTTPException(status_code=400, detail="Retry failed")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Resubmission of task failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Retry failed")


@router.post("/records/{record_id}/cancel")
async def cancel_upload_task(
    record_id: int,
    upload_service: BilibiliUploadService = Depends(get_upload_service)
):
    """Canceling article posting task"""
    try:
        success = upload_service.cancel_upload_task(record_id)
        if success:
            return {"message": "Post task cancelled"}
        else:
            raise HTTPException(status_code=400, detail="Cancel failed")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to cancel post task: {str(e)}")
        raise HTTPException(status_code=500, detail="Cancel failed")


@router.delete("/records/{record_id}")
async def delete_upload_task(
    record_id: int,
    upload_service: BilibiliUploadService = Depends(get_upload_service)
):
    """Delete posting task"""
    try:
        success = upload_service.delete_upload_task(record_id)
        if success:
            return {"message": "Post task deleted"}
        else:
            raise HTTPException(status_code=400, detail="Delete failed")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to delete post task: {str(e)}")
        raise HTTPException(status_code=500, detail="Delete failed")


@router.get("/records")
async def get_upload_records(
    project_id: Optional[UUID] = None,
    upload_service: BilibiliUploadService = Depends(get_upload_service)
):
    """Getting article records..."""
    try:
        records = upload_service.get_upload_records(project_id)
        return [UploadRecordResponse(**record) for record in records]
    except Exception as e:
        logger.error(f"Failed to get post records: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get post records")


@router.get("/records/{record_id}")
async def get_upload_record(
    record_id: UUID,
    upload_service: BilibiliUploadService = Depends(get_upload_service)
):
    """Getting specific post record"""
    try:
        record = upload_service.get_upload_record(record_id)
        if not record:
            raise HTTPException(status_code=404, detail="Post record does not exist")
        return UploadRecordResponse.from_orm(record)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get post records: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get post records")


# Helper function
async def validate_bilibili_cookies(cookies: dict) -> dict:
    """ValidateBStationCookieValidity"""
    try:
        # BuildCookieString
        cookie_str = "; ".join([f"{k}={v}" for k, v in cookies.items()])
        
        headers = {
            "Cookie": cookie_str,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://www.bilibili.com/"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://api.bilibili.com/x/web-interface/nav",
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                data = await response.json()
                
                if data.get("code") == 0 and data.get("data", {}).get("isLogin"):
                    user_info = data["data"]
                    
                    # Checking required fields
                    required_fields = ['SESSDATA', 'bili_jct', 'DedeUserID']
                    missing_fields = []
                    for field in required_fields:
                        if field not in cookies:
                            missing_fields.append(field)
                    
                    if missing_fields:
                        return {
                            "valid": False, 
                            "message": f"CookieMissing required fields: {', '.join(missing_fields)}"
                        }
                    
                    return {
                        "valid": True,
                        "username": user_info.get("uname"),
                        "nickname": user_info.get("uname"),
                        "mid": user_info.get("mid"),
                        "level": user_info.get("level_info", {}).get("current_level", 0),
                        "can_upload": True  # Temporarily set toTrue, Can add more detailed checks later
                    }
                else:
                    return {"valid": False, "message": "CookieInvalid or expired"}
                    
    except Exception as e:
        logger.error(f"ValidateCookieFailed: {e}")
        return {"valid": False, "message": f"Validation failed: {str(e)}"}


async def generate_qr_code_async(session_id: str):
    """Async QR code generation"""
    try:
        if session_id not in qr_sessions:
            return
        
        session = qr_sessions[session_id]
        
        # Simulating QR code generation process
        await asyncio.sleep(2)  # Simulating network delay...
        
        # Generating mock QR codeURL
        qr_url = f"https://passport.bilibili.com/qrcode/h5/login?qrcode_key={session_id}"
        
        session["qr_code"] = qr_url
        session["status"] = "processing"
        
        # Waiting for scan confirmation...
        await asyncio.sleep(30)  # Waiting30seconds
        
        # Simulated login successful
        if session_id in qr_sessions:
            qr_sessions[session_id]["status"] = "success"
            
    except Exception as e:
        if session_id in qr_sessions:
            qr_sessions[session_id]["status"] = "failed"
            qr_sessions[session_id]["error_message"] = str(e)
        logger.error(f"QR code generation failed: {e}")
