import importlib
import threading
import dotenv
dotenv.load_dotenv()

from app.config.settings import settings
from app.core.logger import get_logger

logger = get_logger(__name__)

def main():
    """
    Docstring for main
    """

    with logger.contextualize(log_label="SERVER"):
        for input_source, worker_location in settings.WORKERS_INPUT_SOURCE.items():
            module_path = worker_location.get("module_path")
            func_name = worker_location.get("func_name")

            logger.info(f"Initiating worker for the input source: {input_source}. Worker location: {module_path}.{func_name}")

            target_module = importlib.import_module(module_path)
            if not target_module:
                logger.error(f"There was an error importing the module {module_path} for the input source {input_source} to initialize the worker.")
                continue

            target_func = getattr(target_module, func_name)
            if not target_func:
                logger.error(f"Worker function not defined in {module_path}. Please verify.")
                continue

            threading.Thread(target=target_func, daemon=True).start()

    
        try:
            while True:
                threading.Event().wait(60) # Wait for not to consume CPU
        except KeyboardInterrupt:
            logger.warning("server is being shut down...")

if __name__ == "__main__":
    main()