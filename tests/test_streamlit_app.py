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


def optional_widget_by_label(widgets, label):
    """Return a widget when its optional, precomputed Phase-5B artifact exists."""
    for widget in widgets:
        if widget.label == label:
            return widget
    return None


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
        self.assertIn("ROH localization of homozygous GERP-weighted derived-allele burden", subheaders)

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
                self.app.select_slider, "GERP threshold — include sites with RS >"
            ).set_value(threshold)
            self.assert_clean_run()

        for cutoff in (0.1, 0.5, 1.0, 1.5, 2.0):
            widget_by_label(
                self.app.select_slider, "ROH length cutoff (Mb) — autozygosity proxy"
            ).set_value(cutoff)
            self.assert_clean_run()

    def test_phase5b_design_damage_and_localization_controls(self):
        design_truth = optional_widget_by_label(self.app.selectbox, "Known scenario N_e")
        design_density = optional_widget_by_label(self.app.selectbox, "Scenario marker density")
        design_outcome = optional_widget_by_label(self.app.selectbox, "Decision outcome")
        if design_truth is not None:
            widget_by_label(self.app.selectbox, "Known scenario N_e").set_value(500)
            self.assert_clean_run()
            boundary_outcomes = (
                "boundary_confident_pass_rate", "indeterminate_rate",
                "boundary_confident_fail_rate",
            )
            self.assertEqual(
                ("Boundary Confident Pass", "Indeterminate", "Boundary Confident Fail"),
                tuple(widget_by_label(self.app.selectbox, "Decision outcome").options),
            )
            for outcome in boundary_outcomes:
                widget_by_label(self.app.selectbox, "Decision outcome").set_value(outcome)
                self.assert_clean_run()
            for truth in (100, 1000):
                widget_by_label(self.app.selectbox, "Known scenario N_e").set_value(truth)
                self.assert_clean_run()
                self.assertEqual(
                    ("Correct Confident", "Indeterminate", "Incorrect Confident"),
                    tuple(widget_by_label(self.app.selectbox, "Decision outcome").options),
                )
            for density in (250, 1000):
                widget_by_label(self.app.selectbox, "Scenario marker density").set_value(density)
                self.assert_clean_run()
            for outcome in (
                "correct_confident_rate", "indeterminate_rate", "incorrect_confident_rate",
            ):
                widget_by_label(self.app.selectbox, "Decision outcome").set_value(outcome)
                self.assert_clean_run()
        else:
            self.assertIsNone(design_density)
            self.assertIsNone(design_outcome)

        damage_variant = optional_widget_by_label(
            self.app.radio, "Variant set for the effect table"
        )
        if damage_variant is not None:
            for variant in ("all_snp", "transversion_only"):
                widget_by_label(
                    self.app.radio, "Variant set for the effect table"
                ).set_value(variant)
                self.assert_clean_run()

        localization_gerp = optional_widget_by_label(
            self.app.selectbox, "Localization GERP threshold"
        )
        localization_roh = optional_widget_by_label(
            self.app.selectbox, "Localization ROH cutoff (Mb)"
        )
        if localization_gerp is None:
            self.assertIsNone(localization_roh)
            info_messages = [element.value for element in self.app.info]
            self.assertTrue(
                any("ROH-localization table not built" in message for message in info_messages)
            )
        else:
            for threshold in (2.0, 3.0, 4.0):
                widget_by_label(
                    self.app.selectbox, "Localization GERP threshold"
                ).set_value(threshold)
                self.assert_clean_run()
            for cutoff in (0.1, 0.5, 1.0, 1.5, 2.0):
                widget_by_label(
                    self.app.selectbox, "Localization ROH cutoff (Mb)"
                ).set_value(cutoff)
                self.assert_clean_run()


if __name__ == "__main__":
    unittest.main()
