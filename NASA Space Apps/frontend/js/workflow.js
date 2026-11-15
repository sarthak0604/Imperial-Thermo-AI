// Render actual backend outputs; library examples remain in the widget library.
window.WORKFLOW = (() => {
  const { esc } = U;
  const resultNames = {
    adiabatic_flame_temp_k: ["Adiabatic flame temperature", "K"],
    adiabatic_flame_temp_c: ["Adiabatic flame temperature", "°C"],
    estimated_dissociation_drop_k: ["Temperature drop due to dissociation", "K"],
    fuel_species: ["Fuel", ""], o2_mole_frac: ["Oxygen mole fraction", ""],
    pressure_kpa: ["Pressure", "kPa"], t_init_k: ["Initial temperature", "K"],
    diluent_gas: ["Diluent", ""], equivalence_ratio: ["Equivalence ratio", ""],
    lewis_number: ["Lewis number", ""], temp_k: ["Temperature", "K"],
    x_o2: ["Oxygen mole fraction", ""], u_flow_ms: ["Airflow speed", "m/s"],
    activation_energy_j: ["Activation energy", "J/mol"], flame_temp_k: ["Leading-edge flame temperature", "K"],
    damkohler_number: ["Damköhler number", ""], flow_residence_time_ms: ["Flow residence time", "ms"],
    chemical_reaction_time_ms: ["Chemical reaction time", "ms"], is_blown_off: ["Blowoff predicted", ""],
    gas_thermal_diffusivity_m2s: ["Gas thermal diffusivity", "m²/s"], da_critical: ["Critical Damköhler number", ""],
    t_amb_k: ["Ambient temperature", "K"], pre_exp_factor: ["Arrhenius frequency factor", "s⁻¹"],
    reaction_order_n: ["Pressure reaction order", ""], o2_order_m: ["Oxygen reaction order", ""],
    t_surface_k: ["Droplet surface temperature", "K"],
    surface_vapor_pressure_kpa: ["Total vapour pressure at the surface", "kPa"],
    thermal_diffusivity_m2_s: ["Thermal diffusivity", "m²/s"], mass_diffusivity_m2_s: ["Mass diffusivity", "m²/s"]
  };
  const number = new Intl.NumberFormat(undefined, { maximumSignificantDigits: 7 });
  function displayValue(value) {
    if (typeof value === "number") return number.format(value);
    if (typeof value === "boolean") return value ? "Yes" : "No";
    return String(value);
  }
  function displayName(key) {
    return resultNames[key]?.[0] || key.replaceAll("_", " ").replace(/^./, char => char.toUpperCase());
  }
  function resultTable(record) {
    const rows = Object.entries(record || {}).flatMap(([key, value]) => {
      if (value == null || (typeof value === "object" &&
          !(Array.isArray(value) && value.length > 0 && value.length <= 8 &&
            value.every(item => item != null && typeof item !== "object")))) return [];
      const [label, unit] = [displayName(key), resultNames[key]?.[1]];
      const shown = Array.isArray(value) ? value.map(displayValue).join(", ") : displayValue(value);
      return '<tr><th scope="row">' + esc(label) + '</th><td>' +
        esc([shown, unit].filter(Boolean).join(" ")) + '</td></tr>';
    });
    return rows.length ? '<table><tbody>' + rows.join("") + '</tbody></table>' : "";
  }
  function downloadJson(prefix, label, suffix, value) {
    return value == null ? "" :
      `<a class="chip" download="${esc(prefix + "-" + suffix + ".json")}" href="data:application/json;charset=utf-8,${encodeURIComponent(JSON.stringify(value, null, 2))}">${esc(label)}</a>`;
  }
  function metrics(items) {
    const valid = items.filter(item => item?.label && item.value != null);
    if (!valid.length) return "";
    return '<dl class="result-metrics">' + valid.map(({label, value, unit, note}) =>
      `<div><dt>${esc(label)}</dt><dd>${esc(displayValue(value))}${unit && unit !== "dimensionless"
        ? ` <small>${esc(unit)}</small>` : ""}</dd>${note ? `<p>${esc(note)}</p>` : ""}</div>`
    ).join("") + "</dl>";
  }
  function render(b) {
    const names = { "THM-07": "THM-07 · Flame blowoff", "THM-12": "THM-12 · Droplet evaporation and condensation" };
    const scenarioTitle = { "methane-iss": "THM-02 · Nominal ISS oxidizer",
      "methane-iss-diluted": "THM-02 · Illustrative nitrogen dilution" };
    const title = `<h3>${esc(b.title || scenarioTitle[b.task_id] || names[b.model_id] || b.model_id || b.type)}</h3>`;
    const evidence = [b.evidence_type?.replaceAll("_", " "), b.illustrative ? "Illustrative inputs" : ""].filter(Boolean);
    const label = evidence.length ? `<p class="result-meta">${esc(evidence.join(" · "))}</p>` : "";
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
      const thresholdChart = b.title === "THM-07 blowoff threshold" && b.series.length === 2;
      const sharedAxis = b.chart_type === "line" && b.series.length > 1 &&
        b.series.every(series => series.unit === b.series[0].unit);
      const groups = sharedAxis ? [b.series] : b.series.map(series => [series]);
      const range = values => {
        let lo = Infinity, hi = -Infinity;
        for (const value of values) { lo = Math.min(lo, value); hi = Math.max(hi, value); }
        return lo === hi ? [lo - 1, hi + 1] : [lo, hi];
      };
      const plots = groups.map(series => {
        const lines = series.map(s => x.map((v, i) => [v, s.values[i]]).filter(p => p.every(Number.isFinite)));
        const all = lines.flat();
        if (!all.length) return "<p>No numeric points.</p>";
        const xr = range(all.map(p => p[0])), yr = range(all.map(p => p[1]));
        const log = thresholdChart && yr[0] > 0 && yr[1] / yr[0] > 30;
        const start = Math.floor(Math.log10(yr[0])), end = Math.ceil(Math.log10(yr[1]));
        const ticks = log ? Array.from({length: end - start + 1}, (_, i) => 10 ** (start + i)) : CH.range(...yr, 4);
        const ylabel = series[0].label.replaceAll("_", " ");
        const legend = sharedAxis ? '<ul class="result-legend">' + series.map((s, i) =>
          `<li class="${i ? "dashed" : ""}">${esc(s.label)}</li>`).join("") + "</ul>" : "";
        return legend + `<div class="result-plot">${CH.host(size => {
          const f = CH.frame(size, { x: xr, y: log ? [ticks[0], ticks.at(-1)] : yr, ylog: log,
            xticks: CH.range(...xr, 4), yticks: ticks, xlabel: b.x.label.replaceAll("_", " "),
            xunit: b.x.unit, ylabel: ylabel + (log ? " (log scale)" : ""), yunit: series[0].unit });
          const annotations = (b.markers || []).filter(marker =>
            Number.isFinite(marker.value) && marker.value >= xr[0] && marker.value <= xr[1]);
          return f.axes + annotations.map(marker => CH.vref(f.sx(marker.value), f.Y1, f.Y0)).join("") +
            lines.map((points, i) => {
            if (!points.length) return "";
            if (b.chart_type === "scatter") return points.map(([a, c]) =>
              CH.dot(f.sx(a), f.sy(c), { r: 3, tip: `${b.x.label} ${number.format(a)}, ${series[i].label} ${number.format(c)}` })).join("");
            return CH.line(points, f.sx, f.sy, { dashed: i > 0 });
          }).join("");
        }, { label: series.map(s => s.label).join(", ") })}</div>`;
      }).join("");
      const rows = x.slice(0,200).map((v,i) => `<tr><td>${esc(displayValue(v))}</td>${b.series.map(s => `<td>${esc(displayValue(s.values[i] ?? ''))}</td>`).join('')}</tr>`).join('');
      const table = `<details><summary>Chart data (${x.length} points${x.length > 200 ? '; first 200 shown, full values in output JSON' : ''})</summary><div style="overflow:auto;max-height:360px"><table><thead><tr><th>${esc(b.x.label)} ${esc(b.x.unit || '')}</th>${b.series.map(s => `<th>${esc(s.label)} ${esc(s.unit || '')}</th>`).join('')}</tr></thead><tbody>${rows}</tbody></table></div></details>`;
      const markers = (b.markers || []).map(marker =>
        `${marker.label} · ${number.format(marker.value)} ${b.x.unit || ""}`);
      const annotations = markers.length ? '<p class="muted">' + esc(markers.join("  /  ")) + '</p>' : "";
      return title + label + plots + annotations + table;
    }
    if (b.type === "calculation") {
      const data = b.data || {};
      const outputs = data.outputs || data.metrics || (b.model_id === "THM-02" ? { ...data.transport_properties, ...data.dimensionless_numbers } : data);
      const details = {...outputs};
      let highlights = b.headline_metrics || [data.frontend_summary?.headline_metric, data.frontend_summary?.secondary_metric];
      if (b.model_id === "THM-07" && Number.isFinite(outputs.critical_blowoff_velocity_ms)) {
        const margin = outputs.blowoff_margin_cms / 100;
        highlights = [
          { label: "Estimated blowoff limit", value: outputs.critical_blowoff_velocity_ms, unit: "m/s" },
          { label: "Tested airflow", value: data.inputs.u_flow_ms, unit: "m/s" },
          { label: "Distance to limit", value: Math.abs(margin), unit: "m/s",
            note: margin ? (outputs.is_blown_off ? "Above the limit" : "Below the limit") : "At the displayed limit" }
        ];
        for (const key of ["critical_blowoff_velocity_ms", "critical_blowoff_velocity_cms",
          "blowoff_margin_cms", "blowoff_velocity_ratio"]) delete details[key];
        highlights.push({ label: "Damköhler number", value: outputs.damkohler_number });
      } else if (b.model_id === "THM-12" && data.components?.length) {
        highlights = data.components.map(component => ({
          label: displayName(component.id),
          value: displayName(component.transfer_direction),
          note: `${number.format(Number(component.surface_partial_pressure_kpa.toPrecision(3)))} kPa at surface · ${number.format(component.ambient_partial_pressure_kpa)} kPa in gas`
        }));
        delete details.model_id;
        delete details.evidence_id;
        delete details.status;
      } else if (b.model_id === "THM-02" && Number.isFinite(outputs.lewis_number)) {
        highlights = [{ label: "Lewis number", value: outputs.lewis_number }];
        delete details.lewis_number;
      }
      const values = resultTable(details);
      const scenario = b.model_id === "THM-12" ? b.input_json?.request?.scenario : null;
      const inputs = resultTable(data.inputs || (scenario ? {
        t_surface_k: scenario.t_surface_k, pressure_kpa: scenario.pressure_kpa,
        ...Object.fromEntries(data.components.map(component => [
          `${displayName(component.id)} in liquid`, `${number.format(100 * component.liquid_mole_fraction)} mol%`
        ]))
      } : null));
      const provenance = (b.input_provenance || []).flatMap(origin => {
        const name = displayName((origin.target_pointer || "").split("/").at(-1));
        if (origin.kind === "scenario_assumption") {
          return [origin.assumption.replace(/^AI assumption for [^:]+: /, `Assumed ${name.toLowerCase()} `)];
        }
        if (origin.kind === "reference_property") {
          const value = typeof origin.value === "object" ? "property fit" : displayValue(origin.value);
          const species = origin.record_id?.split("_")[0];
          const property = name.toLowerCase();
          const label = b.model_id === "THM-12" && species ? `${displayName(species)} ${property}` : name;
          return [`${label} from the reference library · ${value}${origin.unit ? " " + origin.unit : ""}`];
        }
        if (origin.kind === "evidence_package" && origin.id === "methanol_water_snapshot") {
          return ["Assumes an ideal liquid mixture with activity coefficients of 1. The model estimates initial transfer direction at the specified surface temperature."];
        }
        if (origin.kind === "evidence_package" && origin.notes) {
          return [origin.notes];
        }
        if (origin.kind === "evidence_package" && origin.illustrative) {
          return [b.model_id === "THM-07" ? "Bundled illustrative kinetics unless overridden in the prompt." : "Used a bundled illustrative example."];
        }
        return [];
      });
      const defaults = resultTable(Object.fromEntries(Object.entries(b.model_defaults || {})
        .filter(([name]) => !Object.hasOwn(data.inputs || {}, name))));
      const download = (label, suffix, value) => downloadJson(b.task_id || b.model_id, label, suffix, value);
      return title + label + metrics(highlights) +
        (provenance.length ? '<details open><summary>Reference inputs and assumptions</summary><ul>' +
          provenance.map(text => "<li>" + esc(text) + "</li>").join("") + "</ul></details>" : "") +
        (values ? '<details' + (highlights.some(item => item?.value != null) ? '' : ' open') +
          '><summary>Model outputs</summary>' + values + '</details>' : "") +
        (inputs || defaults ? '<details><summary>Model inputs</summary>' + inputs +
          (defaults ? '<h4>Solver defaults</h4>' + defaults : '') + '</details>' : "") +
        '<div class="fups result-downloads">' + download("Input JSON", "input", b.input_json) +
        download("Output JSON", "output", b.data) + download("Provenance JSON", "provenance", b.input_provenance) + "</div>";
    }
    if (b.url && /^https?:\/\//i.test(b.url)) return title+`<a href="${esc(b.url)}" target="_blank" rel="noopener">Open source ${esc(b.type)} ↗</a>`;
    if (b.type === 'inspection') return title+`<p>${esc(b.row_count != null ? `${b.row_count} rows` : b.message || '')}</p><pre style="overflow:auto">${esc(JSON.stringify(b.columns || b.preview || b, null, 2))}</pre>`;
    return title+label+`<details><summary>Calculation inputs and outputs</summary><pre style="overflow:auto">${esc(JSON.stringify(b.data || b, null, 2))}</pre></details>`;
  }
  return { render, downloadJson };
})();
