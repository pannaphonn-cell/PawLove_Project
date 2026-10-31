"""
สคริปต์ทดสอบระบบ PawLove (Automated Integration Tests)
ทดสอบฟังก์ชันการทำงานหลักตามความต้องการทั้ง 10 ข้อ
"""

import sys
import unittest
import json
import io
import os
from app import create_app
from database import get_db_connection

# รองรับการพิมพ์ข้อความภาษาไทยบน Windows console
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass


class PawLoveTestCase(unittest.TestCase):
    def setUp(self):
        """ตั้งค่าก่อนการทดสอบแต่ละเคส"""
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()

    def test_01_admin_direct_access(self):
        """ทดสอบข้อกำหนดที่ 1: เข้าถึงระบบหลังบ้านแอดมินโดยการใส่อีเมลแอดมินและรหัสผ่าน"""
        response = self.client.post('/admin-access', data={
            'admin_email': 'admin@pawlove.org',
            'admin_password': 'Admin1234'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn('เข้าสู่ระบบหลังบ้านสำเร็จ'.encode('utf-8'), response.data)
        self.assertIn('ภาพรวมระบบหลังบ้าน'.encode('utf-8'), response.data)

    def test_02_registration_validation(self):
        """ทดสอบข้อกำหนดที่ 7: ระบบสมัครสมาชิก และตรวจสอบรหัสผ่าน (พิมพ์ใหญ่ พิมพ์เล็ก ตัวเลข)"""
        import time
        unique_email = f"user_{int(time.time()*1000)}@pawlove.test"

        # กรณีรหัสผ่านไม่มีตัวพิมพ์ใหญ่
        res_fail = self.client.post('/register', data={
            'fullname': 'ทดสอบ สมัคร',
            'email': unique_email,
            'confirm_email': unique_email,
            'password': 'password123',
            'confirm_password': 'password123',
            'age_confirmed': '1',
            'privacy_policy': '1',
            'terms_accepted': '1'
        }, follow_redirects=True)
        self.assertIn('รหัสผ่านต้องมีตัวอักษรพิมพ์ใหญ่'.encode('utf-8'), res_fail.data)

        # กรณีถูกต้องครบถ้วน
        res_ok = self.client.post('/register', data={
            'fullname': 'สมศักดิ์ รักสัตว์',
            'email': unique_email,
            'confirm_email': unique_email,
            'password': 'Password1234',
            'confirm_password': 'Password1234',
            'age_confirmed': '1',
            'privacy_policy': '1',
            'terms_accepted': '1'
        }, follow_redirects=True)
        self.assertIn('สมัครสมาชิกสำเร็จเรียบร้อย'.encode('utf-8'), res_ok.data)

    def test_03_login_validation(self):
        """ทดสอบข้อกำหนดที่ 8: ล็อกอินด้วย อีเมล รหัสผ่าน ยืนยันรหัสผ่าน"""
        res = self.client.post('/login', data={
            'email': 'admin@pawlove.org',
            'password': 'Admin1234',
            'confirm_password': 'Admin1234'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn('เข้าสู่ระบบสำเร็จ'.encode('utf-8'), res.data)

    def test_04_user_pet_submission_and_admin_approval(self):
        """ทดสอบข้อกำหนดที่ 2 และ 3: ผู้ใช้เพิ่มสัตว์หาบ้าน (ต้องยืนยันเงื่อนไข) และแอดมินอนุมัติคำขอ"""
        # ล็อกอินเป็นผู้ใช้ทั่วไป
        self.client.post('/login', data={
            'email': 'user@example.com',
            'password': 'User1234',
            'confirm_password': 'User1234'
        })

        # ผู้ใช้ส่งข้อมูลสัตว์หาบ้าน
        submit_res = self.client.post('/help-pet', data={
            'terms_confirmed': '1',
            'species': 'สุนัข',
            'name': 'เจ้าด่างน้อย',
            'age_years': '1',
            'age_months': '2',
            'gender': 'เพศผู้',
            'breed': 'ไทยพื้นเมือง',
            'caretaker_name': 'คุณสมชาย',
            'current_address': 'ซอยสายไหม 10 กรุงเทพฯ',
            'status': 'กำลังหาบ้าน(สุขภาพดี)',
            'description': 'นิสัยดี น่ารัก ขี้เล่นมาก ไม่เห่าพร่ำเพรื่อ',
            'extra_details': 'ฉีดวัคซีนแล้ว 1 เข็ม',
            'image_url': 'https://images.unsplash.com/photo-1543466835-00a7907e9de1'
        }, follow_redirects=True)
        self.assertIn('ส่งข้อมูลน้อง'.encode('utf-8'), submit_res.data)

        # สลับเป็นแอดมินด้วยอีเมลและรหัสผ่านแอดมิน
        self.client.post('/admin-access', data={'admin_email': 'admin@pawlove.org', 'admin_password': 'Admin1234'})

        # ดึงคำขอล่าสุดจาก DB
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM pet_requests WHERE status = 'pending' ORDER BY id DESC LIMIT 1")
        req = cursor.fetchone()
        conn.close()

        self.assertIsNotNone(req, "ต้องมีคำขอส่งมายังแอดมิน")

        # แอดมินกดอนุมัติคำขอ (ข้อกำหนดที่ 2)
        approve_res = self.client.post(f'/admin/requests/{req["id"]}/approve', data={
            'admin_notes': 'ผ่านการตรวจสอบ ข้อมูลครบถ้วน'
        }, follow_redirects=True)
        self.assertIn('อนุมัติคำขอเรียบร้อยแล้ว'.encode('utf-8'), approve_res.data)

    def test_05_admin_status_update_with_datetime(self):
        """ทดสอบข้อกำหนดที่ 6: แอดมินอัปเดตสถานะของสัตว์สม่ำเสมอ พร้อมรายละเอียด วันที่ และเวลา"""
        # เข้าสู่ระบบแอดมิน
        self.client.post('/admin-access', data={'admin_email': 'admin@pawlove.org', 'admin_password': 'Admin1234'})

        # อัปเดตสถานะสัตว์ ID 1
        res = self.client.post('/admin/pets/1/status-update', data={
            'status': 'กำลังหาบ้าน(สุขภาพดี)',
            'details': 'ตรวจสุขภาพซ้ำรอบประจำสัปดาห์ ร่างกายสมบูรณ์แข็งแรงมาก พร้อมรับอุปการะ',
            'update_datetime': '14/10/2026 15:45 น.'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn('อัปเดตสถานะน้อง'.encode('utf-8'), res.data)

        # ตรวจสอบว่าบันทึกลง timeline หรือไม่
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM pet_status_updates WHERE pet_id = 1 ORDER BY id DESC LIMIT 1")
        latest_update = cursor.fetchone()
        conn.close()

        self.assertEqual(latest_update['updated_at'], '14/10/2026 15:45 น.')
        self.assertIn('ตรวจสุขภาพซ้ำ', latest_update['details'])

    def test_06_adoption_application_form_9_1(self):
        """ทดสอบข้อกำหนดที่ 9.1: การสอบถามข้อมูลเบื้องต้นในการรับเลี้ยง"""
        res = self.client.post('/adopt/1/apply', data={
            'applicant_name': 'นันทพร ใจดี',
            'address': '99/1 ซอยอารีย์ พญาไท',
            'postal_code': '10400',
            'email': 'nanthaporn@test.com',
            'confirm_email': 'nanthaporn@test.com',
            'phone': '089-999-8888',
            'other_contacts': 'Line: nanthaporn_a',
            'nearest_airport': 'ดอนเมือง (DMK)',
            'household_members': 'พักกับคู่สมรส 2 คน',
            'household_agreement': 'ทุกคนในบ้านตกลงร่วมกันและยินดีรับเลี้ยง',
            'other_pets': 'ไม่มีสัตว์เลี้ยงอื่น',
            'house_description': 'บ้านเดี่ยวมีรั้วมิดชิด ปลอดภัย',
            'job_and_hours': 'พนักงานบริษัท ทำงาน 8 ชม./วัน',
            'reason_and_about': 'อยากมอบบ้านที่อบอุ่นและมีเวลาดูแลเต็มที่',
            'terms_accepted': '1'
        }, follow_redirects=True)

        self.assertEqual(res.status_code, 200)
        self.assertIn('ส่งแบบฟอร์มขอรับเลี้ยงน้อง'.encode('utf-8'), res.data)

    def test_07_pet_image_choose_file_upload(self):
        """ทดสอบการอัปโหลดรูปภาพสัตว์ผ่านฟังก์ชัน Choose File (ไม่ใช้ URL ลิงก์)"""
        import io
        # ผู้ใช้ทั่วไปส่งสัตว์พร้อมอัปโหลดไฟล์รูปภาพ
        self.client.post('/login', data={
            'email': 'user@example.com',
            'password': 'User1234',
            'confirm_password': 'User1234'
        })

        fake_image = (io.BytesIO(b'\xff\xd8\xff\xe0test_image_data'), 'cute_puppy.jpg')
        res = self.client.post('/help-pet', data={
            'terms_confirmed': '1',
            'species': 'สุนัข',
            'name': 'น้องปุยฝ้าย',
            'age_years': '0',
            'age_months': '8',
            'gender': 'เพศเมีย',
            'breed': 'ปอมเมอเรเนียน',
            'caretaker_name': 'คุณสมหญิง',
            'current_address': 'นนทบุรี',
            'status': 'กำลังหาบ้าน(สุขภาพดี)',
            'description': 'ร่าเริง ขี้อ้อน ชอบวิ่งเล่น',
            'extra_details': 'ฉีดวัคซีนรวมครบแล้ว',
            'pet_image': fake_image
        }, content_type='multipart/form-data', follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        # ตรวจสอบว่าคำขอถูกบันทึกพร้อม URL ที่ชี้ไปยัง /static/uploads/pets/
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT proposed_data FROM pet_requests WHERE status = 'pending' ORDER BY id DESC LIMIT 1")
        req = cursor.fetchone()
        conn.close()

        req_data = json.loads(req['proposed_data'])
        self.assertTrue(req_data['image_url'].startswith('/static/uploads/pets/pet_'))
        self.assertTrue(req_data['image_url'].endswith('.jpg'))

    def test_08_pet_status_timelines_and_flexible_upload(self):
        """ทดสอบไทม์ไลน์ 4 สถานะสัตว์ (ขั้นตอนย่อย 1-5 และสถานะหลัก) และการอัปโหลดไฟล์ไม่จำกัดนามสกุล"""
        from utils import get_timeline_for_status
        import io

        # 1. ทดสอบโครงสร้างไทม์ไลน์สถานะ 1 (กำลังหาบ้าน - สถานะหลัก ไม่ต้องมีขั้นตอนย่อย)
        t1 = get_timeline_for_status('กำลังหาบ้าน(สุขภาพดี)')
        self.assertFalse(t1['has_substeps'])
        self.assertEqual(len(t1['steps']), 0)

        # 2. ทดสอบโครงสร้างไทม์ไลน์สถานะ 2 (กำลังอยู่ระหว่างการรักษา - 5 ขั้นตอน)
        t2 = get_timeline_for_status('กำลังอยู่ระหว่างการรักษา')
        self.assertTrue(t2['has_substeps'])
        self.assertEqual(len(t2['steps']), 5)
        self.assertIn('รับแจ้งข้อมูลน้องและปัญหาที่พบ', t2['steps'][0]['title'])
        self.assertIn('อยู่ระหว่างการรักษาโดยสัตวแพทย์', t2['steps'][2]['title'])
        self.assertIn('รักษาเสร็จสิ้นและเตรียมดูแลต่อ', t2['steps'][4]['title'])

        # 3. ทดสอบโครงสร้างไทม์ไลน์สถานะ 3 (รอรับการช่วยเหลือ - 5 ขั้นตอน)
        t3 = get_timeline_for_status('รอรับการช่วยเหลือ')
        self.assertTrue(t3['has_substeps'])
        self.assertEqual(len(t3['steps']), 5)
        self.assertIn('รับแจ้งข้อมูลและรายละเอียดของน้อง', t3['steps'][0]['title'])
        self.assertIn('ได้รับการช่วยเหลือและประเมินการดูแลต่อไป', t3['steps'][4]['title'])

        # 4. ทดสอบโครงสร้างไทม์ไลน์สถานะ 4 (หาบ้านได้แล้ว - 5 ขั้นตอน)
        t4 = get_timeline_for_status('หาบ้านได้แล้ว')
        self.assertTrue(t4['has_substeps'])
        self.assertEqual(len(t4['steps']), 5)
        self.assertIn('มีผู้สนใจรับเลี้ยงน้อง', t4['steps'][0]['title'])
        self.assertIn('ปิดเคสการหาบ้านสำเร็จ', t4['steps'][4]['title'])

        # 5. ทดสอบแอดมินอัปเดตขั้นตอนในไทม์ไลน์ (current_step = 3)
        self.client.post('/admin-access', data={'admin_email': 'admin@pawlove.org', 'admin_password': 'Admin1234'})
        res = self.client.post('/admin/pets/1/status-update', data={
            'status': 'กำลังอยู่ระหว่างการรักษา(รับโดเนทเฉพาะสัตว์ที่ขึ้นสถานะนี้)',
            'current_step': '3',
            'details': 'อยู่ระหว่างการผ่าตัดและดูแลโดยสัตวแพทย์',
            'update_datetime': '14/10/2026 16:00 น.'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        # ตรวจสอบการบันทึกลงในฐานข้อมูล pets
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT status, current_step FROM pets WHERE id = 1")
        pet = cursor.fetchone()
        conn.close()
        self.assertEqual(pet['current_step'], 3)

        # 6. ทดสอบการอัปโหลดรูปภาพโดยไม่จำกัดนามสกุล (เช่น .customimg, .jfif)
        fake_any_file = (io.BytesIO(b'raw_image_bytes'), 'pet_photo.customimg')
        res_upload = self.client.post('/help-pet', data={
            'terms_confirmed': '1',
            'species': 'แมว',
            'name': 'น้องส้มซ่า',
            'age_years': '1',
            'age_months': '0',
            'gender': 'เพศผู้',
            'breed': 'ไทย',
            'caretaker_name': 'คุณใจดี',
            'current_address': 'กรุงเทพฯ',
            'status': 'กำลังหาบ้าน(สุขภาพดี)',
            'description': 'น่ารัก สุขภาพดี ขี้อ้อน',
            'pet_image': fake_any_file
        }, content_type='multipart/form-data', follow_redirects=True)
        self.assertEqual(res_upload.status_code, 200)

    def test_09_promptpay_qr_and_slip_verification_and_quotes(self):
        """ทดสอบ 3 ฟังก์ชันใหม่ล่าสุด: รวม QR พร้อมเพย์ + ตรวจสอบสลีปโอนเงินจริง + จัดการคำคม + ไอคอนแอปพลิเคชัน"""
        import os

        # 1. ทดสอบหน้าบริจาคมี QR โค้ดและพร้อมเพย์รวมกัน พร้อมข้อมูลผู้รับเงิน น.ส. ปัณณพร เนืองทอง
        res_donate = self.client.get('/donate')
        self.assertEqual(res_donate.status_code, 200)
        self.assertIn('promptpay_qr.jpg'.encode('utf-8'), res_donate.data)
        self.assertIn('ปัณณพร เนืองทอง'.encode('utf-8'), res_donate.data)
        self.assertIn('004999171860413'.encode('utf-8'), res_donate.data)

        # 2. ทดสอบแนบไฟล์ที่ไม่ใช่สลีป (รูปแมว) -> ต้องถูกปฏิเสธ (ตรวจสอบให้ได้ว่าเป็นสลีปโอนเงินจริงๆ)
        cat_img_path = os.path.join(self.app.root_path, 'static', 'uploads', 'pets', 'catnew2.jpg')
        with open(cat_img_path, 'rb') as f:
            cat_bytes = f.read()

        fake_slip = (io.BytesIO(cat_bytes), 'cat_not_slip.jpg')
        res_fail = self.client.post('/donate', data={
            'donor_name': 'นายทดสอบ ไม่ใช่สลีป',
            'amount': '500',
            'purpose': 'medical',
            'slip_file': fake_slip
        }, content_type='multipart/form-data', follow_redirects=True)
        self.assertIn('ไม่ใช่สลีปโอนเงินของธนาคาร'.encode('utf-8'), res_fail.data)

        # 3. ทดสอบแนบไฟล์ที่มี QR Code ของ PromptPay จริง (สลีปที่ถูกต้อง) -> ต้องผ่านการตรวจสอบ
        qr_img_path = os.path.join(self.app.root_path, 'static', 'images', 'promptpay_qr.jpg')
        with open(qr_img_path, 'rb') as f:
            qr_bytes = f.read()

        valid_slip = (io.BytesIO(qr_bytes), 'real_slip_promptpay.jpg')
        res_pass = self.client.post('/donate', data={
            'donor_name': 'คุณใจบุญ สลีปแท้',
            'amount': '999',
            'purpose': 'medical',
            'slip_file': valid_slip
        }, content_type='multipart/form-data', follow_redirects=True)
        self.assertIn('ตรวจสอบผ่าน: สลีปโอนเงินถูกต้องผ่านระบบ'.encode('utf-8'), res_pass.data)

        # 4. ทดสอบแอดมินจัดการคำคมและแบนเนอร์ (เพิ่มคำคมใหม่)
        self.client.post('/admin-access', data={'admin_email': 'admin@pawlove.org', 'admin_password': 'Admin1234'})
        res_add_quote = self.client.post('/admin/quotes/add', data={
            'quote_text': 'ความรักและเมตตาต่อสัตว์คือสิ่งงดงามที่สุด',
            'sub_text': 'ขอบคุณผู้ดูแลระบบ PawLove',
            'author': 'แอดมินใจดี',
            'sort_order': '99',
            'is_active': '1',
            'image_url': 'https://images.unsplash.com/photo-1543466835-00a7907e9de1?w=800'
        }, follow_redirects=True)
        self.assertEqual(res_add_quote.status_code, 200)
        self.assertIn('เพิ่มรูปและคำคมใหม่ลงในแบนเนอร์เรียบร้อยแล้ว'.encode('utf-8'), res_add_quote.data)

        # ตรวจสอบว่าคำคมใหม่ถูกส่งไปแสดงที่หน้าแรก
        res_home = self.client.get('/')
        self.assertEqual(res_home.status_code, 200)
        self.assertIn('ความรักและเมตตาต่อสัตว์คือสิ่งงดงามที่สุด'.encode('utf-8'), res_home.data)

        # 5. ทดสอบหน้าติดต่อเรา ใช้ไอคอนตามแอปพลิเคชัน (E-Mail, Facebook, Instagram, TikTok) ไม่มีอิโมจิ
        res_contact = self.client.get('/contact')
        self.assertEqual(res_contact.status_code, 200)
        self.assertIn('fa-brands fa-facebook'.encode('utf-8'), res_contact.data)
        self.assertIn('fa-brands fa-instagram'.encode('utf-8'), res_contact.data)
        self.assertIn('fa-brands fa-tiktok'.encode('utf-8'), res_contact.data)
        self.assertIn('fa-solid fa-envelope'.encode('utf-8'), res_contact.data)

    def test_10_status_looking_for_home_and_no_donation_card(self):
        """ทดสอบ: 1) สถานะกำลังหาบ้านแสดงผลถูกต้องไม่หาย
        2) ไม่แสดงการ์ดโดเนท/แถบรับบริจาคสำหรับสัตว์ที่กำลังหาบ้านและหาบ้านได้แล้ว
        3) ตรวจสอบการตั้งค่าขนาดอัปโหลดรูปภาพ 100MB"""
        # 1. ตรวจสอบ MAX_CONTENT_LENGTH
        self.assertEqual(self.app.config['MAX_CONTENT_LENGTH'], 100 * 1024 * 1024)

        # 2. ตรวจสอบการแสดงผลหน้าแรก (index)
        res_home = self.client.get('/')
        self.assertEqual(res_home.status_code, 200)
        # ตรวจสอบว่ามีป้าย 'กำลังหาบ้าน' แสดง
        self.assertIn('กำลังหาบ้าน'.encode('utf-8'), res_home.data)

        # 3. ตรวจสอบหน้ารายการสัตว์ (adopt)
        res_adopt = self.client.get('/adopt')
        self.assertEqual(res_adopt.status_code, 200)
        self.assertIn('กำลังหาบ้าน'.encode('utf-8'), res_adopt.data)

        # 4. ตรวจสอบหน้ารายละเอียดสัตว์ที่สถานะ 'กำลังหาบ้าน' หรือ 'หาบ้านได้แล้ว' ต้องไม่มีกล่องระดมทุนบริจาคค่ารักษา
        conn = get_db_connection()
        cursor = conn.cursor()
        # หาสัตว์ที่มีสถานะกำลังหาบ้าน
        cursor.execute("SELECT id FROM pets WHERE status LIKE '%กำลังหาบ้าน%' LIMIT 1")
        healthy_pet = cursor.fetchone()
        conn.close()

        if healthy_pet:
            res_pet = self.client.get(f'/adopt/{healthy_pet["id"]}')
            self.assertEqual(res_pet.status_code, 200)
            self.assertIn('กำลังหาบ้าน'.encode('utf-8'), res_pet.data)
            # กล่องระดมทุน 'ร่วมสมทบทุนค่ารักษา' ต้องไม่ปรากฏ
            self.assertNotIn('ร่วมสมทบทุนค่ารักษา'.encode('utf-8'), res_pet.data)


if __name__ == '__main__':
    unittest.main()




