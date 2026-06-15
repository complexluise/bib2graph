# Informe IED — sandbox `exploracion/`

_Generado por `05_metrics_report.py` sobre `corpus_ied.parquet` (103 papers)._

## Composición del corpus

- 103 papers totales.
- 24 semillas.
- Distribución geográfica: NORTH=52, SOUTH=19, UNKNOWN=32

## Redes

### Red: `co_citacion`

- Nodos: **24** | Aristas: **0** | Densidad: **0.0000**
- Componentes conexas: **24** | GCC: **1** nodos (**4%** del total)

**Top 10 por centralidad de grado:**

  - `Modes of Extraction, Unequal Exchange, and the Progressive
Underdevelopment of an Extreme Periphery: The Brazilian Amazon,
1600--1980` — 0.000
  - `Towards an Ecological Theory of Unequal Exchange: Articulating
World System Theory and Ecological Economics` — 0.000
  - `Biophysical Trade Balance of Ecuador: A Biophysical Perspective
on Asymmetric Exchange` — 0.000
  - `Physical Trade Deficits of Brazil 1990--2015: A Material Flow
Analysis` — 0.000
  - `South-South Trade and Ecological Unequal Exchange: The Case of
India's Pharmaceutical Exports` — 0.000
  - `Is there a global environmental justice movement?` — 0.000
  - `Increased Food Production and Reduced Water Use Through
Teleconnection Between Producers and Consumers` — 0.000
  - `Food Miles, Carbon Labeling, and the Hidden Ecological Costs of
Northern Consumption` — 0.000
  - `The Material Footprint of Nations` — 0.000
  - `Rapidly Increasing Pressure on Commodity Agriculture in Latin
America` — 0.000

**Top 10 por centralidad de intermediación** (betweenness):

  - `Modes of Extraction, Unequal Exchange, and the Progressive
Underdevelopment of an Extreme Periphery: The Brazilian Amazon,
1600--1980` — 0.0000
  - `Towards an Ecological Theory of Unequal Exchange: Articulating
World System Theory and Ecological Economics` — 0.0000
  - `Biophysical Trade Balance of Ecuador: A Biophysical Perspective
on Asymmetric Exchange` — 0.0000
  - `Physical Trade Deficits of Brazil 1990--2015: A Material Flow
Analysis` — 0.0000
  - `South-South Trade and Ecological Unequal Exchange: The Case of
India's Pharmaceutical Exports` — 0.0000
  - `Is there a global environmental justice movement?` — 0.0000
  - `Increased Food Production and Reduced Water Use Through
Teleconnection Between Producers and Consumers` — 0.0000
  - `Food Miles, Carbon Labeling, and the Hidden Ecological Costs of
Northern Consumption` — 0.0000
  - `The Material Footprint of Nations` — 0.0000
  - `Rapidly Increasing Pressure on Commodity Agriculture in Latin
America` — 0.0000

**Comunidades (louvain):** 24

  - Comunidad 0 (1 nodos): `Modes of Extraction, Unequal Exchange, and the Progressive
Underdevelopment of an Extreme Periphery: The Brazilian Amazon,
1600--1980`…
  - Comunidad 1 (1 nodos): `Towards an Ecological Theory of Unequal Exchange: Articulating
World System Theory and Ecological Economics`…
  - Comunidad 2 (1 nodos): `Biophysical Trade Balance of Ecuador: A Biophysical Perspective
on Asymmetric Exchange`…
  - Comunidad 3 (1 nodos): `Physical Trade Deficits of Brazil 1990--2015: A Material Flow
Analysis`…
  - Comunidad 4 (1 nodos): `South-South Trade and Ecological Unequal Exchange: The Case of
India's Pharmaceutical Exports`…

### Red: `co_autoria`

- Nodos: **62** | Aristas: **99** | Densidad: **0.0524**
- Componentes conexas: **23** | GCC: **8** nodos (**13%** del total)

**Asortatividad (autoría con geografía):**
  - Nodos con geografía asignada: **62/62** (100%) — 0 sin asignar (autores OpenAlex sin afiliación poblada).
  - Por región (NORTH/SOUTH/UNKNOWN): **+1.000**  (positivo = homofilia (Norte con Norte))
  - Por grado (degree assortativity, ponderada): **+1.000**  (autores prolíficos co-firman con prolíficos)

**Top 10 por centralidad de grado:**

  - `A5004042357` [NORTH] — 0.115
  - `A5007427123` [NORTH] — 0.115
  - `A5050277246` [NORTH] — 0.115
  - `A5035350172` [NORTH] — 0.115
  - `martínezalier_joan` [NORTH] — 0.115
  - `temper_leah` [NORTH] — 0.115
  - `del_bene_daniela` [NORTH] — 0.115
  - `scheidel_arnim` [NORTH] — 0.115
  - `wiedmann_t_o` [NORTH] — 0.098
  - `schandl_h` [NORTH] — 0.098

**Top 10 por centralidad de intermediación** (betweenness):

  - `bunker_stephen_g` [NORTH] — 0.0000
  - `hornborg_alf` [NORTH] — 0.0000
  - `aldas_c` [SOUTH] — 0.0000
  - `álvarez_m` [SOUTH] — 0.0000
  - `orta_l` [SOUTH] — 0.0000
  - `pereira_j` [SOUTH] — 0.0000
  - `silva_r` [SOUTH] — 0.0000
  - `costa_p` [SOUTH] — 0.0000
  - `khor_m` [SOUTH] — 0.0000
  - `narayanan_s` [SOUTH] — 0.0000

**Comunidades (louvain):** 23

  - Comunidad 10 (8 nodos): `A5004042357`, `A5007427123`, `A5050277246`… — geo: NORTH:8
  - Comunidad 19 (7 nodos): `wiedmann_t_o`, `schandl_h`, `lenzen_m`… — geo: NORTH:7
  - Comunidad 13 (7 nodos): `bringezu_s`, `schuetz_h`, `pengue_w`… — geo: NORTH:7
  - Comunidad 21 (4 nodos): `davis_k_f`, `rulli_m_c`, `seveso_a`… — geo: NORTH:4
  - Comunidad 14 (4 nodos): `hoekstra_a_y`, `chapagain_a_k`, `aldaya_m_m`… — geo: NORTH:4

### Red: `co_word`

- Nodos: **58** | Aristas: **160** | Densidad: **0.0968**
- Componentes conexas: **4** | GCC: **35** nodos (**60%** del total)

**Top 10 por centralidad de grado:**

  - `unequal_exchange` — 0.281
  - `political economy` — 0.228
  - `environmental_justice` — 0.193
  - `movement (music)` — 0.193
  - `economic justice` — 0.193
  - `political science` — 0.193
  - `global justice` — 0.193
  - `environmental ethics` — 0.193
  - `sociology` — 0.193
  - `law` — 0.193

**Top 10 por centralidad de intermediación** (betweenness):

  - `unequal_exchange` — 0.1876
  - `latin america` — 0.1754
  - `telecoupling` — 0.1112
  - `food_miles` — 0.0909
  - `land_use` — 0.0536
  - `northern_consumption` — 0.0401
  - `biophysical_trade` — 0.0375
  - `india` — 0.0330
  - `brazil` — 0.0264
  - `virtual_water` — 0.0191

**Comunidades (louvain):** 7

  - Comunidad 4 (14 nodos): `environmental_justice`, `movement (music)`, `economic justice`…
  - Comunidad 1 (13 nodos): `unequal_exchange`, `ecological exchange`, `periphery`…
  - Comunidad 5 (9 nodos): `latin america`, `telecoupling`, `virtual_water`…
  - Comunidad 2 (7 nodos): `brazil`, `south_south_trade`, `india`…
  - Comunidad 3 (7 nodos): `ecological_debt`, `peru`, `comercio`…

### Red: `coupling`

- Nodos: **103** | Aristas: **646** | Densidad: **0.1230**
- Componentes conexas: **52** | GCC: **52** nodos (**50%** del total)

**Top 10 por centralidad de grado:**

  - `Ecologically unequal exchange: A theory of global environmental <i>in</i> justice` — 0.422
  - `Linking ecological debt and ecologically unequal exchange: stocks, flows, and unequal sink appropriation` — 0.422
  - `Is there a global environmental justice movement?` — 0.402
  - `Ecological Unequal Exchange: Consumption, Equity, and Unsustainable Structural Relationships within the Global Economy` — 0.392
  - `Between activism and science: grassroots concepts for sustainability coined by Environmental Justice Organizations` — 0.392
  - `Breaking Ships in the World-System: An Analysis of Two Ship Breaking Capitals, Alang-Sosiya, India and Chittagong, Bangladesh` — 0.392
  - `The Transnational Organization of Production and Uneven Environmental Degradation and Change in the World Economy` — 0.382
  - `Ecological Unequal Exchange: International Trade and Uneven Utilization of Environmental Space in the World System` — 0.373
  - `Fueling Injustice: Globalization, Ecologically Unequal Exchange and Climate Change` — 0.373
  - `Ecologically unequal exchange and ecological debt` — 0.363

**Top 10 por centralidad de intermediación** (betweenness):

  - `Ecological unequal exchange: quantifying emissions of toxic chemicals embodied in the global trade of chemicals, products, and waste` — 0.0349
  - `Contemporary Contradictions of the Global Development Project: geopolitics, global ecology and the ‘development climate’` — 0.0209
  - `Is there a global environmental justice movement?` — 0.0161
  - `Circularity, entropy, ecological conflicts and LFFU` — 0.0156
  - `Breaking Ships in the World-System: An Analysis of Two Ship Breaking Capitals, Alang-Sosiya, India and Chittagong, Bangladesh` — 0.0136
  - `Ecologically unequal exchange and ecological debt` — 0.0134
  - `Classifying and valuing ecosystem services for urban planning` — 0.0073
  - `Fueling Injustice: Globalization, Ecologically Unequal Exchange and Climate Change` — 0.0072
  - `Decolonizing the Atmosphere: The Climate Justice Movement on Climate Debt` — 0.0062
  - `Two Sides of the Same Coin: A Synthesis of Economic and Ecological Unequal Exchange` — 0.0061

**Comunidades (louvain):** 54

  - Comunidad 5 (22 nodos): `Is there a global environmental justice movement?`, `Ecologically unequal exchange and ecological debt`, `Classifying and valuing ecosystem services for urban planning`…
  - Comunidad 12 (19 nodos): `Ecological Unequal Exchange: International Trade and Uneven Utilization of Environmental Space in the World System`, `Ecological Unequal Exchange: Consumption, Equity, and Unsustainable Structural Relationships within the Global Economy`, `Ecologically Unequal Exchange, Ecological Debt, and Climate Justice`…
  - Comunidad 19 (11 nodos): `Ecological unequal exchange: quantifying emissions of toxic chemicals embodied in the global trade of chemicals, products, and waste`, `Ecological unequal exchange: Evidence from imbalanced cropland soil erosion and agricultural value-added embodied in global agricultural trade`, `Ecological unequal exchange between Turkey and the European Union: An assessment from value added perspective`…
  - Comunidad 0 (1 nodos): `Modes of Extraction, Unequal Exchange, and the Progressive
Underdevelopment of an Extreme Periphery: The Brazilian Amazon,
1600--1980`…
  - Comunidad 1 (1 nodos): `Towards an Ecological Theory of Unequal Exchange: Articulating
World System Theory and Ecological Economics`…

### Geografía del corpus

- 103 papers totales.

  - **NORTH**: 52 (50%)
  - **SOUTH**: 19 (18%)
  - **UNKNOWN**: 32 (31%)

- **Asimetría:** 27% de los papers tiene al menos un autor del Global South (incluyendo co-autorías mixtas). Útil para IED: indica penetración del Sur en el campo, no solo hegemonía del Norte.
