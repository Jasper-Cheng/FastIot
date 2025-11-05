"""
微信登录服务
"""
import uuid
import time
import httpx
from typing import Dict, Optional
from datetime import datetime, timedelta
from app.core.config import settings

# 二维码状态枚举
class QRCodeStatus:
    WAITING = "waiting"  # 等待扫码
    SCANNED = "scanned"  # 已扫码，等待确认
    CONFIRMED = "confirmed"  # 已确认登录
    EXPIRED = "expired"  # 已过期
    CANCELLED = "cancelled"  # 已取消


class WeChatService:
    """微信登录服务类"""
    
    def __init__(self):
        self.qrcode_storage: Dict[str, Dict] = {}  # 存储二维码状态：{scene_id: {status, openid, expires_at, ...}}
        self.scene_to_openid: Dict[str, str] = {}  # scene_id -> openid 映射
        self.qrcode_expire_seconds = 300  # 二维码5分钟过期
        self.confirmed_retention_seconds = 3600  # 已确认的二维码保留1小时后清理
        
    async def get_access_token(self) -> Optional[str]:
        """获取微信access_token"""
        if not settings.WECHAT_APP_ID or not settings.WECHAT_APP_SECRET:
            raise ValueError("微信AppID和AppSecret未配置")
        
        url = "https://api.weixin.qq.com/cgi-bin/token"
        params = {
            "grant_type": "client_credential",
            "appid": settings.WECHAT_APP_ID,
            "secret": settings.WECHAT_APP_SECRET
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params, timeout=10.0)
                data = response.json()
                
                if "access_token" in data:
                    return data["access_token"]
                else:
                    print(f"获取access_token失败: {data}")
                    return None
        except Exception as e:
            print(f"获取access_token异常: {e}")
            return None
    
    async def create_qrcode(self) -> Dict[str, str]:
        """创建微信登录二维码
        
        使用微信网页授权方式，生成授权URL并转换为二维码。
        返回:
            {
                "qrcode_url": "二维码图片URL（需要客户端转换为二维码图片）",
                "scene_id": "场景ID，用于轮询状态"
            }
        """
        from app.core.config import settings
        
        if not settings.WECHAT_APP_ID:
            raise ValueError("微信AppID未配置")
        
        if not settings.WECHAT_REDIRECT_URI:
            raise ValueError("微信回调地址未配置")
        
        # 生成唯一的scene_id
        scene_id = str(uuid.uuid4())
        
        # 构建微信网页授权URL
        # 将scene_id作为state参数传递
        import urllib.parse
        redirect_uri = urllib.parse.quote(settings.WECHAT_REDIRECT_URI, safe='')
        auth_url = (
            f"https://open.weixin.qq.com/connect/oauth2/authorize?"
            f"appid={settings.WECHAT_APP_ID}&"
            f"redirect_uri={redirect_uri}&"
            f"response_type=code&"
            f"scope=snsapi_userinfo&"
            f"state={scene_id}"
            f"#wechat_redirect"
        )
        
        # 存储二维码状态
        self.qrcode_storage[scene_id] = {
            "status": QRCodeStatus.WAITING,
            "auth_url": auth_url,
            "qrcode_url": auth_url,  # 授权URL就是二维码内容
            "created_at": datetime.now(),
            "expires_at": datetime.now() + timedelta(seconds=self.qrcode_expire_seconds),
            "openid": None,
            "user_info": None
        }
        
        # 创建二维码时触发一次清理（惰性清理）
        self.cleanup_expired_qrcodes()
        
        return {
            "qrcode_url": auth_url,  # 返回授权URL，客户端需要将其转换为二维码图片
            "scene_id": scene_id
        }
    
    def get_qrcode_status(self, scene_id: str) -> Dict:
        """获取二维码状态
        
        返回:
            {
                "status": "waiting|scanned|confirmed|expired|cancelled",
                "openid": "微信openid（如果已确认）",
                "user_info": "用户信息（如果已确认）"
            }
        """
        if scene_id not in self.qrcode_storage:
            return {
                "status": QRCodeStatus.EXPIRED,
                "message": "二维码不存在或已过期"
            }
        
        qrcode_info = self.qrcode_storage[scene_id]
        
        # 检查是否过期
        if datetime.now() > qrcode_info["expires_at"]:
            qrcode_info["status"] = QRCodeStatus.EXPIRED
            return {
                "status": QRCodeStatus.EXPIRED,
                "message": "二维码已过期"
            }
        
        status = qrcode_info["status"]
        result = {
            "status": status
        }
        
        if status == QRCodeStatus.CONFIRMED:
            result["openid"] = qrcode_info.get("openid")
            result["user_info"] = qrcode_info.get("user_info")
        
        return result
    
    async def handle_wechat_callback(self, scene_id: str, openid: str, user_info: Optional[Dict] = None) -> bool:
        """处理微信回调
        
        Args:
            scene_id: 场景ID
            openid: 微信openid
            user_info: 用户信息（可选）
        
        Returns:
            bool: 是否处理成功
        """
        if scene_id not in self.qrcode_storage:
            return False
        
        qrcode_info = self.qrcode_storage[scene_id]
        
        # 检查是否过期
        if datetime.now() > qrcode_info["expires_at"]:
            qrcode_info["status"] = QRCodeStatus.EXPIRED
            return False
        
        # 更新状态
        qrcode_info["status"] = QRCodeStatus.CONFIRMED
        qrcode_info["openid"] = openid
        qrcode_info["user_info"] = user_info or {}
        qrcode_info["confirmed_at"] = datetime.now()
        
        # 存储映射关系
        self.scene_to_openid[scene_id] = openid
        
        return True
    
    async def get_user_info_by_openid(self, openid: str, access_token: Optional[str] = None, use_sns: bool = False) -> Optional[Dict]:
        """根据openid获取用户信息
        
        Args:
            openid: 微信openid
            access_token: access_token（如果为None则使用基础接口token）
            use_sns: 是否使用网页授权接口（sns/userinfo），True表示使用网页授权token
        """
        if not access_token:
            access_token = await self.get_access_token()
            if not access_token:
                return None
        
        # 根据use_sns参数选择不同的接口
        if use_sns:
            # 使用网页授权接口
            url = "https://api.weixin.qq.com/sns/userinfo"
            params = {
                "access_token": access_token,
                "openid": openid,
                "lang": "zh_CN"
            }
        else:
            # 使用基础接口
            url = "https://api.weixin.qq.com/cgi-bin/user/info"
            params = {
                "access_token": access_token,
                "openid": openid,
                "lang": "zh_CN"
            }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params, timeout=10.0)
                data = response.json()
                
                if "openid" in data:
                    return data
                else:
                    print(f"获取用户信息失败: {data}")
                    return None
        except Exception as e:
            print(f"获取用户信息异常: {e}")
            return None
    
    def cleanup_expired_qrcodes(self):
        """清理过期的二维码
        
        清理规则：
        1. 已过期且未确认的二维码：立即删除
        2. 已确认但超过保留时间的二维码：删除
        3. 已过期但已确认的二维码：如果超过保留时间则删除
        """
        now = datetime.now()
        to_delete = []
        
        for scene_id, info in self.qrcode_storage.items():
            status = info.get("status")
            expires_at = info.get("expires_at")
            
            # 情况1: 已过期且未确认的二维码，立即删除
            if now > expires_at and status != QRCodeStatus.CONFIRMED:
                to_delete.append(scene_id)
                continue
            
            # 情况2: 已确认的二维码，检查是否超过保留时间
            if status == QRCodeStatus.CONFIRMED:
                confirmed_at = info.get("confirmed_at")
                if confirmed_at:
                    retention_time = confirmed_at + timedelta(seconds=self.confirmed_retention_seconds)
                    if now > retention_time:
                        to_delete.append(scene_id)
                else:
                    # 如果没有确认时间，但已过期，检查是否超过过期时间+保留时间
                    if now > expires_at + timedelta(seconds=self.confirmed_retention_seconds):
                        to_delete.append(scene_id)
        
        # 执行删除
        deleted_count = 0
        for scene_id in to_delete:
            if scene_id in self.qrcode_storage:
                del self.qrcode_storage[scene_id]
                deleted_count += 1
            if scene_id in self.scene_to_openid:
                del self.scene_to_openid[scene_id]
        
        return deleted_count


# 全局实例
wechat_service = WeChatService()

