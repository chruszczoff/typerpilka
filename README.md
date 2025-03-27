# Aplikacja do Typowania Meczów Piłkarskich

Aplikacja webowa do typowania wyników meczów piłkarskich z różnych lig europejskich. Aplikacja wykorzystuje API-Football do pobierania danych o meczach i zawiera funkcje do analizy statystyk oraz historii typowania.

## Funkcje

- Pobieranie danych o meczach z API-Football
- Typowanie wyników meczów
- Statystyki skuteczności typowania
- Analiza czynników wpływających na wyniki
- Historia typów
- Wizualizacja danych

## Wymagania

- Python 3.8+
- Klucz API do API-Football

## Instalacja

1. Sklonuj repozytorium:
```bash
git clone [adres-repozytorium]
cd [nazwa-katalogu]
```

2. Zainstaluj wymagane pakiety:
```bash
pip install -r requirements.txt
```

3. Skonfiguruj klucz API:
- Otwórz plik `.env`
- Zastąp `your_api_key_here` swoim kluczem API z API-Football

## Uruchomienie

1. Uruchom aplikację:
```bash
python app.py
```

2. Otwórz przeglądarkę i przejdź pod adres:
```
http://localhost:5000
```

## Struktura projektu

```
.
├── app.py              # Główny plik aplikacji
├── requirements.txt    # Zależności projektu
├── .env               # Konfiguracja klucza API
├── templates/         # Szablony HTML
│   ├── index.html
│   ├── predictions.html
│   ├── statistics.html
│   └── analysis.html
└── football_predictions.db  # Baza danych SQLite
```

## Wspierane ligi

- Premier League (Anglia)
- Bundesliga (Niemcy)
- Ekstraklasa (Polska)
- Serie A (Włochy)
- La Liga (Hiszpania)
- Ligue 1 (Francja)

## Licencja

MIT 