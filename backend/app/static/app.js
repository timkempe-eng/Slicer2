// Slicer2 mobile web client: upload -> poll -> download.
const $ = (id) => document.getElementById(id);
const form = $("slice-form");
const statusEl = $("status");

$("file").addEventListener("change", (e) => {
  const f = e.target.files[0];
  $("file-label").textContent = f ? f.name : "Tap to choose a model";
});

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  if (!$("legal").checked) {
    alert("Please confirm the rights/liability statement to continue.");
    return;
  }
  const file = $("file").files[0];
  if (!file) return;

  const fd = new FormData();
  fd.append("file", file);
  fd.append("printer", $("printer").value);
  fd.append("filament", $("filament").value);
  fd.append("layer_height_mm", $("layer_height_mm").value);
  fd.append("infill_density", $("infill_density").value);
  fd.append("supports", $("supports").checked);

  setStatus(`<span class="spinner"></span>Uploading & queuing…`);
  $("submit").disabled = true;

  try {
    const res = await fetch("/api/slice", { method: "POST", body: fd });
    if (!res.ok) throw new Error((await res.json()).detail || res.statusText);
    const job = await res.json();
    pollJob(job.id);
  } catch (err) {
    setStatus(`<p class="err">Failed: ${err.message}</p>`);
    $("submit").disabled = false;
  }
});

async function pollJob(id) {
  try {
    const res = await fetch(`/api/jobs/${id}`);
    const job = await res.json();

    if (job.status === "done") {
      const r = job.result || {};
      const time = r.estimated_print_seconds ? fmtTime(r.estimated_print_seconds) : "—";
      const grams = r.filament_grams ? `${r.filament_grams} g` : "—";
      setStatus(`
        <p><strong>Sliced!</strong></p>
        <p>Est. print time: ${time} &middot; Filament: ${grams}</p>
        <p><a href="/api/jobs/${id}/download" download>⬇︎ Download .gcode.3mf</a></p>
        <p style="color:var(--muted);font-size:.85rem">
          Open the downloaded file in <strong>Bambu Handy</strong> to send it to your printer.
        </p>`);
      $("submit").disabled = false;
      return;
    }
    if (job.status === "failed") {
      setStatus(`<p class="err">Slicing failed:\n${job.error || "unknown error"}</p>`);
      $("submit").disabled = false;
      return;
    }
    setStatus(`<span class="spinner"></span>${job.status === "slicing" ? "Slicing…" : "Queued…"}`);
    setTimeout(() => pollJob(id), 1500);
  } catch (err) {
    setStatus(`<p class="err">Lost connection: ${err.message}</p>`);
    $("submit").disabled = false;
  }
}

function setStatus(html) {
  statusEl.classList.remove("hidden");
  statusEl.innerHTML = html;
}
function fmtTime(s) {
  const h = Math.floor(s / 3600), m = Math.round((s % 3600) / 60);
  return h ? `${h}h ${m}m` : `${m}m`;
}
