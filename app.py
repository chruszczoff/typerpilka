from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
import requests
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
import json
import time

load_dotenv()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///football_predictions.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Modele bazy danych
class Match(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    league_id = db.Column(db.Integer)
    home_team = db.Column(db.String(100))
    away_team = db.Column(db.String(100))
    home_team_id = db.Column(db.Integer)  # Dodajemy ID drużyny gospodarzy
    away_team_id = db.Column(db.Integer)  # Dodajemy ID drużyny gości
    date = db.Column(db.DateTime)
    home_score = db.Column(db.Integer)
    away_score = db.Column(db.Integer)
    prediction = db.Column(db.String(10))
    actual_result = db.Column(db.String(10))
    home_form = db.Column(db.String(10))  # Ostatnie 5 meczów
    away_form = db.Column(db.String(10))  # Ostatnie 5 meczów
    home_goals_scored = db.Column(db.Integer)
    home_goals_conceded = db.Column(db.Integer)
    away_goals_scored = db.Column(db.Integer)
    away_goals_conceded = db.Column(db.Integer)

class Prediction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    match_id = db.Column(db.Integer, db.ForeignKey('match.id'))
    prediction = db.Column(db.String(10))
    confidence = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Konfiguracja API
API_KEY = os.getenv('API_FOOTBALL_KEY')
BASE_URL = 'https://v3.football.api-sports.io'

# Lista lig
LEAGUES = {
    'Premier League': 39,
    'Bundesliga': 78,
    'Ekstraklasa': 106,
    'Serie A': 135,
    'La Liga': 140,
    'Ligue 1': 61
}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/predictions')
def predictions():
    print("\nPobieram nadchodzące mecze...")
    # Pobierz nadchodzące mecze
    upcoming_matches = Match.query.filter(
        Match.date > datetime.utcnow()
    ).order_by(Match.date).all()
    
    print(f"Znaleziono {len(upcoming_matches)} nadchodzących meczów")
    
    headers = {
        'x-apisports-key': API_KEY,
        'x-apisports-host': 'v3.football.api-sports.io',
        'Accept': 'application/json'
    }
    
    predictions_data = []
    for match in upcoming_matches:
        print(f"\nAnalizuję mecz: {match.home_team} vs {match.away_team}")
        print(f"Data meczu: {match.date}")
        print(f"Liga ID: {match.league_id}")
        analysis = analyze_match(match, headers)
        predictions_data.append({
            'match': match,
            'analysis': analysis
        })
    
    return render_template('predictions.html', predictions=predictions_data)

@app.route('/statistics')
def statistics():
    # Pobierz statystyki
    total_matches = Match.query.count()
    correct_predictions = Match.query.filter(
        Match.prediction == Match.actual_result
    ).count()
    
    # Statystyki per liga
    league_stats = {}
    for league_name, league_id in LEAGUES.items():
        league_matches = Match.query.filter_by(league_id=league_id).all()
        if league_matches:
            correct = sum(1 for m in league_matches if m.prediction == m.actual_result)
            league_stats[league_name] = {
                'total': len(league_matches),
                'correct': correct,
                'percentage': round((correct / len(league_matches)) * 100, 2)
            }
    
    return render_template('statistics.html', 
                         total_matches=total_matches,
                         correct_predictions=correct_predictions,
                         league_stats=league_stats)

@app.route('/analysis')
def analysis():
    return render_template('analysis.html')

def check_match_results(headers):
    print("\nSprawdzam wyniki zakończonych meczów...")
    
    # Pobierz mecze z ostatnich 24 godzin
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    today = datetime.now().strftime('%Y-%m-%d')
    
    for league_name, league_id in LEAGUES.items():
        print(f"\nSprawdzam wyniki z ligi: {league_name} (ID: {league_id})")
        url = f"{BASE_URL}/fixtures"
        params = {
            'league': league_id,
            'season': 2024,
            'from': yesterday,
            'to': today,
            'timezone': 'Europe/Warsaw'
        }
        
        try:
            response = requests.get(url, headers=headers, params=params)
            if response.status_code == 200:
                data = response.json()
                if 'response' not in data:
                    continue
                    
                matches = data['response']
                for match in matches:
                    # Sprawdź czy mecz jest zakończony (status FT - Full Time)
                    if match['fixture']['status']['short'] == 'FT':
                        # Znajdź mecz w bazie danych
                        db_match = Match.query.filter_by(
                            league_id=league_id,
                            home_team=match['teams']['home']['name'],
                            away_team=match['teams']['away']['name'],
                            date=datetime.strptime(match['fixture']['date'], '%Y-%m-%dT%H:%M:%S%z')
                        ).first()
                        
                        if db_match and db_match.actual_result is None:
                            # Aktualizuj wynik
                            home_score = match['goals']['home']
                            away_score = match['goals']['away']
                            
                            if home_score > away_score:
                                actual_result = '1'
                            elif home_score < away_score:
                                actual_result = '2'
                            else:
                                actual_result = '0'
                                
                            db_match.home_score = home_score
                            db_match.away_score = away_score
                            db_match.actual_result = actual_result
                            
                            print(f"Zaktualizowano wynik: {db_match.home_team} {home_score}-{away_score} {db_match.away_team}")
                            print(f"Typ: {db_match.prediction}, Wynik: {actual_result}")
                            
            time.sleep(1)  # Opóźnienie między zapytaniami
            
        except Exception as e:
            print(f"Błąd podczas sprawdzania wyników dla ligi {league_name}: {str(e)}")
            continue
    
    try:
        db.session.commit()
        print("Zapisano zaktualizowane wyniki do bazy danych")
    except Exception as e:
        print(f"Błąd podczas zapisywania wyników do bazy danych: {str(e)}")
        db.session.rollback()

@app.route('/fetch_data', methods=['POST'])
def fetch_data():
    headers = {
        'x-apisports-key': API_KEY,
        'x-apisports-host': 'v3.football.api-sports.io',
        'Accept': 'application/json'
    }
    
    print("Rozpoczynam pobieranie danych...")
    print(f"Używam klucza API: {API_KEY[:5]}...")
    
    # Najpierw sprawdź wyniki zakończonych meczów
    check_match_results(headers)
    
    # Następnie pobierz nowe mecze
    matches_count = 0
    
    if not API_KEY:
        print("Błąd: Nie skonfigurowano klucza API!")
        return jsonify({'status': 'error', 'message': 'Nie skonfigurowano klucza API'})
    
    # Pobierz dzisiejszą datę
    today = datetime.now().strftime('%Y-%m-%d')
    print(f"Pobieram mecze na datę: {today}")
    
    for league_name, league_id in LEAGUES.items():
        print(f"\nPobieram mecze z ligi: {league_name} (ID: {league_id})")
        url = f"{BASE_URL}/fixtures"
        params = {
            'league': league_id,
            'season': 2024,  # Aktualny sezon 2024/2025
            'date': today,
            'timezone': 'Europe/Warsaw'
        }
        print(f"URL: {url}")
        print(f"Parametry: {params}")
        
        try:
            response = requests.get(url, headers=headers, params=params)
            print(f"Status odpowiedzi dla {league_name}: {response.status_code}")
            print(f"Odpowiedź: {response.text[:200]}...")  # Wyświetl pierwsze 200 znaków odpowiedzi
            
            if response.status_code == 200:
                data = response.json()
                if 'response' not in data:
                    print(f"Brak klucza 'response' w odpowiedzi dla {league_name}")
                    continue
                    
                matches = data['response']
                print(f"Znaleziono {len(matches)} meczów w lidze {league_name}")
                
                for match in matches:
                    try:
                        print(f"\nPrzetwarzam mecz: {match['teams']['home']['name']} vs {match['teams']['away']['name']}")
                        # Pobierz statystyki drużyn
                        home_team_id = match['teams']['home']['id']
                        away_team_id = match['teams']['away']['id']
                        
                        # Pobierz formę drużyn
                        home_form = get_team_form(headers, home_team_id)
                        away_form = get_team_form(headers, away_team_id)
                        
                        # Pobierz statystyki bramkowe
                        home_stats = get_team_stats(headers, home_team_id)
                        away_stats = get_team_stats(headers, away_team_id)
                        
                        # Utwórz obiekt meczu
                        new_match = Match(
                            league_id=league_id,
                            home_team=match['teams']['home']['name'],
                            away_team=match['teams']['away']['name'],
                            home_team_id=home_team_id,  # Dodajemy ID drużyny gospodarzy
                            away_team_id=away_team_id,  # Dodajemy ID drużyny gości
                            date=datetime.strptime(match['fixture']['date'], '%Y-%m-%dT%H:%M:%S%z'),
                            home_score=match['goals']['home'] if match['goals']['home'] is not None else None,
                            away_score=match['goals']['away'] if match['goals']['away'] is not None else None,
                            home_form=home_form,
                            away_form=away_form,
                            home_goals_scored=home_stats['goals_scored'],
                            home_goals_conceded=home_stats['goals_conceded'],
                            away_goals_scored=away_stats['goals_scored'],
                            away_goals_conceded=away_stats['goals_conceded']
                        )
                        
                        # Wykonaj analizę i zapisz typ
                        analysis = analyze_match(new_match, headers)
                        new_match.prediction = analysis['prediction']
                        
                        db.session.add(new_match)
                        matches_count += 1
                        print(f"Dodano mecz: {new_match.home_team} vs {new_match.away_team} (Typ: {new_match.prediction})")
                        
                        # Dodaj opóźnienie między zapytaniami
                        time.sleep(1)
                        
                    except Exception as e:
                        print(f"Błąd podczas przetwarzania meczu: {str(e)}")
                        continue
                        
            elif response.status_code == 429:
                print(f"Przekroczono limit zapytań dla ligi {league_name}. Czekam 60 sekund...")
                time.sleep(60)
                continue
            else:
                print(f"Błąd podczas pobierania danych dla ligi {league_name}: {response.status_code}")
                print(f"Odpowiedź: {response.text}")
                
        except Exception as e:
            print(f"Błąd podczas pobierania danych dla ligi {league_name}: {str(e)}")
            continue
    
    try:
        db.session.commit()
        print(f"Zapisano {matches_count} meczów do bazy danych")
    except Exception as e:
        print(f"Błąd podczas zapisywania do bazy danych: {str(e)}")
        db.session.rollback()
    
    return jsonify({'status': 'success', 'matches_count': matches_count})

def get_team_form(headers, team_id):
    url = f"{BASE_URL}/fixtures"
    params = {
        'team': team_id,
        'last': 5,
        'season': 2024  # Dodajemy sezon
    }
    response = requests.get(url, headers=headers, params=params)
    
    if response.status_code == 200:
        data = response.json()
        if 'response' not in data:
            print(f"Brak klucza 'response' w odpowiedzi dla formy drużyny {team_id}")
            return ''
            
        matches = data['response']
        form = []
        for match in matches:
            if match['teams']['home']['id'] == team_id:
                if match['goals']['home'] is not None and match['goals']['away'] is not None:
                    if match['goals']['home'] > match['goals']['away']:
                        form.append('W')
                    elif match['goals']['home'] == match['goals']['away']:
                        form.append('R')
                    else:
                        form.append('P')
            else:
                if match['goals']['home'] is not None and match['goals']['away'] is not None:
                    if match['goals']['away'] > match['goals']['home']:
                        form.append('W')
                    elif match['goals']['away'] == match['goals']['home']:
                        form.append('R')
                    else:
                        form.append('P')
        return ''.join(form)
    return ''

def get_team_stats(headers, team_id):
    url = f"{BASE_URL}/fixtures"
    params = {
        'team': team_id,
        'last': 5,
        'season': 2024
    }
    response = requests.get(url, headers=headers, params=params)
    
    if response.status_code == 200:
        data = response.json()
        if 'response' not in data:
            print(f"Brak klucza 'response' w odpowiedzi dla statystyk drużyny {team_id}")
            return {'goals_scored': 0, 'goals_conceded': 0, 'shots_on_target': 0, 'home_form': '', 'away_form': ''}
            
        matches = data['response']
        goals_scored = 0
        goals_conceded = 0
        shots_on_target = 0
        home_form = []
        away_form = []
        
        for match in matches:
            if match['teams']['home']['id'] == team_id:
                if match['goals']['home'] is not None:
                    goals_scored += match['goals']['home']
                if match['goals']['away'] is not None:
                    goals_conceded += match['goals']['away']
                if 'statistics' in match and match['statistics']:
                    for stat in match['statistics']:
                        if stat['type'] == 'Shots on Goal':
                            shots_on_target += int(stat['value'])
                home_form.append('W' if match['goals']['home'] > match['goals']['away'] else 'R' if match['goals']['home'] == match['goals']['away'] else 'P')
            else:
                if match['goals']['away'] is not None:
                    goals_scored += match['goals']['away']
                if match['goals']['home'] is not None:
                    goals_conceded += match['goals']['home']
                if 'statistics' in match and match['statistics']:
                    for stat in match['statistics']:
                        if stat['type'] == 'Shots on Goal':
                            shots_on_target += int(stat['value'])
                away_form.append('W' if match['goals']['away'] > match['goals']['home'] else 'R' if match['goals']['away'] == match['goals']['home'] else 'P')
                    
        print(f"\nStatystyki z ostatnich 5 meczów dla drużyny {team_id}:")
        print(f"Gole strzelone: {goals_scored}")
        print(f"Gole stracone: {goals_conceded}")
        print(f"Strzały na bramkę: {shots_on_target}")
        print(f"Forma u siebie: {''.join(home_form)}")
        print(f"Forma na wyjeździe: {''.join(away_form)}")
            
        return {
            'goals_scored': goals_scored,
            'goals_conceded': goals_conceded,
            'shots_on_target': shots_on_target,
            'home_form': ''.join(home_form),
            'away_form': ''.join(away_form)
        }
    return {'goals_scored': 0, 'goals_conceded': 0, 'shots_on_target': 0, 'home_form': '', 'away_form': ''}

def get_head_to_head(headers, home_team_id, away_team_id):
    url = f"{BASE_URL}/fixtures/headtohead"
    params = {
        'h2h': f"{home_team_id}-{away_team_id}",
        'season': 2024
    }
    response = requests.get(url, headers=headers, params=params)
    
    if response.status_code == 200:
        data = response.json()
        if 'response' not in data:
            return {'home_wins': 0, 'away_wins': 0, 'draws': 0, 'total_matches': 0}
            
        matches = data['response']
        home_wins = 0
        away_wins = 0
        draws = 0
        
        for match in matches:
            if match['fixture']['status']['short'] == 'FT':
                if match['teams']['home']['id'] == home_team_id:
                    if match['goals']['home'] > match['goals']['away']:
                        home_wins += 1
                    elif match['goals']['home'] < match['goals']['away']:
                        away_wins += 1
                    else:
                        draws += 1
                else:
                    if match['goals']['away'] > match['goals']['home']:
                        home_wins += 1
                    elif match['goals']['away'] < match['goals']['home']:
                        away_wins += 1
                    else:
                        draws += 1
                        
        return {
            'home_wins': home_wins,
            'away_wins': away_wins,
            'draws': draws,
            'total_matches': len(matches)
        }
    return {'home_wins': 0, 'away_wins': 0, 'draws': 0, 'total_matches': 0}

def analyze_match(match, headers):
    # Pobierz statystyki drużyn
    home_stats = get_team_stats(headers, match.home_team_id)
    away_stats = get_team_stats(headers, match.away_team_id)
    
    # Pobierz statystyki bezpośrednich pojedynków
    h2h = get_head_to_head(headers, match.home_team_id, match.away_team_id)
    
    # Oblicz formę (ostatnie 5 meczów)
    home_recent_form = match.home_form[-5:] if match.home_form else ''
    away_recent_form = match.away_form[-5:] if match.away_form else ''
    
    # Oblicz punkty za formę (zwiększona waga dla ostatnich meczów)
    home_form_score = calculate_form_score(home_recent_form)
    away_form_score = calculate_form_score(away_recent_form)
    
    # Oblicz punkty za statystyki bramkowe (normalizacja względem średniej)
    home_attack = home_stats['goals_scored'] / 10 if home_stats['goals_scored'] else 0
    home_defense = 1 - (home_stats['goals_conceded'] / 10) if home_stats['goals_conceded'] else 0
    away_attack = away_stats['goals_scored'] / 10 if away_stats['goals_scored'] else 0
    away_defense = 1 - (away_stats['goals_conceded'] / 10) if away_stats['goals_conceded'] else 0
    
    # Oblicz punkty za strzały na bramkę (normalizacja względem średniej)
    home_shots = home_stats['shots_on_target'] / 20 if home_stats['shots_on_target'] else 0
    away_shots = away_stats['shots_on_target'] / 20 if away_stats['shots_on_target'] else 0
    
    # Oblicz punkty za formę u siebie/wyjazdach
    home_home_form = calculate_form_score(home_stats['home_form'])
    away_away_form = calculate_form_score(away_stats['away_form'])
    
    # Oblicz punkty za bezpośrednie pojedynki (zwiększona waga dla ostatnich spotkań)
    h2h_home = h2h['home_wins'] / h2h['total_matches'] if h2h['total_matches'] > 0 else 0.5
    h2h_away = h2h['away_wins'] / h2h['total_matches'] if h2h['total_matches'] > 0 else 0.5
    
    # Oblicz końcowe punkty (zmienione wagi)
    home_score = (
        home_form_score * 0.35 +     # Forma (35%)
        home_attack * 0.15 +         # Atak (15%)
        home_defense * 0.15 +        # Obrona (15%)
        home_shots * 0.1 +           # Strzały (10%)
        home_home_form * 0.15 +      # Forma u siebie (15%)
        h2h_home * 0.1              # Bezpośrednie pojedynki (10%)
    )
    
    away_score = (
        away_form_score * 0.35 +     # Forma (35%)
        away_attack * 0.15 +         # Atak (15%)
        away_defense * 0.15 +        # Obrona (15%)
        away_shots * 0.1 +           # Strzały (10%)
        away_away_form * 0.15 +      # Forma na wyjeździe (15%)
        h2h_away * 0.1              # Bezpośrednie pojedynki (10%)
    )
    
    # Oblicz różnicę w punktach
    score_diff = home_score - away_score
    
    # Określ typ i pewność (zmienione progi i sposób obliczania pewności)
    if score_diff > 0.15:  # Zwiększony próg dla zwycięstwa gospodarzy
        prediction = '1'
        confidence = min(abs(score_diff) * 150, 90)  # Zwiększona skala i maksymalna pewność
    elif score_diff < -0.15:  # Zwiększony próg dla zwycięstwa gości
        prediction = '2'
        confidence = min(abs(score_diff) * 150, 90)  # Zwiększona skala i maksymalna pewność
    else:
        prediction = '0'
        # Oblicz pewność remisu na podstawie bliskości wyników
        closeness = 1 - (abs(score_diff) / 0.15)
        confidence = 60 + (closeness * 30)  # Od 60% do 90% w zależności od bliskości wyników
    
    # Dodatkowe czynniki wpływające na pewność
    if prediction in ['1', '2']:
        # Sprawdź spójność formy
        if prediction == '1' and home_recent_form.count('W') >= 2:
            confidence += 5
        elif prediction == '2' and away_recent_form.count('W') >= 2:
            confidence += 5
            
        # Sprawdź przewagę w bezpośrednich pojedynkach
        if prediction == '1' and h2h_home > 0.6:
            confidence += 5
        elif prediction == '2' and h2h_away > 0.6:
            confidence += 5
            
        # Sprawdź przewagę w strzałach
        if prediction == '1' and home_shots > away_shots * 1.5:
            confidence += 5
        elif prediction == '2' and away_shots > home_shots * 1.5:
            confidence += 5
    
    # Ogranicz pewność do 90%
    confidence = min(confidence, 90)
    
    return {
        'prediction': prediction,
        'confidence': round(confidence, 2),
        'factors': {
            'form': f'Forma gospodarzy (5 ostatnich): {home_recent_form}, Forma gości (5 ostatnich): {away_recent_form}',
            'goals': f'Gospodarze: {home_stats["goals_scored"]}/{home_stats["goals_conceded"]}, Goście: {away_stats["goals_scored"]}/{away_stats["goals_conceded"]}',
            'shots': f'Strzały na bramkę - Gospodarze: {home_stats["shots_on_target"]}, Goście: {away_stats["shots_on_target"]}',
            'h2h': f'Bezpośrednie pojedynki - Gospodarze: {h2h["home_wins"]}W {h2h["draws"]}R {h2h["away_wins"]}P',
            'scores': f'Gospodarze: {round(home_score, 2)}, Goście: {round(away_score, 2)}'
        }
    }

def calculate_form_score(form):
    if not form:
        return 0.5
    score = 0
    for result in form:
        if result == 'W':
            score += 1
        elif result == 'R':
            score += 0.5
    return score / len(form)

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False) 