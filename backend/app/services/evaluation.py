from datetime import datetime
from statistics import mean, median, stdev

from app.models_db import Delivery, DeliveryStop, Donation, ExperimentRecord, LocationPing, NGORequest


def ensure_experiment(db, donation, started_at=None, controlled=False):
    record = db.query(ExperimentRecord).filter(ExperimentRecord.donation_id == donation.id).first()
    if record:
        if controlled and not record.is_controlled_trial:
            record.is_controlled_trial = True
            record.trial_id = record.trial_id or f"FB-EXP-{record.id[:8].upper()}"
        return record
    record = ExperimentRecord(
        donation_id=donation.id,
        started_at=started_at or donation.created_at or datetime.utcnow(),
        realtime_measurements_ms=[],
        is_controlled_trial=controlled,
    )
    db.add(record)
    db.flush()
    if controlled:
        record.trial_id = f"FB-EXP-{record.id[:8].upper()}"
    return record


def sync_experiment(db, donation, ended_at=None):
    record = ensure_experiment(db, donation)
    requests = db.query(NGORequest).filter(NGORequest.donation_id == donation.id).all()
    record.ngo_request_count = len(requests)
    record.ngo_rejection_count = sum(request.status == "rejected" for request in requests)
    record.fallback_count = max(0, record.ngo_rejection_count)
    record.accepted_ngo_id = donation.matched_ngo_id if donation.status.value in {"ngo_accepted", "assigned_volunteer", "picked_up", "delivered"} else None
    delivery_stop = db.query(DeliveryStop).filter(DeliveryStop.donation_id == donation.id).first()
    delivery = db.query(Delivery).filter(Delivery.id == delivery_stop.delivery_id).first() if delivery_stop else None
    if delivery:
        record.volunteer_id = delivery.volunteer_id
        record.assignment_at = record.assignment_at or delivery.created_at
        record.route_distance_km = delivery.total_distance_km
        record.route_duration_minutes = delivery.estimated_travel_minutes
        record.gps_update_count = db.query(LocationPing).filter(LocationPing.delivery_id == delivery.id).count()
        if delivery.completed_at:
            record.completion_at = delivery.completed_at
            record.ended_at = ended_at or delivery.completed_at
            record.outcome = "successful" if donation.status.value == "delivered" else record.outcome
        record.arrival_at = record.arrival_at or next((item.arrived_at for item in delivery.stops if item.arrived_at), None)
    if donation.status.value in {"rejected_quality", "expired"}:
        record.outcome = "incomplete"
        record.ended_at = ended_at or datetime.utcnow()
    elif donation.status.value == "pending_match" and not requests:
        record.outcome = "incomplete"
        record.ended_at = ended_at or datetime.utcnow()
    db.add(record)
    return record


def record_location(db, delivery, timestamp):
    donation_ids = [stop.donation_id for stop in delivery.stops]
    for donation_id in donation_ids:
        donation = db.query(Donation).filter(Donation.id == donation_id).first()
        if not donation:
            continue
        record = ensure_experiment(db, donation)
        record.gps_update_count = (record.gps_update_count or 0) + 1
        if timestamp:
            now = datetime.utcnow()
            try:
                latency = max(0.0, (now - timestamp.replace(tzinfo=None)).total_seconds() * 1000)
                values = list(record.realtime_measurements_ms or [])
                values.append(round(latency, 3))
                record.realtime_measurements_ms = values[-100:]
            except (TypeError, ValueError):
                pass
        db.add(record)


def _summary(values):
    if not values:
        return {"average": None, "minimum": None, "maximum": None, "median": None, "standard_deviation": None, "sample_size": 0}
    return {
        "average": round(mean(values), 3), "minimum": round(min(values), 3),
        "maximum": round(max(values), 3), "median": round(median(values), 3),
        "standard_deviation": round(stdev(values), 3) if len(values) > 1 else None,
        "sample_size": len(values),
    }


def results_snapshot(db):
    records = db.query(ExperimentRecord).filter(ExperimentRecord.experiment_type == "foodbridge").order_by(ExperimentRecord.started_at).all()
    operational_records = [record for record in records if not record.is_controlled_trial]
    valid_records = [record for record in records if record.is_controlled_trial and record.outcome != "invalid"]
    completed = [record for record in valid_records if record.outcome == "successful" or record.completion_at]
    accepted = [record for record in valid_records if record.accepted_ngo_id]
    requests = sum(record.ngo_request_count or 0 for record in valid_records)
    rejections = sum(record.ngo_rejection_count or 0 for record in valid_records)
    fallback_success = [record for record in completed if (record.fallback_count or 0) > 0]
    distances = [record.route_distance_km for record in valid_records if record.route_distance_km is not None]
    durations = [record.route_duration_minutes for record in valid_records if record.route_duration_minutes is not None]
    latencies = [value for record in valid_records for value in (record.realtime_measurements_ms or [])]
    assignment_times = [record.assignment_processing_ms for record in valid_records if record.assignment_processing_ms is not None]
    baselines = db.query(ExperimentRecord).filter(ExperimentRecord.experiment_type == "baseline").all()
    return {
        "experiment_period": {"start": valid_records[0].started_at.isoformat() if valid_records else None, "end": valid_records[-1].ended_at.isoformat() if valid_records and valid_records[-1].ended_at else None},
        "sample_size": len(valid_records),
        "operational_data": {"record_count": len(operational_records), "message": "Operational/demo data is excluded from controlled trial metrics."},
        "end_to_end": {"total_experiments": len(valid_records), "successful_redistributions": len(completed), "incomplete": len(valid_records) - len(completed), "success_rate": round(len(completed) / len(valid_records) * 100, 2) if valid_records else None},
        "ngo_matching": {"initial_requests": len([record for record in valid_records if record.ngo_request_count]), "requests": requests, "acceptances": len(accepted), "rejections": rejections, "fallback_attempts": sum((record.fallback_count or 0) for record in valid_records), "fallback_success": len(fallback_success), "acceptance_rate": round(len(accepted) / requests * 100, 2) if requests else None, "fallback_success_rate": round(len(fallback_success) / sum((record.fallback_count or 0) for record in valid_records) * 100, 2) if sum((record.fallback_count or 0) for record in valid_records) else None},
        "volunteer_allocation": {"assignment_successes": len([record for record in valid_records if record.volunteer_id]), "assignment_success_rate": round(len([record for record in valid_records if record.volunteer_id]) / len(accepted) * 100, 2) if accepted else None, "travel_distance_km": _summary(distances), "travel_duration_minutes": _summary(durations), "assignment_processing_ms": _summary(assignment_times)},
        "realtime_tracking": _summary(latencies),
        "delivery_performance": {"completed_deliveries": len(completed), "route_distance_km": _summary(distances), "delivery_duration_minutes": _summary(durations), "completion_rate": round(len(completed) / len(valid_records) * 100, 2) if valid_records else None, "route_deviation_events": None},
        "system_performance": {"donation_creation_ms": _summary([record.donation_creation_ms for record in valid_records if record.donation_creation_ms is not None]), "assignment_processing_ms": _summary(assignment_times)},
        "baseline": {"available": bool(baselines), "message": "Baseline experiment recorded." if baselines else "Baseline experiment not recorded.", "sample_size": len(baselines), "success_rate": round(sum(record.outcome == "successful" for record in baselines) / len(baselines) * 100, 2) if baselines else None},
        "recent_experiments": [{"id": record.trial_id or record.id, "donation_id": record.donation_id, "outcome": record.outcome or "in progress", "ngo_request_count": record.ngo_request_count, "fallback_count": record.fallback_count, "route_distance_km": record.route_distance_km, "gps_update_count": record.gps_update_count, "started_at": record.started_at.isoformat()} for record in valid_records[-10:][::-1]],
    }