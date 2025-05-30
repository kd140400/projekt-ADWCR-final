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

def refresh_and_save_data():
    """Usuwa stare dane i zapisuje nowe dane z API."""
    new_data = fetch_new_data()
    if new_data:
        # Wyczyszczenie pliku CSV
        with open(CSV_FILE, 'w', encoding='utf-8-sig') as f:
            f.truncate(0)
        save_new_data(new_data)
        print(f"✅ Pobrano i zapisano {len(new_data)} rekordów.")
        return new_data
    print("⚠️ Brak nowych danych do zapisania.")
    return None

def generate_html_from_csv(csv_file=CSV_FILE, output_file='hydro_table.html'):
    # 1) Wczytaj dane CSV
    data = []
    with open(csv_file, mode='r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f, delimiter=';')
        for r in reader:
            data.append({k: (v if v != '' else None) for k, v in r.items()})

    # 2) Klasyfikacja
    alarm_state, warning_state, normal_state = classify_water_levels(data)

    # 2a) Funkcja pomocnicza do liczenia statystyk
    def compute_stats(nums):
        if not nums:
            return {
                'Liczba pomiarów': 0,
                'Min': '-',
                'Max': '-',
                'Średnia': '-',
                'Mediana': '-'
            }
        return {
            'Liczba pomiarów': len(nums),
            'Min': f"{min(nums):.2f}",
            'Max': f"{max(nums):.2f}",
            'Średnia': f"{statistics.mean(nums):.2f}",
            'Mediana': f"{statistics.median(nums):.2f}"
        }

    # 2b) Przygotuj listy wartości dla wszystkich i każdej kategorii
    numeric_all     = [float(r['stan']) for r in data if r.get('stan') is not None]
    numeric_alarm   = [float(r['stan']) for r in alarm_state   if r.get('stan') is not None]
    numeric_warning = [float(r['stan']) for r in warning_state if r.get('stan') is not None]
    numeric_normal  = [float(r['stan']) for r in normal_state  if r.get('stan') is not None]

    # 2c) Oblicz słowniki statystyk
    stats_all     = compute_stats(numeric_all)
    stats_alarm   = compute_stats(numeric_alarm)
    stats_warning = compute_stats(numeric_warning)
    stats_normal  = compute_stats(numeric_normal)

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

    # 5) Granice Polski
    with open(GEOJSON_FILE, 'r', encoding='utf-8') as gf:
        boundary = json.load(gf)

    # 6) Szablon HTML
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
    #refresh-button{position:fixed;top:20px;right:20px;padding:10px 20px;background:#3498db;color:#fff;border:none;border-radius:5px;cursor:pointer;box-shadow:0 4px 8px rgba(0,0,0,0.2);}
    #refresh-button:hover{background:#2980b9;}
    .tabs{display:flex;gap:10px;margin-top:20px;}
    .tab-button{padding:10px 20px;background:#eee;border:none;border-radius:5px 5px 0 0;cursor:pointer;}
    .tab-button.active{background:#fff;border-bottom:2px solid #fff;}
    .tab-content{display:none;} .tab-content.active{display:block;}
    .table-container{overflow-x:auto;background:#fff;padding:20px;margin:20px 0;border-radius:8px;box-shadow:0 2px 4px rgba(0,0,0,0.1);}
    table{width:100%;border-collapse:collapse;font-size:0.9em;}
    th,td{padding:10px;border-bottom:1px solid #ddd;text-align:left;}
    th{background:#3498db;color:#fff;position:sticky;top:0;}
    tr:nth-child(even){background:#f2f2f2;} tr:hover{background:#e6f7ff;}
    .coords{font-family:monospace;} .null-value{color:#999;font-style:italic;}
    .alarm td{background:#ffdddd;} .warning td{background:#fff3cd;}
    #leaflet-map{width:100%;height:600px;border-radius:8px;box-shadow:0 2px 4px rgba(0,0,0,0.1);}
    .legend{background:white;padding:6px 8px;font-size:14px;line-height:18px;color:#555;box-shadow:0 0 15px rgba(0,0,0,0.2);border-radius:5px;}
    .legend i{width:12px;height:12px;float:left;margin-right:6px;opacity:0.7;}
    .stats-table{width:50%;margin:0 auto 20px;border-collapse:collapse;}
    .stats-table th,.stats-table td{border:1px solid #ddd;padding:8px;text-align:center;}
    .stats-table th{background:#3498db;color:#fff;}
    canvas{max-width:100%;margin:20px 0;}
    .chart-row {
      display: flex;
      flex-wrap: wrap;
      gap: 20px;
      justify-content: space-between;
      margin: 20px 0;
    }
    .chart-container {
      flex: 1 1 45%;
      /* wysokość = 40% wysokości okna przeglądarki */
      height: 40vh;
      background: #fff;
      padding: 10px;
      border-radius: 8px;
      box-shadow: 0 2px 4px rgba(0,0,0,0.1);
      display: flex;
      flex-direction: column;
    }
    .chart-container h2 {
      text-align: center;
      margin-bottom: 10px;
    }
    .chart-container canvas {
      /* wypełnij całą wysokość kontenera */
      width: 100% !important;
      height: 100% !important;
      flex: 1;
    }
    .footer{text-align:center;color:#7f8c8d;margin-top:20px;}
  </style>
</head>
<body>
  <h1>Dane hydrologiczne IMGW (hydro2)</h1>
  <div class="summary">
    <div class="summary-box alarm-summary">Alarmowe (≥500): {{ alarm_state|length }}</div>
    <div class="summary-box warning-summary">Ostrz. (450–499): {{ warning_state|length }}</div>
    <div class="summary-box normal-summary">Normalne (&lt;450): {{ normal_state|length }}</div>
  </div>
  <button id="refresh-button" onclick="location.reload()">Odśwież dane</button>

  <div class="tabs">
    <button class="tab-button active" data-tab="table">Tabela</button>
    <button class="tab-button" data-tab="map">Mapa</button>
    <button class="tab-button" data-tab="charts">Wykresy i statystyki</button>
  </div>

  <!-- Tabela -->
  <div id="table" class="tab-content active">
    {% if alarm_state %}
      <h2>⚠️ Stany alarmowe (≥500)</h2>
      <div class="table-container alarm">
        <table><thead><tr>
          <th>Kod stacji</th><th>Nazwa</th><th>Współrzędne</th>
          <th>Stan wody</th><th>Data pomiaru</th>
          <th>Przepływ</th><th>Data przepływu</th>
        </tr></thead><tbody>
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
        </tbody></table>
      </div>
    {% endif %}
    {% if warning_state %}
      <h2>⚠️ Stany ostrzegawcze (450–499)</h2>
      <div class="table-container warning">
        <table><thead><tr>
          <th>Kod stacji</th><th>Nazwa</th><th>Współrzędne</th>
          <th>Stan wody</th><th>Data pomiaru</th>
          <th>Przepływ</th><th>Data przepływu</th>
        </tr></thead><tbody>
        {% for r in warning_state %}
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
        </tbody></table>
      </div>
    {% endif %}
    <h2>Wszystkie stacje</h2>
    <div class="table-container">
      <table><thead><tr>
        <th>Kod stacji</th><th>Nazwa</th><th>Współrzędne</th>
        <th>Stan wody</th><th>Data pomiaru</th>
        <th>Przepływ</th><th>Data przepływu</th><th>Status</th>
      </tr></thead><tbody>
        {% for r in data %}
          {% set lvl = r.stan is not none and r.stan|float %}
          <tr>
            <td>{{ r.kod_stacji or '<span class="null-value">brak</span>'|safe }}</td>
            <td>{{ r.nazwa_stacji or '<span class="null-value">brak</span>'|safe }}</td>
            <td class="coords">
              {% if r.lon and r.lat %}
                {{ "%.6f"|format(r.lon|float) }}, {{ "%.6f"|format(r.lat|float) }}
              {% else %}<span class="null-value">brak</span>{% endif %}
            </td>
            <td>
              {% if lvl >= 500 %}
                <strong style="color:red">{{ r.stan }}</strong>
              {% elif lvl >= 450 %}
                <strong style="color:orange">{{ r.stan }}</strong>
              {% else %}
                {{ r.stan or '<span class="null-value">brak</span>'|safe }}
              {% endif %}
            </td>
            <td>{{ r.stan_data or '<span class="null-value">brak</span>'|safe }}</td>
            <td>{{ r.przeplyw or '<span class="null-value">brak</span>'|safe }}</td>
            <td>{{ r.przeplyw_data or '<span class="null-value">brak</span>'|safe }}</td>
            <td>
              {% if lvl >= 500 %}
                <span style="color:red">ALARM</span>
              {% elif lvl >= 450 %}
                <span style="color:orange">OSTRZEŻENIE</span>
              {% else %}
                <span style="color:green">NORMALNY</span>
              {% endif %}
            </td>
          </tr>
        {% endfor %}
      </tbody></table>
    </div>
  </div>

  <!-- Mapa -->
  <div id="map" class="tab-content">
    <h2>Mapa stacji</h2>
    <div id="leaflet-map"></div>
  </div>

  <!-- Wykresy i statystyki -->
  <div id="charts" class="tab-content">
    <h2>Statystyki stanu wody</h2>
    <table class="stats-table">
      <thead>
       <tr>
          <th>Metryka</th>
          <th>Wszystkie</th>
          <th>Alarmowe</th>
          <th>Ostrzegawcze</th>
          <th>Normalne</th>
        </tr>
      </thead>
      <tbody>
        {% for k, v in stats_all.items() %}
        <tr>
          <td>{{ k }}</td>
          <td>{{ v }}</td>
          <td>{{ stats_alarm[k] }}</td>
          <td>{{ stats_warning[k] }}</td>
          <td>{{ stats_normal[k] }}</td>
        </tr>
        {% endfor %}
      </tbody>
    </table>

        <div class="chart-row">
      <div class="chart-container">
        <h2>Liczba stacji wg kategorii</h2>
        <canvas id="stateChart"></canvas>
      </div>
      <div class="chart-container">
        <h2>Top 10 stacji wg poziomu</h2>
        <canvas id="top10Chart"></canvas>
      </div>
    </div>
  </div>

  <div class="footer">
    Ostatnia aktualizacja: {{ timestamp }} | Rekordów: {{ data|length }}
  </div>

  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-datalabels"></script>
  <script>
    Chart.register(ChartDataLabels);

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

    // Leaflet + popup z kodem i nazwą
    var map = L.map('leaflet-map').setView([52.0,19.0],6);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{
      attribution:'© OpenStreetMap contributors'
    }).addTo(map);
    L.geoJSON({{ boundary|tojson }},{style:{color:'#555',weight:1,fill:false}}).addTo(map);
    var stations = {{ data|tojson }};
    stations.forEach(s=>{
      if(s.lon && s.lat){
        L.circleMarker([+s.lat,+s.lon],{
          radius:5,
          color: s.stan>=500?'red':(s.stan>=450?'orange':'green')
        }).addTo(map).bindPopup(
          `<b>${s.kod_stacji} – ${s.nazwa_stacji}</b><br>Stan: ${s.stan}`
        );
      }
    });

    // Legenda mapy
    var legend = L.control({position:'bottomright'});
    legend.onAdd = function(map) {
      var div = L.DomUtil.create('div','legend');
      div.innerHTML += '<i style="background:red"></i> Stany alarmowe<br>';
      div.innerHTML += '<i style="background:orange"></i> Stany ostrzegawcze<br>';
      div.innerHTML += '<i style="background:green"></i> Stany normalne';
      return div;
    };
    legend.addTo(map);

    // Pie chart – udział procentowy
    new Chart(document.getElementById('stateChart'), {
      type: 'pie',
      data:{labels:['Alarmowe','Ostrzegawcze','Normalne'],datasets:[{data:[{{ counts.alarm }},{{ counts.warning }},{{ counts.normal }}],backgroundColor: ['#e74c3c','#f1c40f','#2ecc71']}]},
      options:{responsive:true,maintainAspectRatio: false,plugins:{datalabels:{formatter:(value,ctx)=>{const sum=ctx.chart.data.datasets[0].data.reduce((a,b)=>a+b,0);return (value/sum*100).toFixed(1)+'%';},color:'#fff',font:{weight:'bold',size:14}},legend:{position:'bottom'}}}
    });

    // Bar chart – Top 10
    new Chart(document.getElementById('top10Chart'), {
      type: 'bar',
      data:{labels:{{ top10_labels_full|tojson }},datasets:[{label:'Poziom wody',data:{{ top10_values|tojson }}}]},
      options:{indexAxis:'y',responsive:true,maintainAspectRatio: false,scales:{x:{beginAtZero:true}}}
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
        stats_all=stats_all,
        stats_alarm=stats_alarm,
        stats_warning=stats_warning,
        stats_normal=stats_normal,
        boundary=boundary,
        timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    )
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(rendered)
    print(f"✅ Wygenerowano {output_file}")

if __name__ == '__main__':
    generate_html_from_csv()
