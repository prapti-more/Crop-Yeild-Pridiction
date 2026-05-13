import requests
from flask import Flask, render_template, request, redirect, session, url_for
import sqlite3
import pandas as pd

from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split

app = Flask(__name__)
app.secret_key = "secret123"

# =========================
# DATABASE
# =========================

def init_db():

    conn = sqlite3.connect('users.db')
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        password TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS history(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user TEXT,
        input TEXT,
        prediction TEXT,
        land_area REAL,
        current_crop TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS schemes(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        description TEXT
    )
    """)

    conn.commit()
    conn.close()

init_db()

# =========================
# LOAD DATASET
# =========================

df = pd.read_csv("crop_dataset.csv")

# remove null values
df = df.dropna()

# features
X = df[['RAINFALL', 'TEMPERATURE', 'HUMIDITY', 'ph']]

# target
y = df['CROP_PRICE']

# train test split
X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.2,
    random_state=42
)

# model
model = RandomForestRegressor()

# train model
model.fit(X_train, y_train)

# =========================
# HOME
# =========================

@app.route('/')
def home():
    return render_template('home.html')

# =========================
# REGISTER
# =========================

@app.route('/register', methods=['GET', 'POST'])
def register():

    if request.method == 'POST':

        username = request.form['username']
        password = request.form['password']

        conn = sqlite3.connect('users.db')
        cur = conn.cursor()

        cur.execute(
            "INSERT INTO users(username,password) VALUES(?,?)",
            (username, password)
        )

        conn.commit()
        conn.close()

        return redirect(url_for('login'))

    return render_template('register.html')

# =========================
# LOGIN
# =========================

@app.route('/login', methods=['GET', 'POST'])
def login():

    error = None

    if request.method == 'POST':

        username = request.form['username']
        password = request.form['password']

        conn = sqlite3.connect('users.db')
        cur = conn.cursor()

        cur.execute(
            "SELECT * FROM users WHERE username=? AND password=?",
            (username, password)
        )

        user = cur.fetchone()

        conn.close()

        if user:

            session['username'] = username

            return redirect(url_for('dashboard'))

        else:

            error = "Invalid Username or Password"

    return render_template('login.html', error=error)

# =========================
# DASHBOARD
# =========================

@app.route('/dashboard')
def dashboard():

    if 'username' not in session:
        return redirect(url_for('login'))

    return render_template('dashboard.html')

# =========================
# PREDICT
# =========================

@app.route('/predict', methods=['GET', 'POST'])
def predict():

    if 'username' not in session:
        return redirect(url_for('login'))

    states = df['STATE'].unique()

    prediction = None
    suggested_crop = None
    error = None
    custom_message = None

    if request.method == 'POST':

        try:

            state = request.form['state']

            current_crop = request.form['current_crop']

            land_area = float(request.form['land_area'])

            # filter state data
            state_data = df[df['STATE'] == state]

            if len(state_data) == 0:

                error = "State data not found"

            else:

                row = state_data.iloc[0]

                rainfall = row['RAINFALL']
                temperature = row['TEMPERATURE']
                humidity = row['HUMIDITY']
                ph = row['ph']

                # predict
                pred = model.predict([[
                    rainfall,
                    temperature,
                    humidity,
                    ph
                ]])

                prediction = round(pred[0], 2)

                suggested_crop = row['CROP']

                custom_message = f"""
                State: {state}<br>
                Current Crop: {current_crop}<br>
                Rainfall: {rainfall}<br>
                Temperature: {temperature}<br>
                Humidity: {humidity}<br>
                Soil pH: {ph}<br>
                Land Area: {land_area} acres
                """

                # save history
                conn = sqlite3.connect('users.db')
                cur = conn.cursor()

                cur.execute("""
                INSERT INTO history(
                    user,
                    input,
                    prediction,
                    land_area,
                    current_crop
                )
                VALUES(?,?,?,?,?)
                """, (
                    session['username'],
                    state,
                    str(prediction),
                    land_area,
                    current_crop
                ))

                conn.commit()
                conn.close()

        except Exception as e:

            error = str(e)

    return render_template(
        'predict.html',
        states=states,
        prediction=prediction,
        suggested_crop=suggested_crop,
        custom_message=custom_message,
        error=error
    )

# =========================
# HISTORY
# =========================

@app.route('/history')
def history():

    if 'username' not in session:
        return redirect(url_for('login'))

    conn = sqlite3.connect('users.db')
    cur = conn.cursor()

    cur.execute("""
    SELECT input,prediction,land_area,current_crop
    FROM history
    WHERE user=?
    """, (session['username'],))

    rows = cur.fetchall()

    conn.close()

    return render_template('history.html', rows=rows)
#========================
# Download History
#========================
# =========================
# DOWNLOAD HISTORY
# =========================

@app.route('/download')
def download():

    if 'username' not in session:
        return redirect(url_for('login'))

    conn = sqlite3.connect('users.db')
    cur = conn.cursor()

    cur.execute("""
    SELECT input,prediction,land_area,current_crop
    FROM history
    WHERE user=?
    """, (session['username'],))

    rows = cur.fetchall()

    conn.close()

    content = "Prediction History\n\n"

    for row in rows:

        content += f"""
State: {row[0]}
Prediction: {row[1]}
Land Area: {row[2]}
Current Crop: {row[3]}

-------------------------
"""

    return content
# =========================
# WEATHER
# =========================

@app.route('/weather', methods=['GET', 'POST'])
def weather():

    if 'username' not in session:
        return redirect(url_for('login'))

    weather = None
    error_message = None

    if request.method == 'POST':

        city = request.form['city']

        # YOUR API KEY
        api_key = "85ba40e7bab576bfdcca445ef1119e79"

        url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}&units=metric"

        try:

            response = requests.get(url)

            data = response.json()

            if response.status_code == 200:

                weather = {
                    "city": data['name'],
                    "temperature": data['main']['temp'],
                    "humidity": data['main']['humidity'],
                    "description": data['weather'][0]['description']
                }

            else:

                error_message = "City not found or Invalid API Key"

        except Exception as e:

            error_message = str(e)

    return render_template(
        'weather.html',
        weather=weather,
        error_message=error_message
    )

# =========================
# CHATBOT
# =========================

@app.route('/chatbot', methods=['GET', 'POST'])
def chatbot():

    if 'username' not in session:
        return redirect(url_for('login'))

    answer = ""

    if request.method == 'POST':

        q = request.form['question'].lower()

        if "crop" in q:

            answer = "Rice, Wheat and Cotton are best crops."

        elif "fertilizer" in q:

            answer = "Use NPK fertilizers."

        elif "weather" in q:

            answer = "Check weather section."

        else:

            answer = "Ask agriculture related questions."

    return render_template(
        'chatbot.html',
        answer=answer
    )

# =========================
# SCHEMES
# =========================

@app.route('/schemes', methods=['GET', 'POST'])
def schemes():

    all_schemes = [

        {
            "title": "PM-KISAN Scheme",
            "description": "Farmers receive ₹6000 per year financial support from Government."
        },

        {
            "title": "Pradhan Mantri Fasal Bima Yojana",
            "description": "Crop insurance scheme for farmers against natural disasters."
        },

        {
            "title": "Soil Health Card Scheme",
            "description": "Provides soil testing reports and nutrient recommendations."
        },

        {
            "title": "Kisan Credit Card",
            "description": "Farmers can get low-interest agricultural loans."
        },

        {
            "title": "PM Krishi Sinchai Yojana",
            "description": "Improves irrigation facilities and water management."
        },

        {
            "title": "National Agriculture Market (eNAM)",
            "description": "Online trading platform for agricultural commodities."
        }

    ]

    search = ""

    filtered_schemes = all_schemes

    if request.method == 'POST':

        search = request.form['search'].lower()

        filtered_schemes = []

        for scheme in all_schemes:

            if (
                search in scheme['title'].lower()
                or
                search in scheme['description'].lower()
            ):

                filtered_schemes.append(scheme)

    return render_template(
        'schemes.html',
        schemes=filtered_schemes,
        search=search
    )

# =========================
# ADD SCHEME
# =========================

@app.route('/add_scheme', methods=['GET', 'POST'])
def add_scheme():

    if 'username' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':

        title = request.form['title']
        description = request.form['description']

        conn = sqlite3.connect('users.db')
        cur = conn.cursor()

        cur.execute(
            "INSERT INTO schemes(title,description) VALUES(?,?)",
            (title, description)
        )

        conn.commit()
        conn.close()

        return redirect(url_for('schemes'))

    return render_template('add_scheme.html')

# =========================
# ENCYCLOPEDIA
# =========================

@app.route('/encyclopedia')
def encyclopedia():

    if 'username' not in session:
        return redirect(url_for('login'))

    crops = {

        "Rice":
        "Rice needs high rainfall and warm weather.",

        "Wheat":
        "Wheat grows in cool climate.",

        "Cotton":
        "Cotton needs black soil.",

        "Sugarcane":
        "Sugarcane requires high water supply.",

        "Maize":
        "Maize grows in moderate climate."
    }

    return render_template(
        'encyclopedia.html',
        crops=crops
    )

# =========================
# LOGOUT
# =========================

@app.route('/logout')
def logout():

    session.pop('username', None)

    return redirect(url_for('home'))

# =========================
# MAIN
# =========================

if __name__ == '__main__':
    app.run(debug=True)