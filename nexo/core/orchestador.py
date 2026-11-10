import sqlite3

def calculate_real_progress(database_path, task_id):
    # Connect to the database
    conn = sqlite3.connect(database_path)
    cursor = conn.cursor()

    try:
        # Query the database for progress data
        cursor.execute("SELECT completed_tasks, total_tasks FROM tasks WHERE id = ?", (task_id,))
        result = cursor.fetchone()

        if not result:
            return 0

        completed_tasks, total_tasks = result

        # Calculate the real percentage of progress
        real_progress = (completed_tasks / total_tasks) * 100

        return real_progress

    finally:
        conn.close()
