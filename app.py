from flask import Flask, render_template, request, redirect, url_for
from datetime import datetime, date

app = Flask(__name__)

# In-memory storage for tasks
tasks = []

@app.route('/')
def index():
    filtered_tasks = tasks
    sort_by = request.args.get('sort_by', 'due_date')
    filter_status = request.args.get('filter_status', '')
    filter_priority = request.args.get('filter_priority', '')
    filter_category = request.args.get('filter_category', '')

    if filter_status:
        filtered_tasks = [task for task in filtered_tasks if task['status'] == filter_status]
    if filter_priority:
        filtered_tasks = [task for task in filtered_tasks if task['priority'] == filter_priority]
    if filter_category:
        filtered_tasks = [task for task in filtered_tasks if filter_category in task['categories']]

    sorted_tasks = sorted(filtered_tasks, key=lambda x: x[sort_by])
    
    return render_template('index.html', tasks=sorted_tasks)

@app.route('/add_task', methods=['POST'])
def add_task():
    task = {
        'id': len(tasks) + 1,
        'title': request.form['title'],
        'description': request.form['description'],
        'assigned_to': request.form['assigned_to'],
        'due_date': datetime.strptime(request.form['due_date'], '%Y-%m-%d'),
        'status': 'Pending',
        'priority': request.form['priority'],
        'categories': request.form.getlist('categories')
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
