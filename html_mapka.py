import csv
import folium
import io
import base64
import matplotlib.pyplot as plt
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

def generate_html_from_csv(csv_file='hydro_data.csv', output_file='hydro_dashboard.html'):
    # 1) Wczytanie i czyszczenie
    data = []
    with open(csv_file, mode='r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f, delimiter=';')
        for row in reader:
            cleaned = {k: (v if v != '' else None) for k, v in row.items()}
            data.append(cleaned)

    # 2) Klasyfikacja
    alarm_state, warning_state, normal_state = classify_water_levels(data)

    # 3) Budowa interaktywnej mapy Folium
    #    - centrowanie na Polskę
    m = folium.Map(location=[52.0, 19.0], zoom_start=6)
    #    - granice Polski z lokalnego pliku
    folium.GeoJson('poland.geojson', name='Granice Polski').add_to(m)
    #    - warstwy ostrzegawcza i alarmowa
    fg_warn = folium.FeatureGroup(name='Ostrzegawcze (450–499)')
    for row in warning_state:
        folium.CircleMarker(
            location=[float(row['lat']), float(row['lon'])],
            radius=5,
            color='orange',
            popup=f"{row['nazwa_stacji']}<br>Stan: {row['stan']}"
        ).add_to(fg_warn)
    fg_warn.add_to(m)

    fg_alarm = folium.FeatureGroup(name='Alarmowe (≥500)')
    for row in alarm_state:
        folium.CircleMarker(
            location=[float(row['lat']), float(row['lon'])],
            radius=5,
            color='red',
            popup=f"{row['nazwa_stacji']}<br>Stan: {row['stan']}"
        ).add_to(fg_alarm)
    fg_alarm.add_to(m)

    folium.LayerControl().add_to(m)
    #    - wyrenderuj mapę do HTML stringa
    map_html = m._repr_html_()

    # 4) Wykres kołowy do base64
    buf = io.BytesIO()
    labels = ['Stan alarmowy', 'Stan ostrzegawczy', 'Stan normalny']
    sizes = [len(alarm_state), len(warning_state), len(normal_state)]
    plt.figure(figsize=(4,4))
    plt.pie(sizes, labels=labels, autopct='%1.1f%%')
    plt.tight_layout()
    plt.savefig(buf, format='png')
    plt.close()
    buf.seek(0)
    chart_b64 = base64.b64encode(buf.read()).decode('utf-8')

    # 5) Szablon z zakładkami
    html_template = Template("""
<!DOCTYPE html>
<html lang="pl">
<head>
  <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Hydro Dashboard IMGW</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 0; }
    .tabs { display: flex; background: #2c3e50; }
    .tabs button {
      flex:1; padding:15px; border:none; background:#34495e; color: white; cursor:pointer;
    }
    .tabs button.active { background: #1abc9c; }
    .tab-content { display:none; padding:20px; }
    .tab-content.active { display:block; }
    .table-container { overflow-x:auto; background:white; padding:20px; }
    table { width:100%; border-collapse:collapse; }
    th, td { padding:8px; border:1px solid #ddd; text-align:left; }
    th { background:#3498db; color:white; position:sticky; top:0; }
    .footer { text-align:center; margin-top:10px; color:#7f8c8d; font-size:0.9em; }
  </style>
</head>
<body>

  <div class="tabs">
    <button class="tab-link active" data-tab="table">📋 Tabela</button>
    <button class="tab-link" data-tab="map">🗺️ Mapa</button>
    <button class="tab-link" data-tab="chart">📊 Wykres</button>
  </div>

  <div id="table" class="tab-content active">
    <div class="table-container">
      <h2>Wszystkie stacje (łącznie {{ data|length }})</h2>
      <table>
        <thead>
          <tr>
            <th>Kod</th><th>Nazwa</th><th>Współrzędne</th>
            <th>Stan</th><th>Data pomiaru</th><th>Przepływ</th><th>Data przepływu</th><th>Status</th>
          </tr>
        </thead>
        <tbody>
          {% for row in data %}
          <tr>
            <td>{{ row['kod_stacji'] or '–' }}</td>
            <td>{{ row['nazwa_stacji'] or '–' }}</td>
            <td>
              {% if row['lat'] and row['lon'] %}
                {{ row['lat'] }}, {{ row['lon'] }}
              {% else %}–{% endif %}
            </td>
            <td>{{ row['stan'] or '–' }}</td>
            <td>{{ row['stan_data'] or '–' }}</td>
            <td>{{ row['przeplyw'] or '–' }}</td>
            <td>{{ row['przeplyw_data'] or '–' }}</td>
            <td>
              {% if row['stan'] %}
                {% set lvl = row['stan']|float %}
                {% if lvl >= 500 %}<span style="color:red">ALARM</span>
                {% elif lvl >=450 %}<span style="color:orange">OSTRZEŻENIE</span>
                {% else %}<span style="color:green">NORMALNY</span>{% endif %}
              {% else %}–{% endif %}
            </td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
      <div class="footer">
        Ostatnia aktualizacja: {{ timestamp }} | 
        Alarmowe: {{ alarm_state|length }} | 
        Ostrzegawcze: {{ warning_state|length }} | 
        Normalne: {{ normal_state|length }}
      </div>
    </div>
  </div>

  <div id="map" class="tab-content">
    <h2>Interaktywna mapa</h2>
    {{ map_html|safe }}
  </div>

  <div id="chart" class="tab-content">
    <h2>Rozkład stanów</h2>
    <img src="data:image/png;base64,{{ chart_b64 }}" alt="Wykres kołowy">
  </div>

  <script>
    const tabs = document.querySelectorAll('.tab-link');
    const contents = document.querySelectorAll('.tab-content');
    tabs.forEach(btn => {
      btn.addEventListener('click', () => {
        tabs.forEach(b => b.classList.remove('active'));
        contents.forEach(c => c.classList.remove('active'));
        btn.classList.add('active');
        document.getElementById(btn.dataset.tab).classList.add('active');
      });
    });
  </script>
</body>
</html>
    """)

    # 6) Render i zapis
    rendered = html_template.render(
      data=data,
      alarm_state=alarm_state,
      warning_state=warning_state,
      normal_state=normal_state,
      map_html=map_html,
      chart_b64=chart_b64,
      timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    )
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(rendered)
    print(f"✅ Wygenerowano pulpit nawigacyjny: {output_file}")

if __name__ == '__main__':
    generate_html_from_csv()
