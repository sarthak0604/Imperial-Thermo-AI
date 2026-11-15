"""Assistant-authored scientific scope review of the 19 NASA investigations.

Statements below were composed after reading the live metadata and source tables.
They describe scope/methods, not an assertion that every objective was achieved.
Document-specific findings are stored separately with page/row evidence.
"""

# Number: summary, topics, observed/reported variables, methods, record granularity.
REVIEW = {
25: (
 'BASS-II studies ignition, growth, spread and extinction of solid fuels in forced microgravity flows. Its ISS wind-tunnel campaign includes PMMA films, slabs and rods, fabric and other sample geometries. Flow direction, ventilation and oxygen concentration are varied. The experiment table records named tests and gas readings; the readme explains calibration and video timing limitations.',
 ['Solid-fuel flammability','Flame spread','Flame extinction','Forced convection','Microgravity combustion'],
 [('Flame spread rate',None,'dependent'),('Oxygen concentration','% by volume','controlled'),('Airflow speed','cm/s','independent')],
 ['ISS Microgravity Science Glovebox wind tunnel','Video and still-image observations','Gas-concentration measurements'], 'test_record'),
26: (
 'BASS examines solid-fuel burning and inert-gas suppression in the ISS Microgravity Science Glovebox. The campaign uses fabric and other solid geometries in opposed and concurrent forced flows. Its scientific questions concern microgravity material flammability, flame spread and suppression; the deposited as-run matrix identifies the samples and tests.',
 ['Solid-fuel flammability','Flame spread','Flame suppression','Forced convection','Microgravity combustion'],
 [('Flame spread rate',None,'dependent'),('Flame size',None,'dependent'),('Airflow speed','cm/s','independent')],
 ['ISS Microgravity Science Glovebox wind tunnel','Controlled opposed and concurrent airflow','Flame imaging'], 'test_record'),
117: (
 'Ground-based computational investigation of thermo-convective perturbations to droplet cool flames, using NASA FLEX flight observations for comparison. The deposited data cover oscillatory and stable cool flames, extinction, multistage combustion and radiative behavior. Numerical predictions are distinct from the underlying flight measurements.',
 ['Cool flames','Droplet combustion','Flame extinction','Flame oscillations','Computational combustion','Thermal radiation'],
 [('Ignition delay',None,'dependent'),('Oscillation frequency',None,'dependent'),('Extinction diameter',None,'dependent')],
 ['OpenFOAM computational fluid dynamics','Low-temperature chemical kinetics','Comparison with FLEX flight observations'], 'numerical_study'),
10: (
 'ACME Flame Design investigates normal and inverse spherical diffusion flames, including soot inception, extinction and temperature structure. The final report identifies ethylene as the flight fuel except for one propane calibration day; proposed methane tests were not conducted. Separate normal- and inverse-flame tables preserve test identifiers and conditions. Adiabatic flame temperature is a calculated condition, not a measured peak flame temperature.',
 ['Spherical diffusion flames','Soot formation','Flame extinction','Microgravity combustion'],
 [('Flame temperature',None,'dependent'),('Soot volume fraction',None,'dependent'),('Flame size',None,'dependent')],
 ['Spherical burner experiments on the ISS and in drop towers','Cameras, radiometers, photomultiplier tubes and thermocouples'], 'test_record'),
159: (
 'ACME CFI-G investigates gaseous-fuel cool diffusion flames in normal and inverse spherical configurations. The tables include ignition outcomes, burn duration, termination and burner-temperature observations, including unsuccessful ignition attempts. These outcomes are preserved separately from the project hypotheses about cool-flame stability and transitions.',
 ['Cool flames','Spherical diffusion flames','Flame extinction','Flame oscillations','Microgravity combustion'],
 [('Burn time','s','dependent'),('Burner temperature','degC','dependent'),('Ignition outcome',None,'dependent')],
 ['ISS spherical diffusion-flame tests','Cameras, radiometers, photomultiplier tubes and thermocouples','Comparison with computational chemistry'], 'test_record'),
101: (
 'SAME-R is the reflight of the Smoke and Aerosol Measurement Experiment. It studies smoke-particle size and detector response under controlled heating, transport and aging. The reflight added Pyrell material, extended test conditions and an M-pass instrument. Its test-table records are not assumed to be one-to-one with the 66 flight test points described in the NASA narrative.',
 ['Smoke aerosols','Smoke detection','Particle-size distribution','Microgravity combustion'],
 [('Particle-size distribution',None,'dependent'),('Smoke-detector response',None,'dependent'),('Particle aging time','s','controlled')],
 ['Controlled heating of spacecraft materials','Smoke aging and transport','Moment-method aerosol diagnostics and post-flight validation'], 'test_record'),
98: (
 'Saffire-I examines large-scale fabric-fire growth aboard an uncrewed Cygnus vehicle after departure from the ISS. It uses cotton/fiberglass SIBAL fabric with 20 cm/s airflow, imaging, thermal diagnostics and gas sensors. The deposited table includes sample records and separate pre-test flow-visualization entries; their different roles are retained.',
 ['Solid-fuel flammability','Flame spread','Spacecraft fire safety','Forced convection','Microgravity combustion'],
 [('Burn time','s','dependent'),('Flame radiation',None,'dependent'),('Oxygen concentration',None,'dependent'),('Carbon dioxide concentration',None,'dependent')],
 ['Uncrewed Cygnus fire experiment','Two-camera imaging','Thermocouples, radiometers, gas sensors and anemometers'], 'sample_record'),
39: (
 'CFI studies droplet cool-flame behavior using the ISS Combustion Integrated Rack and Multi-User Droplet Combustion Apparatus. The record includes n-dodecane and other fuels, atmosphere composition, pressure and support-fiber conditions. Conflicting pressure ranges in the NASA narrative are not resolved by guessing; test-table conditions are kept as stated.',
 ['Cool flames','Droplet combustion','Flame extinction','Soot formation','Microgravity combustion'],
 [('Droplet diameter',None,'dependent'),('Flame size',None,'dependent'),('Flame radiation',None,'dependent')],
 ['MDCA droplet deployment and hot-wire ignition','Visible and ultraviolet imaging','Narrow-band and wide-band radiometry'], 'test_record'),
102: (
 'SAME investigates smoke-particle growth and detector response in microgravity using overheated spacecraft materials. Flow, temperature and aging conditions are controlled. The deposited compact experiment table describes eight conditions; it is not treated as a complete enumeration of every flight run. Expectations about larger particles are kept distinct from measured findings.',
 ['Smoke aerosols','Smoke detection','Particle-size distribution','Microgravity combustion'],
 [('Particle-size distribution',None,'dependent'),('Smoke-detector response',None,'dependent'),('Sample mass loss',None,'dependent')],
 ['Controlled heating and aerosol transport','Smoke-detector diagnostics','Thermophoretic sampling and post-flight microscopy'], 'condition_record'),
106: (
 'SLICE investigates the structure and stability of laminar diffusion flames, including liftoff, soot formation and radiative effects. Methane, ethylene and nitrogen-diluted fuels are tested in coflow. The experiment index is organized by test date and fuel; each dated record can cover several flames and calibrations.',
 ['Laminar diffusion flames','Flame liftoff','Soot formation','Thermal radiation','Microgravity combustion'],
 [('Flame length',None,'dependent'),('Fuel flow rate',None,'independent'),('Temperature',None,'dependent')],
 ['Fan-driven flow duct with exchangeable burners','High-resolution imaging with overlaid sensor readings','Airflow and pyrometry calibration'], 'test_day_record'),
99: (
 'Saffire-II compares burning of multiple solid materials aboard an uncrewed Cygnus spacecraft. The deposited table contains nine sample entries plus flow-visualization and explanatory records. It includes microgravity and ground-comparison outcomes, with missing materials, ambiguous labels and apparent formatting errors retained and flagged.',
 ['Solid-fuel flammability','Flame spread','Spacecraft fire safety','Forced convection','Microgravity combustion'],
 [('Burn time','s','dependent'),('Flame radiation',None,'dependent'),('Oxygen concentration',None,'dependent')],
 ['Uncrewed Cygnus fire experiment','Two-camera imaging','Thermocouples, radiometers, gas sensors and anemometers'], 'sample_record'),
107: (
 'SPICE studies the smoke point of non-buoyant coflow diffusion flames, varying fuel, burner diameter, fuel rate and air velocity. The table records flow conditions and ignition/off times. Duplicate rows are retained as source records and flagged; they do not establish independent replicate experiments.',
 ['Laminar diffusion flames','Smoke point','Soot formation','Microgravity combustion'],
 [('Flame length',None,'dependent'),('Fuel flow rate','mg/s','independent'),('Coflow air velocity','cm/s','independent')],
 ['ISS Microgravity Science Glovebox coflow burner','Adjustment of fuel rate to smoke onset','Still and video imaging'], 'condition_record'),
100: (
 'Saffire-III extends the large-scale SIBAL fabric experiments aboard an uncrewed Cygnus vehicle. The deposited table contains concurrent- and opposed-flow sample records at 30 cm/s. Comparisons with Saffire-I must preserve the different airflow and the source-specific geometry fields.',
 ['Solid-fuel flammability','Flame spread','Spacecraft fire safety','Forced convection','Microgravity combustion'],
 [('Flame radiation',None,'dependent'),('Oxygen concentration',None,'dependent'),('Carbon dioxide concentration',None,'dependent')],
 ['Uncrewed Cygnus fire experiment','Two-camera imaging','Thermocouples, radiometers, gas sensors and anemometers'], 'sample_record'),
21: (
 'ACME CLD Flame investigates dilute and sooting methane/ethylene coflow diffusion flames. Scientific objectives include liftoff, extinction, flame temperature and soot volume fraction. Its table summarizes test days, dilution ranges and the number of flames ignited, rather than individual flames; malformed fuel labels remain flagged source values.',
 ['Laminar diffusion flames','Flame liftoff','Flame extinction','Soot formation','Microgravity combustion'],
 [('Flame lift-off height',None,'dependent'),('Soot temperature',None,'dependent'),('Soot volume fraction',None,'dependent')],
 ['ISS ACME coflow burner','Chemiluminescence imaging','Laser extinction and thin-filament pyrometry'], 'test_day_record'),
20: (
 'ACME BRE uses porous gas burners to emulate condensed-fuel burning in microgravity and relate burning to material properties. It studies atmospheric composition, pressure and extinction. The test-day index lists burner size, fuel and oxygen conditions, but does not supply chamber pressures; apparent oxygen-percentage formatting errors are retained and flagged.',
 ['Burning-rate emulation','Flame extinction','Solid-fuel flammability','Microgravity combustion'],
 [('Burner surface temperature',None,'dependent'),('Heat flux',None,'dependent'),('Fuel flow rate',None,'independent')],
 ['Porous circular burner experiments','Surface-temperature and heat-flux measurements','Ground tests and computational-model comparison'], 'test_day_record'),
68: (
 'FLEX-2 extends droplet-combustion research to pure and multicomponent fuels, droplet interactions, soot and extinction. The compact experiment table lists fuel-dependent parameter ranges and combinations rather than individual measured runs. Those ranges are kept as parameter sets and are not expanded into synthetic experiments.',
 ['Droplet combustion','Multicomponent fuels','Flame extinction','Soot formation','Microgravity combustion'],
 [('Ambient pressure','atm','controlled'),('Ambient temperature','degC','controlled'),('Droplet diameter','mm','independent')],
 ['MDCA droplet deployment and hot-wire ignition','High-speed imaging','Chamber pressure and temperature recording'], 'parameter_set'),
22: (
 'ACME E-FIELD Flames investigates electrical forcing of laminar diffusion flames through a voltage difference between the burner and a mesh electrode. Methane/ethylene flames, polarity, dilution and coflow are varied. The test-day table includes continuation rows, which remain separate unresolved source records instead of being silently filled down.',
 ['Electric-field effects on flames','Laminar diffusion flames','Soot formation','Flame stability','Microgravity combustion'],
 [('Ion current',None,'dependent'),('Flame response time',None,'dependent'),('Flame luminosity',None,'dependent')],
 ['High-voltage burner-to-mesh forcing','Voltage-current measurements','Spectral and high-resolution flame imaging'], 'test_day_record'),
23: (
 'ACME s-Flame investigates transient spherical diffusion-flame structure, extinction and pulsating instabilities for fuels and diluents of different transport properties. The experimental index summarizes test days and flame counts. Source atmospheric labels with apparent sequence-fill errors are preserved and flagged.',
 ['Spherical diffusion flames','Flame extinction','Flame oscillations','Thermal radiation','Microgravity combustion'],
 [('Flame temperature',None,'dependent'),('Burner temperature',None,'dependent'),('Radiative flux',None,'dependent')],
 ['Spherical porous burner experiments','Synchronized spectral imaging, temperature and radiative-flux diagnostics','Comparison with detailed numerical simulations'], 'test_day_record'),
69: (
 'FLEX investigates droplet burning, extinction and suppression in microgravity. The table records named methanol and heptane tests with ambient conditions, initial and extinction diameters, duration and termination. The burning-rate column has an ambiguous declared unit, which is preserved rather than converted to an assumed physical unit.',
 ['Droplet combustion','Flame extinction','Flame suppression','Limiting oxygen index','Microgravity combustion'],
 [('Droplet diameter','mm','dependent'),('Visible-flame extinction diameter','mm','dependent'),('Burn time','s','dependent')],
 ['MDCA droplet combustion tests','Oxygen and suppressant variation','Droplet and flame imaging'], 'test_record'),
}

CONCEPTS = {
 'Solid-fuel flammability':(['material flammability'],'Ignition and sustained burning behavior of solid materials under specified conditions.'),
 'Flame spread':([], 'Propagation of a flame along or over a fuel surface.'),
 'Flame extinction':(['quenching'],'Termination of combustion under specified chemical and transport conditions.'),
 'Flame suppression':(['fire suppression'],'Use of an intervention such as an inert gas to extinguish or limit burning.'),
 'Forced convection':(['ventilation'],'Flow driven by an imposed velocity rather than buoyancy alone.'),
 'Microgravity combustion':(['reduced-gravity combustion'],'Combustion studied under reduced buoyancy in a microgravity environment.'),
 'Cool flames':(['low-temperature combustion'],'Low-temperature combustion associated with fuel oxidation chemistry.'),
 'Droplet combustion':([], 'Combustion involving isolated or interacting liquid-fuel droplets.'),
 'Flame oscillations':(['pulsating flames'],'Time-dependent oscillation of flame structure or burning behavior.'),
 'Computational combustion':(['CFD'],'Numerical modeling of reacting flow, heat transfer and chemical kinetics.'),
 'Thermal radiation':(['radiative heat transfer'],'Radiant transfer of energy from flame, soot or heated surfaces.'),
 'Spherical diffusion flames':([], 'Non-premixed flames arranged approximately spherically around a source or sink.'),
 'Laminar diffusion flames':(['non-premixed flames'],'Laminar flames whose fuel and oxidizer mix by transport.'),
 'Soot formation':(['sooting'],'Production and evolution of carbonaceous particles during combustion.'),
 'Smoke aerosols':([], 'Suspended particles or droplets produced by heating or burning materials.'),
 'Smoke detection':([], 'Detection of combustion-generated aerosols with optical, ionization or other diagnostics.'),
 'Particle-size distribution':(['aerosol size distribution'],'Distribution of aerosol number or mass across particle sizes.'),
 'Spacecraft fire safety':([], 'Understanding and controlling fire hazards in spacecraft environments.'),
 'Flame liftoff':(['lifted flames'],'Separation of the flame base from the burner outlet.'),
 'Smoke point':(['laminar smoke point'],'A flame condition marking the onset of soot emission.'),
 'Burning-rate emulation':(['BRE'],'Using a controlled gas burner to represent aspects of condensed-fuel burning.'),
 'Multicomponent fuels':(['fuel mixtures'],'Fuels containing multiple chemical components with coupled vaporization and combustion.'),
 'Electric-field effects on flames':(['ion-driven convection'],'Influence of electrical forcing and charged species on flame behavior.'),
 'Flame stability':([], 'Persistence and dynamic response of a flame under changes in operating conditions.'),
 'Limiting oxygen index':(['LOI'],'An oxygen threshold for sustaining burning under the specified test protocol.'),
}
