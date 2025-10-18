from unittest.mock import patch

from alerts.insider_nvda import Alert
from flows.monitor_nvda_insider import monitor_nvda_insider


def test_monitor_flow_invokes_alert_evaluation():
    fake_alert = Alert(symbol="NVDA", severity="HIGH", payload={"ceo_filings": 1})
    with patch("flows.monitor_nvda_insider.evaluate_nvda_insider_alert", return_value=fake_alert) as mocked:
        result = monitor_nvda_insider()
    mocked.assert_called_once()
    assert result["payload"]["ceo_filings"] == 1
