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
    top10_codes = [k for k, _ in top10]
    top10_values = [v for _, v in top10]
    station_names = {r['kod_stacji']: r['nazwa_stacji'] for r in data}
    top10_labels_full = [f"{k} – {station_names.get(k, k)}" for k in top10_codes]

    # 4) Wczytaj GeoJSON granic Polski
    with open(GEOJSON_FILE, 'r', encoding='utf-8') as gf:
        boundary = json.load(gf)

    # 5) Szablon HTML
    tpl = Template("""
<!DOCTYPE html>
<html lang="pl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Dane hydrologiczne IMGW (hydro2)</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
  <style>
    body{font-family:Arial,sans-serif;margin:20px;background:#f5f5f5;}
    h1,h2{text-align:center;color:#2c3e50;}
    .summary{display:flex;justify-content:space-around;margin:20px 0;}
    .summary-box{padding:15px;border-radius:8px;color:#fff;font-weight:bold;}
    .alarm-summary{background:#e74c3c;} .warning-summary{background:#f1c40f;} .normal-summary{background:#2ecc71;}
    #refresh-button{position:fixed;top:20px;right:20px;padding:10px 20px;
      background:#3498db;color:#fff;border:none;border-radius:5px;cursor:pointer;
      box-shadow:0 4px 8px rgba(0,0,0,0.2);}
    #refresh-button:hover{background:#2980b9;}
    .tabs{display:flex;gap:10px;margin-top:20px;}
    .tab-button{padding:10px 20px;background:#eee;border:none;border-radius:5px 5px 0 0;cursor:pointer;}
    .tab-button.active{background:#fff;border-bottom:2px solid #fff;}
    .tab-content{display:none;} .tab-content.active{display:block;}
    .table-container{overflow-x:auto;background:#fff;padding:20px;margin:20px 0;
      border-radius:8px;box-shadow:0 2px 4px rgba(0,0,0,0.1);}
    table{width:100%;border-collapse:collapse;font-size:0.9em;} 
    th,td{padding:10px;border-bottom:1px solid #ddd;text-align:left;}
    th{background:#3498db;color:#fff;position:sticky;top:0;} 
    tr:nth-child(even){background:#f2f2f2;} tr:hover{background:#e6f7ff;}
    .coords{font-family:monospace;} .null-value{color:#999;font-style:italic;}
    .alarm td{background:#ffdddd;} .warning td{background:#fff3cd;}
    #leaflet-map{width:100%;height:600px;border-radius:8px;
      box-shadow:0 2px 4px rgba(0,0,0,0.1);}
    canvas{max-width:100%;margin:20px 0;}
    .footer{text-align:center;color:#7f8c8d;margin-top:20px;}
  </style>
</head>
<body>
  <h1>Dane hydrologiczne IMGW (hydro2)</h1>
  <div class="summary">
    <div class="summary-box alarm-summary">Alarmowe (≥500): {{ alarm_state|length }}</div>
    <div class="summary-box warning-summary">Ostrz. (450–499): {{ warning_state|length }}</div>
    <div class="summary-box normal-summary">Normalne (<450): {{ normal_state|length }}</div>
  </div>
  <button id="refresh-button" onclick="location.reload()">Odśwież dane</button>

  <div class="tabs">
    <button class="tab-button active" data-tab="table">Tabela</button>
    <button class="tab-button" data-tab="map">Mapa</button>
    <button class="tab-button" data-tab="charts">Wykresy</button>
  </div>

  <!-- Tabela -->
  <div id="table" class="tab-content active">
    <!-- Twoja tabela – bez zmian -->
  </div>

  <!-- Mapa -->
  <div id="map" class="tab-content">
    <div id="leaflet-map"></div>
  </div>

  <!-- Wykresy -->
  <div id="charts" class="tab-content">
    <h2>Liczba stacji wg kategorii</h2>
    <canvas id="stateChart"></canvas>
    <h2>Top 10 stacji wg poziomu</h2>
    <canvas id="top10Chart"></canvas>
  </div>

  <div class="footer">
    Ostatnia aktualizacja: {{ timestamp }} | Rekordów: {{ data|length }}
  </div>

  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-datalabels"></script>
  <script>
    // Zakładki
    document.querySelectorAll('.tab-button').forEach(btn=>{
      btn.addEventListener('click',()=>{
        document.querySelectorAll('.tab-button').forEach(b=>b.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(c=>c.classList.remove('active'));
        btn.classList.add('active');
        document.getElementById(btn.dataset.tab).classList.add('active');
        if(btn.dataset.tab==='map') setTimeout(()=>map.invalidateSize(),200);
      });
    });

    // Leaflet z popupem zawierającym kod i nazwę
    var map = L.map('leaflet-map').setView([52.0,19.0],6);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{
      attribution:'© OpenStreetMap contributors'
    }).addTo(map);
    L.geoJSON({{ boundary|tojson }},{
      style:{color:'#555',weight:1,fill:false}
    }).addTo(map);
    var stations = {{ data|tojson }};
    stations.forEach(s=>{
      if(s.lon && s.lat){
        L.circleMarker([+s.lat,+s.lon],{
          radius:5,
          color: s.stan>=500?'red':(s.stan>=450?'orange':'green')
        }).addTo(map).bindPopup(
          <b>${s.kod_stacji} – ${s.nazwa_stacji}</b><br>+
          Stan: ${s.stan}
        );
      }
    });

    // Pie chart – Liczba stacji wg kategorii z etykietami
    new Chart(document.getElementById('stateChart'), {
      type: 'pie',
      data: {
        labels: ['Alarmowe','Ostrzegawcze','Normalne'],
        datasets: [{
          data: [{{ counts.alarm }}, {{ counts.warning }}, {{ counts.normal }}]
        }]
      },
      options: {
        responsive: true,
        plugins: {
          datalabels: {
            formatter: (value, ctx) => {
              let label = ctx.chart.data.labels[ctx.dataIndex];
              return ${label}: ${value};
            },
            color: '#fff',
            font: { weight: 'bold', size: 14 }
          },
          legend: { position: 'bottom' }
        }
      },
      plugins: [ChartDataLabels]
    });

    // Bar chart – Top 10 stacji wg poziomu
    new Chart(document.getElementById('top10Chart'), {
      type: 'bar',
      data: {
        labels: {{ top10_labels_full|tojson }},
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
        top10_values=top10_values,
        top10_labels_full=top10_labels_full,
        boundary=boundary,
        timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    )
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(rendered)
    print(f"✅ Wygenerowano {output_file}")

if __name__ == '__main__':
    generate_html_from_csv()
