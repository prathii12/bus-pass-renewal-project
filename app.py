from flask import Flask, render_template, request, redirect, session
from flask_mysqldb import MySQL
from datetime import datetime, timedelta
import re
import random

app = Flask(__name__)
app.secret_key = "secretkey"

# ---------------- MYSQL CONFIG ----------------
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'Prathi0412'
app.config['MYSQL_DB'] = 'mini_project'
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'

mysql = MySQL(app)

# ---------------- HOME ----------------
@app.route('/')
def index():
    return render_template('index.html')

# ---------------- REGISTER ----------------
@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        user_id = request.form['userid']
        phone = request.form['phone']
        password = request.form['password']

        if not re.search(r'\d', user_id):
            return "User ID must contain numbers ❌"

        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM users WHERE user_id=%s", (user_id,))
        if cur.fetchone():
            return "User ID already exists ❌"

        otp = random.randint(1000, 9999)
        session['otp'] = otp
        session['temp_user'] = (name, user_id, phone, password)

        print("Register OTP:", otp)

        return redirect('/verify_otp')

    return render_template('register.html')

# ---------------- REGISTER OTP ----------------
@app.route('/verify_otp', methods=['GET','POST'])
def verify_otp():
    if request.method == 'POST':
        user_otp = request.form['otp']

        if not user_otp.isdigit():
            return "OTP must be numbers only ❌"

        if 'otp' not in session or 'temp_user' not in session:
            return "Session expired ❌"

        if int(user_otp) == session['otp']:
            name, user_id, phone, password = session['temp_user']

            cur = mysql.connection.cursor()
            cur.execute(
                "INSERT INTO users(name,user_id,phone,password,role) VALUES(%s,%s,%s,%s,%s)",
                (name, user_id, phone, password, 'user')
            )
            mysql.connection.commit()
            cur.close()

            session.pop('otp', None)
            session.pop('temp_user', None)

            return render_template('success.html')
        else:
            return "Invalid OTP ❌"

    return render_template('otp.html')

# ---------------- LOGIN ----------------
@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        user_id = request.form['userid']
        password = request.form['password']

        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM users WHERE user_id=%s AND password=%s", (user_id, password))
        user = cur.fetchone()
        cur.close()

        if user:
            session['user_id'] = user['id']
            session['username'] = user['user_id']
            return redirect('/dashboard')
        else:
            return "Invalid Login ❌"

    return render_template('login.html')

# ---------------- DASHBOARD ----------------
@app.route('/dashboard', methods=['GET','POST'])
def dashboard():

    if 'user_id' not in session:
        return redirect('/login')

    if request.method == 'POST':
        route = request.form['route']
        pass_type = request.form['pass_type']
        payment_method = request.form['payment_method']

        amount = 500 if pass_type == "Monthly" else 5000
        expiry = datetime.now() + timedelta(days=30 if pass_type == "Monthly" else 365)
        expiry = expiry.strftime('%Y-%m-%d')

        cur = mysql.connection.cursor()
        cur.execute("""
            INSERT INTO renewals(user_id, route, pass_type, expiry_date, payment_method, amount, payment_status, status)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s)
        """, (session['user_id'], route, pass_type, expiry, payment_method, amount, 'Pending', 'Pending'))
        mysql.connection.commit()
        cur.close()

    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT renewals.*, users.user_id AS real_user_id, users.name
        FROM renewals
        JOIN users ON renewals.user_id = users.id
        WHERE renewals.user_id=%s
    """, (session['user_id'],))
    data = cur.fetchall()
    cur.close()

    for r in data:
        expiry = datetime.strptime(str(r['expiry_date']), '%Y-%m-%d')
        r['reminder'] = "⚠ Expiring soon" if (expiry - datetime.now()).days <= 3 else ""

    msg = session.pop('success', None)

    return render_template('dashboard.html', renewals=data, success=msg)

# ---------------- PAYMENT ----------------
@app.route('/payment/<int:id>')
def payment(id):

    if 'user_id' not in session:
        return redirect('/login')

    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM renewals WHERE id=%s", (id,))
    data = cur.fetchone()
    cur.close()

    if not data:
        return "Invalid Request ❌"

    if data['status'] != 'Approved':
        return "Wait for admin approval ❌"

    return render_template('payment.html', r=data)

# ---------------- PAYMENT SUCCESS ----------------
@app.route('/payment_success/<int:id>')
def payment_success(id):

    cur = mysql.connection.cursor()
    cur.execute("SELECT status FROM renewals WHERE id=%s", (id,))
    row = cur.fetchone()

    if not row or row['status'] != 'Approved':
        return "Unauthorized ❌"

    cur.execute("UPDATE renewals SET payment_status=%s WHERE id=%s", ('Paid', id))
    mysql.connection.commit()
    cur.close()

    session['success'] = "Payment Successful ✅"
    return redirect('/dashboard')

# ---------------- RECEIPT ----------------
from datetime import datetime

@app.route('/receipt/<int:id>')
def receipt(id):

    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT renewals.*, users.user_id AS real_user_id, users.name
        FROM renewals
        JOIN users ON renewals.user_id = users.id
        WHERE renewals.id=%s
    """, (id,))
    data = cur.fetchone()
    cur.close()

    if not data:
        return "Receipt not found ❌"

    if data['payment_status'] != 'Paid':
        return "Complete payment first ❌"

    # ✅ ADD THIS
    today = datetime.now().strftime('%d %B %Y, %I:%M %p')

    return render_template('receipt.html', r=data, today=today)

# ---------------- FORGOT PASSWORD ----------------
@app.route('/forgot', methods=['GET','POST'])
def forgot():
    if request.method == 'POST':
        user_id = request.form['userid']

        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM users WHERE user_id=%s", (user_id,))
        user = cur.fetchone()
        cur.close()

        if not user:
            return "User not found ❌"

        otp = random.randint(1000, 9999)
        session['fp_otp'] = otp
        session['fp_user'] = user_id

        print("Forgot OTP:", otp)

        return redirect('/reset_password')

    return render_template('forgot.html')

# ---------------- RESET PASSWORD ----------------
@app.route('/reset_password', methods=['GET','POST'])
def reset_password():
    if request.method == 'POST':
        otp = request.form['otp']
        new_pass = request.form['password']

        if not otp.isdigit():
            return "OTP must be numbers only ❌"

        if 'fp_otp' not in session:
            return "Session expired ❌"

        if int(otp) == session['fp_otp']:

            cur = mysql.connection.cursor()
            cur.execute("UPDATE users SET password=%s WHERE user_id=%s",
                        (new_pass, session['fp_user']))
            mysql.connection.commit()
            cur.close()

            session.pop('fp_otp', None)
            session.pop('fp_user', None)

            return render_template('password_success.html')
        else:
            return "Invalid OTP ❌"

    return render_template('reset_password.html')

# ---------------- ADMIN LOGIN ----------------
@app.route('/admin_login', methods=['GET','POST'])
def admin_login():
    if request.method == 'POST':
        if request.form['password'] == "prathi04":
            session['admin_access'] = True
            return redirect('/admin')
        else:
            return "Wrong Password ❌"

    return render_template('admin_login.html')

# ---------------- ADMIN ----------------
@app.route('/admin', methods=['GET','POST'])
def admin():

    if 'admin_access' not in session:
        return redirect('/admin_login')

    cur = mysql.connection.cursor()

    if request.method == 'POST':
        renewal_id = request.form['id']
        status = request.form['status']

        cur.execute("SELECT status, payment_status FROM renewals WHERE id=%s", (renewal_id,))
        row = cur.fetchone()

        if not row or row['payment_status'] == 'Paid' or row['status'] != 'Pending':
            return "Cannot modify ❌"

        cur.execute("UPDATE renewals SET status=%s WHERE id=%s", (status, renewal_id))
        mysql.connection.commit()

    cur.execute("""
        SELECT renewals.id, users.name, route, pass_type, expiry_date,
               status, payment_method, payment_status, amount
        FROM renewals
        JOIN users ON renewals.user_id = users.id
    """)
    data = cur.fetchall()
    cur.close()

    return render_template('admin.html', renewals=data)

# ---------------- LOGOUT ----------------
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

# ---------------- RUN ----------------
if __name__ == '__main__':
    app.run(debug=True)
