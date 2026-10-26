"""
LOCALYN Gold Set Annotated Benchmark Dataset

Stratified human-grounded candidate pairs across:
- positive: Ground-truth corroborating same real-world civic incident
- negative: Different events (disjoint wards, divergent dates, incompatible categories)
- hard_negative: Same ward and date, but incompatible civic issues or contradictory resolutions
- uncertain: Insufficient evidence / vague boundaries
"""

from typing import List, Dict, Any

GOLD_SET_PAIRS: List[Dict[str, Any]] = [
    # 1. STRONG POSITIVE - Direct Pothole Match in Bellandur ORR
    {
        "id": "GOLD-001",
        "ground_truth": "positive",
        "notes": "Direct pothole grievance and BTP telemetry on Outer Ring Road, Bellandur",
        "bbmp": {
            "complaint_id": "BBMP-2024-7721",
            "category": "Road Maintenance(Engg)",
            "sub_category": "Potholes",
            "grievance_date": "2024-06-18 09:30:00",
            "ward_name": "150 - Bellandur",
            "staff_remarks": "Inspected deep crater pothole near Bellandur EcoSpace flyover descending ramp. Asphalt mix requested."
        },
        "btp": {
            "event_id": "BTP-2024-4109",
            "cause": "pot_holes",
            "timestamp": "2024-06-18 10:15:00",
            "latitude": 12.9280,
            "longitude": 77.6830,  # inside Bellandur polygon
            "location_name": "Outer Ring Road near Bellandur EcoSpace",
            "title": "Severe Slow Traffic Due to Pothole",
            "description": "Traffic movement dead slow towards Marathahalli due to large pothole after flyover."
        }
    },
    # 2. STRONG POSITIVE - Direct Waterlogging in Koramangala
    {
        "id": "GOLD-002",
        "ground_truth": "positive",
        "notes": "Severe monsoon waterlogging at Koramangala 4th Block",
        "bbmp": {
            "complaint_id": "BBMP-2024-8114",
            "category": "Projects Central",
            "sub_category": "Stagnation of water on road/ Water logging",
            "grievance_date": "2024-05-22 17:00:00",
            "ward_name": "151 - Koramangala",
            "staff_remarks": "Heavy runoff inundation near 80ft Road 4th block. Emergency motor deployed."
        },
        "btp": {
            "event_id": "BTP-2024-5201",
            "cause": "water_logging",
            "timestamp": "2024-05-22 18:30:00",
            "latitude": 12.9340,
            "longitude": 77.6250,  # inside Koramangala polygon
            "location_name": "80 Feet Road Koramangala 4th Block",
            "title": "Waterlogging Alert",
            "description": "Koramangala 80ft road waterlogging. Two wheelers stranded, traffic diverted."
        }
    },
    # 3. MEDIUM POSITIVE - Tree Fall / Branch Obstruction in Indiranagar
    {
        "id": "GOLD-003",
        "ground_truth": "positive",
        "notes": "Fallen tree blocking 100ft road Indiranagar",
        "bbmp": {
            "complaint_id": "BBMP-2024-9043",
            "category": "Forest",
            "sub_category": "Removal of dead/fallen trees",
            "grievance_date": "2024-07-02 14:10:00",
            "ward_name": "89 - Indiranagar",
            "staff_remarks": "Gulmohar tree uprooted across carriage way near 12th main junction. Tree squad operating saw."
        },
        "btp": {
            "event_id": "BTP-2024-6012",
            "cause": "tree_fall",
            "timestamp": "2024-07-02 14:45:00",
            "latitude": 12.9710,
            "longitude": 77.6410,  # inside Indiranagar polygon
            "location_name": "100 Feet Road Indiranagar",
            "title": "Road Blocked by Fallen Tree",
            "description": "Big tree fallen on 100ft road near 12th main signal. Traffic blocked towards CMH road."
        }
    },
    # 4. MEDIUM POSITIVE - Road Digging / Construction Obstruction in HSR Layout
    {
        "id": "GOLD-004",
        "ground_truth": "positive",
        "notes": "Unauthorized OFC digging blocking traffic in HSR Sector 2",
        "bbmp": {
            "complaint_id": "BBMP-2024-3420",
            "category": "Optical Fiber Cables (OFC)",
            "sub_category": "Without permission digging of road",
            "grievance_date": "2024-08-11 11:00:00",
            "ward_name": "174 - HSR Layout",
            "staff_remarks": "Unauthorised trenching along 27th Main HSR Sector 2. Notice served to agency."
        },
        "btp": {
            "event_id": "BTP-2024-8140",
            "cause": "construction",
            "timestamp": "2024-08-11 12:00:00",
            "latitude": 12.9120,
            "longitude": 77.6390,  # inside HSR Layout polygon
            "location_name": "27th Main HSR Layout Sector 2",
            "title": "Slow Moving Traffic due to Road Digging",
            "description": "Trenching on road shoulder causing vehicle bottleneck at 27th Main junction."
        }
    },
    # 5. HARD NEGATIVE - Same Ward, Same Category, but Temporal Mismatch (12 Days Apart)
    {
        "id": "GOLD-005",
        "ground_truth": "negative",
        "notes": "Different incidents separated by 12 days in Bellandur",
        "bbmp": {
            "complaint_id": "BBMP-2024-1102",
            "category": "Road Maintenance(Engg)",
            "sub_category": "Potholes",
            "grievance_date": "2024-04-01 10:00:00",
            "ward_name": "150 - Bellandur",
            "staff_remarks": "Old pothole patch completed on April 2nd."
        },
        "btp": {
            "event_id": "BTP-2024-1944",
            "cause": "pot_holes",
            "timestamp": "2024-04-13 18:00:00",  # 12 days later
            "latitude": 12.9300,
            "longitude": 77.6800,
            "location_name": "Bellandur Junction",
            "title": "Fresh Pothole Formed",
            "description": "New pothole formed after overnight rain."
        }
    },
    # 6. HARD NEGATIVE - Same Ward, Same Date, but Incompatible Excluded Category
    {
        "id": "GOLD-006",
        "ground_truth": "negative",
        "notes": "Streetlight failure vs Traffic Congestion in Jayanagar (Excluded Crosswalk)",
        "bbmp": {
            "complaint_id": "BBMP-2024-4091",
            "category": "Electrical",
            "sub_category": "Street Light Not Working",
            "grievance_date": "2024-05-10 20:00:00",
            "ward_name": "177 - Jayanagar",
            "staff_remarks": "Phase bulb replaced at 4th T Block."
        },
        "btp": {
            "event_id": "BTP-2024-3380",
            "cause": "pot_holes",
            "timestamp": "2024-05-10 20:15:00",
            "latitude": 12.9300,
            "longitude": 77.5850,
            "location_name": "Jayanagar 4th Block",
            "title": "Traffic Congestion",
            "description": "Vehicle jam at 4th Block bus stand."
        }
    },
    # 7. NEGATIVE - Same Date, Same Category, but Completely Disjoint Wards
    {
        "id": "GOLD-007",
        "ground_truth": "negative",
        "notes": "Potholes on same day in Hebbal vs Bommanahalli (25 km apart)",
        "bbmp": {
            "complaint_id": "BBMP-2024-5501",
            "category": "Road Maintenance(Engg)",
            "sub_category": "Potholes",
            "grievance_date": "2024-09-05 10:00:00",
            "ward_name": "7 - Hebbal",
            "staff_remarks": "Hebbal flyover ramp pothole reported."
        },
        "btp": {
            "event_id": "BTP-2024-9102",
            "cause": "pot_holes",
            "timestamp": "2024-09-05 10:30:00",
            "latitude": 12.9020,
            "longitude": 77.6210,  # In Bommanahalli!
            "location_name": "Bommanahalli Junction",
            "title": "Pothole Congestion",
            "description": "Slow traffic near Bommanahalli signal."
        }
    },
    # 8. HARD NEGATIVE - Same Ward & Date, but Contradictory Resolution / False Report
    {
        "id": "GOLD-008",
        "ground_truth": "negative",
        "notes": "BBMP staff verified no tree fall occurred; BTP had waterlogging issue",
        "bbmp": {
            "complaint_id": "BBMP-2024-6019",
            "category": "Forest",
            "sub_category": "Issues related Snakes/Birds/Monkeys",
            "grievance_date": "2024-07-15 11:00:00",
            "ward_name": "89 - Indiranagar",
            "staff_remarks": "Wild monkey rescue call transferred to BBMP Wildlife warden. No civic road blockage."
        },
        "btp": {
            "event_id": "BTP-2024-7033",
            "cause": "tree_fall",
            "timestamp": "2024-07-15 11:45:00",
            "latitude": 12.9710,
            "longitude": 77.6410,
            "location_name": "100 Feet Road Indiranagar",
            "title": "Tree Branch on Footpath",
            "description": "Small branch clearance."
        }
    },
    # 9. POSITIVE - Heavy Rain Waterlogging in Hebbal
    {
        "id": "GOLD-009",
        "ground_truth": "positive",
        "notes": "Underpass inundation at Hebbal",
        "bbmp": {
            "complaint_id": "BBMP-2024-8840",
            "category": "Road Maintenance(Engg)",
            "sub_category": "water stagnation",
            "grievance_date": "2024-06-02 16:30:00",
            "ward_name": "7 - Hebbal",
            "staff_remarks": "Hebbal underpass waterlogging 3 feet deep. Motor suction underway."
        },
        "btp": {
            "event_id": "BTP-2024-6991",
            "cause": "water_logging",
            "timestamp": "2024-06-02 17:00:00",
            "latitude": 13.0350,
            "longitude": 77.5970,  # inside Hebbal polygon
            "location_name": "Hebbal Underpass towards Airport Road",
            "title": "Underpass Inundated",
            "description": "Severe water stagnation at Hebbal underpass. Airport bound traffic diverted to flyover."
        }
    },
    # 10. UNCERTAIN - Coarse timestamps with generic description
    {
        "id": "GOLD-010",
        "ground_truth": "uncertain",
        "notes": "General road debris complaint with delayed traffic telemetry",
        "bbmp": {
            "complaint_id": "BBMP-2024-2190",
            "category": "Road Maintenance(Engg)",
            "sub_category": "Debris Removal / Construction Material",
            "grievance_date": "2024-03-12 08:00:00",
            "ward_name": "112 - Domlur",
            "staff_remarks": "Construction debris piled on sidewalk."
        },
        "btp": {
            "event_id": "BTP-2024-3021",
            "cause": "construction",
            "timestamp": "2024-03-13 22:00:00",  # 38 hours later
            "latitude": 12.9600,
            "longitude": 77.6380,
            "location_name": "Domlur Intermediate Ring Road",
            "title": "Minor Congestion",
            "description": "Slow movement near Domlur flyover."
        }
    }
]


def get_gold_set() -> List[Dict[str, Any]]:
    return GOLD_SET_PAIRS
