import random
import pandas as pd
import ollama  # Make sure to install with: pip install ollama
import json

# ----------------- OLLAMA BASED GENERATION -----------------


def serialize_data_for_prompt(courses, teachers, rooms, sections, course_teacher_mappings, days, time_slots):
    """Converts the database objects into a JSON-serializable format for the LLM prompt."""

    # Calculate required slots per course (assuming 1 slot = 1.5 hours)
    # This logic might need adjustment based on actual slot duration
    def get_slots_needed(weekly_hours):
        return round(weekly_hours / 1.5) if weekly_hours > 0 else 0

    data = {
        "courses": [
            {
                "id": c.course_id,
                "name": c.course_name,
                "slots_per_week": get_slots_needed(c.weekly_hours),
                "lab_required": c.reqd_lab
            } for c in courses
        ],
        "teachers": [{"id": t.teacher_id, "name": t.teacher_name} for t in teachers],
        "rooms": [{"id": r.room_id, "type": r.type, "capacity": r.capacity} for r in rooms],
        "sections": [{"id": s.section_id, "students": s.no_of_students} for s in sections],
        "assignments": [
            {
                "course_id": m.course_id,
                "teacher_id": m.teacher_id,
                "section_id": m.sec_id
            } for m in course_teacher_mappings
        ],
        "schedule_options": {
            "days": days,
            "time_slots": time_slots
        }
    }
    return json.dumps(data, indent=2)


def construct_prompt(serialized_data):
    """Constructs the full prompt for the Ollama model."""
    prompt = f"""
You are an expert timetable scheduler. Your task is to create a weekly class schedule based on the provided JSON data.

**Constraints (These are strict rules):**
1.  **No Teacher Clash:** A teacher cannot teach two different classes at the same time.
2.  **No Room Clash:** A room cannot host two different classes at the same time.
3.  **No Section Clash:** A student section cannot attend two different classes at the same time.
4.  **Room Type:** A course that requires a lab (`lab_required: true`) MUST be in a room of type "Lab".
5.  **Correct Assignments:** The teacher for a class must match the assignment in the `assignments` list for that course and section.
6.  **Fulfill Schedule:** Every course assigned to a section must be scheduled for its required number of `slots_per_week`.

**Output Format:**
Your output MUST be a valid JSON array of objects, where each object represents one scheduled class.
Each object must have these keys: "day", "time_slot", "course_id", "teacher_id", "room_id", "section_id".
Do not add any text, explanations, or markdown formatting before or after the JSON array.

**Input Data:**
{serialized_data}

Now, generate the complete and valid timetable as a single JSON array.
"""
    return prompt


def run_ollama_generation(courses, teachers, rooms, sections, course_teacher_mappings, days, time_slots, model='mixtral:8x7b'):
    """
    Generates a timetable using an Ollama model.
    """
    print(f"Serializing data for Ollama model: {model}...")
    serialized_data = serialize_data_for_prompt(courses, teachers, rooms, sections, course_teacher_mappings, days, time_slots)

    print("Constructing prompt...")
    prompt = construct_prompt(serialized_data)

    print(f"Sending request to Ollama model ({model})... This may take a moment.")

    try:
        response = ollama.chat(
            model=model,
            messages=[{'role': 'user', 'content': prompt}],
            options={'temperature': 0.2}  # Lower temperature for more deterministic output
        )

        response_content = response['message']['content']

        # Clean up the response to ensure it's valid JSON
        # LLMs sometimes wrap the JSON in markdown backticks
        if response_content.strip().startswith('```json'):
            response_content = response_content.strip()[7:-3].strip()

        print("Parsing Ollama response...")
        timetable_json = json.loads(response_content)

        # Convert to DataFrame
        timetable_df = pd.DataFrame(timetable_json)

        print(f"Successfully generated timetable with {len(timetable_df)} entries.")
        return timetable_df

    except Exception as e:
        print(f"An error occurred while communicating with Ollama or parsing the response: {e}")
        # Return an empty DataFrame on failure
        return pd.DataFrame()


# ----------------- ORIGINAL GENETIC ALGORITHM (for reference) -----------------

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
