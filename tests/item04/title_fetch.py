"""Real public title lookup, PDF download and parsing; no local PDF substitution."""
import argparse
import json
import time
from common import BASE, client, wait_task, write

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', required=True)
    parser.add_argument('titles', nargs='+')
    args = parser.parse_args()
    output = BASE/args.run
    output.mkdir(parents=True, exist_ok=False)
    with client() as c:
        for i, title in enumerate(args.titles, 1):
            started = time.monotonic()
            response = c.post('/api/v2/acquisition/tasks', json={'title': title})
            response.raise_for_status()
            task = wait_task(c, response.json()['id'], output/f'{i}-task.json')
            proof = {'title':title, 'elapsed_seconds':round(time.monotonic()-started,3),'task':task}
            if task['result'] and task['result'].get('succeeded'):
                pid = task['result']['succeeded'][0]['paper_id']
                reading = c.get('/api/v2/papers/'+pid+'/reading'); reading.raise_for_status()
                proof['reading'] = reading.json()
            write(output/f'{i}-result.json', proof)
            print(json.dumps({'title':title, 'status':task['status'], 'seconds':proof['elapsed_seconds']},ensure_ascii=False),flush=True)
