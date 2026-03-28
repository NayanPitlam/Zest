import os
import click
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash, session, g
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from flask.cli import with_appcontext

app = Flask(__name__)
app.secret_key = 'super_secret_key' # Make sure to change this in a production environment

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf', 'csv', 'json', 'ppt', 'pptx','doc', 'docx', 'xls', 'xlsx', 'txt', 'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False


# Ensure upload folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, nullable=False, default=False)

class Resource(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    filename = db.Column(db.String(200), nullable=False)
    filetype = db.Column(db.String(50), nullable=False)
    level1 = db.Column(db.String(100))
    level2 = db.Column(db.String(100))
    level3 = db.Column(db.String(100))
    subject = db.Column(db.String(100))
    upload_date = db.Column(db.DateTime, server_default=func.now())


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.before_request
def load_logged_in_user():
    user_id = session.get('user_id')
    if user_id is None:
        g.user = None
    else:
        g.user = User.query.get(user_id)

@app.route('/register', methods=('GET', 'POST'))
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        error = None

        if not username:
            error = 'Username is required.'
        elif not password:
            error = 'Password is required.'
        elif User.query.filter_by(username=username).first() is not None:
             error = f"User {username} is already registered."

        if error is None:
            new_user = User(username=username, password=generate_password_hash(password), is_admin=False)
            db.session.add(new_user)
            db.session.commit()
            return redirect(url_for("login"))

        flash(error)

    return render_template('register.html')

@app.route('/login', methods=('GET', 'POST'))
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        error = None
        user = User.query.filter_by(username=username).first()

        if user is None:
            error = 'Incorrect username.'
        elif not check_password_hash(user.password, password):
            error = 'Incorrect password.'

        if error is None:
            session.clear()
            session['user_id'] = user.id
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
    resources = Resource.query.filter_by(level1='School', level2=f'{class_num}th class').order_by(Resource.subject, Resource.upload_date.desc()).all()
    return render_template('resource_list.html', resources=resources, breadcrumbs=[('School', '/school'), (f'{class_num}th class', '')])

@app.route('/intermediate/<class_num>')
def intermediate_class(class_num):
    resources = Resource.query.filter_by(level1='Intermediate', level2=f'{class_num}th class').order_by(Resource.subject, Resource.upload_date.desc()).all()
    return render_template('resource_list.html', resources=resources, breadcrumbs=[('Intermediate', '/intermediate'), (f'{class_num}th class', '')])

@app.route('/undergrad/<course>')
def undergrad_course(course):
    if course == 'B.Tech':
        return redirect(url_for('btech'))
    resources = Resource.query.filter_by(level1='Undergrad', level2=course).order_by(Resource.level3, Resource.subject, Resource.upload_date.desc()).all()
    # Group resources by semester
    resources_by_sem = {}
    for r in resources:
        sem = r.level3
        if sem not in resources_by_sem:
            resources_by_sem[sem] = []
        resources_by_sem[sem].append(r)
    # Sort resources within each semester by subject
    for sem in resources_by_sem:
        resources_by_sem[sem].sort(key=lambda x: x.subject)
    return render_template('course.html', resources_by_sem=resources_by_sem, breadcrumbs=[('Undergrad', '/undergrad'), (course, '')])

@app.route('/undergrad/<course>/<sem>')
def undergrad_sem(course, sem):
    resources = Resource.query.filter_by(level1='Undergrad', level2=course, level3=sem).order_by(Resource.subject, Resource.upload_date.desc()).all()
    return render_template('resource_list.html', resources=resources, breadcrumbs=[('Undergrad', '/undergrad'), (course, f'/undergrad/{course}'), (sem, '')])



@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    if g.user is None or not g.user.is_admin:
        flash('You are not authorized to access this page.', 'danger')
        return redirect(url_for('login'))

    if request.method == 'POST':
        title = request.form['title']
        level1 = request.form['level1']
        level2 = request.form['level2']
        level3 = request.form.get('level3') # level3 might not be present
        subject = request.form.get('subject') # subject might not be present

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
            
            new_resource = Resource(title=title, filename=filename, filetype=filetype, level1=level1, level2=level2, level3=level3, subject=subject)
            db.session.add(new_resource)
            db.session.commit()
            
            return redirect(url_for('index'))
    return render_template('upload.html')

@app.route('/download/<filename>')
def download_file(filename):
    if g.user is None:
        flash('Please log in to download files.', 'info')
        return redirect(url_for('login'))
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)

@app.route('/remove/<filename>', methods=['GET', 'POST'])
def remove_file(filename):
    if g.user is None or not g.user.is_admin:
        flash('You are not authorized to access this page.', 'danger')
        return redirect(url_for('login'))

    if request.method == 'POST':
        resource_to_delete = Resource.query.filter_by(filename=filename).first()
        if resource_to_delete:
            db.session.delete(resource_to_delete)
            db.session.commit()

            # Delete from filesystem
            os.remove(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            
            flash(f'{filename} has been removed.', 'success')
        else:
            flash(f'{filename} not found in database.', 'warning')
        
        return redirect(url_for('index'))

    return render_template('remove.html', filename=filename)

@click.command('create-admin')
@with_appcontext
def create_admin_command():
    """Create a new admin user."""
    if not User.query.filter_by(username='admin').first():
        admin = User(username='admin', password=generate_password_hash('admin'), is_admin=True)
        db.session.add(admin)
        db.session.commit()
        click.echo('Admin user created.')
    else:
        click.echo('Admin user already exists.')

app.cli.add_command(create_admin_command)

@click.command('test-command')
@with_appcontext
def test_command():
    """A simple test command."""
    click.echo('Test command executed successfully!')

app.cli.add_command(test_command)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
