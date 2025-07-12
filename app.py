# app.py
from flask import Flask, request, jsonify, g
from flask_cors import CORS
from datetime import datetime, timedelta
import jwt
import uuid
from functools import wraps

app = Flask(__name__)
# Дозволяємо CORS для всіх доменів під час розробки.
# На продакшені варто обмежити домени, наприклад: CORS(app, resources={r"/*": {"origins": "https://yourdomain.com"}})
CORS(app)

# Секретний ключ для JWT токенів. В продакшені має бути складним і зберігатися в змінних середовища!
app.config['SECRET_KEY'] = 'njgcfqnnjhec25njgcfqncnth,fqcnth25'

# --- In-memory "база даних" ---
# У реальному додатку тут була б база даних (SQLAlchemy, MongoDB тощо)
users = {}  # {user_id: {id, username, email, password, role}}
user_progress = {}  # {user_id: [{date, weight, workouts_completed}]}
workout_templates = {} # {template_id: {id, name, description, exercises: [{name, sets, reps}], is_global, user_id, muscle_groups: []}}
user_workouts_data = {} # {user_id: [{id, template_id, workout_date, status, name, description, exercises}]}

# --- Допоміжні функції ---

def generate_unique_id():
    """Генерує унікальний ID."""
    return str(uuid.uuid4())

# Декоратор для захищених маршрутів
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'x-access-token' in request.headers:
            token = request.headers['x-access-token']

        if not token:
            return jsonify({'message': 'Токен відсутній!'}), 401

        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            current_user = None
            for user_id, user_data in users.items():
                if user_data['id'] == data['user_id']:
                    current_user = user_data
                    break
            if not current_user:
                return jsonify({'message': 'Користувача не знайдено!'}), 401
            g.current_user = current_user # Зберігаємо поточного користувача в g
        except jwt.ExpiredSignatureError:
            return jsonify({'message': 'Токен прострочений!'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'message': 'Недійсний токен!'}), 401
        except Exception as e:
            print(f"Помилка декодування токена: {e}")
            return jsonify({'message': 'Недійсний токен або помилка сервера!'}), 401

        return f(*args, **kwargs)
    return decorated


# --- Маршрути автентифікації ---

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')

    if not username or not email or not password:
        return jsonify({'message': 'Будь ласка, введіть ім\'я користувача, email та пароль.'}), 400

    # Перевірка, чи користувач вже існує
    for user_id, user_data in users.items():
        if user_data['email'] == email:
            return jsonify({'message': 'Користувач з таким email вже існує.'}), 409
        if user_data['username'] == username:
            return jsonify({'message': 'Користувач з таким ім\'ям вже існує.'}), 409

    user_id = generate_unique_id()
    # Перший зареєстрований користувач стає адміном для демонстрації
    role = 'admin' if not users else 'user' 
    users[user_id] = {'id': user_id, 'username': username, 'email': email, 'password': password, 'role': role}
    print(f"DEBUG: Зареєстровано нового користувача: {username} з роллю {role}")
    return jsonify({'message': 'Реєстрація успішна!'}), 201

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({'message': 'Будь ласка, введіть email та пароль.'}), 400

    user = None
    for user_id, user_data in users.items():
        if user_data['email'] == email and user_data['password'] == password: # У реальному додатку тут була б перевірка хешованого пароля
            user = user_data
            break

    if not user:
        return jsonify({'message': 'Невірний email або пароль.'}), 401

    token = jwt.encode({
        'user_id': user['id'],
        'exp': datetime.utcnow() + timedelta(hours=24) # Токен дійсний 24 години
    }, app.config['SECRET_KEY'], algorithm='HS256')

    return jsonify({'message': 'Вхід успішний!', 'token': token}), 200

# --- Маршрути для профілю користувача ---

@app.route('/my_profile_data', methods=['GET'])
@token_required
def get_my_profile_data():
    user = g.current_user
    return jsonify({
        'id': user['id'],
        'username': user['username'],
        'email': user['email'],
        'role': user['role']
    }), 200

@app.route('/my_profile_data', methods=['PUT'])
@token_required
def update_my_profile_data():
    user_id = g.current_user['id']
    data = request.get_json()
    new_username = data.get('username')
    new_email = data.get('email')

    if not new_username or not new_email:
        return jsonify({'message': 'Ім\'я користувача та email не можуть бути порожніми.'}), 400

    # Перевірка унікальності нового email/username (крім поточного користувача)
    for uid, udata in users.items():
        if uid != user_id:
            if udata['email'] == new_email:
                return jsonify({'message': 'Користувач з таким email вже існує.'}), 409
            if udata['username'] == new_username:
                return jsonify({'message': 'Користувач з таким ім\'ям вже існує.'}), 409

    users[user_id]['username'] = new_username
    users[user_id]['email'] = new_email
    return jsonify({'message': 'Дані профілю успішно оновлено!'}), 200

# --- Маршрути для прогресу користувача ---

@app.route('/my_progress', methods=['GET'])
@token_required
def get_my_progress():
    user_id = g.current_user['id']
    # Повертаємо прогрес для поточного користувача, сортуємо за датою
    progress = user_progress.get(user_id, [])
    # Сортуємо від найновіших до найстаріших
    sorted_progress = sorted(progress, key=lambda x: x['date'], reverse=True)
    return jsonify(sorted_progress), 200

@app.route('/my_progress', methods=['POST'])
@token_required
def add_my_progress():
    user_id = g.current_user['id']
    data = request.get_json()
    weight = data.get('weight')
    
    if weight is None:
        return jsonify({'message': 'Вага є обов\'язковим полем.'}), 400
    
    today_date = datetime.now().strftime('%Y-%m-%d')
    
    # Перевіряємо, чи вже є запис за сьогодні
    if user_id not in user_progress:
        user_progress[user_id] = []
    
    # Шукаємо і оновлюємо запис за сьогодні, якщо він існує
    found = False
    for entry in user_progress[user_id]:
        if entry['date'] == today_date:
            entry['weight'] = weight
            entry['workouts_completed'] = entry.get('workouts_completed', 0) # Зберігаємо існуючі завершені тренування
            found = True
            break
    
    if not found:
        user_progress[user_id].append({
            'date': today_date,
            'weight': weight,
            'workouts_completed': 0 # Початкове значення
        })
    
    return jsonify({'message': 'Прогрес успішно збережено!'}), 200

# --- Маршрути для шаблонів тренувань ---

@app.route('/workout_templates', methods=['GET'])
@token_required
def get_workout_templates():
    user_id = g.current_user['id']
    muscle_group_filter = request.args.get('muscle_group')
    goal_filter = request.args.get('goal')
    difficulty_filter = request.args.get('difficulty')
    equipment_filter = request.args.getlist('equipment') # getlist для множинних значень
    duration_category_filter = request.args.get('duration_category')

    filtered_templates = []
    for template_id, template_data in workout_templates.items():
        # Шаблони доступні, якщо вони глобальні або створені поточним користувачем
        is_accessible = template_data.get('is_global', False) or template_data.get('user_id') == user_id
        
        if is_accessible:
            match = True
            if muscle_group_filter and muscle_group_filter not in template_data.get('muscle_groups', []):
                match = False
            if goal_filter and template_data.get('goal') != goal_filter:
                match = False
            if difficulty_filter and template_data.get('difficulty') != difficulty_filter:
                match = False
            if equipment_filter:
                # Перевіряємо, чи всі вибрані елементи обладнання присутні в шаблоні
                if not all(eq in template_data.get('equipment', []) for eq in equipment_filter):
                    match = False
            if duration_category_filter and template_data.get('duration_category') != duration_category_filter:
                match = False

            if match:
                filtered_templates.append(template_data)
    
    return jsonify(filtered_templates), 200

@app.route('/workout_templates', methods=['POST'])
@token_required
def add_workout_template():
    user_id = g.current_user['id']
    role = g.current_user['role']

    if role != 'admin':
        return jsonify({'message': 'У вас немає дозволу на створення шаблонів тренувань.'}), 403

    data = request.get_json()
    name = data.get('name')
    description = data.get('description')
    exercises = data.get('exercises', [])
    is_global = data.get('is_global', False)
    muscle_groups = data.get('muscle_groups', [])
    goal = data.get('goal')
    difficulty = data.get('difficulty')
    equipment = data.get('equipment', [])
    duration_category = data.get('duration_category')

    if not name:
        return jsonify({'message': 'Назва шаблону є обов\'язковою.'}), 400

    template_id = generate_unique_id()
    workout_templates[template_id] = {
        'id': template_id,
        'name': name,
        'description': description,
        'exercises': exercises,
        'is_global': is_global,
        'user_id': user_id, # Зберігаємо ID користувача, який створив шаблон
        'muscle_groups': muscle_groups,
        'goal': goal,
        'difficulty': difficulty,
        'equipment': equipment,
        'duration_category': duration_category
    }
    return jsonify({'message': 'Шаблон тренування успішно створено!'}), 201

@app.route('/workout_templates/<template_id>', methods=['GET'])
@token_required
def get_workout_template(template_id):
    user_id = g.current_user['id']
    template = workout_templates.get(template_id)

    if not template:
        return jsonify({'message': 'Шаблон тренування не знайдено.'}), 404
    
    # Перевірка доступу: глобальний шаблон або створений поточним користувачем
    if not (template.get('is_global', False) or template.get('user_id') == user_id):
        return jsonify({'message': 'У вас немає дозволу на перегляд цього шаблону.'}), 403

    return jsonify(template), 200

@app.route('/workout_templates/<template_id>', methods=['PUT'])
@token_required
def update_workout_template(template_id):
    user_id = g.current_user['id']
    role = g.current_user['role']
    template = workout_templates.get(template_id)

    if not template:
        return jsonify({'message': 'Шаблон тренування не знайдено.'}), 404
    
    # Дозволяємо редагувати лише адмінам або власнику шаблону, якщо він не глобальний
    if role != 'admin' and not (template.get('user_id') == user_id and not template.get('is_global', False)):
        return jsonify({'message': 'У вас немає дозволу на редагування цього шаблону.'}), 403

    data = request.get_json()
    template['name'] = data.get('name', template['name'])
    template['description'] = data.get('description', template.get('description'))
    template['exercises'] = data.get('exercises', template['exercises'])
    template['is_global'] = data.get('is_global', template.get('is_global', False))
    template['muscle_groups'] = data.get('muscle_groups', template.get('muscle_groups', []))
    template['goal'] = data.get('goal', template.get('goal'))
    template['difficulty'] = data.get('difficulty', template.get('difficulty'))
    template['equipment'] = data.get('equipment', template.get('equipment', []))
    template['duration_category'] = data.get('duration_category', template.get('duration_category'))

    return jsonify({'message': 'Шаблон тренування успішно оновлено!'}), 200

@app.route('/workout_templates/<template_id>', methods=['DELETE'])
@token_required
def delete_workout_template(template_id):
    user_id = g.current_user['id']
    role = g.current_user['role']
    template = workout_templates.get(template_id)

    if not template:
        return jsonify({'message': 'Шаблон тренування не знайдено.'}), 404
    
    # Дозволяємо видаляти лише адмінам або власнику шаблону, якщо він не глобальний
    if role != 'admin' and not (template.get('user_id') == user_id and not template.get('is_global', False)):
        return jsonify({'message': 'У вас немає дозволу на видалення цього шаблону.'}), 403

    if template_id in workout_templates:
        del workout_templates[template_id]
        return jsonify({'message': 'Шаблон тренування успішно видалено!'}), 200
    return jsonify({'message': 'Шаблон тренування не знайдено.'}), 404


# --- Маршрути для щоденних тренувань (графік) ---

@app.route('/daily_workouts', methods=['GET'])
@token_required
def get_daily_workouts():
    user_id = g.current_user['id']
    workouts = user_workouts_data.get(user_id, [])
    # Сортуємо від найновіших до найстаріших
    sorted_workouts = sorted(workouts, key=lambda x: x['date'], reverse=True)
    return jsonify(sorted_workouts), 200

@app.route('/daily_workouts', methods=['POST'])
@token_required
def add_daily_workout():
    user_id = g.current_user['id']
    data = request.get_json()
    template_id = data.get('template_id')
    workout_date = data.get('date')

    if not template_id or not workout_date:
        return jsonify({'message': 'ID шаблону та дата є обов\'язковими.'}), 400

    template = workout_templates.get(template_id)
    if not template:
        return jsonify({'message': 'Шаблон тренування не знайдено.'}), 404

    # Перевірка, чи шаблон доступний користувачеві
    if not (template.get('is_global', False) or template.get('user_id') == user_id):
        return jsonify({'message': 'У вас немає дозволу на використання цього шаблону.'}), 403

    daily_workout_id = generate_unique_id()
    
    # Копіюємо дані з шаблону, щоб зберегти стан тренування на момент його створення
    # Це дозволить змінювати шаблон без впливу на вже заплановані тренування
    new_daily_workout = {
        'id': daily_workout_id,
        'user_id': user_id,
        'template_id': template_id,
        'workout_date': workout_date,
        'date': workout_date, # Для сумісності з фронтендом, який очікує 'date'
        'status': 'upcoming',
        'template_name': template['name'], # Зберігаємо назву шаблону
        'description': template.get('description'),
        'exercises': template.get('exercises', [])[:] # Копіюємо список вправ
    }

    if user_id not in user_workouts_data:
        user_workouts_data[user_id] = []
    user_workouts_data[user_id].append(new_daily_workout)

    return jsonify({'message': 'Тренування успішно додано до графіку!'}), 201

@app.route('/daily_workouts/<workout_id>', methods=['GET'])
@token_required
def get_daily_workout(workout_id):
    user_id = g.current_user['id']
    workouts = user_workouts_data.get(user_id, [])
    workout = next((w for w in workouts if w['id'] == workout_id), None)
    
    if not workout:
        return jsonify({'message': 'Тренування не знайдено.'}), 404
    
    return jsonify(workout), 200

@app.route('/daily_workouts/<workout_id>/complete', methods=['POST'])
@token_required
def complete_daily_workout(workout_id):
    user_id = g.current_user['id']
    data = request.get_json()
    actual_exercises = data.get('exercises', [])
    duration_seconds = data.get('duration_seconds', 0)

    workouts = user_workouts_data.get(user_id, [])
    workout = next((w for w in workouts if w['id'] == workout_id), None)

    if not workout:
        return jsonify({'message': 'Тренування не знайдено.'}), 404
    
    if workout['status'] == 'completed':
        return jsonify({'message': 'Тренування вже завершено.'}), 400

    workout['status'] = 'completed'
    workout['exercises'] = actual_exercises # Оновлюємо вправи з фактичними даними
    workout['duration_seconds'] = duration_seconds # Зберігаємо тривалість

    # Оновлюємо прогрес користувача: збільшуємо кількість завершених тренувань за цей день
    workout_date = workout['date']
    if user_id in user_progress:
        found_progress = False
        for entry in user_progress[user_id]:
            if entry['date'] == workout_date:
                entry['workouts_completed'] = entry.get('workouts_completed', 0) + 1
                found_progress = True
                break
        if not found_progress:
            # Якщо запису прогресу за цей день не було, створюємо новий
            user_progress[user_id].append({
                'date': workout_date,
                'weight': None, # Вага може бути не вказана
                'workouts_completed': 1
            })

    return jsonify({'message': 'Тренування успішно завершено!'}), 200

@app.route('/daily_workouts/<workout_id>/reset_status', methods=['POST'])
@token_required
def reset_daily_workout_status(workout_id):
    user_id = g.current_user['id']
    workouts = user_workouts_data.get(user_id, [])
    workout = next((w for w in workouts if w['id'] == workout_id), None)

    if not workout:
        return jsonify({'message': 'Тренування не знайдено.'}), 404
    
    if workout['status'] == 'upcoming':
        return jsonify({'message': 'Тренування вже має статус "заплановано".'}), 400

    workout['status'] = 'upcoming'
    # Опціонально: очистити фактичні дані про виконання
    for exercise in workout['exercises']:
        if 'actual_weight' in exercise:
            del exercise['actual_weight']
        if 'actual_sets_reps' in exercise:
            del exercise['actual_sets_reps']
    if 'duration_seconds' in workout:
        del workout['duration_seconds']

    # Зменшуємо кількість завершених тренувань у прогресі за цей день
    workout_date = workout['date']
    if user_id in user_progress:
        for entry in user_progress[user_id]:
            if entry['date'] == workout_date:
                if entry.get('workouts_completed', 0) > 0:
                    entry['workouts_completed'] -= 1
                break

    return jsonify({'message': 'Статус тренування успішно скинуто на "заплановано"!'}), 200

@app.route('/daily_workouts/<workout_id>', methods=['DELETE'])
@token_required
def delete_daily_workout(workout_id):
    user_id = g.current_user['id']
    
    if user_id not in user_workouts_data:
        return jsonify({'message': 'Тренування не знайдено.'}), 404

    initial_len = len(user_workouts_data[user_id])
    user_workouts_data[user_id] = [w for w in user_workouts_data[user_id] if w['id'] != workout_id]
    
    if len(user_workouts_data[user_id]) < initial_len:
        return jsonify({'message': 'Тренування успішно видалено!'}), 200
    return jsonify({'message': 'Тренування не знайдено.'}), 404


# НОВИЙ ЕНДПОІНТ: Скидання всіх даних користувача
@app.route('/reset_my_data', methods=['DELETE'])
@token_required
def reset_my_data():
    user_id = g.current_user['id']
    
    # Видаляємо прогрес користувача
    if user_id in user_progress:
        del user_progress[user_id]
        print(f"DEBUG: Прогрес користувача {user_id} скинуто.")
    
    # Видаляємо всі заплановані/виконані тренування користувача
    if user_id in user_workouts_data:
        del user_workouts_data[user_id]
        print(f"DEBUG: Тренування користувача {user_id} скинуто.")

    # Примітка: Шаблони тренувань (workout_templates) не видаляються,
    # оскільки вони можуть бути глобальними або особистими, які користувач
    # може захотіти зберегти. Якщо потрібно видаляти і особисті шаблони,
    # знадобиться додаткова логіка фільтрації.
    
    return jsonify({"message": "Всі ваші дані успішно скинуто."}), 200


# --- Ініціалізація тестових даних (видаліть на продакшені) ---
def initialize_test_data():
    if not users: # Додаємо тестових користувачів лише якщо їх немає
        admin_id = generate_unique_id()
        user_id_1 = generate_unique_id()
        user_id_2 = generate_unique_id()

        users[admin_id] = {'id': admin_id, 'username': 'admin', 'email': 'admin@example.com', 'password': 'admin', 'role': 'admin'}
        users[user_id_1] = {'id': user_id_1, 'username': 'user1', 'email': 'user1@example.com', 'password': 'pass1', 'role': 'user'}
        users[user_id_2] = {'id': user_id_2, 'username': 'user2', 'email': 'user2@example.com', 'password': 'pass2', 'role': 'user'}
        print("DEBUG: Додано тестових користувачів.")

    if not workout_templates: # Додаємо тестові шаблони тренувань лише якщо їх немає
        template_id_1 = generate_unique_id()
        workout_templates[template_id_1] = {
            'id': template_id_1,
            'name': 'Тренування для грудей та трицепсів',
            'description': 'Комплексне тренування для розвитку грудних м\'язів та трицепсів.',
            'exercises': [
                {'name': 'Жим лежачи', 'sets': 4, 'reps': '8-12'},
                {'name': 'Жим гантелей на похилій лаві', 'sets': 3, 'reps': '10-15'},
                {'name': 'Віджимання на брусах', 'sets': 3, 'reps': 'до відмови'},
                {'name': 'Французький жим', 'sets': 3, 'reps': '10-15'}
            ],
            'is_global': True,
            'user_id': list(users.keys())[0], # Прив'язуємо до першого користувача (адміна)
            'muscle_groups': ['Груди', 'Трицепс'],
            'goal': 'Набір маси',
            'difficulty': 'Середній',
            'equipment': ['Штанга', 'Гантелі', 'Без обладнання'],
            'duration_category': '30-60 хв'
        }
        
        template_id_2 = generate_unique_id()
        workout_templates[template_id_2] = {
            'id': template_id_2,
            'name': 'Тренування для спини та біцепсів',
            'description': 'Інтенсивне тренування для м\'язів спини та біцепсів.',
            'exercises': [
                {'name': 'Тяга верхнього блоку', 'sets': 4, 'reps': '8-12'},
                {'name': 'Тяга штанги в нахилі', 'sets': 3, 'reps': '8-12'},
                {'name': 'Підтягування', 'sets': 3, 'reps': 'до відмови'},
                {'name': 'Згинання рук зі штангою', 'sets': 3, 'reps': '10-15'}
            ],
            'is_global': True,
            'user_id': list(users.keys())[0],
            'muscle_groups': ['Спина', 'Біцепс'],
            'goal': 'Набір маси',
            'difficulty': 'Середній',
            'equipment': ['Штанга', 'Тренажери', 'Без обладнання'],
            'duration_category': 'Понад 60 хв'
        }

        template_id_3 = generate_unique_id()
        workout_templates[template_id_3] = {
            'id': template_id_3,
            'name': 'Тренування для ніг та плечей',
            'description': 'Функціональне тренування для нижньої частини тіла та дельт.',
            'exercises': [
                {'name': 'Присідання зі штангою', 'sets': 4, 'reps': '6-10' },
                {'name': 'Жим ногами', 'sets': 3, 'reps': '10-15'},
                {'name': 'Махи гантелями в сторони', 'sets': 3, 'reps': '12-15'},
                {'name': 'Жим гантелей сидячи', 'sets': 3, 'reps': '8-12'}
            ],
            'is_global': True,
            'user_id': list(users.keys())[0],
            'muscle_groups': ['Ноги', 'Плечі'],
            'goal': 'Сила',
            'difficulty': 'Просунутий',
            'equipment': ['Штанга', 'Гантелі', 'Тренажери'],
            'duration_category': 'Понад 60 хв'
        }
        
        template_id_4 = generate_unique_id()
        workout_templates[template_id_4] = {
            'id': template_id_4,
            'name': 'Кардіо та прес',
            'description': 'Легке кардіо та вправи для кора.',
            'exercises': [
                {'name': 'Бігова доріжка', 'sets': 1, 'reps': '30 хв'},
                {'name': 'Планка', 'sets': 3, 'reps': '60 сек'},
                {'name': 'Скручування', 'sets': 3, 'reps': '15-20'}
            ],
            'is_global': True,
            'user_id': list(users.keys())[0],
            'muscle_groups': ['Прес', 'Кардіо'],
            'goal': 'Сушка',
            'difficulty': 'Початківець',
            'equipment': ['Без обладнання', 'Тренажери'],
            'duration_category': 'До 30 хв'
        }

        template_id_5 = generate_unique_id()
        workout_templates[template_id_5] = {
            'id': template_id_5,
            'name': 'Домашнє тренування на все тіло',
            'description': 'Тренування вдома без додаткового обладнання.',
            'exercises': [
                {'name': 'Присідання без ваги', 'sets': 3, 'reps': '15-20'},
                {'name': 'Віджимання від підлоги', 'sets': 3, 'reps': '10-15'},
                {'name': 'Випади', 'sets': 3, 'reps': 'по 10-12 на ногу'},
                {'name': 'Планка', 'sets': 3, 'reps': '45-60 сек'}
            ],
            'is_global': False, # Це особистий шаблон
            'user_id': user_id_1, # Прив'язуємо до user1
            'muscle_groups': ['Ноги', 'Груди', 'Прес'],
            'goal': 'Загальний тонус',
            'difficulty': 'Початківець',
            'equipment': ['Без обладнання'],
            'duration_category': '30-60 хв'
        }
        print("DEBUG: Додано тестові шаблони тренувань.")
    
    if not user_progress: # Додаємо тестові дані прогресу
        user_progress[list(users.keys())[1]] = [ # Для user1
            {'date': '2025-06-01', 'weight': 75.5, 'workouts_completed': 2},
            {'date': '2025-06-08', 'weight': 75.0, 'workouts_completed': 1},
            {'date': '2025-06-15', 'weight': 74.8, 'workouts_completed': 3}
        ]
        print("DEBUG: Додано тестові дані прогресу.")

    if not user_workouts_data: # Додаємо тестові щоденні тренування
        user_id_for_workouts = list(users.keys())[1] # user1
        template_for_daily_1 = workout_templates[list(workout_templates.keys())[0]] # Груди/Трицепси
        template_for_daily_2 = workout_templates[list(workout_templates.keys())[3]] # Кардіо/Прес

        user_workouts_data[user_id_for_workouts] = [
            {
                'id': generate_unique_id(),
                'user_id': user_id_for_workouts,
                'template_id': template_for_daily_1['id'],
                'workout_date': '2025-07-01',
                'date': '2025-07-01',
                'status': 'completed',
                'template_name': template_for_daily_1['name'],
                'description': template_for_daily_1['description'],
                'exercises': [
                    {'name': 'Жим лежачи', 'sets': 4, 'reps': '8-12', 'actual_weight': 60, 'actual_sets_reps': '4x10'},
                    {'name': 'Жим гантелей на похилій лаві', 'sets': 3, 'reps': '10-15', 'actual_weight': 20, 'actual_sets_reps': '3x12'}
                ],
                'duration_seconds': 3600
            },
            {
                'id': generate_unique_id(),
                'user_id': user_id_for_workouts,
                'template_id': template_for_daily_2['id'],
                'workout_date': '2025-07-03',
                'date': '2025-07-03',
                'status': 'upcoming',
                'template_name': template_for_daily_2['name'],
                'description': template_for_daily_2['description'],
                'exercises': template_for_daily_2['exercises'][:]
            }
        ]
        print("DEBUG: Додано тестові щоденні тренування.")


# Запускаємо ініціалізацію тестових даних при старті програми
with app.app_context():
    initialize_test_data()


if __name__ == '__main__':
    # Щоб запустити сервер, доступний з інших пристроїв у тій самій локальній мережі,
    # використовуй host='0.0.0.0'.
    # Це означає, що сервер буде слухати на всіх доступних IP-адресах.
    # debug=True корисний для розробки, але ВИМКНИ його для продакшну!
    app.run(host='0.0.0.0', port=5000, debug=True)

    # Якщо ти хочеш запустити його тільки на своєму комп'ютері (за замовчуванням):
    # app.run(debug=True)
