from typing import Dict, List, Optional, Tuple
import asyncio
import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import select

from ..core.database import get_db
from ..models.bilibili import BilibiliAccount
from ..utils.crypto import decrypt_data, encrypt_data
from ..core.celery_app import celery_app

logger = logging.getLogger(__name__)

class AccountHealthStatus:
    """Account health status enumeration"""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    EXPIRED = "expired"
    UNKNOWN = "unknown"

class AccountHealthService:
    """Account health check service"""
    
    def __init__(self):
        self.check_interval = 300  # 5Checked once per minute
        self.cookie_expire_days = 30  # CookieExpiry days
        self.warning_days = 7  # Warning days in advance
        
    async def check_account_health(self, account_id: int) -> Dict:
        """Check single account health status"""
        try:
            db = next(get_db())
            account = db.query(BilibiliAccount).filter(BilibiliAccount.id == account_id).first()
            
            if not account:
                return {
                    "account_id": account_id,
                    "status": AccountHealthStatus.UNKNOWN,
                    "message": "Account not found",
                    "last_check": datetime.now()
                }
            
            # Check validity of Cookie
            cookie_status = await self._check_cookie_validity(account)
            
            # Check login status
            login_status = await self._check_login_status(account)
            
            # Check upload permissions
            upload_status = await self._check_upload_permission(account)
            
            # Perform comprehensive health assessment
            overall_status = self._evaluate_overall_status(
                cookie_status, login_status, upload_status
            )
            
            # Update account status
            account.health_status = overall_status["status"]
            account.last_health_check = datetime.now()
            account.health_details = {
                "cookie": cookie_status,
                "login": login_status,
                "upload": upload_status,
                "last_check": datetime.now().isoformat()
            }
            
            db.commit()
            
            return {
                "account_id": account_id,
                "username": account.username,
                "status": overall_status["status"],
                "message": overall_status["message"],
                "details": {
                    "cookie": cookie_status,
                    "login": login_status,
                    "upload": upload_status
                },
                "last_check": datetime.now()
            }
            
        except Exception as e:
            logger.error(f"Check account {account_id} Health state failed: {str(e)}")
            return {
                "account_id": account_id,
                "status": AccountHealthStatus.UNKNOWN,
                "message": f"Check failed: {str(e)}",
                "last_check": datetime.now()
            }
    
    async def _check_cookie_validity(self, account: BilibiliAccount) -> Dict:
        """Check validity of Cookie"""
        try:
            if not account.cookies:
                return {
                    "status": AccountHealthStatus.CRITICAL,
                    "message": "CookieEmpty",
                    "expires_in": None
                }
            
            # Decrypt Cookie
            try:
                cookies = decrypt_data(account.cookies)
            except Exception as e:
                return {
                    "status": AccountHealthStatus.CRITICAL,
                    "message": f"CookieDecryption failed: {str(e)}",
                    "expires_in": None
                }
            
            # Check Cookie format and required fields
            required_fields = ['SESSDATA', 'bili_jct', 'DedeUserID']
            missing_fields = []
            
            for field in required_fields:
                if field not in cookies:
                    missing_fields.append(field)
            
            if missing_fields:
                return {
                    "status": AccountHealthStatus.CRITICAL,
                    "message": f"CookieMissing required fields: {', '.join(missing_fields)}",
                    "expires_in": None
                }
            
            # Check whether Cookie has expired
            if account.cookie_expires_at:
                now = datetime.now()
                expires_in = (account.cookie_expires_at - now).days
                
                if expires_in <= 0:
                    return {
                        "status": AccountHealthStatus.EXPIRED,
                        "message": "CookieExpired",
                        "expires_in": expires_in
                    }
                elif expires_in <= self.warning_days:
                    return {
                        "status": AccountHealthStatus.WARNING,
                        "message": f"CookieWill expire in {expires_in} days later expired",
                        "expires_in": expires_in
                    }
                else:
                    return {
                        "status": AccountHealthStatus.HEALTHY,
                        "message": "CookieValid",
                        "expires_in": expires_in
                    }
            
            return {
                "status": AccountHealthStatus.HEALTHY,
                "message": "CookieCorrect format",
                "expires_in": None
            }
            
        except Exception as e:
            logger.error(f"Check validity of CookieFailed: {str(e)}")
            return {
                "status": AccountHealthStatus.UNKNOWN,
                "message": f"Check failed: {str(e)}",
                "expires_in": None
            }
    
    async def _check_login_status(self, account: BilibiliAccount) -> Dict:
        """Check login status"""
        try:
            import aiohttp
            
            if not account.cookies:
                return {
                    "status": AccountHealthStatus.CRITICAL,
                    "message": "No Cookie information available"
                }
            
            # Decrypt Cookie
            cookies = decrypt_data(account.cookies)
            
            # Build Cookie string
            cookie_str = '; '.join([f"{k}={v}" for k, v in cookies.items()])
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Cookie': cookie_str,
                'Referer': 'https://www.bilibili.com/'
            }
            
            # Check login status
            async with aiohttp.ClientSession() as session:
                async with session.get('https://api.bilibili.com/x/web-interface/nav', headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('code') == 0:
                            user_info = data.get('data', {})
                            if user_info.get('isLogin'):
                                return {
                                    "status": AccountHealthStatus.HEALTHY,
                                    "message": "Login status: valid",
                                    "user_info": {
                                        "uname": user_info.get('uname'),
                                        "mid": user_info.get('mid'),
                                        "level": user_info.get('level_info', {}).get('current_level')
                                    }
                                }
                            else:
                                return {
                                    "status": AccountHealthStatus.CRITICAL,
                                    "message": "Not logged in"
                                }
                        else:
                            return {
                                "status": AccountHealthStatus.CRITICAL,
                                "message": f"APIReturn error: {data.get('message')}"
                            }
                    else:
                        return {
                            "status": AccountHealthStatus.CRITICAL,
                            "message": f"Request failed: HTTP {response.status}"
                        }
            
        except Exception as e:
            logger.error(f"Check login statusFailed: {str(e)}")
            return {
                "status": AccountHealthStatus.UNKNOWN,
                "message": f"Check failed: {str(e)}"
            }
    
    async def _check_upload_permission(self, account: BilibiliAccount) -> Dict:
        """Check upload permissions"""
        try:
            import aiohttp
            
            if not account.cookies:
                return {
                    "status": AccountHealthStatus.CRITICAL,
                    "message": "No Cookie information available"
                }
            
            # Decrypt Cookie
            cookies = decrypt_data(account.cookies)
            
            # Build Cookie string
            cookie_str = '; '.join([f"{k}={v}" for k, v in cookies.items()])
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Cookie': cookie_str,
                'Referer': 'https://member.bilibili.com/'
            }
            
            # Check upload permissions
            async with aiohttp.ClientSession() as session:
                async with session.get('https://member.bilibili.com/x/web/archive/pre', headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('code') == 0:
                            return {
                                "status": AccountHealthStatus.HEALTHY,
                                "message": "Has upload permission"
                            }
                        elif data.get('code') == -101:
                            return {
                                "status": AccountHealthStatus.CRITICAL,
                                "message": "Account not logged in or Cookie expired"
                            }
                        else:
                            return {
                                "status": AccountHealthStatus.WARNING,
                                "message": f"Upload permission restricted: {data.get('message')}"
                            }
                    else:
                        return {
                            "status": AccountHealthStatus.WARNING,
                            "message": f"Unable toCheck upload permissions: HTTP {response.status}"
                        }
            
        except Exception as e:
            logger.error(f"Check upload permissionsFailed: {str(e)}")
            return {
                "status": AccountHealthStatus.UNKNOWN,
                "message": f"Check failed: {str(e)}"
            }
    
    def _evaluate_overall_status(self, cookie_status: Dict, login_status: Dict, upload_status: Dict) -> Dict:
        """Perform comprehensive account health assessment"""
        statuses = [cookie_status["status"], login_status["status"], upload_status["status"]]
        messages = []
        
        # Collect all issues
        if cookie_status["status"] != AccountHealthStatus.HEALTHY:
            messages.append(f"Cookie: {cookie_status['message']}")
        if login_status["status"] != AccountHealthStatus.HEALTHY:
            messages.append(f"Login: {login_status['message']}")
        if upload_status["status"] != AccountHealthStatus.HEALTHY:
            messages.append(f"Upload: {upload_status['message']}")
        
        # Determine overall status
        if AccountHealthStatus.CRITICAL in statuses or AccountHealthStatus.EXPIRED in statuses:
            overall_status = AccountHealthStatus.CRITICAL
        elif AccountHealthStatus.WARNING in statuses:
            overall_status = AccountHealthStatus.WARNING
        elif AccountHealthStatus.UNKNOWN in statuses:
            overall_status = AccountHealthStatus.WARNING
        else:
            overall_status = AccountHealthStatus.HEALTHY
        
        if messages:
            message = "; ".join(messages)
        else:
            message = "Account status: normal"
        
        return {
            "status": overall_status,
            "message": message
        }
    
    async def check_all_accounts(self) -> List[Dict]:
        """Check health status of all accounts"""
        try:
            db = next(get_db())
            accounts = db.query(BilibiliAccount).filter(BilibiliAccount.is_active == True).all()
            
            results = []
            for account in accounts:
                result = await self.check_account_health(account.id)
                results.append(result)
            
            return results
            
        except Exception as e:
            logger.error(f"BulkCheck accountHealth state failed: {str(e)}")
            return []
    
    async def auto_refresh_cookies(self, account_id: int) -> Dict:
        """Auto-refreshCookie"""
        try:
            db = next(get_db())
            account = db.query(BilibiliAccount).filter(BilibiliAccount.id == account_id).first()
            
            if not account:
                return {
                    "success": False,
                    "message": "Account not found"
                }
            
            # Implement Auto-refreshCookie logic here
            # For example via QR code login, SMS verification, etc.
            # Currently returns a prompt message
            
            return {
                "success": False,
                "message": "Auto-refreshCookie feature not implemented yet, please update Cookie manually",
                "account_id": account_id,
                "username": account.username
            }
            
        except Exception as e:
            logger.error(f"Auto-refreshCookieFailed: {str(e)}")
            return {
                "success": False,
                "message": f"Refreshing failed: {str(e)}"
            }

# Global service instance
health_service = AccountHealthService()

# Celery task
@celery_app.task(name="check_account_health")
def check_account_health_task(account_id: int):
    """Celery task to check account health status"""
    import asyncio
    
    async def run_check():
        return await health_service.check_account_health(account_id)
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(run_check())
        return result
    finally:
        loop.close()

@celery_app.task(name="check_all_accounts_health")
def check_all_accounts_health_task():
    """Celery task to batch check health status of all accounts"""
    import asyncio
    
    async def run_check():
        return await health_service.check_all_accounts()
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(run_check())
        return result
    finally:
        loop.close()

@celery_app.task(name="auto_refresh_cookies")
def auto_refresh_cookies_task(account_id: int):
    """Auto-refreshCookie Celery task"""
    import asyncio
    
    async def run_refresh():
        return await health_service.auto_refresh_cookies(account_id)
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(run_refresh())
        return result
    finally:
        loop.close()