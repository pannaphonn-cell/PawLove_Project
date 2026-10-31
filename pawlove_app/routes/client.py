"""
ระบบฝั่งผู้ใช้งานทั่วไป (Client Routes - หน้าบ้าน)
ครอบคลุม:
1. หน้าหลัก (ข้อมูลโครงการ และ การทำงาน 4 ด้าน) (ตามข้อกำหนดที่ 4)
2. เกี่ยวกับเรา (ตามข้อกำหนดที่ 4)
3. หน้ารับเลี้ยง สุนัข/แมว, ขั้นตอน 5 ข้อ, สิทธิประโยชน์ (ตามข้อกำหนดที่ 9)
4. แบบฟอร์ม 9.1 การสอบถามข้อมูลเบื้องต้นในการรับเลี้ยง (ตามข้อกำหนดที่ 9.1)
5. หน้าให้ความช่วยเหลือ: เพิ่มสัตว์หาบ้าน พร้อมเงื่อนไขยืนยัน (ตามข้อกำหนดที่ 3 และ 2)
6. หน้าขอยื่นแก้ไขข้อมูลสัตว์จากผู้ใช้ (ตามข้อกำหนดที่ 2)
7. หน้าบริจาค (รับโดเนทเฉพาะสัตว์ป่วย/รอช่วยเหลือ) (ตามข้อกำหนดที่ 3 และ 4)
8. หน้าติดต่อเรา (E-Mail, Facebook, Instagram, TikTok) (ตามข้อกำหนดที่ 4)
9. หน้าแจ้งเตือนข่าวสาร การอัปเดต และการอนุมัติจากแอดมิน (ตามข้อกำหนดที่ 4)
"""

import json
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from database import get_db_connection
from utils import save_uploaded_pet_image, get_timeline_for_status, STATUS_TIMELINES, verify_bank_transfer_slip

client_bp = Blueprint('client', __name__, url_prefix='')


def get_site_content(key_name, default_title="", default_content=""):
    """
    ฟังก์ชันผู้ช่วยดึงข้อมูลเนื้อหาเว็บไซต์จากตาราง site_content
    - คืนค่าดิกชันนารีที่มี title และ content
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM site_content WHERE key_name = ?", (key_name,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return row
    return {'key_name': key_name, 'title': default_title, 'content': default_content}


@client_bp.route('/')
def index():
    """
    ฟังก์ชันแสดงหน้าหลักของผู้ใช้ (ข้อกำหนดที่ 4 - เมนูที่ 1)
    - แสดง:
      1. ข้อมูลโครงการ PawLove
      2. การทำงานของโครงการ 4 ด้าน (ดูแลการรักษา, การทำหมัน, การช่วยเหลือฉุกเฉิน, ศูนย์พักพิงชั่วคราว)
      3. ไฮไลต์สัตว์ที่กำลังหาบ้านและสัตว์ที่ต้องการการรักษา
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # ดึงข้อมูลโครงการและการทำงาน
    cursor.execute("SELECT * FROM site_content WHERE key_name IN ('project_info', 'project_work')")
    contents = {row['key_name']: row['content'] for row in cursor.fetchall()}

    # แปลง JSON ข้อมูลการทำงานของโครงการ 4 ด้าน
    project_work = {}
    if 'project_work' in contents:
        try:
            project_work = json.loads(contents['project_work'])
        except Exception:
            project_work = {}

    # ดึงสัตว์ตัวอย่างที่อนุมัติแล้วมาแสดงในหน้าแรก
    cursor.execute('''
    SELECT * FROM pets WHERE is_approved = 1 ORDER BY id DESC LIMIT 6
    ''')
    featured_pets = cursor.fetchall()

    # ดึงข่าวสารและกิจกรรมล่าสุดที่เผยแพร่แล้ว (เรียงจากใหม่สุด)
    cursor.execute('''
    SELECT * FROM news WHERE is_published = 1 ORDER BY id DESC LIMIT 10
    ''')
    latest_news = cursor.fetchall()
    latest_news_list = [dict(n) for n in latest_news]
    latest_news_json = json.dumps(latest_news_list, ensure_ascii=False)

    conn.close()

    return render_template('client/index.html',
                           project_info=contents.get('project_info', ''),
                           project_work=project_work,
                           featured_pets=featured_pets,
                           latest_news=latest_news,
                           latest_news_json=latest_news_json)


@client_bp.route('/about')
def about():
    """
    ฟังก์ชันแสดงหน้าเกี่ยวกับเรา (ข้อกำหนดที่ 4 - เมนูที่ 4)
    - ลิงก์เข้าแสดง:
      1. ข้อมูลโครงการ PawLove
      2. การทำงานของโครงการอย่างละเอียด 4 ด้าน (ดูแลการรักษา, การทำหมัน, การช่วยเหลือฉุกเฉิน, ศูนย์พักพิงชั่วคราว)
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM site_content WHERE key_name IN ('project_info', 'project_work')")
    contents = {row['key_name']: row['content'] for row in cursor.fetchall()}
    conn.close()

    project_work = {}
    if 'project_work' in contents:
        try:
            project_work = json.loads(contents['project_work'])
        except Exception:
            project_work = {}

    return render_template('client/about.html',
                           project_info=contents.get('project_info', ''),
                           project_work=project_work)


@client_bp.route('/adopt')
def adopt():
    """
    ฟังก์ชันแสดงหน้ารับเลี้ยงสัตว์ (ข้อกำหนดที่ 9)
    - แยกหมวดหมู่เป็น 'สุนัข' และ 'แมว' (ผ่าน Query Parameter ?species=สุนัข หรือ แมว หรือ ทั้งหมด)
    - แสดงการ์ดข้อมูลสัตว์:
      (รูปสัตว์, ชื่อ, อายุ(เดือน/ปี), เพศ, สายพันธุ์, ผู้ดูแลปัจจุบัน, ที่อยู่ปัจจุบัน, สถานะปัจจุบัน, รายละเอียด, รายละเอียดเพิ่มเติม)
    - แสดงขั้นตอนการรับเลี้ยง 5 ขั้นตอนครบถ้วน
    - แสดงสิ่งที่จะได้รับจากการรับเลี้ยงจาก PawLove 6 ข้อครบถ้วน
    """
    species_filter = request.args.get('species', 'ทั้งหมด')
    search_query = request.args.get('q', '').strip()

    conn = get_db_connection()
    cursor = conn.cursor()

    query = "SELECT * FROM pets WHERE is_approved = 1"
    params = []

    if species_filter in ['สุนัข', 'แมว']:
        query += " AND species = ?"
        params.append(species_filter)

    if search_query:
        query += " AND (name LIKE ? OR breed LIKE ? OR current_address LIKE ?)"
        wildcard = f"%{search_query}%"
        params.extend([wildcard, wildcard, wildcard])

    query += " ORDER BY id DESC"
    cursor.execute(query, params)
    pets = cursor.fetchall()
    conn.close()

    return render_template('client/adopt.html', pets=pets, current_species=species_filter, search_query=search_query)


@client_bp.route('/adopt/<int:pet_id>')
def pet_detail(pet_id):
    """
    ฟังก์ชันแสดงรายละเอียดสัตว์แต่ละตัวแบบเจาะลึก
    - แสดงข้อมูลสัตว์ครบถ้วน
    - แสดงไทม์ไลน์ประวัติการอัปเดตสถานะของสัตว์ (วันที่ เวลา และรายละเอียด ตามข้อกำหนดที่ 6)
    - มีปุ่มเชื่อมโยงไปยังแบบฟอร์ม 9.1 ขอรับเลี้ยงสัตว์ตัวนี้
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM pets WHERE id = ? AND is_approved = 1", (pet_id,))
    pet = cursor.fetchone()

    if not pet:
        conn.close()
        flash("ไม่พบข้อมูลสัตว์ที่ท่านต้องการ หรือยังไม่ได้รับการอนุมัติ", "warning")
        return redirect(url_for('client.adopt'))

    # ดึงประวัติการอัปเดตสถานะ (ข้อกำหนดที่ 6)
    cursor.execute('''
    SELECT * FROM pet_status_updates WHERE pet_id = ? ORDER BY id DESC
    ''', (pet_id,))
    updates = cursor.fetchall()

    # ดึงยอดบริจาคที่ได้รับจริงสำหรับน้องตัวนี้
    cursor.execute('''
    SELECT COALESCE(SUM(amount), 0.0) as total FROM donations 
    WHERE pet_id = ? AND (is_verified = 1 OR is_verified IS NULL)
    ''', (pet_id,))
    received_row = cursor.fetchone()
    received_amount = float(received_row['total'] or 0.0)
    target_amount = float(pet['donation_target'] or 0.0)
    if target_amount <= 0:
        target_amount = 5000.0  # ค่าเริ่มต้นหากไม่ได้ตั้งไว้
    remaining_amount = max(0.0, target_amount - received_amount)
    progress_percent = min(100, int((received_amount / target_amount) * 100)) if target_amount > 0 else 0
    conn.close()

    timeline_info = get_timeline_for_status(pet['status'])
    return render_template('client/pet_detail.html', pet=pet, updates=updates, timeline_info=timeline_info,
                           target_amount=target_amount, received_amount=received_amount,
                           remaining_amount=remaining_amount, progress_percent=progress_percent)


@client_bp.route('/adopt/<int:pet_id>/apply', methods=['GET', 'POST'])
def adopt_application(pet_id):
    """
    ฟังก์ชันแบบฟอร์มการสอบถามข้อมูลเบื้องต้นในการรับเลี้ยง (ข้อกำหนดที่ 9.1)
    - ต้องเข้าสู่ระบบก่อนจึงจะกรอกข้อมูลยื่นแบบฟอร์มได้
    """
    if 'user_id' not in session:
        flash("กรุณาเข้าสู่ระบบก่อนยื่นแบบฟอร์มขอรับเลี้ยงสัตว์", "warning")
        return redirect(url_for('auth.login'))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM pets WHERE id = ? AND is_approved = 1", (pet_id,))
    pet = cursor.fetchone()

    if not pet:
        conn.close()
        flash("ไม่พบสัตว์ที่ต้องการรับเลี้ยง", "danger")
        return redirect(url_for('client.adopt'))

    if request.method == 'POST':
        applicant_name = request.form.get('applicant_name', '').strip()
        address = request.form.get('address', '').strip()
        postal_code = request.form.get('postal_code', '').strip()
        email = request.form.get('email', '').strip()
        confirm_email = request.form.get('confirm_email', '').strip()
        phone = request.form.get('phone', '').strip()
        other_contacts = request.form.get('other_contacts', '').strip()
        nearest_airport = request.form.get('nearest_airport', '').strip()
        household_members = request.form.get('household_members', '').strip()
        household_agreement = request.form.get('household_agreement', '').strip()
        other_pets = request.form.get('other_pets', '').strip()
        house_description = request.form.get('house_description', '').strip()
        job_and_hours = request.form.get('job_and_hours', '').strip()
        reason_and_about = request.form.get('reason_and_about', '').strip()
        terms_accepted = request.form.get('terms_accepted')

        # ตรวจสอบอีเมลตรงกัน
        if email.lower() != confirm_email.lower():
            flash("อีเมลและการยืนยันอีเมลไม่ตรงกัน", "danger")
            conn.close()
            return render_template('client/adopt_form.html', pet=pet, form=request.form)

        # ตรวจสอบการยอมรับเงื่อนไข
        if not terms_accepted:
            flash("กรุณาทำเครื่องหมายติ๊กยอมรับเงื่อนไขการรับเลี้ยงสัตว์", "danger")
            conn.close()
            return render_template('client/adopt_form.html', pet=pet, form=request.form)

        user_id = session.get('user_id')

        cursor.execute('''
        INSERT INTO adoption_applications (
            pet_id, user_id, applicant_name, address, postal_code, email, phone,
            other_contacts, nearest_airport, household_members, household_agreement,
            other_pets, house_description, job_and_hours, reason_and_about, terms_accepted
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        ''', (
            pet_id, user_id, applicant_name, address, postal_code, email, phone,
            other_contacts, nearest_airport, household_members, household_agreement,
            other_pets, house_description, job_and_hours, reason_and_about
        ))

        # ส่งการแจ้งเตือนกลับไปยังผู้ใช้
        if user_id:
            cursor.execute('''
            INSERT INTO notifications (user_id, title, message)
            VALUES (?, ?, ?)
            ''', (user_id, f"ยื่นคำขอรับเลี้ยง '{pet['name']}' สำเร็จ",
                  f"ระบบได้รับแบบฟอร์มการสอบถามข้อมูลเบื้องต้นเพื่อขอรับเลี้ยงน้อง {pet['name']} แล้ว เจ้าหน้าที่จะติดต่อสัมภาษณ์ผ่านวิดีโอคอลต่อไป"))

        conn.commit()
        conn.close()

        flash(f"ส่งแบบฟอร์มขอรับเลี้ยงน้อง '{pet['name']}' เรียบร้อยแล้ว! เจ้าหน้าที่จะติดต่อสัมภาษณ์ทางวิดีโอคอลต่อไป ขอบพระคุณครับ", "success")
        return redirect(url_for('client.pet_detail', pet_id=pet_id))

    conn.close()
    return render_template('client/adopt_form.html', pet=pet, form={})


@client_bp.route('/help-pet', methods=['GET', 'POST'])
def help_pet():
    """
    ฟังก์ชันหน้า 'ให้ความช่วยเหลือ' (เพิ่มสัตว์ที่ผู้ใช้อยากหาบ้านให้) (ข้อกำหนดที่ 3 และ 4)
    - ต้องมีข้อตกลงและเงื่อนไขให้ยืนยันก่อนเสมอ (Terms modal / confirmation)
    - ข้อมูลสัตว์ที่ต้องใส่:
      1. ชนิดสัตว์ (สุนัข/แมว)
      2. ชื่อ
      3. อายุ (ปี และ เดือน)
      4. เพศ (เพศผู้ / เพศเมีย)
      5. สายพันธุ์
      6. ชื่อผู้ดูแลในปัจจุบัน
      7. ที่อยู่ของสัตว์ในปัจจุบัน
      8. สถานะของสัตว์ปัจจุบัน (1.กำลังหาบ้าน(สุขภาพดี), 2.กำลังอยู่ระหว่างการรักษา, 3.รอรับการช่วยเหลือ, 4.หาบ้านได้แล้ว)
      9. รายละเอียดของสัตว์เพิ่มเติม
      10. รูปภาพ
    - ส่งข้อมูลเป็นคำขอ (Request) ไปให้แอดมินอนุมัติก่อนเสมอ (ตามข้อกำหนดที่ 2)
    """
    if 'user_id' not in session:
        flash("กรุณาเข้าสู่ระบบก่อนเพิ่มข้อมูลสัตว์ที่ต้องการหาบ้าน", "warning")
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        terms_confirmed = request.form.get('terms_confirmed')
        if not terms_confirmed:
            flash("ท่านต้องอ่านและยืนยันข้อตกลงและเงื่อนไขก่อนส่งข้อมูลสัตว์เสมอ", "danger")
            return render_template('client/help_pet.html')

        species = request.form.get('species', 'สุนัข')
        name = request.form.get('name', '').strip()
        age_years = int(request.form.get('age_years') or 0)
        age_months = int(request.form.get('age_months') or 0)
        gender = request.form.get('gender', 'เพศผู้')
        breed = request.form.get('breed', '').strip()
        caretaker_name = request.form.get('caretaker_name', '').strip()
        current_address = request.form.get('current_address', '').strip()
        status = request.form.get('status', 'กำลังหาบ้าน(สุขภาพดี)')
        donation_target = float(request.form.get('donation_target') or 0.0)
        description = request.form.get('description', '').strip()
        extra_details = request.form.get('extra_details', '').strip()

        # จัดการไฟล์รูปภาพสัตว์ที่อัปโหลด (Choose File)
        uploaded_image = request.files.get('pet_image')
        saved_image_url = save_uploaded_pet_image(uploaded_image) if uploaded_image else None
        image_url = saved_image_url or request.form.get('image_url', '').strip()

        if not name or not breed or not caretaker_name or not current_address or not description:
            flash("กรุณากรอกข้อมูลสำคัญของสัตว์ให้ครบถ้วน", "danger")
            return render_template('client/help_pet.html')

        if not image_url:
            # รูปสำรองหากผู้ใช้ไม่ได้อัปโหลดรูป
            image_url = "https://images.unsplash.com/photo-1543466835-00a7907e9de1?w=800&auto=format&fit=crop&q=60"

        pet_data = {
            'species': species,
            'name': name,
            'age_years': age_years,
            'age_months': age_months,
            'gender': gender,
            'breed': breed,
            'caretaker_name': caretaker_name,
            'current_address': current_address,
            'status': status,
            'donation_target': donation_target,
            'description': description,
            'extra_details': extra_details,
            'image_url': image_url
        }

        conn = get_db_connection()
        cursor = conn.cursor()

        # บันทึกคำขอเพิ่มสัตว์ไปยังตาราง pet_requests รอแอดมินอนุมัติ (ข้อกำหนดที่ 2)
        cursor.execute('''
        INSERT INTO pet_requests (request_type, pet_id, user_id, proposed_data, status)
        VALUES ('add', NULL, ?, ?, 'pending')
        ''', (session['user_id'], json.dumps(pet_data, ensure_ascii=False)))

        # ส่งการแจ้งเตือนยืนยันให้ผู้ใช้
        cursor.execute('''
        INSERT INTO notifications (user_id, title, message)
        VALUES (?, ?, ?)
        ''', (session['user_id'], f"ส่งคำขอเพิ่มสัตว์ '{name}' สำเร็จ",
              f"คำขอเพิ่มน้อง '{name}' ของคุณถูกส่งไปยังทีมงานแอดมินเรียบร้อยแล้ว กำลังรอการตรวจสอบและอนุมัติ"))

        conn.commit()
        conn.close()

        flash(f"ส่งข้อมูลน้อง '{name}' เรียบร้อยแล้ว! คำขอจะถูกตรวจสอบและอนุมัติโดยแอดมินก่อนแสดงผลในหน้ารับเลี้ยง", "success")
        return redirect(url_for('client.notifications'))

    return render_template('client/help_pet.html')


@client_bp.route('/my-pets')
def my_pets():
    """
    ฟังก์ชันแสดงรายการสัตว์ที่ผู้ใช้รายนี้เคยสร้างไว้
    - เพื่อให้ผู้ใช้สามารถขอยื่นแก้ไขข้อมูลได้ (ซึ่งต้องรอแอดมินอนุมัติ ตามข้อกำหนดที่ 2)
    """
    if 'user_id' not in session:
        flash("กรุณาเข้าสู่ระบบก่อน", "warning")
        return redirect(url_for('auth.login'))

    conn = get_db_connection()
    cursor = conn.cursor()
    # สัตว์ที่ได้รับการอนุมัติแล้วของผู้ใช้
    cursor.execute("SELECT * FROM pets WHERE created_by = ? ORDER BY id DESC", (session['user_id'],))
    my_pets_list = cursor.fetchall()

    # คำขอที่ยังรออนุมัติของผู้ใช้
    cursor.execute('''
    SELECT * FROM pet_requests WHERE user_id = ? ORDER BY id DESC
    ''', (session['user_id'],))
    my_requests = cursor.fetchall()
    conn.close()

    parsed_requests = []
    for req in my_requests:
        req_dict = dict(req)
        try:
            req_dict['data'] = json.loads(req['proposed_data'])
        except Exception:
            req_dict['data'] = {}
        parsed_requests.append(req_dict)

    return render_template('client/my_pets.html', pets=my_pets_list, requests=parsed_requests)


@client_bp.route('/pet/<int:pet_id>/request-edit', methods=['GET', 'POST'])
def request_edit_pet(pet_id):
    """
    ฟังก์ชันส่งคำขอแก้ไขข้อมูลสัตว์จากผู้ใช้ (ข้อกำหนดที่ 2: การแก้ไขข้อมูลจากผู้ใช้ต้องให้แอดมินอนุมัติ)
    - ผู้ใช้กรอกข้อมูลที่ต้องการแก้ไข
    - บันทึกคำขอเป็นประเภท 'edit' ในตาราง pet_requests
    - ส่งแจ้งเตือนไปยังแอดมินเพื่อรออนุมัติ
    """
    if 'user_id' not in session:
        flash("กรุณาเข้าสู่ระบบก่อนแก้ไขข้อมูล", "warning")
        return redirect(url_for('auth.login'))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM pets WHERE id = ?", (pet_id,))
    pet = cursor.fetchone()

    if not pet:
        conn.close()
        flash("ไม่พบข้อมูลสัตว์ที่ต้องการแก้ไข", "danger")
        return redirect(url_for('client.my_pets'))

    if request.method == 'POST':
        # จัดการไฟล์รูปภาพสัตว์ที่อัปโหลดใหม่ (Choose File)
        uploaded_image = request.files.get('pet_image')
        saved_image_url = save_uploaded_pet_image(uploaded_image) if uploaded_image else None
        image_url = saved_image_url or request.form.get('image_url', '').strip() or pet['image_url']

        proposed_data = {
            'species': request.form.get('species', pet['species']),
            'name': request.form.get('name', pet['name']).strip(),
            'age_years': int(request.form.get('age_years') or pet['age_years']),
            'age_months': int(request.form.get('age_months') or pet['age_months']),
            'gender': request.form.get('gender', pet['gender']),
            'breed': request.form.get('breed', pet['breed']).strip(),
            'caretaker_name': request.form.get('caretaker_name', pet['caretaker_name']).strip(),
            'current_address': request.form.get('current_address', pet['current_address']).strip(),
            'status': request.form.get('status', pet['status']),
            'donation_target': float(request.form.get('donation_target') or pet['donation_target'] or 0.0),
            'description': request.form.get('description', pet['description']).strip(),
            'extra_details': request.form.get('extra_details', pet['extra_details']).strip(),
            'image_url': image_url
        }

        # บันทึกคำขอแก้ไขข้อมูลลง pet_requests
        cursor.execute('''
        INSERT INTO pet_requests (request_type, pet_id, user_id, proposed_data, status)
        VALUES ('edit', ?, ?, ?, 'pending')
        ''', (pet_id, session['user_id'], json.dumps(proposed_data, ensure_ascii=False)))

        # ส่งการแจ้งเตือนยืนยันให้ผู้ใช้
        cursor.execute('''
        INSERT INTO notifications (user_id, title, message)
        VALUES (?, ?, ?)
        ''', (session['user_id'], f"ส่งคำขอแก้ไขข้อมูล '{pet['name']}' สำเร็จ",
              f"คำขอแก้ไขข้อมูลน้อง '{pet['name']}' ถูกส่งให้แอดมินพิจารณาอนุมัติเรียบร้อยแล้ว"))

        conn.commit()
        conn.close()

        flash(f"ยื่นคำขอแก้ไขข้อมูลน้อง '{pet['name']}' เรียบร้อยแล้ว! ข้อมูลจะถูกปรับปรุงเมื่อแอดมินอนุมัติ", "success")
        return redirect(url_for('client.my_pets'))

    conn.close()
    return render_template('client/edit_my_pet.html', pet=pet)


@client_bp.route('/donate', methods=['GET', 'POST'])
def donate():
    """
    ฟังก์ชันหน้าบริจาค (ข้อกำหนดที่ 4 - เมนูที่ 7)
    - ต้องเข้าสู่ระบบก่อนจึงจะสามารถกรอกข้อมูลบริจาคได้ (ดูได้อย่างเดียวหากยังไม่ล็อกอิน)
    - สรุปยอดรวมบริจาค: รายวัน, รายเดือน, รายปี
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        if 'user_id' not in session:
            flash("กรุณาเข้าสู่ระบบก่อนร่วมบริจาค", "warning")
            return redirect(url_for('auth.login'))

        donor_name = request.form.get('donor_name', 'ผู้ไม่ประสงค์ออกนาม').strip()
        amount = float(request.form.get('amount') or 0)
        message = request.form.get('message', '').strip()
        pet_id = request.form.get('pet_id')
        pet_id = int(pet_id) if pet_id and pet_id != '' else None
        anon = bool(request.form.get('anon'))
        if anon:
            donor_name = "ผู้ไม่ประสงค์ออกนาม"

        # ตรวจสอบหลักฐานสลีปโอนเงิน (Thai Bank Slip Verification Engine)
        slip_file = request.files.get('slip_file')
        is_valid_slip, slip_msg, slip_url, ref_code = verify_bank_transfer_slip(slip_file)

        if not is_valid_slip:
            flash(slip_msg, "danger")
        elif amount <= 0:
            flash("กรุณาระบุจำนวนเงินบริจาคที่ถูกต้อง (ตั้งแต่ 1 บาทขึ้นไป)", "danger")
        else:
            cursor.execute('''
            INSERT INTO donations (pet_id, donor_name, amount, message, slip_url, is_verified, verification_info, transfer_ref)
            VALUES (?, ?, ?, ?, ?, 1, ?, ?)
            ''', (pet_id, donor_name, amount, message, slip_url, slip_msg, ref_code))
            conn.commit()
            flash(f"ขอขอบพระคุณคุณ {donor_name} ที่ร่วมบริจาคจำนวน {amount:,.2f} บาท! {slip_msg}", "success")
            conn.close()
            return redirect(url_for('client.donate'))

    # คำนวณยอดบริจาครวม: รายวัน รายเดือน รายปี
    today_str = datetime.now().strftime('%Y-%m-%d')
    this_month_str = datetime.now().strftime('%Y-%m')
    this_year_str = datetime.now().strftime('%Y')

    cursor.execute("SELECT COALESCE(SUM(amount), 0.0) as total FROM donations WHERE DATE(created_at) = DATE(?)", (today_str,))
    donations_daily = float(cursor.fetchone()['total'] or 0.0)

    cursor.execute("SELECT COALESCE(SUM(amount), 0.0) as total FROM donations WHERE strftime('%Y-%m', created_at) = ?", (this_month_str,))
    donations_monthly = float(cursor.fetchone()['total'] or 0.0)

    cursor.execute("SELECT COALESCE(SUM(amount), 0.0) as total FROM donations WHERE strftime('%Y', created_at) = ?", (this_year_str,))
    donations_yearly = float(cursor.fetchone()['total'] or 0.0)

    # ดึงข้อมูลสัตว์ที่อยู่ในสถานะรับโดเนทเท่านั้น (สถานะ 2 และ 3)
    cursor.execute('''
    SELECT * FROM pets 
    WHERE is_approved = 1 
      AND (status LIKE '%กำลังอยู่ระหว่างการรักษา%' OR status LIKE '%รอรับการช่วยเหลือ%')
    ORDER BY id DESC
    ''')
    needy_pets = cursor.fetchall()

    # ดึงข้อความโครงการเกี่ยวกับการบริจาค
    cursor.execute("SELECT content FROM site_content WHERE key_name = 'donation_info'")
    donation_row = cursor.fetchone()
    donation_info = donation_row['content'] if donation_row else ""

    # ดึงประวัติการบริจาคล่าสุด
    cursor.execute("SELECT * FROM donations ORDER BY id DESC LIMIT 10")
    recent_donations = cursor.fetchall()
    conn.close()

    selected_pet_id = request.args.get('pet_id', type=int)

    return render_template('client/donate.html',
                           needy_pets=needy_pets,
                           donation_info=donation_info,
                           recent_donations=recent_donations,
                           selected_pet_id=selected_pet_id,
                           donations_daily=donations_daily,
                           donations_monthly=donations_monthly,
                           donations_yearly=donations_yearly)


@client_bp.route('/contact')
def contact():
    """
    ฟังก์ชันหน้าติดต่อเรา (ข้อกำหนดที่ 4 - เมนูที่ 8)
    - แสดงช่องทางการติดต่อครบถ้วน: E-Mail, Facebook, Instagram, TikTok
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT content FROM site_content WHERE key_name = 'contact_info'")
    contact_row = cursor.fetchone()
    conn.close()

    contact_info = {}
    if contact_row:
        try:
            contact_info = json.loads(contact_row['content'])
        except Exception:
            contact_info = {}

    return render_template('client/contact.html', contact=contact_info)


@client_bp.route('/notifications')
def notifications():
    """
    ฟังก์ชันหน้าแจ้งเตือนข่าวสาร การอัปเดต และการอนุมัติจากแอดมิน (ข้อกำหนดที่ 4 - เมนูที่ 9)
    - แสดงข่าวสารทั่วไปของโครงการ
    - แสดงผลการอนุมัติคำขอเพิ่มสัตว์และแก้ไขสัตว์เฉพาะบุคคลที่ล็อกอินอยู่
    """
    user_id = session.get('user_id')
    conn = get_db_connection()
    cursor = conn.cursor()

    if user_id:
        cursor.execute('''
        SELECT * FROM notifications 
        WHERE user_id IS NULL OR user_id = ? 
        ORDER BY id DESC
        ''', (user_id,))
    else:
        cursor.execute('''
        SELECT * FROM notifications 
        WHERE user_id IS NULL 
        ORDER BY id DESC
        ''')

    notifs = cursor.fetchall()
    conn.close()

    return render_template('client/notifications.html', notifications=notifs)
