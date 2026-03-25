import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash, session, g
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'super_secret_key' # Make sure to change this in a production environment

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf', 'csv', 'json', 'ppt', 'pptx','doc', 'docx', 'xls', 'xlsx', 'txt', 'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Ensure upload folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.before_request
def load_logged_in_user():
    user_id = session.get('user_id')
    if user_id is None:
        g.user = None
    else:
        conn = get_db_connection()
        g.user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
        conn.close()

@app.route('/register', methods=('GET', 'POST'))
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        db = get_db_connection()
        error = None

        if not username:
            error = 'Username is required.'
        elif not password:
            error = 'Password is required.'
        
        if error is None:
            try:
                db.execute(
                    "INSERT INTO users (username, password, is_admin) VALUES (?, ?, ?)",
                    (username, generate_password_hash(password), 0),
                )
                db.commit()
            except db.IntegrityError:
                error = f"User {username} is already registered."
            else:
                return redirect(url_for("login"))
        
        flash(error)

    return render_template('register.html')

@app.route('/login', methods=('GET', 'POST'))
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        db = get_db_connection()
        error = None
        user = db.execute(
            'SELECT * FROM users WHERE username = ?', (username,)
        ).fetchone()

        if user is None:
            error = 'Incorrect username.'
        elif not check_password_hash(user['password'], password):
            error = 'Incorrect password.'

        if error is None:
            session.clear()
            session['user_id'] = user['id']
            return redirect(url_for('index'))

        flash(error)

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/school')
def school():
    return render_template('school.html', classes=range(1, 11))

@app.route('/intermediate')
def intermediate():
    return render_template('intermediate.html', classes=[11, 12])

@app.route('/undergrad')
def undergrad():
    courses = ['B.Tech'] # Add more courses here in the future
    return render_template('undergrad.html', courses=courses)

@app.route('/btech')
def btech():
    semesters = ['1-1', '1-2', '2-1', '2-2', '3-1', '3-2', '4-1', '4-2']
    return render_template('btech.html', course='B.Tech', semesters=semesters)

@app.route('/school/<class_num>')
def school_class(class_num):
    conn = get_db_connection()
    resources = conn.execute('SELECT * FROM resources WHERE level1 = ? AND level2 = ? ORDER BY upload_date DESC', ('School', f'{class_num}th class')).fetchall()
    conn.close()
    return render_template('resource_list.html', resources=resources, breadcrumbs=[('School', '/school'), (f'{class_num}th class', '')])

@app.route('/intermediate/<class_num>')
def intermediate_class(class_num):
    conn = get_db_connection()
    resources = conn.execute('SELECT * FROM resources WHERE level1 = ? AND level2 = ? ORDER BY upload_date DESC', ('Intermediate', f'{class_num}th class')).fetchall()
    conn.close()
    return render_template('resource_list.html', resources=resources, breadcrumbs=[('Intermediate', '/intermediate'), (f'{class_num}th class', '')])

@app.route('/undergrad/<course>')
def undergrad_course(course):
    if course == 'B.Tech':
        return redirect(url_for('btech'))
    conn = get_db_connection()
    resources = conn.execute('SELECT * FROM resources WHERE level1 = ? AND level2 = ? ORDER BY level3, upload_date DESC', ('Undergrad', course)).fetchall()
    conn.close()
    # Group resources by semester
    resources_by_sem = {}
    for r in resources:
        sem = r['level3']
        if sem not in resources_by_sem:
            resources_by_sem[sem] = []
        resources_by_sem[sem].append(r)
    return render_template('course.html', resources_by_sem=resources_by_sem, breadcrumbs=[('Undergrad', '/undergrad'), (course, '')])

@app.route('/undergrad/<course>/<sem>')
def undergrad_sem(course, sem):
    conn = get_db_connection()
    resources = conn.execute('SELECT * FROM resources WHERE level1 = ? AND level2 = ? AND level3 = ? ORDER BY upload_date DESC', ('Undergrad', course, sem)).fetchall()
    conn.close()
    return render_template('resource_list.html', resources=resources, breadcrumbs=[('Undergrad', '/undergrad'), (course, f'/undergrad/{course}'), (sem, '')])



@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    if g.user is None or not g.user['is_admin']:
        flash('You are not authorized to access this page.', 'danger')
        return redirect(url_for('login'))

    if request.method == 'POST':
        title = request.form['title']
        level1 = request.form['level1']
        level2 = request.form['level2']
        level3 = request.form.get('level3') # level3 might not be present

        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filetype = filename.rsplit('.', 1)[1].lower()
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            
            conn = get_db_connection()
            conn.execute('INSERT INTO resources (title, filename, filetype, level1, level2, level3) VALUES (?, ?, ?, ?, ?, ?)',
                         (title, filename, filetype, level1, level2, level3))
            conn.commit()
            conn.close()
            return redirect(url_for('index'))
    return render_template('upload.html')

@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)

@app.route('/remove/<filename>', methods=['GET', 'POST'])
def remove_file(filename):
    if g.user is None or not g.user['is_admin']:
        flash('You are not authorized to access this page.', 'danger')
        return redirect(url_for('login'))

    if request.method == 'POST':
        # Delete from DB
        conn = get_db_connection()
        conn.execute('DELETE FROM resources WHERE filename = ?', (filename,))
        conn.commit()
        conn.close()

        # Delete from filesystem
        os.remove(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        
        flash(f'{filename} has been removed.', 'success')
        return redirect(url_for('index'))

    return render_template('remove.html', filename=filename)







if __name__ == '__main__':







    # Initialize DB schema on startup







    conn = get_db_connection()







    with open('schema.sql') as f:







        conn.executescript(f.read())







    admin_user = conn.execute('SELECT * FROM users WHERE username = ?', ('admin',)).fetchone()
    if not admin_user:
        conn.execute('INSERT INTO users (username, password, is_admin) VALUES (?, ?, ?)',
                     ('admin', generate_password_hash('admin'), 1))
        conn.commit()

    conn.close()







    app.run(debug=True)
