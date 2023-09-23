from flask import Flask, render_template, request, redirect, url_for
import pymysql
from datetime import date
import bcrypt

app = Flask(__name__)


# MySQL configuration
DB_HOST = 'mayhemgolf.mysql.pythonanywhere-services.com'
DB_USERNAME = 'mayhemgolf'
DB_PASSWORD = '%db12db%'
DB_NAME = 'mayhemgolf$mayhemresult'

# Route to display results
@app.route('/')
def show_results():
    # Connect to MySQL database
    conn = pymysql.connect(host=DB_HOST, user=DB_USERNAME, password=DB_PASSWORD, db=DB_NAME)

    # Retrieve bana and result data from database
    cursor = conn.cursor()
    cursor.execute('SELECT year, bana FROM bana_year')
    bana_data = cursor.fetchall()

    cursor.execute('SELECT year, prize, name FROM mayhem_result_year')
    result_data = cursor.fetchall()

    # Group result data by year and prize
    results_by_year = {}
    for year, prize, name in result_data:
        if year not in results_by_year:
            results_by_year[year] = {}
        if prize not in results_by_year[year]:
            results_by_year[year][prize] = []
        results_by_year[year][prize].append(name)

    # Close database connection
    conn.close()

    # Render template with data
    return render_template('results.html', bana_data=bana_data, results_by_year=results_by_year)

# Route to display player stats
@app.route('/player_stats')
def show_player_stats():
    # Connect to MySQL database
    conn = pymysql.connect(host=DB_HOST, user=DB_USERNAME, password=DB_PASSWORD, db=DB_NAME)
    cursor = conn.cursor()

    # Execute a MySQL query to fetch the data
    cursor.execute("SELECT name, prize FROM mayhem_result_year")
    results = cursor.fetchall()

    # Create a dictionary to store player prizes
    results_by_player = {}

    for player, prize in results:
        results_by_player.setdefault(player, {}).setdefault(prize, 0)
        results_by_player[player][prize] += 1

    # Sort the player statistics by award counts in descending order
    sorted_results_by_player = dict(
        sorted(results_by_player.items(), key=lambda x: (
            x[1].get('first_place', 0),
            x[1].get('second_place', 0),
            x[1].get('third_place', 0),
            x[1].get('longest_drive', 0),
            x[1].get('closest_to_pin', 0)),
            reverse=True
        )
    )

    return render_template('player_stats.html', results_by_player=sorted_results_by_player)


@app.route('/exceltour_events')
def show_exceltour_events():
 # Get the current date
    current_date = date.today()

    # Connect to MySQL database
    conn = pymysql.connect(host=DB_HOST, user=DB_USERNAME, password=DB_PASSWORD, db=DB_NAME)

    # Retrieve events where the current date is within the start and end date range
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM et_events WHERE %s BETWEEN start_date AND end_date', (current_date,))

    # Fetch column names
    column_names = [i[0] for i in cursor.description]

    # Fetch data
    current_events_data = cursor.fetchall()

    # Create a list of dictionaries where keys are column names
    formatted_events_data = [dict(zip(column_names, row)) for row in current_events_data]

    # Fetch all venues separately
    cursor.execute('SELECT DISTINCT venue FROM et_events')
    venues = [row[0] for row in cursor.fetchall()]

    # Fetch player results from the database for all venues
    cursor.execute(
        "SELECT e.venue, p.name, s.score FROM et_eventscore s JOIN et_players p ON s.player_id = p.id "
        "JOIN et_events e ON s.event_id = e.id"
    )
    results = cursor.fetchall()

    # Initialize an empty dictionary to store player results
    player_results = {}

    # Iterate through the results and populate the player_results dictionary
    for venue in venues:
        player_results[venue] = {}
        for venue_name, player_name, score in results:
            if venue_name == venue:
                player_results[venue][player_name] = score

    # Close database connection
    conn.close()

    # Render template with formatted events data and player_results
    return render_template('exceltour_events.html', current_events_data=formatted_events_data, player_results=player_results)


@app.route('/submit_scores', methods=['POST'])
def submit_scores():
    # Get form data from the request
    venue = request.form['venue']
    score = request.form['score']
    phcp = request.form['phcp']
    pcode = request.form['pcode']

    # Connect to the database
    conn = pymysql.connect(host=DB_HOST, user=DB_USERNAME, password=DB_PASSWORD, db=DB_NAME)
    cursor = conn.cursor()

    # Retrieve all player names and hashed passwords from et_players
    cursor.execute('SELECT name, hashed_password FROM et_players')
    players_data = cursor.fetchall()

    found_player = None

    # Iterate through player data to find the correct player
    for player_name, hashed_password in players_data:
        if bcrypt.checkpw(pcode.encode('utf-8'), hashed_password.encode('utf-8')):
            found_player = player_name
            break

    if found_player:
        # Player found; insert the score and phcp into et_eventscore
        # Use INSERT ... ON DUPLICATE KEY UPDATE to update an existing score
        cursor.execute('INSERT INTO et_eventscore (event_id, player_id, score, phcp) '
                       'SELECT e.id, p.id, %s, %s '
                       'FROM et_events AS e '
                       'JOIN et_players AS p ON p.name = %s '
                       'WHERE e.venue = %s '
                       'ON DUPLICATE KEY UPDATE score = VALUES(score), phcp = VALUES(phcp)', (score, phcp, found_player, venue))
        conn.commit()
        conn.close()
        submission_result = "Score submitted/updated successfully."
    else:
        # Handle the case where the password doesn't match any player
        conn.close()
        submission_result = "Incorrect password."

    return redirect(url_for('show_exceltour_events', submission_result=submission_result))

if __name__ == '__main__':
    app.run(debug=True)
