"""Observe a task created with the actual browser, without creating another."""
import argparse
from common import BASE, client, wait_task
if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('identity');p.add_argument('run');a=p.parse_args()
    with client() as c:
        task=wait_task(c,a.identity,BASE/a.run/'task.json')
        print(task['status'])
