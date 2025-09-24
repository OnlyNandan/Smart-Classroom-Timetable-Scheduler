"""
Advanced Timetable Generator using Hybrid Algorithm Approach
Combines Greedy + Backtracking, Genetic Algorithm, and Constraint Satisfaction
"""

import random
import copy
import time
from typing import List, Dict, Tuple, Set, Optional
from dataclasses import dataclass
from collections import defaultdict
import multiprocessing as mp
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor


@dataclass
class TimeSlot:
    """Represents a time slot in the timetable"""
    day: str
    period: int
    start_time: str
    end_time: str
    
    def __hash__(self):
        return hash((self.day, self.period))
    
    def __eq__(self, other):
        return self.day == other.day and self.period == other.period


@dataclass
class Activity:
    """Represents a class/activity to be scheduled"""
    id: str
    section_id: int
    teacher_id: int
    subject_id: Optional[int]
    course_id: Optional[int]
    room_id: int
    duration: int = 1  # periods
    priority: int = 1  # 1-5, higher = more constrained
    constraints: List[str] = None
    
    def __post_init__(self):
        if self.constraints is None:
            self.constraints = []


@dataclass
class ConstraintViolation:
    """Represents a constraint violation"""
    type: str  # 'hard' or 'soft'
    description: str
    penalty: float
    activity_ids: List[str]


class ConstraintManager:
    """Manages hard and soft constraints"""
    
    def __init__(self):
        self.hard_constraints = {
            'no_teacher_double_booking': 1000.0,
            'no_room_double_booking': 1000.0,
            'no_section_double_booking': 1000.0,
            'teacher_subject_match': 1000.0,
            'room_capacity': 1000.0
        }
        
        self.soft_constraints = {
            'morning_preference': 10.0,
            'workload_balance': 5.0,
            'schedule_continuity': 8.0,
            'lab_optimization': 15.0,
            'teacher_preference': 3.0
        }
    
    def validate_hard_constraints(self, schedule: Dict[str, TimeSlot]) -> List[ConstraintViolation]:
        """Validate hard constraints - must be 100% satisfied"""
        violations = []
        
        # Group activities by time slot
        time_slot_activities = defaultdict(list)
        for activity_id, time_slot in schedule.items():
            time_slot_activities[time_slot].append(activity_id)
        
        # Check for conflicts
        for time_slot, activities in time_slot_activities.items():
            if len(activities) > 1:
                # Check teacher conflicts
                teachers = [self.get_teacher_id(activity_id) for activity_id in activities]
                if len(teachers) != len(set(teachers)):
                    violations.append(ConstraintViolation(
                        'hard', 'Teacher double-booking', 
                        self.hard_constraints['no_teacher_double_booking'], activities
                    ))
                
                # Check room conflicts
                rooms = [self.get_room_id(activity_id) for activity_id in activities]
                if len(rooms) != len(set(rooms)):
                    violations.append(ConstraintViolation(
                        'hard', 'Room double-booking',
                        self.hard_constraints['no_room_double_booking'], activities
                    ))
                
                # Check section conflicts
                sections = [self.get_section_id(activity_id) for activity_id in activities]
                if len(sections) != len(set(sections)):
                    violations.append(ConstraintViolation(
                        'hard', 'Section double-booking',
                        self.hard_constraints['no_section_double_booking'], activities
                    ))
        
        return violations
    
    def evaluate_soft_constraints(self, schedule: Dict[str, TimeSlot]) -> float:
        """Evaluate soft constraints - optimization objectives"""
        score = 0.0
        
        # Morning preference for difficult subjects
        score += self.morning_preference_score(schedule)
        
        # Teacher workload balance
        score += self.workload_balance_score(schedule)
        
        # Schedule continuity (minimize gaps)
        score += self.schedule_continuity_score(schedule)
        
        # Lab session optimization
        score += self.lab_optimization_score(schedule)
        
        # Teacher preferences
        score += self.teacher_preference_score(schedule)
        
        return score
    
    def morning_preference_score(self, schedule: Dict[str, TimeSlot]) -> float:
        """Prefer morning slots for difficult subjects"""
        score = 0.0
        for activity_id, time_slot in schedule.items():
            if time_slot.period <= 3:  # Morning periods
                difficulty = self.get_subject_difficulty(activity_id)
                score += difficulty * self.soft_constraints['morning_preference']
        return score
    
    def workload_balance_score(self, schedule: Dict[str, TimeSlot]) -> float:
        """Balance teacher workload across days"""
        teacher_daily_load = defaultdict(lambda: defaultdict(int))
        
        for activity_id, time_slot in schedule.items():
            teacher_id = self.get_teacher_id(activity_id)
            teacher_daily_load[teacher_id][time_slot.day] += 1
        
        # Calculate variance in daily load
        total_variance = 0.0
        for teacher_id, daily_loads in teacher_daily_load.items():
            loads = list(daily_loads.values())
            if len(loads) > 1:
                mean_load = sum(loads) / len(loads)
                variance = sum((load - mean_load) ** 2 for load in loads) / len(loads)
                total_variance += variance
        
        return -total_variance * self.soft_constraints['workload_balance']
    
    def schedule_continuity_score(self, schedule: Dict[str, TimeSlot]) -> float:
        """Minimize gaps in student schedules"""
        section_schedules = defaultdict(list)
        
        for activity_id, time_slot in schedule.items():
            section_id = self.get_section_id(activity_id)
            section_schedules[section_id].append(time_slot.period)
        
        continuity_score = 0.0
        for section_id, periods in section_schedules.items():
            periods.sort()
            gaps = 0
            for i in range(len(periods) - 1):
                if periods[i+1] - periods[i] > 1:
                    gaps += periods[i+1] - periods[i] - 1
            continuity_score -= gaps * self.soft_constraints['schedule_continuity']
        
        return continuity_score
    
    def lab_optimization_score(self, schedule: Dict[str, TimeSlot]) -> float:
        """Optimize lab sessions for consecutive periods"""
        score = 0.0
        lab_activities = [aid for aid in schedule.keys() if self.is_lab_activity(aid)]
        
        for activity_id in lab_activities:
            time_slot = schedule[activity_id]
            # Check if next period is also a lab for same section
            next_period = TimeSlot(time_slot.day, time_slot.period + 1, "", "")
            if next_period in schedule.values():
                score += self.soft_constraints['lab_optimization']
        
        return score
    
    def teacher_preference_score(self, schedule: Dict[str, TimeSlot]) -> float:
        """Respect teacher time preferences"""
        score = 0.0
        for activity_id, time_slot in schedule.items():
            teacher_id = self.get_teacher_id(activity_id)
            if self.teacher_prefers_time(teacher_id, time_slot):
                score += self.soft_constraints['teacher_preference']
        return score
    
    # Helper methods (to be implemented based on your data model)
    def get_teacher_id(self, activity_id: str) -> int:
        # Extract teacher ID from activity
        pass
    
    def get_room_id(self, activity_id: str) -> int:
        # Extract room ID from activity
        pass
    
    def get_section_id(self, activity_id: str) -> int:
        # Extract section ID from activity
        pass
    
    def get_subject_difficulty(self, activity_id: str) -> float:
        # Return difficulty level 0-1
        return random.random()
    
    def is_lab_activity(self, activity_id: str) -> bool:
        # Check if activity is a lab
        return False
    
    def teacher_prefers_time(self, teacher_id: int, time_slot: TimeSlot) -> bool:
        # Check if teacher prefers this time slot
        return True


class GeneticOperators:
    """Genetic Algorithm operators for timetable optimization"""
    
    def __init__(self, constraint_manager: ConstraintManager):
        self.constraint_manager = constraint_manager
    
    def crossover(self, parent1: Dict[str, TimeSlot], parent2: Dict[str, TimeSlot]) -> Dict[str, TimeSlot]:
        """Order-preserving crossover for timetables"""
        child = {}
        activities = list(parent1.keys())
        
        # Random crossover point
        crossover_point = random.randint(0, len(activities))
        
        # Copy first part from parent1
        for i in range(crossover_point):
            activity_id = activities[i]
            if self.can_assign(activity_id, parent1[activity_id], child):
                child[activity_id] = parent1[activity_id]
        
        # Fill remaining from parent2, resolving conflicts
        for activity_id in activities[crossover_point:]:
            if activity_id not in child:
                best_slot = self.find_best_available_slot(activity_id, child, parent2)
                if best_slot:
                    child[activity_id] = best_slot
        
        return child
    
    def mutate(self, individual: Dict[str, TimeSlot], mutation_rate: float = 0.05) -> Dict[str, TimeSlot]:
        """Multiple mutation strategies"""
        mutated = individual.copy()
        
        for activity_id in individual:
            if random.random() < mutation_rate:
                mutation_type = random.choice(['swap', 'move', 'exchange'])
                
                if mutation_type == 'swap':
                    # Swap two activities
                    other_activity = random.choice(list(individual.keys()))
                    if other_activity != activity_id:
                        mutated[activity_id], mutated[other_activity] = \
                            mutated[other_activity], mutated[activity_id]
                
                elif mutation_type == 'move':
                    # Move to different time slot
                    new_slot = self.get_random_valid_slot(activity_id, mutated)
                    if new_slot:
                        mutated[activity_id] = new_slot
                
                elif mutation_type == 'exchange':
                    # Exchange with compatible activity
                    compatible = self.find_compatible_activities(activity_id, mutated)
                    if compatible:
                        target = random.choice(compatible)
                        mutated[activity_id], mutated[target] = \
                            mutated[target], mutated[activity_id]
        
        return mutated
    
    def can_assign(self, activity_id: str, time_slot: TimeSlot, schedule: Dict[str, TimeSlot]) -> bool:
        """Check if activity can be assigned to time slot without conflicts"""
        # Check for conflicts with existing assignments
        for existing_id, existing_slot in schedule.items():
            if existing_slot == time_slot:
                # Check if same teacher, room, or section
                if (self.get_teacher_id(activity_id) == self.get_teacher_id(existing_id) or
                    self.get_room_id(activity_id) == self.get_room_id(existing_id) or
                    self.get_section_id(activity_id) == self.get_section_id(existing_id)):
                    return False
        return True
    
    def find_best_available_slot(self, activity_id: str, current_schedule: Dict[str, TimeSlot], 
                                reference_schedule: Dict[str, TimeSlot]) -> Optional[TimeSlot]:
        """Find best available slot for activity"""
        if activity_id in reference_schedule:
            reference_slot = reference_schedule[activity_id]
            if self.can_assign(activity_id, reference_slot, current_schedule):
                return reference_slot
        
        # Try random valid slots
        for _ in range(10):
            slot = self.get_random_valid_slot(activity_id, current_schedule)
            if slot:
                return slot
        
        return None
    
    def get_random_valid_slot(self, activity_id: str, schedule: Dict[str, TimeSlot]) -> Optional[TimeSlot]:
        """Get a random valid time slot for activity"""
        # This would generate valid time slots based on your constraints
        # For now, return a random slot
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
        periods = list(range(1, 9))
        
        for _ in range(20):  # Try up to 20 random slots
            day = random.choice(days)
            period = random.choice(periods)
            slot = TimeSlot(day, period, "", "")
            
            if self.can_assign(activity_id, slot, schedule):
                return slot
        
        return None
    
    def find_compatible_activities(self, activity_id: str, schedule: Dict[str, TimeSlot]) -> List[str]:
        """Find activities that can be exchanged with given activity"""
        compatible = []
        for other_id in schedule.keys():
            if other_id != activity_id:
                # Check if they can be exchanged
                if self.can_exchange(activity_id, other_id, schedule):
                    compatible.append(other_id)
        return compatible
    
    def can_exchange(self, activity1_id: str, activity2_id: str, schedule: Dict[str, TimeSlot]) -> bool:
        """Check if two activities can be exchanged"""
        slot1 = schedule[activity1_id]
        slot2 = schedule[activity2_id]
        
        # Create temporary schedule with exchanged slots
        temp_schedule = schedule.copy()
        temp_schedule[activity1_id] = slot2
        temp_schedule[activity2_id] = slot1
        
        # Check if this creates conflicts
        return (self.can_assign(activity1_id, slot2, temp_schedule) and
                self.can_assign(activity2_id, slot1, temp_schedule))
    
    def get_teacher_id(self, activity_id: str) -> int:
        # Extract teacher ID from activity
        return int(activity_id.split('_')[1])
    
    def get_room_id(self, activity_id: str) -> int:
        # Extract room ID from activity
        return int(activity_id.split('_')[2])
    
    def get_section_id(self, activity_id: str) -> int:
        # Extract section ID from activity
        return int(activity_id.split('_')[0])


class TimetableGenerator:
    """Main timetable generator using hybrid approach"""
    
    def __init__(self, sections, teachers, classrooms, subjects_or_courses, settings, app_mode='college'):
        self.sections = sections
        self.teachers = teachers
        self.classrooms = classrooms
        self.subjects_or_courses = subjects_or_courses
        self.settings = settings
        self.app_mode = app_mode
        
        self.constraint_manager = ConstraintManager()
        self.genetic_operators = GeneticOperators(self.constraint_manager)
        
        # GA parameters (adaptive based on problem size)
        self.adaptive_ga_parameters()
        
        # Performance optimization
        self.constraint_cache = {}
        self.fitness_cache = {}
    
    def adaptive_ga_parameters(self):
        """Set GA parameters based on problem size and complexity"""
        total_sections = len(self.sections)
        total_teachers = len(self.teachers)
        total_rooms = len(self.classrooms)
        total_subjects = len(self.subjects_or_courses)
        
        # Calculate problem complexity
        complexity = total_sections * total_teachers * total_rooms * total_subjects
        
        print(f"🧮 Problem complexity: {complexity:,}")
        
        # Adaptive population size (more complex = larger population)
        if complexity < 10000:  # Small problem
            self.population_size = 50
            self.generations = 30
            self.mutation_rate = 0.1
        elif complexity < 100000:  # Medium problem
            self.population_size = 100
            self.generations = 50
            self.mutation_rate = 0.05
        else:  # Large problem
            self.population_size = 200
            self.generations = 100
            self.mutation_rate = 0.03
        
        # Adaptive crossover rate
        self.crossover_rate = 0.8
        
        # Elite size (10% of population)
        self.elite_size = max(5, self.population_size // 10)
        
        print(f"🎯 GA Parameters:")
        print(f"   Population: {self.population_size}")
        print(f"   Generations: {self.generations}")
        print(f"   Mutation rate: {self.mutation_rate}")
        print(f"   Crossover rate: {self.crossover_rate}")
        print(f"   Elite size: {self.elite_size}")
    
    def generate(self) -> List[Dict]:
        """Main generation pipeline using hybrid approach"""
        print("🚀 Starting hybrid timetable generation...")
        
        # Phase 1: Quick feasible solution with Greedy + Backtracking
        print("📋 Phase 1: Generating initial solution with Greedy + Backtracking...")
        initial_solution = self.greedy_assignment()
        
        if not initial_solution:
            print("❌ Failed to generate initial solution")
            return []
        
        print(f"✅ Initial solution: {len(initial_solution)} activities scheduled")
        
        # Phase 2: Optimize with Genetic Algorithm
        print("🧬 Phase 2: Optimizing with Genetic Algorithm...")
        optimized_solution = self.genetic_algorithm_optimization(initial_solution)
        
        print(f"✅ GA optimization complete: {len(optimized_solution)} activities")
        
        # Phase 3: Local improvements with Constraint Satisfaction
        print("🔧 Phase 3: Final constraint satisfaction refinement...")
        final_solution = self.constraint_satisfaction_refinement(optimized_solution)
        
        print(f"🎉 Final solution: {len(final_solution)} activities scheduled")
        
        return self.convert_to_timetable_entries(final_solution)
    
    def greedy_assignment(self) -> Dict[str, TimeSlot]:
        """Fast initial assignment using greedy + backtracking"""
        print("🔍 Building initial schedule with greedy algorithm...")
        
        # Create activities from sections
        activities = self.create_activities()
        print(f"📚 Created {len(activities)} activities for {len(self.sections)} sections")
        
        if not activities:
            print("❌ No activities created")
            return {}
        
        # Sort by difficulty (most constrained first)
        activities.sort(key=lambda a: a.priority, reverse=True)
        
        schedule = {}
        available_slots = self.get_available_slots()
        print(f"⏰ Available time slots: {len(available_slots)}")
        
        # Track resource usage
        teacher_schedule = defaultdict(set)  # {teacher_id: {time_slots}}
        room_schedule = defaultdict(set)     # {room_id: {time_slots}}
        section_schedule = defaultdict(set)  # {section_id: {time_slots}}
        
        assigned_count = 0
        failed_count = 0
        
        for activity in activities:
            assigned = False
            
            # Try each available slot
            for time_slot in available_slots:
                if self.can_assign_activity(activity, time_slot, teacher_schedule, room_schedule, section_schedule):
                    schedule[activity.id] = time_slot
                    
                    # Update resource tracking
                    teacher_schedule[activity.teacher_id].add(time_slot)
                    room_schedule[activity.room_id].add(time_slot)
                    section_schedule[activity.section_id].add(time_slot)
                    
                    assigned = True
                    assigned_count += 1
                    break
            
            if not assigned:
                failed_count += 1
                print(f"⚠️ Could not assign activity {activity.id} (section {activity.section_id}, teacher {activity.teacher_id})")
        
        print(f"✅ Greedy assignment complete: {assigned_count} assigned, {failed_count} failed")
        
        if assigned_count == 0:
            print("❌ No activities could be assigned with current constraints")
            print("🔄 Attempting fallback: reducing constraints...")
            
            # Fallback: try with relaxed constraints
            return self.fallback_assignment(activities, available_slots)
        
        return schedule
    
    def fallback_assignment(self, activities, available_slots):
        """Fallback assignment with relaxed constraints"""
        print("🆘 Using fallback assignment strategy...")
        
        schedule = {}
        teacher_schedule = defaultdict(set)
        room_schedule = defaultdict(set)
        section_schedule = defaultdict(set)
        
        assigned_count = 0
        
        # Try to assign at least one activity per section
        for activity in activities:
            if assigned_count >= len(self.sections):  # At least one per section
                break
                
            for time_slot in available_slots:
                # Relaxed constraints: only check section conflict
                if time_slot not in section_schedule[activity.section_id]:
                    schedule[activity.id] = time_slot
                    
                    # Update tracking
                    teacher_schedule[activity.teacher_id].add(time_slot)
                    room_schedule[activity.room_id].add(time_slot)
                    section_schedule[activity.section_id].add(time_slot)
                    
                    assigned_count += 1
                    break
        
        print(f"🆘 Fallback assigned {assigned_count} activities")
        return schedule
    
    def can_assign_activity(self, activity, time_slot, teacher_schedule, room_schedule, section_schedule) -> bool:
        """Check if activity can be assigned to time slot without conflicts"""
        # Check teacher conflict
        if time_slot in teacher_schedule[activity.teacher_id]:
            return False
        
        # Check room conflict
        if time_slot in room_schedule[activity.room_id]:
            return False
        
        # Check section conflict
        if time_slot in section_schedule[activity.section_id]:
            return False
        
        return True
    
    def backtrack_and_reassign(self, activity, schedule, backtrack_stack) -> bool:
        """Backtrack and reassign activities to make room"""
        # Simple backtracking - try to move conflicting activities
        for time_slot in self.get_available_slots():
            conflicts = self.find_conflicts(activity, time_slot, schedule)
            
            if not conflicts:
                schedule[activity.id] = time_slot
                return True
            
            # Try to move conflicting activities
            if self.move_conflicting_activities(conflicts, schedule):
                schedule[activity.id] = time_slot
                return True
        
        return False
    
    def find_conflicts(self, activity, time_slot, schedule):
        """Find activities that conflict with the given assignment"""
        conflicts = []
        for existing_id, existing_slot in schedule.items():
            if existing_slot == time_slot:
                # Check if same teacher, room, or section
                if (self.get_teacher_id(activity.id) == self.get_teacher_id(existing_id) or
                    self.get_room_id(activity.id) == self.get_room_id(existing_id) or
                    self.get_section_id(activity.id) == self.get_section_id(existing_id)):
                    conflicts.append(existing_id)
        return conflicts
    
    def move_conflicting_activities(self, conflicts, schedule) -> bool:
        """Try to move conflicting activities to other slots"""
        for conflict_id in conflicts:
            # Try to find alternative slot for conflicting activity
            for time_slot in self.get_available_slots():
                if (time_slot != schedule[conflict_id] and 
                    self.genetic_operators.can_assign(conflict_id, time_slot, schedule)):
                    schedule[conflict_id] = time_slot
                    return True
        return False
    
    def genetic_algorithm_optimization(self, initial_schedule: Dict[str, TimeSlot]) -> Dict[str, TimeSlot]:
        """Optimize using Genetic Algorithm"""
        print(f"🧬 Starting GA with population size {self.population_size}...")
        
        # Initialize population with variations of initial solution
        population = self.create_initial_population(initial_schedule)
        
        best_fitness = float('-inf')
        best_individual = None
        
        for generation in range(self.generations):
            # Evaluate fitness
            fitness_scores = self.evaluate_population_fitness(population)
            
            # Track best individual
            current_best = max(fitness_scores)
            if current_best > best_fitness:
                best_fitness = current_best
                best_individual = population[fitness_scores.index(current_best)]
            
            print(f"Generation {generation + 1}: Best fitness = {best_fitness:.2f}")
            
            # Early termination if optimal solution found
            if best_fitness >= 0.95:  # 95% of optimal
                print("🎯 Optimal solution found, terminating early")
                break
            
            # Selection, crossover, and mutation
            parents = self.tournament_selection(population, fitness_scores)
            offspring = self.create_offspring(parents)
            population = self.elitist_replacement(population, offspring, fitness_scores)
        
        return best_individual or initial_schedule
    
    def create_initial_population(self, initial_schedule: Dict[str, TimeSlot]) -> List[Dict[str, TimeSlot]]:
        """Create initial population with variations of the initial solution"""
        population = []
        
        # Add original solution
        population.append(initial_schedule.copy())
        
        # Create variations
        for _ in range(self.population_size - 1):
            individual = initial_schedule.copy()
            
            # Apply random mutations
            for _ in range(random.randint(1, 5)):
                individual = self.genetic_operators.mutate(individual, 0.1)
            
            population.append(individual)
        
        return population
    
    def evaluate_population_fitness(self, population: List[Dict[str, TimeSlot]]) -> List[float]:
        """Evaluate fitness for entire population"""
        fitness_scores = []
        
        for individual in population:
            # Check hard constraints
            violations = self.constraint_manager.validate_hard_constraints(individual)
            hard_penalty = sum(v.penalty for v in violations)
            
            if hard_penalty > 0:
                # Invalid solution
                fitness_scores.append(-hard_penalty)
            else:
                # Valid solution - evaluate soft constraints
                soft_score = self.constraint_manager.evaluate_soft_constraints(individual)
                fitness_scores.append(soft_score)
        
        return fitness_scores
    
    def tournament_selection(self, population: List[Dict[str, TimeSlot]], 
                           fitness_scores: List[float], tournament_size: int = 3) -> List[Dict[str, TimeSlot]]:
        """Tournament selection for parents"""
        parents = []
        
        for _ in range(len(population)):
            # Select tournament participants
            tournament_indices = random.sample(range(len(population)), tournament_size)
            tournament_fitness = [fitness_scores[i] for i in tournament_indices]
            
            # Select winner
            winner_index = tournament_indices[tournament_fitness.index(max(tournament_fitness))]
            parents.append(population[winner_index])
        
        return parents
    
    def create_offspring(self, parents: List[Dict[str, TimeSlot]]) -> List[Dict[str, TimeSlot]]:
        """Create offspring through crossover and mutation"""
        offspring = []
        
        for i in range(0, len(parents), 2):
            parent1 = parents[i]
            parent2 = parents[i + 1] if i + 1 < len(parents) else parents[0]
            
            # Crossover
            if random.random() < self.crossover_rate:
                child1 = self.genetic_operators.crossover(parent1, parent2)
                child2 = self.genetic_operators.crossover(parent2, parent1)
            else:
                child1 = parent1.copy()
                child2 = parent2.copy()
            
            # Mutation
            child1 = self.genetic_operators.mutate(child1, self.mutation_rate)
            child2 = self.genetic_operators.mutate(child2, self.mutation_rate)
            
            offspring.extend([child1, child2])
        
        return offspring
    
    def elitist_replacement(self, population: List[Dict[str, TimeSlot]], 
                          offspring: List[Dict[str, TimeSlot]], 
                          fitness_scores: List[float]) -> List[Dict[str, TimeSlot]]:
        """Replace population keeping elite individuals"""
        # Sort by fitness
        sorted_population = sorted(zip(population, fitness_scores), key=lambda x: x[1], reverse=True)
        
        # Keep elite individuals
        new_population = [individual for individual, _ in sorted_population[:self.elite_size]]
        
        # Add best offspring
        offspring_fitness = self.evaluate_population_fitness(offspring)
        sorted_offspring = sorted(zip(offspring, offspring_fitness), key=lambda x: x[1], reverse=True)
        
        # Fill remaining slots with best offspring
        remaining_slots = self.population_size - self.elite_size
        for individual, _ in sorted_offspring[:remaining_slots]:
            new_population.append(individual)
        
        return new_population
    
    def constraint_satisfaction_refinement(self, schedule: Dict[str, TimeSlot]) -> Dict[str, TimeSlot]:
        """Final refinement using constraint satisfaction"""
        print("🔧 Applying constraint satisfaction refinement...")
        
        refined_schedule = schedule.copy()
        
        # Try to improve soft constraints
        for _ in range(10):  # 10 improvement attempts
            improved = False
            
            for activity_id in refined_schedule.keys():
                current_slot = refined_schedule[activity_id]
                best_slot = self.find_best_slot_for_activity(activity_id, refined_schedule)
                
                if best_slot != current_slot:
                    refined_schedule[activity_id] = best_slot
                    improved = True
            
            if not improved:
                break
        
        return refined_schedule
    
    def find_best_slot_for_activity(self, activity_id: str, schedule: Dict[str, TimeSlot]) -> TimeSlot:
        """Find the best time slot for an activity considering soft constraints"""
        current_slot = schedule[activity_id]
        best_slot = current_slot
        best_score = self.constraint_manager.evaluate_soft_constraints(schedule)
        
        # Try different slots
        for time_slot in self.get_available_slots():
            if time_slot != current_slot and self.genetic_operators.can_assign(activity_id, time_slot, schedule):
                # Create temporary schedule
                temp_schedule = schedule.copy()
                temp_schedule[activity_id] = time_slot
                
                # Evaluate score
                score = self.constraint_manager.evaluate_soft_constraints(temp_schedule)
                
                if score > best_score:
                    best_score = score
                    best_slot = time_slot
        
        return best_slot
    
    def create_activities(self) -> List[Activity]:
        """Create activities dynamically based on available resources"""
        print("🧮 Calculating optimal activity distribution...")
        
        # Calculate resource constraints
        total_time_slots = len(self.get_available_slots())
        total_teachers = len(self.teachers)
        total_rooms = len(self.classrooms)
        total_sections = len(self.sections)
        
        print(f"📊 Resource Analysis:")
        print(f"   ⏰ Time slots: {total_time_slots}")
        print(f"   👨‍🏫 Teachers: {total_teachers}")
        print(f"   🏫 Rooms: {total_rooms}")
        print(f"   📚 Sections: {total_sections}")
        
        # Calculate maximum possible activities
        max_activities_by_time = total_time_slots
        max_activities_by_teachers = total_teachers * total_time_slots
        max_activities_by_rooms = total_rooms * total_time_slots
        max_activities_by_sections = total_sections * total_time_slots
        
        # The bottleneck is the most limiting resource
        max_possible_activities = min(max_activities_by_time, max_activities_by_teachers, 
                                    max_activities_by_rooms, max_activities_by_sections)
        
        print(f"🎯 Maximum possible activities: {max_possible_activities}")
        
        # Calculate optimal subjects per section
        optimal_subjects_per_section = max(1, min(5, max_possible_activities // total_sections))
        print(f"📖 Optimal subjects per section: {optimal_subjects_per_section}")
        
        activities = []
        working_days = self.settings.get('working_days', ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'])
        
        # Track resource usage to avoid over-allocation
        teacher_usage = defaultdict(int)
        room_usage = defaultdict(int)
        section_usage = defaultdict(int)
        
        for section in self.sections:
            # Get relevant subjects/courses for this section
            if self.app_mode == 'school':
                relevant_subjects = self.subjects_or_courses
            else:
                relevant_subjects = []
                for course in self.subjects_or_courses:
                    if hasattr(course, 'department_id') and course.department_id == section.department_id:
                        relevant_subjects.append(course)
                if not relevant_subjects:
                    relevant_subjects = self.subjects_or_courses
            
            # Shuffle subjects to add variety
            random.shuffle(relevant_subjects)
            
            # Create activities for this section (adaptive number)
            subjects_created = 0
            for subject in relevant_subjects:
                if subjects_created >= optimal_subjects_per_section:
                    break
                
                # Find a teacher who can teach this subject and isn't overused
                suitable_teacher = None
                for teacher in self.teachers:
                    if (self.teacher_can_teach(teacher, subject) and 
                        teacher_usage[teacher.id] < total_time_slots * 0.8):  # Max 80% usage
                        suitable_teacher = teacher
                        break
                
                if suitable_teacher:
                    # Find a suitable classroom for this activity
                    suitable_classroom = None
                    for classroom in self.classrooms:
                        if (classroom.capacity >= len(section.students) if hasattr(section, 'students') else True and
                            room_usage[classroom.id] < total_time_slots * 0.8):  # Max 80% usage
                            suitable_classroom = classroom
                            break
                    
                    if suitable_classroom:
                        activity_id = f"{section.id}_{suitable_teacher.id}_{suitable_classroom.id}_{subject.id}"
                        
                        activity = Activity(
                            id=activity_id,
                            section_id=section.id,
                            teacher_id=suitable_teacher.id,
                            subject_id=subject.id if self.app_mode == 'school' else None,
                            course_id=subject.id if self.app_mode == 'college' else None,
                            room_id=suitable_classroom.id,
                            priority=random.randint(1, 5)
                        )
                        
                        activities.append(activity)
                        
                        # Update usage tracking
                        teacher_usage[suitable_teacher.id] += 1
                        room_usage[suitable_classroom.id] += 1
                        section_usage[section.id] += 1
                        subjects_created += 1
        
        print(f"✅ Created {len(activities)} activities across {total_sections} sections")
        print(f"📈 Average activities per section: {len(activities) / total_sections:.1f}")
        
        return activities
    
    def teacher_can_teach(self, teacher, subject) -> bool:
        """Check if teacher can teach the subject/course"""
        if self.app_mode == 'school':
            return hasattr(teacher, 'subjects') and subject in teacher.subjects
        else:
            return hasattr(teacher, 'courses') and subject in teacher.courses
    
    def get_available_slots(self) -> List[TimeSlot]:
        """Get all available time slots"""
        slots = []
        working_days = self.settings.get('working_days', ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'])
        periods_per_day = 8
        
        for day in working_days:
            for period in range(1, periods_per_day + 1):
                slots.append(TimeSlot(day, period, "", ""))
        
        return slots
    
    def convert_to_timetable_entries(self, schedule: Dict[str, TimeSlot]) -> List[Dict]:
        """Convert schedule to timetable entries format"""
        entries = []
        
        for activity_id, time_slot in schedule.items():
            parts = activity_id.split('_')
            section_id = int(parts[0])
            teacher_id = int(parts[1])
            classroom_id = int(parts[2])
            subject_course_id = int(parts[3])
            
            entry = {
                'day': time_slot.day,
                'period': time_slot.period,
                'teacher_id': teacher_id,
                'section_id': section_id,
                'classroom_id': classroom_id
            }
            
            if self.app_mode == 'school':
                entry['subject_id'] = subject_course_id
                entry['course_id'] = None
            else:
                entry['course_id'] = subject_course_id
                entry['subject_id'] = None
            
            entries.append(entry)
        
        return entries
    
    # Helper methods
    def get_teacher_id(self, activity_id: str) -> int:
        return int(activity_id.split('_')[1])
    
    def get_room_id(self, activity_id: str) -> int:
        return int(activity_id.split('_')[2])
    
    def get_section_id(self, activity_id: str) -> int:
        return int(activity_id.split('_')[0])
