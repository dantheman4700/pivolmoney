from micropython import const

# Display Pins
PIN_SPI_SCK = const(18)    # Pin 7 on LCD
PIN_SPI_MOSI = const(19)   # Pin 6 on LCD
PIN_SPI_MISO = const(16)   # Pin 9 on LCD
PIN_DC = const(20)         # Pin 5 on LCD
PIN_RST = const(21)        # Pin 4 on LCD
PIN_CS = const(17)         # Pin 3 on LCD
PIN_LED = const(22)        # Pin 8 on LCD

# Touch Controller Pins
PIN_TOUCH_SDA = const(4)   # GP4
PIN_TOUCH_SCL = const(5)   # GP5
PIN_TOUCH_INT = const(6)   # GP6
PIN_TOUCH_RST = const(7)   # GP7

# Rotary Encoder Pins
PIN_ROT_CLK = const(14)
PIN_ROT_DT = const(15)
PIN_ROT_SW = const(13)

# Display Configuration
DISPLAY_WIDTH = const(480)
DISPLAY_HEIGHT = const(320)
DISPLAY_ROTATION = const(0)
SPI_BAUDRATE = const(62500000)  # 62.5MHz

# Touch Configuration
TOUCH_I2C_FREQ = const(100000)
TOUCH_DEBOUNCE_MS = const(100)

# Rotary Encoder Configuration
ENCODER_MIN_VAL = const(0)
ENCODER_MAX_VAL = const(65535)
ENCODER_STEP = const(4096)
ENCODER_DEBOUNCE_MS = const(5)

# UI Configuration
LEFT_PANEL_WIDTH = const(360)
RIGHT_PANEL_WIDTH = const(120)
ICON_SIZE = const(48)
ICON_SPACING = const(10)
GRID_COLS = const(3)
GRID_ROWS = const(4)

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