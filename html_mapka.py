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

    # 5) Unikalne nazwy i kody
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
  <meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Dane hydrologiczne IMGW (hydro2)</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
  <style>
    body{font-family:Arial,sans-serif;margin:20px;background:#f5f5f5;}
    h1,h2{text-align:center;color:#2c3e50;margin:0;}
    #refresh-button{position:fixed;top:20px;right:20px;padding:10px 20px;background:#3498db;color:#fff;border:none;border-radius:5px;cursor:pointer;box-shadow:0 4px 8px rgba(0,0,0,0.2);}
    #refresh-button:hover{background:#2980b9;}
    .tabs{display:flex; gap:10px; margin-top:40px;}
    .tab-button{flex:1; padding:10px; background:#eee; border:none; cursor:pointer; text-align:center; border-radius:5px 5px 0 0;}
    .tab-button.active{background:#fff; border-bottom:2px solid #fff;}
    .tab-content{display:none; background:#fff; padding:20px; border:1px solid #ddd; border-top:none; border-radius:0 5px 5px 5px;}
    .tab-content.active{display:block;}
    .table-container{overflow-x:auto; box-shadow:0 2px 4px rgba(0,0,0,0.1); margin-bottom:20px;}
    table{width:100%; border-collapse:collapse; font-size:0.9em;}
    th,td{padding:8px; border:1px solid #ddd; text-align:left;}
    th{background:#3498db; color:#fff; position:sticky; top:0;}
    tr:nth-child(even){background:#f9f9f9;}
    #leaflet-map{width:100%;height:500px;border-radius:8px;box-shadow:0 2px 4px rgba(0,0,0,0.1); margin-bottom:20px;}
    .legend{background:#fff; padding:6px 8px; font-size:13px; line-height:1.4; border-radius:5px; box-shadow:0 0 15px rgba(0,0,0,0.2);}
    .legend i{width:12px;height:12px;display:inline-block;margin-right:6px;opacity:0.7;}
    .filters{position:absolute; top:80px; right:20px; width:200px; background:#fff; padding:10px; border:1px solid #ccc; border-radius:5px; box-shadow:0 2px 4px rgba(0,0,0,0.1);}
    .filters label{display:block; margin-bottom:8px; font-size:0.9em;}
    .filters select{width:100%; height:4em;}
    .filters input[type="number"]{width:80px;}
    .filters button{margin-top:4px;}
    .stats-table{width:60%;margin:0 auto 20px;border-collapse:collapse;}
    .stats-table th,.stats-table td{border:1px solid #ddd;padding:8px;text-align:center;}
    .stats-table th{background:#3498db;color:#fff;}
    canvas{max-width:100%; margin-bottom:20px;}
    .footer{text-align:center;color:#555;margin-top:20px;}
  </style>
</head>
<body>
  <h1>Dane hydrologiczne IMGW (hydro2)</h1>
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
      <div class="table-container">
        <table><thead><tr><th>Kod stacji</th><th>Nazwa</th><th>Stan</th><th>Data</th></tr></thead>
        <tbody>{% for r in alarm_state %}
          <tr><td>{{r.kod_stacji}}</td><td>{{r.nazwa_stacji}}</td><td>{{r.stan}}</td><td>{{r.stan_data}}</td></tr>
        {% endfor %}</tbody></table>
      </div>
    {% endif %}
    {% if warning_state %}
      <h2>⚠️ Stany ostrzegawcze (450–499)</h2>
      <div class="table-container">
        <table><thead><tr><th>Kod stacji</th><th>Nazwa</th><th>Stan</th><th>Data</th></tr></thead>
        <tbody>{% for r in warning_state %}
          <tr><td>{{r.kod_stacji}}</td><td>{{r.nazwa_stacji}}</td><td>{{r.stan}}</td><td>{{r.stan_data}}</td></tr>
        {% endfor %}</tbody></table>
      </div>
    {% endif %}
    <h2>Wszystkie stacje</h2>
    <div class="table-container">
      <table><thead><tr><th>Kod</th><th>Nazwa</th><th>Stan</th><th>Data</th><th>Status</th></tr></thead>
      <tbody>{% for r in data %}
        {% set lvl = (r.stan|float) if r.stan else 0 %}
        <tr>
          <td>{{r.kod_stacji}}</td><td>{{r.nazwa_stacji}}</td>
          <td>{{r.stan}}</td><td>{{r.stan_data}}</td>
          <td>{% if lvl>=500 %}ALARM{% elif lvl>=450 %}OSTRZEŻENIE{% else %}NORMALNY{% endif %}</td>
        </tr>
      {% endfor %}</tbody></table>
    </div>
  </div>

  <!-- Mapa -->
  <div id="map" class="tab-content" style="position:relative;">
    <h2>Mapa stacji</h2>
    <div class="filters">
      <label>Stan wodny:<br>
        <select id="stateFilter" multiple>
          <option value="alarm" selected>Alarmowe</option>
          <option value="warning" selected>Ostrzegawcze</option>
          <option value="normal" selected>Normalne</option>
        </select>
      </label>
      <label>Nazwa stacji:<br>
        <select id="nameFilter" multiple>
          {% for n in unique_names %}<option value="{{n}}" selected>{{n}}</option>{% endfor %}
        </select>
      </label>
      <label>Kod stacji:<br>
        <select id="codeFilter" multiple>
          {% for c in unique_codes %}<option value="{{c}}" selected>{{c}}</option>{% endfor %}
        </select>
      </label>
      <label>Zakres stanu:<br>
        <input type="number" id="minLevel" value="0">–<input type="number" id="maxLevel" value="10000">
      </label>
      <button onclick="filterMarkers()">Filtruj</button>
      <button onclick="resetFilters()">Wyczyść filtry</button>
    </div>
    <div id="leaflet-map"></div>
  </div>

  <!-- Wykresy i statystyki -->
  <div id="charts" class="tab-content">
    <h2>Statystyki stanu wody</h2>
    <table class="stats-table"><thead><tr><th>Metryka</th><th>Wartość</th></tr></thead>
      <tbody>{% for k,v in stats.items() %}<tr><td>{{k}}</td><td>{{v}}</td></tr>{% endfor %}</tbody>
    </table>
    <h2>Liczba stacji wg kategorii</h2>
    <canvas id="stateChart"></canvas>
    <h2>Top 10 stacji wg poziomu</h2>
    <canvas id="top10Chart"></canvas>
  </div>

  <div class="footer">Ostatnia aktualizacja: {{ timestamp }} | Rekordów: {{ data|length }}</div>

  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-datalabels"></script>
  <script>
    Chart.register(ChartDataLabels);
    // Zakładki
    document.querySelectorAll('.tab-button').forEach(b=>{
      b.type='button';
      b.onclick=()=>{ document.querySelectorAll('.tab-button').forEach(x=>x.classList.remove('active'));
                     document.querySelectorAll('.tab-content').forEach(c=>c.classList.remove('active'));
                     b.classList.add('active');
                     document.getElementById(b.dataset.tab).classList.add('active');
                     if(b.dataset.tab==='map') setTimeout(()=>map.invalidateSize(),200);
                   };
    });

    // Leaflet i markery
    var map=L.map('leaflet-map').setView([52.0,19.0],6);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{attribution:'© OSM'}).addTo(map);
    L.geoJSON({{ boundary|tojson }},{style:{color:'#555',weight:1,fill:false}}).addTo(map);
    var markers=[]; {{ data|tojson }}.forEach(s=>{
      if(s.lat&&s.lon){
        var cat=s.stan>=500?'alarm':(s.stan>=450?'warning':'normal');
        var m=L.circleMarker([+s.lat,+s.lon],{radius:5,color:cat==='alarm'?'red':cat==='warning'?'orange':'green'})
          .bindPopup(`<b>${s.kod_stacji} – ${s.nazwa_stacji}</b><br>Stan: ${s.stan}`);
        m.cat=cat; m.name=s.nazwa_stacji; m.code=s.kod_stacji; m.level=+s.stan;
        m.addTo(map); markers.push(m);
      }
    });
    // Legenda
    L.control({position:'bottomright'}).onAdd=()=>{
      var div=L.DomUtil.create('div','legend');
      div.innerHTML='<i style="background:red"></i>Alarmowe<br><i style="background:orange"></i>Ostrzegawcze<br><i style="background:green"></i>Normalne';
      return div;
    }.addTo(map);

    function filterMarkers(){
      var st=Array.from(stateFilter.selectedOptions).map(o=>o.value),
          nm=Array.from(nameFilter.selectedOptions).map(o=>o.value),
          cd=Array.from(codeFilter.selectedOptions).map(o=>o.value),
          min=+minLevel.value, max=+maxLevel.value;
      markers.forEach(m=>{
        var ok=st.includes(m.cat)&&nm.includes(m.name)&&cd.includes(m.code)&&m.level>=min&&m.level<=max;
        ok?map.addLayer(m):map.removeLayer(m);
      });
    }
    function resetFilters(){
      [stateFilter,nameFilter,codeFilter].forEach(s=>Array.from(s.options).forEach(o=>o.selected=true));
      minLevel.value=0; maxLevel.value=10000;
      filterMarkers();
    }

    // Wykresy
    new Chart(stateChart,{
      type:'pie',
      data:{labels:['Alarmowe','Ostrzegawcze','Normalne'],datasets:[{data:[{{counts.alarm}},{{counts.warning}},{{counts.normal}}]}]},
      options:{responsive:true,plugins:{datalabels:{formatter:(v,ctx)=>Math.round(v/ctx.dataset.data.reduce((a,b)=>a+b,0)*100)+'%',color:'#fff',font:{weight:'bold'}},legend:{position:'bottom'}}}
    });
    new Chart(top10Chart,{
      type:'bar',
      data:{labels:{{top10_labels_full|tojson}},datasets:[{label:'Poziom wody',data:{{top10_values|tojson}}}]},
      options:{indexAxis:'y',responsive:true,scales:{x:{beginAtZero:true}}}
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
    generate_html_from_csv()
