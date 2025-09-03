
from typing import Dict, List, Tuple

# Map streams and traits to suggested course codes
STREAM_TO_COURSES = {
    'Science': ['CSE', 'ECE', 'ME', 'BIO', 'DS', 'AI'],
    'Commerce': ['BBA', 'BCom', 'CA', 'CS', 'FIN', 'DS'],
    'Arts': ['BA', 'LAW', 'PSY', 'DESIGN', 'JOUR']
}

PERSONALITY_TO_COURSES = {
    'Analytical': ['CSE','AI','DS','FIN','ME'],
    'Creative': ['DESIGN','JOUR','BA','CSE'],
    'Social': ['BBA','LAW','PSY','JOUR'],
    'Practical': ['ME','ECE','BIO']
}

COURSE_DIFFICULTY = {
    'CSE': 80, 'AI': 85, 'DS': 82, 'ECE': 78, 'ME': 75, 'BIO': 70,
    'BBA': 60, 'BCom': 65, 'CA': 85, 'CS': 80, 'FIN': 78,
    'BA': 55, 'LAW': 75, 'PSY': 65, 'DESIGN': 60, 'JOUR': 58
}

COURSE_LABELS = {
    'CSE': 'Computer Science & Engineering',
    'AI': 'Artificial Intelligence',
    'DS': 'Data Science',
    'ECE': 'Electronics & Communication',
    'ME': 'Mechanical Engineering',
    'BIO': 'Biotechnology/Biology',
    'BBA': 'Bachelor of Business Administration',
    'BCom': 'Bachelor of Commerce',
    'CA': 'Chartered Accountancy',
    'CS': 'Company Secretary',
    'FIN': 'Finance/Investment',
    'BA': 'Bachelor of Arts',
    'LAW': 'Law (LLB)',
    'PSY': 'Psychology',
    'DESIGN': 'Design/UI-UX',
    'JOUR': 'Journalism & Mass Comm.'
}


def normalize_score(marks: float) -> int:
    # Convert board % to 0-20 scale
    try:
        m = max(0.0, min(100.0, float(marks)))
    except Exception:
        m = 0.0
    return round(m * 0.2)


def pick_personality(traits: Dict[str, int]) -> str:
    # traits like {"Analytical": 7, "Creative": 5, ...}
    if not traits:
        return 'Analytical'
    return max(traits.items(), key=lambda t: t[1])[0]


def recommend_courses(stream: str, board_marks: float, aptitude_score20: int,
                      personality_type: str, dream_course: str | None) -> List[Tuple[str, int]]:
    candidates = set()
    # Seed by stream
    if stream in STREAM_TO_COURSES:
        candidates.update(STREAM_TO_COURSES[stream])
    # Seed by personality
    if personality_type in PERSONALITY_TO_COURSES:
        candidates.update(PERSONALITY_TO_COURSES[personality_type])
    # Include dream course if any
    if dream_course:
        candidates.add(dream_course)

    # Academic strength on 0-20
    academics20 = normalize_score(board_marks)

    # Composite score per course
    results = []
    for code in candidates:
        diff = COURSE_DIFFICULTY.get(code, 60)
        # Base fit: higher if aptitude and academics meet difficulty
        fit = 50
        fit += (aptitude_score20 - (diff - 60) / 4) * 1.5
        fit += (academics20 - (diff - 60) / 4) * 1.2
        # Personality boost if course in personality list
        if personality_type in PERSONALITY_TO_COURSES and code in PERSONALITY_TO_COURSES[personality_type]:
            fit += 8
        # Dream course bonus
        if dream_course == code:
            fit += 10
        # Clamp 0-100
        fit = int(max(0, min(100, round(fit))))
        results.append((code, fit))

    # Sort by fit desc, then by difficulty asc
    results.sort(key=lambda x: (-x[1], COURSE_DIFFICULTY.get(x[0], 60)))
    return results[:6]


def filter_colleges(all_colleges: List[dict], selected_course: str, city: str, country: str,
                    abroad: bool, budget: int, include_private=True, include_government=True) -> List[dict]:
    out = []
    for c in all_colleges:
        if selected_course not in [s.strip() for s in c['courses'].split(',')]:
            continue
        if abroad:
            if c['country'].lower() == country.lower():
                continue
        else:
            if c['country'].lower() != country.lower():
                continue
        # If staying in-country, prioritize same city but include others
        city_score = 2 if c['city'].lower() == city.lower() else 1
        # Fees filter by budget if provided (>0)
        if budget and c['fees_per_year'] > budget:
            continue
        if not include_private and not c['is_government']:
            continue
        if not include_government and c['is_government']:
            continue
        cpy = dict(c)
        cpy['city_score'] = city_score
        out.append(cpy)
    out.sort(key=lambda r: (-r['city_score'], r['fees_per_year']))
    return out
