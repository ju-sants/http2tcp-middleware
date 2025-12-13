import importlib
import threading
import dotenv
dotenv.load_dotenv()

from app.config.settings import settings
from app.core.logger import get_logger

logger = get_logger(__name__)

def main():
    """
    Starting point of all application.

    Here threads are initiated, workers start working, ports are open, and listeners are put to listen.
    """

    # FIRST PROCEDURE TO BE STARTED - WORKERS

    # FIRST: INPUT SOURCE WORKERS
    # This workers are defined as input source workers because
    # Its work is to fetch new location data, by HTTP, TCP or other types of connections
    # Decode it, structure it, and then forwards towards output layer of the application
    with logger.contextualize(log_label="SERVER"):

        # Get all input source workers, and they location at once
        for input_source, worker_location in settings.WORKERS_INPUT_SOURCE.items():
            module_path = worker_location.get("module_path")
            func_name = worker_location.get("func_name")

            logger.info(f"Initiating worker for the input source: {input_source}. Worker location: {module_path}.{func_name}")

            # Importing the worker module with import lib and his path
            target_module = importlib.import_module(module_path)
            if not target_module:
                logger.error(f"There was an error importing the module {module_path} for the input source {input_source} to initialize the worker.")
                continue
            
            # getting the worker function with getattr wich gets the worker function atribute of the module 
            target_func = getattr(target_module, func_name)
            if not target_func:
                logger.error(f"Worker function not defined in {module_path}. Please verify.")
                continue
            
            # Initiate the worker with a daemon thread
            threading.Thread(target=target_func, daemon=True).start()

        # Blocking the main thread, so the daemon ones can run freely and undefined    
        try:
            while True:
                threading.Event().wait(60) # Wait for not to consume CPU

        except KeyboardInterrupt: # if asked to stop
            logger.warning("server is being shut down...")

if __name__ == "__main__":
    main()