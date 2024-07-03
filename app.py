from flask import Flask, render_template, request, redirect, url_for, jsonify, session, Response
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date
import os
from functools import wraps
from flask_ckeditor import CKEditor

app = Flask(__name__)
ckeditor = CKEditor(app)
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
    dependencies = db.relationship('TaskDependency', foreign_keys='TaskDependency.task_id', backref='task', lazy='dynamic')
    dependent_on = db.relationship('TaskDependency', foreign_keys='TaskDependency.dependency_id', backref='dependent_task', lazy='dynamic')
    order = db.Column(db.Integer, nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'assigned_to': self.assigned_to,
            'due_date': self.due_date.isoformat(),
            'status': self.status,
            'priority': self.priority,
            'categories': self.categories,
            'parent_id': self.parent_id,
            'time_spent': self.time_spent,
            'recurring': self.recurring,
            'recurring_interval': self.recurring_interval,
            'recurring_unit': self.recurring_unit
        }

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

class TaskDependency(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('task.id'), nullable=False)
    dependency_id = db.Column(db.Integer, db.ForeignKey('task.id'), nullable=False)

class TaskTemplate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

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
    completed_tasks = [task.to_dict() for task in tasks if task.status == 'Completed']
    active_tasks = [task.to_dict() for task in tasks if task.status != 'Completed']
    
    app.logger.info(f"Retrieved {len(active_tasks)} active tasks and {len(completed_tasks)} completed tasks")
    
    return jsonify({
        'active_tasks': active_tasks,
        'completed_tasks': completed_tasks
    })

@app.route('/add_task', methods=['POST'])
@login_required
def add_task():
    try:
        form_data = request.form.to_dict()
        app.logger.info(f"Received task data: {form_data}")
        
        new_task = Task(
            title=form_data['title'],
            description=form_data['description'],
            assigned_to=form_data['assigned_to'],
            due_date=datetime.strptime(form_data['due_date'], '%Y-%m-%d').date(),
            status='Pending',
            priority=form_data['priority'],
            categories=form_data['categories'],
            recurring=form_data.get('recurring', 'false') == 'true',
            recurring_interval=form_data.get('recurring_interval', type=int),
            recurring_unit=form_data.get('recurring_unit')
        )
        db.session.add(new_task)
        db.session.commit()

        if 'file' in request.files:
            file = request.files['file']
            if file.filename != '':
                filename = f"{new_task.id}_{file.filename}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        app.logger.info(f"Task added successfully: {new_task.to_dict()}")
        return jsonify(success=True, task=new_task.to_dict())
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error adding task: {str(e)}")
        return jsonify(success=False, error=str(e)), 500

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

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

@app.route('/add_dependency', methods=['POST'])
@login_required
def add_dependency():
    task_id = request.form.get('task_id', type=int)
    dependency_id = request.form.get('dependency_id', type=int)
    if task_id and dependency_id:
        new_dependency = TaskDependency(task_id=task_id, dependency_id=dependency_id)
        db.session.add(new_dependency)
        db.session.commit()
        return jsonify(success=True)
    return jsonify(success=False, error="Invalid task or dependency ID"), 400

@app.route('/remove_dependency', methods=['POST'])
@login_required
def remove_dependency():
    task_id = request.form.get('task_id', type=int)
    dependency_id = request.form.get('dependency_id', type=int)
    if task_id and dependency_id:
        dependency = TaskDependency.query.filter_by(task_id=task_id, dependency_id=dependency_id).first()
        if dependency:
            db.session.delete(dependency)
            db.session.commit()
            return jsonify(success=True)
    return jsonify(success=False, error="Dependency not found"), 404

@app.route('/save_task_template', methods=['POST'])
@login_required
def save_task_template():
    name = request.form.get('name')
    description = request.form.get('description')
    if name:
        new_template = TaskTemplate(name=name, description=description, user_id=current_user.id)
        db.session.add(new_template)
        db.session.commit()
        return jsonify(success=True, template_id=new_template.id)
    return jsonify(success=False, error="Template name is required"), 400

@app.route('/get_task_templates')
@login_required
def get_task_templates():
    templates = TaskTemplate.query.filter_by(user_id=current_user.id).all()
    return jsonify([{
        'id': template.id,
        'name': template.name,
        'description': template.description
    } for template in templates])

@app.route('/update_task_order', methods=['POST'])
@login_required
def update_task_order():
    task_orders = request.json.get('task_orders', [])
    for task_order in task_orders:
        task = Task.query.get(task_order['id'])
        if task:
            task.order = task_order['order']
    db.session.commit()
    return jsonify(success=True)

@app.route('/advanced_filter', methods=['POST'])
@login_required
def advanced_filter():
    filters = request.json.get('filters', {})
    query = Task.query

    if 'status' in filters:
        query = query.filter(Task.status.in_(filters['status']))
    if 'priority' in filters:
        query = query.filter(Task.priority.in_(filters['priority']))
    if 'assigned_to' in filters:
        query = query.filter(Task.assigned_to.in_(filters['assigned_to']))
    if 'due_date_start' in filters:
        query = query.filter(Task.due_date >= datetime.strptime(filters['due_date_start'], '%Y-%m-%d').date())
    if 'due_date_end' in filters:
        query = query.filter(Task.due_date <= datetime.strptime(filters['due_date_end'], '%Y-%m-%d').date())
    if 'categories' in filters:
        query = query.filter(Task.categories.contains(filters['categories']))

    tasks = query.order_by(Task.order).all()
    return jsonify([task.to_dict() for task in tasks])

if __name__ == '__main__':
    db.create_all()
    app.run(debug=True)
