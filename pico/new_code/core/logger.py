import os
import time
import gc

class Logger:
    # Log levels
    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50
    
    _level_names = {
        DEBUG: 'DEBUG',
        INFO: 'INFO',
        WARNING: 'WARNING',
        ERROR: 'ERROR',
        CRITICAL: 'CRITICAL'
    }
    
    def __init__(self, filename='device.log', max_size=8192, level=INFO):
        self.filename = filename
        self.max_size = max_size
        self.level = level
        self.buffer = []
        self.buffer_size = 50  # Keep last 50 messages in memory
        
        # Always start with a fresh log on boot
        try:
            # If old log exists, rename it
            if self.filename in os.listdir():
                try:
                    os.rename(self.filename, self.filename + '.old')
                except:
                    pass
            
            # Create new log
            with open(self.filename, 'w') as f:
                f.write(f"Log started at {self._get_timestamp()}\n")
        except Exception as e:
            print(f"Error initializing log: {str(e)}")
    
    def _get_timestamp(self):
        """Get current timestamp in readable format"""
        t = time.localtime()
        return "{:02d}:{:02d}:{:02d}".format(t[3], t[4], t[5])
    
    def _write_to_file(self, msg):
        """Write message to log file with size management"""
        try:
            # Check file size
            try:
                size = os.stat(self.filename)[6]
                if size > self.max_size:
                    # Rotate log file
                    try:
                        os.rename(self.filename, self.filename + '.old')
                    except:
                        pass
                    # Create new log
                    with open(self.filename, 'w') as f:
                        f.write(f"Log rotated at {self._get_timestamp()}\n")
            except:
                pass
            
            # Append message
            with open(self.filename, 'a') as f:
                f.write(msg + '\n')
        except:
            pass
        
        # Manage memory
        gc.collect()
    
    def _log(self, level, msg):
        """Internal logging function"""
        if level >= self.level:
            timestamp = self._get_timestamp()
            level_name = self._level_names.get(level, 'UNKNOWN')
            log_msg = f"[{timestamp}] {level_name}: {msg}"
            
            # Add to memory buffer
            self.buffer.append(log_msg)
            if len(self.buffer) > self.buffer_size:
                self.buffer.pop(0)
            
            # Write to file
            self._write_to_file(log_msg)
    
    def debug(self, msg):
        """Log debug message"""
        self._log(self.DEBUG, msg)
    
    def info(self, msg):
        """Log info message"""
        self._log(self.INFO, msg)
    
    def warning(self, msg):
        """Log warning message"""
        self._log(self.WARNING, msg)
    
    def error(self, msg):
        """Log error message"""
        self._log(self.ERROR, msg)
    
    def critical(self, msg):
        """Log critical message"""
        self._log(self.CRITICAL, msg)
    
    def get_logs(self, count=None):
        """Get recent logs from memory buffer"""
        if count is None:
            return self.buffer
        return self.buffer[-count:]
    
    def clear_logs(self):
        """Clear log file and memory buffer"""
        self.buffer = []
        try:
            with open(self.filename, 'w') as f:
                f.write(f"Log cleared at {self._get_timestamp()}\n")
        except:
            pass

# Create global logger instance
_logger = None

def get_logger(module_name=None):
    """Get or create global logger instance"""
    global _logger
    if _logger is None:
        _logger = Logger()
    return _logger 