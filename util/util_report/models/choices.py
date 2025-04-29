PRODUCT_CHOICES = [
    ('Hyperion Planning', 'Hyperion Planning'), 
    ('ARM', 'ARM'),
    ('HFM', 'HFM'),
    ('DRM', 'DRM'),
    ('EPBCS - Capex', 'EPBCS - Capex'),
    ('EPBCS- WF', 'EPBCS- WF'),
    ('EPBCS - Project', 'EPBCS - Project'),
    ('EPBCS -Finance', 'EPBCS -Finance'),
    ('Strategic Work Force Planning (SWP)', 'Strategic Work Force Planning (SWP)'),
    ('Strategic Modelling (SM)', 'Strategic Modelling (SM)'),
    ('Predictive Cash Forecasting (PCF)', 'Predictive Cash Forecasting (PCF)'),
    ('Predictive Planning (PP)', 'Predictive Planning (PP)'),
    ('FCCS', 'FCCS'),
    ('ARCS - RC', 'ARCS - RC'),
    ('ARCS - TM', 'ARCS - TM'),
    ('TRCS', 'TRCS'),
    ('PCMCS', 'PCMCS'),
    ('EDMCS', 'EDMCS'),
    ('Narrative Reporting (NR)', 'Narrative Reporting (NR)'),
    ('Management Reporting (MR)', 'Management Reporting (MR)'),
    ('FDMEE', 'FDMEE'),
    ('Data Management (DM)', 'Data Management (DM)'),
]

ROLE_CHOICES = [
    ('Developer', 'Developer'),
    ('Architect', 'Architect'),
    ('Project Manager', 'Project Manager'),
    ('Business Analyst', 'Business Analyst'),
    ('Technical Lead', 'Technical Lead')
]

SKILL_LEVEL_CHOICES = [
    (1, 'Beginner'),
    (2, 'Intermediate'),
    (3, 'Expert')
]

BILLING_CHOICES = [
    ('Full-Time', 'Full-Time'),
    ('Part-Time', 'Part-Time')
]

RESOURCE_STATUS_CHOICES = [
    ('Active', 'Active'),
    ('Inactive', 'Inactive'),
    ("To-join", "To-join"),
    ("On-leave", "On-leave")
]

ALLOCATION_STATUS_CHOICES = [
    ("On Bench", "On Bench"),
    ("On Project-Full Time", "On Project-Full Time"),
    ("On Project-Part Time", "On Project-Part Time"),
    ("Blocked", "Blocked")  
]

LOCATION_CHOICES = [
    ("Bangalore", "Bangalore"),
    ("Hyderabad", "Hyderabad"),
    ("Chennai", "Chennai")
]

REQUIREMENT_TYPE_CHOICES = [
    ("Internal", "Internal"),
    ("New", "New"),
    ("Replacement", "Replacement"),
    ("CR", "CR")
] 

REGION_CHOICES = [
("ACS", "ACS"),
("ANZ", "ANZ"),
("APAC", "APAC"),
("EMEA", "EMEA"),
("ASEAN", "ASEAN"),
("India", "India"),
("LAD", "LAD"),
("NAC", "NAC")
]

CLUSTER_CHOICES = [
    ("ACS", "ACS"),
    ("ANZ", "ANZ"),
    ("ASEAN + Japan + Hongkong", "ASEAN + Japan + Hongkong"),
    ("CSN", "CSN"),
    ("CSS", "CSS"),
    ("ESG", "ESG"),
    ("Europe + Greece + Israel", "Europe + Greece + Israel"),
    ("India North", "India North"),
    ("India South", "India South"),
    ("India West", "India West"),
    ("MEO", "MEO"),
    ("NAC + LAD", "NAC + LAD"),
    ("NetSuite", "NetSuite"),
    ("Saudi + Sub Sahara", "Saudi + Sub Sahara"),
    ("Sub Sahara", "Sub Sahara"),
    ("UK + IL", "UK + IL")
]

INDUSTRY_CHOICES = [
    ("Banking", "Banking"),
    ("Insurance", "Insurance"),
    ("Retail", "Retail"),
    ("Manufacturing", "Manufacturing"),
    ("Other", "Other")
]

PROJECT_STATUS_CHOICES = [
    ("Yet to Start", "Yet to Start"),
    ("Active", "Active"),
    ("Closed", "Closed"),
    ("On-hold", "On-hold"),
    ("Dropped", "Dropped")
]
