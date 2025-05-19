import csv
from jinja2 import Template
from datetime import datetime
import requests
import pandas as pd
import json
import statistics

# URL API hydro2
API_URL = "https://danepubliczne.imgw.pl/api/data/hydro2"
# Plik CSV
CSV_FILE = 'hydro_data.csv'
# Plik GeoJSON granic Polski
GEOJSON_FILE = 'poland.geojson'

def fetch_new_data():
    r = requests.get(API_URL)
    return r.json() if r.status_code == 200 else None

def save_new_data(data, csv_file=CSV_FILE):
    pd.DataFrame(data).to_csv(csv_file, index=False, encoding='utf-8-sig')

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
    alarm, warning, normal = [], [], []
    for row in data:
        try:
            lvl = float(row.get('stan', 0))
            if lvl >= 500:
                alarm.append(row)
            elif lvl >= 450:
                warning.append(row)
            else:
                normal.append(row)
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

    # 2) Klasyfikacja
    alarm_state, warning_state, normal_state = classify_water_levels(data)

    # 3) Dane do wykresów
    counts = {
        'alarm': len(alarm_state),
        'warning': len(warning_state),
        'normal': len(normal_state)
    }
    levels = [(r['kod_stacji'], float(r['stan']))
              for r in data if r.get('stan') is not None]
    top10 = sorted(levels, key=lambda x: x[1], reverse=True)[:10]
    top10_codes = [k for k, _ in top10]
    top10_values = [v for _, v in top10]
    station_names = {r['kod_stacji']: r['nazwa_stacji'] for r in data}
    top10_labels_full = [f"{k} – {station_names.get(k, k)}" for k in top10_codes]

    # 4) Statystyki
    numeric = [float(r['stan']) for r in data if r.get('stan') is not None]
    stats = {
        'Liczba pomiarów': len(numeric),
        'Min': f"{min(numeric):.2f}",
        'Max': f"{max(numeric):.2f}",
        'Średnia': f"{statistics.mean(numeric):.2f}",
        'Mediana': f"{statistics.median(numeric):.2f}"
    }

    # 5) Unikalne nazwy i kody (dla filtrów)
    unique_names = sorted({r['nazwa_stacji'] for r in data if r.get('nazwa_stacji')})
    unique_codes = sorted({r['kod_stacji'] for r in data if r.get('kod_stacji')})

    # 6) Granice Polski
    with open(GEOJSON_FILE, 'r', encoding='utf-8') as gf:
        boundary = json.load(gf)

    # 7) Szablon HTML
    tpl = Template("""
<!DOCTYPE html>
<html lang="pl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Dane hydrologiczne IMGW (hydro2)</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
  <style>
    /* ... wszystkie dotychczasowe style bez zmian ... */
  </style>
</head>
<body>
  <!-- ... reszta szablonu bez zmian, włączając Tabelę, Mapę z filtrami i Wykresy ... -->
  <script>
    // Zakładki, Leaflet, filtry, wykresy – bez zmian
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
        top10_values=top10_values,
        top10_labels_full=top10_labels_full,
        stats=stats,
        unique_names=unique_names,
        unique_codes=unique_codes,
        boundary=boundary,
        timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    )
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(rendered)
    print(f"✅ Wygenerowano {output_file}")

if __name__ == '__main__':
    # najpierw odśwież dane
    refresh_and_save_data()
    # potem wygeneruj stronę
    generate_html_from_csv()
