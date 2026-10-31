"""
ระบบจัดการฐานข้อมูล PawLove (SQLite)
กำกับฟังก์ชันทุกตัวอย่างละเอียดตามข้อกำหนด
"""

import sqlite3
import os
import sys
import json
from datetime import datetime
from werkzeug.security import generate_password_hash

# รองรับการพิมพ์ข้อความภาษาไทยบน Windows console
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# เส้นทางไฟล์ฐานข้อมูล SQLite
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pawlove.db')


def get_db_connection():
    """
    ฟังก์ชันเชื่อมต่อฐานข้อมูล SQLite
    - คืนค่าการเชื่อมต่อ sqlite3.Connection ที่เปิด row_factory เป็น sqlite3.Row เพื่อให้เข้าถึงคอลัมน์ด้วยชื่อได้
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """
    ฟังก์ชันสร้างตารางทั้งหมดในฐานข้อมูล SQLite หากยังไม่มีอยู่
    - สร้างตาราง users: จัดเก็บข้อมูลผู้ใช้และแอดมิน
    - สร้างตาราง pets: จัดเก็บข้อมูลสัตว์เลี้ยง
    - สร้างตาราง pet_status_updates: จัดเก็บประวัติการอัปเดตสถานะสัตว์ (ระบุวันที่ เวลา และรายละเอียด)
    - สร้างตาราง pet_requests: จัดเก็บคำขอเพิ่มสัตว์และแก้ไขสัตว์จากผู้ใช้ที่ต้องรอแอดมินอนุมัติ
    - สร้างตาราง adoption_applications: จัดเก็บแบบฟอร์ม 9.1 สอบถามข้อมูลเบื้องต้นในการรับเลี้ยง
    - สร้างตาราง notifications: จัดเก็บการแจ้งเตือนข่าวสารและผลการอนุมัติ
    - สร้างตาราง site_content: จัดเก็บข้อมูลหน้าเว็บที่แอดมินสามารถแก้ไขได้ (หน้าหลัก, เกี่ยวกับเรา, ติดต่อเรา ฯลฯ)
    - สร้างตาราง donations: จัดเก็บข้อมูลการบริจาค
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. ตารางผู้ใช้งาน
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fullname TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        age_confirmed INTEGER DEFAULT 1,
        terms_accepted INTEGER DEFAULT 1,
        role TEXT DEFAULT 'user', -- 'user' หรือ 'admin'
        status TEXT DEFAULT 'active', -- 'active' หรือ 'deleted'
        deletion_reason TEXT,
        deleted_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    for col_def in [
        ("status", "TEXT DEFAULT 'active'"),
        ("deletion_reason", "TEXT"),
        ("deleted_at", "TIMESTAMP")
    ]:
        try:
            cursor.execute(f"ALTER TABLE users ADD COLUMN {col_def[0]} {col_def[1]}")
        except Exception:
            pass

    # 2. ตารางสัตว์
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS pets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        species TEXT NOT NULL, -- 'สุนัข' หรือ 'แมว'
        name TEXT NOT NULL,
        age_years INTEGER DEFAULT 0,
        age_months INTEGER DEFAULT 0,
        gender TEXT NOT NULL, -- 'เพศผู้' หรือ 'เพศเมีย'
        breed TEXT NOT NULL,
        caretaker_name TEXT NOT NULL,
        current_address TEXT NOT NULL,
        status TEXT NOT NULL, 
        -- สถานะ 4 แบบ:
        -- 1.กำลังหาบ้าน(สุขภาพดี)
        -- 2.กำลังอยู่ระหว่างการรักษา(รับโดเนทเฉพาะสัตว์ที่ขึ้นสถานะนี้)
        -- 3.รอรับการช่วยเหลือ(รับโดเนทเฉพาะสัตว์ที่ขึ้นสถานะนี้)
        -- 4.หาบ้านได้แล้ว
        description TEXT NOT NULL,
        extra_details TEXT,
        image_url TEXT,
        created_by INTEGER,
        is_approved INTEGER DEFAULT 1, -- 1=เผยแพร่แล้ว, 0=รออนุมัติ
        current_step INTEGER DEFAULT 1,
        donation_target REAL DEFAULT 0.0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (created_by) REFERENCES users (id)
    )
    ''')

    for col_def in [
        ("current_step", "INTEGER DEFAULT 1"),
        ("donation_target", "REAL DEFAULT 0.0")
    ]:
        try:
            cursor.execute(f"ALTER TABLE pets ADD COLUMN {col_def[0]} {col_def[1]}")
        except Exception:
            pass

    # 3. ตารางประวัติการอัปเดตสถานะของสัตว์ (ข้อ 6: ระบุรายละเอียด วันที่ และเวลาในการอัปเดต)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS pet_status_updates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pet_id INTEGER NOT NULL,
        status TEXT NOT NULL,
        details TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        updated_by TEXT DEFAULT 'แอดมิน PawLove',
        FOREIGN KEY (pet_id) REFERENCES pets (id) ON DELETE CASCADE
    )
    ''')

    # 4. ตารางคำขอเพิ่มหรือแก้ไขสัตว์จากผู้ใช้ (ข้อ 2 & ข้อ 3: ต้องให้แอดมินอนุมัติ)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS pet_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        request_type TEXT NOT NULL, -- 'add' (ขอเพิ่มสัตว์ใหม่) หรือ 'edit' (ขอแก้ไขข้อมูลสัตว์เดิม)
        pet_id INTEGER, -- ระบุเมื่อเป็น 'edit'
        user_id INTEGER NOT NULL,
        proposed_data TEXT NOT NULL, -- JSON ข้อมูลที่ส่งมา
        status TEXT DEFAULT 'pending', -- 'pending' (รออนุมัติ), 'approved' (อนุมัติแล้ว), 'rejected' (ปฏิเสธ)
        admin_notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        resolved_at TIMESTAMP,
        FOREIGN KEY (pet_id) REFERENCES pets (id) ON DELETE CASCADE,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    ''')

    # 5. ตารางแบบฟอร์ม 9.1 คำขอรับเลี้ยงสัตว์
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS adoption_applications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pet_id INTEGER NOT NULL,
        user_id INTEGER,
        applicant_name TEXT NOT NULL,
        address TEXT NOT NULL,
        postal_code TEXT NOT NULL,
        email TEXT NOT NULL,
        phone TEXT NOT NULL,
        other_contacts TEXT,
        nearest_airport TEXT NOT NULL,
        household_members TEXT NOT NULL,
        household_agreement TEXT NOT NULL,
        other_pets TEXT,
        house_description TEXT NOT NULL,
        job_and_hours TEXT NOT NULL,
        reason_and_about TEXT NOT NULL,
        terms_accepted INTEGER NOT NULL,
        status TEXT DEFAULT 'รอการติดต่อสัมภาษณ์', -- 'รอการติดต่อสัมภาษณ์', 'ผ่านการสัมภาษณ์', 'อนุมัติรับเลี้ยง', 'ปฏิเสธ'
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (pet_id) REFERENCES pets (id) ON DELETE CASCADE,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    ''')

    # 6. ตารางการแจ้งเตือนข่าวสารและการอนุมัติสำหรับผู้ใช้
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER, -- หากเป็น NULL หมายถึงแจ้งเตือนทั่วไปทุกคน
        title TEXT NOT NULL,
        message TEXT NOT NULL,
        is_read INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    ''')

    # 7. ตารางเนื้อหาเว็บไซต์ที่แอดมินแก้ไขได้ (หน้าหลัก, เกี่ยวกับเรา, บริจาค, ติดต่อเรา)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS site_content (
        key_name TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        extra_data TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # 8. ตารางการบริจาค
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS donations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pet_id INTEGER,
        donor_name TEXT NOT NULL,
        amount REAL NOT NULL,
        message TEXT,
        slip_url TEXT,
        is_verified INTEGER DEFAULT 0,
        verification_info TEXT,
        transfer_ref TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (pet_id) REFERENCES pets (id)
    )
    ''')

    for col_def in [
        ("slip_url", "TEXT"),
        ("is_verified", "INTEGER DEFAULT 0"),
        ("verification_info", "TEXT"),
        ("transfer_ref", "TEXT"),
        ("target_type", "TEXT DEFAULT 'general'")
    ]:
        try:
            cursor.execute(f"ALTER TABLE donations ADD COLUMN {col_def[0]} {col_def[1]}")
        except Exception:
            pass

    # 9. ตารางคำคมและภาพสไลด์แบนเนอร์เคลื่อนไหว (แอดมินจัดการเพิ่ม/แก้ไข/ลบได้)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS banner_quotes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        quote_text TEXT NOT NULL,
        sub_text TEXT,
        author TEXT,
        image_url TEXT NOT NULL,
        sort_order INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # 10. ตารางบันทึกการเข้าสู่ระบบ (User Login Tracking สำหรับแดชบอร์ด)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS user_logins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        email TEXT NOT NULL,
        fullname TEXT,
        role TEXT DEFAULT 'user',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    ''')

    # 11. ตารางข่าวสารและประกาศ (แอดมินเพิ่ม/แก้ไข/ลบได้)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS news (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        category TEXT DEFAULT 'ข่าวประชาสัมพันธ์',
        summary TEXT,
        content TEXT NOT NULL,
        image_url TEXT,
        author TEXT DEFAULT 'ผู้ดูแลระบบ PawLove',
        is_published INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    conn.commit()
    conn.close()


def seed_data():
    """
    ฟังก์ชันใส่ข้อมูลตั้งต้น (Seed Data)
    - สร้างบัญชีแอดมินเริ่มต้น (admin@pawlove.org) ให้สามารถเข้าถึงระบบหลังบ้านด้วยอีเมลได้เลย
    - สร้างบัญชีผู้ใช้ตัวอย่าง (user@example.com)
    - บันทึกเนื้อหาเว็บไซต์เริ่มต้น (โครงการ, การทำงาน 4 ด้าน, ช่องทางติดต่อ)
    - ใส่ข้อมูลสัตว์ตัวอย่างทั้งสุนัขและแมวครบทุกสถานะ
    - ใส่ประวัติการอัปเดตสถานะของสัตว์ตัวอย่าง
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # ตรวจสอบว่ามีข้อมูลผู้ใช้หรือยัง
    cursor.execute("SELECT COUNT(*) as count FROM users")
    if cursor.fetchone()['count'] == 0:
        # สร้างแอดมินเริ่มต้น
        admin_pass = generate_password_hash("Admin1234")
        cursor.execute('''
        INSERT INTO users (fullname, email, password_hash, age_confirmed, terms_accepted, role)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', ("ผู้ดูแลระบบ PawLove", "admin@pawlove.org", admin_pass, 1, 1, "admin"))

        # สร้างผู้ใช้ทั่วไปตัวอย่าง
        user_pass = generate_password_hash("User1234")
        cursor.execute('''
        INSERT INTO users (fullname, email, password_hash, age_confirmed, terms_accepted, role)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', ("สมชาย ใจดี", "user@example.com", user_pass, 1, 1, "user"))

        # เนื้อหาเว็บไซต์เริ่มต้น (แอดมินสามารถแก้ไขได้ทั้งหมด)
        contents = [
            ("project_info", "ข้อมูลโครงการ PawLove", 
             "โครงการ PawLove ก่อตั้งขึ้นด้วยเจตนารมณ์เพื่อช่วยเหลือสุนัขและแมวจรจัดในประเทศไทย ให้ได้รับการดูแลทางการแพทย์ ทำหมัน ฉีดวัคซีน และมีโอกาสได้พบกับครอบครัวที่อบอุ่นและพร้อมมอบความรักอย่างแท้จริง"),
            ("project_work", "การทำงานของโครงการ", 
             json.dumps({
                 "medical": "ดูแลการรักษา: ให้การพยาบาลฟื้นฟูสัตว์ป่วยและบาดเจ็บอย่างเต็มความสามารถจนหายดี",
                 "sterilization": "การทำหมัน: ทำหมันและฉีดวัคซีนป้องกันโรคพิษสุนัขบ้าเพื่อควบคุมประชากรสัตว์จรอย่างยั่งยืน",
                 "emergency": "การช่วยเหลือฉุกเฉิน: หน่วยกู้ภัยสัตว์กรณีได้รับอุบัติเหตุหรือตกอยู่ในภาวะอันตรายเร่งด่วน",
                 "shelter": "ศูนย์พักพิงชั่วคราว: พื้นที่ปลอดภัย สะอาด มีสุขอนามัยที่ดี รองรับการฟื้นฟูก่อนส่งต่อไปยังบ้านใหม่"
             }, ensure_ascii=False)),
            ("contact_info", "ช่องทางการติดต่อ", 
             json.dumps({
                 "email": "contact@pawlove.org",
                 "facebook": "PawLove Thailand Rescue",
                 "instagram": "@pawlove_th",
                 "tiktok": "@pawlove_official"
             }, ensure_ascii=False)),
            ("donation_info", "ข้อมูลการบริจาค",
             "ร่วมเป็นส่วนหนึ่งในการต่อลมหายใจให้แก่สุนัขและแมวที่ต้องการความช่วยเหลือ ทุกบาททุกสตางค์ของท่านจะถูกนำไปใช้เพื่อค่ารักษาพยาบาล อาหาร และอุปกรณ์จำเป็นสำหรับสัตว์ป่วยและสัตว์ที่รอความช่วยเหลือโดยตรง")
        ]

        for key_name, title, content in contents:
            cursor.execute('''
            INSERT OR REPLACE INTO site_content (key_name, title, content)
            VALUES (?, ?, ?)
            ''', (key_name, title, content))

        # ใส่สัตว์ตัวอย่าง (สุนัขและแมว ครบทุกสถานะ)
        now_str = datetime.now().strftime("%d/%m/%Y %H:%M น.")
        pets = [
            (
                "สุนัข", "เจ้าเฉาก๊วย", 2, 6, "เพศผู้", "ไทยผสมบางแก้ว",
                "พี่สมหมาย อาสาสมัครโซนบางเขน", "ศูนย์พักพิง PawLove ชลบุรี",
                "กำลังหาบ้าน(สุขภาพดี)",
                "เฉาก๊วยเป็นน้องหมานิสัยร่าเริง ฉลาด ว่านอนสอนง่าย เข้ากับคนและเด็กได้ดีมาก",
                "ได้รับการทำหมันและฉีดวัคซีนครบถ้วนแล้ว สุขภาพแข็งแรง ขนสวย พร้อมย้ายเข้าบ้านใหม่",
                "https://images.unsplash.com/photo-1543466835-00a7907e9de1?w=800&auto=format&fit=crop&q=60",
                1, 1
            ),
            (
                "สุนัข", "ลัคกี้", 1, 2, "เพศเมีย", "โกลเด้นผสม",
                "คุณหมอแพรว รพ.สัตว์เมตตา", "คลินิกฟื้นฟู PawLove กรุงเทพฯ",
                "กำลังอยู่ระหว่างการรักษา(รับโดเนทเฉพาะสัตว์ที่ขึ้นสถานะนี้)",
                "ถูกรถชนบริเวณกระดูกเชิงกราน ขณะนี้ได้รับการผ่าตัดสำเร็จแล้วและกำลังทำกายภาพบำบัด",
                "ต้องการทุนสนับสนุนค่ากายภาพและค่ายาฟื้นฟูกล้ามเนื้ออย่างต่อเนื่อง",
                "https://images.unsplash.com/photo-1552053831-71594a27632d?w=800&auto=format&fit=crop&q=60",
                1, 1
            ),
            (
                "แมว", "น้องส้มโอ", 0, 8, "เพศเมีย", "ไทยศุภลักษณ์ผสม",
                "ป้าเพ็ญ ผู้ดูแลชุมชน", "ศูนย์พักพิง PawLove เชียงใหม่",
                "กำลังหาบ้าน(สุขภาพดี)",
                "ขี้อ้อนมาก ชอบนอนตักและส่งเสียงกรนเบาๆ เมื่อเกาคาง เข้ากับแมวตัวอื่นได้ดี",
                "ตรวจเลือดไม่พบลิวคีเมียและเอดส์แมว ทำหมันเรียบร้อย ขับถ่ายในกระบะทรายเป็น",
                "https://images.unsplash.com/photo-1514888286974-6c03e2ca1dba?w=800&auto=format&fit=crop&q=60",
                1, 1
            ),
            (
                "แมว", "มอมแมม", 0, 5, "เพศผู้", "แมวไทยลายสลิด",
                "ทีมกู้ภัย PawLove สายไหม", "ห้องดูแลสัตว์รอความช่วยเหลือ PawLove",
                "รอรับการช่วยเหลือ(รับโดเนทเฉพาะสัตว์ที่ขึ้นสถานะนี้)",
                "พบน้องติดอยู่ในท่อระบายน้ำ มีภาวะขาดน้ำ ขาดสารอาหารและมีแผลที่อุ้งเท้าหลัง",
                "กำลังรอรับการประเมินการรักษาเพิ่มเติมและตรวจเลือดอย่างละเอียด ต้องการรับโดเนทเพื่อการฟื้นฟูฉุกเฉิน",
                "https://images.unsplash.com/photo-1573865526739-10659fec78a5?w=800&auto=format&fit=crop&q=60",
                1, 1
            ),
            (
                "สุนัข", "กูฟฟี่", 3, 0, "เพศผู้", "ไซบีเรียนผสม",
                "ครอบครัวใจการุณ", "บ้านใหม่ จ.นนทบุรี",
                "หาบ้านได้แล้ว",
                "ได้ย้ายเข้าสู่บ้านอันอบอุ่นกับคุณพงษ์ศักดิ์และครอบครัวเรียบร้อยแล้ว",
                "ปรับตัวเข้ากับครอบครัวใหม่ได้ดีมาก วิ่งเล่นอย่างมีความสุข",
                "https://images.unsplash.com/photo-1583511655857-d19b40a7a54e?w=800&auto=format&fit=crop&q=60",
                1, 1
            )
        ]

        for pet in pets:
            cursor.execute('''
            INSERT INTO pets (species, name, age_years, age_months, gender, breed, caretaker_name, current_address, status, description, extra_details, image_url, created_by, is_approved)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', pet)
            pet_id = cursor.lastrowid

            # บันทึกประวัติสถานะตั้งต้น (ข้อ 6)
            status_desc = f"อัปเดตสถานะเป็น '{pet[8]}' โดยระบบ บันทึกเพื่อเริ่มกระบวนการช่วยเหลือและหาบ้าน"
            cursor.execute('''
            INSERT INTO pet_status_updates (pet_id, status, details, updated_at, updated_by)
            VALUES (?, ?, ?, ?, ?)
            ''', (pet_id, pet[8], status_desc, now_str, "แอดมิน PawLove"))

        # สร้างการแจ้งเตือนเริ่มต้นสำหรับผู้ใช้ (ข้อ 4 ข้อ 9)
        cursor.execute('''
        INSERT INTO notifications (user_id, title, message)
        VALUES 
        (NULL, 'ยินดีต้อนรับสู่ PawLove!', 'มูลนิธิเปิดรับสมัครครอบครัวใจดีที่พร้อมมอบบ้านที่อบอุ่นให้แก่น้องหมาและน้องแมว'),
        (2, 'ระบบแจ้งเตือนบัญชีของคุณ', 'คุณสามารถส่งคำขอเพิ่มสัตว์ที่ต้องการหาบ้านผ่านเมนู "ให้ความช่วยเหลือ" ได้แล้ววันนี้')
        ''')

        conn.commit()

    # เพิ่มข้อมูลภาพและคำคมสไลด์ตั้งต้น (หากยังไม่มีข้อมูล)
    cursor.execute("SELECT COUNT(*) as count FROM banner_quotes")
    if cursor.fetchone()['count'] == 0:
        default_quotes = [
            (
                "ทุกการช่วยเหลือ คือโอกาสที่น้อง ๆ จะได้มีชีวิตใหม่",
                "PawLove - ปลอดภัย โปร่งใส เพื่อสัตว์ทุกตัวจะได้รับความช่วยเหลือ",
                "PawLove Community",
                "static/uploads/pets/dogquote.jpg",
                1, 1
            ),
            (
                "หนึ่งบ้านที่อบอุ่น เปลี่ยนแปลงโลกทั้งใบของพวกเขาตลอดกาล",
                "ร่วมเปิดประตูบ้านและหัวใจ ต้อนรับเพื่อนสี่ขาที่พร้อมมอบความรักบริสุทธิ์",
                "โครงการหาบ้านใหม่ PawLove",
                "static/uploads/pets/catnew2.jpg",
                2, 1
            ),
            (
                "ความเมตตาของคุณ คือยาวิเศษที่ต่อลมหายใจให้สัตว์บาดเจ็บ",
                "ทุกบาททุกสตางค์เปลี่ยนเป็นค่ายา ค่าผ่าตัด และการดูแลจนกว่าน้องจะหายดี",
                "กองทุนเพื่อการรักษาพยาบาลสัตว์จรจัด",
                "static/uploads/pets/doghelp.jpg",
                3, 1
            ),
            (
                "ไม่ซื้อแต่รับเลี้ยง คุณคือฮีโร่ตัวจริงของสัตว์ไร้บ้าน",
                "สัตว์จรจัดทุกตัวมีหัวใจ และคู่ควรกับความรักและการดูแลที่ปลอดภัย",
                "มูลนิธิเพื่อสวัสดิภาพสัตว์ PawLove",
                "static/uploads/pets/dognew3.jpg",
                4, 1
            )
        ]
        for q in default_quotes:
            cursor.execute('''
            INSERT INTO banner_quotes (quote_text, sub_text, author, image_url, sort_order, is_active)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', q)
        conn.commit()

    # เพิ่มข้อมูลข่าวสารตั้งต้น (หากยังไม่มีข้อมูล)
    cursor.execute("SELECT COUNT(*) as count FROM news")
    if cursor.fetchone()['count'] == 0:
        default_news = [
            (
                "โครงการ PawLove เดินหน้าช่วยเหลือสัตว์จรจัดและเปิดรับอาสาสมัคร",
                "ข่าวประชาสัมพันธ์",
                "เปิดรับสมัครอาสาสมัครร่วมดูแลน้องหมาน้องแมว และสนับสนุนกิจกรรมลงพื้นที่ชุมชน",
                "มูลนิธิ PawLove มุ่งมั่นในการช่วยเหลือสัตว์จรจัดที่ได้รับบาดเจ็บ เจ็บป่วย หรือถูกทอดทิ้ง โดยในเดือนนี้เราเปิดรับอาสาสมัครร่วมภารกิจให้อาหาร ฟื้นฟูสภาพจิตใจน้อง ๆ และช่วยประสานงานหาบ้านใหม่ที่อบอุ่น",
                "static/uploads/pets/Golden Hour Animal Feeding.png",
                "ผู้ดูแลระบบ PawLove",
                1
            ),
            (
                "รายงานสรุปเคสน้องหมาน้องแมวที่ได้รับการรักษาสำเร็จและพร้อมส่งมอบบ้านใหม่",
                "ผลการดำเนินงาน",
                "ติดตามเรื่องราวความสำเร็จในการรักษาพยาบาลและการฟื้นฟูสุขภาพของน้อง ๆ",
                "ตลอดสัปดาห์ที่ผ่านมา ทีมสัตวแพทย์ของ PawLove ได้ทำการรักษาและทำหมันสัตว์จรจัดรวมกว่า 12 ตัว สัตว์ทุกตัวมีสุขภาพแข็งแรง ร่าเริง และเริ่มเปิดรับการคัดเลือกบ้านใหม่ผ่านระบบรับเลี้ยงแล้ว ขอขอบคุณทุกยอดบริจาคที่ร่วมส่งต่อโอกาสนี้",
                "static/uploads/pets/dogquote.jpg",
                "ผู้ดูแลระบบ PawLove",
                1
            ),
            (
                "ประกาศมาตรการคัดกรองสลีปโอนเงินและการรับบริจาคเพื่อความโปร่งใส",
                "ความโปร่งใส & บริจาค",
                "ระบบตรวจสอบสลีปอัตโนมัติ เพื่อให้ทุกการบริจาคส่งถึงมือน้อง ๆ อย่างแท้จริง",
                "PawLove ได้ยกระดับมาตรฐานความปลอดภัยและความโปร่งใส ด้วยระบบตรวจสอบสลีปการโอนเงินของธนาคารอัตโนมัติ เพื่อให้ผู้บริจาคทุกท่านมั่นใจว่าเงินบริจาคทุกบาทถูกนำไปใช้เพื่อค่ารักษาพยาบาล อาหาร และการดูแลน้องหมาน้องแมวอย่างตรงจุดที่สุด",
                "static/uploads/pets/doghelp.jpg",
                "ผู้ดูแลระบบ PawLove",
                1
            )
        ]
        for n in default_news:
            cursor.execute('''
            INSERT INTO news (title, category, summary, content, image_url, author, is_published)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', n)
        conn.commit()

    # เติมประวัติการเข้าสู่ระบบเบื้องต้นจากผู้ใช้ที่มีอยู่ (เพื่อให้แดชบอร์ดมีข้อมูลทันที)
    cursor.execute("SELECT COUNT(*) as count FROM user_logins")
    if cursor.fetchone()['count'] == 0:
        cursor.execute("SELECT id, email, fullname, role, created_at FROM users")
        existing_users = cursor.fetchall()
        for u in existing_users:
            cursor.execute('''
            INSERT INTO user_logins (user_id, email, fullname, role, created_at)
            VALUES (?, ?, ?, ?, ?)
            ''', (u['id'], u['email'], u['fullname'], u['role'], u['created_at']))
        conn.commit()

    conn.close()


if __name__ == '__main__':
    print("กำลังเตรียมและสร้างฐานข้อมูล PawLove...")
    init_db()
    seed_data()
    print("สร้างฐานข้อมูลและเพิ่มข้อมูลตั้งต้นสำเร็จเรียบร้อย!")
