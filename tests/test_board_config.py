"""Static regression checks for revision-specific firmware configuration."""
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


class AmoledRevisionPinTests(unittest.TestCase):
    def test_v1_and_v2_keep_separate_lcd_chip_select_pins(self):
        source = (ROOT / "firmware/main/board_amoled_1_64.c").read_text()
        branch = re.search(
            r"#if TABY_HARDWARE_AMOLED_1_64_V2.*?"
            r"#define PIN_NUM_LCD_CS GPIO_NUM_(\d+).*?"
            r"#else\s*#define PIN_NUM_LCD_CS GPIO_NUM_(\d+)\s*#endif",
            source,
            re.DOTALL,
        )
        self.assertIsNotNone(branch, "Missing isolated V1.1/V2 LCD_CS branch")
        self.assertEqual(branch.groups(), ("46", "9"))


if __name__ == "__main__":
    unittest.main()
