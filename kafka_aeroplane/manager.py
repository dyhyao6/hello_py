import subprocess
import sys
import time
import signal
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class SyncManager:
    def __init__(self):
        self.syncs = {
            "kafka_forwarder": {
                "name": "Kafka Forwarder",
                "script": "kafka_forwarder.py",
                "process": None
            },
            "flight_info": {
                "name": "Flight Info Sync",
                "script": "flight_info_sync.py",
                "process": None
            },
            "apron_stand_status": {
                "name": "Apron Stand Status Sync",
                "script": "apron_stand_status_sync.py",
                "process": None
            },
            "safeguard": {
                "name": "Safeguard Sync",
                "script": "safeguard_sync.py",
                "process": None
            }
        }
        self.running = True
        signal.signal(signal.SIGINT, self.handle_signal)
        signal.signal(signal.SIGTERM, self.handle_signal)
    
    def start(self, sync_name):
        if sync_name not in self.syncs:
            logger.error(f"Unknown sync '{sync_name}'")
            logger.info(f"Available syncs: {', '.join(self.syncs.keys())}")
            return False
        
        sync = self.syncs[sync_name]
        
        logger.info(f"Starting {sync['name']}...")
        
        try:
            process = subprocess.Popen(
                ["python", sync["script"]],
                stdout=None,
                stderr=None
            )
            self.syncs[sync_name]["process"] = process
            logger.info(f"{sync['name']} started successfully")
            return True
        except Exception as e:
            logger.error(f"Error starting {sync['name']}: {e}")
            return False
    
    def stop(self, sync_name):
        if sync_name not in self.syncs:
            logger.error(f"Unknown sync '{sync_name}'")
            logger.info(f"Available syncs: {', '.join(self.syncs.keys())}")
            return False
        
        sync = self.syncs[sync_name]
        
        logger.info(f"Stopping {sync['name']}...")
        
        try:
            if self.syncs[sync_name]["process"]:
                self.syncs[sync_name]["process"].terminate()
                self.syncs[sync_name]["process"].wait(timeout=5)
                self.syncs[sync_name]["process"] = None
            else:
                subprocess.run(
                    ["pkill", "-f", sync["script"]],
                    check=True
                )
            logger.info(f"{sync['name']} stopped successfully")
            return True
        except Exception as e:
            logger.error(f"Error stopping {sync['name']}: {e}")
            return False
    
    def restart(self, sync_name):
        logger.info(f"Restarting {sync_name}...")
        self.stop(sync_name)
        time.sleep(2)
        return self.start(sync_name)
    
    def start_all(self):
        logger.info("Starting all syncs...")
        success_count = 0
        for sync_name in self.syncs.keys():
            if self.start(sync_name):
                success_count += 1
            time.sleep(1)
        logger.info(f"\nStarted {success_count}/{len(self.syncs)} syncs")
        
        logger.info("Monitoring all syncs...")
        try:
            while self.running:
                all_stopped = True
                for sync_name, sync in self.syncs.items():
                    if sync["process"] and sync["process"].poll() is None:
                        all_stopped = False
                if all_stopped:
                    logger.warning("All syncs have stopped, exiting...")
                    break
                time.sleep(5)
        except KeyboardInterrupt:
            pass
        finally:
            self.stop_all()
    
    def stop_all(self):
        logger.info("Stopping all syncs...")
        success_count = 0
        for sync_name in self.syncs.keys():
            if self.stop(sync_name):
                success_count += 1
            time.sleep(0.5)
        logger.info(f"\nStopped {success_count}/{len(self.syncs)} syncs")
    
    def restart_all(self):
        logger.info("Restarting all syncs...")
        self.stop_all()
        time.sleep(2)
        self.start_all()
    
    def status(self):
        logger.info("Sync Status:")
        logger.info("-" * 50)
        for sync_name, sync in self.syncs.items():
            logger.info(f"  {sync['name']}: {sync_name}")
            if sync["process"] and sync["process"].poll() is None:
                logger.info(f"    Status: Running ✓")
            else:
                logger.info(f"    Status: Stopped ✗")
        logger.info("-" * 50)
    
    def list_syncs(self):
        logger.info("Available syncs:")
        logger.info("-" * 50)
        for sync_name, sync in self.syncs.items():
            logger.info(f"  {sync_name}: {sync['name']}")
            logger.info(f"    Script: {sync['script']}")
        logger.info("-" * 50)
    
    def handle_signal(self, signum, frame):
        logger.info(f"\nReceived signal {signum}, shutting down gracefully...")
        self.running = False
        self.stop_all()
        sys.exit(0)


def print_usage():
    logger.info("Usage: python manager.py <command> [sync_name]")
    logger.info("\nCommands:")
    logger.info("  start [sync]    - Start a specific sync (or all if not specified)")
    logger.info("  stop [sync]     - Stop a specific sync (or all if not specified)")
    logger.info("  restart [sync]  - Restart a specific sync (or all if not specified)")
    logger.info("  status          - Show status of all syncs")
    logger.info("  list            - List all available syncs")
    logger.info("\nAvailable syncs:")
    logger.info("  kafka_forwarder      - Kafka Forwarder")
    logger.info("  flight_info         - Flight Info Sync")
    logger.info("  apron_stand_status  - Apron Stand Status Sync")
    logger.info("  safeguard           - Safeguard Sync")
    logger.info("\nExamples:")
    logger.info("  python manager.py start kafka_forwarder")
    logger.info("  python manager.py stop all")
    logger.info("  python manager.py restart flight_info")
    logger.info("  python manager.py status")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(1)
    
    manager = SyncManager()
    command = sys.argv[1].lower()
    
    if command == "start":
        if len(sys.argv) > 2:
            manager.start(sys.argv[2])
        else:
            manager.start_all()
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
        manager.list_syncs()
    else:
        logger.error(f"Unknown command '{command}'")
        print_usage()
        sys.exit(1)