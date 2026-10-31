"""
ไฟล์หลักสำหรับเริ่มต้นและรันแอปพลิเคชัน PawLove (Flask Application Entry Point)
แยกส่วนการทำงานอย่างชัดเจนระหว่างหน้าบ้าน (Client) และหลังบ้าน (Admin)
"""

import os
import sys
from flask import Flask, session
from config import Config
from database import init_db, seed_data, get_db_connection

# รองรับการพิมพ์ข้อความภาษาไทยบน Windows console
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass


def create_app():
    """
    ฟังก์ชันโรงงานสร้างและตั้งค่าแอปพลิเคชัน Flask (Application Factory)
    - กำหนดค่า Config
    - สร้างโฟลเดอร์ที่จำเป็นสำหรับจัดเก็บไฟล์
    - เริ่มต้นฐานข้อมูล SQLite และใส่ข้อมูลตัวอย่างเริ่มต้น
    - ลงทะเบียน Blueprint แยกหมวดหมู่ชัดเจน:
      1. auth_bp: ระบบการยืนยันตัวตนและการเข้าถึงแอดมิน
      2. client_bp: ระบบหน้าบ้านสำหรับผู้ใช้ทั่วไป
      3. admin_bp: ระบบหลังบ้านสำหรับผู้ดูแลระบบ
    - กำหนด Context Processors สำหรับส่งข้อมูลส่วนกลางไปยังทุกเทมเพลต
    """
    app = Flask(__name__)
    app.config.from_object(Config)

    # ตรวจสอบและสร้างโฟลเดอร์ uploads และ uploads/pets หากยังไม่มี
    pets_upload_folder = os.path.join(app.config['UPLOAD_FOLDER'], 'pets')
    os.makedirs(pets_upload_folder, exist_ok=True)

    # เตรียมฐานข้อมูล SQLite
    with app.app_context():
        init_db()
        seed_data()

    # นำเข้าและลงทะเบียน Blueprint
    from routes.auth import auth_bp
    from routes.client import client_bp
    from routes.admin import admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(client_bp)
    app.register_blueprint(admin_bp)

    @app.context_processor
    def inject_global_data():
        """
        ฟังก์ชันจัดเตรียมตัวแปรส่วนกลางสำหรับทุกหน้าเทมเพลต (Context Processor)
        - ส่งจำนวนคำขอรออนุมัติให้แอดมินทราบ (Badge Notification)
        - ส่งจำนวนการแจ้งเตือนของผู้ใช้
        """
        pending_requests_count = 0
        user_notifs_count = 0

        # หากล็อกอินเป็นแอดมิน นับคำขอที่รออนุมัติ
        if session.get('user_role') == 'admin':
            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) as count FROM pet_requests WHERE status = 'pending'")
                row = cursor.fetchone()
                pending_requests_count = row['count'] if row else 0
                conn.close()
            except Exception:
                pending_requests_count = 0

        # นับการแจ้งเตือนสำหรับผู้ใช้ทั่วไป
        if 'user_id' in session:
            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute('''
                SELECT COUNT(*) as count FROM notifications 
                WHERE (user_id IS NULL OR user_id = ?) AND is_read = 0
                ''', (session['user_id'],))
                row = cursor.fetchone()
                user_notifs_count = row['count'] if row else 0
                conn.close()
            except Exception:
                user_notifs_count = 0

        return {
            'pending_requests_count': pending_requests_count,
            'user_notifs_count': user_notifs_count
        }

    return app


def find_available_port(default_port=5000):
    """
    ฟังก์ชันตรวจสอบพอร์ตที่พร้อมใช้งานโดยอัตโนมัติ
    - ป้องกันปัญหาพอร์ต 5000 ติดขัดจากโปรเซสอื่นในระบบ Windows
    """
    import socket
    candidates = [default_port, 5050, 8000, 8080]
    for p in candidates:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.bind(('127.0.0.1', p))
            s.close()
            return p
        except OSError:
            continue
    return default_port


app = create_app()

if __name__ == '__main__':
    port = find_available_port(5000)
    print("=" * 65)
    print(" 🐾 PawLove - ระบบช่วยเหลือและหาบ้านให้น้องหมาน้องแมว ")
    print(f" 🌐 หน้าหลักผู้ใช้งาน: http://127.0.0.1:{port}")
    print(f" 🛡️  เข้าระบบแอดมินโดยตรง (ข้อ 1): http://127.0.0.1:{port}/admin")
    print(f"    (หรือพิมพ์: http://127.0.0.1:{port}/admin-access หรือ /admin-login)")
    print("=" * 65)
    app.run(host='127.0.0.1', port=port, debug=False)

