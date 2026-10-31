"""
ระบบฝั่งผู้ดูแลระบบ (Admin Routes - หลังบ้าน)
ครอบคลุม:
1. การควบคุมสิทธิ์การเข้าถึงหลังบ้าน (Decorators)
2. แผงควบคุมหลัก Dashboard
3. การจัดการสัตว์ทั้งหมด (เพิ่ม, แก้ไข, ลบ)
4. การอัปเดตสถานะของสัตว์พร้อมบันทึกรายละเอียด วันที่ 
5. การจัดการและแก้ไขบัญชีผู้ใช้รายอื่นได้ทั้งหมด
6. การจัดการคำขอจากผู้ใช้: อนุมัติ/ปฏิเสธ คำขอเพิ่มสัตว์และแก้ไขสัตว์
7. การแก้ไขเนื้อหาเว็บไซต์ทั้งหมด (หน้าหลัก, เกี่ยวกับเรา, ติดต่อเรา, ข้อมูลบริจาค)
8. การจัดการคำขอรับเลี้ยงสัตว์ (แบบฟอร์ม)
"""

import json
from functools import wraps
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash
from database import get_db_connection
from utils import (save_uploaded_pet_image, save_uploaded_quote_image,
                   get_timeline_for_status, STATUS_TIMELINES, send_email_notification)


# เดคอเรเตอร์ตรวจสอบสิทธิ์แอดมิน
# - ตรวจสอบว่าผู้ใช้ล็อกอินอยู่และมีบทบาทเป็น 'admin'
# - หากไม่ใช่ จะส่งไปยังหน้า Admin Login
admin_bp = Blueprint('admin', __name__, url_prefix='/admin')
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('user_role') != 'admin':
            flash("หน้านี้สำหรับผู้ดูแลระบบเท่านั้น กรุณากรอกอีเมลแอดมินเพื่อเข้าสู่ระบบ", "danger")
            return redirect(url_for('auth.admin_direct_access'))
        return f(*args, **kwargs)
    return decorated_function


# ฟังก์ชันรองรับเส้นทาง /admin และ /admin/ (ป้องกัน 404 Not Found)
# - หากล็อกอินเป็นแอดมินอยู่แล้ว จะนำทางไปยังหน้า dashboard (/admin/dashboard)
# - หากยังไม่ได้ล็อกอิน จะนำทางไปยังหน้ากรอกอีเมลแอดมินโดยตรง (/admin-access)
@admin_bp.route('')
@admin_bp.route('/')
def admin_root():
    if 'user_id' in session and session.get('user_role') == 'admin':
        return redirect(url_for('admin.dashboard'))
    return redirect(url_for('auth.admin_direct_access'))


# ฟังก์ชันแผงควบคุมหลักของระบบหลังบ้าน (Admin Dashboard)
# - รองรับการดูสรุปรวมแบบรายวัน (Day), รายเดือน (Month), รายปี (Year) และทั้งหมด (All)
# - สรุปยอดเงินบริจาค: รวม, กองทุนกลาง, สัตว์ที่รอรับการช่วยเหลือ, สัตว์ที่อยู่ระหว่างการรักษา
# - สรุปยอดคนเข้าระบบ: จำนวนครั้งทั้งหมด, จำนวนผู้ใช้ไม่ซ้ำ, และแยกผู้ใช้/แอดมิน
# - สรุปยอดสัตว์หาบ้านที่เพิ่มโดยผู้ใช้ (แยกหมา/แมว)
# - สรุปยอดสัตว์หาบ้านได้สำเร็จโดยที่เพิ่มจากผู้ใช้ (แยกหมา/แมว)
# - สรุปยอดสัตว์หาบ้านที่เพิ่มโดยแอดมิน (แยกหมา/แมว)
# - สรุปยอดสัตว์หาบ้านได้สำเร็จโดยที่เพิ่มจากแอดมิน (แยกหมา/แมว)
@admin_bp.route('/dashboard')
@admin_required
def dashboard():
    period = request.args.get('period', 'all')
    now = datetime.now()
    selected_date = request.args.get('date', now.strftime('%Y-%m-%d'))
    selected_month = request.args.get('month', now.strftime('%Y-%m'))
    selected_year = request.args.get('year', now.strftime('%Y'))

    # กำหนดเงื่อนไข SQL ตามตัวกรองเวลา
    if period == 'day':
        period_label = f"รายวัน (ประจำวันที่ {selected_date})"
        date_filter_don = "DATE(created_at) = DATE(?)"
        date_filter_don_d = "DATE(d.created_at) = DATE(?)"
        date_param_don = [selected_date]

        date_filter_pets = "DATE(p.created_at) = DATE(?)"
        date_param_pets = [selected_date]

        date_filter_logins = "DATE(created_at) = DATE(?)"
        date_param_logins = [selected_date]
    elif period == 'month':
        period_label = f"รายเดือน (ประจำเดือน {selected_month})"
        date_filter_don = "strftime('%Y-%m', created_at) = ?"
        date_filter_don_d = "strftime('%Y-%m', d.created_at) = ?"
        date_param_don = [selected_month]

        date_filter_pets = "strftime('%Y-%m', p.created_at) = ?"
        date_param_pets = [selected_month]

        date_filter_logins = "strftime('%Y-%m', created_at) = ?"
        date_param_logins = [selected_month]
    elif period == 'year':
        period_label = f"รายปี (ประจำปี {selected_year})"
        date_filter_don = "strftime('%Y', created_at) = ?"
        date_filter_don_d = "strftime('%Y', d.created_at) = ?"
        date_param_don = [selected_year]

        date_filter_pets = "strftime('%Y', p.created_at) = ?"
        date_param_pets = [selected_year]

        date_filter_logins = "strftime('%Y', created_at) = ?"
        date_param_logins = [selected_year]
    else:
        period = 'all'
        period_label = "สรุปรวมทั้งหมด (All Time)"
        date_filter_don = "1=1"
        date_filter_don_d = "1=1"
        date_param_don = []

        date_filter_pets = "1=1"
        date_param_pets = []

        date_filter_logins = "1=1"
        date_param_logins = []

    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. ยอดบริจาค (รวม กองทุนกลาง สัตว์ที่รอรับการช่วยเหลือ สัตว์ที่อยู่ระหว่างการรักษา)
    # 1.1 ยอดบริจาครวม
    cursor.execute(f'''
    SELECT COALESCE(SUM(amount), 0) as total, COUNT(*) as count 
    FROM donations 
    WHERE (is_verified = 1 OR is_verified IS NULL) AND {date_filter_don}
    ''', date_param_don)
    don_row = cursor.fetchone()
    donations_total = don_row['total'] or 0.0
    donations_count = don_row['count'] or 0

    # 1.2 กองทุนกลาง (pet_id IS NULL or target_type = 'general')
    cursor.execute(f'''
    SELECT COALESCE(SUM(amount), 0) as total 
    FROM donations 
    WHERE (is_verified = 1 OR is_verified IS NULL) 
      AND (pet_id IS NULL OR target_type = 'general')
      AND {date_filter_don}
    ''', date_param_don)
    donations_general = cursor.fetchone()['total'] or 0.0

    # 1.3 สัตว์ที่รอรับการช่วยเหลือ
    cursor.execute(f'''
    SELECT COALESCE(SUM(d.amount), 0) as total 
    FROM donations d
    LEFT JOIN pets p ON d.pet_id = p.id
    WHERE (d.is_verified = 1 OR d.is_verified IS NULL)
      AND (d.target_type = 'rescue' OR p.status LIKE '%รอ%')
      AND {date_filter_don_d}
    ''', date_param_don)
    donations_rescue = cursor.fetchone()['total'] or 0.0

    # 1.4 สัตว์ที่อยู่ระหว่างการรักษา
    cursor.execute(f'''
    SELECT COALESCE(SUM(d.amount), 0) as total 
    FROM donations d
    LEFT JOIN pets p ON d.pet_id = p.id
    WHERE (d.is_verified = 1 OR d.is_verified IS NULL)
      AND (d.target_type = 'medical' OR (p.id IS NOT NULL AND p.status LIKE '%รักษา%'))
      AND {date_filter_don_d}
    ''', date_param_don)
    donations_medical = cursor.fetchone()['total'] or 0.0

    # 2. ยอดคนเข้าระบบ
    cursor.execute(f'''
    SELECT COUNT(*) as total_logins, COUNT(DISTINCT email) as unique_users
    FROM user_logins
    WHERE {date_filter_logins}
    ''', date_param_logins)
    login_row = cursor.fetchone()
    total_logins = login_row['total_logins'] or 0
    unique_users = login_row['unique_users'] or 0

    cursor.execute(f'''
    SELECT 
      SUM(CASE WHEN role = 'user' THEN 1 ELSE 0 END) as user_logins,
      SUM(CASE WHEN role = 'admin' THEN 1 ELSE 0 END) as admin_logins
    FROM user_logins
    WHERE {date_filter_logins}
    ''', date_param_logins)
    role_logins = cursor.fetchone()
    user_logins = role_logins['user_logins'] or 0
    admin_logins = role_logins['admin_logins'] or 0

    # 3. ยอดสัตว์หาบ้านที่เพิ่มโดยผู้ใช้ (แยกหมาแมว)
    cursor.execute(f'''
    SELECT 
      SUM(CASE WHEN p.species = 'สุนัข' THEN 1 ELSE 0 END) as dogs,
      SUM(CASE WHEN p.species = 'แมว' THEN 1 ELSE 0 END) as cats,
      COUNT(*) as total
    FROM pets p
    JOIN users u ON p.created_by = u.id
    WHERE u.role = 'user' AND {date_filter_pets}
    ''', date_param_pets)
    pets_added_by_user = cursor.fetchone()
    user_pets_dog = pets_added_by_user['dogs'] or 0
    user_pets_cat = pets_added_by_user['cats'] or 0
    user_pets_total = pets_added_by_user['total'] or 0

    # 4. ยอดสัตว์หาบ้านได้สำเร็จโดยที่เพิ่มจากผู้ใช้ (แยกหมาแมว)
    cursor.execute(f'''
    SELECT 
      SUM(CASE WHEN p.species = 'สุนัข' THEN 1 ELSE 0 END) as dogs,
      SUM(CASE WHEN p.species = 'แมว' THEN 1 ELSE 0 END) as cats,
      COUNT(*) as total
    FROM pets p
    JOIN users u ON p.created_by = u.id
    WHERE u.role = 'user' 
      AND (p.status LIKE '%หาบ้านได้แล้ว%' OR p.status LIKE '%มีบ้านแล้ว%')
      AND {date_filter_pets}
    ''', date_param_pets)
    pets_adopted_by_user = cursor.fetchone()
    user_adopted_dog = pets_adopted_by_user['dogs'] or 0
    user_adopted_cat = pets_adopted_by_user['cats'] or 0
    user_adopted_total = pets_adopted_by_user['total'] or 0

    # 5. ยอดสัตว์หาบ้านที่เพิ่มโดยแอดมิน (แยกหมาแมว)
    cursor.execute(f'''
    SELECT 
      SUM(CASE WHEN p.species = 'สุนัข' THEN 1 ELSE 0 END) as dogs,
      SUM(CASE WHEN p.species = 'แมว' THEN 1 ELSE 0 END) as cats,
      COUNT(*) as total
    FROM pets p
    LEFT JOIN users u ON p.created_by = u.id
    WHERE (u.role = 'admin' OR p.created_by IS NULL OR u.id IS NULL)
      AND {date_filter_pets}
    ''', date_param_pets)
    pets_added_by_admin = cursor.fetchone()
    admin_pets_dog = pets_added_by_admin['dogs'] or 0
    admin_pets_cat = pets_added_by_admin['cats'] or 0
    admin_pets_total = pets_added_by_admin['total'] or 0

    # 6. ยอดสัตว์หาบ้านได้สำเร็จโดยที่เพิ่มจากแอดมิน (แยกหมาแมว)
    cursor.execute(f'''
    SELECT 
      SUM(CASE WHEN p.species = 'สุนัข' THEN 1 ELSE 0 END) as dogs,
      SUM(CASE WHEN p.species = 'แมว' THEN 1 ELSE 0 END) as cats,
      COUNT(*) as total
    FROM pets p
    LEFT JOIN users u ON p.created_by = u.id
    WHERE (u.role = 'admin' OR p.created_by IS NULL OR u.id IS NULL)
      AND (p.status LIKE '%หาบ้านได้แล้ว%' OR p.status LIKE '%มีบ้านแล้ว%')
      AND {date_filter_pets}
    ''', date_param_pets)
    pets_adopted_by_admin = cursor.fetchone()
    admin_adopted_dog = pets_adopted_by_admin['dogs'] or 0
    admin_adopted_cat = pets_adopted_by_admin['cats'] or 0
    admin_adopted_total = pets_adopted_by_admin['total'] or 0

    # ข้อมูลสถิติรวมของระบบ
    cursor.execute("SELECT COUNT(*) as count FROM pets")
    total_pets = cursor.fetchone()['count']

    cursor.execute("SELECT COUNT(*) as count FROM users")
    total_users = cursor.fetchone()['count']

    cursor.execute("SELECT COUNT(*) as count FROM pet_requests WHERE status = 'pending'")
    pending_requests = cursor.fetchone()['count']

    cursor.execute("SELECT COUNT(*) as count FROM adoption_applications WHERE status = 'รอการติดต่อสัมภาษณ์'")
    pending_adoptions = cursor.fetchone()['count']

    # คำขอล่าสุด 5 รายการ
    cursor.execute('''
    SELECT r.*, u.fullname as user_fullname, u.email as user_email
    FROM pet_requests r
    JOIN users u ON r.user_id = u.id
    WHERE r.status = 'pending'
    ORDER BY r.id DESC LIMIT 5
    ''')
    recent_requests_raw = cursor.fetchall()
    recent_requests = []
    for r in recent_requests_raw:
        item = dict(r)
        try:
            item['data'] = json.loads(r['proposed_data'])
        except Exception:
            item['data'] = {}
        recent_requests.append(item)

    # ประวัติการเข้าสู่ระบบล่าสุด 5 รายการ
    cursor.execute('''
    SELECT * FROM user_logins ORDER BY id DESC LIMIT 5
    ''')
    recent_logins = cursor.fetchall()

    conn.close()

    dashboard_data = {
        'period': period,
        'period_label': period_label,
        'selected_date': selected_date,
        'selected_month': selected_month,
        'selected_year': selected_year,
        # ยอดบริจาค
        'donations_total': donations_total,
        'donations_count': donations_count,
        'donations_general': donations_general,
        'donations_rescue': donations_rescue,
        'donations_medical': donations_medical,
        # ยอดคนเข้าระบบ
        'total_logins': total_logins,
        'unique_users': unique_users,
        'user_logins': user_logins,
        'admin_logins': admin_logins,
        'recent_logins': recent_logins,
        # ยอดสัตว์หาบ้านที่เพิ่มโดยผู้ใช้
        'user_pets_dog': user_pets_dog,
        'user_pets_cat': user_pets_cat,
        'user_pets_total': user_pets_total,
        # ยอดสัตว์หาบ้านได้สำเร็จโดยที่เพิ่มจากผู้ใช้
        'user_adopted_dog': user_adopted_dog,
        'user_adopted_cat': user_adopted_cat,
        'user_adopted_total': user_adopted_total,
        # ยอดสัตว์หาบ้านที่เพิ่มโดยแอดมิน
        'admin_pets_dog': admin_pets_dog,
        'admin_pets_cat': admin_pets_cat,
        'admin_pets_total': admin_pets_total,
        # ยอดสัตว์หาบ้านได้สำเร็จโดยที่เพิ่มจากแอดมิน
        'admin_adopted_dog': admin_adopted_dog,
        'admin_adopted_cat': admin_adopted_cat,
        'admin_adopted_total': admin_adopted_total,
    }

    return render_template('admin/dashboard.html',
                           total_pets=total_pets,
                           total_users=total_users,
                           pending_requests=pending_requests,
                           pending_adoptions=pending_adoptions,
                           recent_requests=recent_requests,
                           d=dashboard_data)


# ฟังก์ชันส่งออกข้อมูลแดชบอร์ด (Export to CSV / Sheets / Excel)
# ข้อกำหนด: ข้อมูลแดชบอร์ดสามารถปริ้นต์หรือลิงก์เข้าชีทได้ (ขอแบบสวยๆ)
@admin_bp.route('/dashboard/export-csv')
@admin_required
def dashboard_export_csv():
    import csv
    import io
    from flask import Response

    period = request.args.get('period', 'all')
    now = datetime.now()
    selected_date = request.args.get('date', now.strftime('%Y-%m-%d'))
    selected_month = request.args.get('month', now.strftime('%Y-%m'))
    selected_year = request.args.get('year', now.strftime('%Y'))

    # กำหนดเงื่อนไข SQL ตามตัวกรอง
    if period == 'day':
        period_label = f"รายวัน ({selected_date})"
        date_filter_don = "DATE(created_at) = DATE(?)"
        date_param_don = [selected_date]
        date_filter_pets = "DATE(p.created_at) = DATE(?)"
        date_param_pets = [selected_date]
        date_filter_logins = "DATE(created_at) = DATE(?)"
        date_param_logins = [selected_date]
    elif period == 'month':
        period_label = f"รายเดือน ({selected_month})"
        date_filter_don = "strftime('%Y-%m', created_at) = ?"
        date_param_don = [selected_month]
        date_filter_pets = "strftime('%Y-%m', p.created_at) = ?"
        date_param_pets = [selected_month]
        date_filter_logins = "strftime('%Y-%m', created_at) = ?"
        date_param_logins = [selected_month]
    elif period == 'year':
        period_label = f"รายปี ({selected_year})"
        date_filter_don = "strftime('%Y', created_at) = ?"
        date_param_don = [selected_year]
        date_filter_pets = "strftime('%Y', p.created_at) = ?"
        date_param_pets = [selected_year]
        date_filter_logins = "strftime('%Y', created_at) = ?"
        date_param_logins = [selected_year]
    else:
        period_label = "สรุปรวมทั้งหมด"
        date_filter_don = "1=1"
        date_param_don = []
        date_filter_pets = "1=1"
        date_param_pets = []
        date_filter_logins = "1=1"
        date_param_logins = []

    conn = get_db_connection()
    cursor = conn.cursor()

    # ดึงยอดบริจาค
    cursor.execute(f"SELECT COALESCE(SUM(amount), 0) as total, COUNT(*) as count FROM donations WHERE (is_verified = 1 OR is_verified IS NULL) AND {date_filter_don}", date_param_don)
    don_total_row = cursor.fetchone()
    don_total = float(don_total_row['total'] or 0.0)
    don_count = don_total_row['count'] or 0

    cursor.execute(f"SELECT COALESCE(SUM(amount), 0) as total FROM donations WHERE (is_verified = 1 OR is_verified IS NULL) AND (pet_id IS NULL OR target_type = 'general') AND {date_filter_don}", date_param_don)
    don_general = float(cursor.fetchone()['total'] or 0.0)

    cursor.execute(f"SELECT COALESCE(SUM(d.amount), 0) as total FROM donations d JOIN pets p ON d.pet_id = p.id WHERE (d.is_verified = 1 OR d.is_verified IS NULL) AND p.status LIKE '%รอรับการช่วยเหลือ%' AND {date_filter_don.replace('created_at', 'd.created_at')}", date_param_don)
    don_rescue = float(cursor.fetchone()['total'] or 0.0)

    cursor.execute(f"SELECT COALESCE(SUM(d.amount), 0) as total FROM donations d JOIN pets p ON d.pet_id = p.id WHERE (d.is_verified = 1 OR d.is_verified IS NULL) AND p.status LIKE '%กำลังอยู่ระหว่างการรักษา%' AND {date_filter_don.replace('created_at', 'd.created_at')}", date_param_don)
    don_medical = float(cursor.fetchone()['total'] or 0.0)

    # ผู้ใช้งาน
    cursor.execute(f"SELECT COUNT(*) as total FROM user_logins WHERE {date_filter_logins}", date_param_logins)
    logins_total = cursor.fetchone()['total'] or 0

    # สถิติสัตว์
    cursor.execute(f"SELECT SUM(CASE WHEN p.species = 'สุนัข' THEN 1 ELSE 0 END) as dogs, SUM(CASE WHEN p.species = 'แมว' THEN 1 ELSE 0 END) as cats, COUNT(*) as total FROM pets p JOIN users u ON p.created_by = u.id WHERE u.role != 'admin' AND {date_filter_pets}", date_param_pets)
    user_pets = cursor.fetchone()

    cursor.execute(f"SELECT SUM(CASE WHEN p.species = 'สุนัข' THEN 1 ELSE 0 END) as dogs, SUM(CASE WHEN p.species = 'แมว' THEN 1 ELSE 0 END) as cats, COUNT(*) as total FROM pets p JOIN users u ON p.created_by = u.id WHERE u.role != 'admin' AND p.status LIKE '%หาบ้านได้แล้ว%' AND {date_filter_pets}", date_param_pets)
    user_adopted = cursor.fetchone()

    cursor.execute(f"SELECT SUM(CASE WHEN p.species = 'สุนัข' THEN 1 ELSE 0 END) as dogs, SUM(CASE WHEN p.species = 'แมว' THEN 1 ELSE 0 END) as cats, COUNT(*) as total FROM pets p JOIN users u ON p.created_by = u.id WHERE u.role = 'admin' AND {date_filter_pets}", date_param_pets)
    admin_pets = cursor.fetchone()

    cursor.execute(f"SELECT SUM(CASE WHEN p.species = 'สุนัข' THEN 1 ELSE 0 END) as dogs, SUM(CASE WHEN p.species = 'แมว' THEN 1 ELSE 0 END) as cats, COUNT(*) as total FROM pets p JOIN users u ON p.created_by = u.id WHERE u.role = 'admin' AND p.status LIKE '%หาบ้านได้แล้ว%' AND {date_filter_pets}", date_param_pets)
    admin_adopted = cursor.fetchone()

    conn.close()

    # สร้างข้อมูล CSV พร้อม BOM สำหรับเปิดใน MS Excel / Google Sheets ภาษาไทยได้ 100%
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["PawLove Foundation - รายงานสรุปภาพรวมและสถิติแดชบอร์ด"])
    writer.writerow(["ช่วงเวลาที่เลือก", period_label])
    writer.writerow(["วันที่จัดทำรายงาน", datetime.now().strftime("%d/%m/%Y %H:%M น.")])
    writer.writerow([])
    writer.writerow(["หมวดหมู่ข้อมูล", "รายการ", "จำนวน / ยอดรวม", "หน่วย"])
    writer.writerow(["1. ยอดเงินบริจาค", "ยอดบริจาครวมทั้งหมด", f"{don_total:,.2f}", "บาท"])
    writer.writerow(["1. ยอดเงินบริจาค", "จำนวนรายการบริจาค", don_count, "ครั้ง"])
    writer.writerow(["1. ยอดเงินบริจาค", "กองทุนกลาง PawLove", f"{don_general:,.2f}", "บาท"])
    writer.writerow(["1. ยอดเงินบริจาค", "สัตว์ที่รอรับการช่วยเหลือ", f"{don_rescue:,.2f}", "บาท"])
    writer.writerow(["1. ยอดเงินบริจาค", "สัตว์ที่อยู่ระหว่างการรักษา", f"{don_medical:,.2f}", "บาท"])
    writer.writerow([])
    writer.writerow(["2. สถิติการเข้าสู่ระบบ", "ยอดการเข้าสู่ระบบทั้งหมด", logins_total, "ครั้ง"])
    writer.writerow([])
    writer.writerow(["3. สัตว์หาบ้าน (เพิ่มโดยผู้ใช้)", "สุนัข", user_pets['dogs'] or 0, "ตัว"])
    writer.writerow(["3. สัตว์หาบ้าน (เพิ่มโดยผู้ใช้)", "แมว", user_pets['cats'] or 0, "ตัว"])
    writer.writerow(["3. สัตว์หาบ้าน (เพิ่มโดยผู้ใช้)", "รวมทั้งสิ้น", user_pets['total'] or 0, "ตัว"])
    writer.writerow([])
    writer.writerow(["4. สัตว์หาบ้านสำเร็จ (จากผู้ใช้)", "สุนัข", user_adopted['dogs'] or 0, "ตัว"])
    writer.writerow(["4. สัตว์หาบ้านสำเร็จ (จากผู้ใช้)", "แมว", user_adopted['cats'] or 0, "ตัว"])
    writer.writerow(["4. สัตว์หาบ้านสำเร็จ (จากผู้ใช้)", "รวมทั้งสิ้น", user_adopted['total'] or 0, "ตัว"])
    writer.writerow([])
    writer.writerow(["5. สัตว์หาบ้าน (เพิ่มโดยแอดมิน)", "สุนัข", admin_pets['dogs'] or 0, "ตัว"])
    writer.writerow(["5. สัตว์หาบ้าน (เพิ่มโดยแอดมิน)", "แมว", admin_pets['cats'] or 0, "ตัว"])
    writer.writerow(["5. สัตว์หาบ้าน (เพิ่มโดยแอดมิน)", "รวมทั้งสิ้น", admin_pets['total'] or 0, "ตัว"])
    writer.writerow([])
    writer.writerow(["6. สัตว์หาบ้านสำเร็จ (จากแอดมิน)", "สุนัข", admin_adopted['dogs'] or 0, "ตัว"])
    writer.writerow(["6. สัตว์หาบ้านสำเร็จ (จากแอดมิน)", "แมว", admin_adopted['cats'] or 0, "ตัว"])
    writer.writerow(["6. สัตว์หาบ้านสำเร็จ (จากแอดมิน)", "รวมทั้งสิ้น", admin_adopted['total'] or 0, "ตัว"])

    csv_data = '\ufeff' + output.getvalue()
    filename = f"pawlove_dashboard_{period}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    return Response(
        csv_data,
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


# ฟังก์ชันแสดงรายการสัตว์ทั้งหมดในระบบหลังบ้าน
# - สามารถค้นหาและกรองตามชนิดหรือสถานะได้
# - มีปุ่มจัดการ: แก้ไขข้อมูล, อัปเดตสถานะ, และลบสัตว์
@admin_bp.route('/pets')
@admin_required
def pets_list():
    species = request.args.get('species', '')
    status = request.args.get('status', '')

    conn = get_db_connection()
    cursor = conn.cursor()

    query = "SELECT * FROM pets WHERE 1=1"
    params = []

    if species:
        query += " AND species = ?"
        params.append(species)
    if status:
        query += " AND status LIKE ?"
        params.append(f"%{status}%")

    query += " ORDER BY id DESC"
    cursor.execute(query, params)
    pets = cursor.fetchall()
    conn.close()

    return render_template('admin/pets_manage.html', pets=pets, selected_species=species, selected_status=status)


# ฟังก์ชันเพิ่มข้อมูลสัตว์โดยแอดมินโดยตรง (อนุมัติทันที)
# - บันทึกข้อมูลสัตว์พร้อมประวัติสถานะเริ่มต้น
@admin_bp.route('/pets/add', methods=['GET', 'POST'])
@admin_required
def pet_add():
    if request.method == 'POST':
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

        if not image_url:
            image_url = "https://images.unsplash.com/photo-1543466835-00a7907e9de1?w=800&auto=format&fit=crop&q=60"

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
        INSERT INTO pets (
            species, name, age_years, age_months, gender, breed, caretaker_name,
            current_address, status, donation_target, description, extra_details, image_url,
            created_by, is_approved
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        ''', (
            species, name, age_years, age_months, gender, breed, caretaker_name,
            current_address, status, donation_target, description, extra_details, image_url,
            session['user_id']
        ))
        pet_id = cursor.lastrowid

        # บันทึกประวัติสถานะตั้งต้น (ข้อกำหนดที่ 6)
        now_str = datetime.now().strftime("%d/%m/%Y %H:%M น.")
        cursor.execute('''
        INSERT INTO pet_status_updates (pet_id, status, details, updated_at, updated_by)
        VALUES (?, ?, ?, ?, ?)
        ''', (pet_id, status, f"แอดมินเพิ่มข้อมูลสัตว์เข้าสู่ระบบพร้อมสถานะ '{status}'", now_str, session.get('user_name', 'แอดมิน PawLove')))

        conn.commit()
        conn.close()

        flash(f"เพิ่มข้อมูลสัตว์น้อง '{name}' สำเร็จเรียบร้อย!", "success")
        return redirect(url_for('admin.pets_list'))

    return render_template('admin/pet_form.html', pet=None, title="เพิ่มสัตว์ใหม่ (แอดมิน)")


# ฟังก์ชันแก้ไขข้อมูลสัตว์โดยแอดมิน
# - แอดมินสามารถอัปเดตทุกฟิลด์ของสัตว์ได้โดยตรงทันที
@admin_bp.route('/pets/<int:pet_id>/edit', methods=['GET', 'POST'])
@admin_required
def pet_edit(pet_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM pets WHERE id = ?", (pet_id,))
    pet = cursor.fetchone()

    if not pet:
        conn.close()
        flash("ไม่พบสัตว์ที่ต้องการแก้ไข", "danger")
        return redirect(url_for('admin.pets_list'))

    if request.method == 'POST':
        species = request.form.get('species', pet['species'])
        name = request.form.get('name', pet['name']).strip()
        age_years = int(request.form.get('age_years') or pet['age_years'])
        age_months = int(request.form.get('age_months') or pet['age_months'])
        gender = request.form.get('gender', pet['gender'])
        breed = request.form.get('breed', pet['breed']).strip()
        caretaker_name = request.form.get('caretaker_name', pet['caretaker_name']).strip()
        current_address = request.form.get('current_address', pet['current_address']).strip()
        status = request.form.get('status', pet['status'])
        donation_target = float(request.form.get('donation_target') or pet['donation_target'] or 0.0)
        description = request.form.get('description', pet['description']).strip()
        extra_details = request.form.get('extra_details', pet['extra_details']).strip()

        # จัดการไฟล์รูปภาพสัตว์ที่อัปโหลดใหม่ (Choose File)
        uploaded_image = request.files.get('pet_image')
        saved_image_url = save_uploaded_pet_image(uploaded_image) if uploaded_image else None
        image_url = saved_image_url or request.form.get('image_url', '').strip() or pet['image_url']

        old_status = pet['status']

        cursor.execute('''
        UPDATE pets SET
            species = ?, name = ?, age_years = ?, age_months = ?, gender = ?,
            breed = ?, caretaker_name = ?, current_address = ?, status = ?,
            donation_target = ?, description = ?, extra_details = ?, image_url = ?
        WHERE id = ?
        ''', (
            species, name, age_years, age_months, gender, breed, caretaker_name,
            current_address, status, donation_target, description, extra_details, image_url, pet_id
        ))

        # หากสถานะมีการเปลี่ยนแปลง บันทึกประวัติ Timeline อัตโนมัติ (ข้อกำหนดที่ 6)
        if old_status != status:
            now_str = datetime.now().strftime("%d/%m/%Y %H:%M น.")
            cursor.execute('''
            INSERT INTO pet_status_updates (pet_id, status, details, updated_at, updated_by)
            VALUES (?, ?, ?, ?, ?)
            ''', (pet_id, status, f"แอดมินปรับเปลี่ยนสถานะจาก '{old_status}' เป็น '{status}'", now_str, session.get('user_name', 'แอดมิน PawLove')))

        # ส่งอีเมลแจ้งเตือนไปยังผู้ใช้เจ้าของสัตว์เมื่อแอดมินแก้ไขข้อมูล
        if pet['created_by']:
            cursor.execute("SELECT fullname, email FROM users WHERE id = ?", (pet['created_by'],))
            owner_user = cursor.fetchone()
            if owner_user and owner_user['email']:
                update_sub = f"[PawLove] ข้อมูลของน้อง {name} ได้รับการอัปเดตโดยผู้ดูแลระบบ"
                update_html = f"""
                  <h2 style="color: #ea580c; margin-top: 0;">ข้อมูลสัตว์ที่คุณดูแลได้รับการอัปเดต</h2>
                  <p>เรียน คุณ {owner_user['fullname']},</p>
                  <p>ผู้ดูแลระบบได้ทำการแก้ไข/ปรับปรุงข้อมูลของน้อง <strong>{name}</strong> ({species}):</p>
                  <ul style="color: #334155; line-height: 1.8;">
                    <li><strong>สถานะ:</strong> {status}</li>
                    <li><strong>เป้าหมายยอดบริจาค:</strong> {donation_target:,.2f} บาท</li>
                    <li><strong>ที่อยู่ปัจจุบัน:</strong> {current_address}</li>
                  </ul>
                  <p>คุณสามารถเข้าสู่ระบบเพื่อตรวจสอบข้อมูลทั้งหมดได้ตลอดเวลา</p>
                """
                send_email_notification(owner_user['email'], update_sub, update_html, f"ข้อมูลของน้อง {name} ได้รับการอัปเดตเรียบร้อยแล้ว")

        conn.commit()
        conn.close()

        flash(f"อัปเดตข้อมูลสัตว์น้อง '{name}' สำเร็จเรียบร้อย!", "success")
        return redirect(url_for('admin.pets_list'))

    conn.close()
    return render_template('admin/pet_form.html', pet=pet, title=f"แก้ไขข้อมูล: {pet['name']}")


# ฟังก์ชันลบข้อมูลสัตว์ออกจากระบบ (แอดมินเท่านั้น)
@admin_bp.route('/pets/<int:pet_id>/delete', methods=['POST'])
@admin_required
def pet_delete(pet_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM pets WHERE id = ?", (pet_id,))
    pet = cursor.fetchone()
    if pet:
        cursor.execute("DELETE FROM pets WHERE id = ?", (pet_id,))
        cursor.execute("DELETE FROM pet_status_updates WHERE pet_id = ?", (pet_id,))
        cursor.execute("DELETE FROM adoption_applications WHERE pet_id = ?", (pet_id,))
        conn.commit()
        flash(f"ลบข้อมูลน้อง '{pet['name']}' ออกจากระบบเรียบร้อยแล้ว", "info")
    conn.close()
    return redirect(url_for('admin.pets_list'))


#  ฟังก์ชันอัปเดตสถานะของสัตว์พร้อมระบุรายละเอียด วันที่ และเวลา
#  - ตัวเลือกสถานะ 4 แบบ:
#    1. กำลังหาบ้าน(สุขภาพดี)
#    2. กำลังอยู่ระหว่างการรักษา
#    3. รอรับการช่วยเหลือ
#    4. หาบ้านได้แล้ว
#  - ระบุรายละเอียดการอัปเดต (เช่น ความคืบหน้าการรักษา, พฤติกรรม, ครอบครัวรับเลี้ยง)
#  - บันทึก วันที่ และเวลา ในการอัปเดตลงตาราง pet_status_updates
@admin_bp.route('/pets/<int:pet_id>/status-update', methods=['GET', 'POST'])
@admin_required
def pet_status_update(pet_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM pets WHERE id = ?", (pet_id,))
    pet = cursor.fetchone()

    if not pet:
        conn.close()
        flash("ไม่พบสัตว์ที่ระบุ", "danger")
        return redirect(url_for('admin.pets_list'))

    if request.method == 'POST':
        new_status = request.form.get('status')
        current_step = int(request.form.get('current_step') or 1)
        details = request.form.get('details', '').strip()
        custom_date = request.form.get('update_datetime', '').strip()

        # หากไม่ได้ระบุวันเวลาที่กำหนดเอง ให้ใช้วันที่และเวลาปัจจุบัน
        if custom_date:
            updated_at = custom_date
        else:
            updated_at = datetime.now().strftime("%d/%m/%Y %H:%M น.")

        timeline_data = get_timeline_for_status(new_status)
        if not details:
            if timeline_data.get('has_substeps') and 1 <= current_step <= len(timeline_data.get('steps', [])):
                details = f"ขั้นตอนที่ {current_step}: {timeline_data['steps'][current_step - 1]['title']}"
            else:
                details = f"อัปเดตสถานะเป็น '{new_status}'"

        # ปรับปรุงสถานะ ขั้นตอนปัจจุบัน และเป้าหมายยอดบริจาคในตาราง pets
        raw_target = request.form.get('donation_target')
        if raw_target is not None and raw_target.strip() != '':
            new_target = float(raw_target)
            cursor.execute("UPDATE pets SET status = ?, current_step = ?, donation_target = ? WHERE id = ?", (new_status, current_step, new_target, pet_id))
        else:
            cursor.execute("UPDATE pets SET status = ?, current_step = ? WHERE id = ?", (new_status, current_step, pet_id))

        # บันทึกลงใน Timeline ประวัติการอัปเดตสถานะ
        cursor.execute('''
        INSERT INTO pet_status_updates (pet_id, status, details, updated_at, updated_by)
        VALUES (?, ?, ?, ?, ?)
        ''', (pet_id, new_status, details, updated_at, session.get('user_name', 'แอดมิน PawLove')))

        # ส่งอีเมลแจ้งเตือนไปยังผู้ใช้เจ้าของเคสโดยตรง (ข้อกำหนด: ข้อมูลที่ถูกอัปเดตจากแอดมินจะส่งให้อีเมลผู้ใช้โดยตรง)
        if pet['created_by']:
            cursor.execute("SELECT fullname, email FROM users WHERE id = ?", (pet['created_by'],))
            owner_user = cursor.fetchone()
            if owner_user and owner_user['email']:
                email_sub = f"[PawLove] อัปเดตสถานะน้อง {pet['name']} เป็น '{new_status}'"
                email_html = f"""
                  <h2 style="color: #ea580c; margin-top: 0;">อัปเดตสถานะสัตว์ที่คุณดูแล</h2>
                  <p>เรียน คุณ {owner_user['fullname']},</p>
                  <p>แอดมิน PawLove ได้ทำการอัปเดตสถานะของน้อง <strong>{pet['name']}</strong> ({pet['species']}):</p>
                  <div style="background: #fff7ed; border-left: 4px solid #ea580c; padding: 14px 18px; margin: 16px 0; border-radius: 4px;">
                    <div style="font-size: 15px; font-weight: bold; color: #9a3412;">สถานะปัจจุบัน: {new_status} (ขั้นตอนที่ {current_step})</div>
                    <div style="margin-top: 6px; color: #431407;">{details}</div>
                    <div style="margin-top: 6px; font-size: 12px; color: #7c2d12;">อัปเดตเมื่อ: {updated_at} โดย {session.get('user_name', 'แอดมิน')}</div>
                  </div>
                  <p>คุณสามารถเข้าสู่ระบบเพื่อดูรายละเอียดและไทม์ไลน์ฉบับเต็มได้ที่เว็บไซต์</p>
                """
                send_email_notification(owner_user['email'], email_sub, email_html, details)

        conn.commit()
        conn.close()

        flash(f"อัปเดตสถานะน้อง '{pet['name']}' เป็น '{new_status}' (ขั้นตอนที่ {current_step}) พร้อมบันทึก Timeline และส่งอีเมลแจ้งผู้ใช้เรียบร้อย!", "success")
        return redirect(url_for('admin.pet_status_update', pet_id=pet_id))

    # ดึงประวัติการอัปเดตสถานะทั้งหมดของสัตว์ตัวนี้
    cursor.execute("SELECT * FROM pet_status_updates WHERE pet_id = ? ORDER BY id DESC", (pet_id,))
    history = cursor.fetchall()
    conn.close()

    timeline_info = get_timeline_for_status(pet['status'])
    return render_template('admin/pet_status_edit.html', pet=pet, history=history, timeline_info=timeline_info, status_timelines=STATUS_TIMELINES)

# ฟังก์ชันแจ้งเตือนและแสดงคำขอจากผู้ใช้ (ข้อกำหนดที่ 2 และ ข้อกำหนดที่ 5 - เมนูที่ 10)
#     - แสดงคำขอเพิ่มสัตว์ใหม่ (request_type = 'add')
#     - แสดงคำขอแก้ไขข้อมูลสัตว์เดิม (request_type = 'edit')
#     - แอดมินสามารถตรวจสอบข้อมูล เปรียบเทียบ และกดอนุมัติหรือปฏิเสธได้
@admin_bp.route('/requests')
@admin_required
def requests_list():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
    SELECT r.*, u.fullname as user_fullname, u.email as user_email
    FROM pet_requests r
    JOIN users u ON r.user_id = u.id
    ORDER BY CASE WHEN r.status = 'pending' THEN 0 ELSE 1 END, r.id DESC
    ''')
    requests_raw = cursor.fetchall()

    requests_parsed = []
    for r in requests_raw:
        item = dict(r)
        try:
            item['data'] = json.loads(r['proposed_data'])
        except Exception:
            item['data'] = {}

        # หากเป็นคำขอแก้ไข ให้ดึงข้อมูลปัจจุบันของสัตว์มาเทียบ
        if r['request_type'] == 'edit' and r['pet_id']:
            cursor.execute("SELECT * FROM pets WHERE id = ?", (r['pet_id'],))
            item['original_pet'] = cursor.fetchone()
        else:
            item['original_pet'] = None

        requests_parsed.append(item)

    conn.close()
    return render_template('admin/requests.html', requests=requests_parsed)


# ฟังก์ชันอนุมัติคำขอจากผู้ใช้
# - กรณี 'add': นำข้อมูลที่ผู้ใช้เสนอมาสร้างเป็นสัตว์ใหม่ในระบบ และตั้ง is_approved = 1
# - กรณี 'edit': นำข้อมูลใหม่ไปอัปเดตทับสัตว์เดิมในตาราง pets
# - อัปเดตสถานะคำขอเป็น 'approved'
# - ส่งการแจ้งเตือนไปยังผู้ใช้ว่าได้รับการอนุมัติเรียบร้อยแล้ว
@admin_bp.route('/requests/<int:request_id>/approve', methods=['POST'])
@admin_required
def request_approve(request_id):
    admin_notes = request.form.get('admin_notes', 'อนุมัติเรียบร้อย').strip()

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM pet_requests WHERE id = ?", (request_id,))
    req = cursor.fetchone()

    if not req or req['status'] != 'pending':
        conn.close()
        flash("ไม่พบคำขอนี้หรือคำขอนี้ได้รับการดำเนินการไปแล้ว", "warning")
        return redirect(url_for('admin.requests_list'))

    try:
        data = json.loads(req['proposed_data'])
    except Exception:
        data = {}

    now_str = datetime.now().strftime("%d/%m/%Y %H:%M น.")

    if req['request_type'] == 'add':
        # เพิ่มสัตว์ใหม่เข้าตาราง pets
        cursor.execute('''
        INSERT INTO pets (
            species, name, age_years, age_months, gender, breed, caretaker_name,
            current_address, status, donation_target, description, extra_details, image_url,
            created_by, is_approved
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        ''', (
            data.get('species', 'สุนัข'),
            data.get('name', 'ไม่ระบุชื่อ'),
            int(data.get('age_years', 0)),
            int(data.get('age_months', 0)),
            data.get('gender', 'เพศผู้'),
            data.get('breed', 'ไม่ระบุ'),
            data.get('caretaker_name', ''),
            data.get('current_address', ''),
            data.get('status', 'กำลังหาบ้าน(สุขภาพดี)'),
            float(data.get('donation_target') or 0.0),
            data.get('description', ''),
            data.get('extra_details', ''),
            data.get('image_url', ''),
            req['user_id']
        ))
        new_pet_id = cursor.lastrowid

        # บันทึกสถานะตั้งต้น
        cursor.execute('''
        INSERT INTO pet_status_updates (pet_id, status, details, updated_at, updated_by)
        VALUES (?, ?, ?, ?, ?)
        ''', (new_pet_id, data.get('status', 'กำลังหาบ้าน(สุขภาพดี)'),
              f"แอดมินอนุมัติคำขอเพิ่มสัตว์จากผู้ใช้: {admin_notes}", now_str, session.get('user_name', 'แอดมิน PawLove')))

        notif_msg = f"ยินดีด้วย! คำขอเพิ่มน้อง '{data.get('name')}' ของคุณได้รับการอนุมัติจากแอดมินแล้ว และกำลังแสดงผลในหน้ารับเลี้ยง"

    elif req['request_type'] == 'edit':
        pet_id = req['pet_id']
        cursor.execute('''
        UPDATE pets SET
            species = ?, name = ?, age_years = ?, age_months = ?, gender = ?,
            breed = ?, caretaker_name = ?, current_address = ?, status = ?,
            donation_target = ?, description = ?, extra_details = ?, image_url = ?
        WHERE id = ?
        ''', (
            data.get('species'), data.get('name'), int(data.get('age_years', 0)),
            int(data.get('age_months', 0)), data.get('gender'), data.get('breed'),
            data.get('caretaker_name'), data.get('current_address'), data.get('status'),
            float(data.get('donation_target') or 0.0),
            data.get('description'), data.get('extra_details'), data.get('image_url'),
            pet_id
        ))

        # บันทึกประวัติการอัปเดต
        cursor.execute('''
        INSERT INTO pet_status_updates (pet_id, status, details, updated_at, updated_by)
        VALUES (?, ?, ?, ?, ?)
        ''', (pet_id, data.get('status'), f"แอดมินอนุมัติการแก้ไขข้อมูลจากผู้ใช้: {admin_notes}", now_str, session.get('user_name', 'แอดมิน PawLove')))

        notif_msg = f"คำขอแก้ไขข้อมูลน้อง '{data.get('name')}' ของคุณได้รับการอนุมัติและปรับปรุงข้อมูลในระบบเรียบร้อยแล้ว"

    # อัปเดตคำขอเป็น approved
    cursor.execute('''
    UPDATE pet_requests 
    SET status = 'approved', admin_notes = ?, resolved_at = CURRENT_TIMESTAMP
    WHERE id = ?
    ''', (admin_notes, request_id))

    # ส่งการแจ้งเตือนไปยังผู้ใช้ (ข้อกำหนดที่ 4 & 2)
    cursor.execute('''
    INSERT INTO notifications (user_id, title, message)
    VALUES (?, 'คำขอของคุณได้รับการอนุมัติแล้ว', ?)
    ''', (req['user_id'], notif_msg))

    # ส่งอีเมลแจ้งเตือนผลการอนุมัติไปยังผู้ใช้โดยตรง
    cursor.execute("SELECT fullname, email FROM users WHERE id = ?", (req['user_id'],))
    target_user = cursor.fetchone()
    if target_user and target_user['email']:
        sub = f"[PawLove] ผลการอนุมัติคำขอ: ผ่านการอนุมัติเรียบร้อยแล้ว"
        html = f"""
          <h2 style="color: #16a34a; margin-top: 0;">คำขอของคุณได้รับการอนุมัติแล้ว</h2>
          <p>เรียน คุณ {target_user['fullname']},</p>
          <p>แอดมิน PawLove ได้ตรวจสอบและ <strong>อนุมัติ</strong> คำขอของคุณเรียบร้อยแล้ว</p>
          <div style="background: #f0fdf4; border-left: 4px solid #16a34a; padding: 14px 18px; margin: 16px 0; border-radius: 4px; color: #166534;">
            <strong>รายละเอียด:</strong> {notif_msg}<br>
            {f"<strong>บันทึกจากแอดมิน:</strong> {admin_notes}" if admin_notes else ""}
          </div>
          <p>คุณสามารถเข้าสู่ระบบเพื่อตรวจสอบข้อมูลในระบบได้ทันที</p>
        """
        send_email_notification(target_user['email'], sub, html, notif_msg)

    conn.commit()
    conn.close()

    flash("อนุมัติคำขอเรียบร้อยแล้ว! ระบบได้อัปเดตข้อมูลและส่งอีเมลแจ้งเตือนผู้ใช้แล้ว", "success")
    return redirect(url_for('admin.requests_list'))


# ฟังก์ชันปฏิเสธคำขอจากผู้ใช้
# - เปลี่ยนสถานะเป็น 'rejected'
# - บันทึกเหตุผลการปฏิเสธของแอดมิน
# - ส่งการแจ้งเตือนไปยังผู้ใช้พร้อมระบุเหตุผล
@admin_bp.route('/requests/<int:request_id>/reject', methods=['POST'])
@admin_required
def request_reject(request_id):
    reason = request.form.get('reason', 'ข้อมูลไม่ครบถ้วนหรือไม่เป็นไปตามเงื่อนไข').strip()

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM pet_requests WHERE id = ?", (request_id,))
    req = cursor.fetchone()

    if not req or req['status'] != 'pending':
        conn.close()
        flash("ไม่พบคำขอนี้หรือได้รับการดำเนินการไปแล้ว", "warning")
        return redirect(url_for('admin.requests_list'))

    cursor.execute('''
    UPDATE pet_requests 
    SET status = 'rejected', admin_notes = ?, resolved_at = CURRENT_TIMESTAMP
    WHERE id = ?
    ''', (reason, request_id))

    # ส่งแจ้งเตือนให้ผู้ใช้
    req_type_str = "เพิ่มสัตว์ใหม่" if req['request_type'] == 'add' else "แก้ไขข้อมูลสัตว์"
    reject_msg = f"คำขอ{req_type_str}ของคุณไม่ได้รับการอนุมัติจากแอดมิน เหตุผล: {reason}"
    cursor.execute('''
    INSERT INTO notifications (user_id, title, message)
    VALUES (?, ?, ?)
    ''', (req['user_id'], f"คำขอ{req_type_str}ไม่ผ่านการอนุมัติ", reject_msg))

    # ส่งอีเมลแจ้งเตือนผลปฏิเสธไปยังผู้ใช้โดยตรง
    cursor.execute("SELECT fullname, email FROM users WHERE id = ?", (req['user_id'],))
    target_user = cursor.fetchone()
    if target_user and target_user['email']:
        sub = f"[PawLove] แจ้งผลคำขอ: ไม่ผ่านการอนุมัติ ({req_type_str})"
        html = f"""
          <h2 style="color: #dc2626; margin-top: 0;">แจ้งผลการพิจารณาคำขอ</h2>
          <p>เรียน คุณ {target_user['fullname']},</p>
          <p>ขออภัย คำขอ<strong>{req_type_str}</strong>ของคุณไม่ผ่านการอนุมัติจากผู้ดูแลระบบ</p>
          <div style="background: #fef2f2; border-left: 4px solid #dc2626; padding: 14px 18px; margin: 16px 0; border-radius: 4px; color: #991b1b;">
            <strong>เหตุผลที่ไม่อนุมัติ:</strong> {reason}
          </div>
          <p>หากมีข้อสงสัยหรือต้องการยื่นแก้ไขข้อมูลเพิ่มเติม สามารถติดต่อทีมงานได้ที่ contact@pawlove.org</p>
        """
        send_email_notification(target_user['email'], sub, html, reject_msg)

    conn.commit()
    conn.close()

    flash("ปฏิเสธคำขอเรียบร้อยแล้ว และส่งอีเมลแจ้งผลไปยังผู้ใช้แล้ว", "info")
    return redirect(url_for('admin.requests_list'))


# ฟังก์ชันแสดงรายชื่อผู้ใช้ทั้งหมด
# - แอดมินสามารถดูรายชื่อผู้ใช้ทั้งหมด
# - สามารถกดแก้ไขหรือลบบัญชีผู้ใช้รายใดก็ได้
@admin_bp.route('/users')
@admin_required
def users_list():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, fullname, email, role, status, deletion_reason, deleted_at, created_at FROM users ORDER BY id ASC")
    users = cursor.fetchall()
    conn.close()

    return render_template('admin/users_manage.html', users=users)


# ฟังก์ชันแก้ไขข้อมูลบัญชีผู้ใช้รายอื่นทั้งหมด
#     - แก้ไขชื่อ-นามสกุล
#     - แก้ไขอีเมล
#     - เปลี่ยนรหัสผ่านใหม่ (หากแอดมินต้องการรีเซ็ตรหัสให้)
#     - เปลี่ยนบทบาท (user หรือ admin)
@admin_bp.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@admin_required
def user_edit(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()

    if not user:
        conn.close()
        flash("ไม่พบบัญชีผู้ใช้ที่ต้องการแก้ไข", "danger")
        return redirect(url_for('admin.users_list'))

    if request.method == 'POST':
        fullname = request.form.get('fullname', user['fullname']).strip()
        email = request.form.get('email', user['email']).strip().lower()
        new_password = request.form.get('new_password', '').strip()
        role = request.form.get('role', user['role'])

        # ตรวจสอบอีเมลซ้ำกับคนอื่นหรือไม่
        cursor.execute("SELECT id FROM users WHERE LOWER(email) = LOWER(?) AND id != ?", (email, user_id))
        if cursor.fetchone():
            flash("อีเมลนี้ถูกใช้งานโดยบัญชีอื่นแล้ว", "danger")
            conn.close()
            return render_template('admin/user_edit.html', user=user)

        if new_password:
            # มีการรีเซ็ตรหัสผ่านใหม่
            pw_hash = generate_password_hash(new_password)
            cursor.execute('''
            UPDATE users SET fullname = ?, email = ?, password_hash = ?, role = ?
            WHERE id = ?
            ''', (fullname, email, pw_hash, role, user_id))
        else:
            cursor.execute('''
            UPDATE users SET fullname = ?, email = ?, role = ?
            WHERE id = ?
            ''', (fullname, email, role, user_id))

        conn.commit()
        conn.close()

        # ส่งอีเมลแจ้งเตือนไปยังผู้ใช้เมื่อแอดมินแก้ไขข้อมูลบัญชี
        edit_sub = "[PawLove] บัญชีผู้ใช้งานของคุณได้รับการปรับปรุงข้อมูลโดยผู้ดูแลระบบ"
        edit_html = f"""
          <h2 style="color: #ea580c; margin-top: 0;">แจ้งเตือนการปรับปรุงข้อมูลบัญชี</h2>
          <p>เรียน คุณ {fullname},</p>
          <p>ผู้ดูแลระบบได้ทำการปรับปรุงข้อมูลบัญชีผู้ใช้งานของคุณในระบบ PawLove ดังนี้:</p>
          <ul style="line-height: 1.8; color: #334155;">
            <li><strong>ชื่อ-สกุล:</strong> {fullname}</li>
            <li><strong>อีเมล:</strong> {email}</li>
            <li><strong>บทบาท:</strong> {role}</li>
            {f"<li><strong>รหัสผ่าน:</strong> ได้รับการรีเซ็ตรหัสผ่านใหม่โดยผู้ดูแลระบบ</li>" if new_password else ""}
          </ul>
          <p>หากคุณไม่ได้ร้องขอหรือมีข้อสงสัย กรุณาติดต่อทีมงานได้ทันทีที่ contact@pawlove.org</p>
        """
        send_email_notification(email, edit_sub, edit_html, "ข้อมูลบัญชีผู้ใช้งานของคุณได้รับการปรับปรุงโดยผู้ดูแลระบบ")

        flash(f"อัปเดตข้อมูลบัญชีผู้ใช้ '{fullname}' และส่งอีเมลแจ้งผู้ใช้สำเร็จเรียบร้อย!", "success")
        return redirect(url_for('admin.users_list'))

    conn.close()
    return render_template('admin/user_edit.html', user=user)


# ฟังก์ชันลบบัญชีผู้ใช้ออกจากระบบ (พร้อมระบุเหตุผลและแจ้งเตือนไปยังบัญชีผู้ใช้)
# - ป้องกันไม่ให้แอดมินลบบัญชีของตัวเองขณะใช้งาน
# - บันทึกสถานะ deleted, เหตุผล และส่งการแจ้งเตือนไปยังบัญชีผู้ใช้
@admin_bp.route('/users/<int:user_id>/delete', methods=['POST'])
@admin_required
def user_delete(user_id):
    if user_id == session.get('user_id'):
        flash("ไม่สามารถลบบัญชีของตัวคุณเองที่กำลังเข้าสู่ระบบอยู่ได้", "danger")
        return redirect(url_for('admin.users_list'))

    reason = request.form.get('reason', '').strip()
    if not reason:
        reason = "ทำผิดเงื่อนไขการใช้งานหรือข้อกำหนดของชุมชน PawLove"

    now_str = datetime.now().strftime("%d/%m/%Y %H:%M น.")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT fullname, email FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    if user:
        # 1. ส่งการแจ้งเตือนอย่างเป็นทางการไปยังบัญชีผู้ใช้
        notif_msg = f"บัญชีผู้ใช้งานของคุณ ({user['fullname']}) ถูกลบ/ระงับการใช้งานโดยผู้ดูแลระบบ PawLove เมื่อ {now_str} เนื่องจาก: {reason}"
        cursor.execute('''
        INSERT INTO notifications (user_id, title, message)
        VALUES (?, 'แจ้งเตือนการลบบัญชีผู้ใช้งาน', ?)
        ''', (user_id, notif_msg))

        # 2. ปรับสถานะบัญชีเป็น 'deleted' พร้อมบันทึกเหตุผลและเวลาที่ลบ
        cursor.execute('''
        UPDATE users 
        SET status = 'deleted', deletion_reason = ?, deleted_at = CURRENT_TIMESTAMP
        WHERE id = ?
        ''', (reason, user_id))

        # 3. ส่งอีเมลแจ้งเตือนไปยังอีเมลผู้ใช้โดยตรง (ข้อกำหนด: เมื่อแอดมินลบบัญชีผู้ใช้จะต้องแจ้งเตือนไปให้ผู้ใช้ด้วย ผ่านทางอีเมล)
        if user['email']:
            sub = f"[PawLove] แจ้งเตือนการระงับ/ลบบัญชีผู้ใช้งาน"
            html = f"""
              <h2 style="color: #dc2626; margin-top: 0;">แจ้งเตือนการระงับและลบบัญชีผู้ใช้งาน</h2>
              <p>เรียน คุณ {user['fullname']},</p>
              <p>ระบบขอแจ้งให้ทราบว่า บัญชีผู้ใช้งาน PawLove ที่ผูกกับอีเมลนี้ ถูกลบหรือระงับการใช้งานโดยผู้ดูแลระบบ</p>
              <div style="background: #fef2f2; border-left: 4px solid #dc2626; padding: 14px 18px; margin: 16px 0; border-radius: 4px; color: #991b1b;">
                <strong>วันที่ดำเนินการ:</strong> {now_str}<br>
                <strong>เหตุผลที่ระบุโดยผู้ดูแลระบบ:</strong> {reason}
              </div>
              <p>หากคุณเชื่อว่าเกิดข้อผิดพลาด สามารถติดต่อสอบถามเจ้าหน้าที่ได้ที่ contact@pawlove.org</p>
            """
            send_email_notification(user['email'], sub, html, notif_msg)

        conn.commit()
        flash(f"ลบบัญชีผู้ใช้ '{user['fullname']}' พร้อมส่งอีเมลแจ้งเหตุผลไปยัง {user['email']} เรียบร้อยแล้ว", "success")
    conn.close()
    return redirect(url_for('admin.users_list'))


# ฟังก์ชันแก้ไขเนื้อหาเว็บไซต์ทั้งหมดที่แอดมินต้องแก้ไขได้ (ข้อกำหนดที่ 5: แถบเมนูแอดมินต้องแก้ไขได้ทั้งหมด)
# - แก้ไขข้อมูลโครงการ (หน้าหลัก)
# - แก้ไขการทำงานของโครงการ 4 ด้าน:
#       1. ดูแลการรักษา
#       2. การทำหมัน
#       3. การช่วยเหลือฉุกเฉิน
#       4. ศูนย์พักพิงชั่วคราว
#  - แก้ไขช่องทางการติดต่อ: E-Mail, Facebook, Instagram, TikTok
#  - แก้ไขข้อมูลการบริจาค
@admin_bp.route('/content-edit', methods=['GET', 'POST'])
@admin_required
def content_edit():
    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        project_info = request.form.get('project_info', '').strip()
        work_medical = request.form.get('work_medical', '').strip()
        work_sterilization = request.form.get('work_sterilization', '').strip()
        work_emergency = request.form.get('work_emergency', '').strip()
        work_shelter = request.form.get('work_shelter', '').strip()

        contact_email = request.form.get('contact_email', '').strip()
        contact_fb = request.form.get('contact_fb', '').strip()
        contact_ig = request.form.get('contact_ig', '').strip()
        contact_tiktok = request.form.get('contact_tiktok', '').strip()

        donation_info = request.form.get('donation_info', '').strip()

        # บันทึกข้อมูลโครงการ
        cursor.execute('''
        INSERT OR REPLACE INTO site_content (key_name, title, content, updated_at)
        VALUES ('project_info', 'ข้อมูลโครงการ PawLove', ?, CURRENT_TIMESTAMP)
        ''', (project_info,))

        # บันทึกการทำงาน 4 ด้าน
        project_work_json = json.dumps({
            "medical": work_medical,
            "sterilization": work_sterilization,
            "emergency": work_emergency,
            "shelter": work_shelter
        }, ensure_ascii=False)
        cursor.execute('''
        INSERT OR REPLACE INTO site_content (key_name, title, content, updated_at)
        VALUES ('project_work', 'การทำงานของโครงการ', ?, CURRENT_TIMESTAMP)
        ''', (project_work_json,))

        # บันทึกช่องทางการติดต่อ
        contact_json = json.dumps({
            "email": contact_email,
            "facebook": contact_fb,
            "instagram": contact_ig,
            "tiktok": contact_tiktok
        }, ensure_ascii=False)
        cursor.execute('''
        INSERT OR REPLACE INTO site_content (key_name, title, content, updated_at)
        VALUES ('contact_info', 'ช่องทางการติดต่อ', ?, CURRENT_TIMESTAMP)
        ''', (contact_json,))

        # บันทึกข้อมูลการบริจาค
        cursor.execute('''
        INSERT OR REPLACE INTO site_content (key_name, title, content, updated_at)
        VALUES ('donation_info', 'ข้อมูลการบริจาค', ?, CURRENT_TIMESTAMP)
        ''', (donation_info,))

        conn.commit()
        flash("บันทึกการแก้ไขข้อมูลหน้าเว็บทั้งหมดสำเร็จเรียบร้อย!", "success")

    # ดึงข้อมูลปัจจุบันมาแสดงในฟอร์ม
    cursor.execute("SELECT * FROM site_content")
    rows = cursor.fetchall()
    conn.close()

    content_dict = {row['key_name']: row['content'] for row in rows}
    
    project_work = {}
    if 'project_work' in content_dict:
        try:
            project_work = json.loads(content_dict['project_work'])
        except Exception:
            pass

    contact_info = {}
    if 'contact_info' in content_dict:
        try:
            contact_info = json.loads(content_dict['contact_info'])
        except Exception:
            pass

    return render_template('admin/content_edit.html',
                           project_info=content_dict.get('project_info', ''),
                           project_work=project_work,
                           contact_info=contact_info,
                           donation_info=content_dict.get('donation_info', ''))


# ฟังก์ชันจัดการคำขอรับเลี้ยงสัตว์ที่ส่งมาจากแบบฟอร์ม
# - แสดงรายละเอียดผู้ยื่นขอรับเลี้ยง ข้อมูลครัวเรือน และเหตุผล
# - แอดมินสามารถอัปเดตสถานะ เช่น 'ติดต่อสัมภาษณ์แล้ว', 'อนุมัติรับเลี้ยง', 'ปฏิเสธ'
@admin_bp.route('/adoptions')
@admin_required
def adoptions_list():
   
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
    SELECT a.*, p.name as pet_name, p.species as pet_species, p.image_url as pet_image
    FROM adoption_applications a
    JOIN pets p ON a.pet_id = p.id
    ORDER BY a.id DESC
    ''')
    adoptions = cursor.fetchall()
    conn.close()

    return render_template('admin/adoption_requests.html', adoptions=adoptions)


# ฟังก์ชันอัปเดตสถานะขั้นตอนการรับเลี้ยงสัตว์
@admin_bp.route('/adoptions/<int:app_id>/status', methods=['POST'])
@admin_required
def adoption_status_update(app_id):
   
    new_status = request.form.get('status')
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE adoption_applications SET status = ? WHERE id = ?", (new_status, app_id))
    conn.commit()
    conn.close()

    flash(f"อัปเดตสถานะคำขอรับเลี้ยงเป็น '{new_status}' เรียบร้อยแล้ว", "success")
    return redirect(url_for('admin.adoptions_list'))


# ==================== ส่วนจัดการคำคมและแบนเนอร์รูปสัตว์เคลื่อนไหว (ข้อกำหนดที่ 2) ====================
# - ตรงส่วนรูปที่เคลื่อนไหว แบ่งเป็นรูปๆไว้เลย ปรับให้ใส่รูปและใส่คำคมเองได้ ในระบบแอดมิน

@admin_bp.route('/quotes')
@admin_required
def quotes_list():
    """แสดงรายการรูปและคำคมสไลด์ทั้งหมดในระบบ"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM banner_quotes ORDER BY sort_order ASC, id ASC")
    quotes = cursor.fetchall()
    conn.close()
    return render_template('admin/quotes_manage.html', quotes=quotes)


@admin_bp.route('/quotes/add', methods=['GET', 'POST'])
@admin_required
def quote_add():
    """เพิ่มรูปสัตว์และคำคมสไลด์ใหม่เข้าระบบแอดมิน"""
    if request.method == 'POST':
        quote_text = request.form.get('quote_text', '').strip()
        sub_text = request.form.get('sub_text', '').strip()
        author = request.form.get('author', 'PawLove Community').strip()
        sort_order = int(request.form.get('sort_order') or 0)
        is_active = 1 if request.form.get('is_active') else 0

        # จัดการไฟล์รูปภาพ
        uploaded_image = request.files.get('quote_image')
        saved_image_url = save_uploaded_quote_image(uploaded_image) if uploaded_image else None
        image_url = saved_image_url or request.form.get('image_url', '').strip()

        if not quote_text:
            flash("กรุณากรอกข้อความคำคม", "danger")
            return redirect(url_for('admin.quotes_list'))

        if not image_url:
            image_url = "https://images.unsplash.com/photo-1543466835-00a7907e9de1?w=800"

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
        INSERT INTO banner_quotes (quote_text, sub_text, author, image_url, sort_order, is_active)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (quote_text, sub_text, author, image_url, sort_order, is_active))
        conn.commit()
        conn.close()

        flash("เพิ่มรูปและคำคมใหม่ลงในแบนเนอร์เรียบร้อยแล้ว!", "success")
        return redirect(url_for('admin.quotes_list'))

    return redirect(url_for('admin.quotes_list'))


@admin_bp.route('/quotes/<int:quote_id>/edit', methods=['POST'])
@admin_required
def quote_edit(quote_id):
    """แก้ไขรูปสัตว์และคำคมสไลด์เดิม"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM banner_quotes WHERE id = ?", (quote_id,))
    quote = cursor.fetchone()

    if not quote:
        conn.close()
        flash("ไม่พบข้อมูลคำคมที่ต้องการแก้ไข", "danger")
        return redirect(url_for('admin.quotes_list'))

    quote_text = request.form.get('quote_text', quote['quote_text']).strip()
    sub_text = request.form.get('sub_text', quote['sub_text']).strip()
    author = request.form.get('author', quote['author']).strip()
    sort_order = int(request.form.get('sort_order') or quote['sort_order'])
    is_active = 1 if request.form.get('is_active') else 0

    uploaded_image = request.files.get('quote_image')
    saved_image_url = save_uploaded_quote_image(uploaded_image) if uploaded_image else None
    image_url = saved_image_url or request.form.get('image_url', '').strip() or quote['image_url']

    cursor.execute('''
    UPDATE banner_quotes 
    SET quote_text = ?, sub_text = ?, author = ?, image_url = ?, sort_order = ?, is_active = ?
    WHERE id = ?
    ''', (quote_text, sub_text, author, image_url, sort_order, is_active, quote_id))
    conn.commit()
    conn.close()

    flash("อัปเดตข้อมูลรูปภาพและคำคมเรียบร้อยแล้ว!", "success")
    return redirect(url_for('admin.quotes_list'))


@admin_bp.route('/quotes/<int:quote_id>/delete', methods=['POST'])
@admin_required
def quote_delete(quote_id):
    """ลบรูปและคำคมออกจากระบบ"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM banner_quotes WHERE id = ?", (quote_id,))
    conn.commit()
    conn.close()
    flash("ลบรูปและคำคมออกจากระบบเรียบร้อยแล้ว", "success")
    return redirect(url_for('admin.quotes_list'))


@admin_bp.route('/quotes/<int:quote_id>/toggle', methods=['POST'])
@admin_required
def quote_toggle(quote_id):
    """เปิด/ปิด การแสดงผลรูปและคำคมบนหน้าแรก"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT is_active FROM banner_quotes WHERE id = ?", (quote_id,))
    row = cursor.fetchone()
    if row:
        new_state = 0 if row['is_active'] == 1 else 1
        cursor.execute("UPDATE banner_quotes SET is_active = ? WHERE id = ?", (new_state, quote_id))
        conn.commit()
        flash("เปลี่ยนสถานะการแสดงผลเรียบร้อยแล้ว", "success")
    conn.close()
    return redirect(url_for('admin.quotes_list'))


# ==================== ส่วนจัดการประวัติการบริจาคและตรวจสอบสลีป (Admin Donations) ====================
@admin_bp.route('/donations')
@admin_required
def donations_list():
    """แสดงประวัติการบริจาคทั้งหมด พร้อมหลักฐานสลีปและสถานะการตรวจสอบความถูกต้อง"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
    SELECT d.*, p.name as pet_name, p.species as pet_species
    FROM donations d
    LEFT JOIN pets p ON d.pet_id = p.id
    ORDER BY d.id DESC
    ''')
    donations = cursor.fetchall()

    cursor.execute("SELECT SUM(amount) as total_sum, COUNT(*) as total_count FROM donations")
    stats = cursor.fetchone()
    conn.close()

    return render_template('admin/donations.html', donations=donations, stats=stats)


@admin_bp.route('/donations/<int:donation_id>/verify', methods=['POST'])
@admin_required
def donation_verify(donation_id):
    """แอดมินตรวจสอบและยืนยันความถูกต้องของสลีป (ชื่อบัญชีปลายทางและยอดเงิน)"""
    action = request.form.get('action', 'verify')
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM donations WHERE id = ?", (donation_id,))
    don = cursor.fetchone()
    if not don:
        conn.close()
        flash("ไม่พบข้อมูลรายการบริจาคนี้", "danger")
        return redirect(url_for('admin.donations_list'))

    if action == 'verify':
        cursor.execute('''
        UPDATE donations 
        SET is_verified = 1, verification_info = 'แอดมินตรวจสอบชื่อบัญชีปลายทางและยอดเงินถูกต้องเรียบร้อยแล้ว'
        WHERE id = ?
        ''', (donation_id,))
        flash(f"ยืนยันสลีปการบริจาคของคุณ {don['donor_name']} เรียบร้อยแล้ว", "success")
    else:
        cursor.execute('''
        UPDATE donations 
        SET is_verified = 0, verification_info = 'รอการตรวจสอบจากแอดมิน'
        WHERE id = ?
        ''', (donation_id,))
        flash(f"ยกเลิกการยืนยันสลีปของคุณ {don['donor_name']} เรียบร้อยแล้ว", "info")

    conn.commit()
    conn.close()
    return redirect(url_for('admin.donations_list'))



# ==================== ส่วนจัดการข่าวสารและประกาศ (Admin News Management) ====================
@admin_bp.route('/news')
@admin_required
def news_manage():
    """แสดงรายการข่าวสารและประกาศทั้งหมดในระบบหลังบ้าน"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM news ORDER BY id DESC")
    news_items = cursor.fetchall()
    conn.close()
    return render_template('admin/news_manage.html', news_items=news_items)


@admin_bp.route('/news/add', methods=['GET', 'POST'])
@admin_required
def news_add():
    """เพิ่มข่าวสารและประกาศใหม่โดยแอดมิน"""
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        category = request.form.get('category', 'ข่าวประชาสัมพันธ์').strip()
        summary = request.form.get('summary', '').strip()
        content = request.form.get('content', '').strip()
        is_published = 1 if request.form.get('is_published') else 0

        if not title or not content:
            flash("กรุณากรอกหัวข้อข่าวและเนื้อหาข่าวให้ครบถ้วน", "danger")
            return render_template('admin/news_form.html', news=None, title="เพิ่มข่าวสารใหม่")

        # จัดการรูปภาพ (Choose File หรือ URL)
        uploaded_image = request.files.get('news_image')
        saved_image_url = save_uploaded_pet_image(uploaded_image) if uploaded_image else None
        image_url = saved_image_url or request.form.get('image_url', '').strip()
        if not image_url:
            image_url = "/static/uploads/pets/Golden Hour Animal Feeding.png"

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
        INSERT INTO news (title, category, summary, content, image_url, author, is_published)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (title, category, summary, content, image_url, session.get('user_name', 'ผู้ดูแลระบบ PawLove'), is_published))

        # ส่งการแจ้งเตือนทั่วไปให้ผู้ใช้ทุกคน
        cursor.execute('''
        INSERT INTO notifications (user_id, title, message)
        VALUES (NULL, ?, ?)
        ''', (f"ข่าวใหม่: {title}", summary or content[:120] + "..."))

        # ส่งอีเมลแจ้งเตือนข่าวสารไปยังสมาชิกผู้ใช้งานทุกคนโดยตรง
        cursor.execute("SELECT email, fullname FROM users WHERE status != 'deleted'")
        active_users = cursor.fetchall()
        news_subject = f"[PawLove ข่าวสาร] {title}"
        news_html = f"""
          <h2 style="color: #ea580c; margin-top: 0;">ข่าวสารและประกาศจาก PawLove</h2>
          <p>เรียน สมาชิกครอบครัว PawLove,</p>
          <div style="background: #fff7ed; border-left: 4px solid #ea580c; padding: 14px 18px; margin: 16px 0; border-radius: 4px;">
            <div style="font-size: 16px; font-weight: bold; color: #9a3412;">{title}</div>
            <div style="font-size: 13px; color: #c2410c; margin-bottom: 8px;">หมวดหมู่: {category}</div>
            <p style="margin: 0; color: #431407; line-height: 1.6;">{summary or content[:200] + '...'}</p>
          </div>
          <p>คุณสามารถคลิกเข้าไปอ่านเนื้อหาข่าวสารฉบับเต็มได้ที่เว็บไซต์ PawLove</p>
        """
        for u in active_users:
            if u['email']:
                try:
                    send_email_notification(u['email'], news_subject, news_html, summary or content[:200])
                except Exception:
                    pass

        conn.commit()
        conn.close()

        flash(f"เพิ่มข่าวสาร '{title}' พร้อมส่งแจ้งเตือนทางอีเมลให้สมาชิกเรียบร้อยแล้ว!", "success")
        return redirect(url_for('admin.news_manage'))

    return render_template('admin/news_form.html', news=None, title="เพิ่มข่าวสารใหม่")


@admin_bp.route('/news/<int:news_id>/edit', methods=['GET', 'POST'])
@admin_required
def news_edit(news_id):
    """แก้ไขข่าวสารเดิม"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM news WHERE id = ?", (news_id,))
    news_item = cursor.fetchone()

    if not news_item:
        conn.close()
        flash("ไม่พบข้อมูลข่าวสารที่ต้องการแก้ไข", "danger")
        return redirect(url_for('admin.news_manage'))

    if request.method == 'POST':
        title = request.form.get('title', news_item['title']).strip()
        category = request.form.get('category', news_item['category']).strip()
        summary = request.form.get('summary', news_item['summary']).strip()
        content = request.form.get('content', news_item['content']).strip()
        is_published = 1 if request.form.get('is_published') else 0

        uploaded_image = request.files.get('news_image')
        saved_image_url = save_uploaded_pet_image(uploaded_image) if uploaded_image else None
        image_url = saved_image_url or request.form.get('image_url', '').strip() or news_item['image_url']

        cursor.execute('''
        UPDATE news 
        SET title = ?, category = ?, summary = ?, content = ?, image_url = ?, is_published = ?
        WHERE id = ?
        ''', (title, category, summary, content, image_url, is_published, news_id))
        conn.commit()
        conn.close()

        flash(f"อัปเดตข่าวสาร '{title}' เรียบร้อยแล้ว!", "success")
        return redirect(url_for('admin.news_manage'))

    conn.close()
    return render_template('admin/news_form.html', news=news_item, title="แก้ไขข่าวสาร")


@admin_bp.route('/news/<int:news_id>/delete', methods=['POST'])
@admin_required
def news_delete(news_id):
    """ลบข่าวสารออกจากระบบ"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM news WHERE id = ?", (news_id,))
    conn.commit()
    conn.close()
    flash("ลบข่าวสารออกจากระบบเรียบร้อยแล้ว", "success")
    return redirect(url_for('admin.news_manage'))


