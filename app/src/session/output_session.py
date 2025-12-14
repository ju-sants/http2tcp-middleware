import socket
import threading
import importlib
import time

from app.core.logger import get_logger
from app.config.settings import settings
from app.src.output.output_mappers import output_mappers
from app.services.redis_service import get_redis

logger = get_logger(__name__)
redis_client = get_redis()

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

        # HeartBeat Timer
        # Using threading.Timer because it runs a thread internally that waits until the time has come
        # And executes the function defined here. Later, in _send_data method we reset this timer. 
        # Every time the device sends data.
        self._heartbeat_timer = threading.Timer(30, self._heartbeat) 

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
                with logger.contextualize(log_label=self.device_id):
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
            
    def _restore_heartbeat_timer(self):
        """
        Restores the internal heartbeat timer
        """

        try:
            # First we cancel the timer
            self._heartbeat_timer.cancel()
            
            # Then we clean the object from the memory
            self._heartbeat_timer = None
            
            # So on, we can create a new object, this "resets" the timer
            self._heartbeat_timer = threading.Timer(30, self._heartbeat) 
        
        except Exception as e:
            logger.error(f"There was an error resetting the heartbeat timer: {e}")
    
    def _heartbeat(self):
        """
        Sends a HeartBeat (HBT) packet to maintain the connection alive.
        Used if the device does'nt send data so often.
        """

        with logger.contextualize(log_label=self.device_id):
            # Get the heartbeat packet builder for the current output protocol
            packet_builder = output_mappers.OUTPUT_PACKET_BUILDERS.get(self.output_protocol, {}).get("heartbeat")
            if not packet_builder:
                logger.error(f"No HeartBeat packet builder defined for {self.output_protocol}.")
                return
            
            # Building the heartbeat packet
            heartbeat_packet = packet_builder(self.device_id)

            # Sending it
            self._send_data(heartbeat_packet, self.output_protocol, "heartbeat")

            # Returning a flag to threading.Timer
            return True
    
    def _handle_protocol_specific_behaviors(self, packet_type: str):
        """
        This method was implemented to handle protocol-specific before sending data
        """

        # Method to get the voltage of the device from his state storage
        def __get_device_voltage(self):
            """
            This is a very specific method, that allow the instance to retrieve voltage information
            from the device state storage
            """

            # Here, we can use the instance of a input sessions manager to retrieve this information
            # But for now, lets use the voltage saved on the redis state storage
            voltage = redis_client.hget(f"device:{self.input_source}:{self.device_id}", "voltage") or 1.11 # Default fallback value

            # returning it
            return float(voltage)

        # First the behaviors of GT06 output protocol
        if self.output_protocol == "gt06":
            if self._is_gt06_login_step and packet_type != "login":
                logger.info(f"Currently in GT06 login step, delaying data send.")
                
                while self._is_gt06_login_step:
                    time.sleep(0.1)

                logger.info(f"GT06 login step completed, proceeding to send heartbeat.")

                # Sending a heartbeat to the cold connection
                self._heartbeat()
            
            # For GT06 protocol, send a Voltage packet before location data
            if packet_type == "location":
                logger.info(f"Sending Voltage packet before location data for GT06 protocol.")

                # First lets get the voltage packet builder from the output protocol
                voltage_packet_builder = output_mappers.OUTPUT_PACKET_BUILDERS.get(self.output_protocol).get("info")
                if voltage_packet_builder:
                    # If there are a voltage packet builder, lets get the device last voltage information
                    voltage = __get_device_voltage()

                    # Now lets build it
                    voltage_packet = voltage_packet_builder(self.device_id, voltage=voltage, serial_number=0)
                    try:
                        # sending the voltage information packet
                        self.sock.sendall(voltage_packet)
                        logger.info(f"Sent Voltage packet to main server: {voltage_packet.hex()}")
                    except Exception as e:
                        logger.error(f"Failed to send Voltage packet to main server: {e}")
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
            self._handle_protocol_specific_behaviors(packet_type)

            # Send the actual data packet
            try:
                self.sock.sendall(data)
                logger.info(f"Sent data to main server: {data.hex()}")

                # Reseting the heartbeat timer
                self._restore_heartbeat_timer()

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


class OutputProcessor:
    """
    Processes outgoing data to be sent to the main server.
    """

    def __init__(self):
        self.sessions_manager = SessionsManager()

    def log_output_packet(self, device_id: str, input_source: str, output_protocol: str, output_packet: bytes, packet_type: str):
        """
        Log the output packet details.
        
        :param device_id: Device identifier
        :type device_id: str
        :param input_source: Input source module name
        :type input_source: str
        :param output_protocol: Output protocol type
        :type output_protocol: str
        :param output_packet: The output packet in bytes
        :type output_packet: bytes
        :param packet_type: Type of packet being sent (e.g., "location", "info")
        :type packet_type: str
        """

        if output_protocol == "suntech4g":
            visual_packet = output_packet.decode("ascii", errors="ignore") # The suntechs binary packets are just text encoded to ASCII table.
        elif output_protocol == "gt06":
            visual_packet = output_packet.hex() # GT06 packets are more complex and need to be logged as HEXADECIMAL

        logger.info(f"Prepared {packet_type} packet for device {device_id} using protocol {output_protocol} from input source {input_source}: {output_packet.hex()}")
        logger.info(f"Visual representation of the packet: {visual_packet}")

    def check_output_protocol(self, device_id: str) -> str:
        """
        Check and retrieve the output protocol for the given device ID from Redis.
        
        :param device_id: Device identifier
        :type device_id: str
        :return: Output protocol type
        :rtype: str
        """

        # Retrieving the device output protocol from the redis
        output_protocol = redis_client.hget(f"device:{device_id}", "output_protocol")

        # If it does'nt have one, we attribute a default to it.
        if not output_protocol:
            output_protocol = settings.DEFAULT_OUTPUT_PROTOCOL # Default output protocol defined in settings 
            logger.info(f"No output protocol found in Redis for device {device_id}. Using default: {output_protocol}")

            # Setting the output protocol for the next time it passes here
            redis_client.hset(f"device:{device_id}", "output_protocol", output_protocol)

        # returning the output protocol
        return output_protocol
    
    def create_output_packet(self, device_id: str, structured_data: dict, output_protocol: str, packet_type: str = "location") -> bytes:
        """
        Create an output packet based on the output protocol.
        
        :param device_id: Device identifier
        :type device_id: str
        :param data: A structured data dictionary to be converted to bytes
        :type data: dict
        :param output_protocol: Output protocol type
        :type output_protocol: str
        :param packet_type: Type of packet being sent (e.g., "location", "info")
        :type packet_type: str
        :return: Formatted output packet
        :rtype: bytes
        """

        # Based on the output protocol and the type of packet needed, we chase for the builder function
        # Who will builds the binary packet from the structured python dictionary
        packet_builder = output_mappers.OUTPUT_PACKET_BUILDERS.get(output_protocol, {}).get(packet_type)
        if not packet_builder:
            logger.error(f"No packet builder defined for protocol {output_protocol} and packet type {packet_type}.")
            return b""

        # Building the output_packet
        output_packet = packet_builder(device_id, structured_data, 0)
        
        # Returning it
        return output_packet
    
    def forward(self, device_id: str, structured_data: dict, input_source: str, packet_type: str = "location"):
        """
        Forward data to the main server via the appropriate session.
        
        :param device_id: Device identifier
        :type device_id: str
        :param input_source: Input source module name
        :type input_source: str
        :param output_protocol: Output protocol type
        :type output_protocol: str
        :param structured_data: A structured data dictionary to be converted to bytes
        :type data: dict
        :param packet_type: Type of packet being sent (e.g., "location", "info")
        :type packet_type: str
        """

        # Checking the output protocol
        output_protocol = self.check_output_protocol(device_id)

        # Creating the output packet
        output_packet = self.create_output_packet(device_id, structured_data, output_protocol, packet_type)

        # Logging it
        self.log_output_packet(device_id, input_source, output_protocol, output_packet, packet_type)

        # Sending it
        self.sessions_manager.send_data(device_id, input_source, output_protocol, output_packet, packet_type)

# Instanciatig the global object "output_processor"
# All input sources MUST use only this object.
# To use this by only calling "output_processor.forward(*args)" 
output_processor = OutputProcessor()
