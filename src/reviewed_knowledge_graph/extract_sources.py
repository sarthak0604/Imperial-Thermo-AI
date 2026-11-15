"""Retain locatable source text and table structure for direct assistant review."""
import csv, hashlib, io, json, math, re, sys, zipfile, subprocess
from pathlib import Path
from xml.etree import ElementTree as ET
sys.path.insert(0,'/private/tmp/nasa-psi-review-deps')
from pypdf import PdfReader
from openpyxl import load_workbook

ROOT=Path(__file__).resolve().parent

def clean(value):
    if value is None:return None
    if isinstance(value,(float,int,str,bool)):return value
    return str(value)

def table(rows,name,all_rows=False):
    sections=[]; sample=[]; nonnumeric=[]; counts=[];n=0
    for n,row in enumerate(rows,1):
        row=[clean(v) for v in row]
        if all_rows or n<=12:sample.append(row)
        while len(counts)<len(row):counts.append({'numeric_count':0,'min':None,'max':None,'blank_count':0})
        has_text=False
        for i,v in enumerate(row):
            c=counts[i]
            if v is None or str(v).strip()=='':c['blank_count']+=1;continue
            try:
                x=float(v)
                if not math.isfinite(x):continue
                c['numeric_count']+=1;c['min']=x if c['min'] is None else min(c['min'],x);c['max']=x if c['max'] is None else max(c['max'],x)
            except (ValueError,TypeError):has_text=True
        if all_rows or has_text or n<=12:
            sections.append({'locator':f'{name}, row {n}','text':' | '.join(f'{i+1}: {v}' for i,v in enumerate(row) if v is not None and str(v).strip())})
    return sections,{'name':name,'row_count':n,'column_count':len(counts),'column_statistics':counts,'rows':sample,'all_rows_retained':all_rows}

def parse(path,all_rows=False):
    ext=path.suffix.lower();sections=[];details={};warnings=[]
    if ext=='.pdf':
        import pymupdf
        book=pymupdf.open(path)
        pages=[page.get_text() for page in book]
        book.close()
        details['page_count']=len(pages);details['empty_pages']=[]
        for i,t in enumerate(pages,1):
            sections.append({'locator':f'page {i}','text':t})
            if len(t.strip())<30:details['empty_pages'].append(i)
        warnings.append('Text extracted; visual content is reviewed only where explicitly recorded.')
    elif ext=='.csv':
        raw=path.read_bytes()
        try:text=raw.decode('utf-8-sig')
        except UnicodeDecodeError:text=raw.decode('cp1252')
        sections,details=table(csv.reader(io.StringIO(text)),'table',all_rows=True)
    elif ext=='.xlsx':
        book=load_workbook(path,read_only=True,data_only=True);details['sheets']=[]
        for sheet in book:
            s,d=table(sheet.iter_rows(values_only=True),'sheet '+sheet.title,all_rows=all_rows)
            sections.extend(s);details['sheets'].append(d)
        book.close();warnings.append('Values read from saved workbook; formulas not recalculated.')
    elif ext=='.xls':
        import xlrd
        book=xlrd.open_workbook(path,on_demand=True);details['sheets']=[]
        for sheet in book.sheets():
            s,d=table((sheet.row_values(n) for n in range(sheet.nrows)),'sheet '+sheet.name,all_rows=all_rows)
            sections.extend(s);details['sheets'].append(d)
        book.release_resources();warnings.append('Saved cell values inspected; formulas not recalculated.')
    elif ext in {'.docx','.pptx'}:
        with zipfile.ZipFile(path) as z:
            names=[n for n in z.namelist() if n=='word/document.xml' or re.fullmatch(r'ppt/slides/slide\d+.xml',n)]
            names.sort(key=lambda n:int(re.search(r'slide(\d+)',n).group(1)) if 'slides/' in n else 0)
            for name in names:
                root=ET.fromstring(z.read(name))
                text='\n'.join(''.join(el.itertext()) for el in root.iter() if el.tag.endswith('}t'))
                sections.append({'locator':name,'text':text})
        warnings.append('Document text extracted; embedded images not interpreted automatically.')
    elif ext=='.zip':
        with zipfile.ZipFile(path) as z:
            details['members']=[{'name':i.filename,'size_bytes':i.file_size} for i in z.infolist() if not i.is_dir()]
            for info in z.infolist():
                if info.filename.lower().endswith(('.txt','.tsv','.csv')) and info.file_size<5_000_000:
                    sections.append({'locator':'archive member '+info.filename,'text':z.read(info).decode('utf-8-sig',errors='replace')})
    elif ext=='.txt':sections=[{'locator':'full text','text':path.read_text(errors='replace')}]
    else:return [],{},['Legacy binary Office format; contents not extracted.'],'unsupported'
    return sections,details,warnings,'extracted' if any(s['text'].strip() for s in sections) else 'no_text'

if __name__=='__main__':
    targets=list((ROOT/'sources').glob('*/download_records/*.json'))
    if len(sys.argv)>1:targets=[p for p in targets if json.loads(p.read_text())['category']==sys.argv[1]]
    priority={'Experimental table':0,'Science Documents':1,'Reports':2,'Presentations':3,'Analyzed Data':4,'metadata':5}
    targets.sort(key=lambda p:priority.get(json.loads(p.read_text())['category'],9))
    for n,recordpath in enumerate(targets,1):
        record=json.loads(recordpath.read_text());out=recordpath.parent.parent/'extracted'/(recordpath.stem+'.json');out.parent.mkdir(exist_ok=True)
        try:cached=json.loads(out.read_text()) if out.exists() else {}
        except (ValueError,UnicodeError):cached={}
        if (cached and (not record['filename'].lower().endswith('.pdf') or cached.get('parser_version')=='review-2')) or record['status']!='downloaded':continue
        try:
            sections,details,warnings,status=parse(Path(record['local_path']),all_rows=record['category']=='Experimental table')
            result={**record,'parser_version':'review-2','sections':sections,'details':details,'warnings':warnings,'extraction_status':status,'review_status':'not_yet_reviewed'}
        except Exception as error:result={**record,'sections':[],'details':{},'extraction_status':'failed','error':f'{type(error).__name__}: {error}'}
        temporary=out.with_suffix('.tmp')
        temporary.write_text(json.dumps(result,ensure_ascii=False,indent=2))
        temporary.replace(out)
        if n%20==0 or result['extraction_status'] in ['failed','unsupported']:print(n,record['study'],record['filename'],result['extraction_status'],flush=True)
