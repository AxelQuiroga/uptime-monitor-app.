from uptime.app import create_app
from uptime.models import Target
from uptime.checker import check_url
from apscheduler.schedulers.blocking import BlockingScheduler

app = create_app()
scheduler = BlockingScheduler()

def run_checks():
    with app.app_context():
        targets = Target.query.filter_by(is_active=True).all()
        print(f"Checking {len(targets)} targets...")
        for target in targets:
            result = check_url(target)
            status = "UP" if result.is_up else "DOWN"
            lat = f"{result.latency_ms:.0f}ms" if result.latency_ms else "N/A"
            print(f"  [{status}] {target.url} - {lat}")

@scheduler.scheduled_job("interval", seconds=30)
def scheduled_check():
    run_checks()

if __name__ == "__main__":
    print("Checker started (every 30s)")
    scheduler.start()
