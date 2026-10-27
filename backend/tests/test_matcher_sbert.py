
import pytest

from backend.app.fusion import matcher


def test_compute_sbert_similarity_basic(monkeypatch):
    """SBERT cosine similarity 0.8 should map to 0.9."""
    class DummyModel:
        def encode(self, texts, convert_to_tensor=True):
            assert len(texts) == 2
            return ["embedding_1", "embedding_2"]

    class DummyUtil:
        @staticmethod
        def pytorch_cos_sim(a, b):
            class Score:
                def item(self):
                    return 0.8
            return Score()

    monkeypatch.setattr(matcher, "_sbert_model", DummyModel())
    monkeypatch.setattr(matcher, "util", DummyUtil)

    score = matcher.compute_sbert_similarity("pothole road", "road pothole")
    assert score == pytest.approx(0.9)


def test_compute_sbert_similarity_fallback_when_no_model(monkeypatch):
    """Jaccard similarity should be used when SBERT is unavailable."""
    monkeypatch.setattr(matcher, "_sbert_model", None)

    score = matcher.compute_sbert_similarity(
        "pothole damaged road",
        "pothole damaged road",
    )

    assert score == pytest.approx(1.0)


def test_candidate_pair_uses_sbert_when_available(monkeypatch):
    """CandidatePair should store the SBERT similarity in its text feature."""
    class DummyModel:
        def encode(self, texts, convert_to_tensor=True):
            assert len(texts) == 2
            return ["embedding_1", "embedding_2"]

    class DummyUtil:
        @staticmethod
        def pytorch_cos_sim(a, b):
            class Score:
                def item(self):
                    return 0.8
            return Score()

    monkeypatch.setattr(matcher, "_sbert_model", DummyModel())
    monkeypatch.setattr(matcher, "util", DummyUtil)

    bbmp = {
        "id": "BBMP-1",
        "category": "Road",
        "sub_category": "Pothole",
        "grievance_date": "2023-01-01T10:00:00Z",
        "ward_name": "Ward 1",
        "description": "Large pothole on Main Street",
    }

    btp = {
        "id": "BTP-1",
        "cause": "Road",
        "timestamp": "2023-01-01T11:00:00Z",
        "ward_name": "Ward 1",
        "latitude": 12.9716,
        "longitude": 77.5946,
        "description": "Pothole reported near Main Street",
    }

    pair = matcher.CandidatePair(bbmp, btp)

    assert pair.features["text"] == pytest.approx(0.9)
    assert "text" in pair.features
