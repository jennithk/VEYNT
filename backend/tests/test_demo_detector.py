from app.services.demo_detector import DemoVoiceDetector


def test_demo_detector_returns_probability_and_labeling():
    detector = DemoVoiceDetector()
    result = detector.analyze({"synthetic_score": 0.91})

    assert result["detector"] == "demo_only"
    assert result["ai_generated_probability"] == 91.0
    assert "demo_only" in result["confidence"].lower()
    assert isinstance(result["explanations"], list)
