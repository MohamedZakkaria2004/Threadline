"""Run actual-model acceptance sequentially against the already running app.

Creates synthetic local demo requests. Never run this alongside other inference
evaluations on a memory-constrained laptop. Stop at the first failed suite.
"""
import subprocess
import sys


def main():
    suites = [
        ['scripts.review_live_evaluate', '--output', 'phase2-final-rag-evaluation.json'],
        ['scripts.phase2_live_evaluate'],
        ['scripts.adversarial_evaluate', '--output', 'phase2-adversarial-evaluation.json'],
        ['scripts.phase2_storage_check'],
    ]
    for suite in suites:
        completed = subprocess.run([sys.executable, '-m', *suite], check=False)
        if completed.returncode:
            raise SystemExit(completed.returncode)


if __name__ == '__main__':
    main()
