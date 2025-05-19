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
            if lvl >= 500: alarm.append(row)
            elif lvl >= 450: warning.append(row)
            else: normal.append(row)
        except:
            continue
    return alarm, warning, normal

def generate_html():
    # 1. Wczytaj CSV
    data = []
    with open(CSV_FILE, encoding='utf-8-sig') as f:
        for r in csv.DictReader(f, delimiter=';'):
            data.append({k: (v or None) for k,v in r.items()})

    # 2. Podział na kategorie
    alarm, warning, normal = classify_water_levels(data)

    # 3. Dane do wykresów
    counts = {'alarm': len(alarm), 'warning': len(warning), 'normal': len(normal)}
    levels = [(r['kod_stacji'], float(r['stan'])) for r in data if r.get('stan')]
    top10 = sorted(levels, key=lambda x: x[1], reverse=True)[:10]
    top10_labels = [f"{k} – { {r['kod_stacji']:r['nazwa_stacji'] for r in data}.get(k)}" for k,v in top10]
    top10_values = [v for k,v in top10]

    # 4. Statystyki
    nums = [float(r['stan']) for r in data if r.get('stan')]
    stats = {
        'Liczba pomiarów': len(nums),
        'Min': f"{min(nums):.2f}",
        'Max': f"{max(nums):.2f}",
        'Średnia': f"{statistics.mean(nums):.2f}",
        'Mediana': f"{statistics.median(nums):.2f}"
    }

    # 5. Unikalne filtry
    unique_names = sorted({r['nazwa_stacji'] for r in data if r.get('nazwa_stacji')})
    unique_codes = sorted({r['kod_stacji'] for r in data if r.get('kod_stacji')})

    # 6. Granice Polski
    boundary = json.load(open(GEOJSON_FILE, encoding='utf-8'))

    # 7. Render HTML
    tpl = Template("""
<!DOCTYPE html>
<html lang="pl">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>IMGW hydro2</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<style>
  body{font-family:Arial,sans-serif;background:#f5f5f5;margin:20px}
  h1,h2{text-align:center;color:#2c3e50}
  .tabs{display:flex;gap:10px;margin-bottom:10px}
  .tab-button{padding:8px 16px;border:none;background:#eee;cursor:pointer;border-radius:4px 4px 0 0}
  .tab-button.active{background:#fff;border-bottom:2px solid #fff}
  .tab-content{display:none;background:#fff;padding:10px;border:1px solid #ddd;border-top:none;border-radius:0 4px 4px 4px}
  .tab-content.active{display:block}
  .filters{position:absolute;top:60px;right:20px;width:200px;background:#fff;padding:10px;border:1px solid #ccc;border-radius:4px;z-index:1000}
  .filters h3{margin:0 0 5px;font-size:14px}
  .filters label{display:block;margin-bottom:4px;font-size:13px}
  #leaflet-map{width:100%;height:500px;margin-top:10px}
  .legend{background:#fff;padding:6px;border:1px solid #ccc;border-radius:4px;font-size:13px;line-height:1.4}
  .legend i{width:12px;height:12px;display:inline-block;margin-right:6px;opacity:0.7}
  table{width:100%;border-collapse:collapse;margin-bottom:10px}
  th,td{border:1px solid #ddd;padding:8px;text-align:left}
  th{background:#3498db;color:#fff;position:sticky;top:0}
</style>
</head>
<body>
  <h1>Dane hydrologiczne IMGW (hydro2)</h1>
  <div class="tabs">
    <button class="tab-button active" data-tab="tabela">Tabela</button>
    <button class="tab-button" data-tab="mapa">Mapa</button>
    <button class="tab-button" data-tab="wykresy">Wykresy i statystyki</button>
  </div>

  <!-- TABELA -->
  <div id="tabela" class="tab-content active">
    {% if alarm %}
      <h2>⚠️ Stan alarmowy (≥500)</h2>
      <table><thead><tr><th>Kod</th><th>Stacja</th><th>Stan</th><th>Data</th></tr></thead><tbody>
      {% for r in alarm %}
        <tr><td>{{r.kod_stacji}}</td><td>{{r.nazwa_stacji}}</td><td>{{r.stan}}</td><td>{{r.stan_data}}</td></tr>
      {% endfor %}</tbody></table>
    {% endif %}
    {% if warning %}
      <h2>⚠️ Stan ostrzegawczy (450–499)</h2>
      <table><thead><tr><th>Kod</th><th>Stacja</th><th>Stan</th><th>Data</th></tr></thead><tbody>
      {% for r in warning %}
        <tr><td>{{r.kod_stacji}}</td><td>{{r.nazwa_stacji}}</td><td>{{r.stan}}</td><td>{{r.stan_data}}</td></tr>
      {% endfor %}</tbody></table>
    {% endif %}
    <h2>Wszystkie stacje</h2>
    <table><thead><tr><th>Kod</th><th>Stacja</th><th>Stan</th><th>Data</th><th>Status</th></tr></thead><tbody>
    {% for r in data %}
      {% set lvl = (r.stan|float) if r.stan %} 
      <tr>
        <td>{{r.kod_stacji}}</td><td>{{r.nazwa_stacji}}</td><td>{{r.stan}}</td><td>{{r.stan_data}}</td>
        <td>{% if lvl>=500 %}ALARM{% elif lvl>=450 %}OSTRZEŻENIE{% else %}NORMALNY{% endif %}</td>
      </tr>
    {% endfor %}</tbody></table>
  </div>

  <!-- MAPA -->
  <div id="mapa" class="tab-content" style="position:relative">
    <h2>Mapa stacji</h2>
    <div class="filters">
      <h3>Filtruj</h3>
      <label><input type="checkbox" id="allStates" checked> Wszystkie stany</label>
      <label><input type="checkbox" class="fstate" value="alarm" checked> Alarmowe</label>
      <label><input type="checkbox" class="fstate" value="warning" checked> Ostrzegawcze</label>
      <label><input type="checkbox" class="fstate" value="normal" checked> Normalne</label>
      <hr>
      <label><input type="checkbox" id="allNames" checked> Wszystkie nazwy</label>
      {% for n in unique_names %}
        <label><input type="checkbox" class="fname" value="{{n}}" checked> {{n}}</label>
      {% endfor %}
      <hr>
      <label><input type="checkbox" id="allCodes" checked> Wszystkie kody</label>
      {% for c in unique_codes %}
        <label><input type="checkbox" class="fcode" value="{{c}}" checked> {{c}}</label>
      {% endfor %}
      <hr>
      <label>Zakres stanu:<br>
        <input type="number" id="minL" value="0" style="width:60px;"> –
        <input type="number" id="maxL" value="10000" style="width:60px;">
        <button id="applyRange">OK</button>
        <button id="clearRange">Czyść</button>
      </label>
    </div>
    <div id="leaflet-map"></div>
  </div>

  <!-- WYKRESY -->
  <div id="wykresy" class="tab-content">
    <h2>Statystyki stanu wody</h2>
    <table style="margin:0 auto 20px;border:1px solid #ddd;border-collapse:collapse">
      <thead><tr><th>Metryka</th><th>Wartość</th></tr></thead><tbody>
      {% for k,v in stats.items() %}
        <tr><td style="border:1px solid #ddd;padding:4px">{{k}}</td><td style="border:1px solid #ddd;padding:4px">{{v}}</td></tr>
      {% endfor %}
      </tbody>
    </table>
    <h2>Liczba stacji wg kategorii</h2><canvas id="stateChart"></canvas>
    <h2>Top 10 stacji wg poziomu</h2><canvas id="top10Chart"></canvas>
  </div>

  <div class="footer">Ostatnia aktualizacja: {{timestamp}}</div>

  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-datalabels"></script>
  <script>
    Chart.register(ChartDataLabels);

    // Zakładki
    document.querySelectorAll('.tab-button').forEach(b=>{
      b.onclick=()=>{
        document.querySelectorAll('.tab-button').forEach(x=>x.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(x=>x.classList.remove('active'));
        b.classList.add('active');
        document.getElementById(b.dataset.tab).classList.add('active');
        if(b.dataset.tab==='mapa') setTimeout(()=>map.invalidateSize(),200);
      };
    });

    // Map
    var map=L.map('leaflet-map').setView([52,19],6);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{attribution:'© OSM'}).addTo(map);
    L.geoJSON({{boundary|tojson}},{style:{color:'#555',weight:1,fill:false}}).addTo(map);
    var markers=[];
    {{# each station in data #}}
    // dodamy poniżej w JS
    {{/each}}

    var dataStations={{data|tojson}};
    dataStations.forEach(s=>{
      if(s.lon && s.lat){
        var cat=s.stan>=500?'alarm':(s.stan>=450?'warning':'normal');
        var m=L.circleMarker([+s.lat,+s.lon],{radius:5,color:cat==='alarm'?'red':cat==='warning'?'orange':'green'}).bindPopup(`<b>${s.kod_stacji} – ${s.nazwa_stacji}</b><br>Stan: ${s.stan}`);
        m.cat=cat; m.name=s.nazwa_stacji; m.code=s.kod_stacji; m.level=+s.stan;
        m.addTo(map); markers.push(m);
      }
    });
    L.control({position:'bottomright'}).onAdd=()=>{let d=L.DomUtil.create('div','legend');d.innerHTML='<i style="background:red"></i>Alarmowe<br><i style="background:orange"></i>Ostrzegawcze<br><i style="background:green"></i>Normalne';return d;}.addTo(map);

    function filterMarkers(){
      let selS=Array.from(document.querySelectorAll('.fstate:checked')).map(i=>i.value);
      let selN=Array.from(document.querySelectorAll('.fname:checked')).map(i=>i.value);
      let selC=Array.from(document.querySelectorAll('.fcode:checked')).map(i=>i.value);
      let minL=+document.getElementById('minL').value, maxL=+document.getElementById('maxL').value;
      markers.forEach(m=>{
        let ok=selS.includes(m.cat)&&selN.includes(m.name)&&selC.includes(m.code)&&m.level>=minL&&m.level<=maxL;
        ok?map.addLayer(m):map.removeLayer(m);
      });
    }

    // Select All handlers
    document.getElementById('allStates').onclick=()=>{let c=event.target.checked;document.querySelectorAll('.fstate').forEach(x=>x.checked=c);filterMarkers()};
    document.getElementById('allNames').onclick=()=>{let c=event.target.checked;document.querySelectorAll('.fname').forEach(x=>x.checked=c);filterMarkers()};
    document.getElementById('allCodes').onclick=()=>{let c=event.target.checked;document.querySelectorAll('.fcode').forEach(x=>x.checked=c);filterMarkers()};
    document.querySelectorAll('.fstate').forEach(x=>x.onchange=filterMarkers);
    document.querySelectorAll('.fname').forEach(x=>x.onchange=filterMarkers);
    document.querySelectorAll('.fcode').forEach(x=>x.onchange=filterMarkers);
    document.getElementById('applyRange').onclick=filterMarkers;
    document.getElementById('clearRange').onclick=()=>{
      document.getElementById('minL').value=0;document.getElementById('maxL').value=10000;filterMarkers();
    };

    // Charts
    new Chart(document.getElementById('stateChart'),{
      type:'pie',data:{labels:['Alarmowe','Ostrzegawcze','Normalne'],datasets:[{data:[{{counts.alarm}},{{counts.warning}},{{counts.normal}}]}]},
      options:{responsive:true,plugins:{datalabels:{formatter:(v,ctx)=>{let sum=ctx.chart.data.datasets[0].data.reduce((a,b)=>a+b,0);return (v/sum*100).toFixed(1)+'%';},color:'#fff'}},legend:{position:'bottom'}}
    });
    new Chart(document.getElementById('top10Chart'),{
      type:'bar',data:{labels:{{top10_labels_full|tojson}},datasets:[{label:'Poziom wody',data:{{top10_values|tojson}}}]},
      options:{indexAxis:'y',responsive:true,scales:{x:{beginAtZero:true}}}
    });
  </script>
</body>
</html>
    """)
    html = tpl.render(
        data=data, alarm=alarm, warning=warning, normal=normal,
        stats=stats, counts=counts,
        top10_labels_full=top10_labels_full, top10_values=top10_values,
        unique_names=unique_names, unique_codes=unique_codes,
        boundary=boundary, timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    )
    with open('hydro_table.html','w',encoding='utf-8') as f:
        f.write(html)
    print("Gotowe: hydro_table.html")

if __name__=='__main__':
    generate_html()
