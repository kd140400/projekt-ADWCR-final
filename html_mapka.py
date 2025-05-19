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
        with open(CSV_FILE, 'w', encoding='utf-8-sig') as f:
            f.truncate(0)
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
        reader = csv.DictReader(f)
        for r in reader:
            # zamień klucze z spacji na podkreślenia dla wygody
            cleaned = {}
            for k,v in r.items():
                key = k.replace(' ', '_')
                cleaned[key] = v or None
            data.append(cleaned)

    # 2) Klasyfikacja
    alarm_state, warning_state, normal_state = classify_water_levels(data)

    # 3) Dane do wykresów
    counts = {
        'alarm': len(alarm_state),
        'warning': len(warning_state),
        'normal': len(normal_state)
    }
    levels = []
    for r in data:
        val = r.get('stan')
        if val is not None:
            try:
                levels.append((r.get('kod_stacji') or r.get('kod_stacji'), float(val)))
            except:
                continue
    top10 = sorted(levels, key=lambda x: x[1], reverse=True)[:10]
    top10_codes = [k for k,_ in top10]
    top10_values = [v for _,v in top10]
    station_names = {}
    for r in data:
        code = r.get('kod_stacji')
        name = r.get('nazwa_stacji')
        if code and name:
            station_names[code] = name
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
    unique_names = sorted({r.get('nazwa_stacji') for r in data if r.get('nazwa_stacji')})
    unique_codes = sorted({r.get('kod_stacji') for r in data if r.get('kod_stacji')})

    # 6) Granice Polski
    with open(GEOJSON_FILE, 'r', encoding='utf-8') as gf:
        boundary = json.load(gf)

    # 7) Szablon HTML
    tpl = Template("""
<!DOCTYPE html>
<html lang="pl">
<head>
  <meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Dane hydrologiczne IMGW (hydro2)</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
  <style>
    /* ... tu wklej wszystkie Twoje style ... */
  </style>
</head>
<body>
  <h1>Dane hydrologiczne IMGW (hydro2)</h1>
  <!-- summary, przyciski, zakładki bez zmian -->
  <div class="filters-panel" style="position:absolute;top:60px;right:20px;z-index:1000;background:#fff;padding:10px;max-height:80vh;overflow:auto;">
    <h4>Stan wody:</h4>
    <label><input type="checkbox" class="stateFilter" value="alarm" checked> Alarmowe</label>
    <label><input type="checkbox" class="stateFilter" value="warning" checked> Ostrzegawcze</label>
    <label><input type="checkbox" class="stateFilter" value="normal" checked> Normalne</label>
    <button onclick="filterMarkers()">Filtruj</button>
    <button onclick="resetFilters()">Wyczyść</button>
    <hr>
    <h4>Nazwa stacji:</h4>
    {% for n in unique_names %}
      <label><input type="checkbox" class="nameFilter" value="{{ n }}" checked> {{ n }}</label>
    {% endfor %}
    <button onclick="filterMarkers()">Filtruj</button>
    <button onclick="resetFilters()">Wyczyść</button>
    <hr>
    <h4>Kod stacji:</h4>
    {% for c in unique_codes %}
      <label><input type="checkbox" class="codeFilter" value="{{ c }}" checked> {{ c }}</label>
    {% endfor %}
    <button onclick="filterMarkers()">Filtruj</button>
    <button onclick="resetFilters()">Wyczyść</button>
    <hr>
    <h4>Zakres stanu:</h4>
    <label>od <input type="number" id="minLevel" value="0" style="width:60px"> do <input type="number" id="maxLevel" value="10000" style="width:60px"></label>
    <button onclick="filterMarkers()">Filtruj</button>
    <button onclick="resetFilters()">Wyczyść</button>
  </div>
  <div id="leaflet-map" style="height:600px;border-radius:8px;"></div>
  <!-- reszta Twojego HTML: Tabela i Wykresy bez zmian -->
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-datalabels"></script>
  <script>
    Chart.register(ChartDataLabels);
    // zakładki, generowanie mapy i markerów z boundary
    var map = L.map('leaflet-map').setView([52.0,19.0],6);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{ attribution:'© OSM' }).addTo(map);
    L.geoJSON({{ boundary|tojson }},{style:{color:'#555',weight:1,fill:false}}).addTo(map);
    var stations = {{ data|tojson }};
    var markers = [];
    stations.forEach(s=>{
      if(s.lat && s.lon){
        var cat = s.stan>=500?'alarm':(s.stan>=450?'warning':'normal');
        var m = L.circleMarker([+s.lat,+s.lon],{radius:5,color:cat==='alarm'?'red':(cat==='warning'?'orange':'green')})
          .bindPopup(`<b>${s.kod_stacji} – ${s.nazwa_stacji}</b><br>Stan: ${s.stan}`)
          .addTo(map);
        m.category=cat; m.stationName=s.nazwa_stacji; m.stationCode=s.kod_stacji; m.level=+s.stan;
        markers.push(m);
      }
    });
    // legenda...
    L.control({position:'bottomright'}).onAdd=map=>{let d=L.DomUtil.create('div','legend');d.innerHTML='<i style="background:red"></i>Alarmowe<br><i style="background:orange"></i>Ostrzegawcze<br><i style="background:green"></i>Normalne';return d;}.addTo(map);
    // filtracja:
    function filterMarkers(){
      let selStates=Array.from(document.querySelectorAll('.stateFilter:checked')).map(i=>i.value);
      let selNames=Array.from(document.querySelectorAll('.nameFilter:checked')).map(i=>i.value);
      let selCodes=Array.from(document.querySelectorAll('.codeFilter:checked')).map(i=>i.value);
      let minL=+document.getElementById('minLevel').value, maxL=+document.getElementById('maxLevel').value;
      markers.forEach(m=>{
        let ok=selStates.includes(m.category)&&selNames.includes(m.stationName)&&selCodes.includes(m.stationCode)&&m.level>=minL&&m.level<=maxL;
        ok?map.addLayer(m):map.removeLayer(m);
      });
    }
    function resetFilters(){
      document.querySelectorAll('.stateFilter,.nameFilter,.codeFilter').forEach(cb=>cb.checked=true);
      document.getElementById('minLevel').value=0; document.getElementById('maxLevel').value=10000;
      filterMarkers();
    }
    // wykresy Chart.js tak jak dotychczas...
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
    # odśwież najpierw CSV
    refresh_and_save_data()
    # a potem wygeneruj HTML
    generate_html_from_csv()
