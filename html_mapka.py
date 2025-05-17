import csv
from jinja2 import Template
from datetime import datetime
import requests
import pandas as pd
import geopandas as gpd
import json

# URL API hydro2
API_URL = "https://danepubliczne.imgw.pl/api/data/hydro2"
# Plik CSV
CSV_FILE = 'hydro_data.csv'
# Plik z granicami Polski
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
            if lvl >= 500: alarm.append(row)
            elif lvl >= 450: warning.append(row)
            else: normal.append(row)
        except:
            continue
    return alarm, warning, normal

def generate_html_from_csv(csv_file=CSV_FILE, output_file='hydro_table.html'):
    # 1) Wczytaj dane do tabeli
    data = []
    with open(csv_file, mode='r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f, delimiter=';')
        for r in reader:
            data.append({k: (v if v != '' else None) for k, v in r.items()})
    alarm_state, warning_state, normal_state = classify_water_levels(data)

    # 2) Wczytaj i zreprojektuj granice Polski do EPSG:4326
    gdf = gpd.read_file(GEOJSON_FILE)
    gdf = gdf.to_crs(epsg=4326)
    boundary_geojson = json.dumps(gdf.__geo_interface__)

    html_template = Template("""
<!DOCTYPE html>
<html lang="pl">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Dane IMGW hydro2</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
  <style>
    body{font-family:Arial,sans-serif;margin:20px;background:#f5f5f5}
    h1,h2{text-align:center;color:#2c3e50}
    .summary{display:flex;justify-content:space-around;margin-bottom:20px}
    .summary-box{padding:15px;border-radius:8px;color:#fff;font-weight:bold}
    .alarm-summary{background:#e74c3c} .warning-summary{background:#f1c40f} .normal-summary{background:#2ecc71}
    #refresh-button{position:fixed;top:20px;right:20px;padding:10px 20px;
      background:#3498db;color:#fff;border:none;border-radius:5px;cursor:pointer;
      box-shadow:0 4px 8px rgba(0,0,0,0.2)}#refresh-button:hover{background:#2980b9}
    .tabs{display:flex;gap:10px;margin-top:20px}
    .tab-button{padding:10px 20px;background:#eee;border:none;border-radius:5px 5px 0 0;cursor:pointer}
    .tab-button.active{background:#fff;border-bottom:2px solid #fff}
    .tab-content{display:none} .tab-content.active{display:block}
    .table-container{overflow-x:auto;background:#fff;padding:20px;margin:20px 0;
      border-radius:8px;box-shadow:0 2px 4px rgba(0,0,0,0.1)}
    table{width:100%;border-collapse:collapse;font-size:0.9em}
    th,td{padding:10px;border-bottom:1px solid #ddd;text-align:left}
    th{background:#3498db;color:#fff;position:sticky;top:0}
    tr:nth-child(even){background:#f2f2f2} tr:hover{background:#e6f7ff}
    .coords{font-family:monospace} .null-value{color:#999;font-style:italic}
    .alarm td{background:#ffdddd} .warning td{background:#fff3cd}
    #leaflet-map{width:100%;height:600px;border-radius:8px;box-shadow:0 2px 4px rgba(0,0,0,0.1)}
    canvas{max-width:100%}
  </style>
</head>
<body>
  <h1>Dane hydrologiczne IMGW (hydro2)</h1>
  <div class="summary">
    <div class="summary-box alarm-summary">Alarmowe (≥500): {{ alarm_state|length }}</div>
    <div class="summary-box warning-summary">Ostrz. (450–499): {{ warning_state|length }}</div>
    <div class="summary-box normal-summary">Normalne (<450): {{ normal_state|length }}</div>
  </div>
  <button id="refresh-button" onclick="window.location.href='/refresh'">Odśwież dane</button>
  <div class="tabs">
    <button class="tab-button active" data-tab="table">Tabela</button>
    <button class="tab-button" data-tab="map">Mapa</button>
    <button class="tab-button" data-tab="charts">Wykresy</button>
  </div>
  <div id="table" class="tab-content active">
    {% if alarm_state %}
      <h2>⚠️ Alarmowe</h2>
      <div class="table-container alarm">
        <table>
          <thead><tr>
            <th>Kod</th><th>Nazwa</th><th>Współrzędne</th>
            <th>Stan</th><th>Data</th><th>Przepływ</th><th>Data przepływu</th>
          </tr></thead>
          <tbody>
          {% for r in alarm_state %}
            <tr>
              <td>{{ r.kod_stacji or '<span class="null-value">brak</span>'|safe }}</td>
              <td>{{ r.nazwa_stacji or '<span class="null-value">brak</span>'|safe }}</td>
              <td class="coords">
                {% if r.lon and r.lat %}
                  {{ "%.6f"|format(r.lon|float) }}, {{ "%.6f"|format(r.lat|float) }}
                {% else %}<span class="null-value">brak</span>{% endif %}
              </td>
              <td><strong>{{ r.stan }}</strong></td>
              <td>{{ r.stan_data or '<span class="null-value">brak</span>'|safe }}</td>
              <td>{{ r.przeplyw or '<span class="null-value">brak</span>'|safe }}</td>
              <td>{{ r.przeplyw_data or '<span class="null-value">brak</span>'|safe }}</td>
            </tr>
          {% endfor %}
          </tbody>
        </table>
      </div>
    {% endif %}
    {% if warning_state %}
      <h2>⚠ Ostrzegawcze</h2>
      ... <!-- analogicznie tabela ostrzegawczych -->
    {% endif %}
    <h2>Wszystkie stacje</h2>
    ... <!-- analogicznie pełna tabela -->
  </div>
  <div id="map" class="tab-content">
    <div id="leaflet-map"></div>
  </div>
  <div id="charts" class="tab-content">
    <canvas id="stateChart"></canvas>
  </div>
  <div class="footer">
    Ostatnia aktualizacja: {{ timestamp }} |
    Rekordów: {{ data|length }} |
    Alarmowych: {{ alarm_state|length }} |
    Ostrzegawczych: {{ warning_state|length }}
  </div>

  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <script>
    // Zakładki
    document.querySelectorAll('.tab-button').forEach(btn=>{
      btn.addEventListener('click', ()=>{
        document.querySelectorAll('.tab-content').forEach(c=>c.classList.remove('active'));
        document.querySelectorAll('.tab-button').forEach(b=>b.classList.remove('active'));
        document.getElementById(btn.dataset.tab).classList.add('active');
        btn.classList.add('active');
        if(btn.dataset.tab==='map') setTimeout(()=>map.invalidateSize(),200);
      });
    });

    // Inicjalizacja Leaflet z prawidłowymi granicami
    var map = L.map('leaflet-map').setView([52.0,19.0],6);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{attribution:'© OpenStreetMap contributors'}).addTo(map);
    var boundary = {{ boundary_geojson|safe }};
    L.geoJSON(boundary, {style:{color:'#555',weight:1,fill:false}}).addTo(map);

    // Markery stacji
    var stations = {{ data|tojson }};
    stations.forEach(s=>{
      if(s.lon&&s.lat){
        var m=L.circleMarker([+s.lat,+s.lon],{radius:5,
            color: s.stan>=500?'red':(s.stan>=450?'orange':'green')
        }).addTo(map);
        m.bindPopup(
          `<b>${s.nazwa_stacji||'—'}</b><br>`+
          `Stan: ${s.stan||'—'}<br>`+
          `Data: ${s.stan_data||'—'}`
        );
      }
    });

    // Chart.js
    var ctx=document.getElementById('stateChart').getContext('2d');
    new Chart(ctx,{
      type:'bar',
      data:{
        labels:['Alarmowe','Ostrzegawcze','Normalne'],
        datasets:[{label:'Liczba stacji',
          data:[
            {{ alarm_state|length }},
            {{ warning_state|length }},
            {{ normal_state|length }}
          ]
        }]
      },
      options:{responsive:true,scales:{y:{beginAtZero:true}}}
    });
  </script>
</body>
</html>
    """)

    rendered = html_template.render(
        data=data,
        alarm_state=alarm_state,
        warning_state=warning_state,
        normal_state=normal_state,
        timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        boundary_geojson=boundary_geojson
    )
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(rendered)
    print(f"✅ Wygenerowano {output_file}")

if __name__ == '__main__':
    generate_html_from_csv()
