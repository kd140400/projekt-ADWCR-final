import csv
from jinja2 import Template
from datetime import datetime
import requests
import pandas as pd

# URL API hydro2 (przykładowy URL, zastąp rzeczywistym)
API_URL = "https://danepubliczne.imgw.pl/api/data/hydro2"

# Plik, w którym przechowywane są dane
CSV_FILE = 'hydro_data.csv'

def fetch_new_data():
    """Pobieranie nowych danych z API"""
    response = requests.get(API_URL)
    if response.status_code == 200:
        return response.json()  # Zwraca dane w formacie JSON
    else:
        return None

def save_new_data(data, csv_file=CSV_FILE):
    """Zapisuje nowe dane do pliku CSV"""
    df = pd.DataFrame(data)
    df.to_csv(csv_file, index=False, encoding='utf-8-sig')

def refresh_and_save_data():
    """Usuwa stare dane w pliku i zapisuje nowe dane"""
    new_data = fetch_new_data()
    if new_data:
        # Usuwamy stare dane
        with open(CSV_FILE, 'w', encoding='utf-8-sig') as f:
            f.truncate(0)
        # Zapisujemy nowe dane
        save_new_data(new_data)
        return new_data
    return None

def classify_water_levels(data):
    """Klasyfikuje stany wód na podstawie wartości w kolumnie 'stan'"""
    alarm_state = []
    warning_state = []
    normal_state = []
    
    for row in data:
        try:
            if row['stan'] is not None:
                level = float(row['stan'])
                if level >= 500:
                    alarm_state.append(row)
                elif 450 <= level < 500:
                    warning_state.append(row)
                else:
                    normal_state.append(row)
        except (ValueError, TypeError):
            continue
    
    return alarm_state, warning_state, normal_state

def generate_html_from_csv(csv_file='hydro_data.csv', output_file='hydro_table.html'):
    """Generuje HTML z danymi z pliku CSV"""
    # Wczytaj dane z pliku CSV
    data = []
    with open(csv_file, mode='r', encoding='utf-8-sig') as file:
        reader = csv.DictReader(file, delimiter=';')
        for row in reader:
            # Konwersja pustych wartości na None dla lepszego wyświetlania
            cleaned_row = {k: (v if v != '' else None) for k, v in row.items()}
            data.append(cleaned_row)

    # Klasyfikacja stanów wód
    alarm_state, warning_state, normal_state = classify_water_levels(data)

    # Szablon HTML z tabelami danych, mapą i wykresami
    html_template = Template("""
    <!DOCTYPE html>
    <html lang="pl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Dane hydrologiczne IMGW (hydro2)</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }
            h1, h2 { color: #2c3e50; text-align: center; }
            .table-container { overflow-x: auto; margin: 20px 0; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
            table { width: 100%; border-collapse: collapse; font-size: 0.9em; margin-bottom: 20px; }
            th, td { padding: 10px 12px; text-align: left; border-bottom: 1px solid #ddd; }
            th { background-color: #3498db; color: white; position: sticky; top: 0; }
            tr:nth-child(even) { background-color: #f2f2f2; }
            tr:hover { background-color: #e6f7ff; }
            .footer { text-align: center; margin-top: 20px; color: #7f8c8d; font-size: 0.9em; }
            .null-value { color: #999; font-style: italic; }
            .coords { font-family: monospace; }
            .alarm { background-color: #ffdddd; }
            .alarm th { background-color: #ff4444; }
            .warning { background-color: #fff3cd; }
            .warning th { background-color: #ffc107; }
            .summary { display: flex; justify-content: space-around; margin-bottom: 20px; }
            .summary-box { padding: 15px; border-radius: 8px; text-align: center; font-weight: bold; color: white; }
            .alarm-summary { background-color: #ff4444; }
            .warning-summary { background-color: #ffc107; }
            .normal-summary { background-color: #28a745; }
            #refresh-button { position: fixed; top: 20px; right: 20px; padding: 15px 30px; background-color: #3498db; color: white; font-size: 16px; border: none; border-radius: 5px; cursor: pointer; box-shadow: 0 4px 8px rgba(0,0,0,0.2); }
            #refresh-button:hover { background-color: #2980b9; }
            .tabs { display: flex; gap: 10px; margin-top: 20px; }
            .tab-button { padding: 10px 20px; background: #eee; border: none; border-radius: 5px 5px 0 0; cursor: pointer; }
            .tab-button.active { background: white; border-bottom: 2px solid white; }
            .tab-content { display: none; }
            .tab-content.active { display: block; }
        </style>
        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    </head>
    <body>
        <h1>Dane hydrologiczne IMGW (hydro2)</h1>
        
        <div class="summary">
            <div class="summary-box alarm-summary">Stany alarmowe (≥500): {{ alarm_state|length }}</div>
            <div class="summary-box warning-summary">Stany ostrzegawcze (450-499): {{ warning_state|length }}</div>
            <div class="summary-box normal-summary">Stany normalne (<450): {{ normal_state|length }}</div>
        </div>

        <button id="refresh-button" onclick="window.location.href='/refresh'">Odśwież dane</button>

        <!-- Zakładki -->
        <div class="tabs">
            <button class="tab-button active" data-tab="table">Tabela</button>
            <button class="tab-button" data-tab="map">Mapa</button>
            <button class="tab-button" data-tab="charts">Wykresy</button>
        </div>

        <!-- Zakładka: Tabela -->
        <div id="table" class="tab-content active">
            {% if alarm_state %}
            <h2>⚠️ Stany alarmowe (≥500)</h2>
            <div class="table-container alarm">
                <table>
                    <thead>
                        <tr>
                            <th>Kod stacji</th><th>Nazwa stacji</th><th>Współrzędne</th>
                            <th>Stan wody</th><th>Data pomiaru stanu</th>
                            <th>Przepływ</th><th>Data pomiaru przepływu</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for row in alarm_state %}
                        <tr>
                            <td>{{ row['kod_stacji'] if row['kod_stacji'] else '<span class="null-value">brak</span>'|safe }}</td>
                            <td>{{ row['nazwa_stacji'] if row['nazwa_stacji'] else '<span class="null-value">brak</span>'|safe }}</td>
                            <td class="coords">
                                {% if row['lon'] and row['lat'] %}
                                    {{ "%.6f"|format(row['lon']|float) }}, {{ "%.6f"|format(row['lat']|float) }}
                                {% else %}
                                    <span class="null-value">brak</span>
                                {% endif %}
                            </td>
                            <td><strong>{{ row['stan'] }}</strong></td>
                            <td>{{ row['stan_data'] if row['stan_data'] else '<span class="null-value">brak</span>'|safe }}</td>
                            <td>{{ row['przeplyw'] if row['przeplyw'] else '<span class="null-value">brak</span>'|safe }}</td>
                            <td>{{ row['przeplyw_data'] if row['przeplyw_data'] else '<span class="null-value">brak</span>'|safe }}</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
            {% endif %}
            {% if warning_state %}
            <h2>⚠ Stany ostrzegawcze (450-499)</h2>
            <div class="table-container warning">
                <table>
                    <thead>
                        <tr>
                            <th>Kod stacji</th><th>Nazwa stacji</th><th>Współrzędne</th>
                            <th>Stan wody</th><th>Data pomiaru stanu</th>
                            <th>Przepływ</th><th>Data pomiaru przepływu</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for row in warning_state %}
                        <tr>
                            <td>{{ row['kod_stacji'] if row['kod_stacji'] else '<span class="null-value">brak</span>'|safe }}</td>
                            <td>{{ row['nazwa_stacji'] if row['nazwa_stacji'] else '<span class="null-value">brak</span>'|safe }}</td>
                            <td class="coords">
                                {% if row['lon'] and row['lat'] %}
                                    {{ "%.6f"|format(row['lon']|float) }}, {{ "%.6f"|format(row['lat']|float) }}
                                {% else %}
                                    <span class="null-value">brak</span>
                                {% endif %}
                            </td>
                            <td><strong>{{ row['stan'] }}</strong></td>
                            <td>{{ row['stan_data'] if row['stan_data'] else '<span class="null-value">brak</span>'|safe }}</td>
                            <td>{{ row['przeplyw'] if row['przeplyw'] else '<span class="null-value">brak</span>'|safe }}</td>
                            <td>{{ row['przeplyw_data'] if row['przeplyw_data'] else '<span class="null-value">brak</span>'|safe }}</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
            {% endif %}
            <h2>Wszystkie stacje</h2>
            <div class="table-container">
                <table>
                    <thead>
                        <tr>
                            <th>Kod stacji</th><th>Nazwa stacji</th><th>Współrzędne</th>
                            <th>Stan wody</th><th>Data pomiaru stanu</th>
                            <th>Przepływ</th><th>Data pomiaru przepływu</th><th>Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for row in data %}
                        <tr>
                            <td>{{ row['kod_stacji'] if row['kod_stacji'] else '<span class="null-value">brak</span>'|safe }}</td>
                            <td>{{ row['nazwa_stacji'] if row['nazwa_stacji'] else '<span class="null-value">brak</span>'|safe }}</td>
                            <td class="coords">
                                {% if row['lon'] and row['lat'] %}
                                    {{ "%.6f"|format(row['lon']|float) }}, {{ "%.6f"|format(row['lat']|float) }}
                                {% else %}
                                    <span class="null-value">brak</span>
                                {% endif %}
                            </td>
                            <td>
                                {% set lvl = row['stan']|float if row['stan'] else None %}
                                {% if lvl is not none and lvl >= 500 %}<strong style="color:red">{{ row['stan'] }}</strong>
                                {% elif lvl is not none and lvl >= 450 %}<strong style="color:orange">{{ row['stan'] }}</strong>
                                {% else %}{{ row['stan'] or '<span class="null-value">brak</span>'|safe }}{% endif %}
                            </td>
                            <td>{{ row['stan_data'] if row['stan_data'] else '<span class="null-value">brak</span>'|safe }}</td>
                            <td>{{ row['przeplyw'] if row['przeplyw'] else '<span class="null-value">brak</span>'|safe }}</td>
                            <td>{{ row['przeplyw_data'] if row['przeplyw_data'] else '<span class="null-value">brak</span>'|safe }}</td>
                            <td>
                                {% if lvl is not none and lvl >= 500 %}<span style="color:red">ALARM</span>
                                {% elif lvl is not none and lvl >= 450 %}<span style="color:orange">OSTRZEŻENIE</span>
                                {% elif lvl is not none %}<span style="color:green">NORMALNY</span>
                                {% else %}<span class="null-value">brak danych</span>{% endif %}
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Zakładka: Mapa -->
        <div id="map" class="tab-content" style="height: 600px;">
            <div id="leaflet-map" style="width:100%; height:100%;"></div>
        </div>

        <!-- Zakładka: Wykresy -->
        <div id="charts" class="tab-content">
            <canvas id="stateChart"></canvas>
        </div>

        <div class="footer">
            Ostatnia aktualizacja: {{ timestamp }} |
            Liczba rekordów: {{ data|length }} |
            Stany alarmowe: {{ alarm_state|length }} |
            Stany ostrzegawcze: {{ warning_state|length }}
        </div>

        <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <script>
        // Obsługa zakładek
        document.querySelectorAll('.tab-button').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
                document.querySelectorAll('.tab-button').forEach(b => b.classList.remove('active'));
                document.getElementById(btn.dataset.tab).classList.add('active');
                btn.classList.add('active');
            });
        });

        // Inicjalizacja mapy Leaflet
        var map = L.map('leaflet-map').setView([52.0, 19.0], 6);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; OpenStreetMap contributors'
        }).addTo(map);
        fetch('poland.geojson').then(r => r.json()).then(geo => {
            L.geoJSON(geo, { style: { color: '#555', weight: 1 } }).addTo(map);
        });
        var stations = {{ data|tojson }};
        stations.forEach(s => {
            if (s.lon && s.lat) {
                var marker = L.circleMarker([+s.lat, +s.lon], {
                    radius: 6,
                    color: s.stan >= 500 ? 'red' : (s.stan >= 450 ? 'orange' : 'green')
                }).addTo(map);
                marker.bindPopup(
                    '<b>' + (s.nazwa_stacji || '—') + '</b><br>' +
                    'Stan wody: ' + (s.stan || '—') + '<br>' +
                    'Data: ' + (s.stan_data || '—')
                );
            }
        });

        // Wykres Chart.js
        var ctx = document.getElementById('stateChart').getContext('2d');
        new Chart(ctx, {
            type: 'bar',
            data: {
                labels: ['Alarmowe', 'Ostrzegawcze', 'Normalne'],
                datasets: [{
                    label: 'Liczba stacji',
                    data: [
                        {{ alarm_state|length }},
                        {{ warning_state|length }},
                        {{ normal_state|length }}
                    ]
                }]
            },
            options: { responsive: true, scales: { y: { beginAtZero: true } } }
        });
        </script>
    </body>
    </html>
    """)

    # Generuj HTML
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    final_html = html_template.render(
        data=data,
        alarm_state=alarm_state,
        warning_state=warning_state,
        normal_state=normal_state,
        timestamp=timestamp
    )

    # Zapisz do pliku
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(final_html)

    print(f"✅ Wygenerowano plik HTML: {output_file}")

# Funkcja uruchamiająca aplikację
if __name__ == '__main__':
    generate_html_from_csv()
