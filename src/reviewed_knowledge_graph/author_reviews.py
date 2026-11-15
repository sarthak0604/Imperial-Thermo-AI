"""Record the assistant's document readings with exact source anchors."""
import json, unicodedata
from pathlib import Path
ROOT=Path(__file__).resolve().parent
reviews=[]

def add(study,filename,title,summary,evidence,locators=None,topics=(),conditions=None,kind='flight_experiment',finding=True,variables=()):
    a=f'PSI-{study}'
    paths=list((ROOT/'sources'/a/'extracted').glob('*.json'))
    docs=[json.loads(p.read_text()) for p in paths]
    matches=[d for d in docs if filename in d['filename']]
    assert len(matches)==1,(a,filename,len(matches))
    d=matches[0]
    for loc,text in evidence:
        source=next(s['text'] for s in d['sections'] if s['locator']==loc)
        assert ' '.join(unicodedata.normalize('NFKC',text).split()) in ' '.join(unicodedata.normalize('NFKC',source).split()),(filename,loc,text)
    reviews.append({'study':a,'filename':d['filename'],'title':title,'summary':summary,'finding':finding,'study_kind':kind,'conditions':conditions or {},'topics':list(topics),'variables':[{'name':v[0],'unit':v[1]} for v in variables],'locators':locators or [loc for loc,_ in evidence],'evidence':[{'locator':loc,'text':text} for loc,text in evidence],'review_method':'Assistant read the specified source sections; not an external extraction-model response.'})

add(10,'FinalRpt_ACMEFlameDesign','Flame Design: radiative extinction and sustained spherical flames',
 'The final report describes atmospheric-pressure ethylene experiments and transient simulations. It reports an extinction temperature near 1130 K and critical mass fluxes of 0.2 g/m²/s for normal flames and 0.68 g/m²/s for inverse flames. The reported values apply to that tested system. Flames with steady-state behavior were observed for up to 870 s; the much longer 100,000 s result is numerical. The flight program used ethylene except for one propane calibration day; proposed methane and CO2-diluent tests were not performed.',
 [('page 25','critical extinction temperature of 1130 K'),('page 27','Tests with CH4 as fuel and CO2 as diluent,')],
 ['page 3','page 25','page 26','page 27'],['Spherical diffusion flames','Flame extinction','Thermal radiation'],{'fuel':'ethylene; separate propane calibration day','pressure':'approximately atmospheric','evidence_scope':'Flight observations and model results distinguished'},variables=[('Flame temperature','K'),('Reactant mass flux','g/m²/s')])

add(159,'FinalRpt_ACME.CFI-G','CFI-G: observed gaseous cool diffusion flames',
 'Normal and inverse ethane, propane and n-butane flames were investigated. The report says gaseous cool diffusion flames were obtained only for normal n-butane flames at 2 bar and ambient oxygen mole fraction 0.39 in this campaign. Hot precursor flames were reported as 2.6 times larger. A separate ground pool-flame study in the report is not classified as an ISS experiment. Ethane replaced the originally proposed n-pentane.',
 [('page 23','only obtained for normal n-butane flames at 2 bar')],['page 23','page 24'],['Cool flames','Spherical diffusion flames'],{'fuel_for_observed_cool_flames':'n-butane','configuration':'normal','pressure_bar':2,'ambient_oxygen_mole_fraction':0.39})

add(39,'CFI Science Final Report','CFI: pressure and helium effects on droplet cool flames',
 'The report describes n-dodecane, n-dodecane/iso-dodecane mixtures and farnesane experiments, with over 200 tests and initial droplets around 4 mm. It reports repeated hot/cool reignition cycles above approximately 2 atm and earlier cool-flame extinction, at a larger remaining droplet diameter, with increased helium dilution. Figure 4 compares free-floating and fiber-supported droplets. The report calls its analysis preliminary; some fuel labels and a gas-composition caption are internally inconsistent and are not used as corrected numerical conditions.',
 [('page 9','reignitions were commonly observed'),('page 9','giving a larger extinction diameter')],['page 3','page 6','page 7','page 8','page 9','page 10','page 11'],['Cool flames','Droplet combustion','Flame extinction'],{'initial_droplet_diameter':'approximately 4 mm','reviewed_figure':'PDF page 9, Figure 4 visually inspected'},variables=[('Cool-flame extinction diameter','mm')])

add(101,'SAME-R_Final Report','SAME-R: particle growth and detector response',
 'The report relates smoke size and morphology to material, flow and aging. Zero-flow conditions produced larger particles than nominal-flow cases, but the appendix discussion gives a 30–40% increase in diameter of average mass while its conclusion gives a 2–3-fold size increase. Those differently stated quantities are not merged into a single effect size. The report supports measuring more than one distribution moment to respond across a broad aerosol range and describes promising MPASS results; this is a research finding rather than a certified detector-performance claim.',
 [('page 83','diameter of average mass is 30 % to 40 % larger'),('page 84','2 to 3 times larger')],['page 83','page 84'],['Smoke aerosols','Smoke detection','Particle-size distribution'],{'source_caveat':'Inconsistent or differently defined size-increase statements require reconciliation.'},variables=[('Particle-size distribution',None)])

add(102,'SAME_Final Science Report','SAME: material-dependent smoke sizes and diagnostics',
 'The report finds material-dependent smoke size distributions and different responses from ISS light-scattering and Shuttle ionization detectors. Silicone and lampwick produced a broader large-particle contribution than Kapton and Teflon under the described conditions. The recovered TEM grids were contaminated, limiting interpretation of microscopy. The closing discussion proposes size-discriminating or multiple-moment detection rather than inferring universal performance from a single detector response.',
 [('page 28','The TEM grids recovered from the thermal precipitators were unfortunately contaminated'),('page 29','more than one moment')],['page 25','page 28','page 29'],['Smoke aerosols','Smoke detection','Particle-size distribution'],variables=[('Particle-size distribution',None),('Smoke-detector response',None)])

add(107,'SPICE_FinalReport','SPICE: coflow and burner-size effects on smoke points',
 'The final report states that smoke-point length increased with coflow velocity and with decreasing burner diameter. Its conclusions rank sooting tendency as ethylene < propane < 50% propylene < 75% propylene < propylene for the studied mixtures. Methane smoke points could not be reached before flames contacted the downstream plate. The campaign-wide count of 526 flames and the concluding count of 55 measured smoke-point flames describe different populations and must not be conflated.',
 [('page 24','An increase in coflow velocity increases the smoke point length.'),('page 24','A decrease in burner diameter increases the smoke point length.')],['page 20','page 24'],['Smoke point','Soot formation','Laminar diffusion flames'],variables=[('Smoke-point flame length','mm')])

add(20,'Reports_Final_20220201','BRE: quasi-steady burning and extinction boundaries',
 'The final report describes quasi-steady flames at nominal oxygen mole fractions of 0.265 and above in the tested configurations. Normal-atmosphere flames self-extinguished within 40 s, while methane/nitrogen flames extinguished within a minute across the tested atmospheres. Both large-flame radiative extinction and a small-flame quenching limit were identified. These are gas-burner emulation results, not direct burns of every condensed material represented by the model. The desired O2/CO2 atmospheric objective was not tested.',
 [('page 40','All flames ignited in normal atmosphere self-extinguished within 40 s.'),('page 40','this objective was not investigated')],['page 25','page 38','page 39','page 40'],['Burning-rate emulation','Flame extinction','Thermal radiation'],{'diagnostic_temperature_evidence':'Four TFP-measured flames supported an extinction range of 1100–1200 K; not a universal threshold.'},variables=[('Heat flux',None),('Burner surface temperature',None)])

add(22,'E-FIELD Flames Final Report','E-FIELD: electrical stabilization and diagnostic limitations',
 'The report describes peak ion currents associated with compact flames, stabilization of weak diluted flames by small electric fields, and unstable behavior at high field strengths. Quantitative soot-volume-fraction measurements were not completed because the mesh support obscured the multispectral camera; qualitative luminous-soot observations were available. Supply-response and polarity constraints also limited the time-response program. The graph therefore does not treat every originally proposed diagnostic as an achieved measurement.',
 [('page 37','distinct peak ion current'),('page 38','the key soot volume fraction instrument was unavailable')],['page 18','page 23','page 37','page 38'],['Electric-field effects on flames','Flame stability','Soot formation'],variables=[('Ion current',None),('Flame luminosity',None)])

add(23,'s_Flame_final_report','s-Flame: radiative and kinetic extinction modes',
 'The report describes nitrogen- and helium-diluted hydrogen, methane and ethylene experiments. In the cited ethylene/nitrogen tests, increasing flow led to radiative extinction and decreasing flow led to kinetic extinction. For the 20–30% ethylene mixtures described on page 26, flames established at 3 cc/s extinguished during ramps before reaching 1 cc/s downward or 8 cc/s upward. These limits describe the reported ramp protocols and are not universal fuel flammability limits. The report states that detailed analysis was ongoing.',
 [('page 26','kinetic extinctions are observed during ramp down before reaching 1 cc/s'),('page 26','before reaching 8 cc/s')],['page 24','page 25','page 26'],['Spherical diffusion flames','Flame extinction','Thermal radiation'],{'fuel':'ethylene/nitrogen','fuel_mole_fraction':'0.20–0.30 in the cited cases','ambient':'approximately 21% O2 / 79% N2'},variables=[('Fuel flow rate','cm³/s')])

add(25,'BASS-II Summary Report','BASS-II: PMMA rod flammability boundaries',
 'The report describes a minimum oxygen concentration near 13.5% on the fitted concurrent-flow PMMA-rod flammability boundary at modified stretch rates around 8–12 s⁻¹. Ignition required more oxygen than sustained burning near the limit. It reports pre-quenching oscillations near 1.1 Hz and increased CO production at low oxygen. These findings are specific to the tested rod geometries, imposed flows and boundary construction, not a general safe-oxygen threshold.',
 [('page 83','approximately 13.5 percent O2'),('page 97','Prequenching extinction oscillations at 1.1 Hz')],['page 56','page 71','page 83','page 97'],['Solid-fuel flammability','Flame extinction','Flame oscillations'],{'fuel':'PMMA rods','flow':'concurrent/stagnation configurations for the boundary'},variables=[('Oxygen concentration','% by volume'),('Flame oscillation frequency','Hz')])

add(26,'BASS_Overview of Recent ISS Results','BASS: thin-fabric spread and low-flow quenching',
 'For the reported thin-fuel cases, opposed-flow flames quickly reached steady spread and had their greatest spread rate at an intermediate flow speed. Concurrent-flow spread increased with flow speed, and quenching was observed near 1 cm/s. The presentation reports 41 samples and 115 burns. These counts and findings refer to the presentation snapshot and should not be substituted for a count of all deposited source-table records.',
 [('page 26','Quenching extinction was observed (around 1 cm/s)'),('page 10','41 samples, 115 burns completed')],['page 10','page 26'],['Flame spread','Flame extinction','Solid-fuel flammability'],{'fuel_class':'thin fabric in the cited results'},variables=[('Flame spread rate',None),('Airflow speed','cm/s')])

add(68,'FLEX-2 SRD Final _ No Hypertext','FLEX-2: measurement plan and parameter envelope',
 'The requirements document specifies time-resolved droplet and flame dimensions, extinction sizes, soot behavior and radiative emission as analysis products. It describes cameras and sampled sensor data and distinguishes minimum from complete science success. This document is a research/requirements plan; its proposed ranges and success criteria are not evidence that every combination was executed. The compact deposited experiment table is consequently represented as parameter sets.',
 [('page 53','Droplet diameter as a function time and burning rate constant')],['page 53','page 54','page 56'],['Droplet combustion','Multicomponent fuels','Flame extinction'],kind='requirements_and_analysis_plan',finding=False)

add(69,'FLEX_Test_Plan','FLEX: limiting-oxygen and suppressant test protocol',
 'The plan describes iterative oxygen/droplet-size tests to determine limiting oxygen behavior and repeats at fixed suppressant levels. It explicitly says the planning matrices do not represent the final test matrix. Therefore, hypothetical combinations in the plan are not expanded into measured runs. The graph uses the deposited named-test table for individual conditions and retains its uncertain burning-rate unit.',
 [('page 5','do not represent the final test matrix')],['page 4','page 5'],['Droplet combustion','Limiting oxygen index','Flame suppression'],kind='test_plan',finding=False)

for a,fragment in [(98,'SAFFIRE-I and SAFFIRE-III Readme'),(100,'SAFFIRE-I and SAFFIRE-III Readme'),(99,'SAFFIRE-II Readme')]:
    summary='The readme explains the sample/camera organization and distinguishes combustion samples from pre-flow/post-flow and calibration image sets. Image representations include downlinked JPEGs, mapped images and processed raw-camera formats; these are related representations, not independent experiments.'
    quote='There were 2 cameras capturing images during the experiment'
    add(a,fragment,'Saffire data organization',summary,[('word/document.xml',quote)],topics=['Spacecraft fire safety'],finding=False)

add(25,'BASS-II_ReadMe','BASS-II: source calibration and timing caveats',
 'The readme describes the investigator-specific sample families and the meaning of the test-matrix fields. It reports a one-day video-date offset, roughly one-minute flow-display response, uncalibrated radiometer gains used for relative intensity, and oxygen readings corrected by a daily offset against ISS atmosphere measurements. These limitations matter when interpreting source records and joining videos to tests.',
 [('word/document.xml','Video display is one day later than actual date')],topics=['Solid-fuel flammability'],finding=False)

add(20,'ACME_BRE_Readme','BRE: run naming and experiment organization',
 'The readme identifies four burner/fuel groups: 25-mm burners with 50% ethylene, pure ethylene or pure methane, and a 50-mm burner with pure ethylene. Run names encode year, day of year, a letter and a number; numerical suffixes often identify variants rather than replicates. The first row of each raw CSV describes its configuration.',
 [('word/document.xml','different numbers can be for repeats but are typically variants')],topics=['Burning-rate emulation'],finding=False)

add(117,'Presentations_Extinction_Characteristics','PSI-117: modeled extinction trends in n-alkane droplets',
 'The presentation compares n-heptane, n-decane and n-dodecane simulations with droplet observations. It reports stronger cool-flame reactivity and smaller extinction diameters for longer n-alkanes in the investigated cases. For n-dodecane, pressure changes lead from two-stage burning toward multicycle and warm-flame behavior. Numerical cases and measured comparisons are kept distinct; these trends are conditional on the stated model, fuel and ambient conditions.',
 [('page 16','exhibited more robust cool flame')],['page 4','page 5','page 6','page 10','page 12','page 13','page 15','page 16'],['Cool flames','Flame extinction','Computational combustion'],kind='simulation_with_experimental_comparison',variables=[('Extinction diameter','mm'),('Peak gas temperature','K')])

add(117,'Presentations_Three_Stage','PSI-117: hot, warm and cool droplet-combustion stages',
 'The presentation reports numerical n-heptane cases in which helium exchange at elevated pressure changes the intermediate and cool burning stages. It describes n-dodecane observations as supporting a prior prediction of three-stage behavior. The warm and cool stages involve different low-temperature kinetic balances; model examples are not represented as additional ISS runs.',
 [('page 17','two possible modes of quasi-steady cool flame')],['page 7','page 8','page 9','page 10','page 17','page 20'],['Cool flames','Droplet combustion','Computational combustion'],kind='simulation_with_experimental_comparison',variables=[('Flame temperature','K')])

add(21,'CLD_Flame_final_report','CLD Flame: soot, temperature and extinction diagnostics',
 'The report describes higher soot levels and lower soot temperatures in its microgravity comparisons, with peak soot shifting from the centerline toward the flame wings. It reports 4–8-fold greater sooting in the studied comparisons but also significant model/measurement discrepancies; residence time alone did not explain the differences. Improved flow controllers supported a third testing round for extinction measurements. CH* diagnostics were emphasized over the originally specified OH* images because the available CH* images were better.',
 [('page 32','4-8 times sootier'),('page 34','the residence-time argument, by itself, is not sufficient')],['page 24','page 32','page 33','page 34','page 35'],['Soot formation','Thermal radiation','Laminar diffusion flames'],variables=[('Soot volume fraction',None),('Soot temperature',None)])

add(106,'SLICE final report 20171226','SLICE: soot and flame-structure comparisons with gravity',
 'The final report summarizes measurements and simulations of coflow methane flames. Microgravity flames had lower soot temperatures and higher soot volume fractions than normal-gravity counterparts, with soot shifted toward the flame wings. It reports substantial uncertainty in coflow velocity and incomplete axisymmetry of lifted flames. Approximately 700 test conditions across 13 sessions are distinct from the date/fuel records in the compact experiment table; the report says only part of the dataset had been analyzed.',
 [('page 43','lower soot temperatures and higher volume fraction'),('page 39','significant uncertainties in the velocity')],['page 39','page 42','page 43','page 44','page 45'],['Soot formation','Flame liftoff','Laminar diffusion flames'],variables=[('Soot temperature',None),('Soot volume fraction',None),('Flame lift-off height',None)])

series = {
 'PROCI_2019_Stable_Cool.csv': ('Stable cool-flame numerical history', 'Numerical time history containing droplet diameter, burning rate, peak gas temperature and flame stand-off ratios. Initial diameter in the first data row is 0.5 mm. This is a provided simulation series, not an additional flight run.', [('Droplet diameter','mm'),('Burning rate','mm²/s'),('Peak gas temperature','K')]),
 'PROCI_2019_Oscillatory_Cool_Flame.csv': ('Oscillatory cool-flame numerical history', 'Numerical time history for the oscillatory cool-flame case with diameter, burning rate, peak gas temperature and stand-off ratios. The first data row starts at 0.5 mm. Gas-composition entries in the accompanying index mix fractions and percentages and should not be normalized without the corresponding presentation.', [('Droplet diameter','mm'),('Burning rate','mm²/s'),('Peak gas temperature','K')]),
 'PROCI_2023_Alkane_Extinction_Diameter_1atm.csv': ('Alkane extinction-diameter comparison', 'Parallel experimental and simulation series for C7, C10 and C12 fuels, with initial diameter and hot/cool extinction diameters. Columns labelled Expt and Sim remain distinct; missing cells and reported zero values are not treated as interchangeable.', [('Initial droplet diameter',None),('Hot-flame extinction diameter',None),('Cool-flame extinction diameter',None)]),
 'PROCI_2023_C12_Extinction_Diameter_vs_pressure.csv': ('Dodecane extinction versus pressure', 'Separate experimental and model hot/cool extinction-diameter series indexed by pressure in atm. Additional columns provide upper and lower cool-flame error-bar values. The independent series have unequal lengths and are not joined merely by row number.', [('Pressure','atm'),('Hot-flame extinction diameter',None),('Cool-flame extinction diameter',None)]),
 'PROCI_C12_2019_Three_Stage.csv': ('Three-stage experimental and simulated histories', 'The file places experimental dimensionless-time series, flame dimensions and radiance beside simulation time, droplet diameter, burning rate and peak temperature. Each time axis belongs to its own adjacent series. Experimental and simulation columns are not interchangeable.', [('Burning rate','mm²/s'),('Peak gas temperature','K'),('Flame diameter','mm')]),
 'MST_2024_Burning_history_Flame_diameter.csv': ('Droplet regression, flame size and radiant power', 'Experimental and model histories include squared droplet diameter, flame diameter and radiant power with separate time axes. The source labels model cases as 1 atm with initial diameter 4 mm. Independent column groups must be aligned by their time coordinate, not by file row.', [('Squared droplet diameter','mm²'),('Flame diameter','mm'),('Radiant power','W')]),
 'MST_2024_Dext.csv': ('Hot/cool extinction comparison', 'The source separates model pressure and hot/cool extinction columns from an experimental pressure and cool-extinction series. Unequal counts are retained; no one-to-one experimental/model matching is inferred from row order.', [('Hot-flame extinction diameter',None),('Cool-flame extinction diameter',None)]),
 'MST_2024_Kavg.csv': ('Average cool-flame burning rate comparison', 'The source provides separate experimental and model pressure/burning-rate series. The model header specifies mm²/s; the experimental Kavg_CF column does not repeat a unit. Its unit is left unresolved in this graph rather than silently borrowed.', [('Model burning rate','mm²/s'),('Experimental average cool-flame burning rate',None)]),
 'MST_2024_Radiance_Flame_Diameter.csv': ('Radiant power and flame diameter at two pressures', 'Experimental groups are labelled 0.5 atm and 5 atm with distinct initial diameters. Simulation groups provide radiant power, flame diameter and peak temperature. The source uses Radiance for quantities labelled W; this graph preserves that label but does not reinterpret W as spectral radiance.', [('Flame diameter','mm'),('Source-labelled radiance','W'),('Peak gas temperature','K')]),
}
for fragment,(title,summary,variables) in series.items():
    docs=[json.loads(p.read_text()) for p in (ROOT/'sources'/'PSI-117'/'extracted').glob('*.json')]
    d=next(d for d in docs if d['filename'].endswith(fragment))
    header=next(s['text'] for s in d['sections'] if s['locator']=='table, row 1')
    add(117,fragment,title,summary,[('table, row 1',header)],['table, row 1','table, row 2'],['Cool flames','Droplet combustion'],kind='provided_data_series',variables=variables)

(ROOT/'document_reviews.json').write_text(json.dumps(reviews,ensure_ascii=False,indent=2)+'\n')
print('Authored and checked',len(reviews),'document reviews')
