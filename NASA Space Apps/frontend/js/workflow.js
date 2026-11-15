// Render actual backend outputs; library examples remain in the widget library.
window.WORKFLOW = (() => {
  const { esc } = U;
  function render(b) {
    const title = `<h3>${esc(b.title || b.model_id || b.type)}</h3>`;
    const label = `<p class="muted">${esc([b.evidence_type?.replaceAll('_', ' '), b.illustrative ? 'Illustrative inputs' : ''].filter(Boolean).join(' · '))}</p>`;
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
    if (b.url && /^https?:\/\//i.test(b.url)) return title+`<a href="${esc(b.url)}" target="_blank" rel="noopener">Open source ${esc(b.type)} ↗</a>`;
    if (b.type === 'inspection') return title+`<p>${esc(b.row_count != null ? `${b.row_count} rows` : b.message || '')}</p><pre style="overflow:auto">${esc(JSON.stringify(b.columns || b.preview || b, null, 2))}</pre>`;
    return title+label+`<details><summary>Calculation inputs and outputs</summary><pre style="overflow:auto">${esc(JSON.stringify(b.data || b, null, 2))}</pre></details>`;
  }
  return { render };
})();
