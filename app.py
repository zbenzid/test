from flask import Flask, render_template, request, redirect, url_for, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date
import os
from functools import wraps

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///tasks.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    assigned_to = db.Column(db.String(80), nullable=False)
    due_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), nullable=False)
    priority = db.Column(db.String(20), nullable=False)
    categories = db.Column(db.String(200), nullable=True)
    parent_id = db.Column(db.Integer, db.ForeignKey('task.id'), nullable=True)
    time_spent = db.Column(db.Integer, default=0)
    recurring = db.Column(db.Boolean, default=False)
    recurring_interval = db.Column(db.Integer, nullable=True)
    recurring_unit = db.Column(db.String(10), nullable=True)

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('task.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class TaskHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('task.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    change_type = db.Column(db.String(50), nullable=False)
    old_value = db.Column(db.Text, nullable=True)
    new_value = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.username != 'admin':
            return jsonify(error="Admin access required"), 403
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
@login_required
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('index'))
        return 'Invalid username or password'
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        hashed_password = generate_password_hash(password)
        new_user = User(username=username, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/tasks')
@login_required
def get_tasks():
    sort_by = request.args.get('sort_by', 'due_date')
    filter_status = request.args.get('filter_status', '')
    filter_priority = request.args.get('filter_priority', '')
    filter_category = request.args.get('filter_category', '')
    search_query = request.args.get('search', '').lower()

    query = Task.query

    if filter_status:
        query = query.filter_by(status=filter_status)
    if filter_priority:
        query = query.filter_by(priority=filter_priority)
    if filter_category:
        query = query.filter(Task.categories.contains(filter_category))
    if search_query:
        query = query.filter((Task.title.ilike(f'%{search_query}%')) | (Task.description.ilike(f'%{search_query}%')))

    tasks = query.order_by(getattr(Task, sort_by)).all()
    return jsonify([task.to_dict() for task in tasks])

@app.route('/add_task', methods=['POST'])
@login_required
def add_task():
    new_task = Task(
        title=request.form['title'],
        description=request.form['description'],
        assigned_to=request.form['assigned_to'],
        due_date=datetime.strptime(request.form['due_date'], '%Y-%m-%d').date(),
        status='Pending',
        priority=request.form['priority'],
        categories=request.form['categories'],
        recurring=request.form.get('recurring', 'false') == 'true',
        recurring_interval=request.form.get('recurring_interval', type=int),
        recurring_unit=request.form.get('recurring_unit')
    )
    db.session.add(new_task)
    db.session.commit()

    if 'file' in request.files:
        file = request.files['file']
        if file.filename != '':
            filename = f"{new_task.id}_{file.filename}"
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

    return jsonify(success=True)

@app.route('/update_task/<int:task_id>', methods=['POST'])
@login_required
def update_task(task_id):
    task = Task.query.get_or_404(task_id)
    old_values = {
        'status': task.status,
        'priority': task.priority,
        'due_date': task.due_date
    }
    task.status = request.form['status']
    task.priority = request.form['priority']
    task.due_date = datetime.strptime(request.form['due_date'], '%Y-%m-%d').date()
    db.session.commit()

    for field, old_value in old_values.items():
        new_value = getattr(task, field)
        if old_value != new_value:
            history = TaskHistory(
                task_id=task.id,
                user_id=current_user.id,
                change_type=f'Updated {field}',
                old_value=str(old_value),
                new_value=str(new_value)
            )
            db.session.add(history)
    db.session.commit()

    return jsonify(success=True)

@app.route('/add_comment/<int:task_id>', methods=['POST'])
@login_required
def add_comment(task_id):
    content = request.form['content']
    new_comment = Comment(task_id=task_id, user_id=current_user.id, content=content)
    db.session.add(new_comment)
    db.session.commit()
    return jsonify(success=True)

@app.route('/get_comments/<int:task_id>')
@login_required
def get_comments(task_id):
    comments = Comment.query.filter_by(task_id=task_id).order_by(Comment.timestamp.desc()).all()
    return jsonify([comment.to_dict() for comment in comments])

@app.route('/add_subtask/<int:parent_id>', methods=['POST'])
@login_required
def add_subtask(parent_id):
    parent_task = Task.query.get_or_404(parent_id)
    new_subtask = Task(
        title=request.form['title'],
        description=request.form['description'],
        assigned_to=request.form['assigned_to'],
        due_date=datetime.strptime(request.form['due_date'], '%Y-%m-%d').date(),
        status='Pending',
        priority=request.form['priority'],
        categories=request.form['categories'],
        parent_id=parent_id
    )
    db.session.add(new_subtask)
    db.session.commit()
    return jsonify(success=True)

@app.route('/update_time_spent/<int:task_id>', methods=['POST'])
@login_required
def update_time_spent(task_id):
    task = Task.query.get_or_404(task_id)
    time_spent = request.form.get('time_spent', type=int)
    if time_spent is not None:
        task.time_spent += time_spent
        db.session.commit()
        return jsonify(success=True)
    return jsonify(success=False, error="Invalid time spent value"), 400

@app.route('/export_tasks')
@login_required
def export_tasks():
    tasks = Task.query.all()
    csv_data = "ID,Title,Description,Assigned To,Due Date,Status,Priority,Categories\n"
    for task in tasks:
        csv_data += f"{task.id},{task.title},{task.description},{task.assigned_to},{task.due_date},{task.status},{task.priority},{task.categories}\n"
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=tasks.csv"}
    )

@app.route('/dashboard')
@login_required
def dashboard():
    total_tasks = Task.query.count()
    completed_tasks = Task.query.filter_by(status='Completed').count()
    completion_rate = (completed_tasks / total_tasks) * 100 if total_tasks > 0 else 0
    
    tasks_by_priority = db.session.query(Task.priority, db.func.count(Task.id)).group_by(Task.priority).all()
    tasks_by_status = db.session.query(Task.status, db.func.count(Task.id)).group_by(Task.status).all()
    
    return jsonify({
        'total_tasks': total_tasks,
        'completed_tasks': completed_tasks,
        'completion_rate': completion_rate,
        'tasks_by_priority': dict(tasks_by_priority),
        'tasks_by_status': dict(tasks_by_status)
    })

if __name__ == '__main__':
    db.create_all()
    app.run(debug=True)
