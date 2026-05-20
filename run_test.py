from src.common.metrics import MetricsCollector
import time

m = MetricsCollector()
m.start_timer("test")
time.sleep(0.01)
m.stop_timer("test")
print("DONE")
