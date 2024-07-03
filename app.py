from flask import Flask, render_template, request, redirect, url_for, jsonify
from datetime import datetime, date

app = Flask(__name__)

# In-memory storage for tasks
tasks = []

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/tasks')
def get_tasks():
    filtered_tasks = tasks
    sort_by = request.args.get('sort_by', 'due_date')
    filter_status = request.args.get('filter_status', '')
    filter_priority = request.args.get('filter_priority', '')
    filter_category = request.args.get('filter_category', '')
    search_query = request.args.get('search', '').lower()

    if filter_status:
        filtered_tasks = [task for task in filtered_tasks if task['status'] == filter_status]
    if filter_priority:
        filtered_tasks = [task for task in filtered_tasks if task['priority'] == filter_priority]
    if filter_category:
        filtered_tasks = [task for task in filtered_tasks if filter_category in task['categories']]
    if search_query:
        filtered_tasks = [task for task in filtered_tasks if search_query in task['title'].lower() or search_query in task['description'].lower()]

    sorted_tasks = sorted(filtered_tasks, key=lambda x: x[sort_by])
    
    return jsonify(sorted_tasks)

@app.route('/add_task', methods=['POST'])
def add_task():
    task = {
        'id': len(tasks) + 1,
        'title': request.form['title'],
        'description': request.form['description'],
        'assigned_to': request.form['assigned_to'],
        'due_date': request.form['due_date'],
        'status': 'Pending',
        'priority': request.form['priority'],
        'categories': request.form['categories'].split(',')
    }
    tasks.append(task)
    return jsonify(success=True)

@app.route('/update_task/<int:task_id>', methods=['POST'])
def update_task(task_id):
    for task in tasks:
        if task['id'] == task_id:
            task['status'] = request.form['status']
            task['priority'] = request.form['priority']
            task['due_date'] = request.form['due_date']
            break
    return jsonify(success=True)

if __name__ == '__main__':
    app.run(debug=True)
