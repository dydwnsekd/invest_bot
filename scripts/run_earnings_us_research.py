"""Run the standalone earnings and US-market CSV research job."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from invest_bot.jobs.earnings_us_research import main

if __name__ == '__main__':
    main()
