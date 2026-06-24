"""
Performance determinant 8-category taxonomy with keyword dictionaries,
canonical name mappings, and alias resolution.

Categories:
1. physiological_requirements  生理要求
2. technical_requirements      技术要求
3. tactical_requirements       战术要求
4. nutritional_requirements    营养要求
5. psychological_skills        心理技能
6. equipment_characteristics   器材特点
7. health                      健康
8. competition_rules           比赛规则
9. other_uncertain             其他/不确定
"""

# ── Category definitions ──────────────────────────────────────────────

CATEGORIES = {
    "physiological_requirements": {
        "key": "physiological_requirements",
        "name_cn": "生理要求",
        "name_en": "Physiological Requirements",
        "description": "Physiological and energetic demands of performance including aerobic/anaerobic capacity, strength, speed, power, and metabolic factors.",
    },
    "technical_requirements": {
        "key": "technical_requirements",
        "name_cn": "技术要求",
        "name_en": "Technical Requirements",
        "description": "Sport-specific technique, skill execution, movement patterns, biomechanics, and motor control.",
    },
    "tactical_requirements": {
        "key": "tactical_requirements",
        "name_cn": "战术要求",
        "name_en": "Tactical Requirements",
        "description": "Decision making, strategy, pacing, positioning, and game intelligence.",
    },
    "nutritional_requirements": {
        "key": "nutritional_requirements",
        "name_cn": "营养要求",
        "name_en": "Nutritional Requirements",
        "description": "Dietary intake, supplementation, hydration, body composition, and energy availability.",
    },
    "psychological_skills": {
        "key": "psychological_skills",
        "name_cn": "心理技能",
        "name_en": "Psychological Skills",
        "description": "Cognitive and perceptual skills including reaction time, attention, motivation, anxiety management, and mental resilience.",
    },
    "equipment_characteristics": {
        "key": "equipment_characteristics",
        "name_cn": "器材特点",
        "name_en": "Equipment Characteristics",
        "description": "Sports equipment, footwear, wearables, tools, and technology affecting performance.",
    },
    "health": {
        "key": "health",
        "name_cn": "健康",
        "name_en": "Health",
        "description": "Injury risk, recovery, sleep, training load management, illness, and overall athlete wellbeing.",
    },
    "competition_rules": {
        "key": "competition_rules",
        "name_cn": "比赛规则",
        "name_en": "Competition Rules",
        "description": "Rules, regulations, scoring systems, qualification criteria, and competition formats.",
    },
    "other_uncertain": {
        "key": "other_uncertain",
        "name_cn": "其他/不确定",
        "name_en": "Other / Uncertain",
        "description": "Terms that could not be confidently classified into the eight main categories.",
    },
}

# ── Category: physiological_requirements ──────────────────────────────

PHYSIOLOGICAL_KEYWORDS = {
    # Aerobic
    "vo2max", "vo2 max", "v̇o2max", "v̇o₂max", "maximal oxygen uptake",
    "maximal oxygen consumption", "aerobic capacity", "aerobic power",
    "maximal aerobic speed", "aerobic fitness", "maximum oxygen uptake",
    "oxygen uptake", "oxygen consumption", "v̇o2", "vo2", "vo₂",
    "v̇o2peak", "vo2peak", "peak oxygen uptake",
    # Anaerobic
    "anaerobic capacity", "anaerobic power", "anaerobic threshold",
    "anaerobic speed reserve", "anaerobic performance", "anaerobic fitness",
    "maximal anaerobic power", "wingate", "anaerobic contribution",
    # Lactate / thresholds
    "lactate threshold", "lactate turnpoint", "onset of blood lactate accumulation",
    "obla", "maximal lactate steady state", "mlss",
    "ventilatory threshold", "ventilatory threshold 1", "ventilatory threshold 2",
    "gas exchange threshold", "respiratory compensation point",
    "blood lactate", "lactate concentration", "lactate profile",
    "lactate accumulation", "peak lactate", "lactate clearance",
    # Running economy / efficiency
    "running economy", "movement economy", "exercise economy",
    "gross efficiency", "delta efficiency", "net efficiency",
    "oxygen cost", "energy cost", "energetic cost",
    "metabolic cost", "metabolic power",
    # Cardiovascular
    "heart rate", "hr", "maximal heart rate", "hrmax", "hr max",
    "heart rate variability", "hrv", "heart rate recovery",
    "stroke volume", "cardiac output", "cardiac function",
    # Speed / sprint
    "speed", "sprint ability", "sprint performance", "sprint speed",
    "maximal sprint speed", "mss", "maximum speed",
    "acceleration", "acceleration capacity", "deceleration",
    "repeated sprint ability", "rsa", "sprint repeatability",
    "change of direction", "cod", "agility",
    # Strength / power
    "strength", "maximal strength", "relative strength",
    "force production", "rate of force development", "rfd",
    "power", "power output", "peak power", "mean power",
    "muscle strength", "muscular strength", "muscle power",
    "isometric force", "dynamic strength", "concentric force",
    "eccentric strength", "explosive strength",
    # Muscular
    "muscular endurance", "muscle endurance",
    "fatigue resistance", "fatigue index",
    "neuromuscular function", "neuromuscular efficiency",
    "muscle activation", "electromyography", "emg",
    # Tendon / stiffness
    "tendon stiffness", "muscle stiffness", "leg stiffness",
    "vertical stiffness", "spring-mass", "stretch-shortening cycle",
    # Energy systems
    "energy system", "metabolic pathway", "aerobic metabolism",
    "anaerobic metabolism", "glycolytic", "oxidative",
    "phosphocreatine", "creatine phosphate", "atp",
    # Buffering
    "buffering capacity", "ph regulation",
    # Body composition related to physiology
    "lean body mass", "muscle mass", "fat free mass",
    "body fat percentage", "body fat",
    # Endurance
    "endurance", "endurance capacity", "endurance performance",
    "time to exhaustion", "time trial performance", "tte",
    "critical speed", "critical power", "critical velocity",
    "w'", "d'", "curvature constant",
    # Efficiency
    "mechanical efficiency", "work efficiency",
    # Heat / environmental physiology
    "thermoregulation", "sweat rate", "core temperature",
    "heat acclimation", "heat adaptation",
}

# ── Category: technical_requirements ──────────────────────────────────

TECHNICAL_KEYWORDS = {
    # Technique general
    "technique", "technical skill", "skill execution", "skill level",
    "movement pattern", "movement quality", "motor pattern",
    "coordination", "motor control", "motor skill",
    "technical performance", "technical ability", "technical proficiency",
    "technique analysis", "technique assessment",
    # Biomechanics
    "biomechanics", "biomechanical", "kinematics", "kinetics",
    "joint angle", "joint velocity", "joint moment",
    "angular velocity", "angular displacement",
    "ground reaction force", "grf", "impulse",
    # Gait / running
    "gait", "gait pattern", "gait cycle", "gait analysis",
    "stride length", "stride frequency", "step length", "step frequency",
    "cadence", "stride width", "stride time",
    "ground contact time", "gct", "contact time",
    "flight time", "swing time", "stance time",
    "running mechanics", "running technique", "running form",
    # Sport-specific
    "stroke technique", "stroke length", "stroke rate",
    "jump technique", "takeoff", "landing mechanics",
    "throwing technique", "throwing mechanics", "release angle",
    "kicking technique", "kicking accuracy",
    "pass accuracy", "pass technique", "shot accuracy",
    "dribbling", "ball control", "first touch",
    "batting", "swing mechanics", "swing technique",
    "stroke mechanics", "swim technique", "swimming efficiency",
    "turn technique", "start technique", "block start",
    # accuracy / consistency
    "movement efficiency", "movement economy",
    "technical error", "skill consistency", "movement variability",
    "technique consistency", "skill retention", "skill acquisition",
    # Posture / alignment
    "posture", "alignment", "body position",
    "center of mass", "center of pressure",
}

# ── Category: tactical_requirements ───────────────────────────────────

TACTICAL_KEYWORDS = {
    # Pacing / racing
    "pacing strategy", "pacing", "race strategy",
    "pacing pattern", "pacing profile", "even pacing",
    "negative split", "positive split", "sprint finish",
    "race tactics", "competition strategy",
    # Decision making
    "decision making", "decision speed", "decision accuracy",
    "game intelligence", "tactical knowledge", "tactical awareness",
    "situational awareness", "game sense", "game reading",
    # Positioning
    "positioning", "spatial awareness", "court position",
    "field position", "formation", "positioning error",
    # Team
    "team cooperation", "team coordination", "team tactics",
    "collective behavior", "team strategy", "group tactics",
    "passing network", "passing pattern", "team shape",
    # Offense/defense
    "offensive strategy", "offensive tactics", "attacking pattern",
    "defensive strategy", "defensive tactics", "defensive organization",
    "pressing", "counter-pressing", "counter-attack",
    # Transition
    "transition", "transition speed", "offensive transition",
    "defensive transition", "turnover",
    # Opponent
    "opponent pressure", "opponent analysis", "opponent strategy",
    "match-up", "one-on-one", "duel",
    # Role / context
    "role-specific action", "positional role",
    "match context", "situational performance",
    "game phase", "match phase",
    "tactical behavior", "tactical action",
    "spacing", "spatial distribution", "distance between players",
    # Set pieces
    "set piece", "corner kick", "free kick", "penalty strategy",
    # Competition
    "competition strategy", "tournament strategy",
    "race plan", "race execution",
}

# ── Category: nutritional_requirements ────────────────────────────────

NUTRITIONAL_KEYWORDS = {
    # Macronutrients
    "carbohydrate intake", "carbohydrate loading", "carbohydrate",
    "protein intake", "protein synthesis", "protein supplement",
    "fat intake", "dietary fat", "fat oxidation",
    "energy intake", "caloric intake", "energy availability",
    "energy deficit", "energy balance", "low energy availability",
    # Hydration
    "hydration", "hydration status", "fluid intake",
    "dehydration", "fluid balance", "electrolyte balance",
    "water intake", "fluid replacement", "hypohydration",
    # Supplements
    "supplementation", "supplement", "dietary supplement",
    "caffeine", "creatine", "nitrate", "nitric oxide",
    "beta alanine", "bicarbonate", "sodium bicarbonate",
    "beetroot juice", "nitrate supplementation",
    "vitamin d", "vitamin", "mineral",
    "antioxidant", "omega 3", "fish oil",
    # Iron / hematology
    "iron status", "iron deficiency", "ferritin",
    "hemoglobin", "hematocrit", "anemia",
    # Body composition
    "body composition", "body mass", "body weight",
    "weight management", "weight loss", "weight gain",
    # Recovery nutrition
    "recovery nutrition", "post-exercise nutrition",
    "glycogen", "glycogen resynthesis", "glycogen replenishment",
    "muscle glycogen", "liver glycogen",
    # Specific diets
    "ketogenic diet", "high fat diet", "low carbohydrate",
    "high carbohydrate", "high protein",
    "intermittent fasting", "time restricted feeding",
    # Gut
    "gut health", "gut microbiome", "gastrointestinal",
    "gi distress", "gi comfort",
    # RED-S
    "red-s", "relative energy deficiency",
    "female athlete triad", "menstrual function",
    "bone health", "bone mineral density",
}

# ── Category: psychological_skills ────────────────────────────────────

PSYCHOLOGICAL_KEYWORDS = {
    # Cognitive / perceptual
    "anticipation", "anticipation skill", "anticipatory",
    "visual skill", "visual search", "visual attention",
    "visual perception", "visual tracking", "gaze behavior",
    "reaction time", "simple reaction time", "choice reaction time",
    "response time", "processing speed", "cognitive speed",
    # Anxiety / arousal
    "anxiety", "competitive anxiety", "somatic anxiety",
    "cognitive anxiety", "state anxiety", "trait anxiety",
    "arousal", "arousal regulation", "activation level",
    "stress", "stress response", "stress management",
    "cortisol", "stress hormone",
    # Attention / concentration
    "attention", "attentional focus", "concentration",
    "sustained attention", "selective attention", "divided attention",
    "mindfulness", "attentional control",
    # Motivation / confidence
    "confidence", "self-confidence", "self-efficacy",
    "motivation", "intrinsic motivation", "achievement motivation",
    "goal orientation", "task motivation", "ego orientation",
    # Resilience / coping
    "resilience", "mental toughness", "psychological resilience",
    "coping", "coping strategy", "emotional regulation",
    "mental skills", "psychological skills", "mental preparation",
    # Fatigue
    "mental fatigue", "cognitive fatigue", "mental exhaustion",
    "decision fatigue", "psychological fatigue",
    "burnout", "overtraining syndrome",
    # Team / social
    "team cohesion", "social cohesion", "group dynamics",
    "leadership", "coach-athlete relationship",
    "communication", "team communication",
    # Performance states
    "flow state", "optimal experience", "zone",
    "peak performance", "clutch performance",
    "choking", "performance under pressure",
    # Sleep / mood
    "mood", "mood state", "profile of mood states",
    "psychological wellbeing", "mental health",
    "self-regulation", "self-control",
    "personality", "perfectionism", "fear of failure",
}

# ── Category: equipment_characteristics ───────────────────────────────

EQUIPMENT_KEYWORDS = {
    # Footwear
    "shoes", "footwear", "spikes", "running shoes",
    "minimalist shoes", "maximalist shoes", "carbon fiber plate",
    "shoe stiffness", "shoe mass", "shoe comfort",
    "cleats", "boots", "football boots",
    # Wearables
    "wearable device", "wearable sensor", "wearable technology",
    "gps", "global positioning system", "gps device",
    "accelerometer", "gyroscope", "inertial sensor", "imu",
    "heart rate monitor", "hr monitor",
    "power meter", "cycling computer",
    # Sports equipment
    "racket", "racquet", "racket stiffness",
    "bicycle", "bike", "cycling equipment",
    "boat", "rowing equipment", "kayak",
    "sled", "bobsled", "luge",
    "ball", "ball type", "ball size",
    "stick", "bat", "club", "pole",
    "swimsuit", "swimming suit", "wetsuit",
    "helmet", "protective equipment", "protective gear",
    # Setup / tool
    "equipment setup", "bike fit", "bike setup",
    "clothing", "sportswear", "compression garment",
    "compression clothing", "compression socks",
    "surface", "track surface", "field surface",
    "playing surface", "court surface",
    "tool", "device", "gear", "material",
    # Technology
    "technology", "performance technology",
    "video analysis", "motion capture",
    "force plate", "force platform",
    "timing system", "timing gate",
    "laser", "radar", "lidar",
    "dartfish", "kinovea",
}

# ── Category: health ──────────────────────────────────────────────────

HEALTH_KEYWORDS = {
    # Injury
    "injury risk", "injury incidence", "injury rate",
    "injury prevention", "injury epidemiology",
    "injury surveillance", "injury burden",
    "overuse injury", "acute injury", "traumatic injury",
    "lower limb injury", "upper limb injury",
    "knee injury", "ankle injury", "shoulder injury",
    "hamstring injury", "groin injury", "acl injury",
    "tendon injury", "tendinopathy", "tendon pain",
    "stress fracture", "bone stress injury",
    "muscle injury", "muscle strain", "muscle damage",
    "concussion", "head injury", "brain injury",
    "ligament injury", "joint injury",
    # Illness
    "illness", "illness incidence", "upper respiratory tract infection",
    "urti", "infection", "immune function",
    "respiratory illness", "gastrointestinal illness",
    # Recovery
    "recovery", "recovery strategy", "recovery time",
    "active recovery", "passive recovery",
    "post-exercise recovery", "recovery kinetics",
    "regeneration",
    # Sleep
    "sleep", "sleep quality", "sleep duration",
    "sleep deprivation", "sleep hygiene", "sleep efficiency",
    "sleep disorder", "insomnia",
    # Soreness / fatigue
    "soreness", "muscle soreness", "doms",
    "delayed onset muscle soreness",
    "fatigue", "perceived fatigue", "neuromuscular fatigue",
    "central fatigue", "peripheral fatigue",
    # Training load
    "training load", "internal load", "external load",
    "load management", "training load monitoring",
    "acute chronic workload ratio", "acwr",
    "training stress balance", "tsb",
    "overtraining", "overtraining syndrome", "non-functional overreaching",
    "functional overreaching", "overreaching",
    # Range of motion / flexibility
    "pain", "injury pain", "pain perception",
    "asymmetry", "limb asymmetry", "bilateral asymmetry",
    "range of motion", "rom", "mobility",
    "flexibility", "joint range of motion",
    "joint function", "joint health",
    # Specific conditions
    "low back pain", "back pain", "lbp",
    "knee pain", "patellofemoral pain",
    "achilles tendon", "patellar tendon",
    "plantar fasciitis", "shin splints",
    # Women's health
    "menstrual health", "menstrual cycle", "menstrual phase",
    "menstrual dysfunction", "amenorrhea",
    "female health", "female athlete",
    # Environmental
    "environmental stress", "heat stress", "heat illness",
    "cold stress", "altitude illness", "altitude sickness",
    "exertional heat illness", "heat stroke",
    # Immune / wellness
    "wellness", "wellbeing", "wellness monitoring",
    "subjective wellbeing", "perceived wellbeing",
    "mood disturbance", "psychological stress",
    # Medical
    "medical screening", "pre-participation screening",
    "health assessment", "medical assessment",
    "return to play", "return to sport",
    "rehabilitation", "rehab program",
}

# ── Category: competition_rules ───────────────────────────────────────

COMPETITION_RULES_KEYWORDS = {
    # General rules
    "rule", "regulation", "rule change", "rule modification",
    "competition rule", "sport rule", "official rule",
    "governing body", "federation rule", "if rule",
    # Scoring
    "scoring", "scoring system", "scoring rule",
    "point system", "score calculation", "score evaluation",
    "judging", "judging criteria", "judging system",
    "judging panel", "judge score", "technical score",
    "artistic score", "difficulty score", "execution score",
    "penalty", "penalty points", "penalty system",
    "bonus points", "point deduction",
    # Qualification
    "qualification", "qualification criteria", "qualification standard",
    "entry standard", "entry requirement",
    "selection criteria", "selection policy",
    "team selection", "athlete selection",
    "disqualification", "dq", "disqualification rule",
    "eligibility", "eligibility criteria", "eligibility rule",
    # Competition format
    "competition format", "event format", "race format",
    "tournament format", "league format", "championship format",
    "round", "heat", "semifinal", "final",
    "ranking system", "ranking points", "world ranking",
    "event rule", "race rule", "match rule",
    # Equipment regulation
    "equipment regulation", "equipment rule",
    "implement specification", "equipment check",
    "doping control", "anti-doping", "wada",
    "banned substance", "prohibited list",
    # Time / measurement
    "time rule", "time limit", "time penalty",
    "measurement rule", "timing system rule",
    "false start", "false start rule",
    # Event specific
    "weight category", "weight class",
    "age category", "age group rule",
    "classification", "classification rule",
    "handicap", "handicap system",
}

# ── Category mapping ──────────────────────────────────────────────────

CATEGORY_KEYWORD_MAP = {
    "physiological_requirements": PHYSIOLOGICAL_KEYWORDS,
    "technical_requirements": TECHNICAL_KEYWORDS,
    "tactical_requirements": TACTICAL_KEYWORDS,
    "nutritional_requirements": NUTRITIONAL_KEYWORDS,
    "psychological_skills": PSYCHOLOGICAL_KEYWORDS,
    "equipment_characteristics": EQUIPMENT_KEYWORDS,
    "health": HEALTH_KEYWORDS,
    "competition_rules": COMPETITION_RULES_KEYWORDS,
}

# ── Canonical name standardization ────────────────────────────────────

CANONICAL_NAMES = {
    # VO2max variants
    "vo2max": "vo2max",
    "vo2 max": "vo2max",
    "v̇o2max": "vo2max",
    "v̇o₂max": "vo2max",
    "maximal oxygen uptake": "vo2max",
    "maximum oxygen uptake": "vo2max",
    "maximal oxygen consumption": "vo2max",
    "vo2peak": "vo2peak",
    "v̇o2peak": "vo2peak",
    "peak oxygen uptake": "vo2peak",
    # Lactate threshold
    "lactate threshold": "lactate_threshold",
    "lactate turnpoint": "lactate_threshold",
    "onset of blood lactate accumulation": "lactate_threshold",
    "obla": "lactate_threshold",
    "maximal lactate steady state": "maximal_lactate_steady_state",
    "mlss": "maximal_lactate_steady_state",
    # Ventilatory threshold
    "ventilatory threshold": "ventilatory_threshold",
    "ventilatory threshold 1": "ventilatory_threshold",
    "ventilatory threshold 2": "ventilatory_threshold_2",
    "gas exchange threshold": "ventilatory_threshold",
    "respiratory compensation point": "respiratory_compensation_point",
    # Running economy
    "running economy": "running_economy",
    "movement economy": "movement_economy",
    "exercise economy": "exercise_economy",
    "economy of running": "running_economy",
    # Efficiency
    "gross efficiency": "gross_efficiency",
    "delta efficiency": "delta_efficiency",
    "net efficiency": "net_efficiency",
    "mechanical efficiency": "mechanical_efficiency",
    # Energy cost
    "oxygen cost": "oxygen_cost",
    "energy cost": "energy_cost",
    "metabolic cost": "metabolic_cost",
    "energetic cost": "energy_cost",
    # Anaerobic
    "anaerobic capacity": "anaerobic_capacity",
    "anaerobic power": "anaerobic_power",
    "anaerobic threshold": "anaerobic_threshold",
    "anaerobic speed reserve": "anaerobic_speed_reserve",
    "maximal anaerobic power": "anaerobic_power",
    # Aerobic
    "aerobic capacity": "aerobic_capacity",
    "aerobic power": "aerobic_power",
    "aerobic fitness": "aerobic_capacity",
    "maximal aerobic speed": "maximal_aerobic_speed",
    # Heart rate
    "heart rate": "heart_rate",
    "hr": "heart_rate",
    "maximal heart rate": "maximal_heart_rate",
    "hrmax": "maximal_heart_rate",
    "heart rate variability": "heart_rate_variability",
    "hrv": "heart_rate_variability",
    "heart rate recovery": "heart_rate_recovery",
    # Speed
    "sprint ability": "sprint_ability",
    "sprint performance": "sprint_ability",
    "sprint speed": "sprint_speed",
    "maximal sprint speed": "maximal_sprint_speed",
    "mss": "maximal_sprint_speed",
    "maximum speed": "maximum_speed",
    "acceleration": "acceleration",
    "acceleration capacity": "acceleration",
    "deceleration": "deceleration",
    "repeated sprint ability": "repeated_sprint_ability",
    "rsa": "repeated_sprint_ability",
    "change of direction": "change_of_direction",
    "cod": "change_of_direction",
    "agility": "agility",
    # Strength
    "maximal strength": "maximal_strength",
    "relative strength": "relative_strength",
    "force production": "force_production",
    "rate of force development": "rate_of_force_development",
    "rfd": "rate_of_force_development",
    "muscle strength": "muscle_strength",
    "muscular strength": "muscle_strength",
    # Power
    "power output": "power_output",
    "peak power": "peak_power",
    "mean power": "mean_power",
    "muscle power": "muscle_power",
    # Muscular endurance
    "muscular endurance": "muscular_endurance",
    "muscle endurance": "muscular_endurance",
    "fatigue resistance": "fatigue_resistance",
    # Neuromuscular
    "neuromuscular function": "neuromuscular_function",
    "neuromuscular efficiency": "neuromuscular_efficiency",
    # Stiffness
    "tendon stiffness": "tendon_stiffness",
    "muscle stiffness": "muscle_stiffness",
    "leg stiffness": "leg_stiffness",
    "vertical stiffness": "vertical_stiffness",
    # Critical power
    "critical power": "critical_power",
    "critical speed": "critical_speed",
    "critical velocity": "critical_velocity",
    # Buffering
    "buffering capacity": "buffering_capacity",
    # Endurance
    "endurance capacity": "endurance_capacity",
    "endurance performance": "endurance_performance",
    "time to exhaustion": "time_to_exhaustion",
    "time trial performance": "time_trial_performance",
    # Technical
    "stride length": "stride_length",
    "step length": "stride_length",
    "stride frequency": "stride_frequency",
    "step frequency": "stride_frequency",
    "cadence": "cadence",
    "ground contact time": "ground_contact_time",
    "gct": "ground_contact_time",
    "flight time": "flight_time",
    "running mechanics": "running_mechanics",
    "running technique": "running_mechanics",
    # Tactical
    "pacing strategy": "pacing_strategy",
    "pacing": "pacing_strategy",
    "race strategy": "race_strategy",
    "decision making": "decision_making",
    "game intelligence": "game_intelligence",
    # Biomechanics
    "kinematics": "kinematics",
    "kinetics": "kinetics",
    "ground reaction force": "ground_reaction_force",
    "grf": "ground_reaction_force",
    # Psychological
    "reaction time": "reaction_time",
    "anticipation": "anticipation",
    "anxiety": "anxiety",
    "competitive anxiety": "competitive_anxiety",
    "attention": "attention",
    "concentration": "concentration",
    "confidence": "confidence",
    "self-confidence": "self_confidence",
    "motivation": "motivation",
    "resilience": "resilience",
    "mental toughness": "mental_toughness",
    "mental fatigue": "mental_fatigue",
    # Nutritional
    "carbohydrate intake": "carbohydrate_intake",
    "protein intake": "protein_intake",
    "hydration": "hydration",
    "caffeine": "caffeine",
    "creatine": "creatine",
    "nitrate": "nitrate",
    "iron status": "iron_status",
    "body composition": "body_composition",
    "energy availability": "energy_availability",
    "glycogen": "glycogen",
    # Health
    "injury risk": "injury_risk",
    "injury incidence": "injury_incidence",
    "injury prevention": "injury_prevention",
    "training load": "training_load",
    "overtraining": "overtraining",
    "recovery": "recovery",
    "sleep": "sleep",
    "sleep quality": "sleep_quality",
    "soreness": "muscle_soreness",
    "muscle soreness": "muscle_soreness",
    "doms": "muscle_soreness",
    "fatigue": "fatigue",
    "pain": "pain",
    "asymmetry": "limb_asymmetry",
    "limb asymmetry": "limb_asymmetry",
    "range of motion": "range_of_motion",
    "rom": "range_of_motion",
    "flexibility": "flexibility",
    "mobility": "mobility",
    # Equipment
    "shoes": "footwear",
    "footwear": "footwear",
    "spikes": "footwear",
    "wearable device": "wearable_device",
    # Competition rules
    "scoring": "scoring_system",
    "scoring system": "scoring_system",
    "qualification": "qualification_criteria",
    "disqualification": "disqualification",
    "competition format": "competition_format",
    "ranking system": "ranking_system",
    "selection criteria": "selection_criteria",
}


def get_canonical_name(term: str) -> str:
    """Standardize a term to its canonical form. Returns the original if no mapping exists."""
    term_lower = term.strip().lower()
    return CANONICAL_NAMES.get(term_lower, term_lower.replace(" ", "_"))


def get_category_keywords(category_key: str) -> set[str]:
    """Get all keywords for a category."""
    return CATEGORY_KEYWORD_MAP.get(category_key, set())


def classify_term(term: str) -> str:
    """Classify a single term into its most likely category.

    Uses exact keyword matching. Returns 'other_uncertain' if no match.
    """
    term_lower = term.strip().lower()
    # Try exact match first (works for space-separated and canonical forms)
    for cat_key, keywords in CATEGORY_KEYWORD_MAP.items():
        if term_lower in keywords:
            return cat_key
    # Try with underscores → spaces (canonical names use underscores, keywords use spaces)
    term_spaces = term_lower.replace("_", " ")
    if term_spaces != term_lower:
        for cat_key, keywords in CATEGORY_KEYWORD_MAP.items():
            if term_spaces in keywords:
                return cat_key
    return "other_uncertain"


def get_all_keywords() -> dict[str, set[str]]:
    """Get all keywords across all categories."""
    return dict(CATEGORY_KEYWORD_MAP)


def get_category_name_cn(category_key: str) -> str:
    """Get Chinese name for a category."""
    cat = CATEGORIES.get(category_key, {})
    return cat.get("name_cn", category_key)


def get_category_name_en(category_key: str) -> str:
    """Get English name for a category."""
    cat = CATEGORIES.get(category_key, {})
    return cat.get("name_en", category_key)
