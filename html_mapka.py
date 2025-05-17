import csv
from jinja2 import Template
from datetime import datetime
import requests
import pandas as pd
import json

# URL API hydro2
API_URL = "https://danepubliczne.imgw.pl/api/data/hydro2"
# Plik CSV
CSV_FILE = 'hydro_data.csv'
# Plik GeoJSON granic Polski (w tej samej ścieżce co skrypt)
GEOJSON_FILE = 'poland.geojson'

def fetch_new_data():
    r = requests.get(API_URL)
    return r.json() if r.status_code == 200 else None

def save_new_data(data, csv_file=CSV_FILE):
    pd.DataFrame(data).to_csv(csv_file, index=False, encoding='utf-8-sig')

def refresh_and_save_data():
    new = fetch_new_data()
    if new:
        with open(CSV_FILE, 'w', encoding='utf-8-sig') as f:
            f.truncate(0)
        save_new_data(new)
        return new
    return None

def classify_water_levels(data):
    alarm, warning, normal = [], [], []
    for row in data:
        try:
            lvl = float(row.get('stan', 0))
            if lvl >= 500:      alarm.append(row)
            elif lvl >= 450:    warning.append(row)
            else:               normal.append(row)
        except:
            continue
    return alarm, warning, normal

def generate_html_from_csv(csv_file=CSV_FILE, output_file='hydro_table.html'):
    # 1) Wczytaj dane CSV
    data = []
    with open(csv_file, mode='r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f, delimiter=';')
        for r in reader:
            data.append({k: (v if v != '' else None) for k, v in r.items()})

    # 2) Klasyfikacja stanów
    alarm_state, warning_state, normal_state = classify_water_levels(data)

    # 3) Przygotuj dane do wykresów
    counts = {
        'alarm': len(alarm_state),
        'warning': len(warning_state),
        'normal': len(normal_state)
    }
    levels = [(r['kod_stacji'], float(r['stan'])) 
              for r in data if r.get('stan') is not None]
    top10 = sorted(levels, key=lambda x: x[1], reverse=True)[:10]
    top10_labels = [k for k, _ in top10]
    top10_values = [v for _, v in top10]

    # 4) Wczytaj GeoJSON granic Polski jako Python‐owy dict
    with open(GEOJSON_FILE, 'r', encoding='utf-8') as gf:
        boundary = json.load(gf)

    # 5) Szablon HTML z poprawioną tylko zakładką “Wykresy”
    tpl = Template("""
<!DOCTYPE html>
<html lang="pl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Dane hydrologiczne IMGW (hydro2)</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
  <style>
    /* ... cały Twój dotychczasowy CSS ... */
  </style>
</head>
<body>
  <!-- ... Tytuł, summary, przycisk, zakładki, Tabela i Mapa dokładnie jak wcześniej ... -->

  <!-- Wykresy -->
  <div id="charts" class="tab-content">
    <h2>Liczba stacji wg kategorii</h2>
    <canvas id="stateChart"></canvas>

    <h2>Top 10 stacji wg poziomu</h2>
    <canvas id="top10Chart"></canvas>
  </div>

  <!-- ... footer itp. ... -->

  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <script>
    // ... Twój kod do przełączania zakładek i Leaflet bez zmian ...

    // Chart.js – Liczba stacji wg kategorii
    new Chart(document.getElementById('stateChart'), {
      type: 'bar',
      data: {
        labels: ['Alarmowe','Ostrzegawcze','Normalne'],
        datasets: [{
          label: 'Liczba stacji',
          data: [
            {{ counts.alarm }}, 
            {{ counts.warning }}, 
            {{ counts.normal }}
          ]
        }]
      },
      options: { 
        responsive: true,
        scales: { y: { beginAtZero: true } }
      }
    });

    // Chart.js – Top 10 stacji wg poziomu
    new Chart(document.getElementById('top10Chart'), {
      type: 'bar',
      data: {
        labels: {{ top10_labels|tojson }},
        datasets: [{
          label: 'Poziom wody',
          data: {{ top10_values|tojson }}
        }]
      },
      options: {
        indexAxis: 'y',
        responsive: true,
        scales: { x: { beginAtZero: true } }
      }
    });
  </script>
</body>
</html>
    """)

    rendered = tpl.render(
        data=data,
        alarm_state=alarm_state,
        warning_state=warning_state,
        normal_state=normal_state,
        counts=counts,
        top10_labels=top10_labels,
        top10_values=top10_values,
        boundary=boundary,
        timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    )

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(rendered)
    print(f"✅ Wygenerowano {output_file}")

if __name__ == '__main__':
    generate_html_from_csv()
