import csv
from jinja2 import Template
from datetime import datetime

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
    # Wczytaj dane z pliku CSV
    data = []
    with open(csv_file, mode='r', encoding='utf-8-sig') as file:
        reader = csv.DictReader(file, delimiter=';')
        for row in reader:
            # Konwersja pustych wartości na None dla lepszego wyświetlania
            cleaned_row = {k: (v if v != '' else None) for k, v in row.items()}
            data.append(cleaned_row)

    # Klasyfikuj stany wód
    alarm_state, warning_state, normal_state = classify_water_levels(data)

    # Szablon HTML z tabelami danych
    html_template = Template("""
    <!DOCTYPE html>
    <html lang="pl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Dane hydrologiczne IMGW (hydro2)</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                margin: 20px;
                background-color: #f5f5f5;
            }
            h1, h2 {
                color: #2c3e50;
                text-align: center;
            }
            .table-container {
                overflow-x: auto;
                margin: 20px 0;
                background: white;
                padding: 20px;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            table {
                width: 100%;
                border-collapse: collapse;
                font-size: 0.9em;
                margin-bottom: 20px;
            }
            th, td {
                padding: 10px 12px;
                text-align: left;
                border-bottom: 1px solid #ddd;
            }
            th {
                background-color: #3498db;
                color: white;
                position: sticky;
                top: 0;
            }
            tr:nth-child(even) {
                background-color: #f2f2f2;
            }
            tr:hover {
                background-color: #e6f7ff;
            }
            .footer {
                text-align: center;
                margin-top: 20px;
                color: #7f8c8d;
                font-size: 0.9em;
            }
            .null-value {
                color: #999;
                font-style: italic;
            }
            .coords {
                font-family: monospace;
            }
            .alarm {
                background-color: #ffdddd;
            }
            .alarm th {
                background-color: #ff4444;
            }
            .warning {
                background-color: #fff3cd;
            }
            .warning th {
                background-color: #ffc107;
            }
            .summary {
                display: flex;
                justify-content: space-around;
                margin-bottom: 20px;
            }
            .summary-box {
                padding: 15px;
                border-radius: 8px;
                text-align: center;
                font-weight: bold;
                color: white;
            }
            .alarm-summary {
                background-color: #ff4444;
            }
            .warning-summary {
                background-color: #ffc107;
            }
            .normal-summary {
                background-color: #28a745;
            }
        </style>
    </head>
    <body>
        <h1>Dane hydrologiczne IMGW (hydro2)</h1>
        
        <div class="summary">
            <div class="summary-box alarm-summary">
                Stany alarmowe (≥500): {{ alarm_state|length }}
            </div>
            <div class="summary-box warning-summary">
                Stany ostrzegawcze (450-499): {{ warning_state|length }}
            </div>
            <div class="summary-box normal-summary">
                Stany normalne (<450): {{ normal_state|length }}
            </div>
        </div>

        {% if alarm_state %}
        <h2>⚠️ Stany alarmowe (≥500)</h2>
        <div class="table-container alarm">
            <table>
                <thead>
                    <tr>
                        <th>Kod stacji</th>
                        <th>Nazwa stacji</th>
                        <th>Współrzędne</th>
                        <th>Stan wody</th>
                        <th>Data pomiaru stanu</th>
                        <th>Przepływ</th>
                        <th>Data pomiaru przepływu</th>
                    </tr>
                </thead>
                <tbody>
                    {% for row in alarm_state %}
                    <tr>
                        <td>{{ row['kod_stacji'] if row['kod_stacji'] is not none else '<span class="null-value">brak</span>'|safe }}</td>
                        <td>{{ row['nazwa_stacji'] if row['nazwa_stacji'] is not none else '<span class="null-value">brak</span>'|safe }}</td>
                        <td class="coords">
                            {% if row['lon'] is not none and row['lat'] is not none %}
                            {{ "%.6f"|format(row['lon']|float) }}, {{ "%.6f"|format(row['lat']|float) }}
                            {% else %}
                            <span class="null-value">brak</span>
                            {% endif %}
                        </td>
                        <td><strong>{{ row['stan'] }}</strong></td>
                        <td>{{ row['stan_data'] if row['stan_data'] is not none else '<span class="null-value">brak</span>'|safe }}</td>
                        <td>{{ row['przeplyw'] if row['przeplyw'] is not none else '<span class="null-value">brak</span>'|safe }}</td>
                        <td>{{ row['przeplyw_data'] if row['przeplyw_data'] is not none else '<span class="null-value">brak</span>'|safe }}</td>
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
                        <th>Kod stacji</th>
                        <th>Nazwa stacji</th>
                        <th>Współrzędne</th>
                        <th>Stan wody</th>
                        <th>Data pomiaru stanu</th>
                        <th>Przepływ</th>
                        <th>Data pomiaru przepływu</th>
                    </tr>
                </thead>
                <tbody>
                    {% for row in warning_state %}
                    <tr>
                        <td>{{ row['kod_stacji'] if row['kod_stacji'] is not none else '<span class="null-value">brak</span>'|safe }}</td>
                        <td>{{ row['nazwa_stacji'] if row['nazwa_stacji'] is not none else '<span class="null-value">brak</span>'|safe }}</td>
                        <td class="coords">
                            {% if row['lon'] is not none and row['lat'] is not none %}
                            {{ "%.6f"|format(row['lon']|float) }}, {{ "%.6f"|format(row['lat']|float) }}
                            {% else %}
                            <span class="null-value">brak</span>
                            {% endif %}
                        </td>
                        <td><strong>{{ row['stan'] }}</strong></td>
                        <td>{{ row['stan_data'] if row['stan_data'] is not none else '<span class="null-value">brak</span>'|safe }}</td>
                        <td>{{ row['przeplyw'] if row['przeplyw'] is not none else '<span class="null-value">brak</span>'|safe }}</td>
                        <td>{{ row['przeplyw_data'] if row['przeplyw_data'] is not none else '<span class="null-value">brak</span>'|safe }}</td>
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
                        <th>Kod stacji</th>
                        <th>Nazwa stacji</th>
                        <th>Współrzędne</th>
                        <th>Stan wody</th>
                        <th>Data pomiaru stanu</th>
                        <th>Przepływ</th>
                        <th>Data pomiaru przepływu</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
                    {% for row in data %}
                    <tr>
                        <td>{{ row['kod_stacji'] if row['kod_stacji'] is not none else '<span class="null-value">brak</span>'|safe }}</td>
                        <td>{{ row['nazwa_stacji'] if row['nazwa_stacji'] is not none else '<span class="null-value">brak</span>'|safe }}</td>
                        <td class="coords">
                            {% if row['lon'] is not none and row['lat'] is not none %}
                            {{ "%.6f"|format(row['lon']|float) }}, {{ "%.6f"|format(row['lat']|float) }}
                            {% else %}
                            <span class="null-value">brak</span>
                            {% endif %}
                        </td>
                        <td>
                            {% if row['stan'] is not none %}
                                {% set level = row['stan']|float %}
                                {% if level >= 500 %}
                                    <strong style="color: red;">{{ row['stan'] }}</strong>
                                {% elif level >= 450 %}
                                    <strong style="color: orange;">{{ row['stan'] }}</strong>
                                {% else %}
                                    {{ row['stan'] }}
                                {% endif %}
                            {% else %}
                                <span class="null-value">brak</span>
                            {% endif %}
                        </td>
                        <td>{{ row['stan_data'] if row['stan_data'] is not none else '<span class="null-value">brak</span>'|safe }}</td>
                        <td>{{ row['przeplyw'] if row['przeplyw'] is not none else '<span class="null-value">brak</span>'|safe }}</td>
                        <td>{{ row['przeplyw_data'] if row['przeplyw_data'] is not none else '<span class="null-value">brak</span>'|safe }}</td>
                        <td>
                            {% if row['stan'] is not none %}
                                {% set level = row['stan']|float %}
                                {% if level >= 500 %}
                                    <span style="color: red;">ALARM</span>
                                {% elif level >= 450 %}
                                    <span style="color: orange;">OSTRZEŻENIE</span>
                                {% else %}
                                    <span style="color: green;">NORMALNY</span>
                                {% endif %}
                            {% else %}
                                <span class="null-value">brak danych</span>
                            {% endif %}
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>

        <div class="footer">
            Ostatnia aktualizacja: {{ timestamp }} | 
            Liczba rekordów: {{ data|length }} | 
            Stany alarmowe: {{ alarm_state|length }} | 
            Stany ostrzegawcze: {{ warning_state|length }}
        </div>
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

if __name__ == '__main__':
    generate_html_from_csv()






### KOD NA MAPE
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
from shapely.geometry import Point
 
# Wczytaj dane z pliku CSV
data = pd.read_csv('hydro_data.csv', delimiter=';')
 
# Wybieramy stacje z poziomem ostrzegawczym (450 ≤ stan < 500)
warning_data = data[data['stan'].between(450, 499, inclusive='left')]
 
# Wybieramy stacje z poziomem alarmowym (stan ≥ 500)
alarm_data = data[data['stan'] >= 500]
 
# Przekształcamy dane na współrzędne geograficzne (Point geometry)
warning_geometry = [Point(xy) for xy in zip(warning_data['lon'], warning_data['lat'])]
alarm_geometry = [Point(xy) for xy in zip(alarm_data['lon'], alarm_data['lat'])]
 
# Tworzymy GeoDataFrame dla stacji ostrzegawczych
warning_gdf = gpd.GeoDataFrame(warning_data, geometry=warning_geometry, crs="EPSG:4326")
 
# Tworzymy GeoDataFrame dla stacji alarmowych
alarm_gdf = gpd.GeoDataFrame(alarm_data, geometry=alarm_geometry, crs="EPSG:4326")
 
# Wczytujemy granice Polski z pliku GeoJSON
poland = gpd.read_file('poland.geojson')  # Zamień na ścieżkę do pliku GeoJSON
 
# Rysujemy mapę Polski
fig, ax = plt.subplots(figsize=(10, 10))
 
# Wyświetlamy granice Polski
poland.plot(ax=ax, color='lightgray')
 
# Rysujemy stacje z poziomem ostrzegawczym (pomarańczowe punkty)
warning_gdf.plot(ax=ax, marker='o', color='orange', markersize=5, label='Poziom Ostrzegawczy')
 
# Rysujemy stacje z poziomem alarmowym (czerwone punkty)
alarm_gdf.plot(ax=ax, marker='o', color='red', markersize=5, label='Poziom Alarmowy')
 
# Dodajemy legendę
plt.legend()
 
# Dodajemy tytuł
plt.title('Stacje z poziomem ostrzegawczym i alarmowym na mapie Polski')
 
# Wyświetlamy mapę
plt.show()
