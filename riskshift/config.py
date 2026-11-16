"""Central configuration for RiskShift-India.

Every threshold, weight and seed used anywhere in the project lives here so that
choices are fixed in one place (and logged in docs/rules_log.md) before results
are looked at.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# ---------------------------------------------------------------- paths
RAW_XLSX = ROOT / "S14B_Global_and_Location_Specific_Risk_Factor_Deaths.XLSX"
PROTOTYPE_EXTRACT = ROOT / "RiskShift_India_S14B_extract.csv"   # supplied pilot extract

DATA = ROOT / "data"
REFERENCE = DATA / "reference"
INTERIM = DATA / "interim"
PROCESSED = DATA / "processed"
OUT = ROOT / "outputs"
TABLES = OUT / "tables"
FIGURES = OUT / "figures"
DOCS = ROOT / "docs"

EXTRACT_CSV = INTERIM / "s14b_india_extract.csv"          # output of 01_extract
ANNOTATED = INTERIM / "s14b_india_annotated.parquet"      # output of 02_annotate
SETS_JSON = PROCESSED / "risk_sets.json"                  # output of 03_sets
FEATURES = PROCESSED / "features_state_risk.parquet"      # output of 04_features
FEATURES_INDIA = PROCESSED / "features_india_risk.parquet"
MC_DRAWS = PROCESSED / "mc_draws.npz"                     # output of rq3 (reused by rq4)

for _p in (REFERENCE, INTERIM, PROCESSED, TABLES, FIGURES, DOCS):
    _p.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------- S14B layout
ROWS_PER_BLOCK = 844          # 88 risk "All causes" rows + 756 risk -> cause rows
N_BLOCKS = 705
FIRST_DATA_ROW = 4            # Excel row of the first data row (3 header rows)
INDIA_BLOCK = 353             # block position of India; states follow
INDIA_BLOCKS = list(range(353, 385))   # India + 31 state units (keyed by position, never by name)

MEASURES = ["deaths", "paf", "asr"]
YEARS = [1990, 2010, 2023]
STATS = ["mean", "lo", "hi"]

# ---------------------------------------------------------------- annotation rules
# Four S14B names that differ from the GBD 2023 risk hierarchy table (Appendix 2, S1).
# Levels below follow that hierarchy.
MANUAL_RISK_LEVELS = {
    "Low birth weight and short gestation": 3,
    "Low birth weight": 4,
    "Diet low in fiber": 3,
    "Bullying victimization": 3,
}
# Risks with no estimated mortality anywhere in India ("-" in every cell): dropped.
NO_MORTALITY_RISKS = [
    "Bullying victimization",
    "Nitrogen dioxide pollution",
    "Occupational noise",
    "Occupational ergonomic factors",
]
AGGREGATE_UNITS = ["Other Union Territories"]

# External geography label for RQ4 4d: Government of India Zonal Councils
# (States Reorganisation Act 1956 + North Eastern Council Act 1971; Sikkim in NEC).
# SDI group (GBD Appendix 1, S12) was not supplied in this upload.
ZONE = {
    "Delhi": "Northern", "Haryana": "Northern", "Himachal Pradesh": "Northern",
    "Jammu & Kashmir and Ladakh": "Northern", "Punjab": "Northern", "Rajasthan": "Northern",
    "Chhattisgarh": "Central", "Madhya Pradesh": "Central", "Uttar Pradesh": "Central",
    "Uttarakhand": "Central",
    "Bihar": "Eastern", "Jharkhand": "Eastern", "Odisha": "Eastern", "West Bengal": "Eastern",
    "Goa": "Western", "Gujarat": "Western", "Maharashtra": "Western",
    "Andhra Pradesh": "Southern", "Karnataka": "Southern", "Kerala": "Southern",
    "Tamil Nadu": "Southern", "Telangana": "Southern",
    "Arunachal Pradesh": "North-Eastern", "Assam": "North-Eastern", "Manipur": "North-Eastern",
    "Meghalaya": "North-Eastern", "Mizoram": "North-Eastern", "Nagaland": "North-Eastern",
    "Sikkim": "North-Eastern", "Tripura": "North-Eastern",
    "Other Union Territories": "Aggregate UTs",
}

# ---------------------------------------------------------------- features
SMALL_BASE_ASR = 5.0          # 2010 ASR under 5 per 100,000 -> small_base flag
LOG_FLOOR = 0.05              # clip before log (S14B rounds ASR to 0.1)

# ---------------------------------------------------------------- risk sets
POLICY_TOP_N = 8              # top national 2023 ASR in the policy pool, plus clearly-rising risks above the materiality floor
DETAIL_MIN_ASR = 0.5          # level-3 risk must have ASR >= this in every state in 2010 and 2023 (S14B rounds to 0.1, so smaller values carry >10% rounding error)
DETAIL_SPLIT = {              # level-3 risks replaced by their level-4 components in the Detail set
    "Particulate matter pollution": [
        "Ambient particulate matter pollution",
        "Household air pollution from solid fuels",
    ],
}

# ---------------------------------------------------------------- RQ1
DIVERGENCE_PP = 10.0          # adverse divergence threshold (percentage points)
DIVERGENCE_PP_ALT = [5.0, 15.0]

# ---------------------------------------------------------------- RQ2
WEIGHTS = {"rate": 0.40, "worsening": 0.35, "divergence": 0.25}
MATERIALITY_ASR = 10.0        # 2023 ASR floor for entering a cross-risk top N
TOP_NS = [10, 20, 30]
SUCCESS_MIN_NEW = 3           # "at least a few" clear-worsening new pairs per top 20

# ---------------------------------------------------------------- RQ3
SEED = 20261116
N_WEIGHT_DRAWS = 1000
N_MC_DRAWS = 1000
ROBUST_FREQ = 0.80
MODERATE_FREQ = 0.50
PRIMARY_N = 20

# ---------------------------------------------------------------- RQ4
K_RANGE = [2, 3, 4, 5, 6]
KMEANS_STARTS = 50
KMEANS_STARTS_RESAMPLE = 10   # for null / bootstrap / perturbation refits
N_NULL = 500
N_BOOT = 500
N_GAP_REFS = 50
PCA_VAR = 0.80
MAX_RAW_FEATURES = 20
SIL_MIN = 0.25
BOOT_JACCARD_STABLE = 0.75
BOOT_JACCARD_PATTERN = 0.60
BOOT_JACCARD_DISSOLVED = 0.50
ARI_MIN = 0.60
CORE_COASSIGN = 0.70          # consensus: states co-assigned >= this form a stable core
FLOAT_COASSIGN = 0.50         # consensus: max co-assignment below this = floater
N_JOBS = -1

DISCLAIMER = ("Association in modelled GBD 2023 estimates; not causal; "
              "not an intervention recommendation.")
