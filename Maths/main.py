import engine_main
import engine
import engine_draw
import engine_io
import engine_save
from engine_nodes import Rectangle2DNode, Text2DNode, CameraNode
from engine_math import Vector2
import random

engine.fps_limit(60)


def shuffle_list(lst):
    """Fisher-Yates shuffle since MicroPython lacks random.shuffle"""
    for i in range(len(lst) - 1, 0, -1):
        j = random.randint(0, i)
        lst[i], lst[j] = lst[j], lst[i]
    return lst


# States
STATE_LEVEL_SELECT = 0
STATE_READ_ALOUD = 1
STATE_QUIZ_SEQUENTIAL = 2
STATE_QUIZ_SHUFFLED = 3
STATE_RESULTS = 4
STATE_FEEDBACK = 5
STATE_QUIZ_INTRO = 6

# Level definitions: (name, operation, max_value)
# operation: "add", "sub", "mixed"
LEVELS = [
    ("Add to 5", "add", 5),
    ("Add to 10", "add", 10),
    ("Add to 20", "add", 20),
    ("Sub from 5", "sub", 5),
    ("Sub from 10", "sub", 10),
    ("Sub from 20", "sub", 20),
    ("Mixed to 10", "mixed", 10),
    ("Mixed to 20", "mixed", 20),
]

NUM_LEVELS = len(LEVELS)
NUM_QUESTIONS = 10

# Initialize save system
engine_save._init_saves_dir("Saves/Games/Maths")
engine_save.set_location("save")

# Load scores for all levels (0-100)
scores = []
save_keys = ["add5", "add10", "add20", "sub5", "sub10", "sub20", "mix10", "mix20"]
for key in save_keys:
    scores.append(engine_save.load("score_" + key, 0))

# Game state
state = STATE_LEVEL_SELECT
selected_level = 0
scroll_offset = 0
max_visible = 7
input_cooldown = 0

# Quiz state
current_question = 0
selected_answer = 0
answers = []  # [answer1, answer2, answer3]
correct_index = 0
first_try_correct = 0
problems = []  # List of (num1, num2, operation, answer) tuples
feedback_timer = 0
feedback_correct = False
question_timer = 0  # 5-second countdown for scored quiz
timed_out = False

# Create camera
camera = CameraNode()

# Title text
title_text = Text2DNode()
title_text.position = Vector2(0, -55)
title_text.color = engine_draw.yellow
title_text.text = "MATHS"

# Level selection menu texts (7 visible items)
menu_texts = []
for i in range(max_visible):
    t = Text2DNode()
    t.position = Vector2(0, -35 + i * 12)
    t.color = engine_draw.white
    t.text = ""
    menu_texts.append(t)

# Selector rectangle for menu
selector = Rectangle2DNode()
selector.width = 110
selector.height = 11
selector.color = engine_draw.yellow
selector.opacity = 0.3
selector.position = Vector2(0, -35)

# Instruction text at bottom
instruction_text = Text2DNode()
instruction_text.position = Vector2(0, 55)
instruction_text.color = engine_draw.lightgrey
instruction_text.text = "A: Select"

# Read aloud texts - two columns (5 each for 10 problems)
left_texts = []
right_texts = []
for i in range(5):
    lt = Text2DNode()
    lt.position = Vector2(-40, -30 + i * 12)
    lt.color = engine_draw.white
    lt.text = ""
    left_texts.append(lt)

    rt = Text2DNode()
    rt.position = Vector2(20, -30 + i * 12)
    rt.color = engine_draw.white
    rt.text = ""
    right_texts.append(rt)

# Quiz question text
question_text = Text2DNode()
question_text.position = Vector2(0, -40)
question_text.color = engine_draw.white
question_text.text = ""

# Quiz answer option texts
option_texts = []
for i in range(3):
    ot = Text2DNode()
    ot.position = Vector2(0, -10 + i * 20)
    ot.color = engine_draw.white
    ot.text = ""
    option_texts.append(ot)

# Answer selector
answer_selector = Rectangle2DNode()
answer_selector.width = 60
answer_selector.height = 16
answer_selector.color = engine_draw.yellow
answer_selector.opacity = 0.3
answer_selector.position = Vector2(0, -10)

# Progress text (Question X/10)
progress_text = Text2DNode()
progress_text.position = Vector2(0, 50)
progress_text.color = engine_draw.lightgrey
progress_text.text = ""

# Score text for shuffled quiz
score_text = Text2DNode()
score_text.position = Vector2(0, 40)
score_text.color = engine_draw.gold
score_text.text = ""

# Results texts
result_title = Text2DNode()
result_title.position = Vector2(0, -40)
result_title.color = engine_draw.yellow
result_title.text = ""

result_score = Text2DNode()
result_score.position = Vector2(0, -10)
result_score.color = engine_draw.white
result_score.text = ""

result_fraction = Text2DNode()
result_fraction.position = Vector2(0, 10)
result_fraction.color = engine_draw.lightgrey
result_fraction.text = ""

result_highscore = Text2DNode()
result_highscore.position = Vector2(0, 30)
result_highscore.color = engine_draw.gold
result_highscore.text = ""

# Timer text for scored quiz
timer_text = Text2DNode()
timer_text.position = Vector2(50, -55)
timer_text.color = engine_draw.yellow
timer_text.text = ""

# Intro screen texts
intro_title = Text2DNode()
intro_title.position = Vector2(0, -35)
intro_title.color = engine_draw.yellow
intro_title.text = ""

intro_line1 = Text2DNode()
intro_line1.position = Vector2(0, -5)
intro_line1.color = engine_draw.white
intro_line1.text = ""

intro_line2 = Text2DNode()
intro_line2.position = Vector2(0, 15)
intro_line2.color = engine_draw.white
intro_line2.text = ""

# Red border rectangles for wrong/timeout feedback
wrong_border_top = Rectangle2DNode()
wrong_border_top.width = 128
wrong_border_top.height = 4
wrong_border_top.color = engine_draw.red
wrong_border_top.position = Vector2(0, -62)
wrong_border_top.opacity = 0

wrong_border_bottom = Rectangle2DNode()
wrong_border_bottom.width = 128
wrong_border_bottom.height = 4
wrong_border_bottom.color = engine_draw.red
wrong_border_bottom.position = Vector2(0, 62)
wrong_border_bottom.opacity = 0

wrong_border_left = Rectangle2DNode()
wrong_border_left.width = 4
wrong_border_left.height = 128
wrong_border_left.color = engine_draw.red
wrong_border_left.position = Vector2(-62, 0)
wrong_border_left.opacity = 0

wrong_border_right = Rectangle2DNode()
wrong_border_right.width = 4
wrong_border_right.height = 128
wrong_border_right.color = engine_draw.red
wrong_border_right.position = Vector2(62, 0)
wrong_border_right.opacity = 0


def show_wrong_border(show):
    """Show or hide the red border for wrong answers"""
    opacity = 1 if show else 0
    wrong_border_top.opacity = opacity
    wrong_border_bottom.opacity = opacity
    wrong_border_left.opacity = opacity
    wrong_border_right.opacity = opacity


def generate_problems(operation, max_value, count=NUM_QUESTIONS):
    """Generate math problems for the selected level"""
    result = []
    attempts = 0
    max_attempts = count * 20  # Prevent infinite loop

    while len(result) < count and attempts < max_attempts:
        attempts += 1

        if operation == "add":
            # Addition: a + b where a + b <= max_value
            a = random.randint(0, max_value)
            b = random.randint(0, max_value - a)
            answer = a + b
            op = "+"
        elif operation == "sub":
            # Subtraction: a - b where a <= max_value and result >= 0
            a = random.randint(0, max_value)
            b = random.randint(0, a)
            answer = a - b
            op = "-"
        else:  # mixed
            if random.randint(0, 1) == 0:
                # Addition
                a = random.randint(0, max_value)
                b = random.randint(0, max_value - a)
                answer = a + b
                op = "+"
            else:
                # Subtraction
                a = random.randint(0, max_value)
                b = random.randint(0, a)
                answer = a - b
                op = "-"

        # Avoid trivial problems like 0+0 or x-0 or 0-0
        if a == 0 and b == 0:
            continue

        # Check for duplicates
        problem = (a, b, op, answer)
        is_dup = False
        for p in result:
            if p[0] == a and p[1] == b and p[2] == op:
                is_dup = True
                break

        if not is_dup:
            result.append(problem)

    shuffle_list(result)
    return result


def generate_wrong_answers(correct, max_value):
    """Generate 2 plausible wrong answers close to correct value"""
    wrongs = set()

    # Use small offsets for plausible wrong answers
    for offset in [1, 2, 3, 4, 5]:
        if correct - offset >= 0:
            wrongs.add(correct - offset)
        if correct + offset <= max_value + 5:  # Allow slightly over for harder levels
            wrongs.add(correct + offset)

    # Remove correct answer if somehow included
    wrongs.discard(correct)

    # Shuffle and return 2
    wrong_list = list(wrongs)
    shuffle_list(wrong_list)
    return wrong_list[:2]


def setup_question_from_problem(problem):
    """Set up a quiz question with 3 answer options from a problem tuple"""
    global answers, correct_index
    _, _, _, correct = problem
    max_val = LEVELS[selected_level][2]
    wrongs = generate_wrong_answers(correct, max_val)
    answers = [correct] + wrongs
    shuffle_list(answers)
    correct_index = answers.index(correct)


def hide_all_ui():
    """Hide all UI elements"""
    title_text.opacity = 0
    selector.opacity = 0
    instruction_text.opacity = 0
    question_text.opacity = 0
    answer_selector.opacity = 0
    progress_text.opacity = 0
    score_text.opacity = 0
    result_title.opacity = 0
    result_score.opacity = 0
    result_fraction.opacity = 0
    result_highscore.opacity = 0
    timer_text.opacity = 0
    intro_title.opacity = 0
    intro_line1.opacity = 0
    intro_line2.opacity = 0
    show_wrong_border(False)
    for t in menu_texts:
        t.opacity = 0
    for t in left_texts:
        t.opacity = 0
    for t in right_texts:
        t.opacity = 0
    for t in option_texts:
        t.opacity = 0


def show_level_select():
    """Show level selection UI"""
    hide_all_ui()
    title_text.opacity = 1
    title_text.text = "MATHS"
    selector.opacity = 0.3
    instruction_text.opacity = 1
    instruction_text.text = "A: Select"
    for t in menu_texts:
        t.opacity = 1
    update_menu_display()


def update_menu_display():
    """Update menu item text based on scroll offset"""
    for i in range(max_visible):
        idx = scroll_offset + i
        if idx < NUM_LEVELS:
            level_name = LEVELS[idx][0]
            score_pct = scores[idx]
            menu_texts[i].text = level_name + "  " + str(score_pct) + "%"
            if idx == selected_level:
                menu_texts[i].color = engine_draw.white
            else:
                menu_texts[i].color = engine_draw.lightgrey
        else:
            menu_texts[i].text = ""
    # Update selector position
    visible_idx = selected_level - scroll_offset
    selector.position.y = -35 + visible_idx * 12


def format_problem(problem):
    """Format a problem tuple as a string like '3 + 4 = 7'"""
    a, b, op, answer = problem
    return str(a) + " " + op + " " + str(b) + " = " + str(answer)


def show_read_aloud():
    """Show read aloud screen with two columns"""
    global problems
    hide_all_ui()
    title_text.opacity = 1
    level_name = LEVELS[selected_level][0]
    title_text.text = level_name
    instruction_text.opacity = 1
    instruction_text.text = "A: Start Quiz"

    # Generate problems for this level
    _, operation, max_value = LEVELS[selected_level]
    problems = generate_problems(operation, max_value)

    # Display problems in two columns (5 each)
    for i in range(5):
        left_texts[i].opacity = 1
        right_texts[i].opacity = 1
        # Left column: 0-4
        left_texts[i].text = format_problem(problems[i])
        # Right column: 5-9
        right_texts[i].text = format_problem(problems[i + 5])


def show_quiz_intro():
    """Show intro screen before scored quiz"""
    hide_all_ui()
    intro_title.opacity = 1
    intro_title.text = "SCORED QUIZ!"
    intro_line1.opacity = 1
    intro_line1.text = "5 seconds per question"
    intro_line2.opacity = 1
    intro_line2.text = "Score shown at end"
    instruction_text.opacity = 1
    instruction_text.text = "A: Start"


def show_quiz(is_shuffled):
    """Show quiz screen"""
    global question_timer
    hide_all_ui()
    question_text.opacity = 1
    answer_selector.opacity = 0.3
    progress_text.opacity = 1
    instruction_text.opacity = 0

    if is_shuffled:
        score_text.opacity = 1
        timer_text.opacity = 1
        question_timer = 300  # 5 seconds at 60fps
        timer_text.text = "5"

    for t in option_texts:
        t.opacity = 1

    update_quiz_display(is_shuffled)


def update_quiz_display(is_shuffled):
    """Update quiz question and answers"""
    global selected_answer

    problem = problems[current_question]
    a, b, op, _ = problem

    question_text.text = str(a) + " " + op + " " + str(b) + " = ?"

    for i in range(3):
        option_texts[i].text = str(answers[i])
        if i == selected_answer:
            option_texts[i].color = engine_draw.white
        else:
            option_texts[i].color = engine_draw.lightgrey

    answer_selector.position.y = -10 + selected_answer * 20
    progress_text.text = "Question " + str(current_question + 1) + "/" + str(NUM_QUESTIONS)

    if is_shuffled:
        score_text.text = "Score: " + str(first_try_correct) + "/" + str(current_question)


def show_feedback(is_correct, is_timeout=False):
    """Show answer feedback"""
    for i in range(3):
        if i == correct_index:
            option_texts[i].color = engine_draw.green
        elif i == selected_answer and not is_correct and not is_timeout:
            option_texts[i].color = engine_draw.red
        else:
            option_texts[i].color = engine_draw.lightgrey
    answer_selector.opacity = 0
    timer_text.opacity = 0
    if not is_correct:
        show_wrong_border(True)
        instruction_text.opacity = 1
        instruction_text.text = "A: Continue"


def show_results():
    """Show results screen"""
    hide_all_ui()
    level_name = LEVELS[selected_level][0]
    result_title.opacity = 1
    result_title.text = level_name + " DONE!"

    result_score.opacity = 1
    pct = (first_try_correct * 100) // NUM_QUESTIONS
    result_score.text = "Score: " + str(pct) + "%"

    result_fraction.opacity = 1
    result_fraction.text = "(" + str(first_try_correct) + "/" + str(NUM_QUESTIONS) + " correct)"

    instruction_text.opacity = 1
    instruction_text.text = "A: Continue"

    # Check for high score
    if pct > scores[selected_level]:
        result_highscore.opacity = 1
        result_highscore.text = "NEW HIGH SCORE!"
        scores[selected_level] = pct
        engine_save.save("score_" + save_keys[selected_level], pct)
    else:
        result_highscore.opacity = 0


# Initialize display
show_level_select()

# Track if we're in shuffled mode
in_shuffled_mode = False

# Main game loop
while True:
    if engine.tick():
        if input_cooldown > 0:
            input_cooldown -= 1

        # Handle menu button to exit
        if engine_io.MENU.is_just_pressed:
            engine.end()
            break

        if state == STATE_LEVEL_SELECT:
            if input_cooldown == 0:
                if engine_io.UP.is_just_pressed:
                    selected_level -= 1
                    if selected_level < 0:
                        selected_level = NUM_LEVELS - 1
                        scroll_offset = max(0, NUM_LEVELS - max_visible)
                    elif selected_level < scroll_offset:
                        scroll_offset = selected_level
                    update_menu_display()
                    input_cooldown = 5

                elif engine_io.DOWN.is_just_pressed:
                    selected_level += 1
                    if selected_level > NUM_LEVELS - 1:
                        selected_level = 0
                        scroll_offset = 0
                    elif selected_level >= scroll_offset + max_visible:
                        scroll_offset = selected_level - max_visible + 1
                    update_menu_display()
                    input_cooldown = 5

                elif engine_io.A.is_just_pressed:
                    state = STATE_READ_ALOUD
                    show_read_aloud()
                    input_cooldown = 10

        elif state == STATE_READ_ALOUD:
            if input_cooldown == 0:
                if engine_io.A.is_just_pressed:
                    # Start sequential quiz
                    state = STATE_QUIZ_SEQUENTIAL
                    in_shuffled_mode = False
                    current_question = 0
                    selected_answer = 1
                    setup_question_from_problem(problems[0])
                    show_quiz(False)
                    input_cooldown = 10

                elif engine_io.B.is_just_pressed:
                    state = STATE_LEVEL_SELECT
                    show_level_select()
                    input_cooldown = 10

        elif state == STATE_QUIZ_SEQUENTIAL:
            if input_cooldown == 0:
                if engine_io.UP.is_just_pressed:
                    selected_answer = (selected_answer - 1) % 3
                    update_quiz_display(False)
                    input_cooldown = 5

                elif engine_io.DOWN.is_just_pressed:
                    selected_answer = (selected_answer + 1) % 3
                    update_quiz_display(False)
                    input_cooldown = 5

                elif engine_io.A.is_just_pressed:
                    feedback_correct = (selected_answer == correct_index)
                    show_feedback(feedback_correct)
                    state = STATE_FEEDBACK
                    feedback_timer = 30
                    input_cooldown = 10

        elif state == STATE_QUIZ_SHUFFLED:
            # Update timer countdown
            question_timer -= 1
            seconds_left = (question_timer + 59) // 60
            timer_text.text = str(seconds_left)

            if question_timer <= 0:
                timed_out = True
                feedback_correct = False
                show_feedback(False, is_timeout=True)
                state = STATE_FEEDBACK
                feedback_timer = 30
                input_cooldown = 10
            elif input_cooldown == 0:
                if engine_io.UP.is_just_pressed:
                    selected_answer = (selected_answer - 1) % 3
                    update_quiz_display(True)
                    input_cooldown = 5

                elif engine_io.DOWN.is_just_pressed:
                    selected_answer = (selected_answer + 1) % 3
                    update_quiz_display(True)
                    input_cooldown = 5

                elif engine_io.A.is_just_pressed:
                    timed_out = False
                    feedback_correct = (selected_answer == correct_index)
                    if feedback_correct:
                        first_try_correct += 1
                    show_feedback(feedback_correct)
                    state = STATE_FEEDBACK
                    feedback_timer = 30
                    input_cooldown = 10

        elif state == STATE_FEEDBACK:
            if feedback_correct:
                feedback_timer -= 1
                can_advance = feedback_timer <= 0
            else:
                can_advance = engine_io.A.is_just_pressed and input_cooldown == 0

            if can_advance:
                current_question += 1
                selected_answer = 1

                if current_question >= NUM_QUESTIONS:
                    if not in_shuffled_mode:
                        # Was sequential, show intro before scored quiz
                        state = STATE_QUIZ_INTRO
                        show_quiz_intro()
                    else:
                        # Was shuffled, show results
                        state = STATE_RESULTS
                        show_results()
                else:
                    if not in_shuffled_mode:
                        # Sequential mode
                        state = STATE_QUIZ_SEQUENTIAL
                        setup_question_from_problem(problems[current_question])
                        show_quiz(False)
                    else:
                        # Shuffled mode
                        state = STATE_QUIZ_SHUFFLED
                        setup_question_from_problem(problems[current_question])
                        show_quiz(True)

                input_cooldown = 5

        elif state == STATE_RESULTS:
            if input_cooldown == 0:
                if engine_io.A.is_just_pressed:
                    state = STATE_LEVEL_SELECT
                    in_shuffled_mode = False
                    show_level_select()
                    input_cooldown = 10

        elif state == STATE_QUIZ_INTRO:
            if input_cooldown == 0:
                if engine_io.A.is_just_pressed:
                    # Start scored quiz with shuffled problems
                    state = STATE_QUIZ_SHUFFLED
                    in_shuffled_mode = True
                    current_question = 0
                    first_try_correct = 0
                    selected_answer = 1
                    # Re-generate and shuffle problems for the scored quiz
                    _, operation, max_value = LEVELS[selected_level]
                    problems = generate_problems(operation, max_value)
                    setup_question_from_problem(problems[0])
                    show_quiz(True)
                    input_cooldown = 10
