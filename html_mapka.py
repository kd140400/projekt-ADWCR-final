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
    # Wczytaj dane z CSV
    data = []
    with open(csv_file, mode='r', encoding='utf-8-sig') as file:
        reader = csv.DictReader(file, delimiter=';')
        for row in reader:
            cleaned = {k: (v if v != '' else None) for k, v in row.items()}
            data.append(cleaned)

    # Klasyfikacja
    alarm_state, warning_state, normal_state = classify_water_levels(data)

    # Szablon HTML z zakładkami, mapą i wykresami
    html_template = Template("""
    <!DOCTYPE html>
    <html lang="pl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Dane hydrologiczne IMGW</title>
        <!-- Bootstrap CSS -->
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <!-- Leaflet CSS -->
        <link rel="stylesheet" href="https://unpkg.com/leaflet/dist/leaflet.css" />
        <style>
            body { font-family: Arial, sans-serif; background: #f5f5f5; }
            .summary { display: flex; justify-content: space-around; margin: 20px 0; }
            .summary-box { padding: 10px 15px; border-radius: 5px; color: white; font-weight: bold; }
            .alarm-summary { background: #dc3545; }
            .warning-summary { background: #ffc107; }
            .normal-summary { background: #28a745; }
            .coords { font-family: monospace; }
            .footer { text-align: center; margin: 20px 0; color: #666; }
        </style>
    </head>
    <body>
      <div class="container">
        <h1 class="text-center my-4">Dane hydrologiczne IMGW</h1>
        <!-- Zakładki -->
        <ul class="nav nav-tabs" id="mainTabs" role="tablist">
          <li class="nav-item" role="presentation">
            <button class="nav-link active" id="stats-tab" data-bs-toggle="tab" data-bs-target="#stats" type="button" role="tab">Statystyki</button>
          </li>
          <li class="nav-item" role="presentation">
            <button class="nav-link" id="map-tab" data-bs-toggle="tab" data-bs-target="#map" type="button" role="tab">Mapa</button>
          </li>
          <li class="nav-item" role="presentation">
            <button class="nav-link" id="series-tab" data-bs-toggle="tab" data-bs-target="#timeseries" type="button" role="tab">Analizy czasowe</button>
          </li>
        </ul>
        <div class="tab-content p-3">
          <!-- Statystyki -->
          <div class="tab-pane fade show active" id="stats" role="tabpanel">
            <div class="summary">
              <div class="summary-box alarm-summary">Alarmowe (≥500): {{ alarm_state|length }}</div>
              <div class="summary-box warning-summary">Ostrzegawcze (450-499): {{ warning_state|length }}</div>
              <div class="summary-box normal-summary">Normalne (&lt;450): {{ normal_state|length }}</div>
            </div>
            {% if alarm_state %}
              <h4>⚠️ Stany alarmowe</h4>
              <div class="table-responsive">
                <table class="table table-striped">
                  <thead><tr><th>Kod</th><th>Nazwa</th><th>Współrzędne</th><th>Stan</th><th>Data</th></tr></thead>
                  <tbody>{% for r in alarm_state %}<tr>
                    <td>{{ r.kod_stacji }}</td>
                    <td>{{ r.nazwa_stacji }}</td>
                    <td class="coords">{{ r.lat }}, {{ r.lon }}</td>
                    <td>{{ r.stan }} m</td>
                    <td>{{ r.stan_data }}</td>
                  </tr>{% endfor %}</tbody>
                </table>
              </div>
            {% endif %}
            {% if warning_state %}
              <h4>⚠ Stany ostrzegawcze</h4>
              <div class="table-responsive">
                <table class="table table-striped">
                  <thead><tr><th>Kod</th><th>Nazwa</th><th>Współrzędne</th><th>Stan</th><th>Data</th></tr></thead>
                  <tbody>{% for r in warning_state %}<tr>
                    <td>{{ r.kod_stacji }}</td>
                    <td>{{ r.nazwa_stacji }}</td>
                    <td class="coords">{{ r.lat }}, {{ r.lon }}</td>
                    <td>{{ r.stan }} m</td>
                    <td>{{ r.stan_data }}</td>
                  </tr>{% endfor %}</tbody>
                </table>
              </div>
            {% endif %}
            <h4>Wszystkie stacje</h4>
            <div class="table-responsive">
              <table class="table table-striped">
                <thead><tr><th>Kod</th><th>Nazwa</th><th>Współrzędne</th><th>Stan</th><th>Data</th><th>Status</th></tr></thead>
                <tbody>{% for r in data %}<tr>
                  <td>{{ r.kod_stacji }}</td>
                  <td>{{ r.nazwa_stacji }}</td>
                  <td class="coords">{{ r.lat }}, {{ r.lon }}</td>
                  <td>{{ r.stan }} m</td>
                  <td>{{ r.stan_data }}</td>
                  <td>{% if r.stan|float >= 500 %}Alarm{% elif r.stan|float >=450 %}Ostrzeżenie{% else %}Normalny{% endif %}</td>
                </tr>{% endfor %}</tbody>
              </table>
            </div>
          </div>
          <!-- Mapa -->
          <div class="tab-pane fade" id="map" role="tabpanel">
            <div id="mapid" style="height:600px;"></div>
          </div>
          <!-- Wykresy czasowe -->
          <div class="tab-pane fade" id="timeseries" role="tabpanel">
            <canvas id="chart-levels" height="200"></canvas>
            <canvas id="chart-status" height="200" class="mt-4"></canvas>
          </div>
        </div>
        <div class="footer">Ostatnia aktualizacja: {{ timestamp }}</div>
      </div>
      <!-- Skrypty -->
      <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
      <script src="https://unpkg.com/leaflet/dist/leaflet.js"></script>
      <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
      <script>
      document.addEventListener('DOMContentLoaded', ()=>{
        // Mapa
        const map = L.map('mapid').setView([52.0,19.0],6);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{attribution:'&copy; OSM'}).addTo(map);
        fetch('poland.geojson').then(r=>r.json()).then(geo=>L.geoJSON(geo).addTo(map));
        // Markery
        const stations = {{ data|tojson }};
        stations.forEach(p=>{
          if(p.lat && p.lon){
            const lvl=parseFloat(p.stan)||0;
            const status=lvl>=500?'alarm':lvl>=450?'warning':'normal';
            const color=status==='alarm'?'red':status==='warning'?'orange':'green';
            const m = L.circleMarker([p.lat,p.lon],{radius:6,fillColor:color,fillOpacity:0.8}).addTo(map);
            m.bindPopup(`<strong>${p.nazwa_stacji}</strong><br/>Kod: ${p.kod_stacji}<br/>Stan: ${p.stan} m`);
          }
        });
        // Wykres poziomu
        const ctx = document.getElementById('chart-levels').getContext('2d');
        new Chart(ctx,{type:'line',data:{labels:stations.map(p=>p.stan_data),datasets:[{label:'Poziom [m]',data:stations.map(p=>p.stan)}]},options:{scales:{x:{type:'time',time:{unit:'hour'}}}}});
        // Wykres statusów
        const count={alarm:0,warning:0,normal:0};stations.forEach(p=>{const l=parseFloat(p.stan)||0;count[l>=500?'alarm':l>=450?'warning':'normal']++;});
        const ctx2=document.getElementById('chart-status').getContext('2d');
        new Chart(ctx2,{type:'doughnut',data:{labels:['Alarm','Ostrzeżenie','Normalny'],datasets:[{data:[count.alarm,count.warning,count.normal]}]},options:{plugins:{legend:{position:'bottom'}}}});
      });
      </script>
    </body>
    </html>
    """)

    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    html = html_template.render(data=data, alarm_state=alarm_state, warning_state=warning_state, normal_state=normal_state, timestamp=timestamp)
    with open(output_file,'w',encoding='utf-8') as f:
        f.write(html)
    print(f"✅ Wygenerowano: {output_file}")

if __name__=='__main__':
    generate_html_from_csv()
