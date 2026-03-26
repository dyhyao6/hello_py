import subprocess
import sys
import os
import time
import signal
import logging
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class ProducerManager:
    def __init__(self):
        self.producers = {
            "passenger_baggage": {
                "name": "Passenger Baggage Producer",
                "script": "passenger_baggage_producer.py",
                "state_file": "state/passenger_baggage_state.json",
                "container_name": "passenger-baggage-producer",
                "image_name": "passenger-baggage-producer"
            },
            "face_vector": {
                "name": "Face Vector Producer",
                "script": "face_vector_producer.py",
                "state_file": "state/face_vector_state.json",
                "container_name": "face-vector-producer",
                "image_name": "face-vector-producer"
            },
            "xray_ocr": {
                "name": "X-ray OCR Producer",
                "script": "xray_ocr_producer.py",
                "state_file": "state/xray_ocr_state.json",
                "container_name": "xray-ocr-producer",
                "image_name": "xray-ocr-producer"
            }
        }
        self.processes = {}
        self.running = True
        signal.signal(signal.SIGINT, self.handle_signal)
        signal.signal(signal.SIGTERM, self.handle_signal)
    
    def start(self, producer_name):
        if producer_name not in self.producers:
            logger.error(f"Unknown producer '{producer_name}'")
            logger.info(f"Available producers: {', '.join(self.producers.keys())}")
            return False
        
        producer = self.producers[producer_name]
        
        logger.info(f"Starting {producer['name']}...")
        
        try:
            process = subprocess.Popen(
                ["python", producer["script"]],
                stdout=None,
                stderr=None
            )
            self.processes[producer_name] = process
            logger.info(f"{producer['name']} started successfully")
            return True
        except Exception as e:
            logger.error(f"Error starting {producer['name']}: {e}")
            return False
    
    def stop(self, producer_name):
        if producer_name not in self.producers:
            logger.error(f"Unknown producer '{producer_name}'")
            logger.info(f"Available producers: {', '.join(self.producers.keys())}")
            return False
        
        producer = self.producers[producer_name]
        
        logger.info(f"Stopping {producer['name']}...")
        
        try:
            if producer_name in self.processes:
                self.processes[producer_name].terminate()
                self.processes[producer_name].wait(timeout=5)
                del self.processes[producer_name]
            else:
                subprocess.run(
                    ["pkill", "-f", producer["script"]],
                    check=True
                )
            logger.info(f"{producer['name']} stopped successfully")
            return True
        except Exception as e:
            logger.error(f"Error stopping {producer['name']}: {e}")
            return False
    
    def restart(self, producer_name):
        logger.info(f"Restarting {producer_name}...")
        self.stop(producer_name)
        time.sleep(2)
        return self.start(producer_name)
    
    def start_all(self):
        logger.info("Starting all producers...")
        success_count = 0
        for producer_name in self.producers.keys():
            if self.start(producer_name):
                success_count += 1
            time.sleep(1)
        logger.info(f"\nStarted {success_count}/{len(self.producers)} producers")
    
    def stop_all(self):
        logger.info("Stopping all producers...")
        success_count = 0
        for producer_name in self.producers.keys():
            if self.stop(producer_name):
                success_count += 1
            time.sleep(0.5)
        logger.info(f"\nStopped {success_count}/{len(self.producers)} producers")
    
    def restart_all(self):
        logger.info("Restarting all producers...")
        self.stop_all()
        time.sleep(2)
        self.start_all()
    
    def status(self):
        logger.info("Producer Status:")
        logger.info("-" * 50)
        for producer_name, producer in self.producers.items():
            logger.info(f"  {producer['name']}: {producer_name}")
            if producer_name in self.processes and self.processes[producer_name].poll() is None:
                logger.info(f"    Status: Running ✓")
            else:
                logger.info(f"    Status: Stopped ✗")
            if os.path.exists(producer["state_file"]):
                logger.info(f"    State file: {producer['state_file']} ✓")
            else:
                logger.info(f"    State file: {producer['state_file']} ✗")
        logger.info("-" * 50)
    
    def list_producers(self):
        logger.info("Available producers:")
        logger.info("-" * 50)
        for producer_name, producer in self.producers.items():
            logger.info(f"  {producer_name}: {producer['name']}")
            logger.info(f"    Script: {producer['script']}")
            logger.info(f"    State file: {producer['state_file']}")
        logger.info("-" * 50)
    
    def monitor(self):
        logger.info("Monitoring producers...")
        try:
            while self.running:
                for producer_name, process in list(self.processes.items()):
                    if process.poll() is not None:
                        logger.warning(f"Producer {producer_name} stopped unexpectedly, restarting...")
                        self.start(producer_name)
                time.sleep(5)
        except KeyboardInterrupt:
            pass
        finally:
            self.stop_all()
    
    def handle_signal(self, signum, frame):
        logger.info(f"\nReceived signal {signum}, shutting down gracefully...")
        self.running = False
        self.stop_all()
        sys.exit(0)


def print_usage():
    logger.info("Usage: python manager.py <command> [producer_name]")
    logger.info("\nCommands:")
    logger.info("  start [producer]    - Start a specific producer (or all if not specified)")
    logger.info("  stop [producer]     - Stop a specific producer (or all if not specified)")
    logger.info("  restart [producer]  - Restart a specific producer (or all if not specified)")
    logger.info("  status              - Show status of all producers")
    logger.info("  list                - List all available producers")
    logger.info("\nAvailable producers:")
    logger.info("  passenger_baggage   - Passenger Baggage Producer")
    logger.info("  face_vector        - Face Vector Producer")
    logger.info("  xray_ocr          - X-ray OCR Producer")
    logger.info("\nExamples:")
    logger.info("  python manager.py start passenger_baggage")
    logger.info("  python manager.py stop all")
    logger.info("  python manager.py restart face_vector")
    logger.info("  python manager.py status")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(1)
    
    manager = ProducerManager()
    command = sys.argv[1].lower()
    
    if command == "start":
        if len(sys.argv) > 2:
            manager.start(sys.argv[2])
            manager.monitor()
        else:
            manager.start_all()
            manager.monitor()
    elif command == "stop":
        if len(sys.argv) > 2:
            manager.stop(sys.argv[2])
        else:
            manager.stop_all()
    elif command == "restart":
        if len(sys.argv) > 2:
            manager.restart(sys.argv[2])
        else:
            manager.restart_all()
    elif command == "status":
        manager.status()
    elif command == "list":
        manager.list_producers()
    else:
        logger.error(f"Unknown command '{command}'")
        print_usage()
        sys.exit(1)
