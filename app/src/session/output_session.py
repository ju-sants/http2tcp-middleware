import socket
import threading

from app.core.logger import get_logger
from app.config.settings import settings

logger = get_logger(__name__)

class MainServerSession:
    def __init__(self, device_id: str, input_source: str, output_protocol: str):
        self.device_id = device_id

        self.input_source = input_source
        self.output_protocol = output_protocol

        self.sock: socket.socket | None = None
        self.lock = threading.RLock()

        self._is_gt06_login_step = False
        self._is_connected = False
    
    def connect(self):
        """
        Establish connection to the main server based on the output protocol.
        """

        with self.lock:
            if self._is_connected:
                return True

            try:
                if not self.output_protocol:
                    logger.info(f"It is not possible to start connection to main server, output protocol type is not defined. input_source: {self.input_source}")
                    return
                
                address = settings.OUTPUT_PROTOCOL_HOST_ADRESSES.get(self.output_protocol)

                if not address:
                    logger.info(f"Unknown output protocol type: {self.output_protocol}. Cannot connect to main server. input_source: {self.input_source}")
                    return

                logger.info(f"Connecting to main server at {address} using protocol {self.output_protocol} input_source: {self.input_source}...")
                self.sock = socket.create_connection(address, timeout=5)
                self._is_connected = True

                logger.info(f"Initiating thread to listen for incoming data from main server...")
                threading.Thread(target=self._listen_to_server, daemon=True).start()

                self._present_connection()

                logger.info(f"Connection and listener thread established successfully.")

                return True
            
            except Exception as e:
                logger.error(f"Failed to connect to main server: {e}")
                self._is_connected = False
                
                return False