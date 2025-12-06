"""
Complete Scoring Service with Competency Breakdown
Save as: proctoring/services/simple_scoring.py
"""
from typing import List, Dict, Tuple
from proctoring.models import Exam, CheatingEvent, CompetencyScore


class SimpleScoringService:
    """Calculate scores, competency breakdown, and rankings"""

    # Marks per competency
    MARKS = {
        'critical_thinking': 4,
        'communication': 2,
        'adaptability': 1,
        'basic_engineering': 5,
        'technical': 6,
    }

    # Maximum possible scores
    MAX_SCORES = {
        'critical_thinking': 5 * 4,   # 20
        'communication': 5 * 2,       # 10
        'adaptability': 2 * 1,        # 2
        'basic_engineering': 5 * 5,   # 25
        'technical': 8 * 6,           # 48
    }

    # Competency weights (job relevance)
    COMPETENCY_WEIGHTS = {
        'critical_thinking': 0.30,
        'communication': 0.20,
        'adaptability': 0.10,
        'basic_engineering': 0.30,
        'technical': 0.50,
    }

    # Course mapping
    COURSE_MAPPING = {
        'critical_thinking': {
            'priority': ['Critical Thinking Bootcamp', 'Problem Solving Workshops'],
            'complementary': ['Decision Making for Engineers'],
            'advanced': ['Advanced Systems Thinking'],
        },
        'communication': {
            'priority': ['Technical Writing Essentials', 'Presentation Skills'],
            'complementary': ['Interpersonal Communication'],
            'advanced': ['Professional Communication for Leaders'],
        },
        'adaptability': {
            'priority': ['Change Management Fundamentals'],
            'complementary': ['Time & Priority Management'],
            'advanced': ['Leadership Agility Program'],
        },
        'basic_engineering': {
            'priority': ['Engineering Fundamentals Refresher'],
            'complementary': ['Materials & Manufacturing Basics'],
            'advanced': ['Advanced Engineering Design'],
        },
        'technical': {
            'priority': ['Field-specific Technical Foundations'],
            'complementary': ['Applied Technical Projects'],
            'advanced': ['Specialization / Capstone Projects'],
        },
    }

    def __init__(self, exam):
        self.exam = exam

    # ---------------------------------------------------------
    # COMPETENCY BREAKDOWN
    # ---------------------------------------------------------
    def save_competency_breakdown(self, competency_scores: Dict[str, float]):
        """Save competency scores, cap %, assign levels, mark strengths & weaknesses"""
        CompetencyScore.objects.filter(exam=self.exam).delete()

        created_scores = []

        for competency_name, raw_score in competency_scores.items():
            max_score = self.MAX_SCORES.get(competency_name, 0)
            percentage = (raw_score / max_score * 100) if max_score > 0 else 0
            percentage = max(0, min(100, percentage))  # cap 0–100

            # Performance level
            if percentage >= 85:
                level = 'advanced'
            elif percentage >= 70:
                level = 'proficient'
            elif percentage >= 50:
                level = 'developing'
            elif percentage >= 30:
                level = 'emerging'
            else:
                level = 'novice'

            obj = CompetencyScore.objects.create(
                exam=self.exam,
                competency_name=competency_name,
                raw_score=raw_score,
                max_score=max_score,
                percentage=percentage,
                performance_level=level,
                is_strength=False,
                is_weakness=False
            )
            created_scores.append(obj)

        self.identify_strengths_weaknesses(created_scores)

    # ---------------------------------------------------------
    # STRENGTHS & WEAKNESSES
    # ---------------------------------------------------------
    def identify_strengths_weaknesses(self, comp_scores: List[CompetencyScore]):
        """Strength ≥75% top2; Weak <60% bottom2"""
        if not comp_scores:
            return

        comp_scores.sort(key=lambda x: x.percentage, reverse=True)

        CompetencyScore.objects.filter(exam=self.exam).update(is_strength=False, is_weakness=False)

        # Strengths
        strengths = [c for c in comp_scores if c.percentage >= 75]
        if len(strengths) < 2:
            strengths = comp_scores[:2]
        for c in strengths[:2]:
            c.is_strength = True
            c.save(update_fields=['is_strength'])

        # Weaknesses
        bottom_sorted = sorted(comp_scores, key=lambda x: x.percentage)
        weaknesses = [c for c in bottom_sorted if c.percentage < 60]
        if len(weaknesses) < 2:
            weaknesses = bottom_sorted[:2]
        for c in weaknesses[:2]:
            c.is_weakness = True
            c.save(update_fields=['is_weakness'])

    # ---------------------------------------------------------
    # IMPROVEMENT PRIORITIES
    # ---------------------------------------------------------
    def compute_improvement_priorities(self):
        priorities = []
        for c in CompetencyScore.objects.filter(exam=self.exam):
            gap = max(0, 75 - c.percentage)
            weight = self.COMPETENCY_WEIGHTS.get(c.competency_name, 0)
            priority_score = round(gap * weight, 3)
            priorities.append({
                'competency_name': c.competency_name,
                'percentage': c.percentage,
                'priority_score': priority_score,
                'is_strength': c.is_strength,
                'is_weakness': c.is_weakness
            })
        priorities.sort(key=lambda x: x['priority_score'], reverse=True)
        return priorities

    # ---------------------------------------------------------
    # COURSE RECOMMENDATION
    # ---------------------------------------------------------
    def recommend_courses(self):
        comp_scores = list(CompetencyScore.objects.filter(exam=self.exam))
        comp_scores.sort(key=lambda c: c.percentage, reverse=True)

        priority = []
        complementary = []
        advanced = []

        pr = self.compute_improvement_priorities()
        weak = [p for p in pr if p['percentage'] < 60]

        # fallback if none <60
        if not weak:
            weak = pr[-2:]

        for w in weak[:2]:
            comp = w['competency_name']
            priority += self.COURSE_MAPPING.get(comp, {}).get('priority', [])

        # complementary: 50–75
        for c in comp_scores:
            if 50 <= c.percentage < 75:
                complementary += self.COURSE_MAPPING.get(c.competency_name, {}).get('complementary', [])

        # advanced: ≥75
        for c in comp_scores:
            if c.percentage >= 75:
                advanced += self.COURSE_MAPPING.get(c.competency_name, {}).get('advanced', [])

        return {
            'priority_courses': list(dict.fromkeys(priority)),
            'complementary_courses': list(dict.fromkeys(complementary)),
            'advanced_courses': list(dict.fromkeys(advanced)),
        }

    # ---------------------------------------------------------
    # ACTION PLAN
    # ---------------------------------------------------------
    def generate_action_plan(self):
        rec = self.recommend_courses()
        priority = rec['priority_courses'][:2]
        complementary = rec['complementary_courses'][:2]
        advanced = rec['advanced_courses'][:2]

        plan = {
            '30_days': [],
            '90_days': [],
            '6_12_months': []
        }

        if priority:
            plan['30_days'].append(f"Complete priority course: {priority[0]}")
        else:
            plan['30_days'].append("Start with foundational skill-building tasks")

        plan['30_days'].append("Practice 30–60 mins daily on weakest competency")

        plan['90_days'] += [f"Complete: {c}" for c in complementary] or ["Build a mini-project to reinforce skills"]
        plan['6_12_months'] += [f"Take advanced course: {c}" for c in advanced] or ["Start a specialization/capstone"]

        strengths = CompetencyScore.objects.filter(exam=self.exam, is_strength=True)
        if strengths:
            names = ", ".join(s.competency_name.replace("_", " ").title() for s in strengths)
            plan['6_12_months'].append(f"Leverage strengths ({names}) for internships or projects.")
        return plan

    # ---------------------------------------------------------
    # ALGORITHM DETAILS
    # ---------------------------------------------------------
    def algorithm_details(self):
        return {
            "marks": self.MARKS,
            "max_scores": self.MAX_SCORES,
            "performance_thresholds": {
                "advanced": "≥85%",
                "proficient": "≥70%",
                "developing": "≥50%",
                "emerging": "≥30%",
                "novice": "<30%"
            },
            "strength_rule": "≥75% & top-2",
            "weakness_rule": "<60% & bottom-2",
            "priority_formula": "(75 - score) × weight",
            "weights": self.COMPETENCY_WEIGHTS,
        }

    # ---------------------------------------------------------
    # CALCULATE TOTAL SCORE
    # ---------------------------------------------------------
    def calculate_total_score(self, questions, user_answers):
        competency_scores = {c: 0 for c in self.MARKS}

        for q in questions:
            qid = q['id']
            comp = q.get('competency_type')
            if user_answers.get(str(qid)) == q['correct_answer']:
                competency_scores[comp] += self.MARKS[comp]

        self.save_competency_breakdown(competency_scores)

        total = sum(competency_scores.values())
        total -= self.calculate_violation_deduction()
        total = max(0, total)
        return total

    # ---------------------------------------------------------
    # PROCTORING VIOLATION DEDUCTION
    # ---------------------------------------------------------
    def calculate_violation_deduction(self):
        violations = CheatingEvent.objects.filter(student=self.exam.student)
        severity = 0

        weights = {
            'multiple_persons': 0.30,
            'object_detected': 0.25,
            'audio_detected': 0.15,
            'gaze_detected': 0.10,
        }

        for v in violations:
            severity += weights.get(v.event_type, 0)

        # tab-switch
        first = violations.first()
        if first and hasattr(first, "tab_switch_count"):
            severity += min(first.tab_switch_count * 0.15, 0.75)

        return 2 if severity >= 1.0 else 0

    # ---------------------------------------------------------
    # RANKING & PERCENTILE
    # ---------------------------------------------------------
    def calculate_ranking(self):
        all_exams = Exam.objects.filter(status="completed").order_by("-total_score", "-timestamp")
        total = all_exams.count()

        for rank, exam in enumerate(all_exams, start=1):
            exam.rank = rank
            exam.percentile = ((total - rank) / total) * 100
            exam.save()

        return self.exam.rank, self.exam.percentile
