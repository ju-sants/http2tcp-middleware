import socket
import threading
import importlib

from app.core.logger import get_logger
from app.config.settings import settings
from app.src.output.output_mappers import output_mappers

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
    
    def disconnect(self):
        """
        Disconnect from the main server.
        """

        with self.lock:
            if not self._is_connected:
                return

            try:
                if self.sock:
                    try:
                        self.sock.shutdown(socket.SHUT_RDWR)
                    except Exception as e:
                        logger.warning(f"Error during socket shutdown: {e}")
                        pass

                    self.sock.close()
                    self.sock = None

                self._is_connected = False
                logger.info(f"Disconnected from main server.")

            except Exception as e:
                logger.error(f"Error while disconnecting from main server: {e}")

    def _present_connection(self):
        """
        Send initial data to present the connection to the main server.
        This is protocol-specific.
        """

        packet_builder = output_mappers.OUTPUT_PACKET_BUILDERS.get(self.output_protocol).get("login")
        if not packet_builder:
            logger.warning(f"No login packet builder defined for protocol {self.output_protocol}. Skipping login step.")
            return
        
        if self.output_protocol == "gt06":
            logger.info(f"Initiating GT06 login...")
            self._is_gt06_login_step = True

        elif self.output_protocol == "suntech4g":
            logger.info(f"Sending Suntech4G MNT login packet...")
        
        login_packet = packet_builder(self.device_id, 0)
        self._send_data(login_packet, self.output_protocol, "login")

        logger.info(f"Login packet sent for protocol {self.output_protocol}.")
    
    def _listen_to_server(self):
        """
        Listen for incoming data from the main server.
        """

        while self._is_connected:
            try:
                if not self.sock:
                    logger.error(f"Socket is not connected. Cannot listen to server.")
                    return

                data = self.sock.recv(4096)
                if not data:
                    logger.warning(f"Connection to main server lost.")
                    self.disconnect()
                    return

                if self._is_gt06_login_step and packet_type != "login":
                    logger.info(f"GT06 login step completed.")
                    self._is_gt06_login_step = False
                    continue

                mapper_func = output_mappers.OUTPUT_COMMAND_MAPPERS.get(self.output_protocol)
                if not mapper_func:
                    logger.warning(f"No command mapper defined for protocol {self.output_protocol}. Cannot process incoming data.")
                    continue

                universal_command = mapper_func(data)
                if not universal_command:
                    logger.warning(f"Failed to map incoming data to universal command for protocol {self.output_protocol}.")
                    continue

                target_module = importlib.import_module(f"app.src.input.{self.input_source}.builder")
                builder_func = getattr(target_module, f"process_command", None)
                if not builder_func:
                    logger.warning(f"No command processor defined in module for protocol {self.output_protocol}.")
                    continue

                logger.info(f"Routing command to input processor {self.input_source} for protocol {self.output_protocol}.")
                builder_func(self.device_id, universal_command)

            except socket.timeout:
                continue

            except (ConnectionResetError, BrokenPipeError):
                logger.warning(f"Connection to main server was reset.")
                self.disconnect()
                return
            
            except OSError as e:
                logger.error(f"OS error while listening to server: {e}")
                if e.errno in [9, 57, 104]:  # Bad file descriptor, Socket is not connected, Connection reset by peer
                    logger.warning(f"Caught Bad file descriptor or connection reset error. Disconnecting...")
                
                self.disconnect()
                return
            
            except Exception as e:
                logger.error(f"Unexpected error while listening to server: {e}")
                self.disconnect()
                return