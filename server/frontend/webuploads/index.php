<?php
require '/var/www/authenticate.php';
authenticate("SeaBee webuploads");
date_default_timezone_set('Europe/Oslo');
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>SeaBee WebUploader</title>
    <style>
        body {
            font-family: 'Segoe UI', sans-serif;
            background: #f2f7fa;
            padding: 2rem;
        }
        .container {
            max-width: 600px;
            background: white;
            padding: 2rem;
            margin: auto;
            border-radius: 8px;
            box-shadow: 0 0 10px rgba(0,0,0,0.1);
        }
        label {
            display: block;
            margin-top: 1rem;
            font-weight: bold;
        }
        input[type="text"] {
            width: 100%;
            padding: 0.6rem;
            margin-top: 0.3rem;
            border-radius: 4px;
            border: 1px solid #ccc;
        }
        button {
            margin-top: 2rem;
            padding: 0.8rem 1.2rem;
            background-color: #007bbd;
            color: white;
            border: none;
            border-radius: 5px;
            cursor: pointer;
        }
        button:hover {
            background-color: #005f93;
        }
        .progress {
            margin-top: 1.5rem;
            background: #eee;
            border-radius: 5px;
            overflow: hidden;
            height: 20px;
            display: none;
        }
        .progress-bar {
            background-color: #007bbd;
            height: 100%;
            width: 0%;
            color: white;
            text-align: center;
            white-space: nowrap;
        }
        .message {
            margin-top: 1rem;
            font-weight: bold;
        }
        .message.success { color: green; }
        .message.error { color: red; }

        .drop-zone {
            margin-top: 1rem;
            padding: 1.5rem;
            border: 2px dashed #007bbd;
            border-radius: 6px;
            text-align: center;
            color: #555;
            background: #f9f9f9;
        }
        .drop-zone.dragover {
            background: #e1f0fa;
            border-color: #005f93;
            color: #000;
        }
        #fileInput {
            display: none;
        }
        #fileCount {
            margin-top: 0.5rem;
            font-style: italic;
            color: #333;
        }
        .container p {
            margin-top: 0.6rem;
            line-height: 1.4;
        }
        .container h2 {
            margin-bottom: 1rem;
            margin-top: 0;
            padding-top: 0;
        }
    </style>
</head>
<body>
  <div class="container">
    <h2>SeaBee Web Upload</h2>
    <p>
        Upload your files to the SeaBee system. When collecting data, please follow the
        <a href="https://doi.org/10.5281/zenodo.14832608" target="_blank">SeaBee data collection guidelines</a>.
    </p>
    <p>
        It is recommended to upload <strong>one mission at a time</strong> as web uploads of large data volumes can be unstable.
    </p>
    <p>
        Files uploaded will be stored in a staging folder. The SeaBee team will later move them to the correct location in the system. 
        Processing will not start until the data have been accepted and moved.
    </p>
    <p>
        Processed results will be available on Geonode at
        <a href="https://geonode.seabee.sigma2.no" target="_blank">geonode.seabee.sigma2.no</a>.<br />
        As well as through the different 
        sections on <a href="https://urbpop.no/seabee" target="_blank">urbpop.no/seabee</a>.
    </p>
    <p>
        For large datasets, a Python uploader script is also available. Please contact the SeaBee team if needed.
    </p>
    <form id="uploadForm" enctype="multipart/form-data">
      <label>Theme: <span style="color:red">*</span>
        <input type="text" name="theme" id="theme" value="Seabirds" required>
      </label>
      <label>Organisation: <span style="color:red">*</span>
        <input type="text" name="organisation" id="organisation" value="NINA" required>
      </label>
      <label>Creator Name (pilot):
        <input type="text" name="creator_name" id="creator_name" value="<?php echo htmlspecialchars($_SESSION['user_firstname'] ?? '')." ".htmlspecialchars($_SESSION['user_lastname'] ?? ''); ?>" required>
      </label>
      <label>Project:
        <input type="text" name="project" id="project">
      </label>

      <label>Upload files:</label>
      <div class="drop-zone" id="dropZone">
        Drag & drop files here or click to select<br>
        (Accepted: .jpg, .mrk, .rtk, .nav, .obs, .bin)
      </div>
      <input type="file" name="files[]" id="fileInput" multiple required accept=".jpg,.mrk,.rtk,.nav,.obs,.bin">
      <div id="fileCount">No files selected</div>
      <div id="fileWarning" class="message error" style="display:none;"></div>

      <button type="submit">Upload</button>

      <div class="progress">
        <div class="progress-bar" id="progress-bar">0%</div>
      </div>
      <div id="message" class="message"></div>
    </form>
  </div>

  <script>
    const form = document.getElementById('uploadForm');
    const dropZone = document.getElementById('dropZone');
    const fileInput = document.getElementById('fileInput');
    const fileCount = document.getElementById('fileCount');
    const fileWarning = document.getElementById('fileWarning');
    const progBar = document.getElementById('progress-bar');
    const progWrap = document.querySelector('.progress');
    const msgBox = document.getElementById('message');
    const acceptedExts = ['jpg','mrk','rtk','nav','obs','bin'];

    // Load saved fields
    window.addEventListener('load', () => {
      ['theme','organisation','creator_name','project'].forEach(f => {
        const v = localStorage.getItem('seabee_'+f);
        if (v) document.getElementById(f).value = v;
      });
    });

    // Drag & drop handlers
    dropZone.addEventListener('click', () => fileInput.click());
    dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('dragover'); });
    dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
    dropZone.addEventListener('drop', e => {
      e.preventDefault();
      dropZone.classList.remove('dragover');
      handleFiles(Array.from(e.dataTransfer.files));
    });
    fileInput.addEventListener('change', () => handleFiles(Array.from(fileInput.files)));

    function handleFiles(list) {
      const valid = [], bad = [];
      list.forEach(f => {
        const ext = f.name.split('.').pop().toLowerCase();
        acceptedExts.includes(ext) ? valid.push(f) : bad.push(f);
      });
      fileWarning.style.display = bad.length ? 'block' : 'none';
      fileWarning.textContent = bad.length ? `⚠️ ${bad.length} file(s) rejected.` : '';
      const dt = new DataTransfer();
      valid.forEach(f => dt.items.add(f));
      fileInput.files = dt.files;
      fileCount.textContent = `${valid.length} file${valid.length!==1?'s':''} selected`;
    }

    let uploadFolder = '';  // <<< new

    form.addEventListener('submit', async e => {
      e.preventDefault();
      // Save fields
      ['theme','organisation','creator_name','project'].forEach(f => {
        localStorage.setItem('seabee_'+f, document.getElementById(f).value);
      });

      const files = Array.from(fileInput.files);
      if (!files.length) return;

      // generate one timestamp in Europe/Oslo local time
      function getOsloTimestamp() {
        // produces e.g. "2025-07-03 16:05:09"
        const osloStr = new Date().toLocaleString('sv-SE', {
          timeZone: 'Europe/Oslo',
          hour12: false
        });
        // strip non-digits → "20250703160509"
        return osloStr.replace(/[^\d]/g,'').slice(0,14);
      }
      const ts = getOsloTimestamp();
      const tsInput = document.createElement('input');
      tsInput.type = 'hidden';
      tsInput.name = 'upload_timestamp';
      tsInput.value = ts;
      form.appendChild(tsInput);

      progBar.style.width = '0%';
      progBar.textContent = '0%';
      progWrap.style.display = 'block';
      msgBox.textContent = '';

      uploadFolder = '';  // reset in case of repeat

      const total = files.length;
      let done = 0;

      // upload in batches of 20
      for (let i = 0; i < total; i += 20) {
        const batch = files.slice(i, i + 20);
        await uploadBatch(batch, total, done);
        done += batch.length;
      }

      msgBox.className = 'message success';
      msgBox.innerHTML = `🎉 All files uploaded into <strong>${uploadFolder}</strong>.`;
    });

    function uploadBatch(batch, total, doneSoFar) {
      return new Promise((resolve, reject) => {
        const fd = new FormData();
        // metadata + timestamp already in form, but rebuild since we're not using form.submit
        ['theme','organisation','creator_name','project','upload_timestamp'].forEach(f => {
          fd.append(f, document.getElementsByName(f)[0].value);
        });
        batch.forEach(f => fd.append('files[]', f));

        const xhr = new XMLHttpRequest();
        xhr.open('POST', 'upload.php', true);
        xhr.upload.onprogress = e => {
          if (e.lengthComputable) {
            const batchPct = e.loaded / e.total;
            const overallPct = ((doneSoFar + batchPct * batch.length) / total) * 100;
            progBar.style.width = overallPct.toFixed(1) + '%';
            progBar.textContent = Math.floor(overallPct) + '%';
          }
        };
        xhr.onload = () => {
            if (xhr.status === 200) {
            // on first successful batch, scrape out the folder name:
            if (!uploadFolder) {
                const m = xhr.responseText.match(/<strong>([^<]+)<\/strong>/);
                if (m) uploadFolder = m[1];
            }
            resolve();
            } else {
            msgBox.className = 'message error';
            msgBox.textContent = `❌ Batch ${Math.floor(doneSoFar/20)+1} failed.`;
            reject();
            }
        };
        xhr.onerror = () => {
            msgBox.className = 'message error';
            msgBox.textContent = `❌ Network error on batch ${Math.floor(doneSoFar/20)+1}.`;
            reject();
        };
        xhr.send(fd);
      });
    }
  </script>
</body>
</html>
