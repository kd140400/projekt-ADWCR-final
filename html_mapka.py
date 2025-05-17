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

def fetch_new_data():
    r = requests.get(API_URL)
    return r.json() if r.status_code == 200 else None

def save_new_data(data, csv_file=CSV_FILE):
    pd.DataFrame(data).to_csv(csv_file, index=False, encoding='utf-8-sig')

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
    # Wczytaj dane
    data = []
    with open(csv_file, mode='r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f, delimiter=';')
        for r in reader:
            data.append({k: (v if v != '' else None) for k, v in r.items()})
    alarm_state, warning_state, normal_state = classify_water_levels(data)

    # Top10 stacji wg poziomu
    levels = [(r['kod_stacji'], float(r['stan'])) for r in data if r.get('stan') is not None]
    top10 = sorted(levels, key=lambda x: x[1], reverse=True)[:10]
    top10_keys = [k for k, v in top10]
    top10_vals = [v for k, v in top10]

    # Średni poziom (gauge)
    vals = [float(r['stan']) for r in data if r.get('stan') is not None]
    avg_level = sum(vals) / len(vals) if vals else 0

    # Dane historyczne (tu: tylko jeden punkt, można rozbudować)
    history_data = {
        r['kod_stacji']: {
            'dates': [r['stan_data']],
            'levels': [float(r['stan'])] if r.get('stan') is not None else [0]
        }
        for r in data if r.get('kod_stacji') and r.get('stan_data')
    }

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
    .tabs{display:flex;gap:10px;margin-top:20px;}
    .tab-button{padding:10px 20px;background:#eee;border:none;border-radius:5px 5px 0 0;cursor:pointer;}
    .tab-button.active{background:#fff;border-bottom:2px solid #fff;}
    .tab-content{display:none;} .tab-content.active{display:block;}
    .table-container{overflow-x:auto;background:#fff;padding:20px;margin:20px 0;border-radius:8px;box-shadow:0 2px 4px rgba(0,0,0,0.1);}
    table{width:100%;border-collapse:collapse;font-size:0.9em;} th,td{padding:10px;border-bottom:1px solid #ddd;text-align:left;}
    th{background:#3498db;color:#fff;position:sticky;top:0;} tr:nth-child(even){background:#f2f2f2;} tr:hover{background:#e6f7ff;}
    .coords{font-family:monospace;} .null-value{color:#999;font-style:italic;}
    #leaflet-map{width:100%;height:600px;border-radius:8px;box-shadow:0 2px 4px rgba(0,0,0,0.1);}
    canvas{max-width:100%;margin:20px 0;}
    #stationSelect{width:100%;padding:10px;margin-bottom:20px;border-radius:5px;border:1px solid #ccc;}
    .footer{text-align:center;color:#7f8c8d;margin-top:20px;}
  </style>
</head>
<body>
  <h1>Dane hydrologiczne IMGW (hydro2)</h1>
  <div class="tabs">
    <button class="tab-button active" data-tab="chart-area">Wykresy</button>
    <button class="tab-button" data-tab="table-area">Tabela</button>
    <button class="tab-button" data-tab="map-area">Mapa</button>
  </div>

  <!-- Wykresy -->
  <div id="chart-area" class="tab-content active">
    <h2>Rozkład stanów stacji</h2>
    <canvas id="pieStateChart"></canvas>

    <h2>Średni poziom wody (gauge)</h2>
    <canvas id="doughnutChart"></canvas>

    <h2>Top 10 stacji według poziomu</h2>
    <canvas id="top10Chart"></canvas>

    <h2>Trend stanu wybranej stacji</h2>
    <select id="stationSelect">
      {% for r in data %}
      <option value="{{ r.kod_stacji }}">{{ r.kod_stacji }} – {{ r.nazwa_stacji }}</option>
      {% endfor %}
    </select>
    <canvas id="lineTrendChart"></canvas>
  </div>

  <!-- Tabela -->
  <div id="table-area" class="tab-content">
    <div class="table-container">
      <table>
        <thead>
          <tr><th>Kod stacji</th><th>Nazwa</th><th>Stan</th><th>Data pomiaru</th></tr>
        </thead>
        <tbody>
          {% for r in data %}
          <tr>
            <td>{{ r.kod_stacji }}</td>
            <td>{{ r.nazwa_stacji }}</td>
            <td>{{ r.stan or '–' }}</td>
            <td>{{ r.stan_data or '–' }}</td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
    </div>
  </div>

  <!-- Mapa -->
  <div id="map-area" class="tab-content">
    <div id="leaflet-map"></div>
  </div>

  <div class="footer">
    Wygenerowano: {{ timestamp }}
  </div>

  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <script>
    // Zakładki
    document.querySelectorAll('.tab-button').forEach(btn=>{
      btn.addEventListener('click',()=>{
        document.querySelectorAll('.tab-button').forEach(b=>b.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(c=>c.classList.remove('active'));
        btn.classList.add('active');
        document.getElementById(btn.dataset.tab).classList.add('active');
      });
    });

    // PIE Chart
    new Chart(document.getElementById('pieStateChart'), {
      type: 'pie',
      data: {
        labels: ['Alarmowe','Ostrzegawcze','Normalne'],
        datasets: [{ data: [{{ alarm_state|length }},{{ warning_state|length }},{{ normal_state|length }}] }]
      },
      options:{responsive:true}
    });

    // GAUGE (doughnut half)
    new Chart(document.getElementById('doughnutChart'), {
      type: 'doughnut',
      data: {
        labels: ['Średni poziom',''],
        datasets:[{ data:[{{ avg_level }}, {{ 1000-avg_level }}] }]
      },
      options:{
        responsive:true,
        circumference: Math.PI,
        rotation: Math.PI
      }
    });

    // TOP10 horizontal bar
    new Chart(document.getElementById('top10Chart'), {
      type:'bar',
      data:{
        labels: {{ top10_keys|tojson }},
        datasets:[{ label:'Poziom wody', data: {{ top10_vals|tojson }} }]
      },
      options:{indexAxis:'y',responsive:true,scales:{x:{beginAtZero:true}}}
    });

    // LINE trend
    const historyData = {{ history_data|tojson }};
    const select = document.getElementById('stationSelect');
    const ctxLine = document.getElementById('lineTrendChart').getContext('2d');
    let lineChart = new Chart(ctxLine, {
      type:'line',
      data:{
        labels: historyData[select.value].dates,
        datasets:[{ label:'Stan wody', data: historyData[select.value].levels, fill:false, tension:0.1 }]
      },
      options:{responsive:true}
    });
    select.addEventListener('change',()=>{
      const d = historyData[select.value];
      lineChart.data.labels = d.dates;
      lineChart.data.datasets[0].data = d.levels;
      lineChart.update();
    });

    // Leaflet map
    var map = L.map('leaflet-map').setView([52,19],6);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{
      attribution:'© OpenStreetMap contributors'
    }).addTo(map);
    const stations = {{ data|tojson }};
    stations.forEach(s=>{
      if(s.lat && s.lon){
        L.circleMarker([+s.lat,+s.lon], {
          radius:5,
          color: s.stan>=500?'red':(s.stan>=450?'orange':'green')
        }).addTo(map).bindPopup(
          `<b>${s.nazwa_stacji}</b><br>Stan: ${s.stan}`
        );
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
        top10_keys=top10_keys,
        top10_vals=top10_vals,
        avg_level=avg_level,
        history_data=history_data,
        timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    )

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(rendered)
    print(f"✅ Wygenerowano {output_file}")

if __name__ == '__main__':
    generate_html_from_csv()
