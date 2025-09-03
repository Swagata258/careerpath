""""
Simple trainer: loads CSVs (colleges/resources) & seeds DB.
Also, you can extend with your own dataset mapping stream+marks to course codes.
No third-party packages used.
"""
import csv
import json
import os
from datetime import datetime, timedelta
from .db import init_db, execute, query_all
from .tests_engine import seed_questions_if_empty

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SAMPLE_DIR = os.path.join(BASE_DIR, 'sample_data')


def seed_colleges():
    path = os.path.join(SAMPLE_DIR, 'colleges.csv')
    with open(path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            courses = [row[f'courses{i}'] for i in range(5) if f'courses{i}' in row and row[f'courses{i}']]
            courses_str = ",".join(courses)

            execute("""
                INSERT INTO colleges
                (name, country, city, is_government, courses, fees_per_year, scholarships, placements, website)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                row['name'], row['country'], row['city'], int(row['is_government']),
                courses_str, int(row['fees_per_year']), row['scholarships'], row['placements'], row['website']
            ))

def seed_resources():
    with open(os.path.join(BASE_DIR, "sample_data", "resources.csv"), "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            course_code = row.get("course_code") or row.get("CourseCode") or "UNKNOWN"
            title = row.get("title") or "Untitled"
            url = row.get("url") or ""
            is_free = int(row.get("is_free", "1"))

            execute(
                "INSERT INTO resources (course_code, title, url, is_free) VALUES (?,?,?,?)",
                (course_code, title, url, is_free),
            )


def run():
    print('Initializing database...')
    init_db()
    print('Seeding questions...')
    seed_questions_if_empty()
    # Only seed colleges/resources if empty
    if query_all('SELECT COUNT(1) as n FROM colleges')[0]['n'] == 0:
        print('Seeding colleges...')
        seed_colleges()
    if query_all('SELECT COUNT(1) as n FROM resources')[0]['n'] == 0:
        print('Seeding resources...')
        seed_resources()
    print('Done.')

if __name__ == '__main__':
    run()