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
                lvl = float(row['stan'])
                if lvl >= 500:
                    alarm_state.append(row)
                elif lvl >= 450:
                    warning_state.append(row)
                else:
                    normal_state.append(row)
        except (ValueError, TypeError):
            continue
    return alarm_state, warning_state, normal_state

def generate_html_from_csv(csv_file='hydro_data.csv', output_file='hydro_map.html'):
    # Wczytanie danych z CSV
    data = []
    with open(csv_file, mode='r', encoding='utf-8-sig') as file:
        reader = csv.DictReader(file, delimiter=';')
        for row in reader:
            # Mapowanie pól rzeka/akwen i kod rzeki
            row['river'] = row.get('rzeka')
            row['riverCode'] = row.get('kod_rzeki')
            # Zamiana pustych na None
            cleaned = {k: (v if v != '' else None) for k,v in row.items()}
            data.append(cleaned)

    # Klasyfikacja stanów
    alarm_state, warning_state, normal_state = classify_water_levels(data)

    # Szablon HTML z zakładkami, mapą i wykresami
    html_template = Template("""
<!DOCTYPE html>
<html lang="pl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Dane hydrologiczne IMGW</title>
  <!-- Bootstrap 5 CSS -->
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
  <!-- Leaflet CSS -->
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
          <div class="summary-box bg-danger text-white p-2 rounded">Alarmowe (≥500): {{ alarm_state|length }}</div>
          <div class="summary-box bg-warning text-dark p-2 rounded">Ostrzegawcze (450-499): {{ warning_state|length }}</div>
          <div class="summary-box bg-success text-white p-2 rounded">Normalne (&lt;450): {{ normal_state|length }}</div>
        </div>
        <!-- Tutaj mogą się znaleźć Twoje tabele z alarm_state, warning_state i wszystkimi danymi -->
      </div>

      <!-- Mapa stacji -->
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

  <!-- Skrypty -->
  <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
  <script src="https://unpkg.com/leaflet/dist/leaflet.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <script>
    document.addEventListener('DOMContentLoaded', () => {
      // 1) Inicjalizacja mapy
      const map = L.map('mapid').setView([52, 19], 6);
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap'
      }).addTo(map);

      // 2) Granice Polski
      fetch('/static/poland.geojson')
        .then(r => r.json())
        .then(geo => L.geoJSON(geo, {
          style: { color: '#444', weight: 2, fillOpacity: 0 }
        }).addTo(map));

      // 3) Markery stacji
      const stations = {{ data|tojson|safe }};
      stations.forEach(p => {
        if (p.lat && p.lon) {
          const lvl = parseFloat(p.stan) || 0;
          const color = lvl >= 500 ? 'red' : lvl >= 450 ? 'orange' : 'green';
          L.circleMarker([p.lat, p.lon], {
            radius: 6, fillColor: color, color: '#000', weight: 1, fillOpacity: 0.8
          })
          .bindPopup(
            `<strong>${p.nazwa_stacji}</strong><br>` +
            `Rzeka/Akwen: ${p.river || 'brak'} (${p.riverCode || 'brak'})<br>` +
            `Stan: ${p.stan} m`
          ).addTo(map);
        }
      });

      // 4) Wykres poziomów
      const labels = stations.map(p => p.stan_data);
      const values = stations.map(p => p.stan);
      new Chart(document.getElementById('chart-levels'), {
        type: 'line',
        data: { labels, datasets: [{ label: 'Poziom [m]', data: values }] },
        options: { scales: { x: { type: 'time', time: { unit: 'hour' } } } }
      });

      // 5) Wykres statusów
      const counts = { alarm: 0, warning: 0, normal: 0 };
      stations.forEach(p => {
        const lvl = parseFloat(p.stan) || 0;
        const key = lvl >= 500 ? 'alarm' : lvl >= 450 ? 'warning' : 'normal';
        counts[key]++;
      });
      new Chart(document.getElementById('chart-status'), {
        type: 'doughnut',
        data: {
          labels: ['Alarm', 'Ostrzeżenie', 'Normalny'],
          datasets: [{ data: [counts.alarm, counts.warning, counts.normal] }]
        }
      });
    });
  </script>
</body>
</html>
""")

    # Wypełnienie i zapis
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    final_html = html_template.render(
        data=data,
        alarm_state=alarm_state,
        warning_state=warning_state,
        normal_state=normal_state,
        timestamp=timestamp
    )

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(final_html)

    print(f"✅ Wygenerowano plik HTML: {output_file}")

if __name__ == '__main__':
    generate_html_from_csv()
