"""
ไฟล์กำหนดค่าสำหรับระบบ PawLove Flask Application
"""

import os

class Config:
    # รหัสลับสำหรับ Session และ Flash messages
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'pawlove-secret-key-2026-safe-secure'
    
    # โฟลเดอร์อัปโหลดไฟล์รูปภาพสัตว์
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
    MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # ปรับเพิ่มขนาดไฟล์รูปภาพสัตว์ที่อัปโหลดได้สูงสุดเป็น 100 MB
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

    # การตั้งค่าระบบส่งอีเมล (Email / SMTP)
    # โหลดค่าจากไฟล์ .env อัตโนมัติ (หากมี) หรือจาก Environment Variables
    env_file = os.path.join(BASE_DIR, '.env')
    if os.path.exists(env_file):
        try:
            with open(env_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        k, v = line.split('=', 1)
                        k = k.strip()
                        v = v.strip().strip("'\"")
                        if k not in os.environ:
                            os.environ[k] = v
        except Exception:
            pass

    SMTP_SERVER = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
    SMTP_PORT = int(os.environ.get('SMTP_PORT', 587))
    SMTP_USER = os.environ.get('SMTP_USER', '')
    SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD', '')
    MAIL_FROM_NAME = os.environ.get('MAIL_FROM_NAME', 'PawLove Foundation (มูลนิธิเพื่อเพื่อนสี่ขา)')
