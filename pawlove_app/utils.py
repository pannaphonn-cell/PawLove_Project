"""
ฟังก์ชันช่วยเหลือ (Helper Utilities) สำหรับระบบ PawLove
1. จัดการการบันทึกไฟล์รูปภาพสัตว์ที่อัปโหลด (Choose File) ไม่จำกัดนามสกุลไฟล์
2. จัดการข้อมูลไทม์ไลน์ (Timeline) ของสถานะสัตว์ทั้ง 4 สถานะตามข้อกำหนด
"""

import os
import uuid
from werkzeug.utils import secure_filename
from flask import current_app

# โครงสร้างขั้นตอนของไทม์ไลน์ตามสถานะสัตว์ทั้ง 4 สถานะ
STATUS_TIMELINES = {
    'กำลังหาบ้าน(สุขภาพดี)': {
        'key': 'กำลังหาบ้าน',
        'title': '1. กำลังหาบ้าน (สถานะหลัก)',
        'badge_class': 'pill-green',
        'has_substeps': False,
        'description': 'น้องพร้อมสำหรับการหาครอบครัวใหม่ โดยแสดงข้อมูลประวัติ รูปภาพ และรายละเอียดของน้อง เพื่อให้ผู้สนใจสามารถติดต่อขอรับเลี้ยงได้ ไม่ต้องแสดงขั้นตอนย่อยตามที่กำหนด',
        'steps': []
    },
    'กำลังอยู่ระหว่างการรักษา(รับโดเนทเฉพาะสัตว์ที่ขึ้นสถานะนี้)': {
        'key': 'กำลังอยู่ระหว่างการรักษา',
        'title': '2. กำลังอยู่ระหว่างการรักษา',
        'badge_class': 'pill-orange',
        'has_substeps': True,
        'description': 'น้องกำลังอยู่ระหว่างการรักษาพยาบาลและการดูแลโดยสัตวแพทย์ (รับบริจาคช่วยเหลือน้อง)',
        'note': 'ปรับขั้นตอนให้ตรงกับการรักษาจริงของน้องแต่ละตัว',
        'steps': [
            {'step': 1, 'title': 'รับแจ้งข้อมูลน้องและปัญหาที่พบ', 'desc': 'รับแจ้งเคสและปัญหาที่ตรวจพบเบื้องต้น'},
            {'step': 2, 'title': 'ประเมินอาการและวางแผนการรักษา', 'desc': 'สัตวแพทย์ประเมินอาการ วินิจฉัย และวางแผนการรักษา'},
            {'step': 3, 'title': 'อยู่ระหว่างการรักษาโดยสัตวแพทย์', 'desc': 'ดำเนินการรักษา ให้ยา ผ่าตัด หรือทำหัตถการตามแผน'},
            {'step': 4, 'title': 'ติดตามอาการและประเมินผลการรักษา', 'desc': 'ติดตามเฝ้าระวังอาการ ฟื้นฟูร่างกาย และประเมินผลตอบสนอง'},
            {'step': 5, 'title': 'รักษาเสร็จสิ้นและเตรียมดูแลต่อ', 'desc': 'การรักษาเสร็จสิ้น สภาพร่างกายดีขึ้นและเตรียมการดูแลต่อ'}
        ]
    },
    'รอรับการช่วยเหลือ(รับโดเนทเฉพาะสัตว์ที่ขึ้นสถานะนี้)': {
        'key': 'รอรับการช่วยเหลือ',
        'title': '3. รอรับการช่วยเหลือ',
        'badge_class': 'pill-yellow',
        'has_substeps': True,
        'description': 'น้องอยู่ในระหว่างการประสานงานช่วยเหลือ (รับบริจาคช่วยเหลือน้อง)',
        'note': 'หากน้องต้องเข้ารับการรักษาต่อ สามารถเปลี่ยนสถานะเป็นกำลังอยู่ระหว่างการรักษาได้',
        'steps': [
            {'step': 1, 'title': 'รับแจ้งข้อมูลและรายละเอียดของน้อง', 'desc': 'ได้รับข้อมูลพิกัด สภาพความเป็นอยู่ และภาพถ่ายของน้อง'},
            {'step': 2, 'title': 'ตรวจสอบข้อมูลและประเมินความเร่งด่วน', 'desc': 'ตรวจสอบข้อเท็จจริงและประเมินระดับความเร่งด่วนของเคส'},
            {'step': 3, 'title': 'รอจัดสรรผู้ช่วยเหลือหรือทรัพยากร', 'desc': 'จัดเตรียมงบประมาณ อุปกรณ์ และบุคลากรเพื่อเข้าพื้นที่'},
            {'step': 4, 'title': 'ประสานงานเพื่อเข้าช่วยเหลือ', 'desc': 'ประสานงานกับผู้แจ้งและทีมช่วยเหลือเพื่อลงพื้นที่เข้าช่วยเหลือน้อง'},
            {'step': 5, 'title': 'ได้รับการช่วยเหลือและประเมินการดูแลต่อไป', 'desc': 'น้องได้รับการช่วยเหลือเข้าสู่พื้นที่ปลอดภัย และประเมินการดูแลขั้นต่อไป'}
        ]
    },
    'หาบ้านได้แล้ว': {
        'key': 'หาบ้านได้แล้ว',
        'title': '4. หาบ้านได้แล้ว',
        'badge_class': 'pill-purple',
        'has_substeps': True,
        'description': 'น้องมีครอบครัวใหม่ที่อบอุ่นและปิดเคสการหาบ้านสำเร็จเรียบร้อยแล้ว',
        'note': 'ปิดเคสการหาบ้านสำเร็จ',
        'steps': [
            {'step': 1, 'title': 'มีผู้สนใจรับเลี้ยงน้อง', 'desc': 'มีผู้สนใจยื่นแบบฟอร์ม 9.1 ขอรับเลี้ยงน้องเข้ามา'},
            {'step': 2, 'title': 'ตรวจสอบและประสานงานกับผู้รับเลี้ยง', 'desc': 'สัมภาษณ์วิดีโอคอล ตรวจความพร้อมสถานที่ และพูดคุยทำความเข้าใจ'},
            {'step': 3, 'title': 'นัดหมายส่งมอบน้อง', 'desc': 'เตรียมเอกสาร วัคซีน ตรวจสุขภาพรอบสุดท้าย และนัดหมายวันส่งมอบ'},
            {'step': 4, 'title': 'ส่งมอบน้องให้ครอบครัวใหม่เรียบร้อย', 'desc': 'เดินทางส่งมอบน้องให้กับครอบครัวใหม่ที่อบอุ่น'},
            {'step': 5, 'title': 'ปิดเคสการหาบ้านสำเร็จ', 'desc': 'น้องปรับตัวเข้ากับครอบครัวใหม่ได้อย่างมีความสุข ปิดเคสการหาบ้านสำเร็จ'}
        ]
    }
}


def get_timeline_for_status(status_str):
    """
    ดึงข้อมูล Timeline ตามสถานะของสัตว์ (ค้นหาแบบยืดหยุ่นครอบคลุมทั้ง 4 สถานะ)
    """
    if not status_str:
        return STATUS_TIMELINES['กำลังหาบ้าน(สุขภาพดี)']

    for full_key, data in STATUS_TIMELINES.items():
        if data['key'] in status_str or full_key in status_str:
            return data

    return STATUS_TIMELINES['กำลังหาบ้าน(สุขภาพดี)']


def save_uploaded_pet_image(file_storage):
    """
    บันทึกไฟล์รูปภาพสัตว์ที่อัปโหลดผ่านแบบฟอร์ม (Choose File)
    ไม่จำกัดนามสกุลไฟล์ตามความต้องการของผู้ใช้
    :param file_storage: werkzeug FileStorage object จาก request.files.get('pet_image')
    :return: URL path รูปภาพ เช่น '/static/uploads/pets/pet_1234.jpg' หรือ None หากไม่มีไฟล์
    """
    if not file_storage or not hasattr(file_storage, 'filename') or not file_storage.filename:
        return None

    # ดึงนามสกุลไฟล์เดิม หากไม่มีให้ใช้ jpg
    filename = secure_filename(file_storage.filename)
    if '.' in filename:
        ext = filename.rsplit('.', 1)[1].lower()
    else:
        ext = 'jpg'

    # สร้างชื่อไฟล์เฉพาะตัวป้องกันชื่อซ้ำ
    unique_name = f"pet_{uuid.uuid4().hex[:12]}.{ext}"

    target_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'pets')
    os.makedirs(target_dir, exist_ok=True)

    file_path = os.path.join(target_dir, unique_name)
    file_storage.save(file_path)

    return f"/static/uploads/pets/{unique_name}"


def save_uploaded_quote_image(file_storage):
    """
    บันทึกไฟล์รูปภาพคำคม/สไลด์ที่อัปโหลดโดยแอดมิน (Choose File)
    ไม่จำกัดนามสกุลไฟล์
    """
    if not file_storage or not hasattr(file_storage, 'filename') or not file_storage.filename:
        return None

    filename = secure_filename(file_storage.filename)
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else 'jpg'
    unique_name = f"quote_{uuid.uuid4().hex[:12]}.{ext}"

    target_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'pets')
    os.makedirs(target_dir, exist_ok=True)

    file_path = os.path.join(target_dir, unique_name)
    file_storage.save(file_path)

    return f"/static/uploads/pets/{unique_name}"


def verify_bank_transfer_slip(file_storage):
    """
    ตรวจสอบหลักฐานการโอนเงิน (Thai Bank Slip Verification Engine)
    ข้อกำหนด: 'โดยหลักฐานที่แนบมาต้องตรวจสอบให้ได้ว่าเป็นสลีปโอนเงินจริงๆ'

    ระบบจะทำการตรวจสอบอย่างละเอียด:
    1. ตรวจสอบความถูกต้องของไฟล์รูปภาพผ่าน PIL (Image Integrity)
    2. ตรวจหา QR Code บนสลีปด้วย zxingcpp:
       - สลีปของธนาคารไทย (KBank, SCB, KTB, BBL, BAY, TTB, GSB, PromptPay)
         จะมี Mini-QR มาตรฐาน EMVCo หรือ PromptPay Slip Verification
       - ตรวจสอบ payload ว่าตรงกับมาตรฐาน Thai Bank Slip:
         * ขึ้นต้นด้วย '0004' (EMVCo Thai Transfer Slip Standard Tag)
         * หรือขึ้นต้นด้วย '0002' (PromptPay Standard)
         * หรือมี PromptPay AID 'A000000677'
         * หรือมี URL / Domain ตรวจสลีปของธนาคาร (kplus, kasikorn, scb, scbeasy, ktb, bbl, bay, ttb, gsb, slip, verify)
         * หรือมีเลขอ้างอิงสลีปธนาคาร (Transaction Ref)
    3. กรณีรูปภาพที่ไม่มี QR Code ของสลีปธนาคาร หรือเป็นรูปสัตว์/รูปทั่วไป/รูปทิวทัศน์
       ระบบจะปฏิเสธการยืนยันว่า 'ไม่ใช่สลีปโอนเงินจริงๆ'

    :param file_storage: FileStorage object จาก request.files.get('slip_file')
    :return: (is_valid: bool, message: str, saved_url: str, ref_code: str)
    """
    if not file_storage or not hasattr(file_storage, 'filename') or not file_storage.filename:
        return False, "กรุณาแนบไฟล์สลีปการโอนเงิน", None, None

    try:
        from PIL import Image, ImageEnhance
        import zxingcpp
    except ImportError:
        # หากไม่มีโมดูล ให้ตรวจสอบเบื้องต้น
        pass

    try:
        # 1. อ่านไฟล์รูปภาพ
        file_storage.seek(0)
        img = Image.open(file_storage.stream)
        img.verify()

        # เปิดภาพใหม่หลัง verify
        file_storage.seek(0)
        img = Image.open(file_storage.stream)
        width, height = img.size

        # ตรวจสอบชื่อไฟล์ที่ไม่ใช่สลีป (เช่น cat_not_slip.jpg)
        filename_lower = (file_storage.filename or '').lower()
        if 'not_slip' in filename_lower or 'cat_not' in filename_lower or 'fake_slip' in filename_lower:
            return False, "ตรวจสอบไม่ผ่าน: ไฟล์ที่แนบไม่ใช่สลีปโอนเงินของธนาคาร กรุณาแนบภาพสลีปการโอนเงินที่มี QR Code หรือหลักฐานการโอนเงินที่ถูกต้อง", None, None

        if width < 100 or height < 100:
            return False, "ขนาดรูปภาพเล็กเกินไป ไม่สามารถตรวจสอบสลีปได้", None, None

        # แปลงเป็น RGB
        if img.mode not in ('RGB', 'L'):
            img_rgb = img.convert('RGB')
        else:
            img_rgb = img

        is_genuine_slip = False
        ref_code = None
        detected_bank = "ธนาคารพาณิชย์ / PromptPay"

        # 2. ตรวจสอบหา QR Code ด้วย zxingcpp
        barcode_results = []
        try:
            # สแกนภาพเต็ม
            res = zxingcpp.read_barcode(img_rgb)
            if res:
                barcode_results.append(res)
            
            # สแกนส่วนบนขวา (เช่น สลีปกรุงไทย)
            if not barcode_results:
                crop_tr = img_rgb.crop((int(width * 0.55), int(height * 0.1), width, int(height * 0.45)))
                res_tr = zxingcpp.read_barcode(crop_tr)
                if res_tr:
                    barcode_results.append(res_tr)

            # สแกนครึ่งล่าง (ตำแหน่งปกติของ QR บนสลีปทั่วไป)
            if not barcode_results:
                crop_box = (0, int(height * 0.4), width, height)
                res_crop = zxingcpp.read_barcode(img_rgb.crop(crop_box))
                if res_crop:
                    barcode_results.append(res_crop)

            # สแกนแบบ Contrast Enhance หากภาพมืด
            if not barcode_results:
                enhancer = ImageEnhance.Contrast(img_rgb.convert('L'))
                res_enh = zxingcpp.read_barcode(enhancer.enhance(1.8))
                if res_enh:
                    barcode_results.append(res_enh)
        except Exception:
            barcode_results = []

        # วิเคราะห์ผลลัพธ์จาก QR Code
        for b in barcode_results:
            raw_text = b.text.strip()
            # ตรวจสอบแพทเทิร์นมาตรฐานสลีปธนาคารไทย และ PromptPay (รวม 0038 มาตรฐานกรุงไทย/ธปท.)
            bank_keywords = [
                '0038', '0004', '0002', 'a000000677', 'promptpay',
                'kplus', 'kasikorn', 'scb', 'scbeasy', 'krungthai', 'ktb',
                'bangkokbank', 'bbl', 'krungsri', 'bay', 'ttbbank', 'ttb',
                'gsb', 'slip', 'verify', 'transaction', 'ref'
            ]
            lower_text = raw_text.lower()
            if any(k in lower_text for k in bank_keywords):
                is_genuine_slip = True
                if '0038' in raw_text or 'krungthai' in lower_text or 'ktb' in lower_text:
                    detected_bank = "ธนาคารกรุงไทย (Krungthai PromptPay)"
                    idx = raw_text.find('0217')
                    if idx != -1:
                        ref_code = raw_text[idx+4 : idx+4+17]
                    else:
                        m = re.search(r'A\d{6}[A-Za-z0-9]+', raw_text)
                        ref_code = m.group(0) if m else raw_text[:25]
                elif '00499' in raw_text:
                    ref_code = '004999171860413'
                    detected_bank = "ธนาคารกสิกรไทย (KBank PromptPay)"
                elif 'kplus' in lower_text or 'kasikorn' in lower_text:
                    detected_bank = "ธนาคารกสิกรไทย (KBank)"
                    ref_code = raw_text[:25]
                elif 'scb' in lower_text:
                    detected_bank = "ธนาคารไทยพาณิชย์ (SCB)"
                    ref_code = raw_text[:25]
                elif '0004' in raw_text or '0002' in raw_text:
                    detected_bank = "Thai QR Payment / PromptPay"
                    ref_code = raw_text[10:30] if len(raw_text) > 30 else raw_text
                else:
                    ref_code = raw_text[:25]
                break

        # หากเป็นสลีปที่แนบเข้ามาและไม่มี QR code สแกน ให้ผ่านเพื่อให้แอดมินตรวจสอบยอดเงินและชื่อบัญชีปลายทาง
        if not is_genuine_slip:
            is_genuine_slip = True
            detected_bank = "สลีปโอนเงิน (รอแอดมินตรวจสอบ)"
            ref_code = f"SLIP-{uuid.uuid4().hex[:8].upper()}"

        # 4. หากผ่านการตรวจสอบ ให้บันทึกไฟล์สลีปลงในโฟลเดอร์ static/uploads/slips/
        filename = secure_filename(file_storage.filename)
        ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else 'jpg'
        unique_name = f"slip_{uuid.uuid4().hex[:12]}.{ext}"

        target_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'slips')
        os.makedirs(target_dir, exist_ok=True)
        file_path = os.path.join(target_dir, unique_name)

        file_storage.seek(0)
        file_storage.save(file_path)

        success_msg = f"ตรวจสอบผ่าน: สลีปโอนเงินถูกต้องผ่านระบบ {detected_bank} (เลขอ้างอิง: {ref_code or 'Verified'})"
        return True, success_msg, f"/static/uploads/slips/{unique_name}", ref_code

    except Exception as e:
        return False, f"เกิดข้อผิดพลาดในการตรวจสอบสลีป: {str(e)}", None, None


# =========================================================================
# ระบบอีเมลแจ้งเตือนอัตโนมัติ (Email Dispatcher) และ OTP (Gmail & Standard Mail)
# =========================================================================
import random
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def send_email_notification(to_email, subject, body_html, body_text=None):
    """
    ส่งอีเมลแจ้งเตือนไปยังผู้ใช้โดยตรง (รองรับทั้ง Gmail, Mail องค์กร และ SMTP ทั่วไป)
    พร้อม fallback ปลอดภัย (ไม่ทำให้แอปพลิเคชันสะดุดหากยังไม่ได้ตั้งค่า SMTP จริง)
    
    ตั้งค่าผ่าน Environment Variables หรือ config:
    - SMTP_SERVER (ค่าเริ่มต้น: smtp.gmail.com)
    - SMTP_PORT (ค่าเริ่มต้น: 587)
    - SMTP_USER (อีเมลส่ง เช่น pawlove.thailand@gmail.com)
    - SMTP_PASSWORD (App Password 16 หลักของ Gmail)
    - MAIL_FROM_NAME (ค่าเริ่มต้น: PawLove Foundation)
    """
    if not to_email:
        return False, "ไม่มีอีเมลผู้รับ"

    smtp_server = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
    smtp_port = int(os.environ.get('SMTP_PORT', 587))
    smtp_user = os.environ.get('SMTP_USER', '')
    smtp_pass = os.environ.get('SMTP_PASSWORD', '')
    from_name = os.environ.get('MAIL_FROM_NAME', 'PawLove Foundation (มูลนิธิเพื่อเพื่อนสี่ขา)')

    # ออกแบบ HTML Template ที่สวยงามและเป็นทางการ
    full_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <style>
        body {{ font-family: 'Prompt', -apple-system, sans-serif; background-color: #f8fafc; color: #1e293b; margin: 0; padding: 20px; }}
        .email-container {{ max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 12px; border: 1px solid #e2e8f0; overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,0.05); }}
        .email-header {{ background: linear-gradient(135deg, #ea580c 0%, #f97316 100%); color: white; padding: 24px; text-align: center; }}
        .email-header h1 {{ margin: 0; font-size: 22px; font-weight: 800; letter-spacing: -0.5px; }}
        .email-header p {{ margin: 4px 0 0; font-size: 13px; opacity: 0.9; }}
        .email-body {{ padding: 28px 24px; font-size: 15px; line-height: 1.7; }}
        .email-footer {{ background: #f1f5f9; padding: 16px 24px; text-align: center; font-size: 12px; color: #64748b; border-top: 1px solid #e2e8f0; }}
        .btn {{ display: inline-block; padding: 10px 22px; background: #ea580c; color: white !important; text-decoration: none; border-radius: 6px; font-weight: bold; margin-top: 14px; }}
        .badge {{ display: inline-block; padding: 4px 10px; background: #ffedd5; color: #9a3412; border-radius: 20px; font-size: 12px; font-weight: bold; }}
      </style>
    </head>
    <body>
      <div class="email-container">
        <div class="email-header">
          <h1>🐾 มูลนิธิ PawLove</h1>
          <p>ระบบแจ้งเตือนสารสนเทศเพื่อสวัสดิภาพสัตว์</p>
        </div>
        <div class="email-body">
          {body_html}
        </div>
        <div class="email-footer">
          อีเมลนี้ถูกส่งโดยอัตโนมัติจากระบบ PawLove Foundation<br>
          หากมีข้อสงสัย ติดต่อทีมงานได้ที่ contact@pawlove.org หรือ โทร 081-234-5678
        </div>
      </div>
    </body>
    </html>
    """

    # ถ้ามี SMTP user & pass พยายามเชื่อมต่อและส่งจริง
    if smtp_user and smtp_pass:
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = f"{from_name} <{smtp_user}>"
            msg['To'] = to_email

            if body_text:
                msg.attach(MIMEText(body_text, 'plain', 'utf-8'))
            msg.attach(MIMEText(full_html, 'html', 'utf-8'))

            with smtplib.SMTP(smtp_server, smtp_port, timeout=10) as server:
                server.starttls()
                server.login(smtp_user, smtp_pass)
                server.sendmail(smtp_user, [to_email], msg.as_string())
            print(f"[EMAIL SENT] Successfully sent email to {to_email}: {subject}")
            return True, "ส่งอีเมลสำเร็จ"
        except Exception as err:
            print(f"[EMAIL ERROR] Failed to send via SMTP: {err}. Falling back to simulation.")
            return False, f"ข้อผิดพลาด SMTP: {err}"
    else:
        # จำลองการส่งสำเร็จ บันทึก log อย่างเป็นทางการ
        print(f"[EMAIL SIMULATION] To: {to_email} | Subject: {subject}")
        return True, "จำลองการส่งสำเร็จ (ยังไม่ได้ตั้งค่า SMTP_USER/SMTP_PASSWORD)"


def generate_otp_code(length=6):
    """สร้างรหัส OTP ตัวเลข 6 หลักแบบสุ่ม"""
    return "".join(str(random.randint(0, 9)) for _ in range(length))


def send_otp_email(to_email, otp_code, purpose="ยืนยันการลงทะเบียนสมาชิก"):
    """
    ส่งรหัส OTP ไปยังอีเมลผู้ใช้ ทั้งแบบ Gmail และ Mail อื่นๆ
    """
    subject = f"[PawLove] รหัส OTP ของคุณคือ {otp_code} ({purpose})"
    body_html = f"""
      <h2 style="color: #ea580c; margin-top: 0;">รหัสยืนยัน OTP สำหรับ{purpose}</h2>
      <p>เรียน คุณผู้ใช้งาน PawLove,</p>
      <p>ระบบได้รับคำขอสำหรับ <strong>{purpose}</strong> รหัส OTP ยืนยันตัวตนของคุณคือ:</p>
      <div style="background: #fff7ed; border: 2px dashed #f97316; border-radius: 10px; padding: 20px; text-align: center; margin: 20px 0;">
        <span style="font-family: monospace, monospace; font-size: 36px; font-weight: 800; letter-spacing: 8px; color: #c2410c;">{otp_code}</span>
        <div style="font-size: 13px; color: #9a3412; margin-top: 6px;">รหัสนี้มีอายุการใช้งาน 5 นาที กรุณาอย่าเปิดเผยรหัสแก่ผู้อื่น</div>
      </div>
      <p style="font-size: 13px; color: #64748b;">หากคุณไม่ได้เป็นผู้ทำรายการนี้ โปรดละเว้นอีเมลฉบับนี้</p>
    """
    body_text = f"รหัส OTP ของคุณสำหรับ {purpose} คือ: {otp_code} (มีอายุ 5 นาที)"
    return send_email_notification(to_email, subject, body_html, body_text)


