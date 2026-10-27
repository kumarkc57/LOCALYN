import builtins
from unittest.mock import patch

from backend.app.chef.calculator import compute_dempster_chef

def test_compute_dempster_chef_all_perfect():
    with patch('backend.app.chef.calculator.calculate_source_reliability', return_value=1.0), \
         patch('backend.app.chef.calculator.calculate_temporal_consistency', return_value=1.0), \
         patch('backend.app.chef.calculator.calculate_corroboration', return_value=1.0):
        result = compute_dempster_chef('any', 'news', '2023-01-01T00:00:00Z')
        assert result['confidence'] == 1.0
        assert result['confidence_tier'] == 'HIGH'

def test_compute_dempster_chef_conflict():
    # High source reliability, low temporal and corroboration
    with patch('backend.app.chef.calculator.calculate_source_reliability', return_value=1.0), \
         patch('backend.app.chef.calculator.calculate_temporal_consistency', return_value=0.0), \
         patch('backend.app.chef.calculator.calculate_corroboration', return_value=0.0):
        result = compute_dempster_chef('any', 'news', '2023-01-01T00:00:00Z')
        # Expect confidence less than 0.5 due to conflicting evidence
        assert 0.0 <= result['confidence'] < 0.5
        assert result['confidence_tier'] == 'LOW'

def test_compute_dempster_chef_all_zero():
    with patch('backend.app.chef.calculator.calculate_source_reliability', return_value=0.0), \
         patch('backend.app.chef.calculator.calculate_temporal_consistency', return_value=0.0), \
         patch('backend.app.chef.calculator.calculate_corroboration', return_value=0.0):
        result = compute_dempster_chef('any', 'news', '2023-01-01T00:00:00Z')
        assert result['confidence'] == 0.0
        assert result['confidence_tier'] == 'LOW'
