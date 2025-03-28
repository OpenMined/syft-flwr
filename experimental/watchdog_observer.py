from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import time
import sys
import os
import platform
import psutil  # For system monitoring

class WatcherHandler(FileSystemEventHandler):
    def on_any_event(self, event):
        print(f"Event Type: {event.event_type} | Path: {event.src_path}")

def check_system_limits():
    try:
        process = psutil.Process(os.getpid())
        open_files = len(process.open_files())
        pid_count = len(psutil.pids())

        # Inotify limits (Linux only)
        if platform.system() == "Linux":
            with open("/proc/sys/fs/inotify/max_user_watches", "r") as f:
                max_watches = int(f.read().strip())
            with open("/proc/sys/fs/inotify/max_user_instances", "r") as f:
                max_instances = int(f.read().strip())
            with open("/proc/sys/fs/inotify/max_queued_events", "r") as f:
                max_queued = int(f.read().strip())

            # Count inotify descriptors safely
            inotify_watches = sum(
                1 for fd in os.listdir("/proc/self/fd")
                if os.path.exists(f"/proc/self/fd/{fd}") and "anon_inode:inotify" in os.readlink(f"/proc/self/fd/{fd}")
            )

            print(f"Inotify: {inotify_watches}/{max_watches} watches, {max_instances} instances, {max_queued} queued")

        print(f"Open files: {open_files}, PID count: {pid_count}")

        if inotify_watches >= max_watches - 10:
            print("⚠️ WARNING: Approaching inotify watch limit!")

    except Exception as e:
        print(f"Error checking system limits: {e}")

def main(directory):
    if not os.path.exists(directory):
        print(f"Error: Directory '{directory}' does not exist!")
        sys.exit(1)

    event_handler = WatcherHandler()
    observer = Observer()
    print(f"Using Observer: {type(observer).__name__}")
    print(f"Running on: {platform.system()} {platform.release()}")
    observer.schedule(event_handler, directory, recursive=True)
    observer.start()

    print(f"Watching directory: {directory}")
    
    try:
        while True:
            check_system_limits()
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        print("Stopped Watching.")
    
    observer.join()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python watchdog_monitor.py <directory_to_watch>")
        sys.exit(1)

    main(sys.argv[1])
