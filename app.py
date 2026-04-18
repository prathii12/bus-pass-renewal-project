from flask import Flask, render_template, request, redirect, session
from flask_mysqldb import MySQL
from datetime import datetime, timedelta   # ✅ correct place

app = Flask(__name__)
app.secret_key = "secretkey"

# MySQL Configuration
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
import re
import random

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        user_id = request.form['user_id']
        phone = request.form['phone']
        password = request.form['password']

        # ❌ user_id must contain number
        if not re.search(r'\d', user_id):
            return "User ID must contain numbers (ex: prathi123)"

        cur = mysql.connection.cursor()

        # ❌ check duplicate user_id
        cur.execute("SELECT * FROM users WHERE user_id=%s", (user_id,))
        existing = cur.fetchone()

        if existing:
            return "User ID already exists"

        # ✅ generate OTP
        otp = random.randint(1000, 9999)
        session['otp'] = otp
        session['temp_user'] = (name, user_id, phone, password)

        print("OTP:", otp)  # check in terminal

        return redirect('/verify_otp')   # ✅ STOP here

    return render_template('register.html')

# ---------------- LOGIN ----------------
@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        user_id = request.form['user_id']
        password = request.form['password']

        cur = mysql.connection.cursor()
        cur.execute(
            "SELECT * FROM users WHERE user_id=%s AND password=%s",
            (user_id, password)
        )
        user = cur.fetchone()
        cur.close()

        # ✅ ADD HERE 👇
        print("USER DATA:", user)
        if user:
            print("ROLE:", user['role'])

        if user:
            session['user_id'] = user['id']
            session['username'] = user['user_id']
            session['role'] = user['role']

            if user['role'].lower() == 'admin':
                return redirect('/admin')
            else:
                return redirect('/dashboard')
        else:
            return "Invalid Login"

    return render_template('login.html')


#-----------------DASHBOARD-------------------
@app.route('/dashboard', methods=['GET','POST'])
def dashboard():

    if 'user_id' not in session:
        return redirect('/login')

    if request.method == 'POST':
        route = request.form['route']
        pass_type = request.form['pass_type']
        payment_method = request.form['payment_method']

        # amount
        if pass_type == "Monthly":
            amount = 500
        elif pass_type == "Yearly":
            amount = 5000

        # expiry
        today = datetime.now()
        if pass_type == "Monthly":
            expiry = today + timedelta(days=30)
        elif pass_type == "Yearly":
            expiry = today + timedelta(days=365)

        expiry = expiry.strftime('%Y-%m-%d')

        # insert
        cur = mysql.connection.cursor()
        cur.execute(
            "INSERT INTO renewals(user_id, route, pass_type, expiry_date, payment_method, amount, payment_status) VALUES(%s, %s, %s, %s, %s, %s, %s)",
            (session['user_id'], route, pass_type, expiry, payment_method, amount, 'Pending')
        )
        mysql.connection.commit()
        cur.close()

    # fetch
    cur = mysql.connection.cursor()
    cur.execute("""
    SELECT renewals.*, users.user_id AS real_user_id, users.name
    FROM renewals
    JOIN users ON renewals.user_id = users.id
    WHERE renewals.user_id=%s
    """, (session['user_id'],))
    data = cur.fetchall()
    cur.close()

    # reminder
    for r in data:
        expiry = datetime.strptime(str(r['expiry_date']), '%Y-%m-%d')
        today = datetime.now()

        if (expiry - today).days <= 3:
            r['reminder'] = "⚠ Expiring soon"
        else:
            r['reminder'] = ""

    # ✅ THIS MUST BE INSIDE FUNCTION
    msg = session.pop('success', None)

    return render_template('dashboard.html', renewals=data, success=msg)


# ---------------- PAYMENT ---------------- 
@app.route('/payment/<int:id>')
def payment(id):
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM renewals WHERE id=%s", (id,))
    data = cur.fetchone()
    cur.close()

    return render_template('payment.html', r=data)


#-------------PAYMENT_SUCCESS-------------
@app.route('/payment_success/<int:id>')
def payment_success(id):
    session['success'] = "Payment Successful ✅"

    cur = mysql.connection.cursor()
    cur.execute(
        "UPDATE renewals SET payment_status=%s WHERE id=%s",
        ('Paid', id)
    )
    mysql.connection.commit()
    cur.close()

    return redirect('/dashboard')

#---------------FORGOT----------------
@app.route('/forgot', methods=['GET','POST'])
def forgot():
    if request.method == 'POST':
        user_id = request.form['user_id']
        new_password = request.form['password']

        cur = mysql.connection.cursor()
        cur.execute(
            "UPDATE users SET password=%s WHERE user_id=%s",
            (new_password, user_id)
        )
        mysql.connection.commit()
        cur.close()

        return render_template('password_success.html')

    return render_template('forgot.html')

#-------------RECEIPT--------------
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

    return render_template('receipt.html', r=data)

#------------------VERIFY_OTP------------------
@app.route('/verify_otp', methods=['GET','POST'])
def verify_otp_otp():
    if request.method == 'POST':
        user_otp = request.form['otp']

        if int(user_otp) == session.get('otp'):
            name, user_id, phone, password = session.get('temp_user')

            cur = mysql.connection.cursor()
            cur.execute(
                "INSERT INTO users(name, user_id, phone, password, role) VALUES(%s,%s,%s,%s,%s)",
                (name, user_id, phone, password, 'user')
            )
            mysql.connection.commit()
            cur.close()

            return render_template('success.html')
        else:
            return "Invalid OTP ❌"

    return render_template('otp.html')

#---------------admin_login--------------
@app.route('/admin_login', methods=['GET','POST'])
def admin_login():
    if request.method == 'POST':
        password = request.form['admin_pass']

        # 🔐 your secret admin password
        if password == "prathi04":
            session['admin_access'] = True
            return redirect('/admin')
        else:
            return "Wrong Admin Password ❌"

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

        # ✅ CHECK ONLY AFTER GETTING renewal_id
        cur.execute("SELECT status, payment_status FROM renewals WHERE id=%s", (renewal_id,))
        row = cur.fetchone()

        if row['payment_status'] == 'Paid' or row['status'] != 'Pending':
            return "Cannot modify after approval/payment ❌"

        # ✅ UPDATE
        cur.execute(
            "UPDATE renewals SET status=%s WHERE id=%s",
            (status, renewal_id)
        )
        mysql.connection.commit()

    # ✅ THIS PART ALWAYS RUNS
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