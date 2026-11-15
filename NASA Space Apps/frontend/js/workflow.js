// Render actual backend outputs; library examples remain in the widget library.
window.WORKFLOW = (() => {
  const { esc } = U;
  const resultNames = {
    adiabatic_flame_temp_k: ["Adiabatic flame temperature", "K"],
    adiabatic_flame_temp_c: ["Adiabatic flame temperature", "°C"],
    estimated_dissociation_drop_k: ["Temperature drop due to dissociation", "K"],
    fuel_species: ["Fuel", ""], o2_mole_frac: ["Oxygen mole fraction", ""],
    pressure_kpa: ["Pressure", "kPa"], t_init_k: ["Initial temperature", "K"],
    diluent_gas: ["Diluent", ""], equivalence_ratio: ["Equivalence ratio", ""]
  };
  const number = new Intl.NumberFormat(undefined, { maximumSignificantDigits: 7 });
  function displayValue(value) {
    if (typeof value === "number") return number.format(value);
    if (typeof value === "boolean") return value ? "Yes" : "No";
    return String(value);
  }
  function resultTable(record) {
    const rows = Object.entries(record || {}).flatMap(([key, value]) => {
      if (value == null || (typeof value === "object" &&
          !(Array.isArray(value) && value.length > 0 && value.length <= 8 &&
            value.every(item => item != null && typeof item !== "object")))) return [];
      const [label, unit] = resultNames[key] || [key.replaceAll("_", " "), ""];
      const shown = Array.isArray(value) ? value.map(displayValue).join(", ") : displayValue(value);
      return '<tr><th scope="row">' + esc(label) + '</th><td>' +
        esc([shown, unit].filter(Boolean).join(" ")) + '</td></tr>';
    });
    return rows.length ? '<table><tbody>' + rows.join("") + '</tbody></table>' : "";
  }
  function render(b) {
    const title = `<h3>${esc(b.title || b.model_id || b.type)}</h3>`;
    const label = `<p class="muted">${esc([b.evidence_type?.replaceAll('_', ' '), b.illustrative ? 'Illustrative inputs' : ''].filter(Boolean).join(' · '))}</p>`;
    if (b.type === 'chart' && b.chart_type === 'bar') {
      const series = b.series[0];
      if (!series) return title + label;
      const unit = series.unit || "";
      const max = unit === "%" ? 100 : Math.max(...series.values.filter(Number.isFinite), Number.MIN_VALUE);
      const rows = (b.categories || []).flatMap((name, i) => {
        const value = series?.values[i];
        if (!Number.isFinite(value) || value < 0 || value > max) return [];
        const displayed = new Intl.NumberFormat(undefined, { maximumSignificantDigits: 4 }).format(value);
        return [`<tr><th scope="row">${esc(name)}</th><td style="width:65%"><meter min="0" max="${max}" value="${value}" style="width:100%" aria-label="${esc(name + ' ' + series.label)}"></meter></td><td>${esc(unit === "%" ? displayed + "%" : [displayed, unit].filter(Boolean).join(" "))}</td></tr>`];
      });
      return title + label + `<table style="width:100%"><thead><tr><th scope="col">${esc(b.x.label)}</th><th scope="col" colspan="2">${esc(series.label + (unit ? " (" + unit + ")" : ""))}</th></tr></thead><tbody>${rows.join('')}</tbody></table>`;
    }
    if (b.type === 'chart') {
      const x = b.x.values;
      const plots = b.series.map(s => {
        const points = x.map((v, i) => [v, s.values[i]]).filter(p => p.every(Number.isFinite));
        if (!points.length) return '<p>No numeric points.</p>';
        const range = a => { let lo=Infinity, hi=-Infinity; for (const v of a) {lo=Math.min(lo,v);hi=Math.max(hi,v);} return lo===hi?[lo-1,hi+1]:[lo,hi]; };
        const xr=range(points.map(p=>p[0])), yr=range(points.map(p=>p[1]));
        return `<div style="height:320px">${CH.host(size => {
          const f=CH.frame(size,{x:xr,y:yr,xticks:CH.range(...xr,4),yticks:CH.range(...yr,4),xlabel:b.x.label.replaceAll('_',' '),xunit:b.x.unit,ylabel:s.label.replaceAll('_',' '),yunit:s.unit});
          return f.axes+(b.chart_type==='scatter'?points.map(([a,c])=>CH.dot(f.sx(a),f.sy(c),{r:3,tip:`${b.x.label}: ${number.format(a)} ${b.x.unit || ''}; ${s.label}: ${number.format(c)} ${s.unit || ''}`})).join(''):CH.line(points,f.sx,f.sy));
        },{label:s.label})}</div>`;
      }).join('');
      const rows = x.slice(0,200).map((v,i) => `<tr><td>${esc(displayValue(v))}</td>${b.series.map(s => `<td>${esc(displayValue(s.values[i] ?? ''))}</td>`).join('')}</tr>`).join('');
      const table = `<details><summary>Chart data (${x.length} points${x.length > 200 ? '; first 200 shown, full values in output JSON' : ''})</summary><div style="overflow:auto;max-height:360px"><table><thead><tr><th>${esc(b.x.label)} ${esc(b.x.unit || '')}</th>${b.series.map(s => `<th>${esc(s.label)} ${esc(s.unit || '')}</th>`).join('')}</tr></thead><tbody>${rows}</tbody></table></div></details>`;
      return title+label+plots+table;
    }
    if (b.type === "calculation") {
      const download = (name, value) => `<a class="chip" download="${esc(name)}" href="data:application/json;charset=utf-8,${encodeURIComponent(JSON.stringify(value, null, 2))}">${esc(name)}</a>`;
      const artifacts = `<div class="fups">${b.input_json ? download((b.task_id || b.model_id) + '-input.json', b.input_json) : ''}${download((b.task_id || b.model_id) + '-output.json', b.data)}${b.input_provenance ? download((b.task_id || b.model_id) + '-provenance.json', b.input_provenance) : ''}</div>`;
      const data = b.data || {};
      const outputs = data.outputs || data.metrics || (b.model_id === "THM-02" ? { ...data.transport_properties, ...data.dimensionless_numbers } : data);
      const values = resultTable(outputs);
      const metric = data.frontend_summary?.headline_metric;
      const headline = !values && metric?.label && metric.value != null
        ? resultTable({[metric.label]: [metric.value, metric.unit].filter(v => v != null).join(" ")}) : "";
      const inputs = resultTable(data.inputs);
      return title + label + artifacts + (values || headline) +
        (inputs ? '<details><summary>Model inputs</summary>' + inputs + '</details>' : "");
    }
    if (b.url && /^https?:\/\//i.test(b.url)) return title+`<a href="${esc(b.url)}" target="_blank" rel="noopener">Open source ${esc(b.type)} ↗</a>`;
    if (b.type === 'inspection') return title+`<p>${esc(b.row_count != null ? `${b.row_count} rows` : b.message || '')}</p><pre style="overflow:auto">${esc(JSON.stringify(b.columns || b.preview || b, null, 2))}</pre>`;
    return title+label+`<details><summary>Calculation inputs and outputs</summary><pre style="overflow:auto">${esc(JSON.stringify(b.data || b, null, 2))}</pre></details>`;
  }
  function text(b) {
    const title = b.title || b.model_id || b.type;
    if (b.type === 'chart') {
      const xs = b.categories || b.x.values;
      return [title, ...b.series.map(s => `${s.label}${s.unit ? ' (' + s.unit + ')' : ''}: ` +
        xs.slice(0, 20).map((x, i) => `${x}: ${s.values[i] ?? 'unavailable'}`).join('; ')),
        xs.length > 20 ? `First 20 of ${xs.length} points; full values are available in the output JSON.` : ''].filter(Boolean).join('\n');
    }
    if (b.type === 'calculation') {
      const data = b.data || {}, outputs = data.outputs || data.metrics || data;
      const rows = Object.entries(outputs).filter(([, v]) => v != null &&
        (typeof v !== 'object' || Array.isArray(v) && v.length <= 8 && v.every(x => typeof x !== 'object')));
      return [title, ...rows.map(([k, v]) => `${k.replaceAll('_', ' ')}: ${Array.isArray(v) ? v.join(', ') : v}`)].join('\n');
    }
    return [title, b.message, b.url].filter(Boolean).join('\n');
  }
  return { render, text };
})();
