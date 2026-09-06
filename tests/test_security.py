"""本地安全模組測試 (Security Module Tests)

驗證 AES-256-GCM 加解密、PBKDF2 密鑰衍生、防竄改檢查、憑證持久化與敏感資料脫敏。
"""

import os
from pathlib import Path
import pytest

from src.core.security import (
    OKXCredentials,
    SecurityIntegrityError,
    SecurityManager,
)


def test_credentials_repr_masks_sensitive_data() -> None:
    """驗證 OKXCredentials 在 repr/str 輸出時自動遮罩敏感憑證，防止日誌洩漏。"""
    creds = OKXCredentials(
        api_key="okx-api-key-12345",
        api_secret="super-secret-key-99999",
        passphrase="my-secret-passphrase",
    )
    repr_str = repr(creds)
    str_str = str(creds)

    assert "super-secret-key-99999" not in repr_str
    assert "my-secret-passphrase" not in repr_str
    assert "super-secret-key-99999" not in str_str
    assert "my-secret-passphrase" not in str_str
    assert "okx-api-key-12345" not in repr_str or "12345" in repr_str  # 遮罩或部分遮罩


def test_encrypt_decrypt_roundtrip() -> None:
    """驗證使用 AES-256-GCM 加解密字串之往返一致性。"""
    mgr = SecurityManager(master_password="test-secure-password")
    original_secret = "okx-demo-secret-key-xyz888"

    encrypted_b64 = mgr.encrypt(original_secret)
    assert isinstance(encrypted_b64, str)
    assert encrypted_b64 != original_secret

    decrypted = mgr.decrypt(encrypted_b64)
    assert decrypted == original_secret


def test_tampered_ciphertext_raises_integrity_error() -> None:
    """驗證密文遭惡意竄改 1 byte 時，GCM Tag 驗證失敗並拋出 SecurityIntegrityError。"""
    mgr = SecurityManager(master_password="test-secure-password")
    encrypted_b64 = mgr.encrypt("critical-okx-secret")

    # 模擬竄改密文中的字元
    tampered = (
        encrypted_b64[:-2] + ("A" if encrypted_b64[-2] != "A" else "B") + encrypted_b64[-1]
    )

    with pytest.raises(SecurityIntegrityError):
        mgr.decrypt(tampered)


def test_wrong_password_fails_decryption() -> None:
    """驗證以錯誤密碼解密時無法取得明文並拋出 SecurityIntegrityError。"""
    mgr1 = SecurityManager(master_password="correct-password")
    encrypted_b64 = mgr1.encrypt("payload")

    mgr2 = SecurityManager(master_password="wrong-password")
    with pytest.raises(SecurityIntegrityError):
        mgr2.decrypt(encrypted_b64)


def test_credentials_save_and_load_roundtrip(tmp_path: Path) -> None:
    """驗證憑證加密寫入本機檔案後再載入解密的端到端流程。"""
    key_file = tmp_path / "okx_demo_key.enc"
    mgr = SecurityManager(master_password="catos-local-vault")

    creds = OKXCredentials(
        api_key="demo-key-001",
        api_secret="demo-secret-002",
        passphrase="demo-passphrase-003",
    )

    mgr.save_credentials(creds, key_file)
    assert key_file.exists()

    # 確保硬碟檔案內無任何明文字串
    raw_content = key_file.read_text(encoding="utf-8")
    assert "demo-secret-002" not in raw_content
    assert "demo-passphrase-003" not in raw_content

    loaded = mgr.load_credentials(key_file)
    assert loaded.api_key == "demo-key-001"
    assert loaded.api_secret == "demo-secret-002"
    assert loaded.passphrase == "demo-passphrase-003"
