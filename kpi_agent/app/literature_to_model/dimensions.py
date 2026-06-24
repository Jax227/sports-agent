"""
Default performance dimensions and domain-specific keyword dictionaries.

Each dimension includes:
  - Chinese/English names and descriptions
  - Alias terms for matching
  - Example determinants
  - A category-specific keyword set for rule-based classification
"""

from app.literature_to_model.schemas import PerformanceDimension


def load_default_performance_dimensions() -> list[PerformanceDimension]:
    """Return the 8 default performance dimensions for sports science."""

    return [
        PerformanceDimension(
            id="physiological_requirements",
            name_cn="生理要求",
            name_en="Physiological Requirements",
            description="Aerobic/anaerobic capacity, cardiovascular fitness, muscular strength, power, speed, endurance, and metabolic factors.",
            aliases=[
                "aerobic capacity", "vo2max", "maximal oxygen uptake", "vo2 max",
                "anaerobic capacity", "anaerobic power", "anaerobic threshold",
                "lactate threshold", "ventilatory threshold", "heart rate",
                "heart rate variability", "hrv", "cardiorespiratory",
                "cardiovascular", "respiratory", "oxygen transport",
                "maximal strength", "muscular strength", "relative strength",
                "force production", "rate of force development", "rfd",
                "power output", "peak power", "mean power", "muscle power",
                "sprint ability", "sprint speed", "maximum speed", "mss",
                "speed endurance", "acceleration", "running economy",
                "movement economy", "exercise economy", "oxygen cost",
                "energy cost", "metabolic cost", "running performance",
                "endurance", "endurance capacity", "endurance performance",
                "time trial", "time to exhaustion", "ttf",
                "fatigue resistance", "fatigue index", "repeated sprint ability",
                "muscle fiber type", "slow twitch", "fast twitch",
                "flexibility", "range of motion", "rom", "mobility",
                "blood lactate", "blood lactate concentration", "bla",
                "ventilatory equivalent", "ve/vo2", "ve/vco2",
                "exercise capacity", "physical capacity", "physical fitness",
                "metabolic profile", "substrate utilization", "fat oxidation",
                "glycogen", "phosphocreatine", "mitochondrial",
            ],
            examples=[
                "VO2max", "Lactate Threshold", "Running Economy",
                "Maximal Strength", "Power Output", "Sprint Speed",
                "Heart Rate Variability", "Anaerobic Capacity",
            ],
        ),

        PerformanceDimension(
            id="technical_requirements",
            name_cn="技术要求",
            name_en="Technical Requirements",
            description="Sport-specific technique, skill execution, biomechanics, kinematics, motor control, and movement efficiency.",
            aliases=[
                "biomechanics", "kinematics", "kinetics", "motor control",
                "technique", "skill", "skill level", "skill acquisition",
                "movement pattern", "movement quality", "movement efficiency",
                "stride length", "step length", "stride frequency", "cadence",
                "ground contact time", "gct", "contact time", "stance time",
                "flight time", "swing time", "stride parameters",
                "joint angle", "joint kinematics", "joint moment",
                "range of motion", "rom", "flexibility",
                "coordination", "neuromuscular", "proprioception",
                "balance", "postural control", "stability",
                "gait", "gait pattern", "gait analysis", "running mechanics",
                "running technique", "running form", "throwing mechanics",
                "jumping mechanics", "swimming technique", "stroke mechanics",
                "shooting technique", "passing accuracy", "dribbling",
                "foot placement", "landing mechanics",
                "center of mass", "com displacement", "vertical oscillation",
                "arm swing", "leg stiffness", "muscle activation pattern",
                "emg", "electromyography", "force plate",
                "movement screen", "fms", "movement competency",
                "motor learning", "skill retention", "transfer of learning",
            ],
            examples=[
                "Stride Length", "Stride Frequency", "Ground Contact Time",
                "Joint Kinematics", "Running Mechanics", "Balance Control",
            ],
        ),

        PerformanceDimension(
            id="tactical_requirements",
            name_cn="战术要求",
            name_en="Tactical Requirements",
            description="Decision making, strategy, pacing, positioning, tactical knowledge, game intelligence, and competition management.",
            aliases=[
                "tactics", "strategy", "tactical", "tactical behavior",
                "decision making", "decision speed", "decision accuracy",
                "game intelligence", "game reading", "game awareness",
                "situational awareness", "tactical knowledge",
                "pacing strategy", "pacing", "pacing pattern",
                "race strategy", "race tactics", "pacing profile",
                "positioning", "positional play", "spatial awareness",
                "match analysis", "performance analysis",
                "opponent analysis", "scouting",
                "game plan", "competition strategy", "race plan",
                "offensive", "defensive", "transition play",
                "team coordination", "team tactics", "formation",
                "playing style", "game model",
                "set piece", "set play", "restart",
                "time management", "energy management",
                "risk management", "risk taking",
                "anticipation", "pattern recognition",
                "adaptability", "tactical flexibility",
                "pressure management", "competition management",
                "tactical periodization",
            ],
            examples=[
                "Pacing Strategy", "Decision Making", "Positioning",
                "Game Intelligence", "Tactical Knowledge", "Race Strategy",
            ],
        ),

        PerformanceDimension(
            id="nutritional_requirements",
            name_cn="营养要求",
            name_en="Nutritional Requirements",
            description="Dietary intake, macronutrients, micronutrients, hydration, supplementation, body composition, and energy availability.",
            aliases=[
                "nutrition", "nutritional", "diet", "dietary",
                "macronutrient", "micronutrient", "carbohydrate",
                "protein", "fat", "lipid",
                "energy intake", "energy availability", "energy balance",
                "caloric intake", "caloric restriction",
                "hydration", "hydration status", "fluid intake",
                "dehydration", "rehydration", "electrolyte",
                "supplementation", "supplement", "ergogenic aid",
                "creatine", "caffeine", "beta alanine", "bicarbonate",
                "nitrate", "beetroot", "sodium bicarbonate",
                "body composition", "body fat", "body fat percentage",
                "lean body mass", "fat free mass", "body mass", "bmi",
                "weight management", "weight loss", "weight gain",
                "glycogen", "glycogen stores", "carbohydrate loading",
                "glycemic index", "glycemic response",
                "protein synthesis", "protein timing", "amino acid",
                "bcaa", "leucine", "whey protein",
                "vitamin d", "iron", "calcium", "magnesium", "zinc",
                "antioxidant", "omega 3", "fish oil",
                "meal timing", "nutrient timing", "post exercise nutrition",
                "recovery nutrition", "pre competition meal",
                "gut health", "microbiome", "gastrointestinal",
                "exercise induced", "red s", "relative energy deficiency",
                "metabolic rate", "resting metabolic rate", "rmr",
                "bone mineral density", "bmd",
            ],
            examples=[
                "Body Composition", "Hydration Status", "Energy Availability",
                "Carbohydrate Intake", "Protein Timing", "Supplementation",
            ],
        ),

        PerformanceDimension(
            id="psychological_skills",
            name_cn="心理技能",
            name_en="Psychological Skills",
            description="Cognitive abilities, perceptual skills, motivation, anxiety management, mental toughness, focus, and psychological wellbeing.",
            aliases=[
                "psychological", "mental", "cognitive", "perceptual",
                "psychology", "mental skills", "mental training",
                "motivation", "intrinsic motivation", "extrinsic motivation",
                "self determination", "self efficacy", "confidence",
                "anxiety", "competitive anxiety", "state anxiety",
                "trait anxiety", "stress", "stress management",
                "mental toughness", "resilience", "grit",
                "focus", "concentration", "attention",
                "attentional control", "attentional focus",
                "reaction time", "response time", "simple reaction time",
                "choice reaction time", "processing speed",
                "visual perception", "visual search", "visual attention",
                "anticipation", "anticipation skill", "prediction",
                "working memory", "executive function",
                "decision making", "cognitive load", "cognitive fatigue",
                "mood", "mood state", "affect", "emotion", "emotional regulation",
                "arousal", "arousal regulation", "activation",
                "self talk", "imagery", "mental imagery", "visualization",
                "goal setting", "goal orientation",
                "mindfulness", "meditation", "relaxation",
                "flow", "flow state", "clutch performance",
                "burnout", "overtraining", "staleness",
                "team cohesion", "team dynamics", "social support",
                "coach athlete relationship", "leadership",
                "personality", "perfectionism", "coping",
                "sleep quality", "sleep and mental health",
            ],
            examples=[
                "Reaction Time", "Decision Making Speed", "Mental Toughness",
                "Anxiety Management", "Attentional Focus", "Motivation",
            ],
        ),

        PerformanceDimension(
            id="equipment_characteristics",
            name_cn="器材特点",
            name_en="Equipment Characteristics",
            description="Sports equipment, footwear, clothing, protective gear, instruments, wearables, and technology affecting performance.",
            aliases=[
                "equipment", "gear", "apparel", "device", "technology",
                "footwear", "shoe", "running shoe", "cleat", "spike",
                "shoe stiffness", "shoe mass", "shoe comfort",
                "midsole", "carbon fiber plate", "carbon plate",
                "wearable", "wearable technology", "wearable device",
                "gps", "global positioning system", "accelerometer",
                "gyroscope", "inertial sensor", "imu",
                "heart rate monitor", "power meter",
                "lactate meter", "blood analyzer",
                "timing system", "timing gate", "photocell",
                "force plate", "force platform", "pressure sensor",
                "motion capture", "mocap", "video analysis",
                "dartfish", "kinovea", "video tracking",
                "drones", "aerial footage",
                "protective equipment", "helmet", "mouthguard",
                "padding", "brace", "tape", "kinesio tape",
                "clothing", "uniform", "kit", "compression garment",
                "swimsuit", "cycling suit", "aerodynamic suit",
                "racket", "bat", "club", "stick", "ball",
                "bicycle", "bike", "wheel", "frame", "chain",
                "ergometer", "treadmill", "cycle ergometer",
                "isokinetic", "dynamometer", "linear encoder",
                "altitude", "altitude training", "hypoxic",
                "environmental chamber", "heat chamber", "cold chamber",
                "recovery tool", "foam roller", "massage gun",
                "compression boot", "pneumatic compression",
                "vibration", "vibration training", "whole body vibration",
                "electrical stimulation", "nmes", "ems", "tens",
                "blood flow restriction", "bfr",
                "sensor", "iot", "internet of things",
            ],
            examples=[
                "Carbon Fiber Plate Shoes", "GPS Wearables", "Force Plates",
                "Motion Capture", "Compression Garments", "Altitude Training",
            ],
        ),

        PerformanceDimension(
            id="health",
            name_cn="健康",
            name_en="Health",
            description="Injury risk, injury prevention, recovery, training load management, illness, sleep, and overall athlete wellbeing.",
            aliases=[
                "health", "wellbeing", "wellness", "medical",
                "injury", "injury risk", "injury incidence", "injury rate",
                "injury prevention", "injury epidemiology", "injury burden",
                "injury mechanism", "injury surveillance",
                "overuse", "overuse injury", "acute injury", "chronic injury",
                "concussion", "head injury", "acl", "hamstring",
                "muscle strain", "ligament", "tendon", "tendinopathy",
                "stress fracture", "bone stress", "shin splint",
                "recovery", "recovery time", "recovery strategy",
                "active recovery", "passive recovery", "post exercise recovery",
                "training load", "internal load", "external load",
                "load management", "training stress", "acute chronic workload ratio",
                "acwr", "training load monitoring", "session rpe",
                "fatigue", "fatigue monitoring", "neuromuscular fatigue",
                "muscle damage", "muscle soreness", "doms",
                "creatine kinase", "ck", "inflammatory marker",
                "immune", "immune function", "immune system",
                "illness", "upper respiratory tract infection", "urti",
                "infection", "illness risk",
                "sleep", "sleep quality", "sleep duration", "sleep efficiency",
                "sleep deprivation", "sleep disorder", "insomnia",
                "circadian", "circadian rhythm", "chronotype",
                "jet lag", "travel fatigue",
                "overtraining", "overtraining syndrome", "non functional overreaching",
                "functional overreaching",
                "red s", "relative energy deficiency in sport",
                "female athlete triad", "menstrual", "amenorrhea",
                "bone health", "bone mineral density", "osteoporosis",
                "concussion protocol", "return to play", "return to sport",
                "rehabilitation", "rehab", "physiotherapy", "physical therapy",
                "prehabilitation", "prehab", "injury screening",
                "pre participation", "medical screening",
                "pain", "pain management", "pain perception",
                "thermoregulation", "heat illness", "heat stroke",
                "hypothermia", "hyperthermia", "cold injury",
                "hydration and health", "exertional heat illness",
            ],
            examples=[
                "Injury Risk", "Training Load", "Sleep Quality",
                "Recovery", "Overtraining Syndrome", "Concussion",
            ],
        ),

        PerformanceDimension(
            id="competition_rules",
            name_cn="比赛规则",
            name_en="Competition Rules",
            description="Rules, regulations, scoring systems, judging criteria, qualification standards, competition formats, and anti-doping.",
            aliases=[
                "competition", "rules", "regulation", "governing body",
                "federation", "world athletics", "world aquatics",
                "fifa", "uci", "ioc", "wada", "international federation",
                "scoring", "scoring system", "point system", "judging",
                "judging criteria", "referee", "umpire", "official",
                "disqualification", "penalty", "sanction", "violation",
                "rule change", "rule modification", "regulation update",
                "qualification", "qualifying standard", "qualifying time",
                "olympic standard", "entry standard",
                "competition format", "round", "heat", "semi final", "final",
                "elimination", "knockout", "group stage", "playoff",
                "ranking", "ranking system", "world ranking",
                "eligibility", "eligibility criteria", "age category",
                "weight class", "weight category", "classification",
                "para sport", "disability classification",
                "anti doping", "doping", "doping control",
                "prohibited substance", "banned substance",
                "therapeutic use exemption", "tue",
                "whereabouts", "biological passport",
                "equipment regulation", "equipment rule",
                "technology doping", "technological fraud",
                "fair play", "code of conduct", "ethics",
                "competition calendar", "season structure",
                "time rule", "false start", "lane violation",
                "sport specific rules", "event rules",
                "technical delegate", "competition jury",
                "protest", "appeal", "var", "video assistant referee",
                "hawk eye", "goal line technology", "electronic judging",
                "timing", "photo finish", "transponder", "chip timing",
                "competition integrity", "match fixing", "corruption",
                "safeguarding", "child protection", "welfare",
                "gender eligibility", "transgender policy",
                "prize money", "appearance fee", "sponsorship",
            ],
            examples=[
                "Qualification Standards", "Anti-Doping Rules", "Scoring System",
                "Competition Format", "Equipment Regulations", "Eligibility Criteria",
            ],
        ),
    ]


def build_domain_dictionary() -> dict[str, list[str]]:
    """Build a flat dimension_id → keyword_list lookup for rule matching.

    Returns a dict mapping each dimension id to its list of alias keywords,
    suitable for use in rule-based classification.
    """
    dimensions = load_default_performance_dimensions()
    return {d.id: d.aliases for d in dimensions}


def build_inverted_index() -> dict[str, list[str]]:
    """Build a keyword → [dimension_ids] inverted index for fast lookup.

    A keyword may map to multiple dimensions (e.g. 'range of motion'
    appears in both physiological_requirements and technical_requirements).
    """
    inverted: dict[str, list[str]] = {}
    for dim in load_default_performance_dimensions():
        for alias in dim.aliases:
            key = alias.lower().strip()
            if key not in inverted:
                inverted[key] = []
            if dim.id not in inverted[key]:
                inverted[key].append(dim.id)
    return inverted
