from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
import os
from datetime import datetime
from dateutil.relativedelta import relativedelta

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Database connection
user_db = 'user_management.db'
billing_db = 'billing_system.db'

def connect_db(db_name):
    return sqlite3.connect(db_name)

def init_user_db():
    with connect_db(user_db) as conn:
        cur = conn.cursor()
        cur.execute(
            'CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, password TEXT, role TEXT)')
        conn.commit()

        # Sample data for initial testing
        cur.execute("INSERT OR IGNORE INTO users (username, password, role) VALUES ('admin', 'admin123', 'admin')")
        cur.execute("INSERT OR IGNORE INTO users (username, password, role) VALUES ('user', 'user123', 'user')")
        conn.commit()

def init_billing_db():
    with connect_db(billing_db) as db:
        cursor = db.cursor()

        # Create the customers table if it doesn't exist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                phone_number TEXT NOT NULL,
                email TEXT NOT NULL,
                status TEXT NOT NULL,
                subscription_db TEXT NOT NULL  -- Added subscription_db column
            )
        ''')
        db.commit()

        # Add the subscription_db column if it does not exist
        cursor.execute("PRAGMA table_info(customers)")
        columns = [column[1] for column in cursor.fetchall()]
        if 'subscription_db' not in columns:
            cursor.execute('ALTER TABLE customers ADD COLUMN subscription_db TEXT NOT NULL DEFAULT ""')
            db.commit()

        # Create the vendors table if it doesn't exist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS vendors (
                id INTEGER PRIMARY KEY,
                package_name TEXT,
                name TEXT NOT NULL,
                bandwidth TEXT,
                schedule TEXT,
                start_date TEXT,
                end_date TEXT,
                status TEXT,
                disable TEXT,
                price REAL
            )
        ''')
        db.commit()

        # Insert initial vendors if they do not exist
        cursor.executemany('''
            INSERT OR IGNORE INTO vendors (id, name, package_name, bandwidth, schedule, start_date, end_date, status, disable, price)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', [
            (1, 'Mikrotik', 'Basic Package', '100 Mbps', 'monthly', '', '', 'Active', 'No', 50.0),
            (2, 'Cisco', 'Advanced Package', '1 Gbps', 'lifetime', '', '', 'Active', 'No', 500.0)
        ])
        db.commit()

        # Create the log table if it doesn't exist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                datetime TEXT NOT NULL,
                function TEXT NOT NULL,
                event TEXT NOT NULL
            )
        ''')
        db.commit()


# Initialize databases
init_user_db()
init_billing_db()

# Route for user login
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        with connect_db(user_db) as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password))
            user = cur.fetchone()

        if user:
            session['username'] = username
            session['role'] = user[3]
            create_log(datetime.now(), 'Login', f'User {username} logged in')
            return redirect(url_for('dashboard'))
        else:
            create_log(datetime.now(), 'Login', f'Failed login attempt for user {username}')
            return render_template('login.html', error='Invalid credentials. Please try again.')

    return render_template('login.html', error='')

# Route for the dashboard
@app.route('/dashboard')
def dashboard():
    if 'username' in session:
        if session['role'] == 'admin':
            create_log(datetime.now(), 'Dashboard', 'Admin user accessed dashboard')
            return redirect(url_for('add_user_page'))
        elif session['role'] == 'user':
            create_log(datetime.now(), 'Dashboard', 'Regular user accessed dashboard')
            return redirect(url_for('customer_page'))
    else:
        create_log(datetime.now(), 'Unauthorized Access', 'Unauthorized access to dashboard')
        return redirect(url_for('login'))

# Route for adding a user
@app.route('/add_user', methods=['GET', 'POST'])
def add_user_page():
    if 'username' in session and session['role'] == 'admin':
        if request.method == 'POST':
            username = request.form['username']
            password = request.form['password']
            role = request.form['role']

            with connect_db(user_db) as conn:
                cur = conn.cursor()
                cur.execute('INSERT INTO users (username, password, role) VALUES (?, ?, ?)',
                            (username, password, role))
                conn.commit()

            create_log(datetime.now(), 'Add User', f'Added user {username} with role {role}')
            flash('User added successfully', 'success')
            return redirect(url_for('add_user_page'))

        return render_template('customer.html')
    else:
        create_log(datetime.now(), 'Unauthorized Access', 'Unauthorized access to add user page')
        return redirect(url_for('login'))

# Route for viewing customers
@app.route('/customer')
def customer_page():
    with connect_db(billing_db) as db:
        cursor = db.cursor()
        cursor.execute('SELECT * FROM customers')
        customers = cursor.fetchall()
        customer_count = len(customers)
    create_log(datetime.now(), 'Customer Page', 'Viewed customer page')
    return render_template('customer.html', customers=customers, customer_count=customer_count)

@app.route('/add_customer', methods=['POST'])
def add_customer():
    if request.method == 'POST':
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        phone_number = request.form['phone_number']
        email = request.form['email']
        status = request.form['status']

        try:
            with connect_db(billing_db) as db:
                cursor = db.cursor()
                cursor.execute('INSERT INTO customers (first_name, last_name, phone_number, email, status) VALUES (?, ?, ?, ?, ?)',
                               (first_name, last_name, phone_number, email, status))
                db.commit()
            create_log(datetime.now(), 'Add Customer', f'Added customer: {first_name} {last_name}')
            flash('Customer added successfully', 'success')
        except sqlite3.Error as e:
            flash(f'Error adding customer: {str(e)}', 'danger')

    return redirect(url_for('customer_page'))
# Route for viewing a specific customer
@app.route('/customer/<int:customer_id>')
def view_customer(customer_id):
    with connect_db(billing_db) as db:
        cursor = db.cursor()
        cursor.execute('SELECT * FROM customers WHERE id = ?', (customer_id,))
        customer = cursor.fetchone()

        if not customer:
            create_log(datetime.now(), 'View Customer', f'Customer ID {customer_id} not found')
            flash('Customer not found', 'error')
            return redirect(url_for('customer_page'))

    create_log(datetime.now(), 'View Customer', f'Viewed details of Customer ID {customer_id}')
    return render_template('customer_info.html', customer=customer)
# Continued from previous code...

# Route for adding a subscription
@app.route('/add_subscription/<int:customer_id>', methods=['GET', 'POST'])
def add_subscription(customer_id):
    if 'username' in session:
        if session['role'] == 'user':
            try:
                vendors = get_vendors()  # Fetch vendors from the database
            except sqlite3.Error as e:
                flash(f'Error retrieving vendors: {str(e)}', 'danger')
                return redirect(url_for('dashboard'))

            # Fetch customer details to pass to the template
            with connect_db(billing_db) as db:
                cursor = db.cursor()
                cursor.execute('SELECT * FROM customers WHERE id = ?', (customer_id,))
                customer = cursor.fetchone()

            if request.method == 'POST':
                # Handle form submission
                buyer_name = request.form['buyer_name']
                location = request.form['location']
                address = request.form['address']
                bandwidth = request.form['bandwidth']
                schedule = request.form['schedule']
                start_date = request.form['start_date']
                vendor_id = request.form['vendor']
                price = request.form['price']
                end_date = None
                if schedule == 'monthly':
                    start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
                    end_date = start_date_obj + relativedelta(months=1)
                elif schedule == 'lifetime':
                    # Set end_date to None for lifetime subscription
                    end_date = request.form["end_date"]

                current_date = datetime.now().date()
                subscription_id = None

                # Check conditions for status and button
                status = None
                button = None

                if start_date == str(current_date):
                    status = 'Active'
                    create_bill(customer_id, subscription_id, status='Unpaid', price=float(price), bandwidth=bandwidth)
                    create_log(datetime.now(), 'Add Subscription', f'Subscription for Customer ID {customer_id} created. Status: Active')
                else:
                    status = 'Inactive'
                    create_log(datetime.now(), 'Add Subscription', f'Subscription for Customer ID {customer_id} created. Status: Inactive')

                if start_date > str(current_date):
                    button = None
                    status = 'Inactive'
                elif start_date == str(current_date) and status == 'Inactive':
                    button = 'Activate'
                elif end_date == str(current_date) and schedule == 'lifetime':
                    button = 'Update_date'

                if start_date < str(current_date):
                    if schedule == 'monthly':
                        button = 'Renew'
                        status = 'To_be_expired'
                    elif schedule == 'lifetime':
                        button = 'Update_date'
                        status = 'Expire'

                try:
                    create_subscription(customer_id, buyer_name, location, address, bandwidth, start_date, end_date, vendor_id, price, schedule, status)
                    flash('Subscription added successfully', 'success')
                except sqlite3.Error as e:
                    flash(f'Error adding subscription: {str(e)}', 'danger')

                return redirect(url_for('view_subscriptions', customer_id=customer_id))
            else:
                return render_template('add_subscription.html', customer_id=customer_id, vendors=vendors)  # Pass vendors to the template
        else:
            create_log(datetime.now(), 'Unauthorized Access', 'Unauthorized access to add subscription')
            flash('Unauthorized access', 'error')
            return redirect(url_for('dashboard'))
    else:
        create_log(datetime.now(), 'Unauthorized Access', 'Unauthorized access to add subscription')
        return redirect(url_for('login'))

# Function to create a subscription
def create_subscription(customer_id, buyer_name, location, address, bandwidth, start_date, end_date, vendor_id, price, schedule, status):
    # Connect to the customer's subscription database
    subscription_db = connect_db(f'subscriptions_{customer_id}.db')
    cursor = subscription_db.cursor()
    # Create subscriptions table if it doesn't exist
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS subscriptions (
            id INTEGER PRIMARY KEY,
            buyer_name TEXT NOT NULL,
            location TEXT NOT NULL,
            address TEXT NOT NULL,
            bandwidth TEXT NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT,
            vendor_id INTEGER NOT NULL,
            price REAL NOT NULL,
            schedule TEXT NOT NULL,
            status TEXT NOT NULL,
            FOREIGN KEY (vendor_id) REFERENCES vendors(id)
        )
    ''')
    # Insert subscription into the customer's database
    cursor.execute("INSERT INTO subscriptions (buyer_name, location, address, bandwidth, start_date, end_date, vendor_id, price, schedule, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (buyer_name, location, address, bandwidth, start_date, end_date, vendor_id, price, schedule, status))
    subscription_db.commit()
    subscription_db.close()

# Route for viewing subscriptions
@app.route('/view_subscriptions/<int:customer_id>')
def view_subscriptions(customer_id):
    try:
        # Connect to the customer's subscription database
        with connect_db(f'subscriptions_{customer_id}.db') as subscription_db:
            cursor = subscription_db.cursor()

            # Create subscriptions table if it doesn't exist
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS subscriptions (
                    id INTEGER PRIMARY KEY,
                    buyer_name TEXT NOT NULL,
                    location TEXT NOT NULL,
                    address TEXT NOT NULL,
                    bandwidth TEXT NOT NULL,
                    start_date TEXT NOT NULL,
                    end_date TEXT,
                    vendor_id INTEGER NOT NULL,
                    price REAL NOT NULL,
                    schedule TEXT NOT NULL,
                    status TEXT NOT NULL,
                    FOREIGN KEY (vendor_id) REFERENCES vendors(id)
                )
            ''')

            # Retrieve subscriptions from the customer's database
            cursor.execute('SELECT * FROM subscriptions')
            subscriptions = cursor.fetchall()

        # Fetch customer details to pass to the template
        with connect_db(billing_db) as db:
            cursor = db.cursor()
            cursor.execute('SELECT * FROM customers WHERE id = ?', (customer_id,))
            customer = cursor.fetchone()

        return render_template('subscriptions.html', customer=customer, subscriptions=subscriptions)

    except sqlite3.Error as e:
        flash(f'Error accessing subscriptions: {str(e)}', 'danger')
        return redirect(url_for('dashboard'))# Route for editing customer information

@app.route('/edit_customer/<int:customer_id>', methods=['GET', 'POST'])
def edit_customer(customer_id):
    if 'username' in session:
        if session['role'] == 'user':
            with connect_db(billing_db) as db:
                cursor = db.cursor()
                cursor.execute('SELECT * FROM customers WHERE id = ?', (customer_id,))
                customer_tuple = cursor.fetchone()
                if not customer_tuple:
                    create_log(datetime.now(), 'Edit Customer', f'Customer ID {customer_id} not found')
                    flash('Customer not found', 'error')
                    return redirect(url_for('customer_page'))

            customer = {
                'id': customer_tuple[0],
                'first_name': customer_tuple[1],
                'last_name': customer_tuple[2],
                'phone_number': customer_tuple[3],
                'email': customer_tuple[4],
                'status': customer_tuple[5]
            }

            if request.method == 'GET':
                create_log(datetime.now(), 'Edit Customer', f'Viewed edit page of Customer ID {customer_id}')
                return render_template('edit_customer.html', customer=customer)
            elif request.method == 'POST':
                first_name = request.form['first_name']
                last_name = request.form['last_name']
                phone_number = request.form['phone_number']
                email = request.form['email']
                status = request.form['status']

                with connect_db(billing_db) as db:
                    cursor = db.cursor()
                    cursor.execute('''
                        UPDATE customers 
                        SET first_name = ?, last_name = ?, phone_number = ?, email = ?, status = ?
                        WHERE id = ?
                    ''', (first_name, last_name, phone_number, email, status, customer_id))
                    db.commit()

                create_log(datetime.now(), 'Edit Customer', f'Customer ID {customer_id} information updated')
                flash('Customer information updated successfully', 'success')
                return redirect(url_for('customer_page'))
        else:
            create_log(datetime.now(), 'Unauthorized Access', 'Unauthorized access to edit customer')
            flash('Unauthorized access', 'error')
            return redirect(url_for('dashboard'))
    else:
        create_log(datetime.now(), 'Unauthorized Access', 'Unauthorized access to edit customer')
        return redirect(url_for('login'))


@app.route('/delete_customer/<int:customer_id>', methods=['POST'])
def delete_customer(customer_id):
    if 'username' in session:
        if session['role'] == 'user':
            try:
                # Fetch the filename of the subscription database for the customer
                with connect_db(billing_db) as db:
                    cursor = db.cursor()
                    cursor.execute('SELECT subscription_db FROM customers WHERE id = ?', (customer_id,))
                    filename = cursor.fetchone()
                    if filename:
                        filename = filename[0]
                        # Check if the database file exists and delete it
                        if os.path.exists(filename):
                            os.remove(filename)

                # Delete customer from the customers table
                with connect_db(billing_db) as db:
                    cursor = db.cursor()
                    cursor.execute('DELETE FROM customers WHERE id = ?', (customer_id,))
                    db.commit()

                create_log(datetime.now(), 'Delete Customer', f'Deleted customer ID {customer_id} and associated database')
                flash('Customer and associated database deleted successfully', 'success')
            except Exception as e:
                create_log(datetime.now(), 'Delete Customer', f'Error deleting customer ID {customer_id}: {str(e)}')
                flash('An error occurred while deleting the customer', 'error')

            return redirect(url_for('customer_page'))
        else:
            create_log(datetime.now(), 'Unauthorized Access', 'Unauthorized access to delete customer')
            flash('Unauthorized access', 'error')
            return redirect(url_for('dashboard'))
    else:
        create_log(datetime.now(), 'Unauthorized Access', 'Unauthorized access to delete customer')
        return redirect(url_for('login'))


# Function to connect to a customer's subscription database
def connect_subscription_db(customer_id):
    with connect_db(billing_db) as db:
        cursor = db.cursor()
        cursor.execute('SELECT subscription_db FROM customers WHERE id = ?', (customer_id,))
        filename = cursor.fetchone()
        if filename:
            return sqlite3.connect(filename[0]), filename[0]  # Return both connection object and filename
        else:
            return None, None  # Return None if filename is not found

# Function to create a bill
def create_bill(customer_id, subscription_id, status, price, bandwidth):
    with connect_db(billing_db) as db:
        cursor = db.cursor()
        cursor.execute('''
            INSERT INTO bills (customer_id, subscription_id, status, price, bandwidth) 
            VALUES (?, ?, ?, ?, ?)
        ''', (customer_id, subscription_id, status, price, bandwidth))
        db.commit()

# Function to create a log entry
def create_log(datetime, function, event):
    with connect_db(billing_db) as db:
        cursor = db.cursor()
        cursor.execute('INSERT INTO log (Datetime, Function, Event) VALUES (?, ?, ?)', (datetime, function, event))
        db.commit()

# Function to get vendors from the database
def get_vendors():
    with connect_db(billing_db) as db:
        cursor = db.cursor()
        cursor.execute('SELECT id, name FROM vendors')
        vendors = cursor.fetchall()
    return vendors

# Function to get the filename of a customer's subscription database
def get_customer_subscription_db_filename(customer_id):
    with connect_db(billing_db) as db:
        cursor = db.cursor()
        cursor.execute('SELECT subscription_db FROM customers WHERE id = ?', (customer_id,))
        filename = cursor.fetchone()
        if filename:
            return filename[0]
        else:
            return None

# Other routes and functions...

if __name__ == '__main__':
    app.run('0.0.0.0', debug=True, port=3216)


# Function to create a log entry
def create_log(datetime, function, event):
    with connect_db(billing_db) as db:
        cursor = db.cursor()
        cursor.execute('INSERT INTO log (datetime, function, event) VALUES (?, ?, ?)', (datetime, function, event))
        db.commit()

