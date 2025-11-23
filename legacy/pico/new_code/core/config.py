from micropython import const

# Display Pins - Using RP2350 dedicated SPI1
PIN_SPI_SCK = const(10)    # SPI1 SCK
PIN_SPI_MOSI = const(11)   # SPI1 TX
PIN_SPI_MISO = const(12)   # SPI1 RX
PIN_DC = const(13)         # Data/Command
PIN_RST = const(14)        # Reset
PIN_CS = const(15)         # Chip Select
PIN_LED = const(16)        # Backlight

# Touch Controller Pins - Using RP2350 dedicated I2C0
PIN_TOUCH_SDA = const(0)    # I2C0 SDA
PIN_TOUCH_SCL = const(1)    # I2C0 SCL
PIN_TOUCH_INT = const(2)    # Interrupt
PIN_TOUCH_RST = const(3)    # Reset

# Rotary Encoder Pins
PIN_ROT_CLK = const(20)
PIN_ROT_DT = const(21)
PIN_ROT_SW = const(22)

# Display Configuration
DISPLAY_WIDTH = const(480)
DISPLAY_HEIGHT = const(320)
DISPLAY_ROTATION = const(0)
SPI_BAUDRATE = const(125000000)  # 125MHz for RP2350

# Touch Configuration
TOUCH_I2C_FREQ = const(400000)  # 400kHz I2C
TOUCH_DEBOUNCE_MS = const(100)

# Rotary Encoder Configuration
ENCODER_MIN_VAL = const(0)
ENCODER_MAX_VAL = const(65535)
ENCODER_STEP = const(4096)
ENCODER_DEBOUNCE_MS = const(5)

# UI Configuration
LEFT_PANEL_WIDTH = const(160)  # Width of app list panel
CENTER_PANEL_WIDTH = const(220)  # Width of center info panel
RIGHT_PANEL_WIDTH = const(100)  # Width of right button panel
ICON_SIZE = const(60)  # Size of each app icon
ICON_SPACING = const(10)  # Space between icons
GRID_COLS = const(2)  # Number of columns
GRID_ROWS = const(3)  # Number of visible rows

# Colors (RGB565 format)
COLOR_BLACK = const(0x0000)
COLOR_WHITE = const(0xFFFF)
COLOR_RED = const(0xF800)
COLOR_GREEN = const(0x07E0)
COLOR_BLUE = const(0x001F)
COLOR_GRAY = const(0x7BEF)
COLOR_DARK_GRAY = const(0x39E7)

# UI States
class UIState:
    BOOT = 0
    CONNECTING = 1
    SIMPLE_MEDIA = 2
    FULL_UI = 3
    ERROR = 4

# Communication Configuration
SERIAL_BUFFER_SIZE = const(1024)
SERIAL_TIMEOUT_MS = const(100)
RECONNECT_DELAY_MS = const(1000)
HEARTBEAT_INTERVAL_MS = const(5000)

# Icon Data Markers
ICON_START_MARKER = b'<ICON_START>'
ICON_END_MARKER = b'<ICON_END>'

# Logging Configuration
LOG_FILENAME = 'device.log'
LOG_MAX_SIZE = const(8192)  # 8KB
LOG_BUFFER_SIZE = const(50)  # Number of messages to keep in memory

# Error Codes
class ErrorCode:
    NONE = 0
    DISPLAY_INIT_FAILED = 1
    TOUCH_INIT_FAILED = 2
    ENCODER_INIT_FAILED = 3
    SERIAL_INIT_FAILED = 4
    HID_INIT_FAILED = 5
    CONNECTION_LOST = 6

# Message Types
class MessageType:
    TEST = "test"
    CONNECTED = "connected"
    INITIAL_CONFIG = "initial_config"
    ICON_DATA = "icon_data"
    APP_CHANGES = "app_changes"
    VOLUME_UPDATE = "volume_update"
    ERROR = "error"
    HEARTBEAT = "heartbeat"
    TEST_RESPONSE = "test_response"
    READY = "ready" 