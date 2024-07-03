from flask import Flask, render_template, request, redirect, url_for
from datetime import datetime

app = Flask(__name__)

# In-memory storage for tasks
tasks = []

@app.route('/')
def index():
    return render_template('index.html', tasks=tasks)

@app.route('/add_task', methods=['POST'])
def add_task():
    task = {
        'id': len(tasks) + 1,
        'title': request.form['title'],
        'description': request.form['description'],
        'assigned_to': request.form['assigned_to'],
        'due_date': datetime.strptime(request.form['due_date'], '%Y-%m-%d'),
        'status': 'Pending'
    }
    tasks.append(task)
    return redirect(url_for('index'))

@app.route('/update_status/<int:task_id>', methods=['POST'])
def update_status(task_id):
    for task in tasks:
        if task['id'] == task_id:
            task['status'] = request.form['status']
            break
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
