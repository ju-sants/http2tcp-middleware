import socket
import threading
import importlib
import time

from app.core.logger import get_logger
from app.config.settings import settings
from app.src.output.output_mappers import output_mappers

logger = get_logger(__name__)

# This class manages the session with the main server
# It handles connection, disconnection, sending and receiving data
# It also manages protocol-specific behaviors
# Such as login steps and packet formatting
class MainServerSession:
    def __init__(self, device_id: str, input_source: str, output_protocol: str):

        # Device identifier
        self.device_id = device_id

        # Input source module name (e.g., "mt02", "suntech4g")
        self.input_source = input_source
        self.output_protocol = output_protocol # Output protocol type (e.g., "gt06", "suntech4g")

        # Socket for TCP communication with the main server
        self.sock: socket.socket | None = None
        self.lock = threading.RLock() # To manage concurrent access to the socket and use recursive calls

        # State flags
        self._is_gt06_login_step = False # Flag to indicate if in GT06 login step
        self._is_connected = False # Flag to indicate if connected to the main server
    
    def connect(self):
        """
        Establish connection to the main server based on the output protocol.
        """

        with self.lock: # Ensure thread-safe access
            if self._is_connected:
                return True

            try:
                if not self.output_protocol:
                    logger.info(f"It is not possible to start connection to main server, output protocol type is not defined. input_source: {self.input_source}")
                    return
                
                # Get the server address based on the output protocol
                address = settings.OUTPUT_PROTOCOL_HOST_ADRESSES.get(self.output_protocol)

                if not address:
                    logger.info(f"Unknown output protocol type: {self.output_protocol}. Cannot connect to main server. input_source: {self.input_source}")
                    return

                logger.info(f"Connecting to main server at {address} using protocol {self.output_protocol} input_source: {self.input_source}...")
                self.sock = socket.create_connection(address, timeout=5)
                self._is_connected = True

                # Start a thread to listen for incoming data from the main server
                logger.info(f"Initiating thread to listen for incoming data from main server...")
                threading.Thread(target=self._listen_to_server, daemon=True).start()
                
                # Initiate protocol-specific connection presentation
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
                        self.sock.shutdown(socket.SHUT_RDWR) # Shutdown both send and receive
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
        
        # Get the login packet builder for the current output protocol
        packet_builder = output_mappers.OUTPUT_PACKET_BUILDERS.get(self.output_protocol).get("login")
        if not packet_builder:
            logger.warning(f"No login packet builder defined for protocol {self.output_protocol}. Skipping login step.")
            return
        
        if self.output_protocol == "gt06":
            logger.info(f"Initiating GT06 login...")
            self._is_gt06_login_step = True

        elif self.output_protocol == "suntech4g":
            logger.info(f"Sending Suntech4G MNT login packet...")
        
        # Build and send the login packet
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

                data = self.sock.recv(4096) # Receive up to 4096 bytes
                if not data:
                    logger.warning(f"Connection to main server lost.")
                    self.disconnect()
                    return

                # If in GT06 login step and data is received, consider login step complete
                if self._is_gt06_login_step:
                    logger.info(f"GT06 login step completed.")
                    self._is_gt06_login_step = False
                    continue
                
                # Else process the incoming data as a command
                mapper_func = output_mappers.OUTPUT_COMMAND_MAPPERS.get(self.output_protocol)
                if not mapper_func:
                    logger.warning(f"No command mapper defined for protocol {self.output_protocol}. Cannot process incoming data.")
                    continue
                
                # Map the incoming data to a universal command format
                universal_command = mapper_func(data)
                if not universal_command:
                    logger.warning(f"Failed to map incoming data to universal command for protocol {self.output_protocol}.")
                    continue
                
                # Dynamically import the target input module's command processor
                target_module = importlib.import_module(f"app.src.input.{self.input_source}.builder")
                builder_func = getattr(target_module, f"process_command", None)
                if not builder_func:
                    logger.warning(f"No command processor defined in module for protocol {self.output_protocol}.")
                    continue
                
                # Forward the universal command to the input processor
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
            
    def _send_data(self, data: bytes, current_output_protocol: str = None, packet_type: str = "location"):
        """
        Send data to the main server.
        
        :param data: Data to send
        :type data: bytes
        """

        with self.lock:
            if not self._is_connected or not self.sock:
                if not self.connect():
                    logger.error(f"Cannot send data, not connected to main server.")
                    return

            # Check if output protocol has changed
            if current_output_protocol and current_output_protocol.lower() != self.output_protocol:
                logger.warning(f"Output protocol changed from {self.output_protocol} to {current_output_protocol}. Reconnecting...")
                
                self.disconnect()
                self.output_protocol = current_output_protocol
                if not self.connect():
                    logger.error(f"Reconnection failed after output protocol change.")
                    return
            
            # Handle protocol-specific behaviors before sending data
            if self._is_gt06_login_step and packet_type != "login":
                logger.info(f"Currently in GT06 login step, delaying data send.")
                
                while self._is_gt06_login_step:
                    time.sleep(0.1)

                logger.info(f"GT06 login step completed, proceeding to send data.")

            # For GT06 protocol, send a Voltage packet before location data
            if self.output_protocol == "gt06" and packet_type == "location":
                logger.info(f"Sending Voltage packet before location data for GT06 protocol.")
                voltage_packet_builder = output_mappers.OUTPUT_PACKET_BUILDERS.get(self.output_protocol).get("info")
                if voltage_packet_builder:
                    voltage_packet = voltage_packet_builder(self.device_id, voltage=1.11, serial_number=0)
                    try:
                        self.sock.sendall(voltage_packet)
                        logger.info(f"Sent Voltage packet to main server: {voltage_packet.hex()}")
                    except Exception as e:
                        logger.error(f"Failed to send Voltage packet to main server: {e}")
                        self.disconnect()
                        return
            
            # Send the actual data packet
            try:
                self.sock.sendall(data)
                logger.info(f"Sent data to main server: {data.hex()}")

            except Exception as e:
                logger.error(f"Failed to send data to main server: {e}")
                self.disconnect()


class SessionsManager:
    """
    Manages multiple MainServerSession instances.
    """

    def __init__(self):
        self.sessions = {}
        self.lock = threading.RLock() # To manage concurrent access to the sessions dictionary

    def get_session(self, device_id: str, input_source: str, output_protocol: str) -> MainServerSession:
        """
        Retrieve or create a session for the given device ID.
        
        :param device_id: Device identifier
        :type device_id: str
        :param input_source: Input source module name
        :type input_source: str
        :param output_protocol: Output protocol type
        :type output_protocol: str
        :return: MainServerSession instance
        :rtype: MainServerSession
        """

        with self.lock:
            if device_id not in self.sessions: # Create a new session if it doesn't exist
                logger.info(f"Creating new session for device ID {device_id}.")

                self.sessions[device_id] = MainServerSession(device_id, input_source, output_protocol)
            
            return self.sessions[device_id]
    
    def remove_session(self, device_id: str):
        """
        Remove and disconnect the session for the given device ID.
        
        :param device_id: Device identifier
        :type device_id: str
        """

        with self.lock:
            session = self.sessions.pop(device_id, None)
            if session:
                session.disconnect()

                logger.info(f"Session for device ID {device_id} removed and disconnected.")

    def exists(self, device_id: str) -> bool:
        """
        Check if a session exists for the given device ID.
        
        :param device_id: Device identifier
        :type device_id: str
        :return: Boolean indicating existence of session
        :rtype: bool
        """

        with self.lock:
            if device_id in self.sessions:
                socket_obj = self.sessions[device_id].sock # Get the socket object
                if socket_obj is None:
                    return False
                
                try:
                    socket_obj.getpeername() # Check if socket is connected
                    return socket_obj.fileno() != -1 # Check if socket is valid
                except socket.error:
                    return False
                
            return False
        
    def send_data(self, device_id: str, input_source: str, output_protocol: str, data: bytes, packet_type: str = "location"):
        """
        Send data through the session for the given device ID.
        
        :param device_id: Device identifier
        :type device_id: str
        :param input_source: Input source module name
        :type input_source: str
        :param output_protocol: Output protocol type
        :type output_protocol: str
        :param data: Data to send
        :type data: bytes
        :param packet_type: Type of packet being sent (e.g., "location", "info")
        :type packet_type: str
        """

        # Retrieve the session from the manager
        session = self.get_session(device_id, input_source, output_protocol)

        # Send the data using the session's send method
        session._send_data(data, current_output_protocol=output_protocol, packet_type=packet_type)