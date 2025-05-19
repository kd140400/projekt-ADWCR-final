import csv
from jinja2 import Template
from datetime import datetime
import requests
import pandas as pd
import json
import statistics

API_URL = "https://danepubliczne.imgw.pl/api/data/hydro2"
CSV_FILE = 'hydro_data.csv'
GEOJSON_FILE = 'poland.geojson'

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

def generate_html_from_csv():
    # 1) Wczytanie CSV
    data = []
    with open(CSV_FILE, encoding='utf-8-sig') as f:
        for r in csv.DictReader(f, delimiter=';'):
            data.append({k: (v or None) for k, v in r.items()})

    # 2) Klasyfikacja
    alarm_state, warning_state, normal_state = classify_water_levels(data)

    # 3) Dane do wykresów
    counts = {
        'alarm': len(alarm_state),
        'warning': len(warning_state),
        'normal': len(normal_state)
    }
    levels = [(r['kod_stacji'], float(r['stan'])) for r in data if r.get('stan')]
    top10 = sorted(levels, key=lambda x: x[1], reverse=True)[:10]
    station_names = {r['kod_stacji']: r['nazwa_stacji'] for r in data}
    top10_labels = [f"{k} – {station_names.get(k)}" for k,_ in top10]
    top10_values = [v for _,v in top10]

    # 4) Statystyki
    nums = [float(r['stan']) for r in data if r.get('stan')]
    stats = {
        'Liczba pomiarów': len(nums),
        'Min': f"{min(nums):.2f}",
        'Max': f"{max(nums):.2f}",
        'Średnia': f"{statistics.mean(nums):.2f}",
        'Mediana': f"{statistics.median(nums):.2f}",
    }

    # 5) Unikalne listy
    unique_names = sorted({r['nazwa_stacji'] for r in data if r.get('nazwa_stacji')})
    unique_codes = sorted({r['kod_stacji'] for r in data if r.get('kod_stacji')})

    # 6) GeoJSON
    boundary = json.load(open(GEOJSON_FILE, encoding='utf-8'))

    # 7) Generowanie HTML
    tpl = Template("""<!DOCTYPE html>
<html lang="pl">
<head>
  <meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Dane hydrologiczne IMGW</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
  <style>
    body{font-family:Arial,sans-serif;margin:20px;background:#f5f5f5;}
    h1,h2{text-align:center;color:#2c3e50;}
    .tabs{display:flex;gap:10px;margin-bottom:10px;}
    .tab-button{padding:8px 16px;border:none;background:#eee;cursor:pointer;border-radius:4px 4px 0 0;}
    .tab-button.active{background:#fff;border-bottom:2px solid #fff;}
    .tab-content{display:none;background:#fff;padding:10px;border:1px solid #ddd;border-top:none;border-radius:0 4px 4px 4px;}
    .tab-content.active{display:block;}
    .table-container{overflow-x:auto;box-shadow:0 2px 4px rgba(0,0,0,0.1);border-radius:8px;}
    table{width:100%;border-collapse:collapse;font-size:0.9em;}
    th,td{padding:8px;border:1px solid #ddd;text-align:left;}
    th{background:#3498db;color:#fff;position:sticky;top:0;}
    #leaflet-map{width:100%;height:500px;border-radius:8px;box-shadow:0 2px 4px rgba(0,0,0,0.1);}
    .filters{position:absolute;top:60px;right:20px;width:220px;background:#fff;padding:10px;border:1px solid #ccc;border-radius:4px;z-index:1000;}
    .filters label{display:block;margin-bottom:8px;font-size:0.9em;}
    .legend{background:#fff;padding:6px 8px;font-size:13px;line-height:1.4;border:1px solid #ccc;border-radius:4px;}
    .legend i{width:12px;height:12px;display:inline-block;margin-right:6px;opacity:0.7;}
    .stats-table{width:60%;margin:0 auto 20px;border-collapse:collapse;}
    .stats-table th,.stats-table td{border:1px solid #ddd;padding:6px;text-align:center;}
    .stats-table th{background:#3498db;color:#fff;}
    canvas{max-width:100%;margin:20px 0;}
    .footer{text-align:center;color:#555;margin-top:20px;}
    #refresh-button{position:fixed;top:20px;right:20px;padding:8px 16px;background:#3498db;color:#fff;border:none;border-radius:4px;cursor:pointer;box-shadow:0 2px 4px rgba(0,0,0,0.2);}
    #refresh-button:hover{background:#2980b9;}
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

  <!-- TABELA -->
  <div id="table" class="tab-content active">
    {% if alarm_state %}
      <h2>⚠️ Stan alarmowy (≥500)</h2>
      <div class="table-container">
        <table><thead><tr><th>Kod</th><th>Stacja</th><th>Stan</th><th>Data</th></tr></thead>
        <tbody>{% for r in alarm_state %}
          <tr><td>{{r.kod_stacji}}</td><td>{{r.nazwa_stacji}}</td><td>{{r.stan}}</td><td>{{r.stan_data}}</td></tr>
        {% endfor %}</tbody></table>
      </div>
    {% endif %}
    {% if warning_state %}
      <h2>⚠️ Stan ostrzegawczy (450–499)</h2>
      <div class="table-container">
        <table><thead><tr><th>Kod</th><th>Stacja</th><th>Stan</th><th>Data</th></tr></thead>
        <tbody>{% for r in warning_state %}
          <tr><td>{{r.kod_stacji}}</td><td>{{r.nazwa_stacji}}</td><td>{{r.stan}}</td><td>{{r.stan_data}}</td></tr>
        {% endfor %}</tbody></table>
      </div>
    {% endif %}
    <h2>Wszystkie stacje</h2>
    <div class="table-container">
      <table><thead>
        <tr><th>Kod</th><th>Stacja</th><th>Stan</th><th>Data</th><th>Status</th></tr>
      </thead><tbody>{% for r in data %}
        {% set lvl = (r.stan|float) if r.stan else 0 %}
        <tr>
          <td>{{r.kod_stacji}}</td><td>{{r.nazwa_stacji}}</td>
          <td>{{r.stan}}</td><td>{{r.stan_data}}</td>
          <td>{% if lvl>=500 %}ALARM{% elif lvl>=450 %}OSTRZEŻENIE{% else %}NORMALNY{% endif %}</td>
        </tr>
      {% endfor %}</tbody></table>
    </div>
  </div>

  <!-- MAPA -->
  <div id="map" class="tab-content" style="position:relative;">
    <h2>Mapa stacji</h2>
    <div class="filters">
      <label>Stan:<br>
        <select id="stateFilter" multiple size="3">
          <option value="alarm" selected>Alarmowe</option>
          <option value="warning" selected>Ostrzegawcze</option>
          <option value="normal" selected>Normalne</option>
        </select>
        <button class="clear-btn" onclick="clearSelect('stateFilter')">Wyczyść</button>
      </label>
      <label>Nazwa:<br>
        <select id="nameFilter" multiple size="5">
          {% for n in unique_names %}
          <option value="{{n}}" selected>{{n}}</option>
          {% endfor %}
        </select>
        <button class="clear-btn" onclick="clearSelect('nameFilter')">Wyczyść</button>
      </label>
      <label>Kod:<br>
        <select id="codeFilter" multiple size="5">
          {% for c in unique_codes %}
          <option value="{{c}}" selected>{{c}}</option>
          {% endfor %}
        </select>
        <button class="clear-btn" onclick="clearSelect('codeFilter')">Wyczyść</button>
      </label>
      <label>Zakres stanów:<br>
        <input type="number" id="minLevel" value="0" style="width:60px;">–
        <input type="number" id="maxLevel" value="10000" style="width:60px;">
        <button onclick="applyRange()">OK</button>
        <button class="clear-btn" onclick="clearRange()">Wyczyść</button>
      </label>
    </div>
    <div id="leaflet-map"></div>
  </div>

  <!-- WYKRESY -->
  <div id="charts" class="tab-content">
    <h2>Statystyki stanu wody</h2>
    <table class="stats-table"><thead><tr><th>Metryka</th><th>Wartość</th></tr></thead><tbody>
      {% for k,v in stats.items() %}
      <tr><td>{{k}}</td><td>{{v}}</td></tr>
      {% endfor %}
    </tbody></table>
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
  <script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-datalabels@2/dist/chartjs-plugin-datalabels.min.js"></script>
  <script>
    // PRZEŁĄCZANIE ZAKŁADEK
    document.querySelectorAll('.tab-button').forEach(btn=>{
      btn.type = 'button';
      btn.addEventListener('click',()=>{
        document.querySelectorAll('.tab-button').forEach(b=>b.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(c=>c.classList.remove('active'));
        btn.classList.add('active');
        document.getElementById(btn.dataset.tab).classList.add('active');
        if(btn.dataset.tab==='map') setTimeout(()=>map.invalidateSize(),200);
      });
    });

    // LEAFLET & FILTROWANIE
    var map = L.map('leaflet-map').setView([52.0,19.0],6);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{attribution:'© OSM'}).addTo(map);
    L.geoJSON({{ boundary|tojson }},{style:{color:'#555',weight:1,fill:false}}).addTo(map);
    var markers=[]; {{ data|tojson }}.forEach(s=>{
      if(s.lon&&s.lat){
        var cat=s.stan>=500?'alarm':(s.stan>=450?'warning':'normal');
        var m=L.circleMarker([+s.lat,+s.lon],{radius:5,color:cat==='alarm'?'red':cat==='warning'?'orange':'green'})
           .bindPopup(`<b>${s.kod_stacji} – ${s.nazwa_stacji}</b><br>Stan: ${s.stan}`);
        m.cat=cat; m.name=s.nazwa_stacji; m.code=s.kod_stacji; m.level=+s.stan;
        m.addTo(map); markers.push(m);
      }
    });
    L.control({position:'bottomright'}).onAdd=()=>{let d=L.DomUtil.create('div','legend');
      d.innerHTML='<i style="background:red"></i>Alarmowe<br><i style="background:orange"></i>Ostrz.<br><i style="background:green"></i>Normalne';return d;
    }.addTo(map);

    function filterMarkers(){
      let st=Array.from(stateFilter.selectedOptions).map(o=>o.value);
      let nm=Array.from(nameFilter.selectedOptions).map(o=>o.value);
      let cd=Array.from(codeFilter.selectedOptions).map(o=>o.value);
      let minL=+minLevel.value, maxL=+maxLevel.value;
      markers.forEach(m=>{
        let ok=st.includes(m.cat)&&nm.includes(m.name)&&cd.includes(m.code)&&m.level>=minL&&m.level<=maxL;
        ok?map.addLayer(m):map.removeLayer(m);
      });
    }
    function clearSelect(id){let s=document.getElementById(id);s.querySelectorAll('option').forEach(o=>o.selected=false);filterMarkers();}
    function applyRange(){filterMarkers();}
    function clearRange(){minLevel.value=0;maxLevel.value=10000;filterMarkers();}

    stateFilter.onchange=filterMarkers;
    nameFilter.onchange=filterMarkers;
    codeFilter.onchange=filterMarkers;

    // WYKRESY
    Chart.register(ChartDataLabels);
    new Chart(stateChart,{
      type:'pie',
      data:{labels:['Alarmowe','Ostrzegawcze','Normalne'],datasets:[{data:[{{counts.alarm}},{{counts.warning}},{{counts.normal}}]}]},
      options:{
        responsive:true,
        plugins:{
          datalabels:{
            formatter:(v,ctx)=> Math.round(v/ctx.chart.data.datasets[0].data.reduce((a,b)=>a+b,0)*100)+'%',
            color:'#fff',font:{weight:'bold',size:14}
          },
          legend:{position:'bottom'}
        }
      }
    });
    new Chart(top10Chart,{
      type:'bar',
      data:{labels:{{top10_labels|tojson}},datasets:[{label:'Poziom wody',data:{{top10_values|tojson}}}]},
      options:{indexAxis:'y',responsive:true,scales:{x:{beginAtZero:true}}}
    });
  </script>
</body>
</html>
    """)
    html = tpl.render(
        data=data,
        alarm_state=alarm_state,
        warning_state=warning_state,
        normal_state=normal_state,
        counts=counts,
        top10_labels=top10_labels,
        top10_values=top10_values,
        stats=stats,
        unique_names=unique_names,
        unique_codes=unique_codes,
        boundary=boundary,
        timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    )
    with open('hydro_table.html','w',encoding='utf-8') as f:
        f.write(html)
    print("✅ Wygenerowano hydro_table.html")

if __name__=="__main__":
    generate_html_from_csv()
