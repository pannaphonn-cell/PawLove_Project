"""
ระบบการยืนยันตัวตนและการจัดการสิทธิ์ (Authentication Routes)
ครอบคลุม:
1. การเข้าถึงระบบหลังบ้านแอดมินด้วยอีเมลแอดมินโดยตรง (ตามข้อกำหนดที่ 1)
2. ระบบสมัครสมาชิก พร้อมเงื่อนไขตรวจสอบรหัสผ่านและข้อตกลง (ตามข้อกำหนดที่ 7)
3. ระบบล็อกอินทั่วไป (ตามข้อกำหนดที่ 8)
4. การออกจากระบบ (Logout)
"""

import re
import time
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from database import get_db_connection
from utils import generate_otp_code, send_otp_email

auth_bp = Blueprint('auth', __name__, url_prefix='')


def validate_password_strength(password):
    if len(password) < 6:
        return False, "รหัสผ่านต้องมีความยาวอย่างน้อย 6 ตัวอักษร"
    if not re.search(r'[A-Z]', password):
        return False, "รหัสผ่านต้องมีตัวอักษรพิมพ์ใหญ่อย่างน้อย 1 ตัว (A-Z)"
    if not re.search(r'[a-z]', password):
        return False, "รหัสผ่านต้องมีตัวอักษรพิมพ์เล็กอย่างน้อย 1 ตัว (a-z)"
    if not re.search(r'\d', password):
        return False, "รหัสผ่านต้องมีตัวเลขอย่างน้อย 1 ตัว (0-9)"
    return True, ""


# ฟังก์ชันระบบสมัครสมาชิก (ลบการยืนยันอายุออก + เพิ่มขั้นตอน OTP ไปยังอีเมล)
@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        fullname = request.form.get('fullname', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        privacy_policy = request.form.get('privacy_policy')
        terms_accepted = request.form.get('terms_accepted')

        # 1. ตรวจสอบข้อมูลครบถ้วน
        if not fullname or not email or not password:
            flash("กรุณากรอกข้อมูลให้ครบถ้วนทุกช่อง", "danger")
            return render_template('auth/register.html', fullname=fullname, email=email)

        # 2. ตรวจสอบการยืนยันรหัสผ่าน
        if password != confirm_password:
            flash("รหัสผ่านและการยืนยันรหัสผ่านไม่ตรงกัน", "danger")
            return render_template('auth/register.html', fullname=fullname, email=email)

        # 3. ตรวจสอบความซับซ้อนของรหัสผ่าน (ตัวพิมพ์ใหญ่ พิมพ์เล็ก ตัวเลข)
        is_valid_pw, pw_error = validate_password_strength(password)
        if not is_valid_pw:
            flash(pw_error, "danger")
            return render_template('auth/register.html', fullname=fullname, email=email)

        # 4. ตรวจสอบนโยบายและเงื่อนไข (ลบการยืนยันอายุออกแล้ว)
        if not privacy_policy or not terms_accepted:
            flash("กรุณายอมรับนโยบายความเป็นส่วนตัวและข้อตกลงเงื่อนไขการใช้งาน", "danger")
            return render_template('auth/register.html', fullname=fullname, email=email)

        # 5. ตรวจสอบอีเมลซ้ำในฐานข้อมูล
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE LOWER(email) = LOWER(?)", (email,))
        if cursor.fetchone():
            conn.close()
            flash("อีเมลนี้ถูกใช้งานในระบบแล้ว กรุณาใช้อีเมลอื่นหรือเข้าสู่ระบบ", "warning")
            return render_template('auth/register.html', fullname=fullname)
        conn.close()

        # 6. สร้างรหัส OTP ส่งไปยังอีเมลผู้ใช้ (Gmail และ Mail)
        otp = generate_otp_code(6)
        pw_hash = generate_password_hash(password)

        session['reg_data'] = {
            'fullname': fullname,
            'email': email.lower(),
            'password_hash': pw_hash,
            'otp': otp,
            'otp_time': time.time()
        }

        # ส่งอีเมลจริง/จำลอง
        send_otp_email(email.lower(), otp, purpose="ยืนยันการลงทะเบียนสมาชิก PawLove")
        flash(f"ระบบได้ส่งรหัส OTP ไปยังอีเมล {email} แล้ว กรุณากรอกรหัสเพื่อยืนยันตัวตน", "info")
        return redirect(url_for('auth.verify_otp'))

    return render_template('auth/register.html')


# ฟังก์ชันตรวจสอบรหัส OTP ที่ส่งไปยังอีเมล
@auth_bp.route('/verify-otp', methods=['GET', 'POST'])
def verify_otp():
    reg_data = session.get('reg_data')
    if not reg_data:
        flash("ไม่พบข้อมูลการลงทะเบียน กรุณากรอกข้อมูลใหม่อีกครั้ง", "warning")
        return redirect(url_for('auth.register'))

    if request.method == 'POST':
        # ทำความสะอาดรหัส OTP ที่ผู้ใช้กรอก (ตัดช่องว่าง, ขีด, หรืออักขระแปลกปลอม)
        user_otp = request.form.get('otp', '').strip().replace(' ', '').replace('-', '')

        # ตรวจสอบอายุ OTP (5 นาที = 300 วินาที)
        otp_created_time = reg_data.get('otp_time', 0)
        remaining_time = 300 - int(time.time() - otp_created_time)
        if remaining_time <= 0:
            flash("รหัส OTP หมดอายุแล้ว (เกิน 5 นาที) กรุณากด 'ส่งรหัสใหม่อีกครั้ง'", "danger")
            return render_template('auth/verify_otp.html', email=reg_data['email'], remaining_seconds=0)

        expected_otp = str(reg_data.get('otp', '')).strip()
        if not user_otp or user_otp != expected_otp:
            flash("รหัส OTP ไม่ถูกต้อง กรุณาตรวจสอบรหัส 6 หลักล่าสุดจากอีเมลแล้วลองใหม่อีกครั้ง", "danger")
            return render_template('auth/verify_otp.html', email=reg_data['email'], remaining_seconds=max(0, remaining_time))

        # OTP ถูกต้อง บันทึกผู้ใช้ใหม่ลงฐานข้อมูล
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
        INSERT INTO users (fullname, email, password_hash, age_confirmed, terms_accepted, role)
        VALUES (?, ?, ?, 1, 1, 'user')
        ''', (reg_data['fullname'], reg_data['email'], reg_data['password_hash']))
        conn.commit()
        conn.close()

        session.pop('reg_data', None)
        flash("ยืนยันอีเมลสำเร็จ! บัญชีของคุณพร้อมใช้งานแล้ว สามารถเข้าสู่ระบบได้ทันที", "success")
        return redirect(url_for('auth.login'))

    otp_created_time = reg_data.get('otp_time', 0)
    remaining_time = max(0, 300 - int(time.time() - otp_created_time))
    return render_template('auth/verify_otp.html', email=reg_data['email'], remaining_seconds=remaining_time)


# ฟังก์ชันส่งรหัส OTP ใหม่
@auth_bp.route('/resend-otp')
def resend_otp():
    reg_data = session.get('reg_data')
    if not reg_data:
        flash("ไม่พบข้อมูลการลงทะเบียน กรุณากรอกข้อมูลการสมัครใหม่อีกครั้ง", "warning")
        return redirect(url_for('auth.register'))

    new_otp = generate_otp_code(6)
    
    # อัปเดต reg_data ใน session และเซฟให้สมบูรณ์
    updated_reg = dict(reg_data)
    updated_reg['otp'] = new_otp
    updated_reg['otp_time'] = time.time()
    session['reg_data'] = updated_reg
    session.modified = True

    # ส่งอีเมลรหัส OTP ใหม่ไปยังอีเมลผู้รับ
    success, msg = send_otp_email(updated_reg['email'], new_otp, purpose="ยืนยันการลงทะเบียนสมาชิก PawLove")
    if success:
        flash(f"ระบบได้ส่งรหัส OTP ชุดใหม่ไปยังอีเมล {updated_reg['email']} เรียบร้อยแล้ว (มีอายุ 5 นาที)", "success")
    else:
        flash(f"ส่งรหัสใหม่ไม่สำเร็จ: {msg} กรุณาลองใหม่อีกครั้ง", "danger")

    return redirect(url_for('auth.verify_otp'))


    # ฟังก์ชันระบบล็อกอิน
    #   1. อีเมล
    #   2. รหัสผ่าน
    #   3. ยืนยันรหัสผ่าน
    # - ตรวจสอบความถูกต้องและสร้าง Session การใช้งาน พร้อมบันทึกประวัติการเข้าสู่ระบบ
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        # ตรวจสอบว่ากรอกข้อมูลครบถ้วน
        if not email or not password or not confirm_password:
            flash("กรุณากรอกอีเมล รหัสผ่าน และยืนยันรหัสผ่านให้ครบถ้วน", "danger")
            return render_template('auth/login.html', email=email)

        # ตรวจสอบการยืนยันรหัสผ่าน
        if password != confirm_password:
            flash("รหัสผ่านและการยืนยันรหัสผ่านไม่ตรงกัน", "danger")
            return render_template('auth/login.html', email=email)

        # ตรวจสอบในฐานข้อมูล
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE LOWER(email) = LOWER(?)", (email,))
        user = cursor.fetchone()

        if user and check_password_hash(user['password_hash'], password):
            # ตรวจสอบว่าบัญชีถูกลบหรือระงับหรือไม่
            user_status = user['status'] if 'status' in user.keys() else 'active'
            if user_status == 'deleted':
                deletion_reason = user['deletion_reason'] or 'ทำผิดข้อกำหนดการใช้งานระบบ'
                conn.close()
                flash(f"บัญชีนี้ถูกลบ/ระงับการใช้งานโดยผู้ดูแลระบบ เหตุผล: {deletion_reason}", "danger")
                return render_template('auth/login.html', email=email, deleted_reason=deletion_reason)

            # บันทึกสถานะการล็อกอินลง Session
            session['user_id'] = user['id']
            session['user_name'] = user['fullname']
            session['user_email'] = user['email']
            session['user_role'] = user['role']

            # บันทึกลงตาราง user_logins สำหรับวิเคราะห์สถิติในแดชบอร์ด
            try:
                cursor.execute('''
                INSERT INTO user_logins (user_id, email, fullname, role)
                VALUES (?, ?, ?, ?)
                ''', (user['id'], user['email'], user['fullname'], user['role']))
                conn.commit()
            except Exception:
                pass

            conn.close()

            flash(f"ยินดีต้อนรับคุณ {user['fullname']} เข้าสู่ระบบสำเร็จ", "success")
            
            # ถ้าเป็น admin นำทางไปยังระบบหลังบ้าน
            if user['role'] == 'admin':
                return redirect(url_for('admin.dashboard'))
            return redirect(url_for('client.index'))
        else:
            conn.close()
            flash("อีเมลหรือรหัสผ่านไม่ถูกต้อง กรุณาลองใหม่อีกครั้ง", "danger")
            return render_template('auth/login.html', email=email)

    return render_template('auth/login.html')


    # ฟังก์ชันเข้าถึงระบบหลังบ้านแอดมินด้วยอีเมลและรหัสผ่านแอดมินอย่างเป็นทางการ
    # - รับข้อมูล: อีเมลแอดมิน (admin_email) และ รหัสผ่านแอดมิน (admin_password)
    # - ตรวจสอบสิทธิ์ว่ามีบทบาทเป็น 'admin' และตรวจสอบความถูกต้องของรหัสผ่านด้วย check_password_hash
    # - หากถูกต้องจะเปิด Session ผู้ดูแลระบบและนำทางเข้าสู่ระบบหลังบ้านทันที
@auth_bp.route('/admin-access', methods=['GET', 'POST'])
@auth_bp.route('/admin-login', methods=['GET', 'POST'])
def admin_direct_access():
    if request.method == 'POST':
        admin_email = request.form.get('admin_email', '').strip().lower()
        admin_password = request.form.get('admin_password', '').strip()

        if not admin_email or not admin_password:
            flash("กรุณากรอกทั้งอีเมลแอดมินและรหัสผ่านให้ครบถ้วน", "danger")
            return render_template('auth/admin_login.html', admin_email=admin_email)

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE LOWER(email) = LOWER(?) AND role = 'admin'", (admin_email,))
        admin_user = cursor.fetchone()

        if admin_user and check_password_hash(admin_user['password_hash'], admin_password):
            # ให้สิทธิ์เข้าสู่ระบบหลังบ้านทันที
            session['user_id'] = admin_user['id']
            session['user_name'] = admin_user['fullname']
            session['user_email'] = admin_user['email']
            session['user_role'] = 'admin'

            # บันทึกประวัติการเข้าสู่ระบบแอดมิน
            try:
                cursor.execute('''
                INSERT INTO user_logins (user_id, email, fullname, role)
                VALUES (?, ?, ?, ?)
                ''', (admin_user['id'], admin_user['email'], admin_user['fullname'], 'admin'))
                conn.commit()
            except Exception:
                pass

            conn.close()

            flash(f"เข้าสู่ระบบหลังบ้านสำเร็จในฐานะผู้ดูแลระบบ: {admin_user['fullname']}", "success")
            return redirect(url_for('admin.dashboard'))
        else:
            conn.close()
            flash("อีเมลแอดมินหรือรหัสผ่านไม่ถูกต้อง หรือบัญชีนี้ไม่มีสิทธิ์ผู้ดูแลระบบ", "danger")
            return render_template('auth/admin_login.html', admin_email=admin_email)

    return render_template('auth/admin_login.html')


    # ฟังก์ชันรีเซ็ตรหัสผ่านใหม่กรณีลืมรหัสผ่าน
@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        if not email or not password or not confirm_password:
            flash("กรุณากรอกข้อมูลให้ครบถ้วนทุกช่อง", "danger")
            return render_template('auth/forgot_password.html', email=email)

        if password != confirm_password:
            flash("รหัสผ่านใหม่และการยืนยันรหัสผ่านไม่ตรงกัน", "danger")
            return render_template('auth/forgot_password.html', email=email)

        is_valid_pw, pw_error = validate_password_strength(password)
        if not is_valid_pw:
            flash(pw_error, "danger")
            return render_template('auth/forgot_password.html', email=email)

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, fullname FROM users WHERE LOWER(email) = LOWER(?)", (email,))
        user = cursor.fetchone()

        if not user:
            conn.close()
            flash("ไม่พบบัญชีผู้ใช้งานที่ใช้อีเมลนี้ในระบบ กรุณาตรวจสอบอีเมลอีกครั้ง หรือสมัครสมาชิกใหม่", "danger")
            return render_template('auth/forgot_password.html', email=email)

        pw_hash = generate_password_hash(password)
        cursor.execute("UPDATE users SET password_hash = ? WHERE id = ?", (pw_hash, user['id']))
        conn.commit()
        conn.close()

        flash("รีเซ็ตรหัสผ่านใหม่สำเร็จเรียบร้อยแล้ว ท่านสามารถเข้าสู่ระบบด้วยรหัสผ่านใหม่ได้ทันที", "success")
        return redirect(url_for('auth.login'))

    return render_template('auth/forgot_password.html')


    # ฟังก์ชันออกจากระบบ (Logout)
    # - ล้างข้อมูล Session ทั้งหมดของผู้ใช้
    # - นำทางกลับไปยังหน้าหลัก
@auth_bp.route('/logout')
def logout():
    session.clear()
    flash("คุณได้ออกจากระบบเรียบร้อยแล้ว", "info")
    return redirect(url_for('client.index'))
