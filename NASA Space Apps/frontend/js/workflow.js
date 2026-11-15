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
      const rows = (b.categories || []).flatMap((name, i) => {
        const value = series?.values[i];
        if (!Number.isFinite(value) || value < 0 || value > 100) return [];
        const displayed = new Intl.NumberFormat(undefined, { maximumSignificantDigits: 4 }).format(value);
        return [`<tr><th scope="row">${esc(name)}</th><td style="width:65%"><meter min="0" max="100" value="${value}" style="width:100%" aria-label="${esc(name + ' mole percent')}"></meter></td><td>${esc(displayed)}%</td></tr>`];
      });
      return title + label + `<table style="width:100%"><thead><tr><th scope="col">Gas species</th><th scope="col" colspan="2">Mole fraction (%)</th></tr></thead><tbody>${rows.join('')}</tbody></table>`;
    }
    if (b.type === 'chart') {
      const x = b.x.values;
      const plots = b.series.map(s => {
        const points = x.map((v, i) => [v, s.values[i]]).filter(p => p.every(Number.isFinite));
        if (!points.length) return '<p>No numeric points.</p>';
        const range = a => { let lo=Infinity, hi=-Infinity; for (const v of a) {lo=Math.min(lo,v);hi=Math.max(hi,v);} return lo===hi?[lo-1,hi+1]:[lo,hi]; };
        const xr=range(points.map(p=>p[0])), yr=range(points.map(p=>p[1]));
        return `<div style="height:320px">${CH.host(size => {
          const f=CH.frame(size,{x:xr,y:yr,xticks:CH.range(...xr,4),yticks:CH.range(...yr,4),xlabel:b.x.label,xunit:b.x.unit,ylabel:s.label,yunit:s.unit});
          return f.axes+(b.chart_type==='scatter'?points.map(([a,c])=>CH.dot(f.sx(a),f.sy(c),{r:2})).join(''):CH.line(points,f.sx,f.sy));
        },{label:s.label})}</div>`;
      }).join('');
      return title+label+plots;
    }
    if (b.type === "calculation") {
      const data = b.data || {};
      const outputs = data.outputs || data.metrics || data;
      const values = resultTable(outputs);
      const metric = data.frontend_summary?.headline_metric;
      const headline = !values && metric?.label && metric.value != null
        ? resultTable({[metric.label]: [metric.value, metric.unit].filter(v => v != null).join(" ")}) : "";
      const inputs = resultTable(data.inputs);
      return title + label + (values || headline) +
        (inputs ? '<details><summary>Model inputs</summary>' + inputs + '</details>' : "");
    }
    if (b.url && /^https?:\/\//i.test(b.url)) return title+`<a href="${esc(b.url)}" target="_blank" rel="noopener">Open source ${esc(b.type)} ↗</a>`;
    if (b.type === 'inspection') return title+`<p>${esc(b.row_count != null ? `${b.row_count} rows` : b.message || '')}</p><pre style="overflow:auto">${esc(JSON.stringify(b.columns || b.preview || b, null, 2))}</pre>`;
    return title+label+`<details><summary>Calculation inputs and outputs</summary><pre style="overflow:auto">${esc(JSON.stringify(b.data || b, null, 2))}</pre></details>`;
  }
  return { render };
})();
