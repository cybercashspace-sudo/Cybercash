from kivy.metrics import dp
from kivy.utils import get_color_from_hex

# ==========================================================
# CYBER CASH FINTECH THEME
# ==========================================================

APP_NAME = "CYBER CASH"

# ----------------------------------------------------------
# Primary Colors
# ----------------------------------------------------------

PRIMARY = get_color_from_hex("#D4AF37")      # Gold
PRIMARY_DARK = get_color_from_hex("#B8860B")
PRIMARY_LIGHT = get_color_from_hex("#FFD95A")

# ----------------------------------------------------------
# Backgrounds
# ----------------------------------------------------------

BACKGROUND = get_color_from_hex("#0B0B0B")
BACKGROUND_LIGHT = get_color_from_hex("#161616")
SURFACE = get_color_from_hex("#1E1E1E")
CARD = get_color_from_hex("#222222")

# ----------------------------------------------------------
# Text
# ----------------------------------------------------------

TEXT_PRIMARY = get_color_from_hex("#FFFFFF")
TEXT_SECONDARY = get_color_from_hex("#BFBFBF")
TEXT_HINT = get_color_from_hex("#8A8A8A")

# ----------------------------------------------------------
# Status Colors
# ----------------------------------------------------------

SUCCESS = get_color_from_hex("#3CB371")
ERROR = get_color_from_hex("#FF5A5F")
WARNING = get_color_from_hex("#FFC107")
INFO = get_color_from_hex("#29B6F6")

# ----------------------------------------------------------
# Borders
# ----------------------------------------------------------

BORDER = get_color_from_hex("#3A3A3A")
DIVIDER = get_color_from_hex("#2B2B2B")

# ----------------------------------------------------------
# Glass Effect
# ----------------------------------------------------------

GLASS_BG = [1, 1, 1, 0.08]
GLASS_BORDER = [1, 1, 1, 0.15]

# ----------------------------------------------------------
# Radius
# ----------------------------------------------------------

RADIUS_SMALL = dp(10)
RADIUS_MEDIUM = dp(18)
RADIUS_LARGE = dp(28)
RADIUS_BUTTON = dp(32)

# ----------------------------------------------------------
# Elevation
# ----------------------------------------------------------

ELEVATION_LOW = 2
ELEVATION_MEDIUM = 4
ELEVATION_HIGH = 8

# ----------------------------------------------------------
# Spacing
# ----------------------------------------------------------

SPACE_4 = dp(4)
SPACE_8 = dp(8)
SPACE_12 = dp(12)
SPACE_16 = dp(16)
SPACE_20 = dp(20)
SPACE_24 = dp(24)
SPACE_32 = dp(32)

# ----------------------------------------------------------
# Font Sizes
# ----------------------------------------------------------

FONT_SMALL = "12sp"
FONT_NORMAL = "14sp"
FONT_MEDIUM = "16sp"
FONT_LARGE = "22sp"
FONT_TITLE = "28sp"
FONT_HERO = "34sp"

# ----------------------------------------------------------
# Animation
# ----------------------------------------------------------

ANIMATION_DURATION = 0.25
ANIMATION_FAST = 0.15
ANIMATION_SLOW = 0.40


class CyberTheme:
    GOLD = PRIMARY
    EMERALD = get_color_from_hex("#3CB371")
    DARK_BG = BACKGROUND
    CARD_BG = CARD
    SUCCESS = SUCCESS
    ERROR = ERROR
    BTC = get_color_from_hex("#F39C12")
