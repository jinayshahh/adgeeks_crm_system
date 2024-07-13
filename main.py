from collections import defaultdict
from flask import Flask, request, redirect, session, render_template, jsonify, url_for, flash, send_from_directory
import mysql.connector
from flask_cors import CORS
from datetime import datetime, time, timedelta
import time
import random
import string
import shutil
import re
import os
from werkzeug.utils import secure_filename
from googleapiclient.discovery import build
from google.oauth2 import service_account
from googleapiclient.http import MediaFileUpload
import pytz

# Set the timezone to Indian Standard Time
indian_tz = pytz.timezone('Asia/Kolkata')

# Get the current date and time in Indian Standard Time
current_time_in_india = datetime.now(indian_tz)

# Format the date as DD-MM-YYYY
todays_date = current_time_in_india.strftime('%d-%m-%Y')

SCOPES = ['https://www.googleapis.com/auth/drive']
SERVICE_ACCOUNT_FILES = 'service_account.json'
PARENT_FOLDER_ID = "1oD3gUD2PYT5ZL5D74r7cezh5Sz8IyIW7"


def authenticate():
    creds = service_account.Credentials.from_service_account_file(SERVICE_ACCOUNT_FILES, scopes=SCOPES)
    return creds


def create_drive_folder(name, parents):
    creds = authenticate()
    service = build('drive', 'v3', credentials=creds)
    file_metadata = {
        'name': name,
        'mimeType': 'application/vnd.google-apps.folder',
        'parents': parents
    }
    file = service.files().create(body=file_metadata, fields='id').execute()
    return file.get('id')


def upload_file_to_drive(filename, mime_type, parent_id):
    creds = authenticate()
    service = build('drive', 'v3', credentials=creds)
    file_metadata = {
        'name': os.path.basename(filename),
        'parents': [parent_id]
    }
    media = MediaFileUpload(filename, mimetype=mime_type)
    file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    return file.get('id')


def upload_directory_to_drive(directory_path, parent_id, folder_name):
    # Assume directory_path is a directory
    folder_id = create_drive_folder(os.path.basename(directory_path), [parent_id])
    for item in os.listdir(directory_path):
        item_path = os.path.join(directory_path, item)
        if os.path.isfile(item_path):
            # Define MIME type as needed or use 'application/octet-stream' as generic
            upload_file_to_drive(item_path, 'application/octet-stream', folder_id)
        elif os.path.isdir(item_path):
            # Recursive call to handle subdirectories
            upload_directory_to_drive(item_path, folder_id)
    # Generate and return the URL to access the folder
    folder_url = f"https://drive.google.com/drive/folders/{folder_id}"
    new_folder_name = folder_name.replace("Final", "Raw")
    mycur.execute(f"SELECT work_id FROM work_record where title = '{folder_name}'")
    last_creator_id = mycur.fetchone()
    if last_creator_id:
        mycur.execute(
            f"UPDATE work_record SET initial_task_link = '{folder_url}' WHERE title = '{folder_name}'")
        conn.commit()
    else:
        mycur.execute(
            f"UPDATE work_record SET final_task_link = '{folder_url}' WHERE title = '{new_folder_name}'")
        conn.commit()
    # shutil.rmtree(directory_path)
    return folder_url


conn = mysql.connector.connect(
    user="root",
    password="abcd1234",
    host="localhost",
    database="adgeeks_crm_system",
    port="3306"
)
mycur = conn.cursor(buffered=True)
app = Flask(__name__)
CORS(app)
app.secret_key = 'your_secret_key'  # Set a secret key for session management

# Configure the upload folder
UPLOAD_FOLDER = os.path.join('static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}

UPLOAD_TASK = os.path.join('static', 'work')
os.makedirs(UPLOAD_TASK, exist_ok=True)
app.config['UPLOAD_TASK'] = UPLOAD_TASK
app.config['MAX_CONTENT_LENGTH'] = 50000 * 1024 * 1024  # 1500 Megabytes

if not os.path.exists(app.config['UPLOAD_TASK']):
    os.makedirs(app.config['UPLOAD_TASK'])

month_raw = {}
month_final = {}


def make_folder(username):
    mycur.execute(
        f"select username, months, start_date, end_date from client_information where username = '{username}'")
    client_details = mycur.fetchall()
    conn.commit()
    month_service = client_details[0][1]
    # month_start = client_details[0][1]
    # formatted_start_date = month_start.strftime("%Y-%m-%d")
    # month_end = client_details[0][2]
    # formatted_end_date = month_end.strftime("%Y-%m-%d")
    # print(formatted_start_date, formatted_end_date)
    for i in range(1, month_service + 1):
        month_raw[i] = os.path.join(app.config['UPLOAD_TASK'], f"{client_details[0][0]} Raw month {i}")
        if not os.path.exists(month_raw[i]):
            os.makedirs(month_raw[i])
        month_final[i] = os.path.join(app.config['UPLOAD_TASK'], f"{client_details[0][0]} Final month {i}")
        if not os.path.exists(month_final[i]):
            os.makedirs(month_final[i])
    return


def select_folder(username):
    mycur.execute(
        f"select username, months, start_date, end_date, work_status from client_information where username = '{username}'")
    client_details = mycur.fetchall()
    conn.commit()
    month_service = client_details[0][1]
    month_start = client_details[0][2]
    today_date_format = datetime.now()  # or datetime(2024, 6, 30) for testing with a specific date
    mycur.execute(f"select work_id from work_record where client_username = '{username}' and work_status = 'Completed'")
    no_folders = mycur.fetchall()
    conn.commit()
    print(len(no_folders), "this")
    if len(no_folders) == 0:
        current_month = ((today_date_format.year - month_start.year) * 12 + today_date_format.month - month_start.month
                         + 1)
    else:
        current_month = ((today_date_format.year - month_start.year) * 12 + today_date_format.month - month_start.month
                         + 1 + len(no_folders))
    if 0 < current_month <= month_service:
        directory_path_folder = f"static/work/{client_details[0][0]} Raw month {current_month}"
        folder_name = f"{client_details[0][0]} Raw month {current_month}"
        return directory_path_folder, folder_name
    else:
        print("Current date is not within the service period.")
    return "error 404"


def allowed_file(filename):
    """Check if the file has one of the allowed extensions."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower()


def generate_password(length=12):
    characters = string.ascii_letters + string.digits + "!@#$%^&*()-_=+[]{}|;:,.<>?/"
    characters = characters.replace('"', '').replace("'", "")
    return ''.join(random.choices(characters, k=length))


def delete_image(file_path):
    if os.path.exists(file_path):
        os.remove(file_path)
        return print(f"deleted image: {file_path}")
    else:
        return print(f"No such image found: {file_path}")


def task_listing(directory_path_sql, client_username):
    time.sleep(2)
    try:
        # Use parameterized queries to prevent SQL injection
        sql_query = ("UPDATE work_record SET title = %s WHERE client_username = %s and work_status != 'Completed'"
                     " ORDER BY work_id ASC LIMIT 1")
        mycur.execute(sql_query, (directory_path_sql, client_username))
        conn.commit()
    except Exception as e:
        print(f"An error occurred: {e}")
        # Optionally re-raise the exception if you want calling code to handle it
        raise

    return directory_path_sql


def fetch_files(folder_name_fetch):
    try:
        path = f"static/work/{folder_name_fetch}/"
        files_fetched = [f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))]
        return files_fetched
    except:
        pass


@app.route('/tester')
def tester():
    return render_template("tester.html")



#
#
# begin log in process
#
#
#
@app.route('/', methods=['GET', 'POST'])
def log_in():
    error = None
    if request.method == 'POST':
        input_login_username = request.form['Username']
        input_login_password = request.form['password']
        mycur.execute(
            f"select * from adgeeks_passwords where username = '{input_login_username}'")
        user_password = mycur.fetchall()
        if user_password:
            if user_password[0][3] == input_login_password:
                if user_password[0][4] == "Admin":
                    return redirect("/admin_dashboard")
                elif user_password[0][4] == "client":
                    return redirect(url_for('client_dashboard', user_name=input_login_username))
                else:
                    return redirect(url_for('creator_dashboard', user_name=input_login_username))
            else:
                error = "Incorrect credentials. Please try again."
    return render_template("adgeeks_login.html", error=error)


@app.route('/change_password_username', methods=['GET', 'POST'])
def change_password_username():
    error = None
    if request.method == 'POST':
        input_login_username = request.form['Username']
        mycur.execute(
            f"select * from adgeeks_passwords where username = '{input_login_username}'")
        user_password = mycur.fetchall()
        if user_password:
            session['change_password_username'] = input_login_username
            return redirect("/otp")
        else:
            error = "Incorrect Username. Please try again."
    return render_template("adgeeks_username.html", error=error)


# Function to generate OTP
def generate_otp():
    otp = ''.join(random.choices(string.digits, k=6))
    return otp


@app.route('/otp', methods=['GET', 'POST'])
def otp():
    error = None
    if request.method == 'POST':
        input_login_otp = request.form['password_otp']
        stored_otp = session.get('otp')

        print(f"Entered OTP: {input_login_otp}, Generated OTP: {stored_otp}")

        if input_login_otp == stored_otp:
            return redirect("/new_password")
        else:
            error = "Incorrect OTP. Please try again."

    # Generate and store OTP in session when the page is loaded (GET request)
    if request.method == 'GET' or request.path == '/otp/resend':
        session['otp'] = generate_otp()
        print(f"Generated OTP: {session['otp']}")

    return render_template("adgeeks_otp.html", error=error)


@app.route('/otp/resend', methods=['GET'])
def resend_otp():
    session['otp'] = generate_otp()
    flash("A new OTP has been sent.")
    return redirect("/otp")


@app.route('/new_password', methods=['GET', 'POST'])
def new_password():
    error = None
    change_password_username = session.get('change_password_username')
    print(change_password_username)
    if request.method == 'POST':
        reset_password = request.form['password']
        confirm_password = request.form['confirm-password']
        if reset_password == confirm_password:
            mycur.execute(
                f"UPDATE adgeeks_passwords SET password = '{reset_password}' WHERE username = '{change_password_username}';")
            conn.commit()
            return redirect('/password_changed')
        else:
            error = "Password doesnt match. Please try again."
    return render_template("adgeeks_newpassword.html", error=error)


@app.route('/password_changed')
def password_changed():
    return render_template("adgeeks_passwordchanged.html")


#
#
#
# end log in process
#
#
#
#
#
#
# begin admin section
#
#
#
@app.route('/admin_dashboard')
def admin_dashboard():
    return render_template("adgeeks_admin_dashboard.html")


@app.route('/admin_target_section_individual/<creator_username>')
def admin_target_section_individual(creator_username):
    mycur.execute(f"SELECT * FROM work_record where creator_username = '{creator_username}' and admin_roll_out = 'no'")
    work_records = mycur.fetchall()
    conn.commit()
    print(work_records)
    return render_template("adgeeks_admin_target_section_individual.html", work_records=work_records)


@app.route('/admin_target_section_all')
def admin_target_section_all():
    mycur.execute(f"SELECT * FROM work_record")
    work_records = mycur.fetchall()
    conn.commit()
    print(work_records)
    return render_template("adgeeks_admin_target_section_all.html", work_records=work_records)


# client section
@app.route('/admin_client_panel', methods=['GET', 'POST'])
def admin_client_panel():
    mycur.execute("SELECT * FROM adgeeks_crm_system.client_information WHERE client_status != 'Delete'")
    client_details = mycur.fetchall()
    conn.commit()
    return render_template("adgeeks_admin_clientpanel.html", client_details=client_details)


@app.route('/admin_client_details_block/<int:client_id>', methods=['GET', 'POST'])
def admin_client_details_block(client_id):
    mycur.execute(f"SELECT * FROM client_information WHERE client_id = '{client_id}'")
    client_details = mycur.fetchall()
    conn.commit()
    if client_details:
        client_details = [client_details]
        for client in client_details:
            if client[0][28] == 'Block':
                mycur.execute(f"UPDATE client_information SET client_status = 'Active' WHERE client_id = '{client_id}'")
                conn.commit()
            else:
                mycur.execute(f"UPDATE client_information SET client_status = 'Block' WHERE client_id = '{client_id}'")
                conn.commit()
    return redirect(url_for('admin_client_panel'))


@app.route('/admin_client_details_delete/<int:client_id>', methods=['GET', 'POST'])
def admin_client_details_delete(client_id):
    mycur.execute(f"SELECT * FROM client_information WHERE client_id = '{client_id}'")
    client_details = mycur.fetchall()
    conn.commit()
    if client_details:
        client_details = [client_details]
        for client in client_details:
            if client[0][28] == 'Delete':
                mycur.execute(f"UPDATE client_information SET client_status = 'Active' WHERE client_id = '{client_id}'")
                conn.commit()
            else:
                mycur.execute(f"UPDATE client_information SET client_status = 'Delete' WHERE client_id = '{client_id}'")
                conn.commit()
    return redirect(url_for('admin_client_panel'))


@app.route('/admin_client_work')
def admin_client_work():
    return render_template("adgeeks_admin_client_work.html")


@app.route('/admin_client_details/<int:client_id>')
def admin_client_details(client_id):
    mycur.execute(f"SELECT * FROM adgeeks_crm_system.client_information WHERE client_id = {client_id}")
    client_details = mycur.fetchone()
    conn.commit()
    if client_details:
        client_details = [client_details]
        print(client_details)
        return render_template("adgeeks_admin_client_details.html", client_details=client_details)
    else:
        flash('Client not found!', 'error')
        return redirect(url_for('admin_client_panel'))


@app.route('/admin_client_details_update/<int:client_id>')
def admin_client_details_update(client_id):
    mycur.execute(f"SELECT * FROM adgeeks_crm_system.client_information WHERE client_id = {client_id}")
    client_details = mycur.fetchone()
    conn.commit()
    if client_details:
        client_details = [client_details]
        print(client_details)
        return render_template("adgeeks_admin_client_details_update.html", client_details=client_details)
    else:
        flash('Client not found!', 'error')
        return redirect(url_for('admin_dashboard'))


@app.route('/admin_client_details_update_form/<int:client_id>', methods=['GET', 'POST'])
def admin_client_details_update_form(client_id):
    if request.method == 'POST':
        time.sleep(3)
        mycur.execute(f"SELECT * FROM adgeeks_crm_system.client_information WHERE client_id = {client_id}")
        client_details = mycur.fetchone()
        client_details = [client_details]
        conn.commit()
        print(client_details)
        for client in client_details:
            client_form_full_name = request.form['full_name']
            if client_form_full_name:
                client_form_full_name_data = client_form_full_name
            else:
                client_form_full_name_data = client[1]
            client_form_company_name = request.form['company_name']
            if client_form_company_name:
                client_form_company_name_data = client_form_company_name
            else:
                client_form_company_name_data = client[2]

            client_form_user_name = request.form['user_name']
            if client_form_user_name:
                client_form_user_name_data = client_form_user_name
            else:
                client_form_user_name_data = client[3]

            client_form_password = request.form['password']
            if client_form_password:
                client_form_password_data = client_form_password
            else:
                client_form_password_data = client[4]

            client_form_email = request.form['email']
            if client_form_email:
                client_form_email_data = client_form_email
            else:
                client_form_email_data = client[5]

            client_form_mobileno = request.form['mobileno']
            if client_form_mobileno:
                client_form_mobileno_data = client_form_mobileno
            else:
                client_form_mobileno_data = client[6]

            client_form_address = request.form['address']
            if client_form_address:
                client_form_address_data = client_form_address
            else:
                client_form_address_data = client[8]

            client_form_city = request.form['city']
            if client_form_city:
                client_form_city_data = client_form_city
            else:
                client_form_city_data = client[7]

            client_form_gstnumber = request.form['gstnumber']
            if client_form_gstnumber:
                client_form_gstnumber_data = client_form_gstnumber
            else:
                client_form_gstnumber_data = client[9]
            client_form_service = request.form.getlist('service')
            if client_form_service:
                client_form_service_str = ', '.join(client_form_service)
                client_form_service_data = client_form_service_str
            else:
                client_form_service_data = client[10]
            client_form_payment_period = request.form['payment_period']
            if client_form_payment_period:
                client_form_payment_period_data = client_form_payment_period
            else:
                client_form_payment_period_data = client[22]
            client_form_payment_amount = request.form['payment_amount']
            if client_form_payment_amount:
                client_form_payment_amount_data = client_form_payment_amount
            else:
                client_form_payment_amount_data = client[23]
            client_form_start_date = request.form['start_date']
            if client_form_start_date:
                client_form_start_date_data = client_form_start_date
            else:
                client_form_start_date_data = client[24]
            client_form_end_date = request.form['end_date']
            if client_form_end_date:
                client_form_end_date_data = client_form_end_date
            else:
                client_form_end_date_data = client[25]
                # Update client information in the database
            uploaded_file_path = request.form.get('uploaded_file_path', '')
            if uploaded_file_path:
                delete_image(client[21])
                uploaded_file_path_data = uploaded_file_path
            else:
                uploaded_file_path_data = client[21]
            print(uploaded_file_path_data)
            mycur.execute("""
                    UPDATE client_information SET
                        full_name = %s,
                        company_name = %s,
                        username = %s,
                        password = %s,
                        email = %s,
                        mobile_number = %s,
                        city = %s,
                        address = %s,
                        gst_number = %s,
                        services = %s,
                        invoice = %s,
                        months = %s,
                        amount = %s,
                        start_date = %s,
                        end_date = %s,
                        assigned_creator = %s
                    WHERE client_id = %s
                """, (
                client_form_full_name_data, client_form_company_name_data, client_form_user_name_data,
                client_form_password_data, client_form_email_data, client_form_mobileno_data, client_form_city_data,
                client_form_address_data, client_form_gstnumber_data, client_form_service_data, uploaded_file_path_data,
                client_form_payment_period_data, client_form_payment_amount_data, client_form_start_date_data,
                client_form_end_date_data, 'N/A', client_id
            ))
            conn.commit()
            return redirect(url_for("admin_client_details", client_id=client_id))
    return redirect("/admin_client_details")


@app.route('/admin_client_details_task_section')
def admin_client_details_task_section():
    return render_template("adgeeks_admin_client_details_task_section.html")


@app.route('/admin_client_details_worksection')
def admin_client_details_worksection():
    return render_template("adgeeks_admin_client_details_worksection.html")


@app.route('/admin_client_details_work_review_section')
def admin_client_details_work_review_section():
    return render_template("adgeeks_admin_client_details_work_review_section.html")


@app.route('/admin_client_details_work_view_section')
def admin_client_details_work_view_section():
    return render_template("adgeeks_admin_client_details_work_view_section.html")


@app.route('/admin_client_details_performancesection')
def admin_client_details_performancesection():
    return render_template("adgeeks_admin_client_details_performancesection.html")


@app.route('/admin_client_details_creativesection')
def admin_client_details_creativesection():
    return render_template("adgeeks_admin_client_details_creativesection.html")


@app.route('/admin_client_details_strategysection')
def admin_client_details_strategysection():
    return render_template("adgeeks_admin_client_details_strategysection.html")


@app.route('/upload_image', methods=['POST'])
def upload_image():
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])

    file = request.files.get('image')
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        return jsonify(success=True, file_path=file_path)
    return jsonify(success=False)


@app.route('/admin_client_creation_form', methods=['GET', 'POST'])
def admin_client_creation_form():
    if request.method == 'POST':
        time.sleep(3)
        mycur.execute("SELECT client_id FROM client_information ORDER BY client_id DESC LIMIT 1")
        last_client_id = mycur.fetchone()
        if last_client_id:
            last_client_id = int(last_client_id[0])
        try:
            client_id = last_client_id + 1
        except:
            client_id = 1
        mycur.execute("SELECT id_passwords FROM adgeeks_passwords ORDER BY id_passwords DESC LIMIT 1")
        last_password_id = mycur.fetchone()

        if last_password_id:
            last_password_id = int(last_password_id[0])
        try:
            password_id = last_password_id + 1
        except:
            password_id = 1
        client_form_full_name = request.form['full_name']
        client_form_company_name = request.form['company_name']
        client_form_user_name = request.form['user_name']
        client_form_password = generate_password()
        client_form_email = request.form['email']
        client_form_mobileno = request.form['mobileno']
        client_form_address = request.form['address']
        client_form_city = request.form['city']
        client_form_gstnumber = request.form['gstnumber']
        client_form_status = request.form['client_status']
        client_form_service = request.form.getlist('service')
        if client_form_service:
            client_form_service_str = ', '.join(client_form_service)
            client_form_service_data = client_form_service_str
        else:
            client_form_service_data = "N/A"
        client_form_budget_performance = request.form['budget_performance']
        if client_form_budget_performance:
            client_form_budget_performance_data = client_form_budget_performance
        else:
            client_form_budget_performance_data = "N/A"
        client_form_performance_months = request.form['performance_months']
        if client_form_performance_months:
            client_form_performance_months_data = client_form_performance_months
        else:
            client_form_performance_months_data = "N/A"
        client_form_info_performance = request.form['info_performance']
        if client_form_info_performance:
            client_form_info_performance_data = client_form_info_performance
        else:
            client_form_info_performance_data = "N/A"
        client_form_reels_creative = request.form['reels_creative']
        if client_form_reels_creative:
            client_form_reels_creative_data = client_form_reels_creative
        else:
            client_form_reels_creative_data = "N/A"
        client_form_info_creative_reel = request.form['info_creative_reel']
        if client_form_info_creative_reel:
            client_form_info_creative_reel_data = client_form_info_creative_reel
        else:
            client_form_info_creative_reel_data = "N/A"
        client_form_posts_creative = request.form['posts_creative']
        if client_form_posts_creative:
            client_form_posts_creative_data = client_form_posts_creative
        else:
            client_form_posts_creative_data = "N/A"
        client_form_info_creative_posts = request.form['info_creative_posts']
        if client_form_info_creative_posts:
            client_form_info_creative_posts_data = client_form_info_creative_posts
        else:
            client_form_info_creative_posts_data = "N/A"
        client_form_story_creative = request.form['story_creative']
        if client_form_story_creative:
            client_form_story_creative_data = client_form_story_creative
        else:
            client_form_story_creative_data = 'N/A'
        client_form_info_creative_story = request.form['info_creative_story']
        if client_form_info_creative_story:
            client_form_info_creative_story_data = client_form_info_creative_story
        else:
            client_form_info_creative_story_data = "N/A"
        client_form_strategy = request.form.getlist('strategy')
        if client_form_strategy:
            client_form_strategy_str = ', '.join(client_form_strategy)
            client_form_strategy_data = client_form_strategy_str
        else:
            client_form_strategy_data = "N/A"
        client_form_overview_strategy = request.form['overview_strategy']
        if client_form_overview_strategy:
            client_form_overview_strategy_data = client_form_overview_strategy
        else:
            client_form_overview_strategy_data = 'N/A'
        client_form_payment_period = request.form['payment_period']
        if client_form_payment_period:
            client_form_payment_period_data = client_form_payment_period
        else:
            client_form_payment_period_data = '0'
        client_form_payment_amount = request.form['payment_amount']
        if client_form_payment_amount:
            client_form_payment_amount_data = client_form_payment_amount
        else:
            client_form_payment_amount_data = '0'
        client_form_start_date = request.form['start_date']
        if client_form_start_date:
            client_form_start_date_data = client_form_start_date
        else:
            client_form_start_date_data = '2024-03-28'
        client_form_end_date = request.form['end_date']
        if client_form_end_date:
            client_form_end_date_data = client_form_end_date
        else:
            client_form_end_date_data = '2024-03-28'
        uploaded_file_path = request.form.get('uploaded_file_path', '')
        mycur.execute("INSERT INTO client_information (client_id, full_name, company_name, username, password, email,"
                      " mobile_number, city, address, gst_number, services, performance_budget, performance_months,"
                      " info_performance, reels_creative, info_reels, posts_creative, info_posts, story_creative, "
                      "info_story, strategy, overview_strategy, invoice, months, amount, start_date, end_date, "
                      "assigned_creator, client_status) VALUES "
                      f"('{client_id}', '{client_form_full_name}', '{client_form_company_name}', "
                      f"'{client_form_user_name}', '{client_form_password}', '{client_form_email}', "
                      f"'{client_form_mobileno}', '{client_form_city}', '{client_form_address}',"
                      f" '{client_form_gstnumber}', '{client_form_service_data}', "
                      f"'{client_form_budget_performance_data}', '{client_form_performance_months_data}',"
                      f" '{client_form_info_performance_data}', '{client_form_reels_creative_data}', "
                      f"'{client_form_info_creative_reel_data}', "
                      f"'{client_form_posts_creative_data}', '{client_form_info_creative_posts_data}', "
                      f"'{client_form_story_creative_data}', '{client_form_info_creative_story_data}', "
                      f"'{client_form_strategy_data}', '{client_form_overview_strategy_data}', '{uploaded_file_path}'"
                      f", '{client_form_payment_period_data}', '{client_form_payment_amount_data}', "
                      f"'{client_form_start_date_data}', '{client_form_end_date_data}', 'N/A', '{client_form_status}')")
        conn.commit()
        mycur.execute(f"INSERT INTO adgeeks_passwords (id_passwords, type, username, password, access_level) VALUES "
                      f"('{password_id}', 'Client', '{client_form_user_name}', '{client_form_password}', 'client')")
        conn.commit()
        make_folder(client_form_user_name)
        print(range(int(client_form_payment_period_data)))
        for _ in range(int(client_form_payment_period_data)):
            mycur.execute("SELECT work_id FROM work_record ORDER BY work_id DESC LIMIT 1")
            last_creator_id = mycur.fetchone()
            if last_creator_id:
                last_creator_id = int(last_creator_id[0])
            try:
                work_id = last_creator_id + 1
            except:
                work_id = 1
            mycur.execute(
                f"INSERT INTO work_record (work_id, client_username, services, total_reels, total_posts,"
                f" total_stories) VALUES ('{work_id}', '{client_form_user_name}', '{client_form_service_data}', "
                f"'{client_form_reels_creative_data}', '{client_form_posts_creative_data}', "
                f"'{client_form_story_creative_data}')")
            conn.commit()
        return redirect("/admin_client_panel")
    return render_template("adgeeks_admin_client_creation_form.html")


# Creators section

@app.route('/admin_creator_panel')
def admin_creator_panel():
    mycur.execute("SELECT * FROM adgeeks_crm_system.creator_information WHERE creator_status != 'Delete'")
    creator_details = mycur.fetchall()
    conn.commit()
    print(creator_details)
    return render_template("adgeeks_admin_creator_panel.html", creator_details=creator_details)


@app.route('/admin_creator_details_block/<int:creator_id>', methods=['GET', 'POST'])
def admin_creator_details_block(creator_id):
    mycur.execute(f"SELECT * FROM creator_information WHERE creator_id = '{creator_id}'")
    creator_details = mycur.fetchall()
    conn.commit()
    if creator_details:
        creator_details = [creator_details]
        for creator in creator_details:
            if creator[0][11] == 'Block':
                mycur.execute(
                    f"UPDATE creator_information SET creator_status = 'Active' WHERE creator_id = '{creator_id}'")
                conn.commit()
            else:
                mycur.execute(
                    f"UPDATE creator_information SET creator_status = 'Block' WHERE creator_id = '{creator_id}'")
                conn.commit()
    return redirect(request.url)


@app.route('/admin_creator_details_delete/<int:creator_id>', methods=['GET', 'POST'])
def admin_creator_details_delete(creator_id):
    mycur.execute(f"SELECT * FROM creator_information WHERE creator_id = '{creator_id}'")
    creator_details = mycur.fetchall()
    conn.commit()
    if creator_details:
        creator_details = [creator_details]
        for creator in creator_details:
            if creator[0][11] == 'Delete':
                mycur.execute(
                    f"UPDATE creator_information SET creator_status = 'Active' WHERE creator_id = '{creator_id}'")
                conn.commit()
            else:
                mycur.execute(
                    f"UPDATE creator_information SET creator_status = 'Delete' WHERE creator_id = '{creator_id}'")
                conn.commit()
    return redirect(url_for('admin_creator_panel'))


@app.route('/admin_creator_work')
def admin_creator_work():
    return render_template("adgeeks_admin_creator_work.html")


@app.route('/admin_creator_details/<int:creator_id>')
def admin_creator_details(creator_id):
    mycur.execute(f"SELECT * FROM adgeeks_crm_system.creator_information WHERE creator_id = {creator_id}")
    creator_details = mycur.fetchone()
    conn.commit()
    if creator_details:
        creator_details = [creator_details]
        print(creator_details)
        return render_template("adgeeks_admin_creator_details.html", creator_details=creator_details)
    else:
        flash('creator not found!', 'error')
        return redirect(url_for('admin_creator_panel'))


@app.route('/admin_creator_details_update/<int:creator_id>')
def admin_creator_details_update(creator_id):
    mycur.execute(f"SELECT * FROM adgeeks_crm_system.creator_information WHERE creator_id = {creator_id}")
    creator_details = mycur.fetchone()
    conn.commit()
    if creator_details:
        creator_details = [creator_details]
        print(creator_details)
        return render_template("adgeeks_admin_creator_details_update.html", creator_details=creator_details)
    else:
        flash('creator not found!', 'error')
        return redirect(url_for('admin_dashboard'))


@app.route('/admin_creator_details_update_form/<int:creator_id>', methods=['GET', 'POST'])
def admin_creator_details_update_form(creator_id):
    if request.method == 'POST':
        time.sleep(3)
        mycur.execute(f"SELECT * FROM adgeeks_crm_system.creator_information WHERE creator_id = {creator_id}")
        creator_details = mycur.fetchone()
        creator_details = [creator_details]
        conn.commit()
        print(creator_details)
        for creator in creator_details:
            creator_form_full_name = request.form['full_name']
            if creator_form_full_name:
                creator_form_full_name_data = creator_form_full_name
            else:
                creator_form_full_name_data = creator[1]

            creator_form_user_name = request.form['user_name']
            if creator_form_user_name:
                creator_form_user_name_data = creator_form_user_name
            else:
                creator_form_user_name_data = creator[2]

            creator_form_password = request.form['password']
            if creator_form_password:
                creator_form_password_data = creator_form_password
            else:
                creator_form_password_data = creator[3]

            creator_form_email = request.form['email']
            if creator_form_email:
                creator_form_email_data = creator_form_email
            else:
                creator_form_email_data = creator[4]

            creator_form_mobileno = request.form['mobileno']
            if creator_form_mobileno:
                creator_form_mobileno_data = creator_form_mobileno
            else:
                creator_form_mobileno_data = creator[5]

            creator_form_address = request.form['address']
            if creator_form_address:
                creator_form_address_data = creator_form_address
            else:
                creator_form_address_data = creator[7]

            creator_form_city = request.form['city']
            if creator_form_city:
                creator_form_city_data = creator_form_city
            else:
                creator_form_city_data = creator[6]

            creator_form_creator_type = request.form['creator_type']
            if creator_form_creator_type:
                creator_form_creator_type_data = creator_form_creator_type
            else:
                creator_form_creator_type_data = creator[8]

            creator_form_access_level = request.form['access_level']
            if creator_form_access_level:
                delete_image(creator[9])
                creator_form_access_level_data = creator_form_access_level
            else:
                creator_form_access_level_data = creator[9]
            mycur.execute("""
                    UPDATE creator_information SET
                        full_name = %s,
                        username = %s,
                        password = %s,
                        email = %s,
                        mobile_number = %s,
                        city = %s,
                        address = %s,
                        creator_type = %s,
                        access_level = %s,
                        assigned_client = %s
                    WHERE creator_id = %s
                """, (
                creator_form_full_name_data, creator_form_user_name_data,
                creator_form_password_data, creator_form_email_data, creator_form_mobileno_data, creator_form_city_data,
                creator_form_address_data, creator_form_creator_type_data, creator_form_access_level_data, 'N/A',
                creator_id
            ))
            conn.commit()
            return redirect(url_for("admin_creator_details", creator_id=creator_id))
    return redirect("/admin_creator_details")


@app.route('/admin_creator_details_worksection')
def admin_creator_details_worksection():
    return render_template("adgeeks_admin_creator_details_worksection.html")


@app.route('/admin_creator_details_work_review_section')
def admin_creator_details_work_review_section():
    return render_template("adgeeks_admin_creator_details_work_review_section.html")


@app.route('/admin_creator_details_task_section')
def admin_creator_details_task_section():
    return render_template("adgeeks_admin_creator_details_task_section.html")


@app.route('/admin_creator_details_work_view_section')
def admin_creator_details_work_view_section():
    return render_template("adgeeks_admin_creator_details_work_view_section.html")


@app.route('/admin_creator_details_performancesection')
def admin_creator_details_performancesection():
    return render_template("adgeeks_admin_creator_details_performancesection.html")


@app.route('/admin_creator_details_creativesection')
def admin_creator_details_creativesection():
    return render_template("adgeeks_admin_creator_details_creativesection.html")


@app.route('/admin_creator_details_strategysection')
def admin_creator_details_strategysection():
    return render_template("adgeeks_admin_creator_details_strategysection.html")


@app.route('/admin_creator_creation_form', methods=['GET', 'POST'])
def admin_creator_creation_form():
    if request.method == 'POST':
        mycur.execute("SELECT creator_id FROM creator_information ORDER BY creator_id DESC LIMIT 1")
        last_creator_id = mycur.fetchone()
        if last_creator_id:
            last_creator_id = int(last_creator_id[0])
        try:
            creator_id = last_creator_id + 1
        except:
            creator_id = 1
        mycur.execute("SELECT id_passwords FROM adgeeks_passwords ORDER BY id_passwords DESC LIMIT 1")
        last_password_id = mycur.fetchone()

        if last_password_id:
            last_password_id = int(last_password_id[0])
        try:
            password_id = last_password_id + 1
        except:
            password_id = 1
        creator_form_full_name = request.form['full_name']
        creator_form_user_name = request.form['user_name']
        creator_form_password = generate_password()
        creator_form_email = request.form['email']
        creator_form_mobileno = request.form['mobileno']
        creator_form_address = request.form['address']
        creator_form_city = request.form['city']
        creator_form_creator_type = request.form.getlist('creator_type')
        if creator_form_creator_type:
            creator_form_creator_type_str = ', '.join(creator_form_creator_type)
            creator_form_creator_type_data = creator_form_creator_type_str
        else:
            creator_form_creator_type_data = "N/A"
        creator_form_access_level = request.form['access_level']
        if creator_form_access_level:
            creator_form_access_level_data = creator_form_access_level
        else:
            creator_form_access_level_data = "N/A"
        creator_form_status = request.form['creator_status']
        mycur.execute("INSERT INTO creator_information (creator_id, full_name, username, password, email, mobile_number"
                      ", city, address, creator_type, access_level, assigned_client, creator_status) VALUES "
                      f"('{creator_id}', '{creator_form_full_name}', "
                      f"'{creator_form_user_name}', '{creator_form_password}', '{creator_form_email}', "
                      f"'{creator_form_mobileno}', '{creator_form_city}', '{creator_form_address}', "
                      f"'{creator_form_creator_type_data}', '{creator_form_access_level_data}', 'N/A',"
                      f" '{creator_form_status}')")
        conn.commit()
        mycur.execute(f"INSERT INTO adgeeks_passwords (id_passwords, type, username, password, access_level) VALUES "
                      f"('{password_id}', 'Creator', '{creator_form_user_name}', '{creator_form_password}',"
                      f" '{creator_form_access_level_data}')")
        conn.commit()
        return redirect("/admin_creator_panel")
    return render_template("adgeeks_admin_creator_creation_form.html")


@app.route('/admin_creator_assign/<int:creator_id>')
def admin_creator_assign(creator_id):
    mycur.execute("SELECT * FROM adgeeks_crm_system.client_information")
    client_details = mycur.fetchall()
    conn.commit()
    return render_template("adgeeks_admin_creator_assign.html", client_details=client_details, creator_id=creator_id)


@app.route('/admin_creator_assign_button/<int:creator_id>', methods=['POST'])
def admin_creator_assign_button(creator_id):
    data = request.get_json()
    if data:
        action = data.get('action')
        client_id = data.get('client_id')

        print(creator_id)
        mycur.execute(f"SELECT * FROM creator_information WHERE creator_id={creator_id}")
        creator_details = mycur.fetchone()
        conn.commit()
        print(creator_details)

        if action == 'unassign':
            print("assign")
            print("Client ID:", client_id)

            mycur.execute(f"SELECT * FROM adgeeks_crm_system.client_information WHERE client_id = {client_id}")
            client_details = mycur.fetchone()
            conn.commit()

            mycur.execute(f"UPDATE client_information SET assigned_creator = 'yes' WHERE client_id = {client_id}")
            conn.commit()

            mycur.execute(f"SELECT * FROM adgeeks_crm_system.creator_information WHERE creator_id = {creator_id}")
            creator_details = mycur.fetchone()
            conn.commit()

            mycur.execute(f"UPDATE creator_information SET assigned_client = 'yes' WHERE creator_id = {creator_id}")
            conn.commit()

            mycur.execute(f"UPDATE work_record SET creator_username = '{creator_details[2]}' WHERE client_username = "
                          f"'{client_details[3]}'")
            conn.commit()

            if client_details and creator_details:
                mycur.execute("""
                    INSERT INTO assign_admin (id_assign, creator_username, client_username, services)
                    VALUES (%s, %s, %s, %s)
                """, (
                    client_details[0],  # assuming this is id_assign
                    creator_details[2],  # assuming this is creator_username
                    client_details[3],  # assuming this is client_username
                    client_details[10]  # assuming this is services
                ))
                conn.commit()

            return jsonify(success=True, message=action)

        elif action == 'assign':
            print("unassign")
            print("Client ID:", client_id)

            mycur.execute(f"SELECT * FROM adgeeks_crm_system.client_information WHERE client_id = {client_id}")
            client_details = mycur.fetchone()
            conn.commit()
            mycur.execute(f"UPDATE client_information SET assigned_creator = 'no' WHERE client_id = {client_id}")
            conn.commit()
            mycur.execute(f"""
                DELETE FROM assign_admin 
                WHERE creator_username = %s AND client_username = %s
            """, (creator_details[2], client_details[3]))
            conn.commit()

            return jsonify(success=True, message=action)

        else:
            return jsonify(success=False, message="Invalid action")

    return jsonify(success=False, message="No action provided")


@app.route('/admin_upload_files_section/<folder_name>')
def admin_upload_files_section(folder_name):
    mycur.execute(f"select creator_username, client_username from work_record where title = '{folder_name}'")
    username_list = mycur.fetchall()
    conn.commit()
    creator_username = username_list[0][0]
    client_username = username_list[0][1]
    mycur.execute(f"UPDATE work_record set status_admin = 'no' where client_username = '{client_username}'")
    conn.commit()
    mycur.execute(
        f"SELECT * FROM work_record WHERE creator_username = '{creator_username}' and client_username = '{client_username}'")
    creator_details = [mycur.fetchone()]
    conn.commit()
    print(creator_details)
    session['folder_name'] = folder_name
    files_fetched_check = fetch_files(folder_name)
    files_fetched = [('None')]
    if files_fetched_check:
        files_fetched = files_fetched_check
    services = creator_details[0][9].split(', ')
    number_reels = creator_details[0][19] - creator_details[0][13]
    number_posts = creator_details[0][20] - creator_details[0][15]
    number_story = creator_details[0][21] - creator_details[0][17]
    mycur.execute(f"select * from work_details where creator_username = '{creator_username}' and client_username "
                  f"= '{client_username}' and status_detail = 'active'")
    raw_data = mycur.fetchall()
    conn.commit()
    merged_data = defaultdict(list)
    for item in raw_data:
        merged_data[item[1]].append(item)

    # Process to combine data entries
    final_data = []
    for file_name, items in merged_data.items():
        combined = list(items[0])  # Start with the first item's data
        for item in items[1:]:  # Start from the second item
            for i in range(len(item)):
                if item[i] is not None:
                    combined[i] = item[i]  # Replace with non-None values
        final_data.append(tuple(combined))
    mycur.execute(f'select detail_id from work_details where admin_approve = "yes" and '
                  f'creator_username = "{creator_username}" and client_username = "{client_username}"')
    approved_work = mycur.fetchall()
    conn.commit()
    total_work = creator_details[0][19] + creator_details[0][20] + creator_details[0][21] - len(approved_work)
    print(creator_details[0][19], creator_details[0][20], creator_details[0][21], len(approved_work))
    files_with_details = []
    for file in files_fetched:
        file_info = {
            'name': file,
            'details': None,
            'reviews': None,
            'approve': None,
        }
        for work in final_data:
            if work[1] == file:
                if work[10] == 'yes':
                    file_info['details'] = work[4]
                    file_info['reviews'] = work[5]
                    file_info['approve'] = 'yes'
                    break
                else:
                    file_info['details'] = work[4]
                    file_info['reviews'] = work[5]
                    break
        files_with_details.append(file_info)
    return render_template("adgeeks_admin_upload_files_section.html", creator_details=creator_details,
                           files=files_with_details, folder_name=folder_name, services=services,
                           number_reels=number_reels, total_work=total_work,
                           number_posts=number_posts, number_story=number_story, work_details=final_data)


@app.route('/upload_review/<file_name>', methods=['POST'])
def upload_review(file_name):
    information_upload = request.form['information']
    mycur.execute("SELECT detail_id FROM work_details ORDER BY detail_id DESC LIMIT 1")
    last_creator_id = mycur.fetchone()
    if last_creator_id:
        last_creator_id = int(last_creator_id[0])
    try:
        detail_id = last_creator_id + 1
    except:
        detail_id = 1
    client_username = session.get('client_username')
    creator_username = session.get('user_name')
    mycur.execute(f"INSERT INTO work_details (detail_id, file_name, client_username, "
                  f"creator_username, review_admin, status_detail) VALUES ('{detail_id}', '{file_name}',"
                  f" '{client_username}', '{creator_username}', '{information_upload}', 'active')")
    conn.commit()
    mycur.execute(f"UPDATE work_record set status_admin = 'yes' where client_username = '{client_username}'")
    conn.commit()
    folder_name = session.get('folder_name')
    return redirect(url_for('admin_upload_files_section', folder_name=folder_name))



@app.route('/admin_approve_task/<file_name>', methods=['POST', 'GET'])
def admin_approve_task(file_name):
    mycur.execute(f"update work_details set admin_approve = 'yes' where file_name = '{file_name}' and status_detail = "
                  f"'active'")
    conn.commit()
    folder_name = session.get('folder_name')
    return redirect(url_for('admin_upload_files_section', folder_name=folder_name))


@app.route('/roll_out/<folder_name>')
def roll_out(folder_name):
    print("run")
    upload_directory_to_drive(f'static/work/{folder_name}', PARENT_FOLDER_ID, folder_name)
    mycur.execute(f"select creator_username, client_username from work_record where title = '{folder_name}'")
    username_list = mycur.fetchall()
    conn.commit()
    creator_username = username_list[0][0]
    client_username = username_list[0][1]
    mycur.execute(f"update work_details set admin_roll_out = 'yes' where client_username = '{client_username}' and "
                  f"creator_username = '{creator_username}'")
    conn.commit()
    mycur.execute(f"update work_record set admin_roll_out = 'yes' where client_username = '{client_username}' and "
                  f"creator_username = '{creator_username}' and work_status != 'Completed' ORDER BY work_id ASC LIMIT 1")
    conn.commit()
    return redirect(url_for('admin_target_section_individual', creator_username=creator_username))


#
#
#
# end admin section
#
#
#
#
#
#
# start creators section
#
#
#

@app.route('/creator_dashboard/<user_name>')
def creator_dashboard(user_name):
    session['user_name'] = user_name
    mycur.execute(f"SELECT * FROM adgeeks_crm_system.creator_information WHERE username = '{user_name}'")
    creator_details = mycur.fetchone()
    conn.commit()
    if creator_details:
        creator_details = [creator_details]
        mycur.execute("SELECT assigned_client from creator_information where assigned_client = 'yes'")
        client_assigned = mycur.fetchall()
        conn.commit()
        if client_assigned:
            mycur.execute(f"SELECT client_username, services from assign_admin where "
                          f"creator_username = '{creator_details[0][2]}'")
            assign_info = mycur.fetchall()
            conn.commit()
            client_info_list = []
            if assign_info:
                for assign in assign_info:
                    mycur.execute(f"SELECT * FROM client_information where username = '{assign[0]}'")
                    client_info = mycur.fetchall()
                    conn.commit()
                    client_info_list.append(client_info)
                    print(client_info_list)
            return render_template("adgeeks_creator_dashboard.html", creator_details=creator_details,
                                   client_info_list=client_info_list)
    else:
        flash('creator not found!', 'error')
        return redirect(url_for('log_in'))


@app.route('/creator_details_task_section/<int:creator_id>')
def creator_details_task_section(creator_id):
    mycur.execute(f"SELECT * FROM adgeeks_crm_system.creator_information WHERE creator_id = '{creator_id}'")
    creator_details = mycur.fetchone()
    conn.commit()
    if creator_details:
        creator_details = [creator_details]
        if creator_details[0][10]:
            mycur.execute(f"SELECT client_username, services from assign_admin where "
                          f"creator_username = '{creator_details[0][2]}'")
            assign_info = mycur.fetchall()
            conn.commit()
            client_info_list = []
            if assign_info:
                for assign in assign_info:
                    mycur.execute(
                        f"select work_status from work_record where creator_username = '{creator_details[0][2]}' and"
                        f" client_username = '{assign[0]}'")
                    status_work = mycur.fetchall()
                    conn.commit()
                    print(status_work)
                    mycur.execute(
                        f"update client_information set work_status = '{status_work[0][0]}' where username = '{assign[0]}'")
                    conn.commit()
                    mycur.execute(f"SELECT * FROM client_information where username = '{assign[0]}'")
                    client_info = mycur.fetchall()
                    conn.commit()
                    client_info_list.append(client_info)
            print(client_info_list)
            return render_template("adgeeks_creator_details_task_section.html",
                                   creator_details=creator_details, creator_id=creator_id,
                                   todays_date=todays_date, client_info_list=client_info_list,
                                   )


@app.route('/creator_task_timeline/<file_name>')
def creator_task_timeline(file_name):
    try:
        # mycur.execute(f'select content_link from work_details where file_name = "{file_name}"')
        try:
            mycur.execute(f'select * from work_details where file_name = "{file_name}"'
                          f'and content_link != "no link"')
            work_details = mycur.fetchall()
            conn.commit()
            old_file_name = work_details[0][9]
            mycur.execute(
                f'select * from work_details where file_name = "{old_file_name}" and status_detail = "passive"')
            work_details_old = mycur.fetchall()
            conn.commit()
            mycur.execute(f'select * from work_details where file_name = "{file_name}" and status_detail = "passive"')
            work_details = mycur.fetchall()
            conn.commit()
            if work_details:
                combined_details = work_details_old + work_details
                print(combined_details)
                mycur.execute(
                    f"SELECT * FROM adgeeks_crm_system.creator_information WHERE username = '{work_details[0][3]}'")
                creator_details = mycur.fetchone()
                conn.commit()
                return render_template("adgeeks_creator_task_timeline.html", creator_details=creator_details,
                                       work_details=combined_details)
            else:
                mycur.execute(
                    f"SELECT * FROM adgeeks_crm_system.creator_information WHERE username = '{work_details[0][3]}'")
                creator_details = mycur.fetchone()
                conn.commit()
                return render_template("adgeeks_creator_task_timeline.html", creator_details=creator_details,
                                       work_details=work_details_old)
        except:
            mycur.execute(f'select * from work_details where file_name = "{file_name}" and status_detail = "passive"')
            work_details = mycur.fetchall()
            conn.commit()
            mycur.execute(
                f"SELECT * FROM adgeeks_crm_system.creator_information WHERE username = '{work_details[0][3]}'")
            creator_details = mycur.fetchone()
            conn.commit()
            print(work_details)
            return render_template("adgeeks_creator_task_timeline.html", creator_details=creator_details,
                                   work_details=work_details)
    except:
        folder_name = session.get('folder_name')
        return render_template('error-500.html', folder_name=folder_name)


@app.route('/task_schedule/<int:client_id>')
def task_schedule(client_id):
    creator_username = session.get('user_name')
    mycur.execute(f"SELECT * from creator_information where username = '{creator_username}'")
    creator_details = mycur.fetchall()
    conn.commit()
    mycur.execute(f"SELECT * FROM client_information where client_id = '{client_id}'")
    client_info = mycur.fetchall()
    conn.commit()
    mycur.execute(f"SELECT * FROM work_record where client_username = '{client_info[0][3]}' and work_status != "
                  f"'Completed'")
    work_record = mycur.fetchone()
    conn.commit()
    client_username = client_info[0][3]
    if work_record[6] == 'approved':
        print("ashbdinso")
        work_record = [work_record]
        start_date = client_info[0][25]
        due_date = start_date + timedelta(days=7)
        formatted_due_date = due_date.strftime("%d-%m-%y")
        services = client_info[0][10].split(', ')
        service_target_creatives = None
        service_target_performance_marketing = None
        service_target_strategy = None
        directory_path, folder_name = select_folder(client_info[0][3])
        session['folder_name'] = folder_name
        session['client_username'] = client_info[0][3]
        for service_check in services:
            if service_check == 'Creatives':
                service_target_creatives = (f"{client_info[0][14]} reels, {client_info[0][16]} posts and "
                                            f"{client_info[0][18]} stories in a month")
            elif service_check == 'Performance marketing':
                service_target_performance_marketing = (f"{client_info[0][3]} has a budget of "
                                                        f"{client_info[0][11]} for {client_info[0][12]}"
                                                        f" months")
            else:
                service_target_strategy = f"we have to make a {client_info[0][20]} for {client_info[0][3]}"
        return render_template("adgeeks_task_schedule.html", creator_details=creator_details,
                               client_info=client_info, work_record=work_record,
                               service_target_creatives=service_target_creatives, folder_name=folder_name,
                               service_target_performance_marketing=service_target_performance_marketing,
                               service_target_strategy=service_target_strategy, formatted_due_date=formatted_due_date)
    elif work_record[4] == 'yes':
        return redirect(url_for('create_calendar', client_username=client_info[0][3]))
    else:
        return render_template('adgeeks_creator_schedule_making.html', client_username=client_username)



@app.route('/task_section', methods=['GET', 'POST'])
def task_section():
    creator_username = session.get('user_name')
    mycur.execute(f"SELECT * FROM work_record where creator_username = '{creator_username}'")
    work_records = mycur.fetchall()
    conn.commit()
    print(work_records)
    return render_template("adgeeks_task_section.html", work_records=work_records)


@app.route('/target_section_initial_form', methods=['GET', 'POST'])
def target_section_initial_form():
    if request.method == 'POST':
        mycur.execute("SELECT work_id FROM work_record ORDER BY work_id DESC LIMIT 1")
        last_creator_id = mycur.fetchone()
        if last_creator_id:
            last_creator_id = int(last_creator_id[0])
        try:
            work_id = last_creator_id + 1
        except:
            work_id = 1
        creator_username = session.get('user_name')
        target_section_initial_form_title = request.form['title']
        target_section_initial_form_additionalinfo = request.form['additionalinfo']
        client_username = session.get('client_username')
        mycur.execute(f"select client_id, services, reels_creative, posts_creative, story_creative from "
                      f"client_information, month, start_date where username = '{client_username}'")
        client_info = mycur.fetchall()
        conn.commit()
        print(client_info)
        mycur.execute(
            "INSERT INTO work_record (work_id, title, description, creator_username, client_username, "
            "services, total_reels, total_posts, total_stories) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (work_id, target_section_initial_form_title, target_section_initial_form_additionalinfo, creator_username,
             client_username, client_info[0][1], client_info[0][2], client_info[0][3], client_info[0][4]))

        conn.commit()
        return redirect(url_for("task_schedule", client_id=client_info[0][0]))


@app.route('/task_folders_view')
def task_folders_view():
    return render_template('task_folders_view.html')


@app.route('/task_folders')
def task_folders():
    creator_username = session.get('user_name')
    mycur.execute(f"SELECT * FROM work_record WHERE creator_username = '{creator_username}'")
    creator_details = mycur.fetchall()
    conn.commit()
    return render_template("adgeeks_task_folders.html", creator_details=creator_details)


@app.route('/upload_files_section/<folder_name>')
def upload_files_section(folder_name):
    client_username = session.get('client_username')
    creator_username = session.get('user_name')
    mycur.execute(
        f"SELECT * FROM work_record WHERE creator_username = '{creator_username}' and "
        f"client_username = '{client_username}' and work_status != 'Completed'")
    creator_details = [mycur.fetchone()]
    conn.commit()
    if creator_details[0][26] == 'yes':
        return render_template('folder_complete.html', folder_name=folder_name)
    else:
        session['folder_name'] = folder_name
        files_fetched_check = fetch_files(folder_name)
        files_fetched = [('None')]
        if files_fetched_check:
            files_fetched = files_fetched_check
        services = creator_details[0][9].split(', ')
        number_reels = creator_details[0][19] - creator_details[0][13]
        number_posts = creator_details[0][20] - creator_details[0][15]
        number_story = creator_details[0][21] - creator_details[0][17]
        mycur.execute(f"select * from work_details where creator_username = '{creator_username}' and client_username "
                      f"= '{client_username}' and status_detail = 'active'")
        raw_data = mycur.fetchall()
        conn.commit()
        print(raw_data)
        merged_data = defaultdict(list)
        for item in raw_data:
            merged_data[item[1]].append(item)
        final_data = []
        for file_name, items in merged_data.items():
            combined = list(items[0])  # Start with the first item's data
            for item in items[1:]:  # Start from the second item
                for i in range(len(item)):
                    if item[i] is not None:
                        combined[i] = item[i]  # Replace with non-None values
            final_data.append(tuple(combined))
        # print(final_data)

        mycur.execute(f"select detail_id from work_details where admin_approve = 'yes' and "
                      f"client_username = '{client_username}' and creator_username = '{creator_username}'")
        approved_work = mycur.fetchall()
        conn.commit()
        total_work = creator_details[0][19] + creator_details[0][20] + creator_details[0][21] - len(approved_work)
        mycur.execute(f"select detail_id from work_details where content_uploaded = 'yes' and "
                      f"client_username = '{client_username}' and creator_username = '{creator_username}'")
        uploaded_work = mycur.fetchall()
        conn.commit()
        total_uploaded = creator_details[0][19] + creator_details[0][20] + creator_details[0][21] - len(uploaded_work)

        mycur.execute("select content_link from work_details where content_link != 'no link'")
        excluded_files = mycur.fetchall()
        conn.commit()
        excluded_filenames = {file[0] for file in excluded_files}
        files_with_details = []
        for file in files_fetched:
            if file not in excluded_filenames:  # Skip files that are in the excluded list
                file_info = {
                    'name': file,
                    'details': None,
                    'reviews': None,
                    'approve': None,
                    'client_approve': None,
                    'client_review': None,
                    'uploaded_work': None
                }
                for work in final_data:
                    if work[1] == file:
                        if work[14] == 'yes':
                            print("1")
                            file_info['uploaded_work'] = 'yes'
                            break
                        elif work[12] == 'yes':
                            print("3")
                            file_info['details'] = work[4]
                            file_info['reviews'] = work[5]
                            file_info['client_approve'] = 'yes'
                            file_info['client_review'] = work[6]
                            break
                        elif work[10] == 'yes':
                            print("2")
                            file_info['details'] = work[4]
                            file_info['reviews'] = work[5]
                            file_info['approve'] = 'yes'
                            file_info['client_review'] = work[6]
                            break
                        else:
                            print("4")
                            file_info['details'] = work[4]
                            file_info['reviews'] = work[5]
                            file_info['client_review'] = work[6]
                            break
                files_with_details.append(file_info)
                # print(files_with_details)
        return render_template("adgeeks_upload_files_section.html", creator_details=creator_details,
                               files=files_with_details, folder_name=folder_name, services=services,
                               number_reels=number_reels, total_work=total_work, total_uploaded=total_uploaded,
                               number_posts=number_posts, number_story=number_story, work_details=final_data)


@app.route('/upload_details/<file_name>', methods=['POST'])
def upload_details(file_name):
    information_upload = request.form['information']
    mycur.execute("SELECT detail_id FROM work_details ORDER BY detail_id DESC LIMIT 1")
    last_creator_id = mycur.fetchone()
    if last_creator_id:
        last_creator_id = int(last_creator_id[0])
    try:
        detail_id = last_creator_id + 1
    except:
        detail_id = 1
    client_username = session.get('client_username')
    creator_username = session.get('user_name')
    print(current_time_in_india)
    mycur.execute(f"INSERT INTO work_details (detail_id, file_name, additional_details, client_username, "
                  f"creator_username, status_detail) VALUES ('{detail_id}', '{file_name}', "
                  f"'{information_upload}', '{client_username}', '{creator_username}', 'active')")
    conn.commit()
    mycur.execute(f"UPDATE work_record set status_admin = 'yes' where client_username = '{client_username}'")
    conn.commit()
    mycur.execute(f"""
            SELECT MAX(detail_id)
            FROM work_details
            WHERE creator_username = '{creator_username}' AND client_username = '{client_username}'
        """)
    last_id = mycur.fetchone()[0]
    conn.commit()
    mycur.execute(f'Update work_details set status_detail = "passive" where creator_username = "{creator_username}" '
                  f'and client_username = "{client_username}" and detail_id < "{last_id}" and file_name = "{file_name}"')
    conn.commit()
    folder_name = session.get('folder_name')
    return redirect(url_for('upload_files_section', folder_name=folder_name))


@app.route('/upload_task', methods=['POST'])
def upload_task():
    if 'file' not in request.files:
        return jsonify(success=False, message="No file part"), 400
    time.sleep(10)
    file = request.files['file']
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        client_username = session.get('client_username')
        directory_path, folder_name = select_folder(client_username)
        file_path = os.path.join(directory_path, filename)
        file.save(file_path)  # Save the file to the specified directory
        task_listing(folder_name, client_username)
        mycur.execute("SELECT detail_id FROM work_details ORDER BY detail_id DESC LIMIT 1")
        last_creator_id = mycur.fetchone()
        if last_creator_id:
            last_creator_id = int(last_creator_id[0])
        try:
            detail_id = last_creator_id + 1
        except:
            detail_id = 1
        client_username = session.get('client_username')
        creator_username = session.get('user_name')
        mycur.execute(f"INSERT INTO work_details (detail_id, file_name, client_username, "
                      f"creator_username, status_detail) VALUES ('{detail_id}', '{filename}', '{client_username}'"
                      f",'{creator_username}', 'active')")
        conn.commit()
        mycur.execute(f"update work_record set work_status = 'In progress' where client_username = '{client_username}'"
                      f" and creator_username = '{creator_username}' and work_status != 'Completed' ORDER BY work_id ASC LIMIT 1")
        return jsonify(success=True, file_path=file_path)

    return jsonify(success=False, message="File not allowed"), 400


@app.route('/Submit_task/<client_username>', methods=['POST'])
def submit_task(client_username):
    # upload_directory_to_drive(f'{directory_path}', PARENT_FOLDER_ID)
    mycur.execute(
        f"select reel_count, post_count, story_count from work_record where client_username = '{client_username}' and"
        f" work_status != 'Completed' ORDER BY work_id ASC LIMIT 1")
    count_task = mycur.fetchall()
    client_form_reels_creative = request.form['reels_creative']
    if client_form_reels_creative:
        client_form_reels_creative_data = int(client_form_reels_creative) + int(count_task[0][0])
    else:
        client_form_reels_creative_data = "N/A"
    client_form_posts_creative = request.form['posts_creative']
    if client_form_posts_creative:
        client_form_posts_creative_data = int(client_form_posts_creative) + int(count_task[0][1])
    else:
        client_form_posts_creative_data = "N/A"
    client_form_story_creative = request.form['story_creative']
    if client_form_story_creative:
        client_form_story_creative_data = int(client_form_story_creative) + int(count_task[0][2])
    else:
        client_form_story_creative_data = 'N/A'
    mycur.execute(f'UPDATE work_record SET reel_count = "{client_form_reels_creative_data}", post_count = '
                  f'"{client_form_posts_creative_data}", story_count = "{client_form_story_creative_data}"'
                  f' where client_username = "{client_username}" and work_status != "Completed" ORDER BY work_id ASC LIMIT 1')
    conn.commit()
    folder_name = session.get('folder_name')
    return redirect(url_for('upload_files_section', folder_name=folder_name))


@app.route('/submit_task_review', methods=['POST'])
def submit_task_review_upload():
    # upload_directory_to_drive(f'{directory_path}', PARENT_FOLDER_ID)
    file_name = request.form['file_name']
    creator_username = session.get('user_name')
    client_username = session.get('client_username')
    mycur.execute("select file_name, detail_id from work_details where detail_id = ( select max(detail_id) from work_details)")
    change_content = mycur.fetchall()[0]
    conn.commit()
    print(change_content)
    mycur.execute(f"INSERT INTO work_details (detail_id, file_name, client_username, "
                  f"creator_username, status_detail, content_link) VALUES ('{int(change_content[1]) + 1}', '{change_content[0]}', "
                  f"'{client_username}', '{creator_username}', 'active', '{file_name}')")
    conn.commit()
    mycur.execute(f"UPDATE work_details set status_detail = 'passive' where file_name = '{file_name}'")
    conn.commit()
    folder_name = session.get('folder_name')
    return redirect(url_for('upload_files_section', folder_name=folder_name))


@app.route('/work_upload_details/<client_username>')
def work_upload_details(client_username):
    creator_username = session.get('user_name')
    session['client_username'] = client_username
    mycur.execute(f"SELECT * from creator_information where username = '{creator_username}'")
    creator_details = mycur.fetchall()
    conn.commit()
    mycur.execute(f"select * from client_information  where username = '{client_username}'")
    client_details = mycur.fetchall()
    conn.commit()
    print(client_details)
    services = client_details[0][10].split(', ')
    print(services)
    return render_template("adgeeks_work_upload_details.html", creator_details=creator_details,
                           client_details=client_details, services=services)


@app.route('/delete_file/<folder_name>/<file_name>')
def delete_file(folder_name, file_name):
    try:
        path = os.path.join('static', 'work', folder_name, file_name)
        os.remove(path)
        flash('File successfully deleted!', 'success')
    except Exception as e:
        flash(str(e), 'error')
    return redirect(url_for('upload_files_section', folder_name=folder_name))


@app.route('/rename_file/<folder_name>/<file_name>', methods=['POST'])
def rename_file(folder_name, file_name):
    new_file_name = secure_filename(request.form['new_file_name'])  # Ensure the filename is secure
    old_path = os.path.join('static', 'work', folder_name, file_name)
    new_path = os.path.join('static', 'work', folder_name, new_file_name)

    try:
        os.rename(old_path, new_path)  # Attempt to rename the file
        mycur.execute(f"update work_details set file_name = %s where file_name = %s", (new_file_name, file_name))
        conn.commit()
        response = {'status': 'success', 'message': 'File renamed successfully!'}
    except Exception as e:
        response = {'status': 'error', 'message': str(e)}

    return jsonify(response)


@app.route('/uploaded_creator', methods=['POST'])
def uploaded_creator():
    file_name = request.json.get('file_name')
    print(file_name)
    mycur.execute(f"update work_details set content_uploaded = 'yes' where file_name = '{file_name}' and status_detail = "
                  f"'active'")
    conn.commit()
    return "Task approved", 200


@app.route('/work_over/<folder_name>', methods=['POST', 'GET'])
def work_over(folder_name):
    final_folder_name = folder_name.replace("Raw", "Final")
    upload_directory_to_drive(f'static/work/{final_folder_name}', PARENT_FOLDER_ID, final_folder_name)
    mycur.execute(f"UPDATE work_record SET uploaded_all = 'yes', work_status = 'Completed' where title = '{folder_name}'")
    conn.commit()
    mycur.execute(f"select creator_username from work_record where title = '{folder_name}'")
    creator_name = mycur.fetchall()
    conn.commit()
    mycur.execute(f"select creator_id from creator_information where username = '{creator_name[0][0]}'")
    creator_id = mycur.fetchall()
    conn.commit()
    return redirect(url_for('creator_details_task_section', creator_id=creator_id[0][0]))


@app.route('/new_task/<creator_id>', methods=['POST', 'GET'])
def new_task(creator_id):
    return render_template('adgeeks_new_task.html', creator_id=creator_id)


#
#
#
# trying calendar
#
#
#
@app.route('/create_calendar/<client_username>')
def create_calendar(client_username):
    creator_username = session.get('user_name')
    mycur.execute(f"SELECT * from creator_information where username = '{creator_username}'")
    creator_details = mycur.fetchall()
    conn.commit()
    mycur.execute(f"SELECT total_reels, total_posts, total_stories, client_username, calendar_status, calendar_review, "
                  f"calendar_update FROM work_record where creator_username = '{creator_username}' and client_username "
                  f"= '{client_username}' ORDER BY work_id ASC LIMIT 1")
    work_record = mycur.fetchone()
    conn.commit()
    service_target_creatives = (f"{work_record[0]} reel(s), {work_record[1]} post(s) and "
                                f"{work_record[2]} story in a month")
    client_username = work_record[3]
    session['client_username'] = client_username
    mycur.execute(f"select id from calendar_data where client_username = '{client_username}' and creator_username = '{creator_username}'")
    calendar_entry = mycur.fetchall()
    conn.commit()
    send_client = False
    if calendar_entry:
        send_client = True
    calendar_status = work_record[4]
    calendar_review_client = work_record[5]
    calendar_update_client = work_record[6]
    if calendar_status == 'yes':
        print("gsvuabhdijno")
        if not calendar_review_client or calendar_update_client == 'yes':
            creator_username = creator_details[0][1]
            return render_template('adgeeks_creator_calendar_approval.html', creator_username=creator_username)
        else:
            return render_template("adgeeks_creator_calendar.html", creator_details=creator_details,
                                   service_target_creatives=service_target_creatives, send_client=send_client,
                                   calendar_review=calendar_review_client)
    else:
        print("dtfyguhikpodfshbcu")
        return render_template("adgeeks_creator_calendar.html", creator_details=creator_details,
                               service_target_creatives=service_target_creatives, send_client=send_client,
                               calendar_review=calendar_review_client)

@app.route('/send_client_btn')
def send_client_btn():
    creator_username = session.get('user_name')
    client_username = session.get('client_username')
    mycur.execute(f"select calendar_review from work_record where client_username = '{client_username}' and "
                  f"creator_username = '{creator_username}' ORDER BY work_id ASC LIMIT 1")
    calendar_review = mycur.fetchone()[0]
    conn.commit()
    if calendar_review:
        mycur.execute(f"update work_record set calendar_update = 'yes' where client_username = '{client_username}' and "
                      f"creator_username = '{creator_username}' ORDER BY work_id ASC LIMIT 1")
        conn.commit()
        return redirect(url_for('create_calendar', client_username=client_username))
    else:
        mycur.execute(f"update work_record set calendar_status = 'yes' where client_username = '{client_username}' and "
                      f"creator_username = '{creator_username}' ORDER BY work_id ASC LIMIT 1")
        conn.commit()
        return redirect(url_for('create_calendar', client_username=client_username))

@app.route('/fetch_events', methods=['GET'])
def get_events():
    client_username = session.get('client_username')
    mycur.execute(f'select creator_username from assign_admin where client_username = "{client_username}"')
    creator_username = mycur.fetchone()[0]
    conn.commit()
    mycur.execute(f"SELECT * FROM calendar_data where client_username = '{client_username}' and creator_username = "
                  f"'{creator_username}'")
    events = mycur.fetchall()
    conn.commit()
    result = []
    for event in events:
        result.append({
            'id': event[0],
            'title': event[1],
            'description': event[2],
            'start': event[3].isoformat(),
        })
    return jsonify(result)


@app.route('/creation_events', methods=['POST'])
def add_event():
    data = request.get_json()
    client_username = session.get('client_username')
    mycur.execute(f'select creator_username from assign_admin where client_username = "{client_username}"')
    creator_username = mycur.fetchone()[0]
    conn.commit()
    mycur.execute("INSERT INTO calendar_data (title, description, start, client_username"
                  ", creator_username) VALUES (%s, %s, %s, %s, %s)",(data['title'], data['description'],
                  data['start'], client_username, creator_username))
    conn.commit()
    return jsonify({'message': 'Event added successfully'}), 201


@app.route('/edit_events', methods=['PUT'])
def update_event():
    data = request.get_json()
    mycur.execute("""
        UPDATE calendar_data
        SET title=%s, description=%s, start=%s
        WHERE id=%s
    """, (data['title'], data['description'], data['start'], data['id']))
    conn.commit()
    return jsonify({'message': 'Event updated successfully'})



@app.route('/delete_events', methods=['PUT'])
def delete_event():
    data = request.get_json()
    mycur.execute("DELETE FROM calendar_data WHERE id=%s", (data['id'],))
    conn.commit()
    return jsonify({'message': 'Event deleted successfully'})

#
#
#
# trying calendar
#
#
#
#

#
#
#
#
#
# client start
#
#
#
#
#


@app.route('/client_dashboard/<user_name>')
def client_dashboard(user_name):
    session['client_username'] = user_name
    mycur.execute(f"SELECT * FROM adgeeks_crm_system.client_information WHERE username = '{user_name}'")
    client_details = mycur.fetchone()
    conn.commit()
    if client_details:
        client_details = [client_details]
        mycur.execute("SELECT assigned_creator from client_information where assigned_creator = 'yes'")
        creator_assigned = mycur.fetchall()
        conn.commit()
        if creator_assigned:
            mycur.execute(f"SELECT creator_username, services from assign_admin where "
                          f"client_username = '{client_details[0][2]}'")
            assign_info = mycur.fetchall()
            conn.commit()
            creator_info_list = []
            if assign_info:
                for assign in assign_info:
                    mycur.execute(f"SELECT * FROM creator_information where username = '{assign[0]}'")
                    creator_info = mycur.fetchall()
                    conn.commit()
                    creator_info_list.append(creator_info)
                    print(creator_info_list)
            return render_template("adgeeks_client_dashboard.html", creator_details=client_details,
                                   client_info_list=creator_info_list)
    else:
        flash('creator not found!', 'error')
        return redirect(url_for('log_in'))


@app.route('/client_upload_files_section')
def client_upload_files_section():
    client_username = session.get('client_username')
    mycur.execute(f'select creator_username from assign_admin where client_username = "{client_username}"')
    creator_username = mycur.fetchone()[0]
    conn.commit()
    mycur.execute(
        f"SELECT * FROM work_record WHERE creator_username = '{creator_username}' and client_username = "
        f"'{client_username}'")
    creator_details = mycur.fetchall()
    conn.commit()

    if creator_details[0][25] == 'yes':
        folder_name = creator_details[0][1]
        files_fetched_check = fetch_files(folder_name)
        files_fetched = [('None')]
        if files_fetched_check:
            files_fetched = files_fetched_check
        services = creator_details[0][9].split(', ')
        number_reels = creator_details[0][19] - creator_details[0][13]
        number_posts = creator_details[0][20] - creator_details[0][15]
        number_story = creator_details[0][21] - creator_details[0][17]
        mycur.execute(f"select * from work_details where creator_username = '{creator_username}' and client_username "
                      f"= '{client_username}' and status_detail = 'active'")
        raw_data = mycur.fetchall()
        conn.commit()
        merged_data = defaultdict(list)
        for item in raw_data:
            merged_data[item[1]].append(item)

        # Process to combine data entries
        final_data = []
        for file_name, items in merged_data.items():
            combined = list(items[0])  # Start with the first item's data
            for item in items[1:]:  # Start from the second item
                for i in range(len(item)):
                    if item[i] is not None:
                        combined[i] = item[i]  # Replace with non-None values
            final_data.append(tuple(combined))
        mycur.execute('select detail_id from work_details where admin_approve = "yes"')
        approved_work = mycur.fetchall()
        conn.commit()
        total_work = creator_details[0][19] + creator_details[0][20] + creator_details[0][21] - len(approved_work)
        files_with_details = []
        for file in files_fetched:
            file_info = {
                'name': file,
                'details': None,
                'reviews': None,
                'approve': None,
            }
            for work in final_data:
                if work[1] == file:
                    if work[12] == 'yes':
                        file_info['details'] = work[4]
                        file_info['reviews'] = work[6]
                        file_info['approve'] = 'yes'
                        break
                    else:
                        file_info['details'] = work[4]
                        file_info['reviews'] = work[6]
                        break
            files_with_details.append(file_info)
        return render_template("adgeeks_client_upload_files_section.html", creator_details=creator_details,
                               files=files_with_details, folder_name=folder_name, services=services,
                               number_reels=number_reels, total_work=total_work,
                               number_posts=number_posts, number_story=number_story, work_details=final_data)
    elif creator_details[0][4] == 'yes' and creator_details[0][6] != 'approved':
        return redirect(url_for('client_calendar', client_username=client_username))
    else:
        return render_template('adgeeks_no_task.html', client_username=client_username)


@app.route('/upload_review_client/<file_name>', methods=['POST'])
def upload_review_client(file_name):
    information_upload = request.form['information']
    mycur.execute("SELECT detail_id FROM work_details ORDER BY detail_id DESC LIMIT 1")
    last_creator_id = mycur.fetchone()
    if last_creator_id:
        last_creator_id = int(last_creator_id[0])
    try:
        detail_id = last_creator_id + 1
    except:
        detail_id = 1
    folder_name = session.get('folder_name')
    mycur.execute(f"select creator_username, client_username from work_record where title = '{folder_name}'")
    username_list = mycur.fetchall()
    conn.commit()
    creator_username = username_list[0][0]
    client_username = username_list[0][1]
    mycur.execute(f"INSERT INTO work_details (detail_id, file_name, client_username, "
                  f"creator_username, review_client, status_detail) VALUES ('{detail_id}', '{file_name}',"
                  f" '{client_username}', '{creator_username}', '{information_upload}', 'active')")
    conn.commit()
    mycur.execute(f"UPDATE work_record set status_client = 'yes' where client_username = '{client_username}'")
    conn.commit()
    return redirect(url_for('client_upload_files_section'))


@app.route('/client_approve_task/<file_name>', methods=['POST', 'GET'])
def client_approve_task(file_name):
    mycur.execute(f"update work_details set client_approve = 'yes' where file_name = '{file_name}' and status_detail = "
                  f"'active'")
    conn.commit()
    client_username = session.get('client_username')
    mycur.execute(f'select creator_username from assign_admin where client_username = "{client_username}"')
    creator_username = mycur.fetchone()[0]
    conn.commit()
    mycur.execute(
        f"SELECT * FROM work_record WHERE creator_username = '{creator_username}' and client_username = "
        f"'{client_username}' and admin_roll_out = 'yes' and work_status != 'Completed'")
    creator_details = mycur.fetchall()
    conn.commit()
    creator_string = creator_details[0][1]
    final_folder_name = creator_string.replace("Raw", "Final")
    # Construct the final directory path
    final_directory_path = f"static/work/{final_folder_name}"

    # Ensure the directory exists, if not, create it
    if not os.path.exists(final_directory_path):
        os.makedirs(final_directory_path)

    # Assuming 'file_name' includes the current relative or absolute path to the file
    current_file_path = f"static/work/{creator_string}/{file_name}"  # Update this if 'file_name' doesn't contain the path

    # Construct the new file path where the file will be moved
    new_file_path = os.path.join(final_directory_path, file_name)

    # Move the file to the new directory
    try:
        shutil.copy(current_file_path, new_file_path)
        print(f"File has been successfully moved to: {new_file_path}")
    except Exception as e:
        print(f"An error occurred while moving the file: {e}")
    return redirect(url_for('client_upload_files_section'))


#
#
#
#
#  client calendar
#
#
#
#

@app.route('/client_calendar/<client_username>')
def client_calendar(client_username):
    mycur.execute(f"SELECT * from client_information where username = '{client_username}'")
    client_details = mycur.fetchall()
    conn.commit()
    mycur.execute(f'select creator_username from assign_admin where client_username = "{client_details[0][3]}"')
    creator_username = mycur.fetchone()[0]
    conn.commit()
    mycur.execute(f"SELECT total_reels, total_posts, total_stories, client_username, calendar_status, title, "
                  f"calendar_review, calendar_update FROM work_record where creator_username = '{creator_username}' "
                  f"and client_username = '{client_username}' ORDER BY work_id ASC LIMIT 1")
    work_record = mycur.fetchone()
    conn.commit()
    service_target_creatives = (f"{work_record[0]} reel(s), {work_record[1]} post(s) and "
                                f"{work_record[2]} story in a month")
    folder_name = work_record[5]
    session['folder_name'] = folder_name
    mycur.execute(f"select id from calendar_data where client_username = '{client_username}' and creator_username = '{creator_username}'")
    calendar_entry = mycur.fetchall()
    conn.commit()
    send_client = False
    if calendar_entry:
        send_client = True
    calendar_update = work_record[7]
    # if calendar_status == 'yes':
    #     return render_template('adgeeks_creator_calendar_approval.html', creator_username=creator_username)
    # else:
    calendar_review = work_record[6]
    if calendar_review and calendar_update != 'yes':
        return render_template('adgeeks_client_review_uploaded.html', client_username=client_username)
    return render_template("adgeeks_client_calendar.html", creator_details=client_details,
                           service_target_creatives=service_target_creatives, send_client=send_client)


@app.route("/calendar_review", methods=['POST', 'GET'])
def calendar_review():
    data = request.get_json()
    client_username = session.get('client_username')
    print(data)
    # information_upload = request.form['information']
    # mycur.execute(f"update work_record set calendar_review = '{information_upload}', calendar_update = 'no' where "
    #               f"client_username = '{client_username}' ORDER BY work_id ASC LIMIT 1")
    # conn.commit()
    return render_template('adgeeks_client_review_uploaded.html', client_username=client_username)


@app.route('/approve_calendar')
def approve_calendar():
    client_username = session.get('client_username')
    mycur.execute(f"UPDATE work_record SET calendar_update = 'approved' where client_username = '{client_username}' "
                  f"ORDER BY work_id ASC LIMIT 1")
    conn.commit()
    return redirect(url_for('client_upload_files_section'))


if __name__ == '__main__':
    app.run(debug=True)
