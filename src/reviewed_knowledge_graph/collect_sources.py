"""Download public source documents for direct review; never calls an LLM."""
import concurrent.futures, hashlib, json, sys, time, zipfile, subprocess, os
from pathlib import Path
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / 'psi_kg'))
from psi_graph.nasa_access import request, BASE_URL

TMP = Path('/private/tmp/nasa-psi-review-01a1dfae')
FORMATS = {'.pdf','.csv','.xlsx','.docx','.pptx','.txt','.xls','.doc','.ppt'}

def selected(entry):
    category=entry['key'].split('/')[2]
    return category not in {'Raw Data','Calibration','Representative Image(s)'} and (Path(entry['key']).suffix.lower() in FORMATS or category=='metadata')

def fetch(job):
    accession, version, entry=job
    key=hashlib.sha256(entry['id'].encode()).hexdigest()[:20]
    directory=TMP/accession/key
    path=directory/Path(entry['key']).name
    record={'id':f'res:{accession}:{key}','study':accession,'filename':path.name,'key':entry['key'],'category':entry['key'].split('/')[2], 'size_bytes':int(entry.get('bytes_size') or 0),'source_url':f'{BASE_URL}/studies/{accession}/download?'+urlencode({'file':entry['id'],'version':entry['version'],'studyVersion':version,'redirect':'true'}),'local_path':str(path)}
    for attempt in range(3):
        try:
            if not path.exists():
                directory.mkdir(parents=True,exist_ok=True)
                # Reuse an unchanged, previously downloaded source where available.
                cached=list((ROOT.parent/'psi_kg'/'output'/accession).glob('**/'+path.name)) if accession=='PSI-117' else []
                cached=[p for p in cached if p.is_file() and p.stat().st_size==record['size_bytes']]
                if cached:
                    import shutil
                    shutil.copyfile(cached[0],path)
                    record['retrieval_method']='existing_local_copy_same_filename_and_byte_count; newly hashed'
                else:
                    params=urlencode({'file':entry['id'],'version':entry['version'],'studyVersion':version,'redirect':'false'})
                    with request(f'{BASE_URL}/studies/{accession}/download?{params}') as response:link=response.read().decode().strip()
                    if link.startswith('"'):link=json.loads(link)
                    if not link.startswith('https://'):raise ValueError('Expected HTTPS download')
                    temporary=directory/('download-'+str(os.getpid())+'.part')
                    result=subprocess.run(['curl','--http1.1','--fail','--silent','--show-error','--location','--max-time','180','--output',str(temporary),link],capture_output=True,text=True)
                    if result.returncode:raise RuntimeError('curl failed: '+result.stderr[:180])
                    if temporary.stat().st_size!=record['size_bytes']:raise ValueError('Downloaded byte count does not match NASA inventory')
                    os.replace(temporary,path)
                    record['retrieval_method']='NASA downloader endpoint and curl transport'
            h=hashlib.sha256()
            with path.open('rb') as stream:
                for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
            record.update(sha256=h.hexdigest(),status='downloaded')
            break
        except Exception as error:
            record.update(status='failed',error=f'{type(error).__name__}: {error}')
            if attempt<2:time.sleep(1)
    (ROOT/'sources'/accession/'download_records').mkdir(exist_ok=True)
    (ROOT/'sources'/accession/'download_records'/f'{key}.json').write_text(json.dumps(record,indent=2))
    return record

if __name__=='__main__':
    jobs=[]
    for source in (ROOT/'sources').iterdir():
        metadata=json.loads((source/'metadata.json').read_text())
        for entry in json.loads((source/'files.json').read_text()):
            if selected(entry):jobs.append((source.name,metadata['version'],entry))
    priority={'Experimental table':0,'Science Documents':1,'Reports':2,'metadata':3,'Presentations':4,'Engineering Documents':5,'Analyzed Data':6,'Reference Data':7}
    jobs.sort(key=lambda j:(priority.get(j[2]['key'].split('/')[2],9),j[2].get('bytes_size',0)))
    print(f'Selected {len(jobs)} source documents; {sum(int(j[2].get("bytes_size") or 0) for j in jobs)/1e6:.1f} MB',flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        for n,record in enumerate(pool.map(fetch,jobs),1):
            if n%10==0 or record['status']=='failed':print(n,record['study'],record['filename'],record['status'],flush=True)
