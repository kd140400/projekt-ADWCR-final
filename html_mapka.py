import csv
import json
from jinja2 import Template
from datetime import datetime

def classify_water_levels(data):
    al, wr, no = [], [], []
    for r in data:
        try:
            if r.get('stan'):
                lvl = float(r['stan'])
                if lvl >= 500: al.append(r)
                elif lvl >= 450: wr.append(r)
                else: no.append(r)
        except: pass
    return al, wr, no


def generate_html_from_csv(csv_file='hydro_data.csv', output_file='hydro_map.html'):
    # Wczytanie danych z CSV
    data = []
    with open(csv_file, encoding='utf-8-sig') as f:
        reader = csv.DictReader(f, delimiter=';')
        for row in reader:
            row['river'] = row.get('rzeka')
            row['riverCode'] = row.get('kod_rzeki')
            data.append({k: (v if v != '' else None) for k, v in row.items()})
    alarm_state, warning_state, normal_state = classify_water_levels(data)

    tpl = Template("""
<!DOCTYPE html>
<html lang="pl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Dane hydrologiczne IMGW</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
  <link rel="stylesheet" href="https://unpkg.com/leaflet/dist/leaflet.css" />
  <style>
    #mapid { height: 600px; }
    .coords { font-family: monospace; }
    .footer { text-align: center; margin-top: 20px; color: #666; }
  </style>
</head>
<body>
  <div class="container my-4">
    <h1 class="text-center">Dane hydrologiczne IMGW</h1>
    <!-- Nav tabs -->
    <ul class="nav nav-tabs" id="mainTabs" role="tablist">
      <li class="nav-item" role="presentation">
        <a class="nav-link active" id="stats-tab" data-bs-toggle="tab" href="#stats" role="tab">Statystyki</a>
      </li>
      <li class="nav-item" role="presentation">
        <a class="nav-link" id="map-tab" data-bs-toggle="tab" href="#map" role="tab">Mapa stacji</a>
      </li>
      <li class="nav-item" role="presentation">
        <a class="nav-link" id="timeseries-tab" data-bs-toggle="tab" href="#timeseries" role="tab">Analizy czasowe</a>
      </li>
    </ul>

    <div class="tab-content mt-3">
      <!-- Statystyki -->
      <div class="tab-pane fade show active" id="stats" role="tabpanel" aria-labelledby="stats-tab">
        <div class="summary d-flex justify-content-around mb-3">
          <div class="summary-box alarm-summary bg-danger text-white p-2 rounded">Alarmowe (≥500): {{ alarm_state|length }}</div>
          <div class="summary-box warning-summary bg-warning text-dark p-2 rounded">Ostrzegawcze (450-499): {{ warning_state|length }}</div>
          <div class="summary-box normal-summary bg-success text-white p-2 rounded">Normalne (&lt;450): {{ normal_state|length }}</div>
        </div>
        <!-- Tutaj tabele dla alarm_state, warning_state i wszystkie dane -->
      </div>

      <!-- Mapa -->
      <div class="tab-pane fade" id="map" role="tabpanel" aria-labelledby="map-tab">
        <div id="mapid"></div>
      </div>

      <!-- Analizy czasowe -->
      <div class="tab-pane fade" id="timeseries" role="tabpanel" aria-labelledby="timeseries-tab">
        <canvas id="chart-levels" height="200"></canvas>
        <canvas id="chart-status" height="200" class="mt-4"></canvas>
      </div>
    </div>

    <div class="footer">Ostatnia aktualizacja: {{ timestamp }}</div>
  </div>

  <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
  <script src="https://unpkg.com/leaflet/dist/leaflet.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <script>
    document.addEventListener('DOMContentLoaded', () => {
      // Inicjalizacja mapy
      const map = L.map('mapid').setView([52, 19], 6);
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { attribution: '&copy; OpenStreetMap' }).addTo(map);
      // Granice Polski
      fetch('poland.geojson').then(r => r.json()).then(geo => L.geoJSON(geo, { style: { color: '#444', weight: 2, fillOpacity: 0 } }).addTo(map));
      // Markery stacji
      const stations = {{ data|tojson|safe }};
      const stationsLayer = L.layerGroup().addTo(map);
      stations.forEach(p => {
        if (p.lat && p.lon) {
          const lvl = parseFloat(p.stan) || 0;
          const status = lvl >= 500 ? 'alarm' : lvl >= 450 ? 'warning' : 'normal';
          const color = status === 'alarm' ? 'red' : status === 'warning' ? 'orange' : 'green';
          L.circleMarker([p.lat, p.lon], { radius: 6, fillColor: color, color: '#000', weight: 1, fillOpacity: 0.8 })
           .bindPopup(`<strong>${p.nazwa_stacji}</strong><br>Rzeka/Akwen: ${p.river || 'brak'} (${p.riverCode || 'brak'})<br>Stan: ${p.stan} m`)
           .addTo(stationsLayer);
        }
      });
      // Wykres poziomów
      const ctx1 = document.getElementById('chart-levels').getContext('2d');
      new Chart(ctx1, {
        type: 'line',
        data: { labels: stations.map(p => p.stan_data), datasets: [{ label: 'Poziom [m]', data: stations.map(p => p.stan) }] },
        options: { scales: { x: { type: 'time', time: { unit: 'hour' } } } }
      });
      // Wykres statusów
      const counts = { alarm: 0, warning: 0, normal: 0 };
      stations.forEach(p => { const l = parseFloat(p.stan) || 0; counts[l >= 500 ? 'alarm' : l >= 450 ? 'warning' : 'normal']++; });
      const ctx2 = document.getElementById('chart-status').getContext('2d');
      new Chart(ctx2, { type: 'doughnut', data: { labels: ['Alarm', 'Ostrzeżenie', 'Normalny'], datasets: [{ data: [counts.alarm, counts.warning, counts.normal] }] } });
    });
  </script>
</body>
</html>
""")
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    html = tpl.render(data=data, alarm_state=alarm_state, warning_state=warning_state, normal_state=normal_state, timestamp=ts)
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"✅ HTML wygenerowany: {output_file}")

if __name__ == '__main__':
    generate_html_from_csv()
