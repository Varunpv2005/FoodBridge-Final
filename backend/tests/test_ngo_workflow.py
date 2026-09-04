import unittest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models_db import Donation, DonationStatus, ExperimentRecord, NGORequest, Role, User
from app.services.evaluation import results_snapshot
from app.services.ngo_requests import advance_request, create_request_queue, request_state


class NgoWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(self.engine)
        self.session = sessionmaker(bind=self.engine)()
        self.donor = User(email="donor@test", hashed_password="x", role=Role.donor, name="Donor")
        self.first = User(email="first@test", hashed_password="x", role=Role.ngo, name="First NGO", lat=12.30, lng=76.65)
        self.second = User(email="second@test", hashed_password="x", role=Role.ngo, name="Second NGO", lat=12.31, lng=76.66)
        self.session.add_all([self.donor, self.first, self.second])
        self.session.flush()
        self.donation = Donation(
            donor_id=self.donor.id, food_type="rice", quantity_plates=20,
            pickup_lat=12.30, pickup_lng=76.64, quality_confidence=0.9,
        )
        self.session.add(self.donation)
        self.session.flush()

    def tearDown(self):
        self.session.close()
        self.engine.dispose()

    def candidate(self, ngo, rank):
        return {
            "ngo_id": ngo.id, "ngo_name": ngo.name, "probability": 0.9 - rank * 0.1,
            "distance_km": float(rank), "shap": {}, "factors": {},
            "reason": f"Candidate {ngo.name}", "explanation": ["Capacity and distance considered."],
        }

    def test_queue_requests_best_candidate_without_delivery(self):
        with patch("app.services.ngo_requests.rank_ngo_candidates", return_value=[
            self.candidate(self.first, 0), self.candidate(self.second, 1)
        ]):
            requests = create_request_queue(self.session, self.donation, [self.first, self.second])

        self.assertEqual(len(requests), 2)
        self.assertEqual(self.donation.status, DonationStatus.matched)
        self.assertEqual(self.donation.matched_ngo_id, self.first.id)
        self.assertEqual(requests[0].status, "pending")
        self.assertEqual(requests[1].status, "queued")
        self.assertEqual(self.session.query(NGORequest).count(), 2)
        self.assertEqual(self.donation.delivery_id if hasattr(self.donation, "delivery_id") else None, None)

    def test_rejection_advances_to_next_candidate(self):
        with patch("app.services.ngo_requests.rank_ngo_candidates", return_value=[
            self.candidate(self.first, 0), self.candidate(self.second, 1)
        ]):
            requests = create_request_queue(self.session, self.donation, [self.first, self.second])
        next_request = advance_request(self.session, self.donation, requests[0])

        self.assertIs(next_request, requests[1])
        self.assertEqual(requests[0].status, "rejected")
        self.assertEqual(requests[1].status, "pending")
        self.assertEqual(self.donation.matched_ngo_id, self.second.id)
        status, history = request_state(self.session, self.donation)
        self.assertEqual(status, "pending")
        self.assertEqual([item["status"] for item in history], ["rejected", "pending"])

    def test_all_rejections_leave_donation_unassigned(self):
        with patch("app.services.ngo_requests.rank_ngo_candidates", return_value=[
            self.candidate(self.first, 0), self.candidate(self.second, 1)
        ]):
            requests = create_request_queue(self.session, self.donation, [self.first, self.second])
        advance_request(self.session, self.donation, requests[0])
        self.assertIsNone(advance_request(self.session, self.donation, requests[1]))

        self.assertEqual(self.donation.status, DonationStatus.pending_match)
        self.assertIsNone(self.donation.matched_ngo_id)
        self.assertEqual([request.status for request in requests], ["rejected", "rejected"])

    def test_operational_record_is_excluded_from_controlled_sample(self):
        self.session.add(ExperimentRecord(donation_id=self.donation.id, started_at=self.donation.created_at))
        self.session.commit()
        snapshot = results_snapshot(self.session)
        self.assertEqual(snapshot["sample_size"], 0)
        self.assertEqual(snapshot["operational_data"]["record_count"], 1)
        self.assertIsNone(snapshot["end_to_end"]["success_rate"])


if __name__ == "__main__":
    unittest.main()
