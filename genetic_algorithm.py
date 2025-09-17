import random
import pandas as pd


# ----------------- FITNESS -----------------

def calculate_fitness(timetable_df, rooms, sections):
    """
    Fitness = negative penalty. 0 means perfect.
    Penalize clashes: room, teacher, section, lab mismatches.
    """
    penalty = 0

    # Room clashes
    room_time_usage = timetable_df.groupby(['day', 'time_slot', 'room_id']).size()
    penalty += (room_time_usage[room_time_usage > 1].sum()) * 100

    # Teacher clashes
    teacher_time_usage = timetable_df.groupby(['day', 'time_slot', 'teacher_id']).size()
    penalty += (teacher_time_usage[teacher_time_usage > 1].sum()) * 100

    # Section clashes
    section_time_usage = timetable_df.groupby(['day', 'time_slot', 'section_id']).size()
    penalty += (section_time_usage[section_time_usage > 1].sum()) * 100

    # Lab mismatch
    lab_courses = {c.course_id for c in timetable_df['course'] if c.reqd_lab}
    lab_rooms = {r.room_id for r in rooms if r.type.lower() == "lab"}
    lab_mismatches = timetable_df[
        timetable_df['course_id'].isin(lab_courses) & 
        ~timetable_df['room_id'].isin(lab_rooms)
    ]
    penalty += len(lab_mismatches) * 50

    return -penalty


# ----------------- INITIAL POPULATION -----------------

def create_individual(courses, teachers, rooms, sections, days, time_slots):
    """Create a random timetable."""
    timetable = []
    for section in sections:
        for course in courses:
            entry = {
                'section': section,
                'section_id': section.section_id,
                'course': course,
                'course_id': course.course_id,
                'teacher': random.choice(teachers),
                'teacher_id': None,
                'room': random.choice(rooms),
                'room_id': None,
                'day': random.choice(days),
                'time_slot': random.choice(time_slots),
            }
            entry['teacher_id'] = entry['teacher'].teacher_id
            entry['room_id'] = entry['room'].room_id
            timetable.append(entry)

    return pd.DataFrame(timetable)


def create_population(size, courses, teachers, rooms, sections, days, time_slots):
    return [create_individual(courses, teachers, rooms, sections, days, time_slots) for _ in range(size)]


# ----------------- SELECTION / CROSSOVER / MUTATION -----------------

def selection(population, fitnesses, num_parents):
    parents = []
    for _ in range(num_parents):
        tournament = random.sample(list(zip(population, fitnesses)), k=5)
        winner = max(tournament, key=lambda x: x[1])
        parents.append(winner[0])
    return parents


def crossover(parent1, parent2):
    if len(parent1) != len(parent2):
        return parent1, parent2

    point = random.randint(1, len(parent1) - 1)
    child1 = pd.concat([parent1.iloc[:point], parent2.iloc[point:]]).reset_index(drop=True)
    child2 = pd.concat([parent2.iloc[:point], parent1.iloc[point:]]).reset_index(drop=True)
    return child1, child2


def mutate(individual, teachers, rooms, days, time_slots, rate=0.05):
    for i in range(len(individual)):
        if random.random() < rate:
            individual.at[i, 'time_slot'] = random.choice(time_slots)
        if random.random() < rate:
            individual.at[i, 'day'] = random.choice(days)
        if random.random() < rate:
            new_room = random.choice(rooms)
            individual.at[i, 'room'] = new_room
            individual.at[i, 'room_id'] = new_room.room_id
    return individual


# ----------------- MAIN GA -----------------

def run_genetic_algorithm(courses, teachers, rooms, sections, days, time_slots,
                          population_size=100, generations=50, mutation_rate=0.05):

    population = create_population(population_size, courses, teachers, rooms, sections, days, time_slots)
    best = None
    best_fitness = -float('inf')

    for g in range(generations):
        fitnesses = [calculate_fitness(ind, rooms, sections) for ind in population]

        current_best = max(fitnesses)
        if current_best > best_fitness:
            best_fitness = current_best
            best = population[fitnesses.index(best_fitness)]
            print(f"Gen {g+1}: Best fitness = {best_fitness}")
            if best_fitness == 0:
                print("✅ Perfect timetable found")
                break

        parents = selection(population, fitnesses, population_size // 2)

        offspring = []
        while len(offspring) < population_size:
            p1, p2 = random.sample(parents, 2)
            c1, c2 = crossover(p1, p2)
            offspring.append(mutate(c1, teachers, rooms, days, time_slots, mutation_rate))
            if len(offspring) < population_size:
                offspring.append(mutate(c2, teachers, rooms, days, time_slots, mutation_rate))

        population = offspring

    return best
