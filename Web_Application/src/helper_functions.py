from datetime import datetime
from pymongo import MongoClient

def get_hourly_viewing_data(viewing_collection):
    pipeline = [
        {"$group": {
            "_id": {
                "exhibit_id": "$exhibit_id",
                "hour": {"$hour": "$timestamp"},
                "day": {"$dayOfMonth": "$timestamp"},
                "month": {"$month": "$timestamp"},
                "year": {"$year": "$timestamp"}
            },
            "count": {"$sum": 1}
        }},
        {"$sort": {"_id.exhibit_id": 1, "_id.year": 1, "_id.month": 1, "_id.day": 1, "_id.hour": 1}}
    ]

    data = list(viewing_collection.aggregate(pipeline))

    total_detections_per_hour = {}
    total_detections = {}

    for entry in data:
        exhibit_id = entry["_id"]["exhibit_id"]
        hour = entry["_id"]["hour"]
        count = entry["count"]

        if exhibit_id not in total_detections_per_hour:
            total_detections_per_hour[exhibit_id] = [0] * 24

        total_detections_per_hour[exhibit_id][hour] += count

    total_viewing_percentage = {}
    for exhibit_id, hourly_counts in total_detections_per_hour.items():
        hourly_percentages = [hourly_count / 7200 * 100 for hourly_count in hourly_counts]
        total_viewing_percentage[exhibit_id] = hourly_percentages

    return total_viewing_percentage
