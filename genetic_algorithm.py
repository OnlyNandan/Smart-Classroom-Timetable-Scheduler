import random
import pandas as pd

# --- Fitness Function and Constraints ---

def calculate_fitness(timetable_df, rooms, groups):
    """
    Calculates the fitness of a timetable. The higher the fitness, the better.
    A score of 0 means a perfect timetable with no hard constraint violations.
    We use a penalty system: start with a high score and subtract for each violation.
    """
    penalty = 0
    
    # Hard Constraints (must be satisfied)
    
    # 1. One class per room at any given time
    room_time_usage = timetable_df.groupby(['day', 'time_slot', 'room_id']).size()
    penalty += (room_time_usage[room_time_usage > 1].sum() - room_time_usage[room_time_usage > 1].count()) * 100

    # 2. One class per teacher at any given time
    teacher_time_usage = timetable_df.groupby(['day', 'time_slot', 'teacher_id']).size()
    penalty += (teacher_time_usage[teacher_time_usage > 1].sum() - teacher_time_usage[teacher_time_usage > 1].count()) * 100

    # 3. One class for a student group at any given time
    group_time_usage = timetable_df.groupby(['day', 'time_slot', 'group_id']).size()
    penalty += (group_time_usage[group_time_usage > 1].sum() - group_time_usage[group_time_usage > 1].count()) * 100

    # 4. Room capacity must be sufficient for the student group (simplified assumption)
    # In a real scenario, group size would be a DB field. Here we assume a proxy.
    # This check is illustrative as we don't have group sizes.
    
    # 5. Lab courses must be in a lab room
    lab_courses = {c.id for c in timetable_df['course'].unique() if c.lab_required}
    lab_rooms = {r.id for r in rooms if r.is_lab}
    
    lab_mismatches = timetable_df[timetable_df['course_id'].isin(lab_courses) & ~timetable_df['room_id'].isin(lab_rooms)]
    penalty += len(lab_mismatches) * 50

    return -penalty # Return negative penalty, so higher is better (closer to 0)


# --- Genetic Algorithm Components ---

def create_individual(courses, teachers, rooms, groups, days, time_slots):
    """
    Creates a single random timetable (an individual chromosome).
    Each class for each group is assigned a random valid slot, teacher, and room.
    """
    timetable = []
    # Simplified: Assume each group takes each course once.
    for group in groups:
        for course in courses:
            entry = {
                'group': group,
                'group_id': group.id,
                'course': course,
                'course_id': course.id,
                'teacher': random.choice(teachers),
                'teacher_id': 0, # Placeholder
                'room': random.choice(rooms),
                'room_id': 0, # Placeholder
                'day': random.choice(days),
                'time_slot': random.choice(time_slots),
            }
            entry['teacher_id'] = entry['teacher'].id
            entry['room_id'] = entry['room'].id
            timetable.append(entry)

    return pd.DataFrame(timetable)

def create_population(size, courses, teachers, rooms, groups, days, time_slots):
    """Creates an initial population of random timetables."""
    return [create_individual(courses, teachers, rooms, groups, days, time_slots) for _ in range(size)]

def selection(population, fitnesses, num_parents):
    """Selects the best individuals from the population to be parents."""
    parents = []
    # Using tournament selection
    for _ in range(num_parents):
        tournament = random.sample(list(zip(population, fitnesses)), k=5)
        winner = max(tournament, key=lambda x: x[1])
        parents.append(winner[0])
    return parents

def crossover(parent1, parent2):
    """
    Performs crossover between two parent timetables.
    A random crossover point is chosen, and the parts are swapped.
    """
    if len(parent1) != len(parent2):
        return parent1, parent2 # Should not happen if data is consistent
    
    crossover_point = random.randint(1, len(parent1) - 1)
    
    child1 = pd.concat([parent1.iloc[:crossover_point], parent2.iloc[crossover_point:]]).reset_index(drop=True)
    child2 = pd.concat([parent2.iloc[:crossover_point], parent1.iloc[crossover_point:]]).reset_index(drop=True)
    
    return child1, child2

def mutate(individual, teachers, rooms, days, time_slots, mutation_rate=0.05):
    """
    Performs mutation on an individual timetable.
    A small chance to randomly change an entry's time, room, or teacher.
    """
    for i in range(len(individual)):
        if random.random() < mutation_rate:
            # Change time slot
            individual.at[i, 'time_slot'] = random.choice(time_slots)
        if random.random() < mutation_rate:
            # Change room
            new_room = random.choice(rooms)
            individual.at[i, 'room'] = new_room
            individual.at[i, 'room_id'] = new_room.id
        # We can add more mutations, e.g., for teacher
    return individual


# --- Main GA Runner ---

def run_genetic_algorithm(courses, teachers, rooms, groups, days, time_slots, population_size=100, generations=50, mutation_rate=0.05):
    """
    The main function to run the genetic algorithm.
    """
    print("GA: Creating initial population...")
    population = create_population(population_size, courses, teachers, rooms, groups, days, time_slots)
    
    best_timetable = None
    best_fitness = -float('inf')

    for gen in range(generations):
        print(f"GA: Generation {gen + 1}/{generations}...")
        
        # 1. Calculate fitness for each individual
        fitnesses = [calculate_fitness(ind, rooms, groups) for ind in population]

        # 2. Find the best individual in this generation
        current_best_fitness = max(fitnesses)
        if current_best_fitness > best_fitness:
            best_fitness = current_best_fitness
            best_timetable = population[fitnesses.index(best_fitness)]
            print(f"GA: New best fitness found: {best_fitness}")
            # If a perfect timetable is found, stop early
            if best_fitness == 0:
                print("GA: Perfect timetable found!")
                break
        
        # 3. Selection
        num_parents = population_size // 2
        parents = selection(population, fitnesses, num_parents)
        
        # 4. Crossover and Mutation to create the next generation
        offspring = []
        while len(offspring) < population_size:
            p1, p2 = random.sample(parents, 2)
            c1, c2 = crossover(p1, p2)
            offspring.append(mutate(c1, teachers, rooms, days, time_slots, mutation_rate))
            if len(offspring) < population_size:
                offspring.append(mutate(c2, teachers, rooms, days, time_slots, mutation_rate))
                
        population = offspring

    print(f"GA: Finished. Best fitness score: {best_fitness}")
    return best_timetable
