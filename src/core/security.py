"""本地金鑰安全模組 (Security Module)

負責 OKX 模擬盤 API 金鑰的 AES-256-GCM 認證加密、PBKDF2 密鑰衍生、
防竄改驗證、本機持久化與敏感憑證脫敏保護。
嚴格杜絕明文金鑰寫入日誌或對外洩漏。
"""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from pydantic import BaseModel, Field


class SecurityIntegrityError(Exception):
    """安全完整性檢驗失敗異常（密文遭竄改、密碼錯誤或格式破損）。"""


class OKXCredentials(BaseModel):
    """OKX 模擬盤身分驗證憑證模型。

    具備敏感欄位遮罩，嚴防於日誌或字串輸出時暴露明文密鑰。
    """

    api_key: str = Field(..., description="OKX 模擬盤 API Key")
    api_secret: str = Field(..., description="OKX 模擬盤 Secret Key")
    passphrase: str = Field(..., description="OKX 模擬盤 Passphrase")

    def __repr__(self) -> str:
        masked_key = (
            f"{self.api_key[:4]}***{self.api_key[-4:]}"
            if len(self.api_key) >= 8
            else "***"
        )
        return (
            f"OKXCredentials(api_key='{masked_key}', "
            f"api_secret='******', passphrase='******')"
        )

    def __str__(self) -> str:
        return self.__repr__()


class SecurityManager:
    """本地 AES-256-GCM 安全管理器。"""

    PBKDF2_ITERATIONS = 100_000
    SALT_SIZE = 16  # bytes
    NONCE_SIZE = 12  # bytes
    KEY_SIZE = 32  # 256 bits

    def __init__(self, master_password: str | None = None) -> None:
        """初始化安全管理器。

        :param master_password: 本地金鑰衍生密碼，若未指定則使用本機預設種子。
        """
        self._master_password = master_password or "catOS_v1_LocalVault_DefaultSeed_2026"

    def _derive_key(self, salt: bytes) -> bytes:
        """依據主密碼與鹽值透過 PBKDF2-HMAC-SHA256 衍生出 256-bit 對稱金鑰。"""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=self.KEY_SIZE,
            salt=salt,
            iterations=self.PBKDF2_ITERATIONS,
        )
        return kdf.derive(self._master_password.encode("utf-8"))

    def encrypt(self, plaintext: str) -> str:
        """使用 AES-256-GCM 加密明文字串。

        輸出格式為：Base64(Salt[16] + Nonce[12] + Ciphertext + Tag[16])
        """
        salt = os.urandom(self.SALT_SIZE)
        nonce = os.urandom(self.NONCE_SIZE)
        key = self._derive_key(salt)

        aesgcm = AESGCM(key)
        ciphertext_and_tag = aesgcm.encrypt(
            nonce, plaintext.encode("utf-8"), associated_data=None
        )

        packed = salt + nonce + ciphertext_and_tag
        return base64.b64encode(packed).decode("utf-8")

    def decrypt(self, ciphertext_b64: str) -> str:
        """解密並驗證 Base64 編碼的 AES-256-GCM 密文。

        若密文遭到竄改或解密金鑰不符，拋出 SecurityIntegrityError。
        """
        try:
            packed = base64.b64decode(ciphertext_b64.encode("utf-8"))
        except Exception as e:
            raise SecurityIntegrityError("密文格式無效，無法進行 Base64 解碼。") from e

        min_len = self.SALT_SIZE + self.NONCE_SIZE + 16  # 最小長度含 tag 16 bytes
        if len(packed) < min_len:
            raise SecurityIntegrityError("密文長度不足，資料已損毀。")

        salt = packed[: self.SALT_SIZE]
        nonce = packed[self.SALT_SIZE : self.SALT_SIZE + self.NONCE_SIZE]
        ciphertext_and_tag = packed[self.SALT_SIZE + self.NONCE_SIZE :]

        key = self._derive_key(salt)
        aesgcm = AESGCM(key)

        try:
            decrypted_bytes = aesgcm.decrypt(
                nonce, ciphertext_and_tag, associated_data=None
            )
            return decrypted_bytes.decode("utf-8")
        except InvalidTag as e:
            raise SecurityIntegrityError(
                "憑證資料完整性校驗失敗（密文已被竄改或主密碼不正確）。"
            ) from e
        except Exception as e:
            raise SecurityIntegrityError(f"解密過程發生未預期錯誤: {e}") from e

    def save_credentials(
        self, credentials: OKXCredentials, filepath: Path | str
    ) -> None:
        """將憑證模型加密並保存至指定檔案。"""
        target_path = Path(filepath)
        target_path.parent.mkdir(parents=True, exist_ok=True)

        payload_json = json.dumps(
            {
                "api_key": credentials.api_key,
                "api_secret": credentials.api_secret,
                "passphrase": credentials.passphrase,
            }
        )
        encrypted = self.encrypt(payload_json)
        target_path.write_text(encrypted, encoding="utf-8")

    def load_credentials(self, filepath: Path | str) -> OKXCredentials:
        """從指定加密檔案讀取並解密憑證模型。"""
        target_path = Path(filepath)
        if not target_path.exists():
            raise FileNotFoundError(f"憑證檔案不存在: {target_path}")

        encrypted = target_path.read_text(encoding="utf-8")
        decrypted_json = self.decrypt(encrypted)

        try:
            data = json.loads(decrypted_json)
            return OKXCredentials(
                api_key=data["api_key"],
                api_secret=data["api_secret"],
                passphrase=data["passphrase"],
            )
        except Exception as e:
            raise SecurityIntegrityError("憑證資料結構異常，無法解析憑證。") from e
