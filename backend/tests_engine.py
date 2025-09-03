
import json
import os
from typing import List, Dict
from .db import connect, execute, query_all

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SAMPLE_DIR = os.path.join(BASE_DIR, 'sample_data')

QUESTIONS_MAP = {
    'aptitude': os.path.join(SAMPLE_DIR, 'questions_aptitude.json'),
    'personality': os.path.join(SAMPLE_DIR, 'questions_personality.json')
}


def load_questions(kind: str) -> List[dict]:
    path = QUESTIONS_MAP[kind]
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def seed_questions_if_empty():
    existing = query_all('SELECT COUNT(1) AS n FROM test_questions')
    if existing and existing[0]['n'] > 0:
        return
    for kind in ('aptitude','personality'):
        for q in load_questions(kind):
            execute('INSERT INTO test_questions(kind, question, options_json, answer_key, trait_map_json) VALUES(?,?,?,?,?)', (
                kind,
                q['question'],
                json.dumps(q['options']),
                q.get('answer_key'),
                json.dumps(q.get('traits', {}))
            ))


def score_aptitude(answers: Dict[int, str]) -> int:
    # answers: {question_id: chosen_key}
    with connect() as con:
        rows = con.execute('SELECT id, answer_key FROM test_questions WHERE kind="aptitude"').fetchall()
        ans_map = {r['id']: r['answer_key'] for r in rows}
    score = 0
    for qid, chosen in answers.items():
        if ans_map.get(int(qid)) == chosen:
            score += 1
    return score  # out of number of aptitude questions


def score_personality(answers: Dict[int, str]) -> Dict[str, int]:
    # Sum trait points from selected options
    trait_totals: Dict[str, int] = {}
    with connect() as con:
        rows = con.execute('SELECT id, options_json, trait_map_json FROM test_questions WHERE kind="personality"').fetchall()
    for r in rows:
        qid = r['id']
        trait_map = json.loads(r['trait_map_json'] or '{}')
        chosen_key = answers.get(qid)
        if chosen_key and chosen_key in trait_map:
            # trait_map like {"A": {"Analytical":2}, "B": {"Creative":2}}
            for trait, pts in trait_map[chosen_key].items():
                trait_totals[trait] = trait_totals.get(trait, 0) + int(pts)
    return trait_totals
