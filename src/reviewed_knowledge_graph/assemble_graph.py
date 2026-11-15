"""Assemble the requested v1.0.0 graph from reviewed sources, not an LLM pipeline."""
import collections, hashlib, json, re, sys, unicodedata
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from curation import REVIEW, CONCEPTS

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'output';OUT.mkdir(exist_ok=True)
sys.path.insert(0,str(ROOT.parent/'psi_kg'))
from psi_graph.graph import SCHEMA,DIRECTIONS
from jsonschema import Draft202012Validator

def digest(text):return hashlib.sha256(text.encode()).hexdigest()[:20]
def read(path):return json.loads(path.read_text())
def write(path,data):path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
def norm(text):return ' '.join(unicodedata.normalize('NFKC',str(text)).split())
def page_url(a):return f'https://psi.nasa.gov/physci/repo/data/investigations/{a}'
def download_url(a,version,f):return f'https://psi.nasa.gov/geode-py/ws/studies/{a}/download?'+urlencode({'file':f['id'],'version':f['version'],'studyVersion':version,'redirect':'true'})

nodes={};edges={};provenance={};study_node_ids={};quality=[];coverage=[];row_counts={};review_log=[]
def node(id,kind,properties,refs=()):
    if id not in nodes:nodes[id]={'id':id,'type':kind,'properties':properties}
    provenance.setdefault(id,[])
    for ref in refs:
        if ref not in provenance[id]:provenance[id].append(ref)
    return id

def edge(source,target,kind,refs,origin='source_review',status='verified'):
    assert refs,(source,target,kind)
    id='edge:'+digest(source+'\0'+kind+'\0'+target)
    if id not in edges:edges[id]={'id':id,'source':source,'target':target,'type':kind,'properties':{'origin':origin,'verification_status':status,'evidence':[]}}
    for ref in refs:
        if ref not in edges[id]['properties']['evidence']:edges[id]['properties']['evidence'].append(ref)
    if status=='needs_review':edges[id]['properties']['verification_status']='needs_review'

def concept(name,refs):
    synonyms,description=CONCEPTS.get(name,([],None))
    return node('concept:'+digest(name.lower()),'Concept',{'name':name,'synonyms':synonyms,'description':description},refs)

def variable(name,unit,role,refs):
    return node('var:'+digest(name.lower()+'|'+str(unit)+'|'+str(role)),'Variable',{'name':name,'symbol':None,'unit':unit,'role':role},refs)

def doc_ref(d,locator,fragment=None):
    text=next(s['text'] for s in d['sections'] if s['locator']==locator)
    if fragment:
        assert norm(fragment) in norm(text),(d['filename'],locator,fragment)
        text=fragment
    return {'source_url':d['source_url'],'locator':locator,'text':norm(text)}

MATERIALS=[
 ('PMMA',r'\bpmma\b|polymethylmethacrylate'),('SIBAL cotton/fiberglass fabric',r'sibal|cotton.fiberglass'),
 ('Nomex',r'nomex'),('Silicone',r'silicone'),('Kapton',r'kapton'),('Teflon',r'teflon'),('Pyrell',r'pyrell'),('Lampwick',r'lampwick'),
 ('Methane',r'\bch4\b|methane'),('Ethylene',r'\bc2h4\b|ethylene'),('Ethane',r'\bc2h6\b|\bethane\b'),
 ('Propane',r'\bc3h8\b|\bpropane\b'),('Propylene',r'\bc3h6\b|propylene'),('n-Butane',r'n.butane|\bc4h10\b'),
 ('n-Pentane',r'n.pentane|\bc5h12\b'),('n-Heptane',r'heptane|\bc7h16\b'),('n-Dodecane',r'n.dodecane|\bc12h26\b'),
 ('Farnesane',r'farnesane'),('Methanol',r'methanol|meoh'),('Iso-octane',r'iso.?octane'),('n-Octane',r'n.octane'),
 ('n-Decane',r'n.decane|\bc10h22\b'),('Hydrogen',r'\bh2\b|hydrogen')]

def row_issues(a,headers,row,rownum):
    issues=[];s=' | '.join(str(x) for x in row)
    if re.search(r'\bCH[5-9]\b|\bN[3-9]\b',s):issues.append('Apparent chemical-formula sequence-fill error in source; unchanged.')
    for h,v in zip(headers,row):
        if 'oxygen conc' in h.lower() and re.search(r'\b(?:2100|3400)%',str(v)):issues.append('Oxygen percentage exceeds 100%; apparent source formatting error, not corrected.')
    if a=='PSI-69':issues.append('Source burning-rate unit is labelled mm; physical rate unit is unresolved.')
    if a=='PSI-99':
        if '?-g' in ' '.join(headers):issues.append('Source gravity label contains an unreadable ? character.')
        if '037 mm' in s:issues.append('Thickness is written 037 mm in source; decimal placement is unresolved.')
        if len(row)>1 and not str(row[1]).strip():issues.append('Material cell is blank; not inferred from the preceding row.')
    if a in ['PSI-98','PSI-100']:issues.append('Geometry/thickness values are preserved from this table; do not assume agreement with narrative or other Saffire tables.')
    if a=='PSI-22' and not any(str(v).strip() for v in row[:5]):issues.append('Continuation or annotation row without date/test identifier; context not silently filled down.')
    return issues

review_file=ROOT/'document_reviews.json'
document_reviews=read(review_file) if review_file.exists() else []

for number,review in REVIEW.items():
    a=f'PSI-{number}';source=ROOT/'sources'/a;m=read(source/'metadata.json');files=read(source/'files.json')
    summary,topics,variables,methods,granularity=review
    meta_refs=[{'source_url':page_url(a),'locator':'metadata.'+k,'text':norm(m[k])} for k in ['objective','approach'] if m.get(k)]
    inv=node('inv:'+a,'Investigation',{'title':m['title'],'summary':summary,'keywords':topics,'doi':m.get('doi') or None,'source_url':page_url(a)},meta_refs)
    campaign=node('exp:'+a+':campaign','Experiment',{'title':(m.get('investigationAcronym') or a)+' — investigation-level study','summary':summary,'keywords':topics,'conditions':{'record_kind':'investigation_campaign','project_type':m.get('projectType'),'hardware':m.get('experimentHardware') or None,'flight_program_as_reported':m.get('flightProgram') or None,'scope':'Study-level description; not a single physical test.','observations_vs_objectives':'Metadata objectives and hypotheses are not treated as measured findings.'},'methods':methods,'source_url':page_url(a)},meta_refs)
    edge(inv,campaign,'CONTAINS',meta_refs)
    for name in topics:edge(campaign,concept(name,meta_refs),'STUDIES',meta_refs)
    # These are investigation-level reported diagnostics/targets; row-level values
    # below and document findings have more specific provenance.
    for name,unit,role in variables:
        status='needs_review' if number in [10,21,23,117] else 'verified'
        edge(campaign,variable(name,unit,role,meta_refs),'MEASURES',meta_refs,'reported_measurement_scope',status)
    extracted={p.stem:read(p) for p in (source/'extracted').glob('*.json')}
    downloads={p.stem:read(p) for p in (source/'download_records').glob('*.json')}
    doc_by_filename={d['filename']:d for d in extracted.values()}
    table_records=0
    for f in files:
        key=digest(f['id']);rid=f'res:{a}:{key}';name=Path(f['key']).name;category=f['key'].split('/')[2];d=extracted.get(key);retrieval=downloads.get(key)
        ref={'source_url':page_url(a),'locator':f"NASA public file inventory, file id {f['id']}, version {f['version']}",'text':f['key']}
        reviewed=[r for r in document_reviews if r['study']==a and r['filename']==name]
        resource_summary=' '.join(r['summary'] for r in reviewed) or None
        status='listed_public_unread'
        if retrieval:
            status='download_failed' if retrieval['status']=='failed' else 'downloaded_unreviewed'
        if d:status='text_extracted_unreviewed' if d.get('extraction_status')=='extracted' else 'downloaded_'+d.get('extraction_status','unknown')
        if reviewed:status='reviewed_selected_sections'
        if category=='Experimental table' and d and d.get('extraction_status')=='extracted':status='structured_table_reviewed'
        node(rid,'Resource',{'title':name,'filename':name,'resource_type':category,'file_format':Path(name).suffix[1:].lower().strip() or None,'summary':resource_summary,'keywords':[],'variables':[],'source_url':download_url(a,m['version'],f),'storage_uri':None,'access_status':status,'size_bytes':int(f.get('bytes_size') or 0)},[ref])
        edge(campaign,rid,'HAS_RESOURCE',[ref],'NASA_public_file_listing')
        coverage.append({'resource_id':rid,'study':a,'filename':name,'category':category,'size_bytes':int(f.get('bytes_size') or 0),'source_url':download_url(a,m['version'],f),'status':status,'sha256':(retrieval or {}).get('sha256'),'extracted_source':str((source/'extracted'/(key+'.json')).relative_to(ROOT)) if d else None,'extraction_warnings':(d or {}).get('warnings',[]),'reviewed_locators':list(dict.fromkeys(loc for r in reviewed for loc in r['locators'])),'retrieval_method':(retrieval or {}).get('retrieval_method')})
        if category!='Experimental table' or not d or d.get('extraction_status')!='extracted':continue
        rows=d['details']['rows'];headers=[str(v).strip() if v else f'unnamed_column_{i+1}' for i,v in enumerate(rows[0])]
        seen={}
        for n,row in enumerate(rows[1:],2):
            if not any(str(v or '').strip() for v in row):continue
            if str(row[0]).startswith('Note '):continue
            # Keep malformed, duplicate and continuation records explicit.
            issues=row_issues(a,headers,row,n);signature=json.dumps(row)
            if signature in seen:issues.append(f'Exact duplicate of source row {seen[signature]}; not an independent replicate.')
            else:seen[signature]=n
            identity=None
            for label in ['Test','Test #','As Run Test #','FLEX Test #','Flex Number','SAME Test #','Sample Number','Test Day','Test Day*','Test Date']:
                if label in headers:
                    value=row[headers.index(label)] if headers.index(label)<len(row) else None
                    if value:identity=str(value);break
            kind=granularity
            if str(row[0]).startswith('F') and a in ['PSI-98','PSI-99','PSI-100']:kind='flow_visualization_record'
            if a=='PSI-22' and not any(str(v).strip() for v in row[:5]):kind='continuation_record'
            props={h:row[i] if i<len(row) and row[i]!='' else None for i,h in enumerate(headers)}
            props.update(record_kind=kind,source_table=name,source_row=n,source_quality_notes=issues)
            if issues:quality.append({'study':a,'filename':name,'row':n,'issues':issues})
            eid=f'exp:{a}:table:{key}:row:{n}'
            title=f'{a} {identity or kind.replace("_"," ")} (source row {n})'
            ref=doc_ref(d,f'table, row {n}');head=doc_ref(d,'table, row 1')
            node(eid,'Experiment',{'title':title,'summary':f'Source {kind.replace("_"," ")} transcribed from {name}, row {n}. Blank values remain unknown; ranges remain ranges.','keywords':[],'conditions':props,'methods':[],'source_url':d['source_url']},[head,ref])
            state='needs_review' if issues else 'verified'
            edge(inv,eid,'CONTAINS',[ref],'source_table_transcription',state)
            edge(eid,rid,'HAS_RESOURCE',[head,ref],'source_table_transcription',state)
            material_text=' '.join(str(row[i]) for i,h in enumerate(headers) if i<len(row) and any(t in h.lower() for t in ['fuel','material','sample type']))
            for material,pattern in MATERIALS:
                if re.search(pattern,material_text,re.I):edge(eid,concept(material,[ref]),'STUDIES',[ref],'source_table_material',state)
            # Only output/readout columns become MEASURES; controls stay in conditions.
            for i,h in enumerate(headers):
                if i>=len(row) or not str(row[i]).strip():continue
                if re.search(r'burn time|extinction diameter|burning rate|peak burner|weight loss rate|spread rate|flames ignited|calibrated.*o2|initial co|final co',h,re.I):
                    unit=None
                    match=re.search(r'\(([^()]+)\)\s*$',h)
                    if match:unit=match.group(1)
                    elif ';' in h:unit=h.rsplit(';',1)[1].strip()
                    elif 'ppm' in h.lower():unit='ppm'
                    elif '% by vol' in h.lower():unit='% by volume'
                    if 'flames ignited' in h.lower():unit='count'
                    vid=variable(h,unit,'dependent',[head])
                    edge(eid,vid,'MEASURES',[head,ref],'source_table_readout',state)
            table_records+=1
        nodes[rid]['properties']['summary']=f'Experiment index with {len(rows)-1} source rows after the header; nonempty data records are retained without expanding parameter ranges. Row type: {granularity}. Source errors and duplicate records are flagged.'
        nodes[rid]['properties']['variables']=headers
    row_counts[a]=table_records
    # Explicit document reviews enrich the campaign and can add scoped studies.
    for r in [r for r in document_reviews if r['study']==a]:
        d=doc_by_filename.get(r['filename'])
        if not d:raise ValueError('Reviewed source extraction missing: '+r['filename'])
        refs=[]
        for item in r.get('evidence',[]):refs.append(doc_ref(d,item['locator'],item['text']))
        if not refs:raise ValueError('Review requires exact evidence: '+r['filename'])
        provenance[campaign].extend(ref for ref in refs if ref not in provenance[campaign])
        provenance[inv].extend(ref for ref in refs if ref not in provenance[inv])
        if r.get('finding'):
            eid='exp:'+a+':review:'+digest(r['filename']+'|'+r.get('title',''))
            node(eid,'Experiment',{'title':r.get('title',r['filename']),'summary':r['summary'],'keywords':r.get('topics',[]),'conditions':{'record_kind':'documented_scientific_study','study_kind':r.get('study_kind','as_reported'),**r.get('conditions',{})},'methods':r.get('methods',[]),'source_url':d['source_url']},refs)
            edge(inv,eid,'CONTAINS',refs)
            edge(eid,d['id'],'HAS_RESOURCE',refs)
            for topic in r.get('topics',[]):edge(eid,concept(topic,refs),'STUDIES',refs)
            for v in r.get('variables',[]):edge(eid,variable(v['name'],v.get('unit'),'dependent',refs),'MEASURES',refs)
        review_log.append(r)
    # Bibliographic records stay citations, never claimed as papers read.
    for publication in m.get('publications',[]):
        title=publication.get('title')
        if not title:continue
        doi=publication.get('doi') or None;rid='citation:'+digest(doi or title)
        ref={'source_url':page_url(a),'locator':'metadata.publications','text':title}
        node(rid,'Resource',{'title':title,'filename':None,'resource_type':'publication_citation','file_format':None,'summary':None,'keywords':[],'variables':[],'source_url':'https://doi.org/'+doi if doi else page_url(a),'storage_uri':None,'access_status':'citation_only','size_bytes':None},[ref])
        edge(campaign,rid,'HAS_RESOURCE',[ref],'NASA_bibliographic_metadata')
    inv_edges=[e for e in edges.values() if e['source']==inv]
    expids={e['target'] for e in inv_edges}
    ids={inv}|expids|{e['target'] for e in edges.values() if e['source'] in expids}
    study_node_ids[a]=ids

generated=datetime.now(timezone.utc).isoformat()
graph={'schema_version':'1.0.0','graph_id':'NASA-PSI-19-reviewed-2026-11-15','source_url':'https://psi.nasa.gov/physci/repo/data/investigations','generated_at':generated,'nodes':list(nodes.values()),'edges':list(edges.values())}
validator=Draft202012Validator(SCHEMA)
errors=list(validator.iter_errors(graph));assert not errors,[(list(e.path),e.message) for e in errors[:8]]
for e in edges.values():
    assert e['source'] in nodes and e['target'] in nodes
    assert (nodes[e['source']]['type'],nodes[e['target']]['type'])==DIRECTIONS[e['type']]
assert sum(n['type']=='Investigation' for n in nodes.values())==19
assert len(coverage)==sum(len(read(p)) for p in (ROOT/'sources').glob('*/files.json'))
write(OUT/'knowledge_graph.json',graph)
write(OUT/'graph_schema.json',SCHEMA)
write(OUT/'node_provenance.json',provenance)
write(OUT/'source_quality_issues.json',quality)
write(OUT/'resource_coverage.json',coverage)
write(OUT/'document_review_log.json',review_log)
(OUT/'studies').mkdir(exist_ok=True)
for a,ids in study_node_ids.items():
    sub={**graph,'graph_id':'reviewed:'+a,'source_url':page_url(a),'nodes':[n for n in nodes.values() if n['id'] in ids],'edges':[e for e in edges.values() if e['source'] in ids and e['target'] in ids]}
    write(OUT/'studies'/(a+'.json'),sub)
counts=collections.Counter(n['type'] for n in nodes.values());ecounts=collections.Counter(e['type'] for e in edges.values())
report={'schema_validation':'passed','referential_integrity':'passed','edge_type_directions':'passed','all_requested_investigations':True,'all_public_inventory_files_represented':True,'node_counts':dict(counts),'edge_counts':dict(ecounts),'total_nodes':len(nodes),'total_edges':len(edges),'public_files':len(coverage),'listed_bytes':sum(c['size_bytes'] for c in coverage),'coverage_statuses':dict(collections.Counter(c['status'] for c in coverage)),'table_source_records_by_study':row_counts,'document_reviews':len(review_log),'source_quality_records':len(quality),'limitations':['Resource listing is not content review. Raw videos/images and unreviewed sources have explicit access_status values.','PDF text extraction is not full visual review. Only recorded locators were substantively reviewed.','Experiment nodes include campaign, test-day, condition and parameter-set records. They are not all independent physical runs.','Source errors and ambiguous units are retained and flagged; metadata hypotheses are not promoted to results.','No claim is made that all 13.47 TB of raw contents have been analyzed.']}
write(OUT/'validation_report.json',report)
print(json.dumps(report,indent=2))
