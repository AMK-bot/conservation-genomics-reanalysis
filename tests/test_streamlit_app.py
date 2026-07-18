"""Runtime smoke tests for the read-only Fragility Explorer.

These tests execute the Streamlit script with its tracked deploy artifacts. They do not
start a server or run bioinformatics; their purpose is to catch missing files, schema
drift, and widget-state errors before deployment.
"""

from pathlib import Path
import unittest

from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app" / "streamlit_app.py"


def widget_by_label(widgets, label):
    """Return one Streamlit test widget by its user-visible label."""
    for widget in widgets:
        if widget.label == label:
            return widget
    raise AssertionError(f"widget not found: {label!r}")


class FragilityExplorerSmokeTest(unittest.TestCase):
    def setUp(self):
        self.app = AppTest.from_file(str(APP), default_timeout=30).run()
        self.assertEqual([], list(self.app.exception))

    def assert_clean_run(self):
        self.app.run()
        self.assertEqual([], list(self.app.exception))

    def test_expected_tabs_and_core_artifacts(self):
        self.assertEqual(
            [
                "N_e / GBF verdict",
                "Structure & diversity",
                "🐺 Wolf: load & ROH",
                "About / limitations",
            ],
            [tab.label for tab in self.app.tabs],
        )
        self.assertGreaterEqual(len(self.app.metric), 10)
        subheaders = [element.value for element in self.app.subheader]
        self.assertIn("Fragility scorecard — what survives the sensitivity tests?", subheaders)
        self.assertIn("What evidence would change the conclusion?", subheaders)

    def test_all_peafowl_filter_structure_states(self):
        for preset in ("lenient", "standard", "strict"):
            widget_by_label(self.app.select_slider, "Filtering stringency").set_value(preset)
            self.assert_clean_run()

            widget_by_label(self.app.radio, "Population structure").set_value("pooled")
            self.assert_clean_run()

            widget_by_label(self.app.radio, "Population structure").set_value("per_population")
            self.assert_clean_run()

    def test_all_wolf_sensitivity_states(self):
        for threshold in (2, 3, 4):
            widget_by_label(
                self.app.select_slider, "GERP threshold — deleterious if RS >"
            ).set_value(threshold)
            self.assert_clean_run()

        for cutoff in (0.1, 0.5, 1.0, 1.5, 2.0):
            widget_by_label(
                self.app.select_slider, "ROH length cutoff (Mb) — counts as inbreeding"
            ).set_value(cutoff)
            self.assert_clean_run()


if __name__ == "__main__":
    unittest.main()
