"""
RSA加密解密工具
用于密码等敏感数据的加密传输
每次启动时生成新的密钥对
"""
import base64
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.backends import default_backend


class RSACrypto:
    """RSA加密解密类"""
    
    def __init__(self):
        self._private_key = None
        self._public_key = None
        self._generate_keys()
    
    def _generate_keys(self):
        """生成RSA密钥对（每次启动都生成新的）"""
        self._private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        self._public_key = self._private_key.public_key()
        print("✅ RSA密钥对已生成")
    
    def get_public_key(self) -> str:
        """获取公钥（PEM格式字符串）"""
        public_pem = self._public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        return public_pem.decode('utf-8')
    
    def decrypt(self, encrypted_data: str) -> str:
        """解密数据
        
        Args:
            encrypted_data: Base64编码的加密数据
        
        Returns:
            解密后的明文
        """
        try:
            # Base64解码
            encrypted_bytes = base64.b64decode(encrypted_data)
            
            # RSA解密
            decrypted_bytes = self._private_key.decrypt(
                encrypted_bytes,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None
                )
            )
            
            return decrypted_bytes.decode('utf-8')
        except Exception as e:
            raise ValueError(f"解密失败: {str(e)}")


# 全局实例
rsa_crypto = RSACrypto()

