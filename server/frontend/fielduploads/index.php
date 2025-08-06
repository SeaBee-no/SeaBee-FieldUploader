<?php
require '/var/www/authenticate.php';
authenticate("SeaBee fielduploads");
?>
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Seabirds Clusters Map</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet/dist/leaflet.css" />
  <link rel="stylesheet" href="https://unpkg.com/leaflet-draw/dist/leaflet.draw.css" />
  <style>
    body { margin:0; display:flex; height:100vh; font-family:sans-serif; }
    #sidebar {
      width:30%; min-width:300px;
      display:flex; flex-direction:column;
      background:#f7f7f7;
    }
    #clusterDetails {
      flex:1; padding:10px;
      background:#fff; border-bottom:2px solid #ccc;
      overflow-y:auto;
    }
    #clusterList {
      flex:1; padding:10px;
      overflow-y:auto;
    }
    #clusterList-controls {
      display:flex; flex-wrap:wrap; gap:10px;
      padding:8px; background:#fff; border-bottom:1px solid #ccc;
      align-items:center;
    }
    #clusterSummary {
      padding:8px; background:#eef;
      border:1px solid #ccd; border-radius:4px;
      margin-bottom:12px;
    }
    #clusterDetails form div { margin-bottom:8px; }
    #clusterDetails form label {
      display:block; font-weight:bold; margin-bottom:2px;
    }
    #clusterDetails form input {
      width:100%; box-sizing:border-box; padding:4px;
    }
    #clusterItems .cluster-item {
      display:flex; align-items:center;
      margin-bottom:12px; padding:6px;
      background:#fff; border:1px solid #ddd; border-radius:4px;
    }
    #clusterItems .cluster-item h4 {
      margin:0 0 4px; font-size:1em;
    }
    .zoom-btn {
      font-size:0.9em; padding:2px 6px; margin-left:auto;
    }
    #map { flex:1; }
  </style>
</head>
<body>
  <div id="sidebar">
    <div id="clusterDetails">
      <p><em>Select a cluster to view/edit its properties.</em></p>
    </div>
    <div id="clusterList">
      <div id="clusterList-controls">
        <label><input type="checkbox" id="showAllChk"> Show all clusters</label>
        <label><input type="checkbox" id="showSkippedChk"> Show skipped clusters</label>
        <label><input type="checkbox" id="inViewChk"> Only show clusters in view</label>
        <button id="mergeBtn" disabled>Merge Selected</button>
        <button id="splitBtn" disabled>Split This Cluster</button>
      </div>
      <h3>Clusters</h3>
      <div id="clusterItems">Loading…</div>
    </div>
  </div>
  <div id="map"></div>

  <script src="https://unpkg.com/leaflet/dist/leaflet.js"></script>
  <script src="https://unpkg.com/leaflet-draw/dist/leaflet.draw.js"></script>
  <script>
    const MAX_ZOOM = 18;

    // Initialize map & basemaps (omitted here for brevity; same as before)
    const map = L.map('map').setView([64,11],5);
    const basemaps = {
      'OpenStreetMap': L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{
        maxZoom:22, attribution:'© OSM'
      }).addTo(map),
      'Norgeskart': L.tileLayer('https://cache.kartverket.no/v1/wmts/1.0.0/topo/default/webmercator/{z}/{y}/{x}.png',{
        attribution:'© Kartverket'
      }),
      'Sjøkart': L.tileLayer('https://cache.kartverket.no/v1/wmts/1.0.0/sjokartraster/default/webmercator/{z}/{y}/{x}.png',{
        attribution:'© Kartverket'
      }),
      'CartoDB Positron': L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',{
        maxZoom:22
      }),
      'Norge i bilder': L.tileLayer(
        'https://opencache.statkart.no/gatekeeper/gk/gk.open_nib_web_mercator_wmts_v2?' +
        'layer=Nibcache_web_mercator_v2&style=default&tilematrixset=default028mm&Service=WMTS&Request=GetTile&Version=1.0.0&Format=image/jpeg&TileMatrix={z}&TileCol={x}&TileRow={y}',
        { maxZoom:19 }
      ),
      'Google Flyfoto': L.tileLayer('https://{s}.google.com/vt/lyrs=s&x={x}&y={y}&z={z}',{
        maxZoom:21, subdomains:['mt0','mt1','mt2','mt3']
      })
    };
    L.control.layers(basemaps).addTo(map);
    
    map.createPane('polygonsPane'); map.getPane('polygonsPane').style.zIndex = 300;
    map.createPane('pointsPane');   map.getPane('pointsPane').style.zIndex   = 600;

    // UI elements
    const showAllChk     = document.getElementById('showAllChk');
    const showSkippedChk = document.getElementById('showSkippedChk');
    const inViewChk      = document.getElementById('inViewChk');
    const mergeBtn       = document.getElementById('mergeBtn');
    const splitBtn       = document.getElementById('splitBtn');
    const clusterDetails = document.getElementById('clusterDetails');
    const clusterItems   = document.getElementById('clusterItems');
    let currentPointsLayer  = null;
    let currentClusterProps = null;

    // Re-draw list on toggles or map move (for in-view)
    showAllChk.addEventListener('change', loadClusterList);
    showSkippedChk.addEventListener('change', loadClusterList);
    inViewChk.addEventListener('change', loadClusterList);
    map.on('moveend', () => { if (inViewChk.checked) loadClusterList(); });

    function updateClusterSummary(summary) {
      const sumDiv = document.getElementById('clusterSummary');
      if (!sumDiv) return;
      const dirs = Array.isArray(summary.directories)
        ? summary.directories.join(', ')
        : '–';
      sumDiv.innerHTML = `
        <strong>Cluster ${summary.cluster_id}</strong><br>
        First: ${summary.first_timestamp||'–'} 
        Last: ${summary.last_timestamp||'–'}<br>
        Count: ${summary.nfiles} files<br>
        Dirs: ${dirs}
      `;
    }

    function showClusterDetails(props) {
      currentClusterProps = props;
      splitBtn.disabled = false;
      clusterDetails.innerHTML = '';

      // Summary
      const sum = document.createElement('div');
      sum.id = 'clusterSummary';
      const dirs = Array.isArray(props.directories)
        ? props.directories.join(', ')
        : '…';
      sum.innerHTML = `
        <strong>Cluster ${props.cluster_id}</strong><br>
        First: ${props.first_timestamp||'…'} 
        Last: ${props.last_timestamp||'…'}<br>
        Count: ${props.nfiles} files<br>
        Dirs: ${dirs}
      `;
      clusterDetails.appendChild(sum);

      // Editable form
      const form = document.createElement('form');
      const fields = [
        {name:'grouping',type:'text'},{name:'area',type:'text'},
        {name:'datetime',type:'text'},{name:'organisation',type:'text'},
        {name:'creator_name',type:'text'},{name:'project',type:'text'},
        {name:'theme',type:'text'},
        {name:'mosaic',type:'checkbox'},{name:'classify',type:'checkbox'},
        {name:'publish',type:'checkbox'},{name:'readyforsigma',type:'checkbox'},
        {name:'skip',type:'checkbox'}
      ];
      fields.forEach(f=>{
        const row = document.createElement('div');
        const lbl = document.createElement('label');
        lbl.textContent = f.name.replace('_',' ').toUpperCase();
        lbl.htmlFor = f.name;
        const inp = document.createElement('input');
        inp.type = f.type; inp.id = f.name; inp.name = f.name;
        if (f.type==='checkbox') inp.checked = !!props[f.name];
        else inp.value = props[f.name]||'';
        row.appendChild(lbl);
        row.appendChild(inp);
        form.appendChild(row);
      });
      const saveBtn = document.createElement('button');
      saveBtn.type = 'button';
      saveBtn.textContent = 'Save Changes';
      saveBtn.onclick = () => {
        const payload = { cluster_id: props.cluster_id };
        fields.forEach(f => {
          payload[f.name] = (f.type==='checkbox')
            ? form.elements[f.name].checked?1:0
            : form.elements[f.name].value;
        });
        fetch('update_cluster.php',{
          method:'POST',
          headers:{'Content-Type':'application/json'},
          body:JSON.stringify(payload)
        })
        .then(r=>r.json())
        .then(res=>{
          if (res.success) {
            alert('Cluster updated');
            loadClusterPoints(props.cluster_id);
            loadClusterList();
          } else {
            alert('Error: '+res.error);
          }
        })
        .catch(()=>alert('Network error'));
      };
      form.appendChild(saveBtn);
      clusterDetails.appendChild(form);
    }

    function loadClusterPoints(id) {
      if (currentPointsLayer) map.removeLayer(currentPointsLayer);
      fetch(`points.php?cluster_id=${id}`)
        .then(r=>r.json())
        .then(data=>{
          updateClusterSummary(data.summary);
          currentPointsLayer = L.geoJSON(data.features,{
            pane:'pointsPane',
            pointToLayer:(_,ll)=>L.circleMarker(ll,{radius:4,color:'red'}),
            onEachFeature:(f,layer)=>layer.bindTooltip(
              f.properties.filename + '<br>' + f.properties.datetimetaken
            )
          }).addTo(map);
        });
    }

    function loadClusterList() {
      mergeBtn.disabled = true;
      splitBtn.disabled = true;
      clusterItems.innerHTML = 'Loading…';
      // clear old polygons
      map.eachLayer(l=>l.options&&l.options.pane==='polygonsPane'&&map.removeLayer(l));

      const includeAll     = showAllChk.checked;
      const includeSkipped = showSkippedChk.checked;
      const viewOnly       = inViewChk.checked;
      const bounds         = map.getBounds();

      fetch('clusters.php')
        .then(r=>r.json())
        .then(data=>{
          clusterItems.innerHTML = '';
          L.geoJSON(data, {
            pane:'polygonsPane',
            style:{color:'blue',weight:2,fillOpacity:0.1},
            filter: feature => {
              const p = feature.properties;
              if (!includeAll && p.readyforsigma) return false;
              if (!includeSkipped && p.skip)        return false;
              return true;
            },
            onEachFeature:(feature,layer)=>{
              layer.addTo(map);
              const p = feature.properties, id = p.cluster_id;
              const inView = viewOnly ? bounds.intersects(layer.getBounds()) : true;
              if (!inView) return;

              const cb = document.createElement('input');
              cb.type='checkbox'; cb.value=id;
              cb.onchange = ()=>mergeBtn.disabled =
                clusterItems.querySelectorAll('input:checked').length < 2;

              const div = document.createElement('div');
              div.className = 'cluster-item';
              div.appendChild(cb);

              const info = document.createElement('div');
              info.innerHTML = `
                <h4>Cluster ${id}</h4>
                <div><strong>Mission:</strong> ${p.grouping||'–'}</div>
                <div><strong>Area:</strong>    ${p.area||'–'}</div>
                <div><strong>Date:</strong>    ${p.datetime||'–'}</div>
              `;
              div.appendChild(info);

              const zoom = document.createElement('button');
              zoom.className = 'zoom-btn';
              zoom.textContent = 'Zoom & Edit';
              zoom.onclick = ()=>{
                map.fitBounds(layer.getBounds(),{maxZoom:MAX_ZOOM});
                showClusterDetails(p);
                loadClusterPoints(id);
              };
              div.appendChild(zoom);
              clusterItems.appendChild(div);

              layer.on('click', ()=>{
                map.fitBounds(layer.getBounds(),{maxZoom:MAX_ZOOM});
                showClusterDetails(p);
                loadClusterPoints(id);
              });
            }
          });
        });
    }

    mergeBtn.onclick = ()=>{
      const sel = Array.from(clusterItems.querySelectorAll('input:checked'))
                       .map(cb=>+cb.value);
      if (sel.length < 2) return;
      fetch('merge_clusters.php',{
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({clusters:sel})
      })
      .then(r=>r.json())
      .then(res=>{
        if (res.success) {
          alert('Merged into ' + res.new_id);
          loadClusterList();
          if (currentClusterProps && sel.includes(currentClusterProps.cluster_id))
            loadClusterPoints(res.new_id);
        } else {
          alert('Error: ' + res.error);
        }
      });
    };

    splitBtn.onclick = ()=>{
      if (!currentClusterProps) return;
      const drawCtrl = new L.Control.Draw({
        draw:{polygon:true,polyline:false,rectangle:false,circle:false,marker:false},
        edit:false
      });
      map.addControl(drawCtrl);
      map.once('draw:created', e=>{
        const polyGeo = e.layer.toGeoJSON().geometry;
        map.removeControl(drawCtrl);
        fetch('split_cluster.php',{
          method:'POST',
          headers:{'Content-Type':'application/json'},
          body:JSON.stringify({
            cluster_id: currentClusterProps.cluster_id,
            polygon:    polyGeo
          })
        })
        .then(r=>r.json())
        .then(res=>{
          if (res.success) {
            alert(`Split complete: new cluster ${res.new_id}`);
            loadClusterList();
            map.fitBounds(
              [[res.bounds2.minY,res.bounds2.minX],[res.bounds2.maxY,res.bounds2.maxX]],
              {maxZoom:MAX_ZOOM}
            );
          } else {
            alert('Error: ' + res.error);
          }
        })
        .catch(e=>alert('Network error:' + e));
      });
    };

    // Initial load
    loadClusterList();
  </script>
</body>
</html>
