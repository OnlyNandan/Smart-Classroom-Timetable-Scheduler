# genetic_algorithm.py
import random
from collections import defaultdict, Counter
from datetime import date
import json

from init_db import (db, Course, Teacher, Room, StudentGroup, TimetableEntry, TimetableRun,
                     CourseAssignment, Holiday, ManualLock, Substitution, Exam, Attendance, ConstraintWeight)

# GA params (configurable)
POPULATION_SIZE = 50
GENERATIONS = 200
MUTATION_RATE = 0.12

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri"]
SLOTS_PER_DAY = 6

HARD_PENALTY = -1000000
SOFT_PENALTY = -5

# -------------------------
# Helpers
# -------------------------
def room_suits(course, room, group):
    # capacity
    min_cap = course.required_capacity or group.size or 0
    if room.capacity < min_cap:
        return False
    # room type
    if course.required_room_type and room.room_type != course.required_room_type:
        return False
    # features
    required = set(course.get_required_features())
    available = set(room.get_features())
    if not required.issubset(available):
        return False
    return True

def load_master_data():
    courses = Course.query.all()
    teachers = Teacher.query.all()
    rooms = Room.query.all()
    groups = StudentGroup.query.all()
    assignments = CourseAssignment.query.all()
    holidays = {h.date for h in Holiday.query.all()}
    locks = {lock.entry_id for lock in ManualLock.query.all()}
    # Build maps
    lookup = {
        'courses': {c.id: c for c in courses},
        'teachers': {t.id: t for t in teachers},
        'rooms': {r.id: r for r in rooms},
        'groups': {g.id: g for g in groups},
        'assignments_by_course': defaultdict(list),
        'assignments_by_group': defaultdict(list),
        'holidays': holidays,
        'manual_locks': locks
    }
    for a in assignments:
        lookup['assignments_by_course'][a.course_id].append(a.group_id)
        lookup['assignments_by_group'][a.group_id].append(a.course_id)
    return lookup

# -------------------------
# Chromosome representation
# -------------------------
# chromosome: list of dicts with keys:
# course_id, teacher_id, room_id, group_id, day, start_slot, duration
# one entry per (course,group) mapping (so electives with multiple groups produce multiple assignments)

def create_initial_population(lookup):
    population = []
    courses = list(lookup['courses'].values())
    teachers = list(lookup['teachers'].values())
    rooms = list(lookup['rooms'].values())
    # Build (course,group) pairs to schedule
    assignments = []
    for course_id, groups in lookup['assignments_by_course'].items():
        if not groups:
            # if no explicit groups: schedule once on a random group (fallback)
            groups = [random.choice(list(lookup['groups'].keys()))]
        for group_id in groups:
            assignments.append((course_id, group_id))
    for _ in range(POPULATION_SIZE):
        chrom = []
        for (course_id, group_id) in assignments:
            course = lookup['courses'][course_id]
            # choose teacher (prefer assigned)
            teacher_id = course.teacher_id or random.choice(list(lookup['teachers'].keys()))
            # choose room that suits or fallback
            suitable_rooms = [r for r in rooms if room_suits(course, r, lookup['groups'][group_id])]
            room = random.choice(suitable_rooms) if suitable_rooms else random.choice(rooms)
            # day and start slot
            duration = course.duration or 1
            day = random.choice(DAYS)
            start_slot = random.randint(1, max(1, SLOTS_PER_DAY - duration + 1))
            chrom.append({
                "course_id": course_id,
                "group_id": group_id,
                "teacher_id": teacher_id,
                "room_id": room.id,
                "day": day,
                "start_slot": start_slot,
                "duration": duration
            })
        population.append(chrom)
    return population

# -------------------------
# Fitness & Constraints
# -------------------------
def compute_fitness(chrom, lookup):
    score = 0
    # trackers
    teacher_map = set()
    room_map = set()
    group_map = set()
    teacher_day_count = defaultdict(lambda: defaultdict(int))
    teacher_week_count = defaultdict(int)
    # elective balancing: count per course number of groups scheduled early slots (lower start_slot)
    elective_balance_score = 0
    # check holidays - if any day maps to holiday -> huge penalty
    holidays = lookup['holidays']

    for a in chrom:
        course = lookup['courses'][a['course_id']]
        room = lookup['rooms'][a['room_id']]
        group = lookup['groups'][a['group_id']]
        teacher = lookup['teachers'].get(a['teacher_id'])
        duration = a.get('duration', course.duration or 1)
        day = a['day']
        start = int(a['start_slot'])

        # holiday check
        # NOTE: mapping day->date requires a calendar; for now assume holidays are date-level
        # We skip scheduling on holiday by treating day as allowed and assume admin uses calendar to avoid generation on holiday week
        # (Optional: provide date mapping to days)

        # room suitability
        if not room_suits(course, room, group):
            score += HARD_PENALTY

        # contiguous fits
        if start < 1 or (start + duration - 1) > SLOTS_PER_DAY:
            score += HARD_PENALTY

        for s in range(start, start + duration):
            tkey = (a['teacher_id'], day, s)
            rkey = (a['room_id'], day, s)
            gkey = (a['group_id'], day, s)
            if tkey in teacher_map:
                score += HARD_PENALTY
            teacher_map.add(tkey)
            if rkey in room_map:
                score += HARD_PENALTY
            room_map.add(rkey)
            if gkey in group_map:
                score += HARD_PENALTY
            group_map.add(gkey)
            teacher_day_count[a['teacher_id']][day] += 1
            teacher_week_count[a['teacher_id']] += 1

        # elective priority: reward scheduling earlier for high-priority courses
        if course.priority and (start <= 2):
            score += course.priority * 20
        elif course.priority:
            score += course.priority * 2

    # teacher workload enforcement (hard)
    for tid, day_counts in teacher_day_count.items():
        t = lookup['teachers'][tid]
        if t.max_hours_per_day:
            for day, count in day_counts.items():
                if count > t.max_hours_per_day:
                    score += HARD_PENALTY * (count - t.max_hours_per_day)
        if t.max_hours_per_week and teacher_week_count[tid] > t.max_hours_per_week:
            score += HARD_PENALTY * (teacher_week_count[tid] - t.max_hours_per_week)

    # soft: min gap between classes (penalty for adjacent classes if min_gap > 0)
    # gather per teacher per day slots
    teacher_slots = defaultdict(lambda: defaultdict(list))
    for a in chrom:
        dur = a.get('duration', 1)
        for s in range(a['start_slot'], a['start_slot'] + dur):
            teacher_slots[a['teacher_id']][a['day']].append(s)
    for tid, dayslots in teacher_slots.items():
        t = lookup['teachers'][tid]
        if t.min_gap_between_classes and t.min_gap_between_classes > 0:
            for day, slots in dayslots.items():
                ssorted = sorted(slots)
                for i in range(len(ssorted) - 1):
                    gap = ssorted[i+1] - ssorted[i] - 1
                    if gap < (t.min_gap_between_classes):
                        score += SOFT_PENALTY * ((t.min_gap_between_classes) - gap)

    return score

def validate_schedule(chrom, lookup):
    """
    Strict validation before saving. Returns (valid, list_of_violations)
    """
    violations = []
    teacher_map = set()
    room_map = set()
    group_map = set()
    teacher_day_count = defaultdict(lambda: defaultdict(int))
    teacher_week_count = defaultdict(int)

    for a in chrom:
        course = lookup['courses'][a['course_id']]
        room = lookup['rooms'][a['room_id']]
        group = lookup['groups'][a['group_id']]
        teacher = lookup['teachers'].get(a['teacher_id'])
        dur = a.get('duration', course.duration or 1)
        day = a['day']
        start = int(a['start_slot'])
        # room suitability
        if not room_suits(course, room, group):
            violations.append(f"Room {room.name} unsuitable for course {course.code}({course.name}) or group size {group.size}")
        # contiguous
        if start < 1 or (start + dur - 1) > SLOTS_PER_DAY:
            violations.append(f"Course {course.code} assigned out-of-bounds start_slot {start}")
        for s in range(start, start + dur):
            tkey = (a['teacher_id'], day, s)
            rkey = (a['room_id'], day, s)
            gkey = (a['group_id'], day, s)
            if tkey in teacher_map:
                violations.append(f"Teacher {teacher.name} double-booked day {day} slot {s}")
            teacher_map.add(tkey)
            if rkey in room_map:
                violations.append(f"Room {room.name} double-booked day {day} slot {s}")
            room_map.add(rkey)
            if gkey in group_map:
                violations.append(f"Group {group.name} double-booked day {day} slot {s}")
            group_map.add(gkey)
            teacher_day_count[a['teacher_id']][day] += 1
            teacher_week_count[a['teacher_id']] += 1

    for tid, day_counts in teacher_day_count.items():
        t = lookup['teachers'][tid]
        if t.max_hours_per_day:
            for day, count in day_counts.items():
                if count > t.max_hours_per_day:
                    violations.append(f"Teacher {t.name} exceeds max_hours_per_day on {day}: {count} > {t.max_hours_per_day}")
        if t.max_hours_per_week and teacher_week_count[tid] > t.max_hours_per_week:
            violations.append(f"Teacher {t.name} exceeds max_hours_per_week: {teacher_week_count[tid]} > {t.max_hours_per_week}")

    return (len(violations) == 0, violations)

# -------------------------
# GA Operators
# -------------------------
def tournament_selection(pop, fitnesses, k=3):
    chosen = random.sample(range(len(pop)), k)
    best = max(chosen, key=lambda i: fitnesses[i])
    return pop[best]

def crossover(parent1, parent2):
    # single-point crossover
    size = len(parent1)
    if size <= 1:
        return parent1.copy(), parent2.copy()
    pt = random.randint(1, size - 1)
    c1 = parent1[:pt] + parent2[pt:]
    c2 = parent2[:pt] + parent1[pt:]
    return c1, c2

def mutate(chrom, lookup):
    if random.random() > MUTATION_RATE:
        return chrom
    c = [dict(x) for x in chrom]
    idx = random.randrange(len(c))
    gene = c[idx]
    # mutate one of teacher/room/day/start_slot
    choice = random.choice(['teacher', 'room', 'day', 'start'])
    if choice == 'teacher':
        # pick random teacher from lookup
        gene['teacher_id'] = random.choice(list(lookup['teachers'].keys()))
    elif choice == 'room':
        # pick suitable room preferably
        course = lookup['courses'][gene['course_id']]
        group = lookup['groups'][gene['group_id']]
        rooms = list(lookup['rooms'].values())
        suitable = [r for r in rooms if room_suits(course, r, group)]
        gene['room_id'] = random.choice(suitable).id if suitable else random.choice(rooms).id
    elif choice == 'day':
        gene['day'] = random.choice(DAYS)
    else:
        course = lookup['courses'][gene['course_id']]
        dur = course.duration or 1
        gene['start_slot'] = random.randint(1, max(1, SLOTS_PER_DAY - dur + 1))
    return c

# -------------------------
# Run GA and save results
# -------------------------
def run_class_timetable(run_notes=None, created_by=None):
    lookup = load_master_data()
    population = create_initial_population(lookup)
    # evolve
    for gen in range(GENERATIONS):
        fitnesses = [compute_fitness(p, lookup) for p in population]
        newpop = []
        while len(newpop) < POPULATION_SIZE:
            p1 = tournament_selection(population, fitnesses)
            p2 = tournament_selection(population, fitnesses)
            c1, c2 = crossover(p1, p2)
            c1 = mutate(c1, lookup)
            c2 = mutate(c2, lookup)
            newpop.append(c1)
            if len(newpop) < POPULATION_SIZE:
                newpop.append(c2)
        population = newpop
        # optionally track best per generation for debugging

    # final best
    fitnesses = [compute_fitness(p, lookup) for p in population]
    best_idx = max(range(len(population)), key=lambda i: fitnesses[i])
    best = population[best_idx]

    # validate
    valid, violations = validate_schedule(best, lookup)
    if not valid:
        return {'ok': False, 'violations': violations}

    # save run and entries
    run = TimetableRun(created_by=created_by, notes=run_notes)
    db.session.add(run)
    db.session.flush()  # get run.id
    saved = 0
    # clear or keep old runs as history; we save a new run and mark it
    for a in best:
        course = lookup['courses'][a['course_id']]
        teacher = lookup['teachers'][a['teacher_id']]
        room = lookup['rooms'][a['room_id']]
        group = lookup['groups'][a['group_id']]
        te = TimetableEntry(run_id=run.id,
                            day=a['day'],
                            start_slot=a['start_slot'],
                            duration=a.get('duration', course.duration or 1),
                            course_id=a['course_id'],
                            teacher_id=a['teacher_id'],
                            room_id=a['room_id'],
                            group_id=a['group_id'],
                            course_name=f"{course.code} - {course.name}",
                            teacher_name=teacher.name,
                            room_name=room.name,
                            group_name=group.name)
        db.session.add(te)
        saved += 1
    db.session.commit()
    return {'ok': True, 'run_id': run.id, 'saved': saved}

# -------------------------
# Exam scheduling stub (similar approach but stricter: no student overlap across exams)
# -------------------------
def run_exam_scheduler(exam_list):
    # exam_list: list of (course_id, group_id, duration)
    # This function should be implemented with similar GA but stricter conflict checks
    raise NotImplementedError("Exam scheduler not implemented in this stub. Consider CP-SAT/OR-Tools for exams.")

# -------------------------
# Utility: conflict detector for a run_id
# -------------------------
def detect_conflicts_for_run(run_id):
    entries = TimetableEntry.query.filter_by(run_id=run_id).all()
    violations = []
    teacher_map = set()
    room_map = set()
    group_map = set()
    for e in entries:
        for s in range(e.start_slot, e.start_slot + e.duration):
            tkey = (e.teacher_id, e.day, s)
            rkey = (e.room_id, e.day, s)
            gkey = (e.group_id, e.day, s)
            if tkey in teacher_map:
                violations.append(f"Teacher {e.teacher_name} double-booked {e.day} slot {s}")
            teacher_map.add(tkey)
            if rkey in room_map:
                violations.append(f"Room {e.room_name} double-booked {e.day} slot {s}")
            room_map.add(rkey)
            if gkey in group_map:
                violations.append(f"Group {e.group_name} double-booked {e.day} slot {s}")
            group_map.add(gkey)
    return violations
